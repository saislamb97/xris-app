import os
import re
import subprocess
import numpy as np
from pathlib import Path
from datetime import datetime
from collections import defaultdict
import uuid
from django.utils.timezone import make_aware
from django.conf import settings
from celery import shared_task
import logging
from datasets.models import XmprData as DatasetXmprData
from processor.models import XmprData as ProcessorXmprData

from processor.utils.formatter import TranslateFormat
from processor.utils.coordinates import CoordinateSystem
from processor.utils.gdal_tools import ModGdal
from processor.utils.image import ascii2img
from processor.utils.file_ops import file_delete, move_row_files, move_csv_files
logger = logging.getLogger(__name__)


# Constants
SOURCE_DIR = Path(settings.MEDIA_ROOT).resolve()
TARGET_EXTS = ['.csv', '.png', '.tif', '.tiff']

TARGET_DIRS = [
    SOURCE_DIR / "converted",
    SOURCE_DIR / "images" / "png",
    SOURCE_DIR / "images" / "tif",
]


def get_file_key_and_datetime(filename):
    pattern = re.compile(r"(?P<key>\d{8}_\d{6}_[^_]+_\d{3})\.(csv|png|tif|tiff)", re.IGNORECASE)
    match = pattern.match(filename)
    if match:
        key = match.group("key")
        try:
            dt = make_aware(datetime.strptime("_".join(key.split("_")[:2]), "%Y%m%d_%H%M%S"))
            return key, dt
        except ValueError:
            return None, None
    return None, None


@shared_task
def scan_and_insert_by_file_key():
    file_map = defaultdict(lambda: {'csv': None, 'png': None, 'tiff': None, 'datetime': None})

    for base_dir in TARGET_DIRS:
        if not base_dir.exists():
            continue

        for root, _, files in os.walk(base_dir):
            for file in sorted(files):
                ext = Path(file).suffix.lower()
                if ext not in TARGET_EXTS:
                    continue

                full_path = Path(root) / file
                try:
                    size = full_path.stat().st_size
                    if size == 0:
                        continue
                except Exception:
                    continue

                key, dt = get_file_key_and_datetime(file)
                if not key or not dt:
                    continue

                try:
                    rel_path = full_path.resolve().relative_to(SOURCE_DIR).as_posix()
                except ValueError:
                    continue

                file_map[key]['datetime'] = dt
                file_info = {'path': rel_path, 'size': size}
                if ext == '.csv':
                    file_map[key]['csv'] = file_info
                elif ext == '.png':
                    file_map[key]['png'] = file_info
                elif ext in ['.tif', '.tiff']:
                    file_map[key]['tiff'] = file_info

    inserted = 0
    for group in file_map.values():
        if not all(group.values()):
            continue

        exists = DatasetXmprData.objects.filter(
            csv=group['csv']['path']
        ).exists() or DatasetXmprData.objects.filter(
            png=group['png']['path']
        ).exists() or DatasetXmprData.objects.filter(
            tiff=group['tiff']['path']
        ).exists()

        if exists:
            continue

        DatasetXmprData.objects.create(
            time=group['datetime'],
            csv=group['csv']['path'],
            csv_size=group['csv']['size'],
            png=group['png']['path'],
            png_size=group['png']['size'],
            tiff=group['tiff']['path'],
            tiff_size=group['tiff']['size'],
        )
        inserted += 1

    return inserted


