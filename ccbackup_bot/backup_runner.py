import re
from datetime import datetime
from pathlib import Path

from ccbackup_bot.cisco_telnet import backup_running_config
from ccbackup_bot.models import BackupResult, Device
from ccbackup_bot.network import ping_host


def safe_filename(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    return cleaned.strip("._") or "switch"


def create_backup_folder(base_folder: str | Path = "backups") -> Path:
    date_today = datetime.now().strftime("%Y-%m-%d")
    folder = Path(base_folder) / date_today
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def save_backup(device: Device, running_config: str, backup_folder: str | Path) -> Path:
    backup_path = Path(backup_folder) / f"{safe_filename(device.name)}.txt"
    backup_path.write_text(running_config, encoding="utf-8")
    return backup_path


def backup_device(device: Device, backup_folder: str | Path, check_reachable: bool = True) -> BackupResult:
    if check_reachable and not ping_host(device.ip_address):
        return BackupResult(device=device, success=False, message=f"{device.name} is not available on {device.ip_address}")

    if device.connection_type != "telnet":
        return BackupResult(device=device, success=False, message=f"{device.connection_type} is not supported yet")

    try:
        running_config = backup_running_config(device)
        backup_path = save_backup(device, running_config, backup_folder)
    except Exception as exc:
        return BackupResult(device=device, success=False, message=f"Error connecting to {device.name} ({device.ip_address}): {exc}")

    return BackupResult(
        device=device,
        success=True,
        message=f"Configuration for {device.name} saved successfully.",
        backup_path=str(backup_path),
        running_config=running_config,
    )


def run_backup_job(devices: list[Device], backup_folder: str | Path, check_reachable: bool = True) -> list[BackupResult]:
    return [backup_device(device, backup_folder, check_reachable=check_reachable) for device in devices]
