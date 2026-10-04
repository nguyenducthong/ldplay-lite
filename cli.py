from __future__ import annotations

import argparse
from pathlib import Path
import sys

from core.adb import ADBManager
from core.detector import detect_ldplayer
from core.ldplayer import LDPlayerConsole
from core.optimizer import OptimizationProfile, Optimizer
from utils.config import ConfigStore, load_profiles
from utils.logger import configure_logging
from utils.system import logs_dir


def _configure_console_encoding() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            reconfigure(encoding="utf-8", errors="replace")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ldlite", description="Quản lý LDPlayer nhẹ bằng CLI")
    parser.add_argument("--console", help="Đường dẫn ldconsole.exe")
    parser.add_argument("--adb", help="Đường dẫn adb.exe")
    parser.add_argument("--verbose", action="store_true")
    commands = parser.add_subparsers(dest="command")
    commands.add_parser("gui", help="Mở giao diện")
    commands.add_parser("detect", help="Phát hiện LDPlayer")
    commands.add_parser("list", help="Liệt kê instance")

    for name in ("start", "stop", "restart", "delete", "optimize"):
        item = commands.add_parser(name)
        item.add_argument("index", type=int)
        if name == "optimize":
            item.add_argument("--profile", default="Lite")

    create = commands.add_parser("create")
    create.add_argument("name")
    clone = commands.add_parser("clone")
    clone.add_argument("index", type=int)
    clone.add_argument("name")
    rename = commands.add_parser("rename")
    rename.add_argument("index", type=int)
    rename.add_argument("name")
    optimize_all = commands.add_parser("optimize-all")
    optimize_all.add_argument("--profile", default="Lite")
    start_all = commands.add_parser("start-all")
    start_all.add_argument("--delay", type=int)
    commands.add_parser("stop-all")
    restore = commands.add_parser("restore")
    restore.add_argument("backup_folder")

    adb = commands.add_parser("adb")
    adb.add_argument("serial")
    adb.add_argument("shell_command", nargs=argparse.REMAINDER)
    screenshot = commands.add_parser("screenshot")
    screenshot.add_argument("serial")
    screenshot.add_argument("--output")
    return parser


def _paths(args: argparse.Namespace, config: ConfigStore) -> tuple[Path | None, Path | None]:
    console = Path(args.console or config.data.get("console_path", ""))
    adb = Path(args.adb or config.data.get("adb_path", ""))
    if not console.is_file():
        installation = detect_ldplayer(args.console)
        if installation:
            console = installation.console
            adb = installation.adb or adb
            config.update(
                ldplayer_path=str(installation.root),
                console_path=str(console),
                adb_path=str(adb) if adb and adb.is_file() else "",
            )
    return (console if console.is_file() else None, adb if adb.is_file() else None)


def _profile(name: str) -> OptimizationProfile:
    profiles = load_profiles()
    match = next((key for key in profiles if key.lower() == name.lower()), None)
    if not match:
        raise ValueError(f"Không có profile '{name}'. Có sẵn: {', '.join(profiles)}")
    return OptimizationProfile.from_dict(profiles[match])


def main(argv: list[str] | None = None) -> int:
    _configure_console_encoding()
    args = _parser().parse_args(argv)
    if args.command in (None, "gui"):
        from gui.main_window import run_gui

        return run_gui()

    configure_logging(logs_dir(), verbose=args.verbose)
    config = ConfigStore()
    console_path, adb_path = _paths(args, config)

    if args.command == "detect":
        if not console_path:
            print("Không tìm thấy LDPlayer.", file=sys.stderr)
            return 1
        print(f"LDConsole: {console_path}")
        print(f"ADB: {adb_path or 'không tìm thấy'}")
        return 0

    if args.command in ("adb", "screenshot"):
        if not adb_path:
            print("Không tìm thấy ADB. Dùng --adb để chỉ định đường dẫn.", file=sys.stderr)
            return 2
        adb = ADBManager(adb_path, timeout=int(config.data.get("adb_timeout", 30)))
        if args.command == "adb":
            command = " ".join(args.shell_command).strip()
            print(adb.shell(args.serial, command), end="")
        else:
            print(adb.screenshot(args.serial, args.output))
        return 0

    if not console_path:
        print("Không tìm thấy LDConsole. Dùng --console để chỉ định đường dẫn.", file=sys.stderr)
        return 2
    console = LDPlayerConsole(console_path)

    if args.command == "list":
        for item in console.list_instances():
            print(f"{item.index:>2}  {item.name:<24} {item.status}")
    elif args.command in ("start", "stop", "restart", "delete"):
        getattr(console, args.command)(args.index)
    elif args.command == "create":
        console.create(args.name)
    elif args.command == "clone":
        console.clone(args.index, args.name)
    elif args.command == "rename":
        console.rename(args.index, args.name)
    elif args.command in ("optimize", "optimize-all"):
        optimizer = Optimizer(console, ADBManager(adb_path) if adb_path else None)
        profile = _profile(args.profile)
        targets = [args.index] if args.command == "optimize" else [item.index for item in console.list_instances()]
        for index in targets:
            backup = optimizer.apply(index, profile)
            print(f"Đã tối ưu {index}; backup: {backup}")
    elif args.command == "start-all":
        indices = [item.index for item in console.list_instances() if not item.running]
        delay = args.delay if args.delay is not None else int(config.data.get("startup_delay", 10))
        console.start_sequential(indices, delay)
    elif args.command == "stop-all":
        console.stop_all()
    elif args.command == "restore":
        Optimizer(console).restore(args.backup_folder)
        print("Đã khôi phục cấu hình instance.")
    return 0
