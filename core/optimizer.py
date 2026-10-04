from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
import json
import logging
from pathlib import Path
import shutil
from typing import Any

from core.adb import ADBManager
from core.ldplayer import LDPlayerConsole
from utils.system import backup_dir


@dataclass(slots=True, frozen=True)
class OptimizationProfile:
    cpu: int
    ram: int
    width: int
    height: int
    dpi: int
    fps: int
    animation: bool = False
    audio: bool = False

    @classmethod
    def from_dict(cls, values: dict[str, Any]) -> "OptimizationProfile":
        resolution = values.get("resolution")
        if resolution and ("width" not in values or "height" not in values):
            width, height = str(resolution).lower().split("x", 1)
        else:
            width, height = values.get("width", 540), values.get("height", 960)
        profile = cls(
            cpu=int(values.get("cpu", 1)),
            ram=int(values.get("ram", 512)),
            width=int(width),
            height=int(height),
            dpi=int(values.get("dpi", 160)),
            fps=int(values.get("fps", 20)),
            animation=bool(values.get("animation", False)),
            audio=bool(values.get("audio", False)),
        )
        profile.validate()
        return profile

    def validate(self) -> None:
        if not 1 <= self.cpu <= 16:
            raise ValueError("CPU phải nằm trong khoảng 1–16 core.")
        if self.ram not in (512, 768, 1024, 1536, 2048, 4096, 8192):
            raise ValueError("Dung lượng RAM không hợp lệ.")
        if not 240 <= self.width <= 3840 or not 240 <= self.height <= 3840:
            raise ValueError("Độ phân giải phải nằm trong khoảng 240–3840 pixel.")
        if not 80 <= self.dpi <= 640:
            raise ValueError("DPI phải nằm trong khoảng 80–640.")
        if self.fps not in (15, 20, 30, 60):
            raise ValueError("FPS phải là 15, 20, 30 hoặc 60.")


class Optimizer:
    def __init__(self, console: LDPlayerConsole, adb: ADBManager | None = None):
        self.console = console
        self.adb = adb
        self.logger = logging.getLogger("ldlite")

    def _native_config(self, index: int) -> Path | None:
        base = self.console.path.parent
        candidates = (
            base / "vms" / "config" / f"leidian{index}.config",
            base / "vms" / "config" / f"leidian{index}.config.bak",
        )
        return next((path for path in candidates if path.is_file()), None)

    def backup(self, index: int, profile: OptimizationProfile) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        folder = backup_dir() / f"instance_{index}" / timestamp
        folder.mkdir(parents=True, exist_ok=False)
        native = self._native_config(index)
        copied = None
        if native:
            copied = folder / native.name
            shutil.copy2(native, copied)
        metadata = {
            "instance_index": index,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "native_config": str(native) if native else None,
            "native_backup": copied.name if copied else None,
            "requested_profile": asdict(profile),
        }
        (folder / "backup.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return folder

    def apply(self, index: int, profile: OptimizationProfile) -> Path:
        profile.validate()
        current = next((item for item in self.console.list_instances() if item.index == index), None)
        if current is None:
            raise RuntimeError(f"Instance {index} không tồn tại.")
        backup = self.backup(index, profile)
        self.console.modify(
            index,
            cpu=profile.cpu,
            memory=profile.ram,
            width=profile.width,
            height=profile.height,
            dpi=profile.dpi,
            fps=profile.fps,
        )
        verified = next((item for item in self.console.list_instances() if item.index == index), None)
        if verified is None:
            raise RuntimeError("Không thể xác minh instance sau khi tối ưu.")
        if verified.running:
            self.set_instance_animations(index, profile.animation)
        else:
            self.logger.info(
                "Instance %s đang dừng; cài đặt animation sẽ được áp dụng khi tối ưu lại lúc instance đang chạy.",
                index,
            )
        return backup

    def set_instance_animations(self, index: int, enabled: bool) -> None:
        value = "1" if enabled else "0"
        for setting in (
            "window_animation_scale",
            "transition_animation_scale",
            "animator_duration_scale",
        ):
            self.console.adb_shell(index, f"shell settings put global {setting} {value}")

    def set_animations(self, serial: str, enabled: bool) -> None:
        if not self.adb:
            raise RuntimeError("ADB chưa được cấu hình.")
        value = "1" if enabled else "0"
        for setting in (
            "window_animation_scale",
            "transition_animation_scale",
            "animator_duration_scale",
        ):
            self.adb.shell(serial, f"settings put global {setting} {value}")

    def restore(self, backup_folder: str | Path) -> None:
        folder = Path(backup_folder)
        metadata = json.loads((folder / "backup.json").read_text(encoding="utf-8"))
        index = int(metadata["instance_index"])
        instance = next((item for item in self.console.list_instances() if item.index == index), None)
        if instance is None:
            raise RuntimeError(f"Instance {index} không còn tồn tại.")
        if instance.running:
            raise RuntimeError(f"Hãy dừng instance {index} trước khi khôi phục.")
        source_name = metadata.get("native_backup")
        destination = metadata.get("native_config")
        if not source_name or not destination:
            raise RuntimeError("Bản sao lưu này không chứa file cấu hình gốc.")
        source = folder / source_name
        target = Path(destination)
        if not source.is_file():
            raise RuntimeError("Không tìm thấy file cấu hình trong bản sao lưu.")
        if target.is_file():
            safety_copy = folder / f"pre_restore_{datetime.now():%Y%m%d_%H%M%S}.config"
            shutil.copy2(target, safety_copy)
        shutil.copy2(source, target)
