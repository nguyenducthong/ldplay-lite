from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.adb import ADBDevice, ldplayer_index_from_serial
from core.instance import Instance
from core.packages import AndroidPackage


class PackagesPanel(QWidget):
    scan_requested = Signal(str, bool)
    disable_requested = Signal(str, list)
    enable_requested = Signal(str, list)
    restore_requested = Signal()
    analyze_requested = Signal(str, str)

    def __init__(self) -> None:
        super().__init__()
        title = QLabel("Ứng dụng Android")
        title.setObjectName("pageTitle")
        hint = QLabel(
            "Mặc định chỉ hiện ứng dụng người dùng. Hãy vô hiệu hóa từng nhóm nhỏ rồi kiểm tra; Manager không gỡ cài đặt package."
        )
        hint.setWordWrap(True)
        hint.setObjectName("warning")

        self.devices = QComboBox()
        self.include_system = QCheckBox("Hiện package hệ thống")
        scan = QPushButton("Quét package")
        scan.setObjectName("primaryButton")
        scan.clicked.connect(self._scan)
        controls = QHBoxLayout()
        controls.addWidget(QLabel("Thiết bị"))
        controls.addWidget(self.devices, 1)
        controls.addWidget(self.include_system)
        controls.addWidget(scan)

        self.target = QLineEdit("vn.kvtm.js")
        self.target.setPlaceholderText("Package ứng dụng cần giữ")
        analyze = QPushButton("Phân tích ứng dụng mục tiêu")
        analyze.clicked.connect(
            lambda: self.analyze_requested.emit(
                self.current_serial(), self.target.text().strip()
            )
        )
        target_row = QHBoxLayout()
        target_row.addWidget(QLabel("Chỉ cần chạy"))
        target_row.addWidget(self.target, 1)
        target_row.addWidget(analyze)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(("Chọn", "Package", "Loại", "Trạng thái", "Đánh giá"))
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().hide()
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        for column in (2, 3, 4):
            header.setSectionResizeMode(column, QHeaderView.ResizeToContents)

        disable = QPushButton("Vô hiệu hóa đã chọn")
        disable.setObjectName("dangerButton")
        disable.clicked.connect(
            lambda: self.disable_requested.emit(self.current_serial(), self.selected_packages())
        )
        enable = QPushButton("Bật lại đã chọn")
        enable.clicked.connect(
            lambda: self.enable_requested.emit(self.current_serial(), self.selected_packages())
        )
        restore = QPushButton("Khôi phục từ backup…")
        restore.clicked.connect(self.restore_requested.emit)
        actions = QHBoxLayout()
        actions.addWidget(disable)
        actions.addWidget(enable)
        actions.addWidget(restore)
        actions.addStretch()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(12)
        layout.addWidget(title)
        layout.addWidget(hint)
        layout.addLayout(controls)
        layout.addLayout(target_row)
        layout.addWidget(self.table, 1)
        layout.addLayout(actions)

    def current_serial(self) -> str:
        return str(self.devices.currentData() or "")

    def set_devices(self, devices: list[ADBDevice], instances: list[Instance] | None = None) -> None:
        previous = self.current_serial()
        self.devices.clear()
        by_index = {item.index: item for item in (instances or [])}
        for device in devices:
            index = ldplayer_index_from_serial(device.serial)
            instance = by_index.get(index) if index is not None else None
            label = f"{instance.name} ({device.serial})" if instance else f"{device.serial}  ·  {device.state}"
            self.devices.addItem(label, device.serial)
        index = self.devices.findData(previous)
        if index >= 0:
            self.devices.setCurrentIndex(index)

    def set_packages(self, packages: list[AndroidPackage]) -> None:
        self.table.setRowCount(len(packages))
        for row, package in enumerate(packages):
            check = QTableWidgetItem()
            check.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
            check.setCheckState(Qt.Unchecked)
            check.setData(Qt.UserRole, package.name)
            if package.protected:
                check.setFlags(Qt.NoItemFlags)
            elif package.review_suggested and not package.disabled:
                check.setCheckState(Qt.Checked)
            self.table.setItem(row, 0, check)
            values = (
                package.name,
                package.source,
                "Đã tắt" if package.disabled else "Đang bật",
                package.recommendation
                or ("Được bảo vệ" if package.protected else ("Nên xem xét" if package.review_suggested else "Thủ công")),
            )
            for column, value in enumerate(values, start=1):
                item = QTableWidgetItem(value)
                if column == 3:
                    item.setForeground(QColor("#94a3b8" if package.disabled else "#22c55e"))
                if column == 4 and package.review_suggested:
                    item.setForeground(QColor("#fbbf24"))
                self.table.setItem(row, column, item)

    def selected_packages(self) -> list[str]:
        selected: list[str] = []
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and item.checkState() == Qt.Checked:
                selected.append(str(item.data(Qt.UserRole)))
        return selected

    def _scan(self) -> None:
        self.scan_requested.emit(self.current_serial(), self.include_system.isChecked())
