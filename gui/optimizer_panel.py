from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from core.optimizer import OptimizationProfile


class OptimizerPanel(QWidget):
    apply_selected_requested = Signal(object)
    apply_all_requested = Signal(object)
    restore_requested = Signal()

    def __init__(self, profiles: dict[str, dict]) -> None:
        super().__init__()
        self.profiles = profiles
        title = QLabel("Tối ưu hiệu năng")
        title.setObjectName("pageTitle")
        warning = QLabel("RAM quá thấp có thể khiến Android hoặc ứng dụng bị hệ thống đóng.")
        warning.setObjectName("warning")

        self.profile = QComboBox()
        self.profile.addItems(profiles.keys())
        self.cpu = QSpinBox()
        self.cpu.setRange(1, 16)
        self.ram = QComboBox()
        self.ram.addItems(("512", "768", "1024", "1536", "2048", "4096", "8192"))
        self.width = QSpinBox()
        self.width.setRange(240, 3840)
        self.height = QSpinBox()
        self.height.setRange(240, 3840)
        self.dpi = QSpinBox()
        self.dpi.setRange(80, 640)
        self.fps = QComboBox()
        self.fps.addItems(("15", "20", "30", "60"))
        self.animations = QCheckBox("Giữ hiệu ứng Android")

        form = QFormLayout()
        form.setSpacing(14)
        form.addRow("Profile", self.profile)
        form.addRow("CPU (core)", self.cpu)
        form.addRow("RAM (MB)", self.ram)
        form.addRow("Chiều rộng", self.width)
        form.addRow("Chiều cao", self.height)
        form.addRow("DPI", self.dpi)
        form.addRow("FPS", self.fps)
        form.addRow("", self.animations)

        apply_selected = QPushButton("Áp dụng cho instance đã chọn")
        apply_selected.setObjectName("primaryButton")
        apply_selected.clicked.connect(lambda: self.apply_selected_requested.emit(self.current_profile()))
        apply_all = QPushButton("Tối ưu tất cả")
        apply_all.clicked.connect(lambda: self.apply_all_requested.emit(self.current_profile()))
        restore = QPushButton("Khôi phục backup…")
        restore.clicked.connect(self.restore_requested.emit)
        actions = QHBoxLayout()
        actions.addWidget(apply_selected)
        actions.addWidget(apply_all)
        actions.addWidget(restore)
        actions.addStretch()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(14)
        layout.addWidget(title)
        layout.addWidget(warning)
        layout.addLayout(form)
        layout.addLayout(actions)
        layout.addStretch()

        self.profile.currentTextChanged.connect(self._load_profile)
        if profiles:
            self._load_profile(self.profile.currentText())

    def _load_profile(self, name: str) -> None:
        values = self.profiles.get(name, {})
        try:
            profile = OptimizationProfile.from_dict(values)
        except (ValueError, TypeError):
            return
        self.cpu.setValue(profile.cpu)
        self.ram.setCurrentText(str(profile.ram))
        self.width.setValue(profile.width)
        self.height.setValue(profile.height)
        self.dpi.setValue(profile.dpi)
        self.fps.setCurrentText(str(profile.fps))
        self.animations.setChecked(profile.animation)

    def current_profile(self) -> OptimizationProfile:
        return OptimizationProfile(
            cpu=self.cpu.value(),
            ram=int(self.ram.currentText()),
            width=self.width.value(),
            height=self.height.value(),
            dpi=self.dpi.value(),
            fps=int(self.fps.currentText()),
            animation=self.animations.isChecked(),
        )
