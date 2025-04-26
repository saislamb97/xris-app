import os
import shutil
import psycopg2
import boto3
from botocore.exceptions import BotoCoreError, ClientError
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# --- Config ---
SOURCE_DIR = os.getenv("SOURCE_DIR")
DESTINATION_DIR = os.getenv("DESTINATION_DIR")
BUCKET = os.getenv("S3_BUCKET")
REGION = os.getenv("REGION")
LOG_FILE = "xmpr_upload.log"

# PostgreSQL connection
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

# Initialize S3 if available
s3 = None
s3_available = False
if BUCKET and REGION and os.getenv("AWS_ACCESS_KEY_ID") and os.getenv("AWS_SECRET_ACCESS_KEY"):
    try:
        s3 = boto3.client(
            "s3",
            region_name=REGION,
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        )
        s3_available = True
    except (BotoCoreError, ClientError, ValueError) as e:
        print(f"[S3 WARNING] {e}")

SUPPORTED_EXTS = ['.csv', '.png', '.tif', '.tiff']

# --- Logging ---
def log(msg):
    print(msg)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{datetime.now().isoformat()} - {msg}\n")

# --- Helpers ---
def file_already_uploaded(file_name):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT 1 FROM public.datasets_xmprdata 
            WHERE csv = %s OR png = %s OR tiff = %s 
            LIMIT 1
        """, (
            f"xmpr/csv/{file_name}",
            f"xmpr/png/{file_name}",
            f"xmpr/tiff/{file_name}"
        ))
        return cur.fetchone() is not None

def insert_record(time, csv=None, png=None, tiff=None, csv_size=0, png_size=0, tiff_size=0):
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO public.datasets_xmprdata (time, csv, png, tiff, csv_size, png_size, tiff_size, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, now(), now())
        """, (time, csv, png, tiff, csv_size, png_size, tiff_size))
        conn.commit()

def get_datetime_from_name(name):
    """
    Extract datetime from filename.
    Expected filename starts with: YYYYMMDD_HHMMSS
    Example: 20241222_041800_Rain_000.png
    """
    try:
        # Find the first 15 characters
        timestamp_part = name[:15]

        # Validate basic structure
        if len(timestamp_part) == 15 and timestamp_part[8] == '_':
            dt = datetime.strptime(timestamp_part, '%Y%m%d_%H%M%S')
            return dt
        else:
            raise ValueError(f"Invalid timestamp format: {timestamp_part}")
    
    except Exception as e:
        log(f"[TIME PARSE WARNING] Failed to parse time from {name}: {e}")
        return datetime.now()

def upload_or_copy_file(full_path, ext):
    file_name = os.path.basename(full_path)
    subfolder = {
        '.csv': 'csv',
        '.png': 'png',
        '.tif': 'tiff',
        '.tiff': 'tiff'
    }.get(ext, 'other')

    rel_path = f"xmpr/{subfolder}/{file_name}"

    if s3_available:
        try:
            s3.upload_file(full_path, BUCKET, rel_path)
            log(f"[S3 UPLOADED] {file_name} → {rel_path}")
        except ClientError as e:
            log(f"[S3 ERROR] Failed upload {file_name}: {e}")
            return None
    else:
        dest_path = os.path.join(DESTINATION_DIR, rel_path)
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        shutil.copy2(full_path, dest_path)
        log(f"[LOCAL COPY] {file_name} → {dest_path}")

    return rel_path

def scan_and_upload():
    for root, _, files in sorted(os.walk(SOURCE_DIR), key=lambda x: x[0]):
        for file in sorted(files):
            ext = Path(file).suffix.lower()
            if ext not in SUPPORTED_EXTS:
                continue

            if file_already_uploaded(file):
                log(f"[SKIP] Already uploaded: {file}")
                continue

            full_path = os.path.join(root, file)
            storage_path = upload_or_copy_file(full_path, ext)
            if not storage_path:
                continue  # skip if upload failed

            dt = get_datetime_from_name(file)
            file_size = os.path.getsize(full_path)

            csv = png = tiff = None
            csv_size = png_size = tiff_size = 0

            if ext == '.csv':
                csv = storage_path
                csv_size = file_size
            elif ext == '.png':
                png = storage_path
                png_size = file_size
            elif ext in ['.tif', '.tiff']:
                tiff = storage_path
                tiff_size = file_size

            insert_record(dt, csv=csv, png=png, tiff=tiff, csv_size=csv_size, png_size=png_size, tiff_size=tiff_size)
            log(f"[DB INSERTED] {file} → DB record created")

if __name__ == "__main__":
    try:
        scan_and_upload()
    except Exception as e:
        log(f"[FATAL ERROR] {e}")
    finally:
        conn.close()
        log("[DONE] Connection closed.")
