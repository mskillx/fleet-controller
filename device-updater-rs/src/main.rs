use std::{
    fs::{self, File, OpenOptions},
    io::{self, Read},
    path::{Path, PathBuf},
    process::Command,
    thread,
    time::{Duration, Instant},
};

use chrono::Utc;
use clap::{Parser, Subcommand};
use log::{debug, error, info, warn};
use rand::Rng;
use reqwest::blocking::Client as HttpClient;
use rumqttc::{AsyncClient, Event, MqttOptions, Packet, QoS};
use serde_json::json;
use sha2::{Digest, Sha256};
use tempfile::Builder as TempBuilder;
use zip::ZipArchive;

#[derive(Parser, Debug)]
#[command(name = "device-updater-rs", version)]
struct Cli {
    #[arg(long, env = "MQTT_BROKER", default_value = "localhost")]
    mqtt_broker: String,

    #[arg(long, env = "MQTT_PORT", default_value_t = 1883)]
    mqtt_port: u16,

    #[arg(long, env = "DEVICE_ID")]
    device_id: Option<String>,

    #[arg(long, env = "INSTALL_BASE", default_value = "/root")]
    install_base: PathBuf,

    #[arg(long, env = "APP_LINK", default_value = "/root/unilog")]
    app_link: PathBuf,

    #[arg(long, env = "CONTROLLER_SERVICE", default_value = "controller")]
    controller_service: String,

    #[arg(long, env = "HEALTH_CHECK_TIMEOUT", default_value_t = 30.0)]
    health_timeout_secs: f64,

    #[arg(long, env = "UPDATE_FAILURE_RATE", default_value_t = 0.1)]
    update_failure_rate: f64,

    #[arg(long, env = "DEVICE_VERSION", default_value = "0.0.0")]
    device_version_default: String,

    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand, Debug)]
enum Commands {
    /// Subscribe to MQTT commands and run OTA updates on `{"command":"update"}`.
    Listen,

    /// Run exactly one update (useful for testing / running without MQTT).
    RunOnce {
        #[arg(long)]
        command_id: String,
        #[arg(long)]
        version: String,
        #[arg(long)]
        download_url: String,
        #[arg(long)]
        checksum_sha256: String,
    },
}

#[derive(Clone, Debug)]
struct OtaConfig {
    install_base: PathBuf,
    versions_dir: PathBuf,
    app_link: PathBuf,
    controller_service: String,
    health_timeout: f64,
    simulated_failure_rate: f64,
    lock_file: PathBuf,
    current_version_file: PathBuf,
    device_version_default: String,
}

impl OtaConfig {
    fn from_cli(cli: &Cli) -> Self {
        let versions_dir = cli.install_base.join("versions");
        let lock_file = cli.install_base.join(".update.lock");
        let current_version_file = cli.install_base.join(".current_version");
        Self {
            install_base: cli.install_base.clone(),
            versions_dir,
            app_link: cli.app_link.clone(),
            controller_service: cli.controller_service.clone(),
            health_timeout: cli.health_timeout_secs,
            simulated_failure_rate: cli.update_failure_rate,
            lock_file,
            current_version_file,
            device_version_default: cli.device_version_default.clone(),
        }
    }
}

fn now_iso_utc() -> String {
    Utc::now().to_rfc3339()
}

fn effective_device_id(cli: &Cli) -> String {
    cli.device_id.clone().unwrap_or_else(|| {
        let mut rng = rand::rng();
        let suffix: String = (0..6)
            .map(|_| format!("{:x}", rng.random_range(0..16)))
            .collect();
        format!("device-{}", suffix)
    })
}

fn publish_update_status(
    client: &AsyncClient,
    device_id: &str,
    command_id: &str,
    version: &str,
    status: &str,
    error: Option<&str>,
) {
    let status_topic = format!("fleet/{}/update/status", device_id);
    let payload = json!({
        "device_id": device_id,
        "command_id": command_id,
        "version": version,
        "status": status,
        "error": error,
        "timestamp": now_iso_utc(),
    });
    let _ = client.try_publish(status_topic, QoS::AtMostOnce, false, payload.to_string());

    if status == "success" || status == "failed" || status == "rolledback" {
        let command_response_topic = format!("fleet/{}/commands/response", device_id);
        let command_status = if status == "success" { "executed" } else { "failed" };
        let response = json!({
            "device_id": device_id,
            "command_id": command_id,
            "status": command_status,
            "timestamp": now_iso_utc(),
            "response": { "update_status": status, "version": version },
        });
        client
            .try_publish(command_response_topic, QoS::AtMostOnce, false, response.to_string())
            .ok();
    }

    info!("[updater] → status={}", status);
}

