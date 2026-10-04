from __future__ import annotations

import logging

from core.instance import Instance


PRIORITIES = {"normal", "below_normal", "idle"}


def set_instance_priority(instance: Instance, priority: str) -> list[str]:
    """Set host process priority after boot so startup itself remains responsive."""
    if priority not in PRIORITIES:
        raise ValueError(f"Độ ưu tiên tiến trình không hợp lệ: {priority}")
    if priority == "normal":
        return []
    try:
        import psutil
    except ImportError as exc:
        raise RuntimeError("Thiếu psutil; hãy cài lại requirements.txt.") from exc

    target = {
        "below_normal": psutil.BELOW_NORMAL_PRIORITY_CLASS,
        "idle": psutil.IDLE_PRIORITY_CLASS,
    }[priority]
    warnings: list[str] = []
    for pid in {instance.process_id, instance.vbox_process_id} - {0}:
        try:
            psutil.Process(pid).nice(target)
        except (psutil.NoSuchProcess, psutil.AccessDenied) as exc:
            warnings.append(f"Không thể đặt độ ưu tiên PID {pid}: {exc}")
    if warnings:
        logging.getLogger("ldlite").warning("; ".join(warnings))
    return warnings