@shared_task
def process_csv_file(csv_relative_path: str):
    """
    • Skip CSVs with <10 data rows
    • Convert CSV -> SSV (no extension)
    • Run polar2mesh
    • Convert mesh -> GeoTIFF & PNG
    • Insert into DB (if new)
    """

    media_root = settings.MEDIA_ROOT
    csv_path   = os.path.join(media_root, csv_relative_path)
    basename   = os.path.splitext(os.path.basename(csv_path))[0]

    # ────────────────────────── CSV sanity check ─────────────────────────
    try:
        with open(csv_path, "r") as fh:
            data_rows = [ln for ln in fh if ln.strip()]
        if len(data_rows) < 11:          # header + <10 rows
            logger.warning(f"Skip {csv_relative_path}: only "
                           f"{len(data_rows)-1} data rows")
            return f"Too few rows ({len(data_rows)-1})"
    except Exception as e:
        logger.error(f"Cannot read {csv_relative_path}: {e}")
        return f"Read-error: {e}"

    # ─────────────────────────── temp file names ──────────────────────────
    tmp_dir = os.path.join(media_root, "temp")
    os.makedirs(tmp_dir, exist_ok=True)

    polar_path = os.path.join(tmp_dir, f"polar_{basename}")   # <-- NO EXT
    mesh_path  = os.path.join(tmp_dir, f"mesh_{basename}")    # <-- NO EXT

    try:
        logger.info(f"▶︎  Processing {csv_path}")

        # 1. CSV → SSV  (extension-less)
        TranslateFormat.to_ssv(csv_path, polar_path)
        if not os.path.isfile(polar_path) or os.path.getsize(polar_path) == 0:
            err = f"SSV not created: {polar_path}"
            logger.error(err)
            return err
        logger.info(f"SSV OK  → {polar_path}")

        # 2. polar2mesh
        cmd = [str(settings.POLAR2MESH_PATH), polar_path, mesh_path]
        logger.debug("CMD  " + " ".join(cmd))
        subprocess.run(cmd, check=True,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if not os.path.isfile(mesh_path) or os.path.getsize(mesh_path) == 0:
            err = f"Mesh not created: {mesh_path}"
            logger.error(err)
            return err
        logger.info(f"Mesh OK → {mesh_path}")

        # 3. datetime from filename
        date_part, time_part = basename.split("_", 2)[:2]
        dt = make_aware(datetime.strptime(f"{date_part}_{time_part}",
                                          "%Y%m%d_%H%M%S"))

        # 4. UTM
        utm = CoordinateSystem.latlon2utm(settings.PROCESSOR_LONGITUDE,
                                          settings.PROCESSOR_LATITUDE)

        # 5. final output folders
        y, m, d = dt.strftime("%Y"), dt.strftime("%m"), dt.strftime("%d")
        tif_dir = os.path.join(media_root, "images", "tif", y, m, d)
        png_dir = os.path.join(media_root, "images", "png", y, m, d)
        os.makedirs(tif_dir, exist_ok=True)
        os.makedirs(png_dir, exist_ok=True)

        tif_path = os.path.join(tif_dir, f"{basename}.tif")
        png_path = os.path.join(png_dir, f"{basename}.png")

        # 6. mesh → GeoTIFF
        ModGdal.ascii2tiff(utm["epsg"], mesh_path, tif_path)
        logger.info(f"TIFF  → {tif_path}")

        # 7. mesh → colour PNG
        data = np.loadtxt(mesh_path, delimiter=" ", skiprows=6)
        ascii2img(data, png_path)
        logger.info(f"PNG   → {png_path}")

        # 8. DB
        if ProcessorXmprData.objects.filter(csv=csv_relative_path).exists():
            logger.warning(f"DB already has {csv_relative_path}")
        else:
            ProcessorXmprData.objects.create(
                time   = dt,
                csv    = csv_relative_path,
                image  = os.path.relpath(png_path, media_root),
                geotiff= os.path.relpath(tif_path, media_root),
            )
            logger.info(f"DB insert ✓  {csv_relative_path}")

        return 1

    except subprocess.CalledProcessError as e:
        logger.error(f"polar2mesh failed: {e.stderr or e}")
        return f"polar2mesh failed: {e.stderr or e}"

    except Exception as e:
        logger.exception(f"Unhandled error for {csv_relative_path}")
        return f"Processing failed: {e}"

    finally:
        file_delete(polar_path, mesh_path)
        logger.debug("Temp cleaned")


@shared_task
def move_and_process_files():
    logger.info("=== move_and_process_files start ===")

    # 1) Move any raw rain-RT files
    move_row_files()
    logger.info("Moved rain-RT files")

    csv_root = os.path.join(settings.MEDIA_ROOT, "csv")
    succeeded = []
    failed = []

    # 2) Process all CSVs
    for root, _, files in os.walk(csv_root):
        for name in files:
            if not name.lower().endswith(".csv"):
                continue

            rel = os.path.relpath(os.path.join(root, name), settings.MEDIA_ROOT)
            res = process_csv_file(rel)
            if res == 1:
                succeeded.append(rel)
                logger.info(f"✓ Processed: {rel}")
            else:
                failed.append((rel, res))
                logger.error(f"✗ {rel}: {res}")

    # 3) Summary
    total = len(succeeded) + len(failed)
    logger.info(
        f"Processing complete: {total} total, {len(succeeded)} succeeded, {len(failed)} failed"
    )

    if failed:
        failed_files = [path for path, _ in failed]
        logger.warning("Failed files:\n  • " + "\n  • ".join(failed_files))
    else:
        failed_files = []

    # 4) Move processed files separately
    if succeeded:
        move_csv_files(succeeded, success=True)
        logger.info("Moved succeeded files to converted/")
    if failed_files:
        move_csv_files(failed_files, success=False)
        logger.info("Moved failed files to failed/")

    logger.info("=== move_and_process_files end ===")

    return {
        "total": total,
        "succeeded": len(succeeded),
        "failed": len(failed),
        "failed_files": failed_files
    }