fn get_current_version(cfg: &OtaConfig) -> String {
    if cfg.current_version_file.exists() {
        if let Ok(s) = fs::read_to_string(&cfg.current_version_file) {
            let v = s.trim().to_string();
            if !v.is_empty() {
                return v;
            }
        }
    }
    cfg.device_version_default.clone()
}

struct UpdateLock {
    lock_file: PathBuf,
}

impl UpdateLock {
    fn acquire(cfg: &OtaConfig) -> io::Result<Self> {
        fs::create_dir_all(&cfg.install_base)?;
        let pid = std::process::id();

        let mut opts = OpenOptions::new();
        opts.write(true).create_new(true).truncate(false);

        match opts.open(&cfg.lock_file) {
            Ok(mut f) => {
                use std::io::Write;
                writeln!(f, "{}", pid)?;
                Ok(Self {
                    lock_file: cfg.lock_file.clone(),
                })
            }
            Err(e) => {
                if e.kind() == io::ErrorKind::AlreadyExists {
                    Err(io::Error::new(
                        io::ErrorKind::Other,
                        "Another update is already in progress",
                    ))
                } else {
                    Err(e)
                }
            }
        }
    }
}

impl Drop for UpdateLock {
    fn drop(&mut self) {
        let _ = fs::remove_file(&self.lock_file);
    }
}

fn sha256_file(path: &Path) -> io::Result<String> {
    let mut file = File::open(path)?;
    let mut hasher = Sha256::new();
    let mut buf = [0u8; 65536];
    loop {
        let n = file.read(&mut buf)?;
        if n == 0 {
            break;
        }
        hasher.update(&buf[..n]);
    }
    Ok(hex::encode(hasher.finalize()))
}

fn extract_zip_or_marker(zip_path: &Path, dest_base: &Path, version: &str) -> io::Result<PathBuf> {
    let dest = dest_base.join(version);

    if dest.exists() {
        fs::remove_dir_all(&dest)?;
    }
    fs::create_dir_all(&dest)?;

    // Port of Python's `zipfile.is_zipfile()` + fallback marker creation.
    let file = File::open(zip_path)?;
    match ZipArchive::new(file) {
        Ok(mut archive) => {
            for i in 0..archive.len() {
                let mut zf = archive.by_index(i)?;
                let outpath = match zf.enclosed_name() {
                    Some(p) => dest.join(p),
                    None => continue,
                };

                if zf.is_dir() {
                    fs::create_dir_all(&outpath)?;
                } else {
                    if let Some(parent) = outpath.parent() {
                        fs::create_dir_all(parent)?;
                    }
                    let mut outfile = File::create(&outpath)?;
                    io::copy(&mut zf, &mut outfile)?;
                }
            }
            info!("[updater] Extracted zip → {}", dest.display());
        }
        Err(_) => {
            info!(
                "[updater] [sim] Not a valid zip – creating version marker at {}",
                dest.display()
            );
            fs::write(dest.join("version.txt"), version)?;
        }
    }

    Ok(dest)
}

fn atomic_symlink_swap(target_dir: &Path, app_link: &Path) -> io::Result<()> {
    let tmp_path = PathBuf::from(format!("{}.tmp", app_link.display()));

    // Best-effort cleanup of old tmp.
    let _ = fs::remove_file(&tmp_path);
    let _ = fs::remove_dir_all(&tmp_path);

    #[cfg(unix)]
    {
        std::os::unix::fs::symlink(target_dir, &tmp_path)?;
    }
    #[cfg(windows)]
    {
        std::os::windows::fs::symlink_dir(target_dir, &tmp_path)?;
    }

    // `os.replace` overwrites the destination; mimic it by removing the old path first on Windows.
    let _ = fs::remove_file(app_link);
    let _ = fs::remove_dir_all(app_link);

    fs::rename(&tmp_path, app_link)?;
    info!("[updater] {} → {}", app_link.display(), target_dir.display());
    Ok(())
}

