from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class FactoryBase(BaseModel):
    name: str


class FactoryCreate(FactoryBase):
    pass


class Factory(FactoryBase):
    id: int
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class DeviceBase(BaseModel):
    device_id: str


class Device(DeviceBase):
    id: int
    factory_id: Optional[int] = None
    factory: Optional[Factory] = None
    registered_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class DeviceStatBase(BaseModel):
    device_id: str
    timestamp: str
    sensor1: float
    sensor2: float
    sensor3: float
    version: Optional[str] = None


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
    version: Optional[str] = None
    factory_name: Optional[str] = None



class FactoryWithDevices(Factory):
    devices: List[Device] = []


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
    response: Optional[str] = None
    sent_at: Optional[datetime] = None
    responded_at: Optional[datetime] = None

    class Config:
        from_attributes = True
