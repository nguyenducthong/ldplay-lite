from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
import re

from core.adb import ADBManager
from utils.system import backup_dir


PACKAGE_PATTERN = re.compile(r"^[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)+$")

PROTECTED_EXACT = {
    "android",
    "com.android.systemui",
    "com.android.settings",
    "com.android.packageinstaller",
    "com.android.permissioncontroller",
    "com.android.shell",
    "com.google.android.gms",
    "com.google.android.gsf",
    "com.google.android.webview",
    "com.android.webview",
    "com.android.vending",
    "com.android.providers.settings",
    "com.android.providers.downloads",
    "com.android.providers.media",
    "com.android.documentsui",
    "com.android.externalstorage",
    "com.android.captiveportallogin",
    "com.android.coreservice",
    "com.ldmnq.launcher3",
}
PROTECTED_PREFIXES = (
    "com.android.internal.",
)
REVIEW_TOKENS = (
    ".ads",
    "advert",
    "analytics",
    "appstore",
    "gamecenter",
    "recommend",
    "promotion",
    "feedback",
    "browser",
    "livewallpaper",
)

SAFE_OPTIONAL_PACKAGES = {
    "com.google.ar.core",
    "com.google.android.safetycore",
    "com.android.ld.appstore",
    "com.android.soundrecorder",
    "com.android.printspooler",
    "com.google.android.feedback",
    "com.android.dreams.phototable",
    "com.android.wallpaper.livepicker",
    "com.android.traceur",
    "com.cyanogenmod.filemanager",
    "com.android.bookmarkprovider",
    "com.android.wallpaperbackup",
    "com.android.gallery3d",
    "com.android.messaging",
    "com.android.mms.service",
    "com.android.smspush",
    "com.android.basicsmsreceiver",
    "com.android.server.telecom",
    "com.android.simappdialog",
    "com.android.carrierconfig",
    "com.android.carrierdefaultapp",
    "com.android.contacts",
    "com.android.providers.contacts",
    "com.android.providers.calendar",
    "com.android.providers.telephony",
    "com.android.providers.userdictionary",
    "com.google.android.tts",
    "com.google.android.backuptransport",
    "com.google.android.configupdater",
    "com.android.companiondevicemanager",
    "com.android.htmlviewer",
    "com.android.se",
    "com.android.vpndialogs",
    "com.android.location.fused",
    "com.android.settings.intelligence",
    "com.android.managedprovisioning",
    "com.android.provision",
    "com.android.inputmethod.pinyin",
    "com.google.android.play.games",
    "com.android.chrome",
}


@dataclass(slots=True, frozen=True)
class AndroidPackage:
    name: str
    source: str
    disabled: bool
    protected: bool
    review_suggested: bool
    recommendation: str = ""


@dataclass(slots=True)
class PackageActionResult:
    backup: Path
    changed: list[str]
    failed: dict[str, str]


def parse_package_list(output: str) -> set[str]:
    packages: set[str] = set()
    for line in output.splitlines():
        value = line.strip()
        if not value.startswith("package:"):
            continue
        value = value.removeprefix("package:")
        if "=" in value:
            value = value.rsplit("=", 1)[-1]
        if PACKAGE_PATTERN.fullmatch(value):
            packages.add(value)
    return packages


def is_protected_package(package: str) -> bool:
    lowered = package.lower()
    return (
        lowered in PROTECTED_EXACT
        or lowered.startswith(PROTECTED_PREFIXES)
        or "launcher" in lowered
        or "systemui" in lowered
        or lowered.endswith(".settings")
    )


