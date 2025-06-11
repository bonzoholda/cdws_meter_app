# app/drive_utils.py

import io
import os
import json
from PIL import Image
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload, MediaFileUpload, MediaIoBaseDownload
from dotenv import load_dotenv
from urllib.parse import urlparse
from app.database import DATABASE_URL
import stat


load_dotenv()

SCOPES = ['https://www.googleapis.com/auth/drive']
SERVICE_ACCOUNT_INFO = json.loads(os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON"))
FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID")
BACKUP_FOLDER_ID = os.getenv("GOOGLE_DRIVE_BACKUP_ID")

credentials = service_account.Credentials.from_service_account_info(SERVICE_ACCOUNT_INFO, scopes=SCOPES)
drive_service = build('drive', 'v3', credentials=credentials)

# --------- IMAGE FUNCTIONS (Already existed) ----------

def compress_image(image_file, max_size_kb=150):
    image = Image.open(image_file)
    buffer = io.BytesIO()
    quality = 85
    while True:
        buffer.seek(0)
        image.save(buffer, format="JPEG", quality=quality)
        size_kb = buffer.tell() / 1024
        if size_kb <= max_size_kb or quality < 10:
            break
        quality -= 5
    buffer.seek(0)
    return buffer

def upload_image_to_drive(image_file, filename):
    compressed = compress_image(image_file)
    media = MediaIoBaseUpload(compressed, mimetype='image/jpeg')
    file_metadata = {
        'name': filename,
        'parents': [FOLDER_ID]
    }
    file = drive_service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id'
    ).execute()

    # Set permissions to public
    drive_service.permissions().create(
        fileId=file['id'],
        body={"role": "reader", "type": "anyone"},
    ).execute()

    return file['id']

# --------- DATABASE BACKUP FUNCTIONS ----------

def upload_database_backup(local_path, drive_filename):
    if not os.path.exists(local_path):
        raise FileNotFoundError(f"Database file not found at {local_path}")

    # Read DB file in binary mode for reliable upload
    with open(local_path, "rb") as f:
        media = MediaIoBaseUpload(f, mimetype='application/x-sqlite3')

        file_metadata = {
            'name': drive_filename,
            'parents': [BACKUP_FOLDER_ID]
        }

        uploaded_file = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()

    return uploaded_file['id']


def restore_database_from_drive(filename: str):
    # Step 1: Search for the backup file by name
    query = f"'{BACKUP_FOLDER_ID}' in parents and name = '{filename}' and trashed = false"
    response = drive_service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
    files = response.get('files', [])

    if not files:
        raise FileNotFoundError(f"❌ No backup file named {filename} found in Drive.")

    file_id = files[0]['id']
    print(f"📥 Found backup file: {filename} (ID: {file_id})")

    # Step 2: Resolve DB path
    if DATABASE_URL.startswith("sqlite:///"):
        parsed = urlparse(DATABASE_URL)
        db_path = os.path.abspath(os.path.join(".", parsed.path.lstrip("/")))
    else:
        raise RuntimeError("❌ Restore only supports SQLite databases.")

    print(f"📁 Restoring to local path: {db_path}")

    # Step 3: Delete existing DB if it exists
    if os.path.exists(db_path):
        os.remove(db_path)
        print(f"🗑️ Deleted old DB at {db_path}")

    # Step 4: Download and overwrite DB
    request = drive_service.files().get_media(fileId=file_id)
    fh = io.FileIO(db_path, 'wb')
    downloader = MediaIoBaseDownload(fh, request)

    done = False
    while not done:
        status, done = downloader.next_chunk()
        if status:
            print(f"⬇️ Download progress: {int(status.progress() * 100)}%")

    fh.close()

    # Step 5: Set correct file permissions
    os.chmod(db_path, stat.S_IRUSR | stat.S_IWUSR)
    print(f"✅ Restored DB and set writable permissions at {db_path}")

    # ✅ Step 6: Verify table contents
    import sqlite3
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = {row[0] for row in cursor.fetchall()}
        print(f"📦 Tables found: {tables}")

        if "data_pelanggan" in tables:
            cursor.execute("SELECT COUNT(*) FROM data_pelanggan;")
            count = cursor.fetchone()[0]
            print(f"✅ data_pelanggan rows restored: {count}")
        else:
            print("⚠️ Table 'data_pelanggan' not found.")

        if "meter_records" in tables:
            cursor.execute("SELECT COUNT(*) FROM meter_records;")
            count = cursor.fetchone()[0]
            print(f"✅ meter_records rows restored: {count}")
        else:
            print("⚠️ Table 'meter_records' not found.")

        conn.close()
    except Exception as e:
        print("❌ Error verifying restored database:")
        import traceback
        traceback.print_exc()

    print(f"✅ Restore complete: {filename}")



def get_latest_backup_file():
    """Return the name of the latest .db backup file in BACKUP_FOLDER_ID."""
    results = drive_service.files().list(
        q=f"'{BACKUP_FOLDER_ID}' in parents and name contains '.db'",
        spaces='drive',
        fields="files(id, name, createdTime)",
        orderBy="createdTime desc",
        pageSize=1
    ).execute()

    files = results.get("files", [])
    if files:
        return files[0]["name"]
    return None

