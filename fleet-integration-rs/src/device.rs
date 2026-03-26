use std::collections::HashMap;
use std::sync::{Arc, Mutex, RwLock};
use std::time::Duration;

use rand::Rng;
use rumqttc::{AsyncClient, Event, MqttOptions, Packet, QoS};
use serde_json::{json, Value};
use tracing::{debug, error, info, warn};

use crate::config::DeviceConfig;
use crate::models::{CommandPayload, CommandResponse, DeviceStats};

// ---------------------------------------------------------------------------
// Type aliases
// ---------------------------------------------------------------------------

type CommandHandler = Arc<dyn Fn(&CommandPayload) -> Value + Send + Sync>;
type StatsGenerator = Arc<dyn Fn() -> DeviceStats + Send + Sync>;

// ---------------------------------------------------------------------------
// FleetDevice
// ---------------------------------------------------------------------------

/// MQTT-based fleet device SDK.
///
/// Handles:
/// - Connecting (with automatic retry) to the MQTT broker.
/// - Periodically publishing telemetry stats.
/// - Receiving commands and dispatching them to registered handlers.
/// - Publishing command responses.
///
/// # Basic usage
///
/// ```no_run
/// use fleet_integration::{FleetDevice, DeviceConfig};
///
/// #[tokio::main]
/// async fn main() {
///     let device = FleetDevice::new(DeviceConfig::default());
///     device.run().await.unwrap();
/// }
/// ```
///
/// # Custom stats
///
/// ```no_run
/// # use fleet_integration::{FleetDevice, DeviceConfig, DeviceStats};
/// # let device = FleetDevice::new(DeviceConfig::default());
/// device.set_stats_generator({
///     let id = device.device_id().to_string();
///     let ver = device.version();
///     move || DeviceStats::now(&id, 42.0, 65.0, 1013.0, Some(ver.clone()))
/// });
/// ```
///
/// # Custom command handler
///
/// ```no_run
/// # use fleet_integration::FleetDevice;
/// # use serde_json::json;
/// # let device = FleetDevice::new(Default::default());
/// device.on_command("ping", |_cmd| json!({"message": "pong"}));
/// ```
///
/// # Background usage
///
/// ```no_run
/// # use fleet_integration::FleetDevice;
/// # use std::sync::Arc;
/// let device = Arc::new(FleetDevice::new(Default::default()));
/// let handle = {
///     let d = Arc::clone(&device);
///     tokio::spawn(async move { d.run().await })
/// };
/// // ... do other work ...
/// handle.abort();
/// ```
pub struct FleetDevice {
    config: DeviceConfig,
    version: Arc<Mutex<String>>,
    handlers: Arc<RwLock<HashMap<String, CommandHandler>>>,
    stats_gen: Arc<RwLock<StatsGenerator>>,
}

impl FleetDevice {
    /// Create a new device with the given configuration.
    /// Built-in command handlers (`ping`, `reboot`, `reset_sensors`,
    /// `report_full`, `update_software`) are registered automatically.
    pub fn new(config: DeviceConfig) -> Self {
        let version = Arc::new(Mutex::new(config.version.clone()));
        let handlers = Arc::new(RwLock::new(HashMap::<String, CommandHandler>::new()));

        let device = Self {
            stats_gen: Arc::new(RwLock::new(Self::make_default_stats_gen(
                &config.device_id,
                Arc::clone(&version),
            ))),
            config,
            version,
            handlers,
        };

        device.register_builtin_handlers();
        device
    }

    // ------------------------------------------------------------------
    // Public API
    // ------------------------------------------------------------------

    pub fn device_id(&self) -> &str {
        &self.config.device_id
    }

    pub fn version(&self) -> String {
        self.version.lock().unwrap().clone()
    }

