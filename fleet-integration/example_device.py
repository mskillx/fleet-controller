"""Example: run a simulated device using the fleet-integration SDK.

This replicates the behaviour of device-simulator/simulator.py but is built
on top of the reusable FleetDevice class.

Run:
    poetry run python example_device.py

Environment variables (all optional):
    MQTT_BROKER, MQTT_PORT, DEVICE_ID, DEVICE_VERSION,
    STATS_INTERVAL_MIN, STATS_INTERVAL_MAX
"""

import logging

from fleet_integration import DeviceConfig, FleetDevice

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

device = FleetDevice(DeviceConfig())

# All built-in commands (ping, reboot, reset_sensors, report_full,
# update_software) are registered automatically.
# Override or add commands with the @device.command decorator, e.g.:
#
# @device.command("my_command")
# def handle_my_command(cmd):
#     return {"result": "ok"}

if __name__ == "__main__":
    device.run()
