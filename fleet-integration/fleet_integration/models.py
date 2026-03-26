from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


class DeviceStats(BaseModel):
    """Telemetry payload published to fleet/{device_id}/stats."""

    device_id: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    sensor1: float
    sensor2: float
    sensor3: float
    version: Optional[str] = None

    @field_validator("timestamp", mode="before")
    @classmethod
    def coerce_timestamp(cls, v: Any) -> str:
        if isinstance(v, datetime):
            return v.isoformat()
        return v


class CommandPayload(BaseModel):
    """Inbound command received from fleet/{device_id}/commands."""

    command_id: str
    command: str
    payload: dict[str, Any] = Field(default_factory=dict)


class CommandResponse(BaseModel):
    """Response published to fleet/{device_id}/commands/response."""

    device_id: str
    command_id: str
    status: str = "executed"
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    response: dict[str, Any] = Field(default_factory=dict)