    /// Register (or replace) a handler for the given command name.
    ///
    /// The closure receives a [`CommandPayload`] and must return a
    /// [`serde_json::Value`] that will be set as the `response` field
    /// of the published [`CommandResponse`].
    pub fn on_command<F>(&self, name: impl Into<String>, handler: F)
    where
        F: Fn(&CommandPayload) -> Value + Send + Sync + 'static,
    {
        self.handlers
            .write()
            .unwrap()
            .insert(name.into(), Arc::new(handler));
    }

    /// Replace the default random stats generator with a custom one.
    ///
    /// The closure must return a [`DeviceStats`] instance and will be
    /// called on every stats publish interval.
    pub fn set_stats_generator<F>(&self, generator: F)
    where
        F: Fn() -> DeviceStats + Send + Sync + 'static,
    {
        *self.stats_gen.write().unwrap() = Arc::new(generator);
    }

    // ------------------------------------------------------------------
    // Lifecycle
    // ------------------------------------------------------------------

    /// Connect to the broker and run forever, blocking the current task.
    /// Handles Ctrl-C gracefully.
    pub async fn run(&self) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
        let (client, mut eventloop) = self.create_mqtt_client();
        let client = Arc::new(client);

        // Spawn the periodic stats publisher
        {
            let stats_client = Arc::clone(&client);
            let stats_gen = Arc::clone(&self.stats_gen);
            let device_id = self.config.device_id.clone();
            let interval_min = self.config.stats_interval_min;
            let interval_max = self.config.stats_interval_max;

            tokio::spawn(async move {
                info!("[{device_id}] Starting stats publish loop…");
                loop {
                    let stats = { stats_gen.read().unwrap().clone()() };
                    match serde_json::to_string(&stats) {
                        Ok(payload) => {
                            let topic = format!("fleet/{device_id}/stats");
                            if let Err(e) = stats_client
                                .publish(&topic, QoS::AtLeastOnce, false, payload)
                                .await
                            {
                                error!("[{device_id}] Failed to publish stats: {e}");
                            } else {
                                debug!("[{device_id}] Published stats");
                            }
                        }
                        Err(e) => error!("[{device_id}] Failed to serialize stats: {e}"),
                    }

                    let interval = rand::thread_rng().gen_range(interval_min..interval_max);
                    tokio::time::sleep(Duration::from_secs_f64(interval)).await;
                }
            });
        }

        // Drive the MQTT event loop
        loop {
            match eventloop.poll().await {
                Ok(Event::Incoming(Packet::ConnAck(_))) => {
                    info!("[{}] Connected to broker", self.config.device_id);
                    let topic = format!("fleet/{}/commands", self.config.device_id);
                    client.subscribe(&topic, QoS::AtLeastOnce).await?;
                }
                Ok(Event::Incoming(Packet::Publish(msg))) => {
                    let client = Arc::clone(&client);
                    let handlers = Arc::clone(&self.handlers);
                    let device_id = self.config.device_id.clone();
                    tokio::spawn(async move {
                        handle_incoming(client, handlers, device_id, msg).await;
                    });
                }
                Ok(_) => {}
                Err(e) => {
                    warn!(
                        "[{}] MQTT error: {e} — retrying in {}s…",
                        self.config.device_id, self.config.reconnect_delay_secs
                    );
                    tokio::time::sleep(Duration::from_secs_f64(
                        self.config.reconnect_delay_secs,
                    ))
                    .await;
                }
            }
        }
    }

    // ------------------------------------------------------------------
    // Internal helpers
    // ------------------------------------------------------------------

    fn create_mqtt_client(&self) -> (AsyncClient, rumqttc::EventLoop) {
        let mut options = MqttOptions::new(
            &self.config.device_id,
            &self.config.broker,
            self.config.port,
        );
        options.set_keep_alive(Duration::from_secs(60));
        AsyncClient::new(options, 10)
    }

    fn make_default_stats_gen(
        device_id: &str,
        version: Arc<Mutex<String>>,
    ) -> StatsGenerator {
        let device_id = device_id.to_string();
        Arc::new(move || {
            let mut rng = rand::thread_rng();
            let round2 = |v: f64| (v * 100.0).round() / 100.0;
            DeviceStats::now(
                &device_id,
                round2(rng.gen_range(0.0_f64..100.0)),
                round2(rng.gen_range(20.0_f64..80.0)),
                round2(rng.gen_range(-10.0_f64..50.0)),
                Some(version.lock().unwrap().clone()),
            )
        })
    }

    fn register_builtin_handlers(&self) {
        self.on_command("ping", |_cmd| json!({"message": "pong"}));

        self.on_command("reboot", |_cmd| {
            let eta = rand::thread_rng().gen_range(5u64..30);
            json!({"message": "Rebooting device", "eta_seconds": eta})
        });

        self.on_command("reset_sensors", |_cmd| {
            json!({"message": "Sensors reset", "values": [0.0, 0.0, 0.0]})
        });

        self.on_command("report_full", |_cmd| {
            let mut rng = rand::thread_rng();
            let round2 = |v: f64| (v * 100.0).round() / 100.0;
            json!({
                "message": "Full report",
                "sensor1": round2(rng.gen_range(0.0_f64..100.0)),
                "sensor2": round2(rng.gen_range(20.0_f64..80.0)),
                "sensor3": round2(rng.gen_range(-10.0_f64..50.0)),
                "uptime_seconds": rng.gen_range(100u64..100_000),
            })
        });

        let version = Arc::clone(&self.version);
        self.on_command("update_software", move |cmd| {
            let target = cmd.payload.get("version").and_then(Value::as_str);
            let new_version = if let Some(v) = target {
                v.to_string()
            } else {
                let current = version.lock().unwrap();
                bump_version(&current)
            };
            *version.lock().unwrap() = new_version.clone();
            json!({"message": "Software updated", "version": new_version})
        });
    }
}

