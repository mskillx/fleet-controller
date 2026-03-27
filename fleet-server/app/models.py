from sqlalchemy import Column, String, Float, DateTime, Integer, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class Factory(Base):
    __tablename__ = "factories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    devices = relationship("Device", back_populates="factory")


class Device(Base):
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String, unique=True, nullable=False, index=True)
    factory_id = Column(Integer, ForeignKey("factories.id"), nullable=True)
    registered_at = Column(DateTime(timezone=True), server_default=func.now())

    factory = relationship("Factory", back_populates="devices")


class DeviceStat(Base):
    __tablename__ = "device_stats"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String, index=True, nullable=False)
    timestamp = Column(String, nullable=False)
    sensor1 = Column(Float, nullable=False)
    sensor2 = Column(Float, nullable=False)
    sensor3 = Column(Float, nullable=False)
    version = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class CommandLog(Base):
    __tablename__ = "command_logs"

    id = Column(Integer, primary_key=True, index=True)
    command_id = Column(String, unique=True, index=True, nullable=False)
    device_id = Column(String, index=True, nullable=False)
    command = Column(String, nullable=False)
    payload = Column(String, nullable=True)       # JSON string
    status = Column(String, default="sent")       # sent | executed | failed
    response = Column(String, nullable=True)      # JSON string from device
    sent_at = Column(DateTime(timezone=True), server_default=func.now())
    responded_at = Column(DateTime(timezone=True), nullable=True)
