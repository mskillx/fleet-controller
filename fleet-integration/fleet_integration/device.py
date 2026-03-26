from __future__ import annotations

import json
import logging
import random
import threading
import time
from collections.abc import Callable
from typing import Any, Optional

import paho.mqtt.client as mqtt

from fleet_integration.config import DeviceConfig
from fleet_integration.models import CommandPayload, CommandResponse, DeviceStats

logger = logging.getLogger(__name__)

# Type aliases
StatsGenerator = Callable[[], DeviceStats]
CommandHandler = Callable[[CommandPayload], dict[str, Any]]


class FleetDevice:
    """MQTT-based fleet device SDK.

    Handles:
    - Connecting (with automatic retry) to the MQTT broker.
    - Periodically publishing telemetry stats.
    - Receiving commands and dispatching them to registered handlers.
    - Publishing command responses.

    Basic usage
    -----------
    >>> device = FleetDevice()
    >>> device.run()          # blocks forever, publishes random stats

    Custom stats
    ------------
    >>> @device.stats_generator
    ... def my_stats() -> DeviceStats:
    ...     return DeviceStats(
    ...         device_id=device.device_id,
    ...         sensor1=read_temp(),
    ...         sensor2=read_humidity(),
    ...         sensor3=read_pressure(),
    ...         version=device.version,
    ...     )

    Custom command handler
    ----------------------
    >>> @device.command("ping")
    ... def handle_ping(cmd: CommandPayload) -> dict:
    ...     return {"message": "pong"}

    Async-friendly
    --------------
    Call `device.start()` + `device.stop()` instead of `device.run()` when you
    need the loop to run in a background thread and keep control of the main
    thread yourself.
    """

    def __init__(self, config: Optional[DeviceConfig] = None) -> None:
        self._config = config or DeviceConfig()
        self._version = self._config.version

        self._command_handlers: dict[str, CommandHandler] = {}
        self._stats_gen: StatsGenerator = self._default_stats

        self._client: Optional[mqtt.Client] = None
        self._stop_event = threading.Event()
        self._stats_thread: Optional[threading.Thread] = None

        # Register built-in command handlers
        self._register_builtin_handlers()

    # ------------------------------------------------------------------
    # Public properties
    # ------------------------------------------------------------------

    @property
    def device_id(self) -> str:
        return self._config.device_id

    @property
    def version(self) -> str:
        return self._version

    # ------------------------------------------------------------------
    # Decorator API
    # ------------------------------------------------------------------

    def command(self, name: str) -> Callable[[CommandHandler], CommandHandler]:
        """Register a handler for the given command name.

        The decorated function receives a :class:`CommandPayload` and must
        return a plain ``dict`` that will be set as the ``response`` field of
        the published :class:`CommandResponse`.

        >>> @device.command("ping")
        ... def ping(cmd: CommandPayload) -> dict:
        ...     return {"message": "pong"}
        """

        def decorator(fn: CommandHandler) -> CommandHandler:
            self._command_handlers[name] = fn
            return fn

        return decorator

    def stats_generator(self, fn: StatsGenerator) -> StatsGenerator:
        """Replace the default random stats generator with a custom one.

        The decorated function must return a :class:`DeviceStats` instance.

        >>> @device.stats_generator
        ... def my_stats() -> DeviceStats:
        ...     return DeviceStats(device_id=device.device_id, ...)
        """
        self._stats_gen = fn
        return fn

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Connect, start the MQTT loop and block until KeyboardInterrupt."""
        self._connect()
        self._client.loop_start()  # type: ignore[union-attr]
        self._stats_thread = threading.Thread(target=self._publish_stats_loop, daemon=True)
        self._stats_thread.start()
        logger.info(f"[{self.device_id}] Running. Press Ctrl-C to stop.")
        try:
            while not self._stop_event.is_set():
                time.sleep(0.5)
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()

    def start(self) -> None:
        """Connect and start background threads without blocking."""
        self._connect()
        self._client.loop_start()  # type: ignore[union-attr]
        self._stats_thread = threading.Thread(target=self._publish_stats_loop, daemon=True)
        self._stats_thread.start()

    def stop(self) -> None:
        """Disconnect and stop all background threads."""
        self._stop_event.set()
        if self._client is not None:
            self._client.loop_stop()
            self._client.disconnect()
        logger.info(f"[{self.device_id}] Stopped.")

    # ------------------------------------------------------------------
    # Internal – MQTT wiring
    # ------------------------------------------------------------------

    def _connect(self) -> None:
        self._client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message

        while not self._stop_event.is_set():
            try:
                self._client.connect(self._config.broker, self._config.port, 60)
                break
            except Exception as exc:
                logger.warning(
                    f"[{self.device_id}] Cannot connect to broker: {exc}. "
                    f"Retrying in {self._config.reconnect_delay}s…"
                )
                time.sleep(self._config.reconnect_delay)

    def _on_connect(
        self,
        client: mqtt.Client,
        userdata: Any,
        flags: Any,
        rc: int,
        properties: Any = None,
    ) -> None:
        logger.info(f"[{self.device_id}] Connected to broker (rc={rc})")
        client.subscribe(f"fleet/{self.device_id}/commands")

    def _on_message(self, client: mqtt.Client, userdata: Any, msg: mqtt.MQTTMessage) -> None:
        try:
            raw = json.loads(msg.payload.decode())
            cmd = CommandPayload(**raw)
            logger.info(f"[{self.device_id}] Received command: {cmd.command} (id={cmd.command_id})")
            response_data = self._dispatch(cmd)
            response = CommandResponse(
                device_id=self.device_id,
                command_id=cmd.command_id,
                response=response_data,
            )
            client.publish(
                f"fleet/{self.device_id}/commands/response",
                response.model_dump_json(),
            )
        except Exception as exc:
            logger.error(f"[{self.device_id}] Error handling command: {exc}")

    # ------------------------------------------------------------------
    # Internal – command dispatch
    # ------------------------------------------------------------------

    def _dispatch(self, cmd: CommandPayload) -> dict[str, Any]:
        handler = self._command_handlers.get(cmd.command)
        if handler is None:
            return {"message": f"Command '{cmd.command}' acknowledged"}
        return handler(cmd)

    def _register_builtin_handlers(self) -> None:
        @self.command("ping")
        def _ping(cmd: CommandPayload) -> dict:
            return {"message": "pong"}

        @self.command("reboot")
        def _reboot(cmd: CommandPayload) -> dict:
            return {"message": "Rebooting device", "eta_seconds": random.randint(5, 30)}

        @self.command("reset_sensors")
        def _reset_sensors(cmd: CommandPayload) -> dict:
            return {"message": "Sensors reset", "values": [0.0, 0.0, 0.0]}

        @self.command("report_full")
        def _report_full(cmd: CommandPayload) -> dict:
            return {
                "message": "Full report",
                "sensor1": round(random.uniform(0, 100), 2),
                "sensor2": round(random.uniform(20, 80), 2),
                "sensor3": round(random.uniform(-10, 50), 2),
                "uptime_seconds": random.randint(100, 100000),
            }

        @self.command("update_software")
        def _update_software(cmd: CommandPayload) -> dict:
            target = cmd.payload.get("version")
            new_version = target if target else _bump_version(self._version)
            self._version = new_version
            return {"message": "Software updated", "version": new_version}

    # ------------------------------------------------------------------
    # Internal – stats publishing
    # ------------------------------------------------------------------

    def _publish_stats_loop(self) -> None:
        logger.info(f"[{self.device_id}] Starting stats publish loop…")
        while not self._stop_event.is_set():
            try:
                stats = self._stats_gen()
                topic = f"fleet/{self.device_id}/stats"
                if self._client is not None:
                    self._client.publish(topic, stats.model_dump_json())
                    logger.debug(f"[{self.device_id}] Published stats: {stats}")
            except Exception as exc:
                logger.error(f"[{self.device_id}] Error publishing stats: {exc}")

            interval = random.uniform(
                self._config.stats_interval_min,
                self._config.stats_interval_max,
            )
            self._stop_event.wait(interval)

    def _default_stats(self) -> DeviceStats:
        return DeviceStats(
            device_id=self.device_id,
            sensor1=round(random.uniform(0, 100), 2),
            sensor2=round(random.uniform(20, 80), 2),
            sensor3=round(random.uniform(-10, 50), 2),
            version=self._version,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _bump_version(version: str) -> str:
    """Increment the patch segment of a semver string (e.g. v1.0.1 → v1.0.2)."""
    try:
        prefix = version[0] if version[0].isalpha() else ""
        parts = version.lstrip("vV").split(".")
        parts[-1] = str(int(parts[-1]) + 1)
        return prefix + ".".join(parts)
    except Exception:
        return version
