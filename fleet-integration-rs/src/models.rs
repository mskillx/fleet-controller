use chrono::Utc;
use serde::{Deserialize, Serialize};
use serde_json::Value;

/// Telemetry payload published to `fleet/{device_id}/stats`.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DeviceStats {
    pub device_id: String,
    pub timestamp: String,
    pub sensor1: f64,
    pub sensor2: f64,
    pub sensor3: f64,
    pub version: Option<String>,
}

impl DeviceStats {
    pub fn now(
        device_id: impl Into<String>,
        sensor1: f64,
        sensor2: f64,
        sensor3: f64,
        version: Option<String>,
    ) -> Self {
        Self {
            device_id: device_id.into(),
            timestamp: Utc::now().to_rfc3339(),
            sensor1,
            sensor2,
            sensor3,
            version,
        }
    }
}

/// Inbound command received from `fleet/{device_id}/commands`.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CommandPayload {
    pub command_id: String,
    pub command: String,
    #[serde(default)]
    pub payload: serde_json::Map<String, Value>,
}

/// Response published to `fleet/{device_id}/commands/response`.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CommandResponse {
    pub device_id: String,
    pub command_id: String,
    pub status: String,
    pub timestamp: String,
    pub response: Value,
}

impl CommandResponse {
    pub fn executed(device_id: impl Into<String>, command_id: impl Into<String>, response: Value) -> Self {
        Self {
            device_id: device_id.into(),
            command_id: command_id.into(),
            status: "executed".into(),
            timestamp: Utc::now().to_rfc3339(),
            response,
        }
    }
}
