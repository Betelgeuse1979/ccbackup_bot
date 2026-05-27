import pytest

from ccbackup_bot.serial_console import (
    ReadinessState,
    SerialReadinessResult,
    classify_restore_readiness,
    detect_prompt_text,
    format_readiness_report,
    is_blocked_command,
    parse_hostname,
    parse_ios_version,
    parse_model,
    parse_serial_number,
    run_read_only_command,
    save_pre_restore_backup_bundle,
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
    assert is_blocked_command("format flash:")
    assert is_blocked_command("vlan database")
    assert is_blocked_command("archive download-sw /overwrite tftp://example/image.bin")


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


def test_readiness_classifies_existing_config_evidence():
    command_outputs = {
        "show running-config": "hostname core-sw-01\nusername admin secret 9 abc\nenable secret 9 abc\nip route 0.0.0.0 0.0.0.0 192.168.1.1\n",
        "show startup-config": "hostname core-sw-01\n",
        "show vlan brief": "1 default active\n20 STAFF active\n",
        "show ip interface brief": "Vlan10 192.168.10.2 YES manual up up\n",
    }

    state, evidence, warnings = classify_restore_readiness(command_outputs, hostname="core-sw-01")

    assert state == ReadinessState.HAS_EXISTING_CONFIG.value
    assert not warnings
    assert any("Non-default hostname" in item for item in evidence)
    assert any("Local username" in item for item in evidence)
    assert any("Non-default VLAN" in item for item in evidence)


def test_readiness_classifies_initial_setup_as_likely_default():
    command_outputs = {"initial_prompt": "Would you like to enter the initial configuration dialog? [yes/no]:"}

    state, evidence, warnings = classify_restore_readiness(command_outputs)

    assert state == ReadinessState.LIKELY_FACTORY_DEFAULT.value
    assert evidence == []
    assert warnings


def test_pre_restore_backup_bundle_generation(tmp_path):
    command_outputs = {
        "show running-config": "hostname core-sw-01\n",
        "show startup-config": "hostname core-sw-01\n",
        "show version": "Cisco IOS Software, Version 15.2(7)E7\n",
        "show inventory": 'PID: WS-C2960X-24TS-L , VID: V05, SN: FOC1234A1BC\n',
        "show vlan brief": "1 default active\n",
        "show ip interface brief": "Vlan1 unassigned YES unset administratively down down\n",
    }
    result = SerialReadinessResult(
        port="COM5",
        baudrate=9600,
        readiness_state=ReadinessState.HAS_EXISTING_CONFIG.value,
        hostname="core-sw-01",
        evidence_found=("Non-default hostname detected: core-sw-01",),
        success=True,
    )

    bundle_path = save_pre_restore_backup_bundle(tmp_path, "core-sw-01", command_outputs, "session log", result)

    assert (bundle_path / "running-config.txt").read_text(encoding="utf-8") == "hostname core-sw-01\n"
    assert (bundle_path / "startup-config.txt").exists()
    assert (bundle_path / "show-version.txt").exists()
    assert (bundle_path / "show-inventory.txt").exists()
    assert (bundle_path / "vlan-brief.txt").exists()
    assert (bundle_path / "ip-interface-brief.txt").exists()
    assert (bundle_path / "serial-session.log").read_text(encoding="utf-8") == "session log"
    report = (bundle_path / "readiness-report.txt").read_text(encoding="utf-8")
    assert "NO CONFIGURATION CHANGES WERE MADE" in report
    assert "backup bundle was captured successfully" in report


def test_readiness_report_for_existing_config_states_no_restore():
    result = SerialReadinessResult(
        port="COM5",
        baudrate=9600,
        readiness_state=ReadinessState.HAS_EXISTING_CONFIG.value,
        hostname="core-sw-01",
        evidence_found=("Startup-config exists",),
        success=True,
    )

    report = format_readiness_report(result)

    assert "The switch appears already configured" in report
    assert "No restore actions were performed" in report
