import difflib
import hashlib
from dataclasses import dataclass
from datetime import datetime

from ccbackup_bot.models import Device


def normalize_config_text(config_text: str) -> str:
    lines = config_text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    return "\n".join(line.rstrip() for line in lines).strip() + "\n"


def config_sha256(config_text: str) -> str:
    normalized = normalize_config_text(config_text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def generate_config_diff(
    old_config: str,
    new_config: str,
    old_label: str = "previous",
    new_label: str = "latest",
) -> str:
    old_lines = normalize_config_text(old_config).splitlines(keepends=True)
    new_lines = normalize_config_text(new_config).splitlines(keepends=True)
    return "".join(
        difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=old_label,
            tofile=new_label,
        )
    )


@dataclass(frozen=True)
class ConfigChangeEntry:
    device: Device
    backup_time: datetime
    changed: bool
    message: str
    diff_text: str = ""


def format_change_report(entries: list[ConfigChangeEntry], generated_at: datetime | None = None) -> str:
    generated_at = generated_at or datetime.now()
    lines = [
        "Cisco Configuration Change Report",
        f"Generated: {generated_at.strftime('%Y-%m-%d %H:%M:%S')}",
        "",
    ]

    if not entries:
        lines.append("No successful backups were available for database comparison.")
        return "\n".join(lines) + "\n"

    for entry in entries:
        lines.extend(
            [
                "=" * 80,
                f"Device: {entry.device.name} / {entry.device.ip_address}",
                f"Backup timestamp: {entry.backup_time.strftime('%Y-%m-%d %H:%M:%S')}",
                f"Config changed: {'Yes' if entry.changed else 'No'}",
                entry.message,
                "",
            ]
        )
        if entry.diff_text:
            lines.append(entry.diff_text)
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"
