from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional

from app.database import get_db
from app import models, schemas

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/", response_model=List[schemas.DeviceInfo])
def get_all_stats(db: Session = Depends(get_db)):
    """Get latest stats for all devices."""
    subquery = (
        db.query(
            models.DeviceStat.device_id,
            func.max(models.DeviceStat.id).label("max_id"),
        )
        .group_by(models.DeviceStat.device_id)
        .subquery()
    )
    latest = (
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
        )
        for s in latest
    ]


@router.get("/history", response_model=List[schemas.DeviceStat])
def get_history(
    device_id: Optional[str] = Query(None),
    limit: int = Query(100, le=500),
    db: Session = Depends(get_db),
):
    """Get historical stats, optionally filtered by device_id."""
    query = db.query(models.DeviceStat)
    if device_id:
        query = query.filter(models.DeviceStat.device_id == device_id)
    return query.order_by(models.DeviceStat.id.desc()).limit(limit).all()
