from dataclasses import dataclass


@dataclass(frozen=True)
class Device:
    name: str
    ip_address: str
    username: str = ""
    password: str = ""
    enable_password: str = ""
    connection_type: str = "telnet"


@dataclass(frozen=True)
class BackupResult:
    device: Device
    success: bool
    message: str
    backup_path: str = ""
    running_config: str = ""
