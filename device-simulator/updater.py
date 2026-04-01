"""OTA updater – production-grade with simulation fallback.

Production directory layout (mirrors the real device)
------------------------------------------------------
  /root/versions/
    1.0.0/          ← extracted zip for each version
    1.2.0/
  /root/unilog      ← symlink → /root/versions/{active_version}
                       (WorkingDirectory in controller.service)

Update flow
-----------
1.  Publish status=downloading  →  HTTP GET the zip
2.  Verify SHA-256 checksum      →  abort & publish status=failed on mismatch
3.  Publish status=installing
4.  Extract zip to versions/{new}/
5.  Atomic symlink swap:  /root/unilog → versions/{new}
6.  systemctl stop controller
7.  systemctl start controller
8.  Health-check loop (systemctl is-active, timeout=HEALTH_CHECK_TIMEOUT)
    OK  → prune old versions, publish status=success
    KO  → restore symlink, restart old version, publish status=rolledback

Simulation fallback
-------------------
When systemd is not available (e.g. inside Docker) every systemctl call is
replaced by a time-delayed log message.  Set UPDATE_FAILURE_RATE (0–1) to
inject random health-check failures and exercise the rollback path.
"""

import hashlib
import json
import logging
import os
import random
import shutil
import subprocess
import tempfile
import time
import urllib.request
import zipfile
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# ── configuration (all overridable via env) ───────────────────────────────────

# Root where versioned installs live; matches WorkingDirectory parent in service
INSTALL_BASE    = os.getenv("INSTALL_BASE", "/root")
VERSIONS_DIR    = os.path.join(INSTALL_BASE, "versions")

# The symlink that always points to the active version directory.
# In production:  /root/unilog  →  /root/versions/1.2.0
APP_LINK        = os.getenv("APP_LINK", os.path.join(INSTALL_BASE, "unilog"))

SERVICE_NAME    = os.getenv("CONTROLLER_SERVICE", "controller")
HEALTH_TIMEOUT  = float(os.getenv("HEALTH_CHECK_TIMEOUT", "30"))

# State files stored alongside INSTALL_BASE
LOCK_FILE             = os.path.join(INSTALL_BASE, ".update.lock")
CURRENT_VERSION_FILE  = os.path.join(INSTALL_BASE, ".current_version")

# Simulator-only: inject random health-check failures (0 = never, 1 = always)
_SIMULATED_FAILURE_RATE = float(os.getenv("UPDATE_FAILURE_RATE", "0.1"))


# ── systemctl helpers ─────────────────────────────────────────────────────────

def _has_systemctl() -> bool:
    """Return True when systemd is reachable (not inside a plain Docker container)."""
    try:
        r = subprocess.run(
            ["systemctl", "status"],
            capture_output=True, timeout=5,
        )
        # rc 0 = running, 1 = degraded – both mean systemd is present
        return r.returncode in (0, 1)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


_SYSTEMD_AVAILABLE: Optional[bool] = None   # cached after first call


def _systemd() -> bool:
    global _SYSTEMD_AVAILABLE
    if _SYSTEMD_AVAILABLE is None:
        _SYSTEMD_AVAILABLE = _has_systemctl()
        if not _SYSTEMD_AVAILABLE:
            logger.info("[updater] systemd not available – running in simulation mode")
    return _SYSTEMD_AVAILABLE


def _ctl(action: str) -> bool:
    """Run `systemctl <action> <SERVICE_NAME>`.

    Returns True on success.  Falls back to a time-delayed simulation when
    systemd is not present.
    """
    if _systemd():
        try:
            r = subprocess.run(
                ["systemctl", action, SERVICE_NAME],
                capture_output=True, text=True, timeout=30,
            )
            if r.returncode != 0:
                logger.warning(
                    f"[updater] systemctl {action} {SERVICE_NAME} failed "
                    f"(rc={r.returncode}): {r.stderr.strip()}"
                )
            return r.returncode == 0
        except subprocess.TimeoutExpired:
            logger.error(f"[updater] systemctl {action} timed out")
            return False
    else:
        logger.info(f"[updater] [sim] systemctl {action} {SERVICE_NAME}")
        time.sleep(0.5)
        return True


def _service_is_active() -> bool:
    """Return True if the service reports 'active'."""
    if _systemd():
        try:
            r = subprocess.run(
                ["systemctl", "is-active", SERVICE_NAME],
                capture_output=True, text=True, timeout=10,
            )
            return r.stdout.strip() == "active"
        except subprocess.TimeoutExpired:
            return False
    else:
        # Simulate: pass or fail based on the configured failure rate
        return random.random() > _SIMULATED_FAILURE_RATE


# ── version tracking ──────────────────────────────────────────────────────────

def get_current_version() -> str:
    if os.path.exists(CURRENT_VERSION_FILE):
        with open(CURRENT_VERSION_FILE) as f:
            v = f.read().strip()
            if v:
                return v
    return os.getenv("DEVICE_VERSION", "0.0.0")


def _persist_version(version: str) -> None:
    os.makedirs(INSTALL_BASE, exist_ok=True)
    with open(CURRENT_VERSION_FILE, "w") as f:
        f.write(version)


# ── update lock (prevents concurrent updates) ─────────────────────────────────

class _UpdateLock:
    def __enter__(self):
        os.makedirs(INSTALL_BASE, exist_ok=True)
        if os.path.exists(LOCK_FILE):
            raise RuntimeError("Another update is already in progress")
        with open(LOCK_FILE, "w") as f:
            f.write(str(os.getpid()))
        return self

    def __exit__(self, *_):
        try:
            os.remove(LOCK_FILE)
        except FileNotFoundError:
            pass


