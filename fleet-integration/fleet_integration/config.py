from __future__ import annotations

import os
import uuid
from dataclasses import dataclass, field


@dataclass
class DeviceConfig:
    """Runtime configuration for a FleetDevice.

    All fields have sensible defaults and can be overridden via constructor
    arguments or the matching environment variables.

    Environment variables (checked only when the default is used):
        MQTT_BROKER     — broker hostname  (default: localhost)
        MQTT_PORT       — broker port      (default: 1883)
        DEVICE_ID       — device identifier (default: device-<random 6 hex chars>)
        DEVICE_VERSION  — initial firmware version (default: v1.0.0)
        STATS_INTERVAL_MIN — minimum seconds between stat publishes (default: 2.0)
        STATS_INTERVAL_MAX — maximum seconds between stat publishes (default: 5.0)
    """

    broker: str = field(default_factory=lambda: os.getenv("MQTT_BROKER", "localhost"))
    port: int = field(default_factory=lambda: int(os.getenv("MQTT_PORT", "1883")))
    device_id: str = field(
        default_factory=lambda: os.getenv("DEVICE_ID", f"device-{uuid.uuid4().hex[:6]}")
    )
    version: str = field(default_factory=lambda: os.getenv("DEVICE_VERSION", "v1.0.0"))
    stats_interval_min: float = field(
        default_factory=lambda: float(os.getenv("STATS_INTERVAL_MIN", "2.0"))
    )
    stats_interval_max: float = field(
        default_factory=lambda: float(os.getenv("STATS_INTERVAL_MAX", "5.0"))
    )
    reconnect_delay: float = 3.0
