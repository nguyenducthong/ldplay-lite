from __future__ import annotations

import os
from pathlib import Path


APP_NAME = "LDPlayerLiteManager"
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def user_data_dir() -> Path:
    base = Path(os.environ.get("APPDATA", Path.home()))
    path = base / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def logs_dir() -> Path:
    path = user_data_dir() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def backup_dir() -> Path:
    path = user_data_dir() / "backups"
    path.mkdir(parents=True, exist_ok=True)
    return path


def screenshots_dir() -> Path:
    path = user_data_dir() / "screenshots"
    path.mkdir(parents=True, exist_ok=True)
    return path
