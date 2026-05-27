from telnetlib import Telnet

from ccbackup_bot.models import Device


def backup_running_config(device: Device, timeout: int = 15) -> str:
    if not device.password:
        raise ValueError("Missing password")

    with Telnet(device.ip_address, 23, timeout=timeout) as tn:
        login_prompt = tn.read_until(b"Password: ", timeout=timeout)
        if b"Username:" in login_prompt and device.username:
            tn.write(device.username.encode("ascii") + b"\n")
            tn.read_until(b"Password: ", timeout=timeout)

        tn.write(device.password.encode("ascii") + b"\n")
        tn.write(b"enable\n")
        tn.write(device.enable_password.encode("ascii") + b"\n")
        tn.write(b"terminal length 0\n")
        tn.write(b"show running-config\n")
        tn.write(b"terminal length 25\n")
        tn.write(b"exit\n")

        output = tn.read_all()

    return output.decode("utf-8", errors="replace")
