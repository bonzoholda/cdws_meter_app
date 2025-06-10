# app/models.py

from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime
from .database import Base

class MeterRecord(Base):
    __tablename__ = "meter_records"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True)
    sr_no = Column(String, index=True)
    drive_file_id = Column(String, nullable=False)
    record_timestamp = Column(DateTime, default=datetime.utcnow)
    meter_pos = Column(Integer, nullable=True)
