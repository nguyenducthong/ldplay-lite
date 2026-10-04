from __future__ import annotations

from pathlib import Path

from core.adb import ADBManager


def capture(adb: ADBManager, serial: str, destination: str | Path | None = None) -> Path:
    """Capture a PNG from one Android device through ADB."""
    return adb.screenshot(serial, destination)
