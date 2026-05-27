import os
from datetime import datetime
from pathlib import Path
from typing import Any

from ccbackup_bot.config_history import (
    ConfigChangeEntry,
    config_sha256,
    format_change_report,
    generate_config_diff,
    normalize_config_text,
)
from ccbackup_bot.models import BackupResult, Device


DB_SKIP_MESSAGE = (
    "PostgreSQL storage skipped: set CCBACKUP_DATABASE_URL or CCBACKUP_PGHOST, "
    "CCBACKUP_PGDATABASE, CCBACKUP_PGUSER, and CCBACKUP_PGPASSWORD to enable it."
)


def database_enabled_from_env(env: dict[str, str] | None = None) -> bool:
    env = os.environ if env is None else env
    return env.get("CCBACKUP_ENABLE_DB", "").lower() in {"1", "true", "yes", "on"}


def database_config_from_env(env: dict[str, str] | None = None) -> str | dict[str, str] | None:
    env = os.environ if env is None else env
    database_url = env.get("CCBACKUP_DATABASE_URL")
    if database_url:
        return database_url

    required_keys = ("CCBACKUP_PGHOST", "CCBACKUP_PGDATABASE", "CCBACKUP_PGUSER", "CCBACKUP_PGPASSWORD")
    if not all(env.get(key) for key in required_keys):
        return None

    return {
        "host": env["CCBACKUP_PGHOST"],
        "dbname": env["CCBACKUP_PGDATABASE"],
        "user": env["CCBACKUP_PGUSER"],
        "password": env["CCBACKUP_PGPASSWORD"],
        "port": env.get("CCBACKUP_PGPORT", "5432"),
    }


def connect_database(config: str | dict[str, str]):
    try:
        import psycopg
    except ImportError as exc:
        raise RuntimeError("PostgreSQL driver is not installed. Install requirements.txt first.") from exc

    if isinstance(config, dict):
        return psycopg.connect(**config)
    return psycopg.connect(config)


def ensure_schema(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS devices (
                id SERIAL PRIMARY KEY,
                hostname TEXT NOT NULL,
                management_ip TEXT NOT NULL,
                vendor TEXT NOT NULL DEFAULT 'Cisco',
                model TEXT,
                site TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                UNIQUE (hostname, management_ip)
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS config_backups (
                id SERIAL PRIMARY KEY,
                device_id INTEGER NOT NULL REFERENCES devices(id),
                backup_time TIMESTAMPTZ NOT NULL,
                config_text TEXT,
                config_hash TEXT,
                backup_file_path TEXT,
                success BOOLEAN NOT NULL,
                error_message TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS config_diffs (
                id SERIAL PRIMARY KEY,
                device_id INTEGER NOT NULL REFERENCES devices(id),
                old_backup_id INTEGER REFERENCES config_backups(id),
                new_backup_id INTEGER NOT NULL REFERENCES config_backups(id),
                diff_text TEXT,
                change_summary TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
    conn.commit()


def get_or_create_device(conn, device: Device) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO devices (hostname, management_ip, vendor, updated_at)
            VALUES (%s, %s, 'Cisco', NOW())
            ON CONFLICT (hostname, management_ip)
            DO UPDATE SET updated_at = NOW()
            RETURNING id
            """,
            (device.name, device.ip_address),
        )
        row = cur.fetchone()
    return int(row[0])


def get_previous_successful_backup(conn, device_id: int) -> dict[str, Any] | None:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, config_text, config_hash
            FROM config_backups
            WHERE device_id = %s AND success = TRUE AND config_hash IS NOT NULL
            ORDER BY backup_time DESC, id DESC
            LIMIT 1
            """,
            (device_id,),
        )
        row = cur.fetchone()

    if not row:
        return None

    return {"id": row[0], "config_text": row[1] or "", "config_hash": row[2] or ""}


def insert_config_backup(
    conn,
    device_id: int,
    backup_time: datetime,
    config_text: str,
    config_hash: str,
    backup_file_path: str,
) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO config_backups (
                device_id, backup_time, config_text, config_hash,
                backup_file_path, success, error_message
            )
            VALUES (%s, %s, %s, %s, %s, TRUE, NULL)
            RETURNING id
            """,
            (device_id, backup_time, config_text, config_hash, backup_file_path),
        )
        row = cur.fetchone()
    return int(row[0])


def insert_config_diff(
    conn,
    device_id: int,
    old_backup_id: int | None,
    new_backup_id: int,
    diff_text: str,
    change_summary: str,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO config_diffs (
                device_id, old_backup_id, new_backup_id, diff_text, change_summary
            )
            VALUES (%s, %s, %s, %s, %s)
            """,
            (device_id, old_backup_id, new_backup_id, diff_text, change_summary),
        )


def create_change_entry(conn, result: BackupResult, backup_time: datetime) -> ConfigChangeEntry:
    device_id = get_or_create_device(conn, result.device)
    previous_backup = get_previous_successful_backup(conn, device_id)
    normalized_config = normalize_config_text(result.running_config)
    latest_hash = config_sha256(normalized_config)
    latest_backup_id = insert_config_backup(
        conn,
        device_id,
        backup_time,
        normalized_config,
        latest_hash,
        result.backup_path,
    )

    if previous_backup is None:
        summary = "Initial database backup - no previous config to compare"
        insert_config_diff(conn, device_id, None, latest_backup_id, "", summary)
        return ConfigChangeEntry(result.device, backup_time, False, "Initial database backup — no previous config to compare")

    if previous_backup["config_hash"] == latest_hash:
        summary = "No configuration change detected"
        insert_config_diff(conn, device_id, previous_backup["id"], latest_backup_id, "", summary)
        return ConfigChangeEntry(result.device, backup_time, False, summary)

    diff_text = generate_config_diff(
        previous_backup["config_text"],
        normalized_config,
        old_label=f"{result.device.name} previous",
        new_label=f"{result.device.name} latest",
    )
    summary = "Configuration change detected"
    insert_config_diff(conn, device_id, previous_backup["id"], latest_backup_id, diff_text, summary)
    return ConfigChangeEntry(result.device, backup_time, True, summary, diff_text)


def write_change_report(report_folder: str | Path, entries: list[ConfigChangeEntry]) -> Path:
    report_folder = Path(report_folder)
    report_folder.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = report_folder / f"config_changes_{timestamp}.txt"
    report_path.write_text(format_change_report(entries), encoding="utf-8")
    return report_path


def store_successful_backups_and_write_report(
    results: list[BackupResult],
    report_folder: str | Path,
    env: dict[str, str] | None = None,
) -> list[str]:
    config = database_config_from_env(env)
    if not config:
        return [DB_SKIP_MESSAGE]

    successful_results = [result for result in results if result.success and result.running_config]
    if not successful_results:
        return ["PostgreSQL storage skipped: no successful backups were available to store."]

    try:
        with connect_database(config) as conn:
            ensure_schema(conn)
            entries = [create_change_entry(conn, result, datetime.now()) for result in successful_results]
            conn.commit()
    except Exception as exc:
        return [f"PostgreSQL storage skipped: {exc}"]

    report_path = write_change_report(report_folder, entries)
    return [
        f"PostgreSQL storage complete for {len(successful_results)} successful backup(s).",
        f"Configuration change report saved to: {report_path}",
    ]
