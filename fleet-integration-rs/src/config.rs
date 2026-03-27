use std::env;

/// Runtime configuration for a [`FleetDevice`](crate::FleetDevice).
///
/// All fields have sensible defaults and can be overridden via constructor
/// arguments or the matching environment variables.
///
/// | Field | Env var | Default |
/// |---|---|---|
/// | `broker` | `MQTT_BROKER` | `localhost` |
/// | `port` | `MQTT_PORT` | `1883` |
/// | `device_id` | `DEVICE_ID` | `device-<random 6 hex chars>` |
/// | `version` | `DEVICE_VERSION` | `v1.0.0` |
/// | `stats_interval_min` | `STATS_INTERVAL_MIN` | `2.0` |
/// | `stats_interval_max` | `STATS_INTERVAL_MAX` | `5.0` |
#[derive(Debug, Clone)]
pub struct DeviceConfig {
    pub broker: String,
    pub port: u16,
    pub device_id: String,
    pub version: String,
    pub stats_interval_min: f64,
    pub stats_interval_max: f64,
    pub reconnect_delay_secs: f64,
}

impl Default for DeviceConfig {
    fn default() -> Self {
        let device_id = env::var("DEVICE_ID").unwrap_or_else(|_| {
            let suffix: String = (0..6)
                .map(|_| format!("{:x}", rand::random::<u8>() & 0xf))
                .collect();
            format!("device-{suffix}")
        });

        Self {
            broker: env::var("MQTT_BROKER").unwrap_or_else(|_| "localhost".into()),
            port: env::var("MQTT_PORT")
                .ok()
                .and_then(|v| v.parse().ok())
                .unwrap_or(1883),
            device_id,
            version: env::var("DEVICE_VERSION").unwrap_or_else(|_| "v1.0.0".into()),
            stats_interval_min: env::var("STATS_INTERVAL_MIN")
                .ok()
                .and_then(|v| v.parse().ok())
                .unwrap_or(0.3),
            stats_interval_max: env::var("STATS_INTERVAL_MAX")
                .ok()
                .and_then(|v| v.parse().ok())
                .unwrap_or(1.0),
            reconnect_delay_secs: 3.0,
        }
    }
}
