# app/database.py

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./meter.db")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# ✅ Only create tables if DB file doesn't exist (SQLite)
if DATABASE_URL.startswith("sqlite:///"):
    from urllib.parse import urlparse

    parsed = urlparse(DATABASE_URL)
    db_path = os.path.abspath(os.path.join(".", parsed.path.lstrip("/")))

    if not os.path.exists(db_path):
        print(f"🛠 Creating new DB at {db_path}")
        Base.metadata.create_all(bind=engine)
    else:
        print(f"📦 Existing DB detected at {db_path}, skipping create_all()")
else:
    # Optional: For other DBs (PostgreSQL, MySQL) you may still want to run create_all
    Base.metadata.create_all(bind=engine)
