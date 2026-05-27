import re
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol


BLOCKED_COMMAND_PATTERNS = (
    re.compile(r"^\s*conf(?:igure)?\s+(?:t|terminal)\s*$", re.IGNORECASE),
    re.compile(r"^\s*write\s+(?:memory|erase|terminal|network)\b", re.IGNORECASE),
    re.compile(r"^\s*wr\s+(?:mem|erase)\b", re.IGNORECASE),
    re.compile(r"^\s*copy\s+\S+\s+\S+", re.IGNORECASE),
    re.compile(r"^\s*reload\b", re.IGNORECASE),
    re.compile(r"^\s*erase\b", re.IGNORECASE),
    re.compile(r"^\s*delete\b", re.IGNORECASE),
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


def initial_setup_detected(output: str) -> bool:
    lowered = output.lower()
    return any(pattern in lowered for pattern in INITIAL_SETUP_PATTERNS)


def detect_prompt_text(output: str) -> str:
    match = PROMPT_RE.search(output)
    return match.group(1) if match else ""


def read_available(serial_connection: SerialLike, read_seconds: float = 2.0) -> str:
    end_time = time.monotonic() + read_seconds
    chunks: list[bytes] = []

    while time.monotonic() < end_time:
        waiting = getattr(serial_connection, "in_waiting", 0)
        if waiting:
            chunks.append(serial_connection.read(waiting))
            end_time = time.monotonic() + 0.2
        else:
            chunk = serial_connection.read(1)
            if chunk:
                chunks.append(chunk)
                end_time = time.monotonic() + 0.2
            else:
                time.sleep(0.05)

    return b"".join(chunks).decode("utf-8", errors="replace")


def detect_prompt(serial_connection: SerialLike) -> tuple[str, str]:
    serial_connection.write(b"\r\n")
    output = read_available(serial_connection)
    return detect_prompt_text(output), output


def run_read_only_command(serial_connection: SerialLike, command: str, read_seconds: float = 4.0) -> str:
    if is_blocked_command(command):
        raise ValueError(f"Blocked unsafe command in read-only serial mode: {command}")

    serial_connection.write(command.encode("ascii") + b"\r\n")
    output = read_available(serial_connection, read_seconds=read_seconds)

    while "--More--" in output or " --More-- " in output:
        serial_connection.write(b" ")
        output += read_available(serial_connection, read_seconds=read_seconds)

    return output


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


def save_serial_log(log_text: str, output_folder: str | Path = "logs") -> Path:
    folder = Path(output_folder)
    folder.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = folder / f"serial_identify_{timestamp}.txt"
    path.write_text(log_text, encoding="utf-8")
    return path


def identify_switch_over_serial(
    port: str,
    baudrate: int = 9600,
    log_folder: str | Path = "logs",
) -> SerialIdentifyResult:
    raw_parts: list[str] = []
    serial_connection = None

    try:
        serial_connection = connect_serial_console(port, baudrate=baudrate)
        prompt, initial_output = detect_prompt(serial_connection)
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
