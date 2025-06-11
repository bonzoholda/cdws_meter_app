# app/drive_utils.py

import io
import os
import json
from PIL import Image
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload, MediaFileUpload, MediaIoBaseDownload
from dotenv import load_dotenv

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

def upload_database_backup(local_path: str, drive_filename: str = "backup_latest.db"):
    file_metadata = {
        'name': drive_filename,
        'parents': [BACKUP_FOLDER_ID]
    }
    media = MediaFileUpload(local_path, mimetype='application/x-sqlite3', resumable=True)

    # Remove existing backup if it exists
    response = drive_service.files().list(
        q=f"'{BACKUP_FOLDER_ID}' in parents and name='{drive_filename}'",
        spaces='drive'
    ).execute()
    for file in response.get('files', []):
        drive_service.files().delete(fileId=file['id']).execute()

    file = drive_service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id'
    ).execute()
    return file.get('id')

def download_database_backup(drive_filename: str = "backup_latest.db", local_path: str = "app/database/app.db"):
    response = drive_service.files().list(
        q=f"'{BACKUP_FOLDER_ID}' in parents and name='{drive_filename}'",
        spaces='drive'
    ).execute()
    files = response.get('files', [])
    if not files:
        raise FileNotFoundError("Backup not found on Google Drive.")

    file_id = files[0]['id']
    request = drive_service.files().get_media(fileId=file_id)
    with open(local_path, 'wb') as f:
        downloader = MediaIoBaseDownload(f, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
    return True
