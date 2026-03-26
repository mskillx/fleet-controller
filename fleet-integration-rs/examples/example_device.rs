/// Example: run a simulated device using the fleet-integration SDK.
///
/// Replicates the behaviour of device-simulator/simulator.py but is built
/// on top of the reusable FleetDevice struct.
///
/// Run:
///     cargo run --example example_device
///
/// Environment variables (all optional):
///     MQTT_BROKER, MQTT_PORT, DEVICE_ID, DEVICE_VERSION,
///     STATS_INTERVAL_MIN, STATS_INTERVAL_MAX
use fleet_integration::{DeviceConfig, FleetDevice};

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| "info".into()),
        )
        .init();

    let device = FleetDevice::new(DeviceConfig::default());

    // All built-in commands (ping, reboot, reset_sensors, report_full,
    // update_software) are registered automatically.
    //
    // Override or add commands with on_command, e.g.:
    //
    // device.on_command("my_command", |_cmd| {
    //     serde_json::json!({"result": "ok"})
    // });

    device.run().await
}
