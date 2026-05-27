import pytest

from ccbackup_bot.serial_console import (
    detect_prompt_text,
    is_blocked_command,
    parse_hostname,
    parse_ios_version,
    parse_model,
    parse_serial_number,
    run_read_only_command,
)


class FakeSerial:
    def __init__(self, output: bytes) -> None:
        self.output = bytearray(output)
        self.writes: list[bytes] = []

    @property
    def in_waiting(self) -> int:
        return len(self.output)

    def write(self, data: bytes) -> None:
        self.writes.append(data)

    def read(self, size: int = 1) -> bytes:
        if not self.output:
            return b""
        size = min(size, len(self.output))
        chunk = self.output[:size]
        del self.output[:size]
        return bytes(chunk)


def test_detect_prompt_text_detects_common_switch_prompts():
    assert detect_prompt_text("\r\nSwitch>") == "Switch>"
    assert detect_prompt_text("\r\ncore-sw-01#") == "core-sw-01#"
    assert detect_prompt_text("\r\nRouter>") == "Router>"


def test_parse_hostname_from_running_config_include_output():
    assert parse_hostname("hostname core-sw-01\r\ncore-sw-01#") == "core-sw-01"


def test_parse_model_from_show_inventory_sample():
    output = 'NAME: "1", DESCR: "WS-C2960X-24TS-L"\nPID: WS-C2960X-24TS-L , VID: V05\n'

    assert parse_model(output) == "WS-C2960X-24TS-L"


def test_parse_serial_number_from_show_inventory_sample():
    output = 'PID: WS-C2960X-24TS-L , VID: V05, SN: FOC1234A1BC\n'

    assert parse_serial_number(output) == "FOC1234A1BC"


def test_parse_ios_version_from_show_version_sample():
    output = "Cisco IOS Software, C2960X Software, Version 15.2(7)E7, RELEASE SOFTWARE (fc3)"

    assert parse_ios_version(output) == "15.2(7)E7"


def test_safety_guard_blocks_write_commands():
    assert is_blocked_command("configure terminal")
    assert is_blocked_command("write memory")
    assert is_blocked_command("copy running-config startup-config")
    assert is_blocked_command("reload")


def test_run_read_only_command_rejects_blocked_command():
    fake_serial = FakeSerial(b"")

    with pytest.raises(ValueError):
        run_read_only_command(fake_serial, "write memory")

    assert fake_serial.writes == []


def test_run_read_only_command_sends_show_command():
    fake_serial = FakeSerial(b"hostname core-sw-01\r\ncore-sw-01#")

    output = run_read_only_command(fake_serial, "show running-config | include hostname", read_seconds=0.01)

    assert fake_serial.writes == [b"show running-config | include hostname\r\n"]
    assert "hostname core-sw-01" in output
