from pydantic import BaseModel
from typing import Optional, List, Union, Literal
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
    current_version: Optional[str] = None
    registered_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class DeviceStatBase(BaseModel):
    device_id: str
    timestamp: str
    last_acquisition: Optional[str] = None
    last_boot: Optional[str] = None
    lights_on: Optional[bool] = None
    disk_usage: Optional[float] = None
    analysis_queue: Optional[int] = None
    is_camera_acquiring: Optional[bool] = None
    lidar: Optional[float] = None
    com4: Optional[float] = None


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
    current_version: Optional[str] = None
    last_acquisition: Optional[str] = None
    last_boot: Optional[str] = None
    lights_on: Optional[bool] = None
    disk_usage: Optional[float] = None
    analysis_queue: Optional[int] = None
    is_camera_acquiring: Optional[bool] = None
    lidar: Optional[float] = None
    com4: Optional[float] = None
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


# ── Update / OTA schemas ─────────────────────────────────────────────────────

class UpdatePackage(BaseModel):
    id: int
    version: str
    filename: str
    checksum_sha256: str
    size_bytes: Optional[int] = None
    is_active: bool
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class UpdateJobStatus(BaseModel):
    id: int
    deploy_id: str
    device_id: str
    version: str
    batch_index: int
    status: str
    error_msg: Optional[str] = None
    command_id: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class DeployRequest(BaseModel):
    """Request body for deploying an update package."""
    # "all" or an explicit list of device_ids
    target: Union[Literal["all"], List[str]] = "all"
    batch_size: int = 10
    batch_delay_seconds: int = 60
    # Fraction of a batch that must succeed before the next batch is triggered
    success_threshold: float = 0.9


class DeployResponse(BaseModel):
    deploy_id: str
    version: str
    total_devices: int
    batches: int
    message: str


class DeploymentSummary(BaseModel):
    deploy_id: str
    version: str
    total: int
    pending: int
    downloading: int
    installing: int
    success: int
    failed: int
    rolledback: int
    aborted: int
