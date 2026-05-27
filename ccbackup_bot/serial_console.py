import re
import time
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Protocol


ALLOWED_READ_ONLY_COMMANDS = {
    "terminal length 0",
    "show version",
    "show inventory",
    "show running-config",
    "show startup-config",
    "show vlan brief",
    "show ip interface brief",
    "show running-config | include hostname",
    "show running-config | include username",
    "show running-config | include enable secret",
    "show running-config | include aaa",
    "show running-config | include interface",
    "show running-config | include router",
    "show running-config | include ip route",
}

BLOCKED_COMMAND_PATTERNS = (
    re.compile(r"^\s*conf(?:igure)?\s+(?:t|terminal)\s*$", re.IGNORECASE),
    re.compile(r"^\s*write\s+(?:memory|erase|terminal|network)\b", re.IGNORECASE),
    re.compile(r"^\s*wr\s+(?:mem|erase)\b", re.IGNORECASE),
    re.compile(r"^\s*copy\s+\S+\s+\S+", re.IGNORECASE),
    re.compile(r"^\s*reload\b", re.IGNORECASE),
    re.compile(r"^\s*erase\b", re.IGNORECASE),
    re.compile(r"^\s*delete\b", re.IGNORECASE),
    re.compile(r"^\s*format\b", re.IGNORECASE),
    re.compile(r"^\s*vlan\s+database\b", re.IGNORECASE),
    re.compile(r"^\s*archive\s+download-sw\b", re.IGNORECASE),
)

INITIAL_SETUP_PATTERNS = (
    "would you like to enter the initial configuration dialog",
    "initial configuration dialog",
    "system configuration dialog",
)

PROMPT_RE = re.compile(r"(?m)([A-Za-z0-9_.:/()-]+[>#])\s*$")
HOSTNAME_RE = re.compile(r"(?im)^\s*hostname\s+([A-Za-z0-9_.-]+)\s*$")
MODEL_RE = re.compile(r"(?im)^\s*(?:PID|Model number)\s*[:=]?\s*([A-Za-z0-9_.-]+)")
SERIAL_RE = re.compile(r"(?im)(?:\bSN|System serial number)\s*[:=]\s*([A-Za-z0-9_.-]+)")
IOS_RE = re.compile(r"(?im)Cisco IOS (?:XE )?Software.*?Version\s+([^,\s]+)")
ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
MORE_RE = re.compile(r"--More--| --More-- |\x08+")


class ReadinessState(StrEnum):
    LIKELY_FACTORY_DEFAULT = "LIKELY_FACTORY_DEFAULT"
    HAS_EXISTING_CONFIG = "HAS_EXISTING_CONFIG"
    UNKNOWN_NEEDS_MANUAL_REVIEW = "UNKNOWN_NEEDS_MANUAL_REVIEW"


class SerialLike(Protocol):
    def write(self, data: bytes) -> object:
        ...

    def read(self, size: int = 1) -> bytes:
        ...

    @property
    def in_waiting(self) -> int:
        ...

    def close(self) -> object:
        ...


@dataclass(frozen=True)
class SerialPortInfo:
    port: str
    description: str


@dataclass(frozen=True)
class SerialIdentifyResult:
    port: str
    baudrate: int
    detected_prompt: str = ""
    hostname: str = ""
    model: str = ""
    serial_number: str = ""
    ios_version: str = ""
    raw_output: str = ""
    success: bool = False
    status: str = ""
    error_message: str = ""
    log_path: str = ""


@dataclass(frozen=True)
class SerialReadinessResult:
    port: str
    baudrate: int
    readiness_state: str
    detected_prompt: str = ""
    hostname: str = ""
    model: str = ""
    serial_number: str = ""
    ios_version: str = ""
    evidence_found: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    command_outputs: dict[str, str] | None = None
    raw_output: str = ""
    success: bool = False
    error_message: str = ""
    backup_bundle_path: str = ""


def list_serial_ports() -> list[SerialPortInfo]:
    from serial.tools import list_ports

    return [
        SerialPortInfo(port=port.device, description=port.description or "")
        for port in list_ports.comports()
    ]


