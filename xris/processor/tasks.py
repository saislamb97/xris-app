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
from processor.models import XmprData as ProcessorXmprData, RainMapImage
from datetime import timedelta
from processor.utils.formatter import TranslateFormat
from processor.utils.coordinates import CoordinateSystem
from processor.utils.gdal_tools import ModGdal
from processor.utils.image import ascii2img
from processor.utils.file_ops import file_delete, move_raw_files, move_csv_files
from processor.helpers import get_file_key_and_datetime, get_datetime_from_jpg
from django.core.cache import cache
from django.utils.timezone import now
from celery import chain


logger = logging.getLogger(__name__)

@shared_task
def scan_and_insert_by_file_key(_result=None):
    SOURCE_DIR = Path(settings.MEDIA_ROOT).resolve()
    TARGET_EXTS = {'.csv', '.png', '.tif', '.tiff', '.jpg'}
    default_dirs = ["converted", "images/png", "images/tif", "RainMAP_JPEG"]
    env_dirs = os.getenv('TARGET_DIRS')
    dir_names = [d.strip() for d in env_dirs.split(',')] if env_dirs else default_dirs
    TARGET_DIRS = [SOURCE_DIR / d for d in dir_names]

    folder_map = defaultdict(lambda: {'csv': [], 'png': [], 'tiff': [], 'jpg': []})
    rainmap_inserted = 0

    # Phase 1: Walk and bucket files by date folder
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

                try:
                    rel_path = full_path.resolve().relative_to(SOURCE_DIR).as_posix()
                except ValueError:
                    continue

                # Determine folder date group: last 3 path components
                try:
                    root_path = Path(root)
                    date_folder = "/".join(root_path.parts[-3:])  # e.g. '2024/12/22'
                except IndexError:
                    continue

                entry = {'file': file, 'path': rel_path, 'size': size}

                if ext == '.jpg':
                    dt = get_datetime_from_jpg(file)
                    if dt and not RainMapImage.objects.filter(image=rel_path).exists():
                        RainMapImage.objects.create(time=dt, image=rel_path)
                        rainmap_inserted += 1
                    continue

                if ext == '.csv':
                    folder_map[date_folder]['csv'].append(entry)
                elif ext == '.png':
                    folder_map[date_folder]['png'].append(entry)
                elif ext in ['.tif', '.tiff']:
                    folder_map[date_folder]['tiff'].append(entry)

    dataset_inserted = 0
    processor_inserted = 0

    # Phase 2: Match within folder and insert records
    for date_folder, group in folder_map.items():
        for csv_entry in group['csv']:
            key, dt = get_file_key_and_datetime(csv_entry['file'])
            if not key or not dt:
                continue

            png_entry = next((p for p in group['png'] if p['file'].startswith(key)), None)
            tiff_entry = next((t for t in group['tiff'] if t['file'].startswith(key)), None)

            if not (png_entry and tiff_entry):
                logger.debug(f"Incomplete match for {key} in {date_folder}")
                continue

            if not DatasetXmprData.objects.filter(csv=csv_entry['path']).exists() \
                and not DatasetXmprData.objects.filter(png=png_entry['path']).exists() \
                and not DatasetXmprData.objects.filter(tiff=tiff_entry['path']).exists():
                DatasetXmprData.objects.create(
                    time=dt,
                    csv=csv_entry['path'],
                    csv_size=csv_entry['size'],
                    png=png_entry['path'],
                    png_size=png_entry['size'],
                    tiff=tiff_entry['path'],
                    tiff_size=tiff_entry['size'],
                )
                dataset_inserted += 1

            if not ProcessorXmprData.objects.filter(csv=csv_entry['path']).exists() \
                and not ProcessorXmprData.objects.filter(image=png_entry['path']).exists() \
                and not ProcessorXmprData.objects.filter(geotiff=tiff_entry['path']).exists():
                ProcessorXmprData.objects.create(
                    time=dt,
                    csv=csv_entry['path'],
                    image=png_entry['path'],
                    geotiff=tiff_entry['path'],
                )
                processor_inserted += 1

    logger.info(f"Inserted RainMap JPEGs: {rainmap_inserted}")
    logger.info(f"Inserted into DatasetXmprData: {dataset_inserted}")
    logger.info(f"Inserted into ProcessorXmprData: {processor_inserted}")

    if _result:
        logger.info(f"Previous move task: {_result['succeeded']} succeeded, {_result['failed']} failed")

    return {
        "input_result": _result,
        "rainmap_inserted": rainmap_inserted,
        "dataset_inserted": dataset_inserted,
        "processor_inserted": processor_inserted
    }


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
        if len(data_rows) < 11:
            logger.warning(f"Skip {csv_relative_path}: only {len(data_rows)-1} data rows")
            return f"Too few rows ({len(data_rows)-1})"
    except Exception as e:
        logger.error(f"Cannot read {csv_relative_path}: {e}")
        return f"Read-error: {e}"

    # ─────────────────────────── temp file names ──────────────────────────
    tmp_dir = os.path.join(media_root, "temp")
    os.makedirs(tmp_dir, exist_ok=True)

    polar_path = os.path.join(tmp_dir, f"polar_{basename}")
    mesh_path  = os.path.join(tmp_dir, f"mesh_{basename}")

    try:
        logger.info(f"▶︎  Processing {csv_path}")

        # 1. CSV → SSV
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
        dt = make_aware(datetime.strptime(f"{date_part}_{time_part}", "%Y%m%d_%H%M%S"))

        # 4. UTM
        utm = CoordinateSystem.latlon2utm(
            settings.PROCESSOR_LONGITUDE,
            settings.PROCESSOR_LATITUDE
        )

        # 5. Final output folders
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

        # 8. Determine converted CSV path (instead of 'csv/...')
        converted_csv_path = os.path.join("converted", y, m, d, os.path.basename(csv_path))

        # 9. DB
        if ProcessorXmprData.objects.filter(csv=converted_csv_path).exists():
            logger.warning(f"DB already has {converted_csv_path}")
        else:
            ProcessorXmprData.objects.create(
                time=dt,
                csv=converted_csv_path,
                image=os.path.relpath(png_path, media_root),
                geotiff=os.path.relpath(tif_path, media_root),
            )
            logger.info(f"DB insert ✓  {converted_csv_path}")

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
    move_raw_files()
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


LOCK_EXPIRE = 120  # seconds

def trigger_xmpr_pipeline(force=False):
    cache_key = "last_xmpr_pipeline_run"
    lock_key = "xmpr_pipeline_lock"
    now_time = now()

    if not force and cache.get(cache_key):
        logger.info("Skipped pipeline trigger: ran recently")
        return False

    if cache.get(lock_key):
        logger.info("Pipeline already running or queued")
        return False

    cache.set(lock_key, True, timeout=LOCK_EXPIRE)

    try:
        task_chain = chain(
            move_and_process_files.s(),
            scan_and_insert_by_file_key.s()
        )
        task_chain.delay()
        logger.info("Dispatched chained XMPR pipeline")

        cache.set(cache_key, now_time, timeout=LOCK_EXPIRE)
        return True
    finally:
        # Let lock expire naturally
        pass
