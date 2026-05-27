import json
from pathlib import Path

import pandas as pd

from ccbackup_bot.models import Device


NAME_COLUMNS = ("Switch_name", "switch_name", "name", "Name")
IP_COLUMNS = ("Ip-address", "ip_address", "ip", "IP", "IP Address")


def load_credentials(path: str | Path) -> dict[str, str]:
    credentials_path = Path(path)
    with credentials_path.open("r", encoding="utf-8") as cred_file:
        return json.load(cred_file)


def _first_matching_column(columns: list[str], candidates: tuple[str, ...]) -> str:
    for candidate in candidates:
        if candidate in columns:
            return candidate
    raise ValueError(f"Missing required column. Expected one of: {', '.join(candidates)}")


def load_devices_from_excel(
    excel_path: str | Path,
    credentials: dict[str, str] | None = None,
) -> list[Device]:
    credentials = credentials or {}
    df = pd.read_excel(excel_path, header=0)
    columns = list(df.columns)
    name_column = _first_matching_column(columns, NAME_COLUMNS)
    ip_column = _first_matching_column(columns, IP_COLUMNS)

    devices: list[Device] = []
    for _, row in df.iterrows():
        name = str(row[name_column]).strip()
        ip_address = str(row[ip_column]).strip()
        if not name or not ip_address or name.lower() == "nan" or ip_address.lower() == "nan":
            continue

        devices.append(
            Device(
                name=name,
                ip_address=ip_address,
                username=str(credentials.get("username", "")),
                password=str(credentials.get("password", "")),
                enable_password=str(credentials.get("enable_password") or credentials.get("password", "")),
                connection_type=str(credentials.get("connection_type", "telnet")).lower(),
            )
        )

    return devices