fn prune_old_versions(cfg: &OtaConfig, keep: usize) -> io::Result<()> {
    if !cfg.versions_dir.is_dir() {
        return Ok(());
    }

    let mut dirs: Vec<String> = vec![];
    for entry in fs::read_dir(&cfg.versions_dir)? {
        let entry = entry?;
        if entry.file_type()?.is_dir() {
            dirs.push(entry.file_name().to_string_lossy().to_string());
        }
    }

    dirs.sort();
    if dirs.len() <= keep {
        return Ok(());
    }

    let to_remove = dirs.len() - keep;
    for old in dirs.into_iter().take(to_remove) {
        fs::remove_dir_all(cfg.versions_dir.join(&old))?;
        info!("[updater] Pruned {}", old);
    }
    Ok(())
}

fn systemctl_available() -> bool {
    match Command::new("systemctl").arg("status").output() {
        Ok(out) => matches!(out.status.code(), Some(0) | Some(1)),
        Err(_) => false,
    }
}

fn ctl(cfg: &OtaConfig, action: &str, systemd_available: bool) -> bool {
    if systemd_available {
        match Command::new("systemctl")
            .arg(action)
            .arg(&cfg.controller_service)
            .output()
        {
            Ok(out) => {
                if !out.status.success() {
                    let stderr = String::from_utf8_lossy(&out.stderr);
                    warn!(
                        "[updater] systemctl {} {} failed (rc={}) : {}",
                        action,
                        cfg.controller_service,
                        out.status.code().unwrap_or(-1),
                        stderr.trim()
                    );
                }
                out.status.success()
            }
            Err(e) => {
                warn!(
                    "[updater] systemctl {} {} failed to run: {}",
                    action, cfg.controller_service, e
                );
                false
            }
        }
    } else {
        info!(
            "[updater] [sim] systemctl {} {}",
            action, cfg.controller_service
        );
        thread::sleep(Duration::from_millis(500));
        true
    }
}

fn service_is_active(cfg: &OtaConfig, systemd_available: bool) -> bool {
    if systemd_available {
        match Command::new("systemctl")
            .arg("is-active")
            .arg(&cfg.controller_service)
            .output()
        {
            Ok(out) => String::from_utf8_lossy(&out.stdout).trim() == "active",
            Err(_) => false,
        }
    } else {
        let mut rng = rand::rng();
        rng.random::<f64>() > cfg.simulated_failure_rate
    }
}

fn health_check(cfg: &OtaConfig, systemd_available: bool) -> bool {
    info!(
        "[updater] Health-check window: {:.0}s",
        cfg.health_timeout
    );
    let deadline = Instant::now() + Duration::from_secs_f64(cfg.health_timeout);
    while Instant::now() < deadline {
        if service_is_active(cfg, systemd_available) {
            info!("[updater] Service is active ✓");
            return true;
        }
        thread::sleep(Duration::from_secs(3));
    }
    warn!("[updater] Health-check timed out");
    false
}

fn persist_version(cfg: &OtaConfig, version: &str) -> io::Result<()> {
    fs::create_dir_all(&cfg.install_base)?;
    fs::write(&cfg.current_version_file, version)?;
    Ok(())
}

fn download_to_path(download_url: &str, dest_path: &Path) -> Result<(), String> {
    let http = HttpClient::new();
    let mut resp = http
        .get(download_url)
        .send()
        .map_err(|e| format!("download failed: {e}"))?;

    if !resp.status().is_success() {
        return Err(format!("download failed: HTTP {}", resp.status()));
    }

    let mut out = File::create(dest_path).map_err(|e| e.to_string())?;
    io::copy(&mut resp, &mut out).map_err(|e| e.to_string())?;
    Ok(())
}

