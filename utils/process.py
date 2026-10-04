from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
from typing import Iterable


@dataclass(slots=True)
class CommandResult:
    command: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


class CommandError(RuntimeError):
    def __init__(self, result: CommandResult):
        message = result.stderr.strip() or result.stdout.strip() or "Lệnh thực thi thất bại."
        super().__init__(f"{message} (mã {result.returncode})")
        self.result = result


def _startupinfo() -> subprocess.STARTUPINFO | None:
    if not hasattr(subprocess, "STARTUPINFO"):
        return None
    info = subprocess.STARTUPINFO()
    info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    return info


def run_command(
    command: Iterable[str | Path],
    *,
    timeout: int = 30,
    check: bool = True,
    cwd: str | Path | None = None,
) -> CommandResult:
    args = tuple(str(part) for part in command)
    try:
        completed = subprocess.run(
            args,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            startupinfo=_startupinfo(),
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            shell=False,
        )
    except FileNotFoundError as exc:
        result = CommandResult(args, 127, "", f"Không tìm thấy tệp thực thi: {args[0]}")
        raise CommandError(result) from exc
    except subprocess.TimeoutExpired as exc:
        result = CommandResult(args, 124, exc.stdout or "", f"Quá thời gian {timeout} giây.")
        raise CommandError(result) from exc

    result = CommandResult(args, completed.returncode, completed.stdout, completed.stderr)
    if check and not result.ok:
        raise CommandError(result)
    return result


def run_binary(
    command: Iterable[str | Path], *, timeout: int = 30, check: bool = True
) -> bytes:
    args = tuple(str(part) for part in command)
    try:
        completed = subprocess.run(
            args,
            capture_output=True,
            timeout=timeout,
            startupinfo=_startupinfo(),
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            shell=False,
        )
    except FileNotFoundError as exc:
        result = CommandResult(args, 127, "", f"Không tìm thấy tệp thực thi: {args[0]}")
        raise CommandError(result) from exc
    except subprocess.TimeoutExpired as exc:
        result = CommandResult(args, 124, "", f"Quá thời gian {timeout} giây.")
        raise CommandError(result) from exc

    if check and completed.returncode != 0:
        result = CommandResult(
            args,
            completed.returncode,
            completed.stdout.decode("utf-8", errors="replace"),
            completed.stderr.decode("utf-8", errors="replace"),
        )
        raise CommandError(result)
    return completed.stdout