class PackageManager:
    def __init__(self, adb: ADBManager):
        self.adb = adb

    def scan(self, serial: str, *, include_system: bool = False) -> list[AndroidPackage]:
        user_packages = parse_package_list(self.adb.shell(serial, "pm list packages -3"))
        system_packages = (
            parse_package_list(self.adb.shell(serial, "pm list packages -s"))
            if include_system
            else set()
        )
        disabled = parse_package_list(self.adb.shell(serial, "pm list packages -d"))
        result: list[AndroidPackage] = []
        for package in sorted(user_packages | system_packages):
            protected = is_protected_package(package)
            result.append(
                AndroidPackage(
                    name=package,
                    source="Hệ thống" if package in system_packages else "Người dùng",
                    disabled=package in disabled,
                    protected=protected,
                    review_suggested=(
                        not protected and any(token in package.lower() for token in REVIEW_TOKENS)
                    ),
                    recommendation="Được bảo vệ" if protected else "Chưa phân tích",
                )
            )
        return result

    def analyze_for_target(self, serial: str, target: str) -> list[AndroidPackage]:
        if not PACKAGE_PATTERN.fullmatch(target):
            raise ValueError("Tên package mục tiêu không hợp lệ.")
        packages = self.scan(serial, include_system=True)
        if target not in {package.name for package in packages}:
            raise ValueError(f"Không tìm thấy ứng dụng mục tiêu {target} trên thiết bị.")
        analyzed: list[AndroidPackage] = []
        for package in packages:
            if package.name == target:
                recommendation = "Ứng dụng mục tiêu — bắt buộc giữ"
                suggested = False
            elif package.protected:
                recommendation = "Dịch vụ Android/Google cần giữ"
                suggested = False
            elif package.name in SAFE_OPTIONAL_PACKAGES:
                recommendation = "Có thể tắt thử cho mục tiêu này"
                suggested = True
            elif package.source == "Người dùng":
                recommendation = "Ứng dụng khác — xem xét tắt"
                suggested = True
            else:
                recommendation = "Chưa rõ — nên giữ"
                suggested = False
            analyzed.append(
                AndroidPackage(
                    name=package.name,
                    source=package.source,
                    disabled=package.disabled,
                    protected=package.protected or package.name == target,
                    review_suggested=suggested,
                    recommendation=recommendation,
                )
            )
        return analyzed

    def _validate(self, packages: list[str]) -> list[str]:
        clean = sorted(set(packages))
        for package in clean:
            if not PACKAGE_PATTERN.fullmatch(package):
                raise ValueError(f"Tên package không hợp lệ: {package}")
        return clean

    def _snapshot(self, serial: str, packages: list[str]) -> Path:
        disabled = parse_package_list(self.adb.shell(serial, "pm list packages -d"))
        safe_serial = re.sub(r"[^A-Za-z0-9_.-]", "_", serial)
        folder = backup_dir() / "packages" / safe_serial
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"packages_{datetime.now():%Y%m%d_%H%M%S_%f}.json"
        data = {
            "serial": serial,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "packages": {package: package in disabled for package in packages},
        }
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def disable(self, serial: str, packages: list[str]) -> PackageActionResult:
        clean = self._validate(packages)
        protected = [package for package in clean if is_protected_package(package)]
        if protected:
            raise ValueError("Không thể vô hiệu hóa package thiết yếu: " + ", ".join(protected))
        backup = self._snapshot(serial, clean)
        changed: list[str] = []
        failed: dict[str, str] = {}
        for package in clean:
            try:
                self.adb.shell(serial, f"pm disable-user --user 0 {package}")
                changed.append(package)
            except Exception as exc:
                failed[package] = str(exc)
        return PackageActionResult(backup, changed, failed)

    def enable(self, serial: str, packages: list[str]) -> PackageActionResult:
        clean = self._validate(packages)
        backup = self._snapshot(serial, clean)
        changed: list[str] = []
        failed: dict[str, str] = {}
        for package in clean:
            try:
                self.adb.shell(serial, f"pm enable {package}")
                changed.append(package)
            except Exception as exc:
                failed[package] = str(exc)
        return PackageActionResult(backup, changed, failed)

    def restore(self, backup_file: str | Path) -> PackageActionResult:
        path = Path(backup_file)
        data = json.loads(path.read_text(encoding="utf-8"))
        serial = str(data["serial"])
        states = dict(data["packages"])
        packages = self._validate(list(states))
        changed: list[str] = []
        failed: dict[str, str] = {}
        for package in packages:
            command = (
                f"pm disable-user --user 0 {package}" if states[package] else f"pm enable {package}"
            )
            try:
                self.adb.shell(serial, command)
                changed.append(package)
            except Exception as exc:
                failed[package] = str(exc)
        return PackageActionResult(path, changed, failed)
