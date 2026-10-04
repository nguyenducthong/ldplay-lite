from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any

from utils.system import PROJECT_ROOT, user_data_dir


DEFAULT_CONFIG: dict[str, Any] = {
    "ldplayer_path": "",
    "console_path": "",
    "adb_path": "",
    "default_profile": "Lite",
    "startup_delay": 5,
    "adb_timeout": 30,
    "screenshot_directory": "",
    "log_directory": "",
    "last_optimization_profile": {},
}


class ConfigStore:
    def __init__(self, path: Path | None = None):
        self.path = path or user_data_dir() / "app_config.json"
        self.data = deepcopy(DEFAULT_CONFIG)
        self.load()

    def load(self) -> dict[str, Any]:
        seed = PROJECT_ROOT / "config" / "app_config.json"
        source = self.path if self.path.exists() else seed
        if source.exists():
            try:
                loaded = json.loads(source.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    self.data.update(loaded)
            except (OSError, json.JSONDecodeError):
                pass
        return self.data

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def update(self, **values: Any) -> None:
        self.data.update(values)
        self.save()


def load_profiles(path: Path | None = None) -> dict[str, dict[str, Any]]:
    source = path or PROJECT_ROOT / "config" / "profiles.json"
    loaded = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError("profiles.json phải là một object JSON.")
    return loaded
