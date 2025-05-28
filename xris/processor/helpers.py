import re
from datetime import datetime
from django.utils.timezone import make_aware
import logging

logger = logging.getLogger(__name__)

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

def get_datetime_from_jpg(filename):
    pattern = re.compile(r"(?P<ts>\d{8}_\d{6})\.jpg$", re.IGNORECASE)
    match = pattern.match(filename)
    if match:
        try:
            return make_aware(datetime.strptime(match.group("ts"), "%Y%m%d_%H%M%S"))
        except ValueError:
            return None
    return None