def connect_serial_console(port: str, baudrate: int = 9600, timeout: int = 2):
    import serial

    return serial.Serial(
        port=port,
        baudrate=baudrate,
        bytesize=serial.EIGHTBITS,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        timeout=timeout,
        xonxoff=False,
        rtscts=False,
        dsrdtr=False,
    )


def is_blocked_command(command: str) -> bool:
    return any(pattern.search(command) for pattern in BLOCKED_COMMAND_PATTERNS)


def is_allowed_read_only_command(command: str) -> bool:
    return command.strip().lower() in ALLOWED_READ_ONLY_COMMANDS


def initial_setup_detected(output: str) -> bool:
    lowered = output.lower()
    return any(pattern in lowered for pattern in INITIAL_SETUP_PATTERNS)


def username_prompt_detected(output: str) -> bool:
    return "username:" in output.lower()


def password_prompt_detected(output: str) -> bool:
    return "password:" in output.lower()


def detect_prompt_text(output: str) -> str:
    match = PROMPT_RE.search(strip_ansi(output).strip())
    return match.group(1) if match else ""


def strip_ansi(output: str) -> str:
    return ANSI_RE.sub("", output)


def read_available(serial_connection: SerialLike, read_seconds: float = 2.0, quiet_seconds: float = 0.25) -> str:
    end_time = time.monotonic() + read_seconds
    quiet_deadline = time.monotonic() + quiet_seconds
    chunks: list[bytes] = []

    while time.monotonic() < end_time:
        waiting = getattr(serial_connection, "in_waiting", 0)
        if waiting:
            chunks.append(serial_connection.read(waiting))
            quiet_deadline = time.monotonic() + quiet_seconds
        else:
            chunk = serial_connection.read(1)
            if chunk:
                chunks.append(chunk)
                quiet_deadline = time.monotonic() + quiet_seconds
            else:
                if chunks and time.monotonic() >= quiet_deadline:
                    break
                time.sleep(0.05)

    return b"".join(chunks).decode("utf-8", errors="replace")


def detect_prompt(serial_connection: SerialLike) -> tuple[str, str]:
    output = ""
    for _ in range(3):
        serial_connection.write(b"\r\n")
        output += read_available(serial_connection, read_seconds=2.0)
        if detect_prompt_text(output) or username_prompt_detected(output) or password_prompt_detected(output) or initial_setup_detected(output):
            break
    return detect_prompt_text(output), output


def prepare_serial_session(
    serial_connection: SerialLike,
    username: str = "",
    password: str = "",
    enable_password: str = "",
) -> tuple[str, str, list[str]]:
    warnings: list[str] = []
    prompt, output = detect_prompt(serial_connection)

    if initial_setup_detected(output) or prompt:
        return prompt, output, warnings

    for _ in range(3):
        if username_prompt_detected(output):
            if not username:
                warnings.append("Username prompt detected but no username was provided")
                return prompt, output, warnings
            serial_connection.write(username.encode("ascii") + b"\r\n")
            output += read_available(serial_connection, read_seconds=3.0)

        if password_prompt_detected(output):
            login_password = password or enable_password
            if not login_password:
                warnings.append("Password prompt detected but no password was provided")
                return prompt, output, warnings
            serial_connection.write(login_password.encode("ascii") + b"\r\n")
            output += read_available(serial_connection, read_seconds=5.0)

        prompt = detect_prompt_text(output)
        if prompt:
            return prompt, output, warnings

        serial_connection.write(b"\r\n")
        output += read_available(serial_connection, read_seconds=3.0)

    warnings.append("Could not reach an exec prompt after console login attempts")
    return prompt, output, warnings


def enter_enable_mode_if_needed(
    serial_connection: SerialLike,
    prompt: str,
    password: str = "",
    enable_password: str = "",
) -> tuple[str, str, list[str]]:
    warnings: list[str] = []
    output = ""

    if not prompt.endswith(">"):
        return prompt, output, warnings

    secret = enable_password or password
    if not secret:
        warnings.append("User exec prompt detected but no enable password was provided")
        return prompt, output, warnings

    serial_connection.write(b"enable\r\n")
    output += read_available(serial_connection, read_seconds=3.0)
    if password_prompt_detected(output):
        serial_connection.write(secret.encode("ascii") + b"\r\n")
        output += read_available(serial_connection, read_seconds=5.0)

    new_prompt = detect_prompt_text(output)
    if new_prompt.endswith("#"):
        return new_prompt, output, warnings

    warnings.append("Enable mode was not reached; privileged show commands may be unavailable")
    return new_prompt or prompt, output, warnings


