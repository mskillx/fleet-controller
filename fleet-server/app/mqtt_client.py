import json
import logging
import threading
from datetime import datetime, timezone
from typing import Optional, Set

import paho.mqtt.client as mqtt
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app import models

logger = logging.getLogger(__name__)

# WebSocket connections registry
websocket_clients: Set = set()

# Shared MQTT client instance (set after start_mqtt_client is called)
_client: Optional[mqtt.Client] = None


def publish_command(device_id: str, command_id: str, command: str, payload: Optional[dict]) -> None:
    """Publish a command to a specific device via MQTT."""
    if _client is None:
        raise RuntimeError("MQTT client not initialised")
    message = {"command_id": command_id, "command": command, "payload": payload or {}}
    _client.publish(f"fleet/{device_id}/commands", json.dumps(message))
    logger.info(f"Sent command '{command}' to {device_id} (id={command_id})")


def broadcast_to_websockets(data: dict):
    """Broadcast message to all connected WebSocket clients."""
    import asyncio

    message = json.dumps(data)
    disconnected = set()
    for ws in websocket_clients.copy():
        try:
            asyncio.run_coroutine_threadsafe(ws.send_text(message), ws._loop)
        except Exception:
            disconnected.add(ws)
    websocket_clients.difference_update(disconnected)


def on_connect(client, userdata, flags, rc, properties=None):
    logger.info(f"Connected to MQTT broker with result code {rc}")
    client.subscribe("fleet/+/stats")
    client.subscribe("fleet/+/commands/response")
    client.subscribe("fleet/+/register")
    client.subscribe("fleet/+/update/status")


def _handle_stats(payload: dict) -> None:
    db: Session = SessionLocal()
    try:
        stat = models.DeviceStat(
            device_id=payload["device_id"],
            timestamp=payload["clock"],
            last_acquisition=payload.get("last_acquisition"),
            last_boot=payload.get("last_boot"),
            lights_on=payload.get("lights_on"),
            disk_usage=payload.get("disk_usage"),
            analysis_queue=payload.get("analysis_queue"),
            is_camera_acquiring=payload.get("is_camera_acquiring"),
            lidar=payload.get("lidar"),
            com4=payload.get("com4"),
        )
        db.add(stat)

        # Keep device.current_version in sync with what the device reports
        reported_version = payload.get("version")
        if reported_version:
            device = (
                db.query(models.Device)
                .filter(models.Device.device_id == payload["device_id"])
                .first()
            )
            if device and device.current_version != reported_version:
                device.current_version = reported_version

        db.commit()
        logger.debug(f"Stored stats for {payload['device_id']}")
        broadcast_to_websockets({"type": "stats_update", "data": payload})
    finally:
        db.close()


def _handle_register(payload: dict) -> None:
    device_id = payload.get("device_id")
    factory_name = payload.get("factory")
    if not device_id or not factory_name:
        logger.warning(f"Invalid registration payload: {payload}")
        return
    db: Session = SessionLocal()
    try:
        factory = db.query(models.Factory).filter(models.Factory.name == factory_name).first()
        if not factory:
            factory = models.Factory(name=factory_name)
            db.add(factory)
            db.flush()

        device = db.query(models.Device).filter(models.Device.device_id == device_id).first()
        if not device:
            device = models.Device(device_id=device_id, factory_id=factory.id)
            db.add(device)
        else:
            device.factory_id = factory.id

        db.commit()
        logger.info(f"Device '{device_id}' registered to factory '{factory_name}'")
        broadcast_to_websockets({"type": "device_registered", "data": {"device_id": device_id, "factory": factory_name}})
    finally:
        db.close()


def _handle_command_response(payload: dict) -> None:
    command_id = payload.get("command_id")
    if not command_id:
        return
    db: Session = SessionLocal()
    try:
        log = db.query(models.CommandLog).filter(models.CommandLog.command_id == command_id).first()
        if log:
            log.status = payload.get("status", "executed")
            log.responded_at = datetime.now(timezone.utc)
            if "response" in payload:
                log.response = json.dumps(payload["response"])
            db.commit()
            logger.info(f"Command {command_id} acknowledged by {payload.get('device_id')} — {log.status}")
            broadcast_to_websockets({"type": "command_response", "data": payload})
    finally:
        db.close()


def _handle_update_status(payload: dict) -> None:
    """Handle OTA progress/result messages from devices.

    Expected payload::
        {
            "device_id": str,
            "command_id": str,
            "version": str,
            "status": "downloading" | "installing" | "success" | "failed" | "rolledback",
            "error": str | None,
            "timestamp": ISO-8601 str
        }
    """
    command_id = payload.get("command_id")
    status = payload.get("status")
    device_id = payload.get("device_id")
    if not command_id or not status:
        logger.warning(f"Invalid update/status payload: {payload}")
        return

    db: Session = SessionLocal()
    try:
        job = (
            db.query(models.UpdateJob)
            .filter(models.UpdateJob.command_id == command_id)
            .first()
        )
        if job:
            job.status = status
            if payload.get("error"):
                job.error_msg = payload["error"]
            if status in {"success", "failed", "rolledback", "aborted"}:
                job.finished_at = datetime.now(timezone.utc)

            # On success, persist the new version on the Device record
            if status == "success":
                version = payload.get("version")
                if version:
                    device = (
                        db.query(models.Device)
                        .filter(models.Device.device_id == device_id)
                        .first()
                    )
                    if device:
                        device.current_version = version

            db.commit()
            logger.info(f"UpdateJob {command_id} ({device_id}) → {status}")
        else:
            logger.warning(f"No UpdateJob found for command_id={command_id}")

        broadcast_to_websockets({"type": "update_status", "data": payload})
    finally:
        db.close()


def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode())
        topic = msg.topic
        if "/stats" in topic:
            _handle_stats(payload)
        elif "/update/status" in topic:
            _handle_update_status(payload)
        elif "/commands/response" in topic:
            _handle_command_response(payload)
        elif "/register" in topic:
            _handle_register(payload)
    except Exception as e:
        logger.error(f"Error processing MQTT message: {e}")


def create_mqtt_client() -> mqtt.Client:
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_message = on_message
    return client


def start_mqtt_client() -> mqtt.Client:
    global _client
    _client = create_mqtt_client()
    try:
        _client.connect(settings.mqtt_broker, settings.mqtt_port, 60)
        thread = threading.Thread(target=_client.loop_forever, daemon=True)
        thread.start()
        logger.info("MQTT client started")
    except Exception as e:
        logger.error(f"Failed to connect to MQTT broker: {e}")
    return _client
