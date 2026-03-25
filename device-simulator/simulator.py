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


def on_connect(client, userdata, flags, rc, properties=None):
    logger.info(f"[{DEVICE_ID}] Connected to broker (rc={rc})")
    client.subscribe(f"fleet/{DEVICE_ID}/commands")


def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode())
        logger.info(f"[{DEVICE_ID}] Received command: {payload}")
        response = {
            "device_id": DEVICE_ID,
            "command_id": payload.get("command_id"),
            "status": "executed",
            "timestamp": datetime.now(timezone.utc).isoformat(),
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

    while True:
        stats = generate_stats()
        topic = f"fleet/{DEVICE_ID}/stats"
        client.publish(topic, json.dumps(stats))
        logger.debug(f"[{DEVICE_ID}] Published to {topic}: {stats}")
        time.sleep(random.uniform(2, 5)/3)


if __name__ == "__main__":
    main()
