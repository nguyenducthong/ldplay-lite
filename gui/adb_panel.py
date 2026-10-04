from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.adb import ADBDevice, ldplayer_index_from_serial
from core.instance import Instance


class ADBPanel(QWidget):
    refresh_requested = Signal()
    shell_requested = Signal(str, str)
    screenshot_requested = Signal(str)
    connect_requested = Signal(str)
    network_test_requested = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        title = QLabel("ADB Console")
        title.setObjectName("pageTitle")

        self.devices = QComboBox()
        refresh = QPushButton("Làm mới thiết bị")
        refresh.clicked.connect(self.refresh_requested.emit)
        self.endpoint = QLineEdit()
        self.endpoint.setPlaceholderText("127.0.0.1:5555")
        connect = QPushButton("Kết nối")
        connect.clicked.connect(lambda: self.connect_requested.emit(self.endpoint.text().strip()))

        device_row = QHBoxLayout()
        device_row.addWidget(QLabel("Thiết bị"))
        device_row.addWidget(self.devices, 1)
        device_row.addWidget(refresh)
        device_row.addSpacing(16)
        device_row.addWidget(self.endpoint)
        device_row.addWidget(connect)

        self.command = QLineEdit()
        self.command.setPlaceholderText("getprop, pm list packages, dumpsys meminfo…")
        self.command.returnPressed.connect(self._run_shell)
        run = QPushButton("Chạy lệnh")
        run.setObjectName("primaryButton")
        run.clicked.connect(self._run_shell)
        screenshot = QPushButton("Chụp màn hình")
        screenshot.clicked.connect(self._screenshot)
        network_test = QPushButton("Kiểm tra mạng")
        network_test.clicked.connect(
            lambda: self.network_test_requested.emit(self.current_serial())
        )
        command_row = QHBoxLayout()
        command_row.addWidget(self.command, 1)
        command_row.addWidget(run)
        command_row.addWidget(screenshot)
        command_row.addWidget(network_test)

        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setPlaceholderText("Kết quả ADB sẽ xuất hiện ở đây.")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(14)
        layout.addWidget(title)
        layout.addLayout(device_row)
        layout.addLayout(command_row)
        layout.addWidget(self.output, 1)

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

    def append_output(self, text: str) -> None:
        self.output.appendPlainText(text.rstrip())

    def _run_shell(self) -> None:
        self.shell_requested.emit(self.current_serial(), self.command.text())

    def _screenshot(self) -> None:
        self.screenshot_requested.emit(self.current_serial())
