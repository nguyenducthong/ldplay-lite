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
        self._all_packages: list[AndroidPackage] = []

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

        # Filter & Search row
        self.filter_combo = QComboBox()
        self.filter_combo.addItems([
            "Tất cả", "Đã tắt (Disabled)", "Đang bật (Active)", "Đề xuất tắt", "Người dùng", "Hệ thống"
        ])
        self.filter_combo.currentTextChanged.connect(self._render_filtered_packages)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Tìm kiếm theo tên package…")
        self.search_input.textChanged.connect(self._render_filtered_packages)

        self.summary_label = QLabel("Chưa tải package")
        self.summary_label.setObjectName("muted")

        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Lọc:"))
        filter_row.addWidget(self.filter_combo)
        filter_row.addWidget(QLabel("Tìm:"))
        filter_row.addWidget(self.search_input, 1)
        filter_row.addWidget(self.summary_label)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(("Chọn", "Package", "Loại", "Trạng thái", "Đánh giá"))
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().hide()
        self.table.cellDoubleClicked.connect(self._on_double_click_row)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        for column in (2, 3, 4):
            header.setSectionResizeMode(column, QHeaderView.ResizeToContents)

        select_all = QPushButton("☑ Chọn tất cả")
        select_all.clicked.connect(self.select_all)
        deselect_all = QPushButton("☐ Bỏ chọn")
        deselect_all.clicked.connect(self.deselect_all)

        quick_toggle = QPushButton("⚡ Bật/Tắt nhanh")
        quick_toggle.clicked.connect(self._quick_toggle_selected)

        disable = QPushButton("🔴 Vô hiệu hóa đã chọn")
        disable.setObjectName("dangerButton")
        disable.clicked.connect(
            lambda: self.disable_requested.emit(self.current_serial(), self.selected_packages())
        )
        enable = QPushButton("🟢 Bật lại đã chọn")
        enable.clicked.connect(
            lambda: self.enable_requested.emit(self.current_serial(), self.selected_packages())
        )
        enable_all = QPushButton("🟢 Bật TẤT CẢ đã tắt")
        enable_all.clicked.connect(self._enable_all_disabled)

        restore = QPushButton("Khôi phục từ backup…")
        restore.clicked.connect(self.restore_requested.emit)

        actions = QHBoxLayout()
        actions.addWidget(select_all)
        actions.addWidget(deselect_all)
        actions.addWidget(quick_toggle)
        actions.addWidget(disable)
        actions.addWidget(enable)
        actions.addWidget(enable_all)
        actions.addWidget(restore)
        actions.addStretch()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(12)
        layout.addWidget(title)
        layout.addWidget(hint)
        layout.addLayout(controls)
        layout.addLayout(target_row)
        layout.addLayout(filter_row)
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
        self._all_packages = packages
        self._render_filtered_packages()

    def _render_filtered_packages(self) -> None:
        mode = self.filter_combo.currentText() if hasattr(self, "filter_combo") else "Tất cả"
        search = self.search_input.text().strip().lower() if hasattr(self, "search_input") else ""

        filtered: list[AndroidPackage] = []
        disabled_count = 0
        for p in self._all_packages:
            if p.disabled:
                disabled_count += 1
            if mode == "Đã tắt (Disabled)" and not p.disabled:
                continue
            if mode == "Đang bật (Active)" and p.disabled:
                continue
            if mode == "Đề xuất tắt" and (not p.review_suggested or p.disabled):
                continue
            if mode == "Người dùng" and p.source != "Người dùng":
                continue
            if mode == "Hệ thống" and p.source != "Hệ thống":
                continue
            if search and search not in p.name.lower():
                continue
            filtered.append(p)

        self.table.setRowCount(len(filtered))
        for row, package in enumerate(filtered):
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

        if hasattr(self, "summary_label"):
            self.summary_label.setText(f"Hiển thị {len(filtered)}/{len(self._all_packages)}  ·  Đã tắt: {disabled_count}")

    def select_all(self) -> None:
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and (item.flags() & Qt.ItemIsUserCheckable):
                item.setCheckState(Qt.Checked)

    def deselect_all(self) -> None:
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and (item.flags() & Qt.ItemIsUserCheckable):
                item.setCheckState(Qt.Unchecked)

    def _quick_toggle_selected(self) -> None:
        selected = self.selected_packages()
        serial = self.current_serial()
        if not selected or not serial:
            return
        pkg_map = {p.name: p for p in self._all_packages}
        to_enable = [name for name in selected if pkg_map.get(name) and pkg_map[name].disabled]
        to_disable = [name for name in selected if pkg_map.get(name) and not pkg_map[name].disabled and not pkg_map[name].protected]
        if to_enable:
            self.enable_requested.emit(serial, to_enable)
        if to_disable:
            self.disable_requested.emit(serial, to_disable)

    def _enable_all_disabled(self) -> None:
        serial = self.current_serial()
        disabled = [p.name for p in self._all_packages if p.disabled]
        if serial and disabled:
            self.enable_requested.emit(serial, disabled)

    def _on_double_click_row(self, row: int, _col: int) -> None:
        item = self.table.item(row, 0)
        if not item: return
        pkg_name = str(item.data(Qt.UserRole))
        serial = self.current_serial()
        if not pkg_name or not serial: return
        pkg_map = {p.name: p for p in self._all_packages}
        pkg = pkg_map.get(pkg_name)
        if not pkg: return
        if pkg.disabled:
            self.enable_requested.emit(serial, [pkg_name])
        elif not pkg.protected:
            self.disable_requested.emit(serial, [pkg_name])

    def selected_packages(self) -> list[str]:
        selected: list[str] = []
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and item.checkState() == Qt.Checked:
                selected.append(str(item.data(Qt.UserRole)))
        return selected

    def _scan(self) -> None:
        self.scan_requested.emit(self.current_serial(), self.include_system.isChecked())