// ---------------------------------------------------------------------------
// Free helpers
// ---------------------------------------------------------------------------

async fn handle_incoming(
    client: Arc<AsyncClient>,
    handlers: Arc<RwLock<HashMap<String, CommandHandler>>>,
    device_id: String,
    msg: rumqttc::Publish,
) {
    let raw = match std::str::from_utf8(&msg.payload) {
        Ok(s) => s,
        Err(e) => {
            error!("[{device_id}] Non-UTF8 payload: {e}");
            return;
        }
    };

    let cmd: CommandPayload = match serde_json::from_str(raw) {
        Ok(c) => c,
        Err(e) => {
            error!("[{device_id}] Failed to parse command: {e}");
            return;
        }
    };

    info!("[{device_id}] Received command: {} (id={})", cmd.command, cmd.command_id);

    let response_data = {
        let map = handlers.read().unwrap();
        match map.get(&cmd.command) {
            Some(handler) => handler(&cmd),
            None => json!({"message": format!("Command '{}' acknowledged", cmd.command)}),
        }
    };

    let response = CommandResponse::executed(&device_id, &cmd.command_id, response_data);

    match serde_json::to_string(&response) {
        Ok(payload) => {
            let topic = format!("fleet/{device_id}/commands/response");
            if let Err(e) = client.publish(&topic, QoS::AtLeastOnce, false, payload).await {
                error!("[{device_id}] Failed to publish response: {e}");
            }
        }
        Err(e) => error!("[{device_id}] Failed to serialize response: {e}"),
    }
}

fn bump_version(version: &str) -> String {
    let prefix = version.chars().next().filter(|c| c.is_alphabetic());
    let stripped = version.trim_start_matches(|c: char| c.is_alphabetic());
    let parts: Vec<&str> = stripped.split('.').collect();
    let bumped_parts: Vec<String> = parts
        .iter()
        .enumerate()
        .map(|(i, part)| {
            if i == parts.len() - 1 {
                part.parse::<u64>()
                    .map(|n| (n + 1).to_string())
                    .unwrap_or_else(|_| part.to_string())
            } else {
                part.to_string()
            }
        })
        .collect();
    let joined = bumped_parts.join(".");
    match prefix {
        Some(p) => format!("{p}{joined}"),
        None => joined,
    }
}
