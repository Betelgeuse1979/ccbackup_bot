import argparse
from pathlib import Path

from ccbackup_bot.backup_runner import create_backup_folder, run_backup_job
from ccbackup_bot.db import database_enabled_from_env, store_successful_backups_and_write_report
from ccbackup_bot.devices import load_credentials, load_devices_from_excel


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Back up Cisco switch running configs.")
    parser.add_argument("--devices", required=True, help="Path to the Excel device inventory.")
    parser.add_argument("--credentials", default="credentials.json", help="Path to credentials JSON.")
    parser.add_argument("--output", default="backups", help="Folder where dated backups are saved.")
    parser.add_argument("--skip-ping", action="store_true", help="Try connecting without pinging first.")
    parser.add_argument(
        "--db-report",
        action="store_true",
        help="Store successful backups in PostgreSQL and write a database change report.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    credentials = load_credentials(args.credentials)
    devices = load_devices_from_excel(args.devices, credentials)
    if not devices:
        print("No devices found in the inventory.")
        return 1

    backup_folder = create_backup_folder(Path(args.output))
    results = run_backup_job(devices, backup_folder, check_reachable=not args.skip_ping)

    failures = 0
    for result in results:
        print(result.message)
        if result.success and result.backup_path:
            print(f"  Saved to: {result.backup_path}")
        if not result.success:
            failures += 1

    if args.db_report or database_enabled_from_env():
        report_folder = Path(args.output) / "reports"
        for message in store_successful_backups_and_write_report(results, report_folder):
            print(message)

    print(f"All done. Successful: {len(results) - failures}, Failed: {failures}")
    return 1 if failures else 0
