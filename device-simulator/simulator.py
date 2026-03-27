import json
import logging
import os
import random
import time
import uuid
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)



MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
DEVICE_ID = os.getenv("DEVICE_ID", f"device-{uuid.uuid4().hex[:6]}")
DEVICE_VERSION = os.getenv("DEVICE_VERSION", "v1.0.0")
FACTORY_NAME = os.getenv("FACTORY_NAME", "default-factory")


def on_connect(client, userdata, flags, rc, properties=None):
    logger.info(f"[{DEVICE_ID}] Connected to broker (rc={rc})")
    client.subscribe(f"fleet/{DEVICE_ID}/commands")
    registration = {"device_id": DEVICE_ID, "factory": FACTORY_NAME}
    client.publish(f"fleet/{DEVICE_ID}/register", json.dumps(registration))
    logger.info(f"[{DEVICE_ID}] Registered to factory '{FACTORY_NAME}'")


def bump_version(version: str) -> str:
    """Increment the patch number of a semver string like v1.0.1."""
    try:
        prefix = version[0] if version[0].isalpha() else ""
        parts = version.lstrip("vV").split(".")
        parts[-1] = str(int(parts[-1]) + 1)
        return prefix + ".".join(parts)
    except Exception:
        return version


def build_response_data(command: str, payload: dict) -> dict:
    global DEVICE_VERSION
    if command == "ping":
        return {"message": "pong"}
    if command == "reboot":
        return {"message": "Rebooting device", "eta_seconds": random.randint(5, 30)}
    if command == "reset_sensors":
        return {"message": "Sensors reset", "values": [0.0, 0.0, 0.0]}
    if command == "report_full":
        return {
            "message": "Full report",
            "sensor1": round(random.uniform(0, 100), 2),
            "sensor2": round(random.uniform(20, 80), 2),
            "sensor3": round(random.uniform(-10, 50), 2),
            "uptime_seconds": random.randint(100, 100000),
        }
    if command == "update_software":
        target = payload.get("version")
        new_version = target if target else bump_version(DEVICE_VERSION)
        DEVICE_VERSION = new_version
        return {"message": "Software updated", "version": new_version}
    return {"message": f"Command '{command}' acknowledged"}


def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode())
        logger.info(f"[{DEVICE_ID}] Received command: {payload}")
        command = payload.get("command", "")
        response = {
            "device_id": DEVICE_ID,
            "command_id": payload.get("command_id"),
            "status": "executed",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "response": build_response_data(command, payload.get("payload") or {}),
        }
        client.publish(f"fleet/{DEVICE_ID}/commands/response", json.dumps(response))
    except Exception as e:
        logger.error(f"[{DEVICE_ID}] Error handling command: {e}")


def generate_stats() -> dict:
    return {
        "device_id": DEVICE_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "sensor1": round(random.uniform(0, 100), 2),
        "sensor2": round(random.uniform(20, 80), 2),
        "sensor3": round(random.uniform(-10, 50), 2),
        "version": DEVICE_VERSION,
    }


def main():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_message = on_message

    while True:
        try:
            client.connect(MQTT_BROKER, MQTT_PORT, 60)
            break
        except Exception as e:
            logger.warning(f"[{DEVICE_ID}] Cannot connect to broker: {e}. Retrying in 3s...")
            time.sleep(3)

    client.loop_start()
    logger.info(f"[{DEVICE_ID}] Starting to publish stats...")

    REGISTER_INTERVAL = 60  # re-send registration every 60 seconds
    last_registered = 0.0

    while True:
        now = time.time()
        if now - last_registered >= REGISTER_INTERVAL:
            registration = {"device_id": DEVICE_ID, "factory": FACTORY_NAME}
            client.publish(f"fleet/{DEVICE_ID}/register", json.dumps(registration))
            last_registered = now

        stats = generate_stats()
        topic = f"fleet/{DEVICE_ID}/stats"
        client.publish(topic, json.dumps(stats))
        logger.debug(f"[{DEVICE_ID}] Published to {topic}: {stats}")
        time.sleep(random.uniform(2, 5))


if __name__ == "__main__":
    main()
