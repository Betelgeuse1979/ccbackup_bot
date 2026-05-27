import platform
import subprocess


def ping_host(ip_address: str, count: int = 2, timeout_seconds: int = 3) -> bool:
    count_flag = "-n" if platform.system().lower() == "windows" else "-c"
    timeout_flag = "-w" if platform.system().lower() == "windows" else "-W"
    command = [
        "ping",
        count_flag,
        str(count),
        timeout_flag,
        str(timeout_seconds),
        ip_address,
    ]
    return subprocess.call(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0
