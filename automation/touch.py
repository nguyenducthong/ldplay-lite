from __future__ import annotations

from core.adb import ADBManager


def tap(adb: ADBManager, serial: str, x: int, y: int) -> None:
    adb.shell(serial, f"input tap {int(x)} {int(y)}")


def swipe(
    adb: ADBManager,
    serial: str,
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    duration_ms: int = 300,
) -> None:
    adb.shell(
        serial,
        f"input swipe {int(x1)} {int(y1)} {int(x2)} {int(y2)} {int(duration_ms)}",
    )
