import os
import re
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from django.db import connection
from django.utils.timezone import make_aware
from celery import shared_task
from django.core.cache import cache
from django.conf import settings
from datasets.models import XmprData  # assuming this is your model

SOURCE_DIR = Path(settings.MEDIA_ROOT).resolve()

target_dirs = [
    SOURCE_DIR / "csv",
    SOURCE_DIR / "images" / "png",
    SOURCE_DIR / "images" / "tif"
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

    for base_dir in target_dirs:
        if not base_dir.exists():
            continue
        for root, _, files in os.walk(base_dir):
            for file in sorted(files):
                ext = Path(file).suffix.lower()
                if ext not in ['.csv', '.png', '.tif', '.tiff']:
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

                file_info = {'path': rel_path, 'size': size}
                file_map[key]['datetime'] = dt
                if ext == '.csv':
                    file_map[key]['csv'] = file_info
                elif ext == '.png':
                    file_map[key]['png'] = file_info
                elif ext in ['.tif', '.tiff']:
                    file_map[key]['tiff'] = file_info

    inserted = 0
    for group in file_map.values():
        if all(group.values()):
            if XmprData.objects.filter(
                csv=group['csv']['path']
            ).exists() or XmprData.objects.filter(
                png=group['png']['path']
            ).exists() or XmprData.objects.filter(
                tiff=group['tiff']['path']
            ).exists():
                continue

            XmprData.objects.create(
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
