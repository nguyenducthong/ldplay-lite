from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


class PathRow(QWidget):
    def __init__(self, value: str, *, executable: bool = True) -> None:
        super().__init__()
        self.edit = QLineEdit(value)
        button = QPushButton("Chọn…")
        button.clicked.connect(lambda: self._browse(executable))
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.edit, 1)
        layout.addWidget(button)

    def _browse(self, executable: bool) -> None:
        if executable:
            value, _ = QFileDialog.getOpenFileName(self, "Chọn tệp", filter="Executable (*.exe);;Tất cả (*)")
        else:
            value = QFileDialog.getExistingDirectory(self, "Chọn thư mục")
        if value:
            self.edit.setText(value)


class SettingsPanel(QWidget):
    save_requested = Signal(dict)
    detect_requested = Signal()

    def __init__(self, config: dict) -> None:
        super().__init__()
        title = QLabel("Cài đặt")
        title.setObjectName("pageTitle")
        self.console = PathRow(str(config.get("console_path", "")))
        self.adb = PathRow(str(config.get("adb_path", "")))
        self.screenshots = PathRow(str(config.get("screenshot_directory", "")), executable=False)
        self.delay = QSpinBox()
        self.delay.setRange(0, 120)
        self.delay.setValue(int(config.get("startup_delay", 10)))
        self.timeout = QSpinBox()
        self.timeout.setRange(5, 300)
        self.timeout.setValue(int(config.get("adb_timeout", 30)))

        form = QFormLayout()
        form.setSpacing(14)
        form.addRow("LDConsole", self.console)
        form.addRow("ADB", self.adb)
        form.addRow("Thư mục ảnh", self.screenshots)
        form.addRow("Trễ khởi động (giây)", self.delay)
        form.addRow("ADB timeout (giây)", self.timeout)

        detect = QPushButton("Tự động phát hiện")
        detect.clicked.connect(self.detect_requested.emit)
        save = QPushButton("Lưu cài đặt")
        save.setObjectName("primaryButton")
        save.clicked.connect(self._save)
        actions = QHBoxLayout()
        actions.addWidget(save)
        actions.addWidget(detect)
        actions.addStretch()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(14)
        layout.addWidget(title)
        layout.addLayout(form)
        layout.addLayout(actions)
        layout.addStretch()

    def set_paths(self, console: str, adb: str) -> None:
        self.console.edit.setText(console)
        self.adb.edit.setText(adb)

    def _save(self) -> None:
        self.save_requested.emit(
            {
                "console_path": self.console.edit.text().strip(),
                "adb_path": self.adb.edit.text().strip(),
                "screenshot_directory": self.screenshots.edit.text().strip(),
                "startup_delay": self.delay.value(),
                "adb_timeout": self.timeout.value(),
            }
        )
