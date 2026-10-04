from __future__ import annotations

import logging
from pathlib import Path
import time
from collections.abc import Callable

from core.instance import Instance, parse_list2
from utils.process import CommandResult, run_command


class LDPlayerConsole:
    def __init__(self, console_path: str | Path, *, timeout: int = 30):
        self.path = Path(console_path)
        self.timeout = timeout
        self.logger = logging.getLogger("ldlite")

    def _run(self, *args: str, timeout: int | None = None) -> CommandResult:
        self.logger.info("LDConsole: %s", " ".join(args))
        return run_command((self.path, *args), timeout=timeout or self.timeout)

    def list_instances(self) -> list[Instance]:
        return parse_list2(self._run("list2").stdout)

    def start(self, index: int) -> None:
        self._run("launch", "--index", str(index))

    def stop(self, index: int) -> None:
        self._run("quit", "--index", str(index))

    def restart(self, index: int) -> None:
        self._run("reboot", "--index", str(index))

    def create(self, name: str) -> None:
        self._run("add", "--name", name)

    def clone(self, source_index: int, name: str) -> None:
        self._run("copy", "--name", name, "--from", str(source_index), timeout=180)

    def delete(self, index: int) -> None:
        self._run("remove", "--index", str(index), timeout=120)

    def rename(self, index: int, name: str) -> None:
        self._run("rename", "--index", str(index), "--title", name)

    def modify(
        self,
        index: int,
        *,
        cpu: int,
        memory: int,
        width: int,
        height: int,
        dpi: int,
    ) -> None:
        resolution = f"{width},{height},{dpi}"
        self._run(
            "modify",
            "--index",
            str(index),
            "--cpu",
            str(cpu),
            "--memory",
            str(memory),
            "--resolution",
            resolution,
        )

    def global_settings(
        self,
        *,
        fps: int,
        audio: bool,
        fastplay: bool = True,
        cleanmode: bool = True,
    ) -> None:
        """Apply LDPlayer's global multi-instance optimization settings."""
        self._run(
            "globalsetting",
            "--fps",
            str(fps),
            "--audio",
            "1" if audio else "0",
            "--fastplay",
            "1" if fastplay else "0",
            "--cleanmode",
            "1" if cleanmode else "0",
        )

    def adb_shell(self, index: int, command: str) -> str:
        """Run a shell command through LDConsole for a specific running instance."""
        return self._run("adb", "--index", str(index), "--command", command).stdout

    def wait_for_state(
        self,
        index: int,
        *,
        running: bool,
        timeout: int = 90,
        poll_interval: float = 1.0,
    ) -> Instance:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            instance = next((item for item in self.list_instances() if item.index == index), None)
            if instance and instance.running == running:
                return instance
            time.sleep(poll_interval)
        state = "khởi động" if running else "dừng"
        raise TimeoutError(f"Instance {index} không {state} trong {timeout} giây.")

    def start_sequential(
        self,
        indices: list[int],
        delay: int = 5,
        *,
        wait_ready: bool = True,
        after_start: Callable[[Instance], None] | None = None,
    ) -> dict[int, float]:
        startup_times: dict[int, float] = {}
        for position, index in enumerate(indices):
            started_at = time.monotonic()
            self.start(index)
            if wait_ready:
                instance = self.wait_for_state(index, running=True)
                startup_times[index] = time.monotonic() - started_at
                if after_start:
                    after_start(instance)
            if position < len(indices) - 1:
                time.sleep(delay)
        return startup_times

    def stop_all(self) -> None:
        self._run("quitall")
