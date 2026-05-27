import argparse
from pathlib import Path

from ccbackup_bot.backup_runner import create_backup_folder, run_backup_job
from ccbackup_bot.db import database_enabled_from_env, store_successful_backups_and_write_report
from ccbackup_bot.devices import load_credentials, load_devices_from_excel
from ccbackup_bot.serial_console import check_restore_readiness_over_serial, identify_switch_over_serial, list_serial_ports


def load_optional_credentials(path: str) -> dict[str, str]:
    try:
        return load_credentials(path)
    except FileNotFoundError:
        return {}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Back up Cisco switch running configs.")
    parser.add_argument("--devices", help="Path to the Excel device inventory.")
    parser.add_argument("--credentials", default="credentials.json", help="Path to credentials JSON.")
    parser.add_argument("--output", default="backups", help="Folder where dated backups are saved.")
    parser.add_argument("--skip-ping", action="store_true", help="Try connecting without pinging first.")
    parser.add_argument(
        "--db-report",
        action="store_true",
        help="Store successful backups in PostgreSQL and write a database change report.",
    )
    parser.add_argument("--list-serial-ports", action="store_true", help="List available serial console ports.")
    parser.add_argument("--serial-identify", metavar="PORT", help="Identify a switch over a read-only serial console session.")
    parser.add_argument("--serial-readiness", metavar="PORT", help="Run a read-only restore readiness check over serial.")
    parser.add_argument("--serial-baudrate", type=int, default=9600, help="Serial baudrate. Default: 9600.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.list_serial_ports:
        try:
            ports = list_serial_ports()
        except Exception as exc:
            print(f"Could not list serial ports: {exc}")
            return 1
        if not ports:
            print("No serial ports found.")
            return 0
        for port in ports:
            print(f"{port.port}: {port.description}")
        return 0

    if args.serial_identify:
        credentials = load_optional_credentials(args.credentials)
        result = identify_switch_over_serial(
            args.serial_identify,
            baudrate=args.serial_baudrate,
            log_folder=Path(args.output) / "logs",
            username=str(credentials.get("username", "")),
            password=str(credentials.get("password", "")),
            enable_password=str(credentials.get("enable_password", "")),
        )
        print(f"Read-only serial identification on {result.port} at {result.baudrate} baud")
        print(f"Status: {result.status}")
        if result.error_message:
            print(f"Error: {result.error_message}")
        print(f"Prompt: {result.detected_prompt or '(not detected)'}")
        print(f"Hostname: {result.hostname or '(not detected)'}")
        print(f"Model: {result.model or '(not detected)'}")
        print(f"Serial number: {result.serial_number or '(not detected)'}")
        print(f"IOS version: {result.ios_version or '(not detected)'}")
        if result.log_path:
            print(f"Serial session log: {result.log_path}")
        return 0 if result.success else 1

    if args.serial_readiness:
        credentials = load_optional_credentials(args.credentials)
        result = check_restore_readiness_over_serial(
            args.serial_readiness,
            baudrate=args.serial_baudrate,
            output_folder=args.output,
            username=str(credentials.get("username", "")),
            password=str(credentials.get("password", "")),
            enable_password=str(credentials.get("enable_password", "")),
        )
        print(f"READ-ONLY restore readiness check on {result.port} at {result.baudrate} baud")
        print("NO CONFIGURATION CHANGES WERE MADE")
        print(f"Readiness state: {result.readiness_state}")
        if result.error_message:
            print(f"Error: {result.error_message}")
        print(f"Prompt: {result.detected_prompt or '(not detected)'}")
        print(f"Hostname: {result.hostname or '(not detected)'}")
        print(f"Model: {result.model or '(not detected)'}")
        print(f"Serial number: {result.serial_number or '(not detected)'}")
        print(f"IOS version: {result.ios_version or '(not detected)'}")
        print("Evidence found:")
        if result.evidence_found:
            for item in result.evidence_found:
                print(f"  - {item}")
        else:
            print("  - None")
        if result.warnings:
            print("Warnings:")
            for item in result.warnings:
                print(f"  - {item}")
        if result.backup_bundle_path:
            print(f"Pre-restore backup bundle / log path: {result.backup_bundle_path}")
        return 0 if result.success else 1

    if not args.devices:
        parser.error("--devices is required unless using --list-serial-ports, --serial-identify, or --serial-readiness")

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
