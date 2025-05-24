import os
import re
import psycopg2
from datetime import datetime
from dotenv import load_dotenv
from pathlib import Path
from collections import defaultdict

# --- Load environment variables ---
load_dotenv()

# --- Configuration ---
SOURCE_DIR = os.getenv("SOURCE_DIR", ".")
LOG_FILE = "xmpr_upload.log"
DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"

# --- Database connection ---
try:
    conn = psycopg2.connect(
        host=os.getenv("DATABASE_HOST"),
        port=os.getenv("DATABASE_PORT"),
        dbname=os.getenv("DATABASE_NAME"),
        user=os.getenv("DATABASE_USER"),
        password=os.getenv("DATABASE_PASSWORD"),
        options='-c search_path=xras'
    )
except Exception as e:
    print(f"[DB ERROR] {e}")
    exit(1)

# --- Logging ---
def log(msg):
    print(msg)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{datetime.now().isoformat()} - {msg}\n")

missing_entries = []

# --- Extract strict file key from filename ---
def get_file_key_and_datetime(path):
    filename = Path(path).name
    pattern = re.compile(r"(?P<key>\d{8}_\d{6}_[^_]+_\d{3})\.(csv|png|tif|tiff)", re.IGNORECASE)
    match = pattern.match(filename)
    if match:
        key = match.group("key")
        try:
            dt_part = "_".join(key.split("_")[:2])
            dt = datetime.strptime(dt_part, "%Y%m%d_%H%M%S")
            return key, dt
        except ValueError:
            return None, None
    return None, None

# --- Check if file already in DB ---
def is_file_uploaded(rel_path):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT 1 FROM public.datasets_xmprdata
            WHERE csv = %s OR png = %s OR tiff = %s
            LIMIT 1
        """, (rel_path, rel_path, rel_path))
        return cur.fetchone() is not None

# --- Insert record ---
def insert_record(dt, csv_info, png_info, tiff_info):
    csv_path = csv_info['path']
    png_path = png_info['path']
    tiff_path = tiff_info['path']

    if any(is_file_uploaded(p) for p in [csv_path, png_path, tiff_path]):
        log(f"[SKIP] Already in DB → {csv_path}")
        return

    if DRY_RUN:
        log(f"[DRY-RUN] Would insert: {csv_path}, {png_path}, {tiff_path}")
        return

    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO public.datasets_xmprdata (
                time, csv, png, tiff, csv_size, png_size, tiff_size, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, now(), now())
        """, (
            dt,
            csv_path,
            png_path,
            tiff_path,
            csv_info['size'],
            png_info['size'],
            tiff_info['size']
        ))
        conn.commit()
        log(f"[INSERTED] {dt} → {csv_path}")

# --- Main processing function ---
def scan_and_insert_by_file_key():
    file_map = defaultdict(lambda: {'csv': None, 'png': None, 'tiff': None, 'datetime': None})

    for root, _, files in os.walk(SOURCE_DIR):
        for file in sorted(files):
            ext = Path(file).suffix.lower()
            if ext not in ['.csv', '.png', '.tif', '.tiff']:
                continue

            full_path = os.path.join(root, file)
            rel_path = os.path.relpath(full_path, SOURCE_DIR).replace("\\", "/")

            try:
                file_size = os.path.getsize(full_path)
                if file_size == 0:
                    log(f"[SKIP] Zero size file: {rel_path}")
                    continue
            except Exception as e:
                log(f"[SKIP] Cannot access: {rel_path} — {e}")
                continue

            key, dt = get_file_key_and_datetime(file)
            if not key or not dt:
                log(f"[SKIP] Filename doesn't match pattern: {file}")
                continue

            file_info = {'path': rel_path, 'size': file_size}
            file_map[key]['datetime'] = dt

            if ext == '.csv':
                file_map[key]['csv'] = file_info
            elif ext == '.png':
                file_map[key]['png'] = file_info
            elif ext in ['.tif', '.tiff']:
                file_map[key]['tiff'] = file_info

    total_inserted = 0
    for key, group in sorted(file_map.items()):
        if group['csv'] and group['png'] and group['tiff']:
            insert_record(group['datetime'], group['csv'], group['png'], group['tiff'])
            total_inserted += 1
        else:
            missing = [ftype.upper() for ftype in ['csv', 'png', 'tiff'] if not group[ftype]]
            missing_entries.append(f"{key} → missing: {', '.join(missing)}")

    log(f"[DONE] Records inserted: {total_inserted}")
    if missing_entries:
        log(f"[REPORT] Incomplete file groups:\n" + "\n".join(missing_entries))

# --- Run script ---
if __name__ == "__main__":
    try:
        scan_and_insert_by_file_key()
    except Exception as e:
        log(f"[FATAL ERROR] {e}")
    finally:
        conn.close()
        log("[DONE] DB connection closed.")