def run_read_only_command(serial_connection: SerialLike, command: str, read_seconds: float = 10.0) -> str:
    if is_blocked_command(command):
        raise ValueError(f"Blocked unsafe command in read-only serial mode: {command}")
    if not is_allowed_read_only_command(command):
        raise ValueError(f"Command is not in the read-only allowlist: {command}")

    serial_connection.write(command.encode("ascii") + b"\r\n")
    output = read_available(serial_connection, read_seconds=read_seconds)

    while MORE_RE.search(output):
        serial_connection.write(b" ")
        output += read_available(serial_connection, read_seconds=read_seconds)

    return strip_ansi(output)


def parse_hostname(output: str) -> str:
    match = HOSTNAME_RE.search(output)
    if match:
        return match.group(1)

    prompt = detect_prompt_text(output)
    if prompt:
        return prompt[:-1]

    return ""


def parse_model(output: str) -> str:
    match = MODEL_RE.search(output)
    if match:
        return match.group(1)

    version_match = re.search(r"(?im)^cisco\s+([A-Za-z0-9_.-]+)\s+\(", output)
    return version_match.group(1) if version_match else ""


def parse_serial_number(output: str) -> str:
    match = SERIAL_RE.search(output)
    return match.group(1) if match else ""


def parse_ios_version(output: str) -> str:
    match = IOS_RE.search(output)
    return match.group(1) if match else ""