# ── checksum ──────────────────────────────────────────────────────────────────

def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# ── install / symlink helpers ─────────────────────────────────────────────────

def _extract(zip_path: str, version: str) -> str:
    """Extract zip into versions/{version}/.  Returns the destination path."""
    dest = os.path.join(VERSIONS_DIR, version)
    if os.path.exists(dest):
        shutil.rmtree(dest)
    os.makedirs(dest, exist_ok=True)

    if zipfile.is_zipfile(zip_path):
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(dest)
        logger.info(f"[updater] Extracted zip → {dest}")
    else:
        # Simulator: zip is not a real application package; create a version marker
        logger.info(f"[updater] [sim] Not a valid zip – creating version marker at {dest}")
        with open(os.path.join(dest, "version.txt"), "w") as f:
            f.write(version)

    return dest


def _atomic_symlink(target_dir: str) -> None:
    """Atomically point APP_LINK at target_dir using a rename trick."""
    tmp = APP_LINK + ".tmp"
    if os.path.lexists(tmp):
        os.remove(tmp)
    os.symlink(target_dir, tmp)
    os.replace(tmp, APP_LINK)   # POSIX rename is atomic
    logger.info(f"[updater] {APP_LINK} → {target_dir}")


def _prune(keep: int = 3) -> None:
    """Delete oldest version directories, keeping the N most recent."""
    if not os.path.isdir(VERSIONS_DIR):
        return
    dirs = sorted(os.listdir(VERSIONS_DIR))
    for old in dirs[:-keep]:
        shutil.rmtree(os.path.join(VERSIONS_DIR, old), ignore_errors=True)
        logger.info(f"[updater] Pruned {old}")


# ── health check ──────────────────────────────────────────────────────────────

def _health_check(timeout: float = HEALTH_TIMEOUT) -> bool:
    """Poll systemctl is-active until the service reports healthy or timeout."""
    logger.info(f"[updater] Health-check window: {timeout:.0f}s")
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _service_is_active():
            logger.info("[updater] Service is active ✓")
            return True
        time.sleep(3)
    logger.warning("[updater] Health-check timed out")
    return False


# ── main entry point ──────────────────────────────────────────────────────────

def run_update(
    mqtt_client,
    device_id: str,
    command_id: str,
    version: str,
    download_url: str,
    checksum_sha256: str,
) -> None:
    """Execute the full OTA update flow in a background thread."""

    def _pub(status: str, error: Optional[str] = None) -> None:
        payload = {
            "device_id": device_id,
            "command_id": command_id,
            "version": version,
            "status": status,
            "error": error,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        mqtt_client.publish(f"fleet/{device_id}/update/status", json.dumps(payload))
        if status in ("success", "failed", "rolledback"):
            mqtt_client.publish(
                f"fleet/{device_id}/commands/response",
                json.dumps({
                    "device_id": device_id,
                    "command_id": command_id,
                    "status": "executed" if status == "success" else "failed",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "response": {"update_status": status, "version": version},
                }),
            )
        logger.info(f"[updater] → status={status}")

    # Skip if already on this version
    if get_current_version() == version:
        logger.info(f"[updater] Already on v{version}, nothing to do")
        _pub("success")
        return

    old_version = get_current_version()
    tmp_path: Optional[str] = None

    try:
        with _UpdateLock():

            # ── 1. Download ──────────────────────────────────────────────
            _pub("downloading")
            fd, tmp_path = tempfile.mkstemp(suffix=".zip", prefix=f"ota-{version}-")
            os.close(fd)
            logger.info(f"[updater] Downloading {download_url}")
            urllib.request.urlretrieve(download_url, tmp_path)

            # ── 2. Checksum ──────────────────────────────────────────────
            actual = _sha256(tmp_path)
            if actual != checksum_sha256:
                raise ValueError(
                    f"Checksum mismatch: expected {checksum_sha256}, got {actual}"
                )
            logger.info("[updater] Checksum verified ✓")

            # ── 3. Extract ───────────────────────────────────────────────
            _pub("installing")
            new_dir = _extract(tmp_path, version)

            # ── 4. Atomic symlink swap ───────────────────────────────────
            _atomic_symlink(new_dir)
            _persist_version(version)

            # ── 5. Stop service ──────────────────────────────────────────
            logger.info(f"[updater] systemctl stop {SERVICE_NAME}")
            _ctl("stop")

            # ── 6. Start service ─────────────────────────────────────────
            logger.info(f"[updater] systemctl start {SERVICE_NAME}")
            _ctl("start")

            # ── 7. Health check ──────────────────────────────────────────
            if _health_check():
                _prune(keep=3)
                _pub("success")
                logger.info(f"[updater] ✓ Updated to v{version}")
            else:
                # ── 8. Rollback ──────────────────────────────────────────
                logger.warning(f"[updater] Health check failed — rolling back to {old_version}")
                old_dir = os.path.join(VERSIONS_DIR, old_version)
                if os.path.exists(old_dir):
                    _atomic_symlink(old_dir)
                _persist_version(old_version)
                _ctl("stop")
                _ctl("start")
                _pub(
                    "rolledback",
                    error=f"Health check failed for v{version}; reverted to v{old_version}",
                )

    except RuntimeError as exc:
        logger.error(f"[updater] Lock error: {exc}")
        _pub("failed", error=str(exc))
    except ValueError as exc:
        logger.error(f"[updater] Validation error: {exc}")
        _pub("failed", error=str(exc))
    except Exception as exc:
        logger.exception(f"[updater] Unexpected error: {exc}")
        _pub("failed", error=str(exc))
    finally:
        if tmp_path:
            try:
                os.remove(tmp_path)
            except FileNotFoundError:
                pass
