import json
import os
from pathlib import Path


SETTINGS_DIR_NAME = "ccbackup_bot"
SETTINGS_FILE_NAME = "gui_settings.json"


def settings_path() -> Path:
    base_path = os.environ.get("APPDATA") or os.environ.get("LOCALAPPDATA")
    if base_path:
        return Path(base_path) / SETTINGS_DIR_NAME / SETTINGS_FILE_NAME
    return Path.home() / ".config" / SETTINGS_DIR_NAME / SETTINGS_FILE_NAME


def load_settings() -> tuple[dict[str, str], str]:
    path = settings_path()
    if not path.exists():
        return {}, ""

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}, "Saved GUI settings could not be read, so defaults were used."

    if not isinstance(data, dict):
        return {}, "Saved GUI settings were invalid, so defaults were used."

    settings: dict[str, str] = {}
    for key in ("inventory_path", "credentials_path", "output_path"):
        value = data.get(key)
        if isinstance(value, str):
            settings[key] = value

    return settings, ""


def save_settings(inventory_path: str, credentials_path: str, output_path: str) -> None:
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "inventory_path": inventory_path,
        "credentials_path": credentials_path,
        "output_path": output_path,
    }
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def clear_settings() -> None:
    path = settings_path()
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass
