# app/auth.py

from fastapi import Request, Form
from fastapi.responses import RedirectResponse
from starlette.middleware.sessions import SessionMiddleware

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "password123"  # Change this securely later!

def add_auth(app):
    app.add_middleware(SessionMiddleware, secret_key="changeme")

def is_logged_in(request: Request):
    return request.session.get("logged_in", False)

async def login_form(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        request.session["logged_in"] = True
        return RedirectResponse("/admin", status_code=302)
    return RedirectResponse("/login", status_code=302)

async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=302)
