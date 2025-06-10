# app/drive_utils.py

import io
import os
import json
from PIL import Image
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from dotenv import load_dotenv

load_dotenv()

SCOPES = ['https://www.googleapis.com/auth/drive']
SERVICE_ACCOUNT_INFO = json.loads(os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON"))
FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID")

credentials = service_account.Credentials.from_service_account_info(SERVICE_ACCOUNT_INFO, scopes=SCOPES)

drive_service = build('drive', 'v3', credentials=credentials)

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
