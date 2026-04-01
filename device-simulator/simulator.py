import json
import logging
import os
import random
import threading
import time
import uuid
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

from updater import get_current_version, run_update

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


STR_FORMAT = "%Y-%m-%d %H:%M:%S"
UTC = timezone.utc

MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
DEVICE_ID = os.getenv("DEVICE_ID", f"device-{uuid.uuid4().hex[:6]}")
FACTORY_NAME = os.getenv("FACTORY_NAME", "default-factory")

_boot_time = datetime.now(UTC).strftime(STR_FORMAT)
_last_trigger = time.time() - random.uniform(10, 300)


def on_connect(client, userdata, flags, rc, properties=None):
    logger.info(f"[{DEVICE_ID}] Connected to broker (rc={rc})")
    client.subscribe(f"fleet/{DEVICE_ID}/commands")
    registration = {"device_id": DEVICE_ID, "factory": FACTORY_NAME}
    client.publish(f"fleet/{DEVICE_ID}/register", json.dumps(registration))
    logger.info(f"[{DEVICE_ID}] Registered to factory '{FACTORY_NAME}'")



def build_response_data(command: str, payload: dict) -> dict:
    if command == "ping":
        return {"message": "pong", "version": get_current_version()}
    if command == "reboot":
        return {"message": "Rebooting device", "eta_seconds": random.randint(5, 30)}
    if command == "reset_sensors":
        return {"message": "Sensors reset", "disk_usage": 0.0, "lidar": 0.0, "com4": 0.0}
    if command == "report_full":
        return {
            "message": "Full report",
            "version": get_current_version(),
            "disk_usage": round(random.uniform(20, 95), 1),
            "lidar": round(random.uniform(100, 500), 1),
            "com4": round(random.uniform(0, 50), 1),
            "uptime_seconds": random.randint(100, 100000),
        }
    return {"message": f"Command '{command}' acknowledged"}


def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode())
        logger.info(f"[{DEVICE_ID}] Received command: {payload}")
        command = payload.get("command", "")
        cmd_payload = payload.get("payload") or {}
        command_id = payload.get("command_id")

        if command == "update":
            if os.getenv("OTA_UPDATER", "python").lower() == "rust":
                logger.info(f"[{DEVICE_ID}] OTA updater is rust; ignoring update command in python simulator")
                return

            # Run the OTA updater in a separate daemon thread so it can manage
            # the service lifecycle independently of this MQTT loop.
            version = cmd_payload.get("version", "")
            download_url = cmd_payload.get("download_url", "")
            checksum = cmd_payload.get("checksum_sha256", "")
            if not version or not download_url or not checksum:
                logger.error(f"[{DEVICE_ID}] Invalid update payload: {cmd_payload}")
                client.publish(
                    f"fleet/{DEVICE_ID}/commands/response",
                    json.dumps({
                        "device_id": DEVICE_ID,
                        "command_id": command_id,
                        "status": "failed",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "response": {"error": "Missing version/download_url/checksum_sha256"},
                    }),
                )
                return

            #t = threading.Thread(
            #    target=run_update,
            #    args=(client, DEVICE_ID, command_id, version, download_url, checksum),
            #    daemon=True,
            #)
            #t.start()
            logger.info(f"[{DEVICE_ID}] OTA update v{version} started in background thread")
            return

        response = {
            "device_id": DEVICE_ID,
            "command_id": command_id,
            "status": "executed",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "response": build_response_data(command, cmd_payload),
        }
        client.publish(f"fleet/{DEVICE_ID}/commands/response", json.dumps(response))
    except Exception as e:
        logger.error(f"[{DEVICE_ID}] Error handling command: {e}")


def generate_stats() -> dict:
    global _last_trigger
    if random.random() < 0.3:
        _last_trigger = time.time()
    return {
        "clock": datetime.now(UTC).strftime(STR_FORMAT),
        "last_acquisition": datetime.fromtimestamp(_last_trigger, UTC).strftime(STR_FORMAT),
        "last_boot": _boot_time,
        "device_id": DEVICE_ID,
        "version": get_current_version(),
        "lights_on": random.choice([True, False]),
        "disk_usage": round(random.uniform(20, 95), 1),
        "analysis_queue": random.randint(0, 10),
        "is_camera_acquiring": random.choice([True, False]),
        "lidar": round(random.uniform(100, 500), 1),
        "com4": round(random.uniform(0, 50), 1),
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
