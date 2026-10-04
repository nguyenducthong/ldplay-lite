from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
import traceback
from typing import Any

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, QTimer, Signal, Slot
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from core.adb import ADBManager
from core.detector import detect_ldplayer
from core.instance import Instance
from core.ldplayer import LDPlayerConsole
from core.optimizer import OptimizationProfile, Optimizer
from core.packages import PackageActionResult, PackageManager
from gui.adb_panel import ADBPanel
from gui.instance_panel import InstancePanel
from gui.optimizer_panel import OptimizerPanel
from gui.packages_panel import PackagesPanel
from gui.settings_panel import SettingsPanel
from utils.config import ConfigStore, load_profiles
from utils.logger import configure_logging
from utils.system import logs_dir, screenshots_dir


APP_STYLE = """
QWidget { background: #0f172a; color: #e2e8f0; font-family: "Segoe UI"; font-size: 13px; }
QMainWindow { background: #0f172a; }
QFrame#sidebar { background: #111827; border-right: 1px solid #263244; }
QLabel#brand { font-size: 19px; font-weight: 700; color: #f8fafc; padding: 8px 4px; }
QLabel#pageTitle { font-size: 24px; font-weight: 700; color: #f8fafc; }
QLabel#muted { color: #94a3b8; }
QLabel#warning { color: #fbbf24; background: #422006; border-radius: 7px; padding: 10px; }
QListWidget { background: transparent; border: 0; outline: 0; padding: 4px; }
QListWidget::item { padding: 11px 12px; margin: 2px 0; border-radius: 7px; color: #aebdd0; }
QListWidget::item:selected { background: #1e3a5f; color: #7dd3fc; }
QPushButton { background: #1e293b; border: 1px solid #334155; border-radius: 7px; padding: 8px 13px; }
QPushButton:hover { background: #27364c; }
QPushButton#primaryButton { background: #0284c7; border-color: #0ea5e9; color: white; font-weight: 600; }
QPushButton#primaryButton:hover { background: #0369a1; }
QPushButton#dangerButton { color: #fca5a5; }
QLineEdit, QComboBox, QSpinBox, QPlainTextEdit, QTableWidget {
  background: #111827; border: 1px solid #334155; border-radius: 6px; padding: 7px; selection-background-color: #0369a1;
}
QComboBox::drop-down { border: 0; }
QHeaderView::section { background: #1e293b; color: #cbd5e1; border: 0; border-bottom: 1px solid #334155; padding: 9px; }
QTableWidget { gridline-color: #263244; }
QTableWidget::item { padding: 6px; }
QStatusBar { background: #111827; color: #94a3b8; }
"""


class WorkerSignals(QObject):
    succeeded = Signal(object)
    failed = Signal(str)
    finished = Signal()


class Worker(QRunnable):
    def __init__(self, function: Callable[[], Any]):
        super().__init__()
        self.function = function
        self.signals = WorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            result = self.function()
            try:
                self.signals.succeeded.emit(result)
            except RuntimeError:
                return
        except Exception as exc:  # GUI boundary: display actionable error instead of crashing.
            details = "".join(traceback.format_exception_only(type(exc), exc)).strip()
            try:
                self.signals.failed.emit(details)
            except RuntimeError:
                return
        finally:
            try:
                self.signals.finished.emit()
            except RuntimeError:
                pass