fn run_update_flow(
    cfg: &OtaConfig,
    mqtt: &AsyncClient,
    device_id: &str,
    command_id: &str,
    version: &str,
    download_url: &str,
    checksum_sha256: &str,
) {
    let publish_err = |err: String| {
        publish_update_status(mqtt, device_id, command_id, version, "failed", Some(&err));
    };

    let current = get_current_version(cfg);
    if current == version {
        info!("[updater] Already on v{}, nothing to do", version);
        publish_update_status(mqtt, device_id, command_id, version, "success", None);
        return;
    }

    let old_version = current;
    let systemd_available = systemctl_available();

    let tmp_file = match TempBuilder::new()
        .suffix(".zip")
        .prefix(&format!("ota-{}-", version))
        .tempfile()
    {
        Ok(f) => f,
        Err(e) => {
            publish_err(format!("failed to create temp file: {}", e));
            return;
        }
    };
    let tmp_path = tmp_file.path().to_path_buf();

    let result = (|| -> Result<(), String> {
        let _lock = UpdateLock::acquire(cfg).map_err(|e| e.to_string())?;

        // 1. Download
        publish_update_status(mqtt, device_id, command_id, version, "downloading", None);
        info!("[updater] Downloading {}", download_url);
        download_to_path(download_url, &tmp_path)?;

        // 2. Checksum
        let actual = sha256_file(&tmp_path).map_err(|e| e.to_string())?;
        if actual != checksum_sha256 {
            return Err(format!(
                "Checksum mismatch: expected {}, got {}",
                checksum_sha256, actual
            ));
        }
        info!("[updater] Checksum verified ✓");

        // 3. Extract
        publish_update_status(mqtt, device_id, command_id, version, "installing", None);
        let new_dir = extract_zip_or_marker(&tmp_path, &cfg.versions_dir, version)
            .map_err(|e| e.to_string())?;

        // 4. Atomic symlink swap
        atomic_symlink_swap(&new_dir, &cfg.app_link).map_err(|e| e.to_string())?;
        persist_version(cfg, version).map_err(|e| e.to_string())?;

        // 5. Stop service
        info!("[updater] systemctl stop {}", cfg.controller_service);
        let _ = ctl(cfg, "stop", systemd_available);

        // 6. Start service
        info!("[updater] systemctl start {}", cfg.controller_service);
        let _ = ctl(cfg, "start", systemd_available);

        // 7. Health check
        if health_check(cfg, systemd_available) {
            prune_old_versions(cfg, 3).map_err(|e| e.to_string())?;
            publish_update_status(mqtt, device_id, command_id, version, "success", None);
            info!("[updater] ✓ Updated to v{}", version);
        } else {
            // 8. Rollback
            warn!(
                "[updater] Health check failed — rolling back to {}",
                old_version
            );
            let old_dir = cfg.versions_dir.join(&old_version);
            if old_dir.exists() {
                atomic_symlink_swap(&old_dir, &cfg.app_link).map_err(|e| e.to_string())?;
            }
            persist_version(cfg, &old_version).map_err(|e| e.to_string())?;
            let _ = ctl(cfg, "stop", systemd_available);
            let _ = ctl(cfg, "start", systemd_available);
            publish_update_status(
                mqtt,
                device_id,
                command_id,
                version,
                "rolledback",
                Some(&format!(
                    "Health check failed for v{}; reverted to v{}",
                    version, old_version
                )),
            );
        }

        Ok(())
    })();

    if let Err(err) = result {
        error!("[updater] update failed: {}", err);
        publish_err(err);
    }

    // tmp_file drops here, removing temp zip.
    drop(tmp_file);
}

