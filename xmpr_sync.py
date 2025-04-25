import os
import shutil
import psycopg2
import boto3
from botocore.exceptions import BotoCoreError, ClientError
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Config
SOURCE_DIR = os.getenv("SOURCE_DIR")                  # e.g., ./incoming
DESTINATION_DIR = os.getenv("DESTINATION_DIR")        # e.g., ./media/xmpr
BUCKET = os.getenv("S3_BUCKET")
REGION = os.getenv("REGION")
LOG_FILE = "upload.log"

# PostgreSQL connection
conn = psycopg2.connect(
    host=os.getenv("RDS_HOST"),
    port=os.getenv("RDS_PORT"),
    dbname=os.getenv("RDS_DB"),
    user=os.getenv("RDS_USER"),
    password=os.getenv("RDS_PASSWORD"),
    options='-c search_path=xras'
)

# Initialize S3 if credentials and region exist
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
        print(f"[WARN] S3 not available or misconfigured: {e}")

SUPPORTED_EXTS = ['.csv', '.png', '.tif', '.tiff']

def log(msg):
    print(msg)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{datetime.now().isoformat()} - {msg}\n")

def file_already_uploaded(filename):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT 1 FROM public.datasets_xmprdata 
            WHERE csv LIKE %s OR png LIKE %s OR tiff LIKE %s 
            LIMIT 1
        """, (f'%{filename}%', f'%{filename}%', f'%{filename}%'))
        return cur.fetchone() is not None

def insert_record(time, csv=None, png=None, tiff=None, size=0):
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO public.datasets_xmprdata (time, csv, png, tiff, size, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, now(), now())
        """, (time, csv, png, tiff, size))
        conn.commit()


def get_datetime_from_name(name):
    try:
        return datetime.strptime(name[:19], '%Y-%m-%d_%H-%M-%S')
    except Exception:
        return datetime.now()

def upload_or_copy_file(path, rel_path, ext):
    file_name = os.path.basename(path)
    subfolder = {
        '.csv': 'csv',
        '.png': 'png',
        '.tif': 'tiff',
        '.tiff': 'tiff'
    }.get(ext, 'other')

    s3_key = f"xmpr/{subfolder}/{rel_path}"
    
    # Attempt S3 upload
    if s3_available:
        try:
            s3.upload_file(path, BUCKET, s3_key)
            url = f"https://{BUCKET}.s3.{REGION}.amazonaws.com/{s3_key}"
            log(f"[S3 UPLOADED] {file_name} → {url}")
            return url
        except ClientError as e:
            log(f"[S3 ERROR] Failed to upload {file_name}: {e}")

    # Fallback to local path
    local_path = os.path.join(DESTINATION_DIR, 'xmpr', subfolder, rel_path)
    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    shutil.copy2(path, local_path)
    log(f"[LOCAL COPY] {file_name} → {local_path}")
    return os.path.relpath(local_path)

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
            rel_path = os.path.relpath(full_path, SOURCE_DIR).replace("\\", "/")
            uploaded_url_or_path = upload_or_copy_file(full_path, rel_path, ext)
            dt = get_datetime_from_name(file)
            size = os.path.getsize(full_path)

            csv_url = uploaded_url_or_path if ext == '.csv' else None
            png_url = uploaded_url_or_path if ext == '.png' else None
            tiff_url = uploaded_url_or_path if ext in ['.tif', '.tiff'] else None

            insert_record(dt, csv_url, png_url, tiff_url, size)
            log(f"[DB INSERTED] {file} → DB record created")
            
            # Optional: remove original file after success
            # os.remove(full_path)
            # log(f"[CLEANUP] Removed original: {file}")

if __name__ == "__main__":
    scan_and_upload()
    conn.close()
