"""OTA update router.

Endpoints
---------
POST   /updates/                       Upload a new software package (zip)
GET    /updates/                       List all packages
GET    /updates/latest                 Latest active package info
GET    /updates/{version}/download     Stream the zip file to a device
GET    /updates/{version}/checksum     Return SHA-256 checksum
DELETE /updates/{version}              Deactivate (soft-delete) a package
POST   /updates/{version}/deploy       Trigger a staged rollout
GET    /updates/deployments            List all deployment summaries
GET    /updates/deployments/{deploy_id} Per-device job status for a deployment
GET    /updates/jobs/{device_id}       Update history for a single device
"""
import hashlib
import json
import logging
import os
import threading
import time
import uuid
from datetime import datetime, timezone
from math import ceil
from typing import List

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app import models, schemas
from app.config import settings
from app.database import SessionLocal, get_db
from app.mqtt_client import publish_command

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/updates", tags=["updates"])

TERMINAL_STATUSES = {"success", "failed", "rolledback", "aborted"}


# ── helpers ──────────────────────────────────────────────────────────────────

def _packages_dir() -> str:
    path = settings.update_packages_dir
    os.makedirs(path, exist_ok=True)
    return path


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _get_package_or_404(version: str, db: Session) -> models.UpdatePackage:
    pkg = (
        db.query(models.UpdatePackage)
        .filter(models.UpdatePackage.version == version, models.UpdatePackage.is_active == True)
        .first()
    )
    if not pkg:
        raise HTTPException(status_code=404, detail=f"Package '{version}' not found")
    return pkg


def _all_device_ids(db: Session) -> List[str]:
    rows = db.query(models.Device.device_id).all()
    return [r.device_id for r in rows]


# ── upload ────────────────────────────────────────────────────────────────────

