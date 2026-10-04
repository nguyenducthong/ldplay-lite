from __future__ import annotations

import os
from pathlib import Path
import sys


base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent / "_internal"))
dll_directories = [base / "PySide6", base / "shiboken6", base]
handles = []
for directory in dll_directories:
    if directory.is_dir() and hasattr(os, "add_dll_directory"):
        handles.append(os.add_dll_directory(str(directory)))

# Keep handles alive and put bundled Qt ahead of third-party Qt/VC runtimes in PATH.
os._ldlite_dll_handles = handles  # type: ignore[attr-defined]
bundled_path = os.pathsep.join(str(path) for path in dll_directories if path.is_dir())
os.environ["PATH"] = bundled_path + os.pathsep + os.environ.get("PATH", "")
plugin_path = base / "PySide6" / "plugins"
if plugin_path.is_dir():
    os.environ["QT_PLUGIN_PATH"] = str(plugin_path)
