# app/models.py

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base

class DataPelanggan(Base):
    __tablename__ = "data_pelanggan"

    user_id = Column(String, primary_key=True, index=True)
    user_name = Column(String, nullable=False)
    user_address = Column(String, nullable=False)

    # Relationship to MeterRecord
    meter_records = relationship("MeterRecord", back_populates="pelanggan")


class MeterRecord(Base):
    __tablename__ = "meter_records"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("data_pelanggan.user_id"), index=True)
    sr_no = Column(String, index=True)
    drive_file_id = Column(String, nullable=False)
    record_timestamp = Column(DateTime, default=datetime.utcnow)
    meter_pos = Column(Integer, nullable=True)

    # Relationship to DataPelanggan
    pelanggan = relationship("DataPelanggan", back_populates="meter_records")