@router.post("/", response_model=schemas.UpdatePackage, status_code=201)
def upload_package(version: str, file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Upload a zip package for the given version string (e.g. '1.2.3')."""
    if db.query(models.UpdatePackage).filter(models.UpdatePackage.version == version).first():
        raise HTTPException(status_code=409, detail=f"Version '{version}' already exists")

    dest_path = os.path.join(_packages_dir(), f"package-{version}.zip")
    size = 0
    with open(dest_path, "wb") as out:
        while chunk := file.file.read(65536):
            out.write(chunk)
            size += len(chunk)

    checksum = _sha256(dest_path)
    pkg = models.UpdatePackage(
        version=version,
        filename=os.path.basename(dest_path),
        checksum_sha256=checksum,
        size_bytes=size,
        is_active=True,
    )
    db.add(pkg)
    db.commit()
    db.refresh(pkg)
    logger.info(f"Package {version} uploaded ({size} bytes, sha256={checksum})")
    return pkg


# ── list / latest ─────────────────────────────────────────────────────────────

@router.get("/", response_model=List[schemas.UpdatePackage])
def list_packages(db: Session = Depends(get_db)):
    return db.query(models.UpdatePackage).order_by(models.UpdatePackage.id.desc()).all()


@router.get("/latest", response_model=schemas.UpdatePackage)
def latest_package(db: Session = Depends(get_db)):
    pkg = (
        db.query(models.UpdatePackage)
        .filter(models.UpdatePackage.is_active == True)
        .order_by(models.UpdatePackage.id.desc())
        .first()
    )
    if not pkg:
        raise HTTPException(status_code=404, detail="No active packages")
    return pkg


# ── download / checksum ───────────────────────────────────────────────────────

@router.get("/{version}/download")
def download_package(version: str, db: Session = Depends(get_db)):
    """Stream the zip file — called by devices during OTA update."""
    pkg = _get_package_or_404(version, db)
    file_path = os.path.join(_packages_dir(), pkg.filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Package file missing on server")
    return FileResponse(
        path=file_path,
        media_type="application/zip",
        filename=pkg.filename,
        headers={"X-Checksum-SHA256": pkg.checksum_sha256},
    )


@router.get("/{version}/checksum")
def get_checksum(version: str, db: Session = Depends(get_db)):
    pkg = _get_package_or_404(version, db)
    return {"version": version, "algorithm": "sha256", "checksum": pkg.checksum_sha256}


# ── deactivate ────────────────────────────────────────────────────────────────

@router.delete("/{version}", status_code=204)
def deactivate_package(version: str, db: Session = Depends(get_db)):
    pkg = _get_package_or_404(version, db)
    pkg.is_active = False
    db.commit()


# ── deploy ────────────────────────────────────────────────────────────────────

@router.post("/{version}/deploy", response_model=schemas.DeployResponse, status_code=202)
def deploy_update(
    version: str,
    body: schemas.DeployRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Trigger a staged OTA rollout. Returns immediately; deployment runs in background."""
    pkg = _get_package_or_404(version, db)

    if body.target == "all":
        device_ids = _all_device_ids(db)
    else:
        device_ids = list(body.target)

    if not device_ids:
        raise HTTPException(status_code=400, detail="No target devices found")

    deploy_id = str(uuid.uuid4())
    batches = [
        device_ids[i : i + body.batch_size]
        for i in range(0, len(device_ids), body.batch_size)
    ]

    # Pre-create all jobs so the caller can query status immediately
    for batch_idx, batch in enumerate(batches):
        for device_id in batch:
            job = models.UpdateJob(
                deploy_id=deploy_id,
                device_id=device_id,
                version=version,
                batch_index=batch_idx,
                status="pending",
            )
            db.add(job)
    db.commit()

    background_tasks.add_task(
        _run_deployment,
        deploy_id=deploy_id,
        pkg_version=version,
        pkg_checksum=pkg.checksum_sha256,
        batches=batches,
        batch_delay=body.batch_delay_seconds,
        success_threshold=body.success_threshold,
    )

    logger.info(
        f"Deploy {deploy_id}: v{version} → {len(device_ids)} devices "
        f"in {len(batches)} batches of {body.batch_size}"
    )
    return schemas.DeployResponse(
        deploy_id=deploy_id,
        version=version,
        total_devices=len(device_ids),
        batches=len(batches),
        message=f"Deploying {version} to {len(device_ids)} devices in {len(batches)} batch(es)",
    )


def _run_deployment(
    deploy_id: str,
    pkg_version: str,
    pkg_checksum: str,
    batches: List[List[str]],
    batch_delay: int,
    success_threshold: float,
) -> None:
    """Background thread: sends MQTT update commands batch by batch."""
    download_url = f"{settings.server_base_url}/updates/{pkg_version}/download"

    for batch_idx, batch in enumerate(batches):
        # Check previous batch success rate before proceeding (skip for batch 0)
        if batch_idx > 0:
            if not _wait_for_batch_and_check(
                deploy_id, batch_idx - 1, batch_delay, success_threshold
            ):
                logger.warning(
                    f"Deploy {deploy_id}: batch {batch_idx - 1} below threshold "
                    f"({success_threshold:.0%}), aborting remaining batches"
                )
                _abort_remaining(deploy_id, batch_idx)
                return

        logger.info(f"Deploy {deploy_id}: starting batch {batch_idx} ({len(batch)} devices)")
        for device_id in batch:
            _dispatch_job(deploy_id, device_id, pkg_version, pkg_checksum, download_url, batch_idx)

    # Wait for final batch to settle (fire-and-forget — we just log the outcome)
    _wait_for_batch_and_check(deploy_id, len(batches) - 1, batch_delay, 0.0)
    logger.info(f"Deploy {deploy_id}: all batches dispatched")


def _dispatch_job(
    deploy_id: str,
    device_id: str,
    version: str,
    checksum: str,
    download_url: str,
    batch_idx: int,
) -> None:
    command_id = str(uuid.uuid4())
    db: Session = SessionLocal()
    try:
        job = (
            db.query(models.UpdateJob)
            .filter(
                models.UpdateJob.deploy_id == deploy_id,
                models.UpdateJob.device_id == device_id,
                models.UpdateJob.batch_index == batch_idx,
            )
            .first()
        )
        if job:
            job.command_id = command_id
            db.commit()

        publish_command(
            device_id,
            command_id,
            "update",
            {
                "version": version,
                "download_url": download_url,
                "checksum_sha256": checksum,
                "checksum_algorithm": "sha256",
            },
        )
        logger.info(f"Deploy {deploy_id}: sent update command to {device_id} (cmd={command_id})")
    except Exception as exc:
        logger.error(f"Deploy {deploy_id}: failed to dispatch to {device_id}: {exc}")
        if job:
            job.status = "failed"
            job.error_msg = str(exc)
            job.finished_at = datetime.now(timezone.utc)
            db.commit()
    finally:
        db.close()


def _wait_for_batch_and_check(
    deploy_id: str, batch_idx: int, max_wait: int, threshold: float
) -> bool:
    """Poll until all jobs in a batch reach a terminal state or max_wait expires."""
    deadline = time.time() + max_wait
    while time.time() < deadline:
        db: Session = SessionLocal()
        try:
            jobs = (
                db.query(models.UpdateJob)
                .filter(
                    models.UpdateJob.deploy_id == deploy_id,
                    models.UpdateJob.batch_index == batch_idx,
                )
                .all()
            )
        finally:
            db.close()

        if not jobs:
            return True

        done = [j for j in jobs if j.status in TERMINAL_STATUSES]
        if len(done) == len(jobs):
            successes = sum(1 for j in jobs if j.status == "success")
            rate = successes / len(jobs)
            logger.info(
                f"Deploy {deploy_id}: batch {batch_idx} done — "
                f"{successes}/{len(jobs)} succeeded ({rate:.0%})"
            )
            return rate >= threshold

        time.sleep(5)

    # Timeout: treat non-terminal jobs as failed
    logger.warning(f"Deploy {deploy_id}: batch {batch_idx} timed out after {max_wait}s")
    db: Session = SessionLocal()
    try:
        jobs = (
            db.query(models.UpdateJob)
            .filter(
                models.UpdateJob.deploy_id == deploy_id,
                models.UpdateJob.batch_index == batch_idx,
                models.UpdateJob.status.notin_(TERMINAL_STATUSES),
            )
            .all()
        )
        for j in jobs:
            j.status = "failed"
            j.error_msg = "Timed out waiting for device response"
            j.finished_at = datetime.now(timezone.utc)
        db.commit()

        all_jobs = (
            db.query(models.UpdateJob)
            .filter(
                models.UpdateJob.deploy_id == deploy_id,
                models.UpdateJob.batch_index == batch_idx,
            )
            .all()
        )
        successes = sum(1 for j in all_jobs if j.status == "success")
        return (successes / len(all_jobs)) >= threshold if all_jobs else True
    finally:
        db.close()


def _abort_remaining(deploy_id: str, from_batch_idx: int) -> None:
    db: Session = SessionLocal()
    try:
        jobs = (
            db.query(models.UpdateJob)
            .filter(
                models.UpdateJob.deploy_id == deploy_id,
                models.UpdateJob.batch_index >= from_batch_idx,
                models.UpdateJob.status == "pending",
            )
            .all()
        )
        for j in jobs:
            j.status = "aborted"
            j.error_msg = "Deployment aborted: previous batch below success threshold"
            j.finished_at = datetime.now(timezone.utc)
        db.commit()
    finally:
        db.close()


# ── deployment queries ────────────────────────────────────────────────────────

@router.get("/deployments", response_model=List[schemas.DeploymentSummary])
def list_deployments(db: Session = Depends(get_db)):
    """Aggregate view of every deployment campaign."""
    rows = db.query(models.UpdateJob).all()
    by_deploy: dict = {}
    for job in rows:
        d = by_deploy.setdefault(
            job.deploy_id,
            {"deploy_id": job.deploy_id, "version": job.version,
             "total": 0, "pending": 0, "downloading": 0, "installing": 0,
             "success": 0, "failed": 0, "rolledback": 0, "aborted": 0},
        )
        d["total"] += 1
        if job.status in d:
            d[job.status] += 1

    return [schemas.DeploymentSummary(**v) for v in by_deploy.values()]


@router.get("/deployments/{deploy_id}", response_model=List[schemas.UpdateJobStatus])
def get_deployment(deploy_id: str, db: Session = Depends(get_db)):
    jobs = (
        db.query(models.UpdateJob)
        .filter(models.UpdateJob.deploy_id == deploy_id)
        .order_by(models.UpdateJob.batch_index, models.UpdateJob.device_id)
        .all()
    )
    if not jobs:
        raise HTTPException(status_code=404, detail="Deployment not found")
    return jobs


@router.get("/jobs/{device_id}", response_model=List[schemas.UpdateJobStatus])
def get_device_jobs(device_id: str, limit: int = 20, db: Session = Depends(get_db)):
    return (
        db.query(models.UpdateJob)
        .filter(models.UpdateJob.device_id == device_id)
        .order_by(models.UpdateJob.id.desc())
        .limit(limit)
        .all()
    )
