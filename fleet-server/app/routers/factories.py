from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from typing import List

from app.database import get_db
from app import models, schemas

router = APIRouter(prefix="/factories", tags=["factories"])


@router.get("/", response_model=List[schemas.FactoryWithDevices])
def list_factories(db: Session = Depends(get_db)):
    """List all factories with their registered devices."""
    return db.query(models.Factory).options(joinedload(models.Factory.devices)).all()


@router.get("/{factory_id}", response_model=schemas.FactoryWithDevices)
def get_factory(factory_id: int, db: Session = Depends(get_db)):
    factory = db.query(models.Factory).filter(models.Factory.id == factory_id).first()
    if not factory:
        raise HTTPException(status_code=404, detail="Factory not found")
    return factory


@router.post("/", response_model=schemas.Factory, status_code=201)
def create_factory(body: schemas.FactoryCreate, db: Session = Depends(get_db)):
    """Manually create a factory."""
    existing = db.query(models.Factory).filter(models.Factory.name == body.name).first()
    if existing:
        raise HTTPException(status_code=409, detail="Factory name already exists")
    factory = models.Factory(name=body.name)
    db.add(factory)
    db.commit()
    db.refresh(factory)
    return factory
