# app/main.py

from fastapi import APIRouter, UploadFile, File, Request, Depends, Form, Response, HTTPException
from fastapi import FastAPI, Request, Form, UploadFile, File, Depends, Query
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from uuid import uuid4
import os
from datetime import datetime, timedelta, timezone
from collections import defaultdict
import csv
import io
from io import StringIO

from .database import Base, engine, SessionLocal, DATABASE_URL
from .models import MeterRecord, DataPelanggan
from .drive_utils import upload_image_to_drive, upload_database_backup, restore_database_from_drive, get_latest_backup_file
from .auth import add_auth, is_logged_in, login_form, login, logout
from urllib.parse import urlparse

Base.metadata.create_all(bind=engine)

app = FastAPI()
add_auth(app)

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

# Dependency for DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

router = APIRouter()

# Session management: Helper to set and check cookies manually
def set_admin_cookie(response: Response):
    expires = datetime.utcnow().replace(tzinfo=timezone.utc) + timedelta(days=7)  # Explicitly setting UTC timezone
    response.set_cookie("admin_logged_in", "true", expires=expires)

def check_admin_logged_in(request: Request):
    if request.cookies.get("admin_logged_in") != "true":
        raise HTTPException(status_code=307, detail="Redirecting to login", headers={"Location": "/login"})


@app.post("/import-pelanggan")
async def import_pelanggan_csv(
    csv_file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    if not csv_file.filename.endswith(".csv"):
        return {"error": "Only CSV files are supported."}

    content = await csv_file.read()
    reader = csv.DictReader(StringIO(content.decode("utf-8")))

    imported = 0
    for row in reader:
        user_id = row["user_id"].strip()
        user_name = row["user_name"].strip()
        user_address = row["user_address"].strip()

        existing = db.query(DataPelanggan).filter_by(user_id=user_id).first()
        if not existing:
            pelanggan = DataPelanggan(
                user_id=user_id,
                user_name=user_name,
                user_address=user_address,
            )
            db.add(pelanggan)
            imported += 1

    db.commit()
    return RedirectResponse(url="/admin", status_code=303)


@app.get("/customer")
def admin_dashboard(request: Request, db: Session = Depends(get_db)):
    pelanggan_list = db.query(DataPelanggan).all()
    return templates.TemplateResponse("customer.html", {
        "request": request,
        "pelanggan_list": pelanggan_list
    })

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):

    if not is_logged_in(request):
        return RedirectResponse("/login")
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/upload-image/")
async def upload_image(
    user_id: str = Form(...),
    sr_no: str = Form(...),
    meter_pos: int = Form(...),
    image: UploadFile = File(...),
    db: Session = Depends(get_db)
):

    filename = f"{user_id}_{sr_no}_{uuid4().hex}.jpg"
    file_id = upload_image_to_drive(image.file, filename)

    new_record = MeterRecord(
        user_id=user_id,
        sr_no=sr_no,
        meter_pos=meter_pos,
        drive_file_id=file_id
    )

    db.add(new_record)
    db.commit()

    return {"message": "Upload successful", "file_id": file_id}

# ---------- Admin routes ----------

@app.get("/login", response_class=HTMLResponse)
async def show_login(request: Request):
    return await login_form(request)

@app.post("/login")
async def handle_login(request: Request, username: str = Form(...), password: str = Form(...)):
    return await login(request, username, password)

@app.get("/logout")
async def handle_logout(request: Request):
    response = await logout(request)

    try:
        # Resolve db_path from DATABASE_URL
        if DATABASE_URL.startswith("sqlite:///"):
            parsed = urlparse(DATABASE_URL)
            db_path = os.path.abspath(os.path.join(".", parsed.path.lstrip("/")))

            if not os.path.exists(db_path):
                raise FileNotFoundError(f"Database file not found at {db_path}")

            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            backup_filename = f"backup_{timestamp}.db"
            upload_database_backup(local_path=db_path, drive_filename=backup_filename)
            print(f"✅ Backup successful: {backup_filename}")
        else:
            print("⚠️ Skipping backup: Not a SQLite DB.")
    except Exception as e:
        import traceback
        print("❌ Backup failed:")
        traceback.print_exc()

    return response



@app.post("/restore-latest-backup")
def restore_latest_backup():
    try:
        latest_file = get_latest_backup_file()
        if not latest_file:
            raise Exception("No backup file found in Google Drive.")
        restored_path = restore_database_from_drive(latest_file)
        print(f"✅ Restored from latest backup: {latest_file}")
        return RedirectResponse(url="/admin", status_code=303)
    except Exception as e:
        print(f"❌ Restore failed: {e}")
        return HTMLResponse(content=f"Restore failed: {e}", status_code=500)



@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request, db: Session = Depends(get_db)):
    if not is_logged_in(request):
        return RedirectResponse("/login")

    records = db.query(MeterRecord).filter(MeterRecord.meter_pos == None).all()
    return templates.TemplateResponse("admin.html", {"request": request, "records": records})

@app.post("/admin/update-pos")
async def update_meter_pos(
    request: Request,
    record_id: int = Form(...),
    meter_pos: int = Form(...),
    db: Session = Depends(get_db)
):
    if not is_logged_in(request):
        return RedirectResponse("/login")

    record = db.query(MeterRecord).filter(MeterRecord.id == record_id).first()
    if record:
        record.meter_pos = meter_pos
        db.commit()
    return RedirectResponse("/admin", status_code=302)


@app.get("/meter-checklist", response_class=HTMLResponse)
async def meter_checklist(request: Request,
                          start_date: str = Query(None),
                          end_date: str = Query(None),
                          db: Session = Depends(get_db)):
    query = db.query(MeterRecord)

    if start_date:
        query = query.filter(MeterRecord.record_timestamp >= datetime.fromisoformat(start_date))
    if end_date:
        query = query.filter(MeterRecord.record_timestamp <= datetime.fromisoformat(end_date))

    records = query.order_by(MeterRecord.user_id, MeterRecord.record_timestamp).all()

    grouped_data = defaultdict(lambda: defaultdict(list))
    for record in records:
        user_id = record.user_id
        month_label = record.record_timestamp.strftime("%Y-%m")
        grouped_data[user_id][month_label].append(record)

    return templates.TemplateResponse("meter-checklist.html", {
        "request": request,
        "grouped_data": grouped_data,
        "start_date": start_date,
        "end_date": end_date
    })


@app.get("/meter-checklist/export", response_class=StreamingResponse)
def export_meter_records(start_date: str = Query(None),
                         end_date: str = Query(None),
                         db: Session = Depends(get_db)):

    query = db.query(MeterRecord)

    if start_date:
        query = query.filter(MeterRecord.record_timestamp >= datetime.fromisoformat(start_date))
    if end_date:
        query = query.filter(MeterRecord.record_timestamp <= datetime.fromisoformat(end_date))

    records = query.order_by(MeterRecord.user_id, MeterRecord.record_timestamp).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["User ID", "Serial No", "Drive File ID", "Meter Pos", "Timestamp"])

    for r in records:
        writer.writerow([
            r.user_id,
            r.sr_no,
            r.drive_file_id,
            r.meter_pos,
            r.record_timestamp.strftime("%Y-%m-%d %H:%M")
        ])

    output.seek(0)
    headers = {
        "Content-Disposition": "attachment; filename=meter_records.csv"
    }
    return StreamingResponse(output, media_type="text/csv", headers=headers)
