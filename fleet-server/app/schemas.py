from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class DeviceStatBase(BaseModel):
    device_id: str
    timestamp: str
    sensor1: float
    sensor2: float
    sensor3: float


class DeviceStatCreate(DeviceStatBase):
    pass


class DeviceStat(DeviceStatBase):
    id: int
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class DeviceInfo(BaseModel):
    device_id: str
    last_seen: str
    sensor1: float
    sensor2: float
    sensor3: float


class CommandRequest(BaseModel):
    command: str
    payload: Optional[dict] = None


class CommandLog(BaseModel):
    id: int
    command_id: str
    device_id: str
    command: str
    payload: Optional[str] = None
    status: str
    sent_at: Optional[datetime] = None
    responded_at: Optional[datetime] = None

    class Config:
        from_attributes = True