async fn mqtt_connect_and_listen(
    cfg: &OtaConfig,
    device_id: &str,
    mqtt_broker: &str,
    mqtt_port: u16,
) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    // Note: rumqttc's publish needs an eventloop poll running, even if we only care about outgoing messages.
    let client_id = format!("device-updater-{}", device_id);
    let mut mqttoptions = MqttOptions::new(client_id, mqtt_broker, mqtt_port);
    mqttoptions.set_keep_alive(Duration::from_secs(30));

    let (client, mut eventloop) = AsyncClient::new(mqttoptions, 10);

    let commands_topic = format!("fleet/{}/commands", device_id);
    client
        .subscribe(commands_topic.clone(), QoS::AtMostOnce)
        .await
        .map_err(|e| format!("MQTT subscribe failed: {e}"))?;

    info!("[updater] Listening on MQTT topic {}", commands_topic);

    loop {
        match eventloop.poll().await {
            Ok(Event::Incoming(Packet::Publish(p))) => {
                if p.topic == commands_topic {
                    let payload_str = String::from_utf8_lossy(&p.payload);
                    debug!("[updater] MQTT command payload: {}", payload_str);

                    let Ok(v) = serde_json::from_slice::<serde_json::Value>(&p.payload) else {
                        warn!("[updater] Invalid JSON on command payload");
                        continue;
                    };

                    let command = v
                        .get("command")
                        .and_then(|v| v.as_str())
                        .unwrap_or("");
                    if command != "update" {
                        continue;
                    }

                    let command_id = v
                        .get("command_id")
                        .and_then(|v| v.as_str())
                        .unwrap_or("")
                        .to_string();

                    let empty_payload = json!({});
                    let payload_obj = v.get("payload").unwrap_or(&empty_payload);
                    let version = payload_obj
                        .get("version")
                        .and_then(|v| v.as_str())
                        .unwrap_or("")
                        .to_string();
                    let download_url = payload_obj
                        .get("download_url")
                        .and_then(|v| v.as_str())
                        .unwrap_or("")
                        .to_string();
                    let checksum_sha256 = payload_obj
                        .get("checksum_sha256")
                        .and_then(|v| v.as_str())
                        .unwrap_or("")
                        .to_string();

                    if command_id.is_empty()
                        || version.is_empty()
                        || download_url.is_empty()
                        || checksum_sha256.is_empty()
                    {
                        warn!("[updater] Invalid update command payload (missing fields)");
                        publish_update_status(
                            &client,
                            device_id,
                            &command_id,
                            &version,
                            "failed",
                            Some("Missing version/download_url/checksum_sha256"),
                        );
                        continue;
                    }

                    info!(
                        "[updater] OTA update triggered v{} (cmd={})",
                        version, command_id
                    );

                    let mqtt = client.clone();
                    let cfg = cfg.clone();
                    let device_id = device_id.to_string();

                    tokio::task::spawn_blocking(move || {
                        run_update_flow(
                            &cfg,
                            &mqtt,
                            &device_id,
                            &command_id,
                            &version,
                            &download_url,
                            &checksum_sha256,
                        );
                    });
                }
            }
            Ok(_) => {}
            Err(e) => {
                warn!("[updater] MQTT error: {}", e);
                thread::sleep(Duration::from_secs(1));
            }
        }
    }
}

async fn mqtt_connect_and_run_once(
    cfg: &OtaConfig,
    device_id: &str,
    mqtt_broker: &str,
    mqtt_port: u16,
    command_id: &str,
    version: &str,
    download_url: &str,
    checksum_sha256: &str,
) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    let client_id = format!("device-updater-{}", device_id);
    let mut mqttoptions = MqttOptions::new(client_id, mqtt_broker, mqtt_port);
    mqttoptions.set_keep_alive(Duration::from_secs(30));

    let (client, mut eventloop) = AsyncClient::new(mqttoptions, 10);

    let mqtt = client.clone();
    tokio::spawn(async move {
        loop {
            let _ = eventloop.poll().await;
        }
    });

    tokio::task::spawn_blocking({
        let cfg = cfg.clone();
        let mqtt = mqtt.clone();
        let device_id = device_id.to_string();
        let command_id = command_id.to_string();
        let version = version.to_string();
        let download_url = download_url.to_string();
        let checksum_sha256 = checksum_sha256.to_string();
        move || {
            run_update_flow(&cfg, &mqtt, &device_id, &command_id, &version, &download_url, &checksum_sha256);
        }
    })
    .await?;

    // Give the outgoing publishes a brief moment to be flushed through the MQTT eventloop.
    tokio::time::sleep(Duration::from_millis(500)).await;
    Ok(())
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    env_logger::init();
    let cli = Cli::parse();
    let device_id = effective_device_id(&cli);
    let ota_cfg = OtaConfig::from_cli(&cli);

    match cli.command {
        Commands::Listen => {
            mqtt_connect_and_listen(&ota_cfg, &device_id, &cli.mqtt_broker, cli.mqtt_port).await?
        }
        Commands::RunOnce {
            command_id,
            version,
            download_url,
            checksum_sha256,
        } => {
            mqtt_connect_and_run_once(
                &ota_cfg,
                &device_id,
                &cli.mqtt_broker,
                cli.mqtt_port,
                &command_id,
                &version,
                &download_url,
                &checksum_sha256,
            )
            .await?;
        }
    }
    Ok(())
}
