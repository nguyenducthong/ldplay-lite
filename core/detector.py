from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


@dataclass(slots=True, frozen=True)
class LDPlayerInstallation:
    root: Path
    console: Path
    adb: Path | None
    player: Path | None


def _registry_candidates() -> list[Path]:
    try:
        import winreg
    except ImportError:
        return []

    candidates: list[Path] = []
    keys = (
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    )
    for hive, key_name in keys:
        try:
            with winreg.OpenKey(hive, key_name) as parent:
                count = winreg.QueryInfoKey(parent)[0]
                for index in range(count):
                    try:
                        with winreg.OpenKey(parent, winreg.EnumKey(parent, index)) as child:
                            name = str(winreg.QueryValueEx(child, "DisplayName")[0])
                            if "ldplayer" not in name.lower():
                                continue
                            location = str(winreg.QueryValueEx(child, "InstallLocation")[0])
                            if location:
                                candidates.append(Path(location))
                    except OSError:
                        continue
        except OSError:
            continue
    return candidates


def candidate_roots(manual_path: str | Path | None = None) -> list[Path]:
    paths: list[Path] = []
    if manual_path:
        manual = Path(manual_path).expanduser()
        paths.append(manual.parent if manual.suffix.lower() == ".exe" else manual)

    for variable in ("LDPLAYER_HOME", "PROGRAMFILES", "PROGRAMFILES(X86)"):
        value = os.environ.get(variable)
        if value:
            base = Path(value)
            if variable == "LDPLAYER_HOME":
                paths.append(base)
            else:
                paths.extend((base / "LDPlayer", base / "LDPlayer9"))

    for drive in ("C", "D", "E", "F", "G", "H", "I", "J"):
        drive_root = Path(f"{drive}:\\")
        if not drive_root.exists():
            continue
        paths.extend(
            (
                drive_root / "LDPlayer",
                drive_root / "LDPlayer9",
                drive_root / "Program Files" / "LDPlayer",
                drive_root / "Program Files" / "LDPlayer9",
                drive_root / "Program Files (x86)" / "LDPlayer",
                drive_root / "Program Files (x86)" / "LDPlayer9",
            )
        )
    paths.extend(_registry_candidates())

    unique: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        key = str(path).lower().rstrip("\\/")
        if key not in seen:
            seen.add(key)
            unique.append(path)
    return unique


def detect_ldplayer(manual_path: str | Path | None = None) -> LDPlayerInstallation | None:
    for root in candidate_roots(manual_path):
        search_roots = (root, root / "LDPlayer9", root / "LDPlayer")
        for folder in search_roots:
            console = folder / "ldconsole.exe"
            if not console.is_file():
                continue
            adb = next((path for path in (folder / "adb.exe", folder / "adb" / "adb.exe") if path.is_file()), None)
            player = next(
                (path for path in (folder / "dnplayer.exe", folder / "LDPlayer.exe") if path.is_file()),
                None,
            )
            return LDPlayerInstallation(folder.resolve(), console.resolve(), adb, player)
    return None
