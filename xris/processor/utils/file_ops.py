import os
import logging
import shutil
from django.conf import settings

logger = logging.getLogger(__name__)


def file_delete(*paths):
    """
    Delete temporary files if they exist and are regular files.
    """
    for p in paths:
        try:
            if os.path.isfile(p):
                os.remove(p)
        except OSError:
            pass


def has_enough_space(path, required_bytes=10 * 1024 * 1024):  # Default: 10MB
    """
    Check if there is enough free space at the location of `path`.
    """
    try:
        total, used, free = shutil.disk_usage(path)
        return free > required_bytes
    except Exception as e:
        logger.error(f"Storage check failed at {path}: {e}")
        return False


def move_raw_files():
    """
    Move files from MEDIA_ROOT/rain-RT → MEDIA_ROOT/raw/YYYY/MM/DD/
    """
    root = settings.MEDIA_ROOT
    src_dir = os.path.join(root, "rain-RT")
    dst_root = os.path.join(root, "raw")

    if not os.path.isdir(src_dir):
        return

    for fn in os.listdir(src_dir):
        parts = fn.split("_")
        if len(parts) < 2:
            continue

        date_str = parts[1]
        if len(date_str) < 8:
            continue

        y, m, d = date_str[:4], date_str[4:6], date_str[6:8]
        tgt_dir = os.path.join(dst_root, y, m, d)
        os.makedirs(tgt_dir, exist_ok=True)

        if not has_enough_space(tgt_dir):
            logger.warning(f"Insufficient storage space in {tgt_dir}, skipping move of {fn}")
            continue

        src_path = os.path.join(src_dir, fn)
        dst_path = os.path.join(tgt_dir, fn)

        try:
            os.rename(src_path, dst_path)
        except OSError as e:
            logger.error(f"Failed to move {fn} to {tgt_dir}: {e}")


def move_csv_files(file_list, success=True):
    """
    Move CSVs to MEDIA_ROOT/converted/YYYY/MM/DD/ or MEDIA_ROOT/failed/YYYY/MM/DD/
    Args:
        file_list (list): list of CSV file paths (relative to MEDIA_ROOT)
        success (bool): True → move to 'converted', False → move to 'failed'
    """
    base_dir = "converted" if success else "failed"
    media_root = settings.MEDIA_ROOT

    for rel_path in file_list:
        src_path = os.path.join(media_root, rel_path)
        filename = os.path.basename(src_path)
        parts = filename.split("_")

        if len(parts) < 2 or len(parts[0]) < 8:
            logger.warning(f"Cannot parse date from filename: {filename}")
            continue

        y, m, d = parts[0][:4], parts[0][4:6], parts[0][6:8]
        dst_dir = os.path.join(media_root, base_dir, y, m, d)
        os.makedirs(dst_dir, exist_ok=True)

        if not has_enough_space(dst_dir):
            logger.warning(f"Insufficient space in {dst_dir}, skipping {filename}")
            continue

        dst_path = os.path.join(dst_dir, filename)

        try:
            os.rename(src_path, dst_path)
            logger.debug(f"Moved {filename} → {dst_dir}")
        except FileNotFoundError:
            logger.warning(f"File already moved or missing: {src_path}")
        except Exception as e:
            logger.error(f"Failed to move {filename}: {e}")
