from sqlalchemy import Column, String, Float, DateTime, Integer
from sqlalchemy.sql import func
from app.database import Base


class DeviceStat(Base):
    __tablename__ = "device_stats"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String, index=True, nullable=False)
    timestamp = Column(String, nullable=False)
    sensor1 = Column(Float, nullable=False)
    sensor2 = Column(Float, nullable=False)
    sensor3 = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class CommandLog(Base):
    __tablename__ = "command_logs"

    id = Column(Integer, primary_key=True, index=True)
    command_id = Column(String, unique=True, index=True, nullable=False)
    device_id = Column(String, index=True, nullable=False)
    command = Column(String, nullable=False)
    payload = Column(String, nullable=True)       # JSON string
    status = Column(String, default="sent")       # sent | executed | failed
    sent_at = Column(DateTime(timezone=True), server_default=func.now())
    responded_at = Column(DateTime(timezone=True), nullable=True)
