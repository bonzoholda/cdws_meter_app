# app/auth.py

from fastapi import Request, Form
from fastapi.responses import RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
from app.utils import templates
import os
import json
from dotenv import load_dotenv

load_dotenv()

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

def add_auth(app):
    app.add_middleware(SessionMiddleware, secret_key="changeme")

def is_logged_in(request: Request):
    return request.session.get("logged_in", False)

async def login_form(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        request.session["logged_in"] = True
        return RedirectResponse("/", status_code=302)
    return RedirectResponse("/login", status_code=302)

async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=302)
