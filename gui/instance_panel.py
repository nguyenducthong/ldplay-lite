from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.instance import Instance


class InstancePanel(QWidget):
    refresh_requested = Signal()
    action_requested = Signal(str, list)
    create_requested = Signal()
    clone_requested = Signal(int)
    rename_requested = Signal(int)

    def __init__(self) -> None:
        super().__init__()
        self.instances: list[Instance] = []

        title = QLabel("Quản lý instance")
        title.setObjectName("pageTitle")
        hint = QLabel("Chọn một hoặc nhiều dòng để thực hiện thao tác hàng loạt.")
        hint.setObjectName("muted")

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(("ID", "Tên", "Trạng thái", "PID", "VBox PID"))
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().hide()
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        for column in (2, 3, 4):
            header.setSectionResizeMode(column, QHeaderView.ResizeToContents)

        top_actions = QHBoxLayout()
        for label, callback in (
            ("Làm mới", self.refresh_requested.emit),
            ("Tạo mới", self.create_requested.emit),
            ("Nhân bản", self._clone),
            ("Đổi tên", self._rename),
        ):
            button = QPushButton(label)
            button.clicked.connect(callback)
            top_actions.addWidget(button)
        top_actions.addStretch()

        actions = QHBoxLayout()
        for label, action, primary in (
            ("Khởi động", "start", True),
            ("Dừng", "stop", False),
            ("Khởi động lại", "restart", False),
            ("Xóa", "delete", False),
        ):
            button = QPushButton(label)
            if primary:
                button.setObjectName("primaryButton")
            if action == "delete":
                button.setObjectName("dangerButton")
            button.clicked.connect(lambda _checked=False, name=action: self._emit_action(name))
            actions.addWidget(button)
        actions.addStretch()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(12)
        layout.addWidget(title)
        layout.addWidget(hint)
        layout.addLayout(top_actions)
        layout.addWidget(self.table, 1)
        layout.addLayout(actions)

    def set_instances(self, instances: list[Instance]) -> None:
        self.instances = instances
        self.table.setRowCount(len(instances))
        for row, instance in enumerate(instances):
            values = (
                str(instance.index),
                instance.name,
                "Đang chạy" if instance.running else "Đã dừng",
                str(instance.process_id or "—"),
                str(instance.vbox_process_id or "—"),
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.UserRole, instance.index)
                if column == 2:
                    item.setForeground(QColor("#22c55e" if instance.running else "#94a3b8"))
                self.table.setItem(row, column, item)

    def selected_indices(self) -> list[int]:
        rows = sorted({item.row() for item in self.table.selectedItems()})
        return [int(self.table.item(row, 0).text()) for row in rows]

    def _emit_action(self, action: str) -> None:
        self.action_requested.emit(action, self.selected_indices())

    def _clone(self) -> None:
        selected = self.selected_indices()
        if len(selected) == 1:
            self.clone_requested.emit(selected[0])

    def _rename(self) -> None:
        selected = self.selected_indices()
        if len(selected) == 1:
            self.rename_requested.emit(selected[0])