def detect_existing_config_evidence(command_outputs: dict[str, str], hostname: str = "") -> list[str]:
    evidence: list[str] = []
    running_config = command_outputs.get("show running-config", "")
    startup_config = command_outputs.get("show startup-config", "")
    vlan_brief = command_outputs.get("show vlan brief", "")
    ip_interface = command_outputs.get("show ip interface brief", "")
    combined = "\n".join(command_outputs.values())

    if hostname and hostname.lower() not in {"switch", "router"}:
        evidence.append(f"Non-default hostname detected: {hostname}")
    if re.search(r"(?im)^\s*username\s+\S+", running_config):
        evidence.append("Local username configuration detected")
    if re.search(r"(?im)^\s*enable\s+secret\b", running_config):
        evidence.append("Enable secret detected")
    if re.search(r"(?im)^\s*aaa\s+", running_config):
        evidence.append("AAA configuration detected")
    if re.search(r"(?im)^\s*description\s+\S+", running_config):
        evidence.append("Interface descriptions detected")
    if re.search(r"(?im)^\s*ip\s+route\s+", running_config):
        evidence.append("Static routes detected")
    if re.search(r"(?im)^\s*router\s+\S+", running_config):
        evidence.append("Routing protocol configuration detected")
    if re.search(r"(?im)^\s*ip\s+address\s+(?!dhcp\b)\S+", running_config):
        evidence.append("Configured IP interface detected in running-config")

    for line in vlan_brief.splitlines():
        match = re.match(r"^\s*(\d+)\s+\S+", line)
        if match and int(match.group(1)) not in {1, 1002, 1003, 1004, 1005}:
            evidence.append(f"Non-default VLAN detected: VLAN {match.group(1)}")
            break

    for line in ip_interface.splitlines():
        if re.search(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", line) and "unassigned" not in line.lower():
            evidence.append("Configured IP interface detected in show ip interface brief")
            break

    startup_missing = any(
        phrase in startup_config.lower()
        for phrase in (
            "startup-config is not present",
            "non-volatile configuration memory is not present",
            "nvram:startup-config is not present",
        )
    )
    if startup_config.strip() and not startup_missing and "show startup-config" not in startup_config.strip().lower():
        evidence.append("Startup-config exists")

    config_lines = [line for line in running_config.splitlines() if line.strip() and not line.strip().startswith("!")]
    if len(config_lines) > 80 or len(running_config) > 4000:
        evidence.append("Non-trivial running-config size detected")

    if "Building configuration" in combined and "% Invalid input" not in combined:
        pass

    return evidence


def classify_restore_readiness(command_outputs: dict[str, str], hostname: str = "") -> tuple[str, list[str], list[str]]:
    warnings: list[str] = []
    combined = "\n".join(command_outputs.values())

    if initial_setup_detected(combined):
        warnings.append("Initial setup dialog detected; no answer was sent")
        return ReadinessState.LIKELY_FACTORY_DEFAULT.value, [], warnings

    evidence = detect_existing_config_evidence(command_outputs, hostname=hostname)
    if evidence:
        return ReadinessState.HAS_EXISTING_CONFIG.value, evidence, warnings

    running_config = command_outputs.get("show running-config", "")
    if running_config.strip() and not re.search(r"(?i)% ?invalid|authorization failed|denied", running_config):
        return ReadinessState.LIKELY_FACTORY_DEFAULT.value, evidence, warnings

    warnings.append("Could not collect enough configuration output for a confident classification")
    return ReadinessState.UNKNOWN_NEEDS_MANUAL_REVIEW.value, evidence, warnings


def save_serial_log(log_text: str, output_folder: str | Path = "logs") -> Path:
    folder = Path(output_folder)
    folder.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = folder / f"serial_identify_{timestamp}.txt"
    path.write_text(log_text, encoding="utf-8")
    return path


def _safe_folder_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    return cleaned.strip("._") or "switch"


def format_readiness_report(result: SerialReadinessResult) -> str:
    lines = [
        "Serial Restore Readiness Report",
        "READ-ONLY MODE - NO CONFIGURATION CHANGES WERE MADE",
        "",
        f"Port: {result.port}",
        f"Baudrate: {result.baudrate}",
        f"Readiness state: {result.readiness_state}",
        f"Prompt: {result.detected_prompt or '(not detected)'}",
        f"Hostname: {result.hostname or '(not detected)'}",
        f"Model: {result.model or '(not detected)'}",
        f"Serial number: {result.serial_number or '(not detected)'}",
        f"IOS version: {result.ios_version or '(not detected)'}",
        "",
    ]

    if result.readiness_state == ReadinessState.HAS_EXISTING_CONFIG.value:
        lines.extend(
            [
                "The switch appears already configured.",
                "A pre-restore safety backup bundle was captured successfully.",
                "No restore actions were performed.",
                "",
            ]
        )

    lines.append("Evidence found:")
    if result.evidence_found:
        lines.extend(f"- {item}" for item in result.evidence_found)
    else:
        lines.append("- None")

    lines.append("")
    lines.append("Warnings:")
    if result.warnings:
        lines.extend(f"- {item}" for item in result.warnings)
    else:
        lines.append("- None")

    if result.error_message:
        lines.extend(["", f"Error: {result.error_message}"])

    return "\n".join(lines).rstrip() + "\n"


def save_pre_restore_backup_bundle(
    output_folder: str | Path,
    hostname: str,
    command_outputs: dict[str, str],
    serial_log: str,
    result: SerialReadinessResult,
) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    bundle_folder = Path(output_folder) / "pre_restore_backups" / f"{timestamp}_{_safe_folder_name(hostname)}"
    bundle_folder.mkdir(parents=True, exist_ok=True)

    files = {
        "running-config.txt": command_outputs.get("show running-config", ""),
        "startup-config.txt": command_outputs.get("show startup-config", ""),
        "show-version.txt": command_outputs.get("show version", ""),
        "show-inventory.txt": command_outputs.get("show inventory", ""),
        "vlan-brief.txt": command_outputs.get("show vlan brief", ""),
        "ip-interface-brief.txt": command_outputs.get("show ip interface brief", ""),
        "serial-session.log": serial_log,
        "readiness-report.txt": format_readiness_report(result),
    }
    for filename, content in files.items():
        (bundle_folder / filename).write_text(content, encoding="utf-8")

    return bundle_folder


def identify_switch_over_serial(
    port: str,
    baudrate: int = 9600,
    log_folder: str | Path = "logs",
    username: str = "",
    password: str = "",
    enable_password: str = "",
) -> SerialIdentifyResult:
    raw_parts: list[str] = []
    serial_connection = None

    try:
        serial_connection = connect_serial_console(port, baudrate=baudrate)
        prompt, initial_output, login_warnings = prepare_serial_session(
            serial_connection,
            username=username,
            password=password,
            enable_password=enable_password,
        )
        raw_parts.append(initial_output)

        if initial_setup_detected(initial_output):
            raw_output = "".join(raw_parts)
            log_path = save_serial_log(raw_output, log_folder)
            return SerialIdentifyResult(
                port=port,
                baudrate=baudrate,
                detected_prompt=prompt,
                raw_output=raw_output,
                success=False,
                status="Initial setup prompt detected; no answer was sent.",
                log_path=str(log_path),
            )
        if login_warnings:
            raw_parts.extend(f"\n# Warning: {warning}\n" for warning in login_warnings)
        if not prompt and login_warnings:
            raw_output = "".join(raw_parts)
            log_path = save_serial_log(raw_output, log_folder)
            return SerialIdentifyResult(
                port=port,
                baudrate=baudrate,
                raw_output=raw_output,
                success=False,
                status="Console login did not reach a switch prompt.",
                error_message="; ".join(login_warnings),
                log_path=str(log_path),
            )
        prompt, enable_output, enable_warnings = enter_enable_mode_if_needed(
            serial_connection,
            prompt,
            password=password,
            enable_password=enable_password,
        )
        if enable_output:
            raw_parts.append("\n# enable\n")
            raw_parts.append(enable_output)
        raw_parts.extend(f"\n# Warning: {warning}\n" for warning in enable_warnings)

        for command in ("terminal length 0", "show version", "show inventory", "show running-config | include hostname"):
            raw_parts.append(f"\n# {command}\n")
            raw_parts.append(run_read_only_command(serial_connection, command))

        raw_output = "".join(raw_parts)
        log_path = save_serial_log(raw_output, log_folder)
        return SerialIdentifyResult(
            port=port,
            baudrate=baudrate,
            detected_prompt=prompt or detect_prompt_text(raw_output),
            hostname=parse_hostname(raw_output),
            model=parse_model(raw_output),
            serial_number=parse_serial_number(raw_output),
            ios_version=parse_ios_version(raw_output),
            raw_output=raw_output,
            success=True,
            status="Read-only serial identification complete.",
            log_path=str(log_path),
        )
    except Exception as exc:
        raw_output = "".join(raw_parts)
        log_path = ""
        if raw_output:
            log_path = str(save_serial_log(raw_output, log_folder))
        return SerialIdentifyResult(
            port=port,
            baudrate=baudrate,
            raw_output=raw_output,
            success=False,
            status="Read-only serial identification failed.",
            error_message=str(exc),
            log_path=log_path,
        )
    finally:
        if serial_connection is not None:
            serial_connection.close()


def check_restore_readiness_over_serial(
    port: str,
    baudrate: int = 9600,
    output_folder: str | Path = "backups",
    username: str = "",
    password: str = "",
    enable_password: str = "",
) -> SerialReadinessResult:
    raw_parts: list[str] = []
    command_outputs: dict[str, str] = {}
    serial_connection = None

    try:
        serial_connection = connect_serial_console(port, baudrate=baudrate)
        prompt, initial_output, login_warnings = prepare_serial_session(
            serial_connection,
            username=username,
            password=password,
            enable_password=enable_password,
        )
        raw_parts.append(initial_output)

        if initial_setup_detected(initial_output):
            command_outputs["initial_prompt"] = initial_output
            result = SerialReadinessResult(
                port=port,
                baudrate=baudrate,
                readiness_state=ReadinessState.LIKELY_FACTORY_DEFAULT.value,
                detected_prompt=prompt,
                warnings=("Initial setup dialog detected; no answer was sent",),
                command_outputs=command_outputs,
                raw_output=initial_output,
                success=True,
            )
            save_serial_log(initial_output, Path(output_folder) / "logs")
            return result
        raw_parts.extend(f"\n# Warning: {warning}\n" for warning in login_warnings)
        if not prompt and login_warnings:
            raw_output = "".join(raw_parts)
            log_path = save_serial_log(raw_output, Path(output_folder) / "logs")
            return SerialReadinessResult(
                port=port,
                baudrate=baudrate,
                readiness_state=ReadinessState.UNKNOWN_NEEDS_MANUAL_REVIEW.value,
                warnings=tuple(login_warnings),
                command_outputs={"console_login": initial_output},
                raw_output=raw_output,
                success=False,
                error_message="Console login did not reach a switch prompt.",
                backup_bundle_path=str(log_path),
            )
        prompt, enable_output, enable_warnings = enter_enable_mode_if_needed(
            serial_connection,
            prompt,
            password=password,
            enable_password=enable_password,
        )
        if enable_output:
            raw_parts.append("\n# enable\n")
            raw_parts.append(enable_output)
        raw_parts.extend(f"\n# Warning: {warning}\n" for warning in enable_warnings)

        commands = (
            ("terminal length 0", 8.0),
            ("show version", 20.0),
            ("show inventory", 20.0),
            ("show running-config | include hostname", 10.0),
            ("show running-config | include username", 10.0),
            ("show running-config | include enable secret", 10.0),
            ("show running-config | include aaa", 10.0),
            ("show running-config | include interface", 15.0),
            ("show running-config | include router", 10.0),
            ("show running-config | include ip route", 10.0),
            ("show vlan brief", 20.0),
            ("show ip interface brief", 20.0),
            ("show startup-config", 60.0),
            ("show running-config", 90.0),
        )

        for command, read_seconds in commands:
            raw_parts.append(f"\n# {command}\n")
            output = run_read_only_command(serial_connection, command, read_seconds=read_seconds)
            command_outputs[command] = output
            raw_parts.append(output)

        raw_output = "".join(raw_parts)
        hostname = parse_hostname(
            command_outputs.get("show running-config | include hostname", "")
            or command_outputs.get("show running-config", "")
            or raw_output
        )
        readiness_state, evidence, warnings = classify_restore_readiness(command_outputs, hostname=hostname)
        warnings = login_warnings + enable_warnings + warnings
        result = SerialReadinessResult(
            port=port,
            baudrate=baudrate,
            readiness_state=readiness_state,
            detected_prompt=prompt or detect_prompt_text(raw_output),
            hostname=hostname,
            model=parse_model(raw_output),
            serial_number=parse_serial_number(raw_output),
            ios_version=parse_ios_version(raw_output),
            evidence_found=tuple(evidence),
            warnings=tuple(warnings),
            command_outputs=command_outputs,
            raw_output=raw_output,
            success=True,
        )

        if readiness_state == ReadinessState.HAS_EXISTING_CONFIG.value:
            bundle_path = save_pre_restore_backup_bundle(
                output_folder,
                hostname or parse_model(raw_output) or "switch",
                command_outputs,
                raw_output,
                result,
            )
            result = SerialReadinessResult(
                port=result.port,
                baudrate=result.baudrate,
                readiness_state=result.readiness_state,
                detected_prompt=result.detected_prompt,
                hostname=result.hostname,
                model=result.model,
                serial_number=result.serial_number,
                ios_version=result.ios_version,
                evidence_found=result.evidence_found,
                warnings=result.warnings,
                command_outputs=result.command_outputs,
                raw_output=result.raw_output,
                success=result.success,
                backup_bundle_path=str(bundle_path),
            )
        else:
            save_serial_log(raw_output, Path(output_folder) / "logs")

        return result
    except Exception as exc:
        raw_output = "".join(raw_parts)
        log_path = ""
        if raw_output:
            log_path = str(save_serial_log(raw_output, Path(output_folder) / "logs"))
        return SerialReadinessResult(
            port=port,
            baudrate=baudrate,
            readiness_state=ReadinessState.UNKNOWN_NEEDS_MANUAL_REVIEW.value,
            command_outputs=command_outputs,
            raw_output=raw_output,
            success=False,
            error_message=str(exc),
            backup_bundle_path=log_path,
        )
    finally:
        if serial_connection is not None:
            serial_connection.close()
