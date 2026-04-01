from sqlalchemy import Boolean, Column, String, Float, DateTime, Integer, ForeignKey, UniqueConstraint, Text
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
    current_version = Column(String, nullable=True)
    registered_at = Column(DateTime(timezone=True), server_default=func.now())

    factory = relationship("Factory", back_populates="devices")


class DeviceStat(Base):
    __tablename__ = "device_stats"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String, index=True, nullable=False)
    timestamp = Column(String, nullable=False)
    last_acquisition = Column(String, nullable=True)
    last_boot = Column(String, nullable=True)
    lights_on = Column(Boolean, nullable=True)
    disk_usage = Column(Float, nullable=True)
    analysis_queue = Column(Integer, nullable=True)
    is_camera_acquiring = Column(Boolean, nullable=True)
    lidar = Column(Float, nullable=True)
    com4 = Column(Float, nullable=True)
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


class UpdatePackage(Base):
    __tablename__ = "update_packages"

    id = Column(Integer, primary_key=True, index=True)
    version = Column(String, unique=True, nullable=False, index=True)
    filename = Column(String, nullable=False)
    checksum_sha256 = Column(String, nullable=False)
    size_bytes = Column(Integer, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class UpdateJob(Base):
    """Tracks the OTA update state for a single device in a deployment."""
    __tablename__ = "update_jobs"

    id = Column(Integer, primary_key=True, index=True)
    deploy_id = Column(String, index=True, nullable=False)   # groups a deployment campaign
    device_id = Column(String, index=True, nullable=False)
    version = Column(String, nullable=False)
    batch_index = Column(Integer, nullable=False, default=0)
    # pending | downloading | installing | success | failed | rolledback | aborted
    status = Column(String, default="pending", nullable=False)
    error_msg = Column(Text, nullable=True)
    command_id = Column(String, nullable=True, index=True)   # maps to CommandLog.command_id
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    finished_at = Column(DateTime(timezone=True), nullable=True)
