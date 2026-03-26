import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List

from app.database import get_db
from app import models, schemas
from app.mqtt_client import publish_command

router = APIRouter(prefix="/devices", tags=["devices"])


@router.get("/", response_model=List[schemas.DeviceInfo])
def list_devices(db: Session = Depends(get_db)):
    """Get all devices with their latest stats."""
    subquery = (
        db.query(
            models.DeviceStat.device_id,
            func.max(models.DeviceStat.id).label("max_id"),
        )
        .group_by(models.DeviceStat.device_id)
        .subquery()
    )
    latest_stats = (
        db.query(models.DeviceStat)
        .join(subquery, models.DeviceStat.id == subquery.c.max_id)
        .all()
    )
    return [
        schemas.DeviceInfo(
            device_id=s.device_id,
            last_seen=s.timestamp,
            sensor1=s.sensor1,
            sensor2=s.sensor2,
            sensor3=s.sensor3,
            version=s.version
        )
        for s in latest_stats
    ]


@router.get("/{device_id}/stats", response_model=schemas.DeviceStat)
def get_device_stats(device_id: str, db: Session = Depends(get_db)):
    """Get latest stats for a specific device."""
    stat = (
        db.query(models.DeviceStat)
        .filter(models.DeviceStat.device_id == device_id)
        .order_by(models.DeviceStat.id.desc())
        .first()
    )
    if not stat:
        raise HTTPException(status_code=404, detail="Device not found")
    return stat


@router.post("/{device_id}/commands", response_model=schemas.CommandLog, status_code=201)
def send_command(device_id: str, body: schemas.CommandRequest, db: Session = Depends(get_db)):
    """Send a command to a device via MQTT and log it."""
    import json as _json

    command_id = str(uuid.uuid4())
    log = models.CommandLog(
        command_id=command_id,
        device_id=device_id,
        command=body.command,
        payload=_json.dumps(body.payload) if body.payload else None,
        status="sent",
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    publish_command(device_id, command_id, body.command, body.payload)
    return log


@router.get("/{device_id}/commands", response_model=List[schemas.CommandLog])
def list_commands(device_id: str, limit: int = 50, db: Session = Depends(get_db)):
    """List command history for a device, most recent first."""
    return (
        db.query(models.CommandLog)
        .filter(models.CommandLog.device_id == device_id)
        .order_by(models.CommandLog.id.desc())
        .limit(limit)
        .all()
    )
