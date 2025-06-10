# app/main.py

from fastapi import FastAPI, Request, Form, UploadFile, File, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from uuid import uuid4
import os

from .database import Base, engine, SessionLocal
from .models import MeterRecord
from .drive_utils import upload_image_to_drive
from .auth import add_auth, is_logged_in, login_form, login, logout

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

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/upload-image/")
async def upload_image(
    user_id: str = Form(...),
    sr_no: str = Form(...),
    image: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    filename = f"{user_id}_{sr_no}_{uuid4().hex}.jpg"
    file_id = upload_image_to_drive(image.file, filename)

    new_record = MeterRecord(user_id=user_id, sr_no=sr_no, drive_file_id=file_id)
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
    return await logout(request)

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
