from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import logging
from pathlib import Path
import re
import shlex

from utils.process import CommandResult, run_binary, run_command
from utils.system import screenshots_dir


@dataclass(slots=True, frozen=True)
class ADBDevice:
    serial: str
    state: str
    details: str = ""


def parse_devices(output: str) -> list[ADBDevice]:
    devices: list[ADBDevice] = []
    for line in output.splitlines():
        line = line.strip()
        if not line or line.startswith("List of devices") or line.startswith("*"):
            continue
        parts = line.split(maxsplit=2)
        if len(parts) >= 2:
            devices.append(ADBDevice(parts[0], parts[1], parts[2] if len(parts) > 2 else ""))
    return devices


def ldplayer_index_from_serial(serial: str) -> int | None:
    """Infer an LDPlayer instance index from its usual local ADB serial."""
    emulator = re.fullmatch(r"emulator-(\d+)", serial.strip(), flags=re.IGNORECASE)
    if emulator:
        port = int(emulator.group(1))
        if port >= 5554 and (port - 5554) % 2 == 0:
            return (port - 5554) // 2

    endpoint = re.fullmatch(r"(?:127\.0\.0\.1|localhost):(\d+)", serial.strip(), flags=re.IGNORECASE)
    if endpoint:
        port = int(endpoint.group(1))
        if port >= 5555 and (port - 5555) % 2 == 0:
            return (port - 5555) // 2
    return None


class ADBManager:
    def __init__(self, adb_path: str | Path, *, timeout: int = 30):
        self.path = Path(adb_path)
        self.timeout = timeout
        self.logger = logging.getLogger("ldlite")

    def _run(self, *args: str, timeout: int | None = None) -> CommandResult:
        self.logger.info("ADB: %s", " ".join(args))
        return run_command((self.path, *args), timeout=timeout or self.timeout)

    def devices(self) -> list[ADBDevice]:
        return parse_devices(self._run("devices", "-l").stdout)

    def connect(self, endpoint: str) -> str:
        return self._run("connect", endpoint).stdout.strip()

    def disconnect(self, endpoint: str | None = None) -> str:
        args = ("disconnect", endpoint) if endpoint else ("disconnect",)
        return self._run(*args).stdout.strip()

    def shell(self, serial: str, command: str) -> str:
        clean = command.strip()
        if re.search(r"adb(?:\.exe)?\s+", clean, flags=re.IGNORECASE):
            serial_match = re.search(r"-s\s+([^\s<>]+)", clean, flags=re.IGNORECASE)
            if serial_match and (not serial or serial.startswith("<")):
                serial = serial_match.group(1)
            clean = re.sub(r"^.*?adb(?:\.exe)?\s+", "", clean, flags=re.IGNORECASE).strip()
            clean = re.sub(r"^-s\s+(?:<[^>]+>|\S+)\s*", "", clean, flags=re.IGNORECASE).strip()
        if clean.lower().startswith("adb "):
            clean = clean[4:].strip()
        if clean.lower().startswith("shell "):
            clean = clean[6:].strip()
            parts = shlex.split(clean, posix=False) if clean else []
            args = ("shell", *parts)
        elif clean.lower().startswith("logcat"):
            parts = shlex.split(clean, posix=False) if clean else []
            args = tuple(parts)
        else:
            parts = shlex.split(clean, posix=False) if clean else []
            args = ("shell", *parts)
        if not args:
            raise ValueError("Lệnh shell không được để trống.")
        return self._run("-s", serial, *args).stdout

    def install(self, serial: str, apk: str | Path) -> str:
        return self._run("-s", serial, "install", "-r", str(apk), timeout=180).stdout

    def uninstall(self, serial: str, package: str) -> str:
        return self._run("-s", serial, "uninstall", package).stdout

    def push(self, serial: str, source: str | Path, destination: str) -> str:
        return self._run("-s", serial, "push", str(source), destination, timeout=120).stdout

    def pull(self, serial: str, source: str, destination: str | Path) -> str:
        return self._run("-s", serial, "pull", source, str(destination), timeout=120).stdout

    def reboot(self, serial: str) -> None:
        self._run("-s", serial, "reboot")

    def screenshot(self, serial: str, destination: str | Path | None = None) -> Path:
        output = Path(destination) if destination else screenshots_dir() / (
            f"{serial.replace(':', '_')}_{datetime.now():%Y%m%d_%H%M%S}.png"
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        image = run_binary(
            (self.path, "-s", serial, "exec-out", "screencap", "-p"),
            timeout=self.timeout,
        )
        if not image.startswith(b"\x89PNG"):
            raise RuntimeError("ADB không trả về ảnh PNG hợp lệ.")
        output.write_bytes(image)
        self.logger.info("Đã lưu ảnh: %s", output)
        return output

    def network_diagnostics(self, serial: str) -> str:
        sections: list[str] = []
        commands = (
            ("DNS", "getprop net.dns1"),
            ("Route", "ip route"),
            ("Ping IP", "ping -c 4 -W 2 1.1.1.1"),
            ("Ping DNS", "ping -c 4 -W 2 google.com"),
        )
        for label, command in commands:
            try:
                output = self.shell(serial, command).strip() or "(không có dữ liệu)"
            except Exception as exc:
                output = f"Lỗi: {exc}"
            sections.append(f"[{label}]\n{output}")
        return "\n\n".join(sections)
