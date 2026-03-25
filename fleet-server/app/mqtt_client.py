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


def _handle_stats(payload: dict) -> None:
    db: Session = SessionLocal()
    try:
        stat = models.DeviceStat(
            device_id=payload["device_id"],
            timestamp=payload["timestamp"],
            sensor1=payload["sensor1"],
            sensor2=payload["sensor2"],
            sensor3=payload["sensor3"],
        )
        db.add(stat)
        db.commit()
        logger.debug(f"Stored stats for {payload['device_id']}")
        broadcast_to_websockets({"type": "stats_update", "data": payload})
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
            db.commit()
            logger.info(f"Command {command_id} acknowledged by {payload.get('device_id')} — {log.status}")
            broadcast_to_websockets({"type": "command_response", "data": payload})
    finally:
        db.close()


def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode())
        topic = msg.topic
        if "/stats" in topic:
            _handle_stats(payload)
        elif "/commands/response" in topic:
            _handle_command_response(payload)
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
