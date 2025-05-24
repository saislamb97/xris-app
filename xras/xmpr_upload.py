import os
import psycopg2
from datetime import datetime
from dotenv import load_dotenv
from pathlib import Path
from collections import defaultdict

# Load environment variables
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

# --- Extract date from path folder ---
def get_date_from_path(path):
    parts = Path(path).parts
    for i in range(len(parts) - 3):
        try:
            yyyy = int(parts[i])
            mm = int(parts[i + 1])
            dd = int(parts[i + 2])
            return f"{yyyy:04d}-{mm:02d}-{dd:02d}"
        except Exception:
            continue
    return None

# --- Check if file already in DB ---
def is_file_uploaded(rel_path):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT 1 FROM public.datasets_xmprdata
            WHERE csv = %s OR png = %s OR tiff = %s
            LIMIT 1
        """, (rel_path, rel_path, rel_path))
        return cur.fetchone() is not None

# --- Insert one row ---
def insert_record(date, csv_info=None, png_info=None, tiff_info=None):
    files_present = sum([
        1 if csv_info else 0,
        1 if png_info else 0,
        1 if tiff_info else 0
    ])

    if files_present < 2:
        log(f"[SKIP] Only {files_present} file(s) found for {date}. Minimum 2 required.")
        return

    csv_path = csv_info['path'] if csv_info else None
    png_path = png_info['path'] if png_info else None
    tiff_path = tiff_info['path'] if tiff_info else None

    if any(is_file_uploaded(p) for p in [csv_path, png_path, tiff_path] if p):
        log(f"[SKIP] Already uploaded — CSV: {csv_path}, PNG: {png_path}, TIFF: {tiff_path}")
        return

    if DRY_RUN:
        log(f"[DRY-RUN] Would insert {date} → CSV: {csv_path}, PNG: {png_path}, TIFF: {tiff_path}")
        return

    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO public.datasets_xmprdata (
                time, csv, png, tiff, csv_size, png_size, tiff_size, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, now(), now())
        """, (
            datetime.strptime(date, '%Y-%m-%d'),
            csv_path,
            png_path,
            tiff_path,
            csv_info['size'] if csv_info else 0,
            png_info['size'] if png_info else 0,
            tiff_info['size'] if tiff_info else 0
        ))
        conn.commit()
        log(f"[INSERTED] {date} → CSV: {csv_path}, PNG: {png_path}, TIFF: {tiff_path}")

# --- Main logic: scan all files and group by date ---
def scan_and_insert_by_date():
    file_map = defaultdict(lambda: {'csv': [], 'png': [], 'tiff': []})

    for root, _, files in os.walk(SOURCE_DIR):
        for file in sorted(files):
            ext = Path(file).suffix.lower()
            if ext not in ['.csv', '.png', '.tif', '.tiff']:
                continue

            full_path = os.path.join(root, file)
            if not os.path.exists(full_path):
                continue

            try:
                file_size = os.path.getsize(full_path)
            except Exception as e:
                log(f"[SKIP] Cannot read size: {full_path} — {e}")
                continue

            if file_size == 0:
                log(f"[SKIP] Zero size file: {full_path}")
                continue

            date = get_date_from_path(full_path)
            if not date:
                log(f"[SKIP] Cannot determine date: {full_path}")
                continue

            rel_path = os.path.relpath(full_path, SOURCE_DIR).replace("\\", "/")
            file_info = {'path': rel_path, 'size': file_size}

            if ext == '.csv':
                file_map[date]['csv'].append(file_info)
            elif ext == '.png':
                file_map[date]['png'].append(file_info)
            elif ext in ['.tif', '.tiff']:
                file_map[date]['tiff'].append(file_info)

    total_inserted = 0
    for date, group in sorted(file_map.items()):
        max_len = max(len(group['csv']), len(group['png']), len(group['tiff']))
        for i in range(max_len):
            csv = group['csv'][i] if i < len(group['csv']) else None
            png = group['png'][i] if i < len(group['png']) else None
            tiff = group['tiff'][i] if i < len(group['tiff']) else None
            insert_record(date, csv_info=csv, png_info=png, tiff_info=tiff)
            total_inserted += 1

    log(f"[DONE] Total records processed: {total_inserted}")

# --- Run ---
if __name__ == "__main__":
    try:
        scan_and_insert_by_date()
    except Exception as e:
        log(f"[FATAL ERROR] {e}")
    finally:
        conn.close()
        log("[DONE] DB connection closed.")