class DashboardPanel(QWidget):
    refresh_requested = Signal()
    start_all_requested = Signal()
    stop_all_requested = Signal()
    optimize_all_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        title = QLabel("Tổng quan")
        title.setObjectName("pageTitle")
        self.ld_status = QLabel("LDPlayer: đang kiểm tra…")
        self.adb_status = QLabel("ADB: đang kiểm tra…")
        self.instance_count = QLabel("Instances: —")
        self.running_count = QLabel("Đang chạy: —")
        for widget in (self.ld_status, self.adb_status, self.instance_count, self.running_count):
            widget.setStyleSheet("font-size: 16px; padding: 5px;")

        actions = QHBoxLayout()
        for label, signal, primary in (
            ("Khởi động tất cả", self.start_all_requested, True),
            ("Dừng tất cả", self.stop_all_requested, False),
            ("Tối ưu tất cả", self.optimize_all_requested, False),
            ("Làm mới", self.refresh_requested, False),
        ):
            button = QPushButton(label)
            if primary:
                button.setObjectName("primaryButton")
            button.clicked.connect(signal.emit)
            actions.addWidget(button)
        actions.addStretch()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(12)
        layout.addWidget(title)
        layout.addSpacing(12)
        layout.addWidget(self.ld_status)
        layout.addWidget(self.adb_status)
        layout.addSpacing(12)
        layout.addWidget(self.instance_count)
        layout.addWidget(self.running_count)
        layout.addSpacing(20)
        layout.addLayout(actions)
        layout.addStretch()

    def set_installation(self, ld_ready: bool, adb_ready: bool) -> None:
        self.ld_status.setText(f"LDPlayer: {'✓ Sẵn sàng' if ld_ready else '✕ Chưa phát hiện'}")
        self.adb_status.setText(f"ADB: {'✓ Sẵn sàng' if adb_ready else '✕ Chưa phát hiện'}")

    def set_instances(self, instances: list[Instance]) -> None:
        self.instance_count.setText(f"Instances: {len(instances)}")
        self.running_count.setText(f"Đang chạy: {sum(item.running for item in instances)}")


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("LDPlayer Lite Manager")
        self.resize(1080, 700)
        self.setMinimumSize(900, 600)
        self.config = ConfigStore()
        self.logger = configure_logging(logs_dir())
        self.console: LDPlayerConsole | None = None
        self.adb: ADBManager | None = None
        self.optimizer: Optimizer | None = None
        self.package_manager: PackageManager | None = None
        self.instances: list[Instance] = []
        self.pool = QThreadPool.globalInstance()
        self._workers: set[Worker] = set()

        self.dashboard = DashboardPanel()
        self.instance_panel = InstancePanel()
        self.optimizer_panel = OptimizerPanel(load_profiles())
        self.optimizer_panel.profile.setCurrentText(
            str(self.config.data.get("default_profile", "Lite"))
        )
        saved_profile = self.config.data.get("last_optimization_profile", {})
        if isinstance(saved_profile, dict) and saved_profile:
            try:
                self.optimizer_panel.set_profile(OptimizationProfile.from_dict(saved_profile))
            except (TypeError, ValueError):
                pass
        self.adb_panel = ADBPanel()
        self.packages_panel = PackagesPanel()
        self.settings_panel = SettingsPanel(self.config.data)
        self.pages = QStackedWidget()
        for page in (
            self.dashboard,
            self.instance_panel,
            self.optimizer_panel,
            self.adb_panel,
            self.packages_panel,
            self.settings_panel,
        ):
            self.pages.addWidget(page)

        self.navigation = QListWidget()
        for label in ("Tổng quan", "Instances", "Tối ưu", "ADB", "Ứng dụng", "Cài đặt"):
            self.navigation.addItem(QListWidgetItem(label))
        self.navigation.setCurrentRow(0)
        self.navigation.currentRowChanged.connect(self.pages.setCurrentIndex)

        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(205)
        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(14, 18, 14, 18)
        brand = QLabel("LDPlayer Lite")
        brand.setObjectName("brand")
        version = QLabel("Manager · MVP")
        version.setObjectName("muted")
        side_layout.addWidget(brand)
        side_layout.addWidget(version)
        side_layout.addSpacing(18)
        side_layout.addWidget(self.navigation, 1)

        root = QWidget()
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(sidebar)
        root_layout.addWidget(self.pages, 1)
        self.setCentralWidget(root)
        self.setStyleSheet(APP_STYLE)
        self.statusBar().showMessage("Sẵn sàng")
        self._connect_signals()
        self._profile_save_timer = QTimer(self)
        self._profile_save_timer.setSingleShot(True)
        self._profile_save_timer.setInterval(300)
        self._profile_save_timer.timeout.connect(self._save_optimization_settings)
        self.optimizer_panel.settings_changed.connect(
            lambda: self._profile_save_timer.start()
        )
        self._configure_services()

    def _connect_signals(self) -> None:
        self.dashboard.refresh_requested.connect(self.refresh_all)
        self.dashboard.start_all_requested.connect(self.start_all)
        self.dashboard.stop_all_requested.connect(self.stop_all)
        self.dashboard.optimize_all_requested.connect(
            lambda: self.apply_profile([], self.optimizer_panel.current_profile(), all_instances=True)
        )
        self.instance_panel.refresh_requested.connect(self.refresh_instances)
        self.instance_panel.action_requested.connect(self.instance_action)
        self.instance_panel.create_requested.connect(self.create_instance)
        self.instance_panel.clone_requested.connect(self.clone_instance)
        self.instance_panel.rename_requested.connect(self.rename_instance)
        self.optimizer_panel.apply_selected_requested.connect(
            lambda profile: self.apply_profile(self.instance_panel.selected_indices(), profile)
        )
        self.optimizer_panel.apply_all_requested.connect(
            lambda profile: self.apply_profile([], profile, all_instances=True)
        )
        self.optimizer_panel.restore_requested.connect(self.restore_backup)
        self.adb_panel.refresh_requested.connect(self.refresh_devices)
        self.adb_panel.shell_requested.connect(self.run_shell)
        self.adb_panel.screenshot_requested.connect(self.capture_screenshot)
        self.adb_panel.connect_requested.connect(self.connect_adb)
        self.adb_panel.network_test_requested.connect(self.test_network)
        self.packages_panel.scan_requested.connect(self.scan_packages)
        self.packages_panel.disable_requested.connect(self.disable_packages)
        self.packages_panel.enable_requested.connect(self.enable_packages)
        self.packages_panel.restore_requested.connect(self.restore_packages)
        self.packages_panel.analyze_requested.connect(self.analyze_target_packages)
        self.settings_panel.save_requested.connect(self.save_settings)
        self.settings_panel.detect_requested.connect(self.detect)

    def _configure_services(self) -> None:
        console_path = Path(str(self.config.data.get("console_path", "")))
        adb_path = Path(str(self.config.data.get("adb_path", "")))
        self.console = LDPlayerConsole(console_path) if console_path.is_file() else None
        self.adb = (
            ADBManager(adb_path, timeout=int(self.config.data.get("adb_timeout", 30)))
            if adb_path.is_file()
            else None
        )
        self.optimizer = Optimizer(self.console, self.adb) if self.console else None
        self.package_manager = PackageManager(self.adb) if self.adb else None
        self.dashboard.set_installation(self.console is not None, self.adb is not None)
        if self.console:
            self.refresh_all()
        else:
            self.detect()

    def _run_async(
        self,
        message: str,
        function: Callable[[], Any],
        on_success: Callable[[Any], None] | None = None,
    ) -> None:
        self.statusBar().showMessage(message)
        worker = Worker(function)
        self._workers.add(worker)
        if on_success:
            worker.signals.succeeded.connect(on_success)
        worker.signals.failed.connect(self._show_error)
        worker.signals.finished.connect(lambda: self._finish_worker(worker))
        self.pool.start(worker)

    def _finish_worker(self, worker: Worker) -> None:
        self._workers.discard(worker)
        self.statusBar().showMessage("Sẵn sàng", 3000)

    def _show_error(self, message: str) -> None:
        self.logger.error(message)
        QMessageBox.critical(self, "Không thể thực hiện", message)

    def detect(self) -> None:
        manual = self.settings_panel.console.edit.text().strip() or None

        def done(installation: Any) -> None:
            if not installation:
                self.dashboard.set_installation(False, False)
                self.statusBar().showMessage("Chưa tìm thấy LDPlayer. Hãy chọn đường dẫn trong Cài đặt.", 8000)
                return
            adb = str(installation.adb or "")
            self.config.update(
                ldplayer_path=str(installation.root),
                console_path=str(installation.console),
                adb_path=adb,
            )
            self.settings_panel.set_paths(str(installation.console), adb)
            self._configure_services()

        self._run_async("Đang phát hiện LDPlayer…", lambda: detect_ldplayer(manual), done)

    def refresh_all(self) -> None:
        self.refresh_instances()
        if self.adb:
            self.refresh_devices()

    def refresh_instances(self) -> None:
        if not self.console:
            return

        def done(instances: list[Instance]) -> None:
            self.instances = instances
            self.instance_panel.set_instances(instances)
            self.dashboard.set_instances(instances)

        self._run_async("Đang đọc danh sách instance…", self.console.list_instances, done)

    def refresh_devices(self) -> None:
        if not self.adb:
            self._show_error("ADB chưa được cấu hình.")
            return
        def done(devices: list[Any]) -> None:
            self.adb_panel.set_devices(devices)
            self.packages_panel.set_devices(devices)

        self._run_async("Đang đọc thiết bị ADB…", self.adb.devices, done)

    def instance_action(self, action: str, indices: list[int]) -> None:
        if not self.console:
            self._show_error("LDConsole chưa được cấu hình.")
            return
        if not indices:
            self._show_error("Hãy chọn ít nhất một instance.")
            return
        if action == "delete":
            answer = QMessageBox.question(
                self,
                "Xóa instance",
                f"Xóa vĩnh viễn {len(indices)} instance đã chọn?",
            )
            if answer != QMessageBox.Yes:
                return

        if action in ("start", "restart"):
            self._start_optimized(indices, restart=action == "restart")
            return

        operations = {"stop": self.console.stop, "delete": self.console.delete}

        def execute() -> None:
            for index in indices:
                operations[action](index)

        self._run_async(f"Đang thực hiện trên {len(indices)} instance…", execute, lambda _: self.refresh_instances())

    def create_instance(self) -> None:
        if not self.console:
            self._show_error("LDConsole chưa được cấu hình.")
            return
        name, ok = QInputDialog.getText(self, "Tạo instance", "Tên instance")
        if ok and name.strip():
            self._run_async("Đang tạo instance…", lambda: self.console.create(name.strip()), lambda _: self.refresh_instances())

    def clone_instance(self, source: int) -> None:
        if not self.console:
            return
        name, ok = QInputDialog.getText(self, "Nhân bản instance", "Tên instance mới")
        if ok and name.strip():
            self._run_async(
                "Đang nhân bản instance…",
                lambda: self.console.clone(source, name.strip()),
                lambda _: self.refresh_instances(),
            )

    def rename_instance(self, index: int) -> None:
        if not self.console:
            return
        current = next((item.name for item in self.instances if item.index == index), "")
        name, ok = QInputDialog.getText(self, "Đổi tên instance", "Tên mới", text=current)
        if ok and name.strip():
            self._run_async(
                "Đang đổi tên…",
                lambda: self.console.rename(index, name.strip()),
                lambda _: self.refresh_instances(),
            )

    def start_all(self) -> None:
        if not self.console:
            self._show_error("LDConsole chưa được cấu hình.")
            return
        indices = [item.index for item in self.instances if not item.running]
        if not indices:
            self.statusBar().showMessage("Tất cả instance đã chạy.", 4000)
            return
        self._start_optimized(indices)

    def _start_optimized(self, indices: list[int], *, restart: bool = False) -> None:
        if not self.console or not self.optimizer:
            self._show_error("Bộ tối ưu chưa sẵn sàng.")
            return
        profile = self.optimizer_panel.current_profile()
        delay = int(self.config.data.get("startup_delay", 5))

        def execute() -> tuple[dict[int, float], list[str]]:
            warnings = self.optimizer.configure_multi_instance(profile)
            targets = indices
            if restart:
                for index in targets:
                    instance = next((item for item in self.console.list_instances() if item.index == index), None)
                    if instance and instance.running:
                        self.console.stop(index)
                        self.console.wait_for_state(index, running=False, timeout=45)
            else:
                running = {item.index for item in self.console.list_instances() if item.running}
                targets = [index for index in targets if index not in running]
            times = self.console.start_sequential(
                targets,
                delay,
                after_start=lambda instance: warnings.extend(
                    self.optimizer.apply_runtime(instance, profile)
                ),
            )
            return times, warnings

        def done(result: tuple[dict[int, float], list[str]]) -> None:
            times, warnings = result
            self.refresh_instances()
            if times:
                average = sum(times.values()) / len(times)
                message = f"Đã khởi động {len(times)} instance, trung bình {average:.1f} giây."
            else:
                message = "Các instance đã được khởi động từ trước."
            if warnings:
                message += "\n\n" + "\n".join(warnings[:5])
            QMessageBox.information(self, "Khởi động tối ưu", message)

        self._run_async(f"Đang khởi động tối ưu {len(indices)} instance…", execute, done)

    def stop_all(self) -> None:
        if not self.console:
            self._show_error("LDConsole chưa được cấu hình.")
            return
        self._run_async("Đang dừng tất cả instance…", self.console.stop_all, lambda _: self.refresh_instances())

    def apply_profile(
        self,
        indices: list[int],
        profile: OptimizationProfile,
        *,
        all_instances: bool = False,
    ) -> None:
        if not self.optimizer:
            self._show_error("LDConsole chưa được cấu hình.")
            return
        targets = [item.index for item in self.instances] if all_instances else indices
        if not targets:
            self._show_error("Hãy chọn ít nhất một instance.")
            return

        def execute() -> list[Any]:
            results: list[Any] = []
            for position, index in enumerate(targets):
                results.append(
                    self.optimizer.apply(
                        index,
                        profile,
                        restart_running=True,
                        configure_global=position == 0,
                    )
                )
            return results

        def done(results: list[Any]) -> None:
            self.refresh_instances()
            warnings = [warning for result in results for warning in result.warnings]
            message = (
                f"Đã áp dụng profile cho {len(targets)} instance.\n"
                f"Đã tạo {len(results)} bản sao lưu. Instance đang chạy đã được khởi động lại."
            )
            if warnings:
                message += "\n\nLưu ý:\n" + "\n".join(warnings[:5])
            QMessageBox.information(
                self,
                "Đã tối ưu",
                message,
            )

        self._run_async(f"Đang tối ưu {len(targets)} instance…", execute, done)

    def run_shell(self, serial: str, command: str) -> None:
        if not self.adb or not serial:
            self._show_error("Hãy chọn một thiết bị ADB đang kết nối.")
            return
        self.adb_panel.append_output(f"> {command}")
        self._run_async(
            "Đang chạy lệnh ADB…",
            lambda: self.adb.shell(serial, command),
            self.adb_panel.append_output,
        )

    def capture_screenshot(self, serial: str) -> None:
        if not self.adb or not serial:
            self._show_error("Hãy chọn một thiết bị ADB đang kết nối.")
            return
        configured = str(self.config.data.get("screenshot_directory", "")).strip()
        destination = None
        if configured:
            from datetime import datetime

            destination = Path(configured) / f"{serial.replace(':', '_')}_{datetime.now():%Y%m%d_%H%M%S}.png"
        self._run_async(
            "Đang chụp màn hình…",
            lambda: self.adb.screenshot(serial, destination),
            lambda path: self.adb_panel.append_output(f"Đã lưu ảnh: {path}"),
        )

    def test_network(self, serial: str) -> None:
        if not self.adb or not serial:
            self._show_error("Hãy chọn một thiết bị ADB đang kết nối.")
            return
        self.adb_panel.append_output("\n=== Kiểm tra mạng LDPlayer ===")
        self._run_async(
            "Đang kiểm tra DNS, route và độ trễ mạng…",
            lambda: self.adb.network_diagnostics(serial),
            self.adb_panel.append_output,
        )

    def scan_packages(self, serial: str, include_system: bool) -> None:
        if not self.package_manager or not serial:
            self._show_error("Hãy kết nối và chọn một thiết bị ADB.")
            return
        self._run_async(
            "Đang quét ứng dụng Android…",
            lambda: self.package_manager.scan(serial, include_system=include_system),
            self.packages_panel.set_packages,
        )

    def analyze_target_packages(self, serial: str, target: str) -> None:
        if not self.package_manager or not serial:
            self._show_error("Hãy kết nối và chọn một thiết bị ADB.")
            return
        self._run_async(
            f"Đang phân tích package cần cho {target}…",
            lambda: self.package_manager.analyze_for_target(serial, target),
            self.packages_panel.set_packages,
        )

    def disable_packages(self, serial: str, packages: list[str]) -> None:
        if not self.package_manager or not serial or not packages:
            self._show_error("Hãy chọn ít nhất một package trên thiết bị ADB.")
            return
        answer = QMessageBox.question(
            self,
            "Vô hiệu hóa ứng dụng",
            f"Vô hiệu hóa {len(packages)} package đã chọn? Trạng thái hiện tại sẽ được sao lưu.",
        )
        if answer != QMessageBox.Yes:
            return
        self._run_package_action(
            serial,
            lambda: self.package_manager.disable(serial, packages),
            "Đang vô hiệu hóa ứng dụng…",
        )

    def enable_packages(self, serial: str, packages: list[str]) -> None:
        if not self.package_manager or not serial or not packages:
            self._show_error("Hãy chọn ít nhất một package trên thiết bị ADB.")
            return
        self._run_package_action(
            serial,
            lambda: self.package_manager.enable(serial, packages),
            "Đang bật lại ứng dụng…",
        )

    def _run_package_action(
        self,
        serial: str,
        action: Callable[[], PackageActionResult],
        message: str,
    ) -> None:
        def done(result: PackageActionResult) -> None:
            summary = f"Đã thay đổi {len(result.changed)} package.\nBackup: {result.backup}"
            if result.failed:
                summary += f"\nKhông thể thay đổi {len(result.failed)} package."
            QMessageBox.information(self, "Ứng dụng Android", summary)
            self.scan_packages(serial, self.packages_panel.include_system.isChecked())

        self._run_async(message, action, done)

    def restore_packages(self) -> None:
        if not self.package_manager:
            self._show_error("ADB chưa được cấu hình.")
            return
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Chọn backup trạng thái package",
            filter="JSON (*.json)",
        )
        if not path:
            return

        def done(result: PackageActionResult) -> None:
            QMessageBox.information(
                self,
                "Đã khôi phục",
                f"Đã khôi phục trạng thái của {len(result.changed)} package.",
            )
            self.refresh_devices()

        self._run_async(
            "Đang khôi phục trạng thái ứng dụng…",
            lambda: self.package_manager.restore(path),
            done,
        )

    def restore_backup(self) -> None:
        if not self.optimizer:
            self._show_error("LDConsole chưa được cấu hình.")
            return
        folder = QFileDialog.getExistingDirectory(self, "Chọn thư mục backup")
        if not folder:
            return
        self._run_async(
            "Đang khôi phục cấu hình…",
            lambda: self.optimizer.restore(folder),
            lambda _: (
                self.refresh_instances(),
                QMessageBox.information(self, "Đã khôi phục", "Cấu hình instance đã được khôi phục."),
            ),
        )

    def connect_adb(self, endpoint: str) -> None:
        if not self.adb or not endpoint:
            self._show_error("Nhập địa chỉ ADB, ví dụ 127.0.0.1:5555.")
            return
        self._run_async(
            "Đang kết nối ADB…",
            lambda: self.adb.connect(endpoint),
            lambda output: (self.adb_panel.append_output(output), self.refresh_devices()),
        )

    def save_settings(self, values: dict) -> None:
        self.config.update(**values)
        self._configure_services()
        self.statusBar().showMessage("Đã lưu cài đặt.", 5000)

    def _save_optimization_settings(self) -> None:
        profile = self.optimizer_panel.current_profile()
        self.config.update(
            default_profile=self.optimizer_panel.profile.currentText(),
            last_optimization_profile={
                "cpu": profile.cpu,
                "ram": profile.ram,
                "width": profile.width,
                "height": profile.height,
                "dpi": profile.dpi,
                "fps": profile.fps,
                "animation": profile.animation,
                "audio": profile.audio,
                "memory_optimization": profile.memory_optimization,
                "process_priority": profile.process_priority,
            },
        )

    def closeEvent(self, event: Any) -> None:
        self._save_optimization_settings()
        self.pool.waitForDone(1000)
        super().closeEvent(event)


def run_gui() -> int:
    app = QApplication.instance() or QApplication([])
    app.setApplicationName("LDPlayer Lite Manager")
    window = MainWindow()
    window.show()
    return app.exec()
