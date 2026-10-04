from __future__ import annotations

import csv
from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class Instance:
    index: int
    name: str
    running: bool
    top_window_handle: int = 0
    bind_window_handle: int = 0
    process_id: int = 0
    vbox_process_id: int = 0
    width: int = 0
    height: int = 0
    dpi: int = 0

    @property
    def status(self) -> str:
        return "RUNNING" if self.running else "STOPPED"


def _number(value: str) -> int:
    try:
        return int(value.strip())
    except (TypeError, ValueError):
        return 0


def parse_list2(output: str) -> list[Instance]:
    instances: list[Instance] = []
    for row in csv.reader(line for line in output.splitlines() if line.strip()):
        if len(row) < 2 or not row[0].strip().lstrip("-").isdigit():
            continue
        values = row + [""] * (10 - len(row))
        instances.append(
            Instance(
                index=_number(values[0]),
                name=values[1].strip(),
                top_window_handle=_number(values[2]),
                bind_window_handle=_number(values[3]),
                running=_number(values[4]) == 1,
                process_id=_number(values[5]),
                vbox_process_id=_number(values[6]),
                width=_number(values[7]),
                height=_number(values[8]),
                dpi=_number(values[9]),
            )
        )
    return sorted(instances, key=lambda item: item.index)
