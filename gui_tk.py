from __future__ import annotations

import threading
import tkinter as tk
import ctypes
from tkinter import filedialog, messagebox, ttk
from pathlib import Path
from typing import Any, Callable

from core.adb import ADBDevice, ADBManager, ldplayer_index_from_serial
from core.detector import detect_ldplayer
from core.instance import Instance
from core.ldplayer import LDPlayerConsole
from core.optimizer import OptimizationProfile, Optimizer
from core.packages import AndroidPackage, PackageManager
from utils.config import ConfigStore, load_profiles
from utils.logger import configure_logging
from utils.system import logs_dir


class CompatApp(tk.Tk):
    BG = "#070b10"
    SURFACE = "#0d141c"
    CARD = "#131d27"
    CARD_HOVER = "#192633"
    BORDER = "#243342"
    TEXT = "#edf4fa"
    MUTED = "#8fa3b7"
    ACCENT = "#22b8f0"
    ACCENT_HOVER = "#0899d0"
    SUCCESS = "#36d399"
    DANGER = "#fb7185"

    def __init__(self) -> None:
        super().__init__()
        self.title("LDPlayer Lite Manager — Compatibility")
        self.geometry("1120x760")
        self.minsize(940, 640)
        self.configure(background=self.BG)
        self.option_add("*Font", ("Segoe UI", 10))
        self.config_store = ConfigStore()
        self.logger = configure_logging(logs_dir())
        self.profiles = load_profiles()
        self.console: LDPlayerConsole | None = None
        self.adb: ADBManager | None = None
        self.optimizer: Optimizer | None = None
        self.package_manager: PackageManager | None = None
        self.instances: list[Instance] = []
        self.adb_devices: list[ADBDevice] = []
        self.device_serials_by_name: dict[str, str] = {}
        self.package_suggestions: list[str] = []

        self._configure_style()
        self._build_ui()
        self._load_saved_profile()
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.after(0, self._enable_dark_title_bar)
        self.after(100, self._configure_services)

    def _configure_style(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")

        style.configure("TFrame", background=self.SURFACE)
        style.configure("Root.TFrame", background=self.BG)
        style.configure("Header.TFrame", background=self.BG)
        style.configure("Page.TFrame", background=self.SURFACE)
        style.configure("Card.TFrame", background=self.CARD, relief="flat")
        style.configure("Actions.TFrame", background=self.SURFACE)
        style.configure("Sidebar.TFrame", background="#090f16")

        style.configure("TLabel", background=self.SURFACE, foreground=self.TEXT)
        style.configure("HeaderTitle.TLabel", background=self.BG, foreground=self.TEXT, font=("Segoe UI", 20, "bold"))
        style.configure("HeaderSub.TLabel", background=self.BG, foreground=self.MUTED, font=("Segoe UI", 9))
        style.configure("Title.TLabel", background=self.SURFACE, foreground=self.TEXT, font=("Segoe UI", 18, "bold"))
        style.configure("Subtitle.TLabel", background=self.SURFACE, foreground=self.MUTED, font=("Segoe UI", 10))
        style.configure("Section.TLabel", background=self.SURFACE, foreground=self.TEXT, font=("Segoe UI", 12, "bold"))
        style.configure("Muted.TLabel", background=self.SURFACE, foreground=self.MUTED)
        style.configure("CardTitle.TLabel", background=self.CARD, foreground=self.MUTED, font=("Segoe UI", 9, "bold"))
        style.configure("CardValue.TLabel", background=self.CARD, foreground=self.TEXT, font=("Segoe UI", 13, "bold"))
        style.configure("Field.TLabel", background=self.CARD, foreground=self.TEXT)
        style.configure("Status.TLabel", background=self.CARD, foreground=self.SUCCESS, padding=(12, 7), font=("Segoe UI", 9, "bold"))
        style.configure("SidebarTitle.TLabel", background="#090f16", foreground=self.MUTED,
                        font=("Segoe UI", 9, "bold"))
        style.configure("SidebarFoot.TLabel", background="#090f16", foreground="#5f7488",
                        font=("Segoe UI", 8))

        style.configure("TButton", background=self.CARD, foreground=self.TEXT, bordercolor=self.BORDER,
                        lightcolor=self.CARD, darkcolor=self.CARD, padding=(13, 8), relief="flat")
        style.map("TButton", background=[("active", self.CARD_HOVER), ("pressed", self.BORDER)],
                  foreground=[("disabled", "#526273")])
        style.configure("Primary.TButton", background=self.ACCENT, foreground="#03131b",
                        bordercolor=self.ACCENT, lightcolor=self.ACCENT, darkcolor=self.ACCENT,
                        font=("Segoe UI", 10, "bold"), padding=(15, 9))
        style.map("Primary.TButton", background=[("active", self.ACCENT_HOVER), ("pressed", "#087ca8")])
        style.configure("Danger.TButton", foreground=self.DANGER)
        style.configure("Nav.TButton", background="#090f16", foreground=self.MUTED, borderwidth=0,
                        bordercolor="#090f16", lightcolor="#090f16", darkcolor="#090f16",
                        anchor="w", padding=(16, 12), font=("Segoe UI", 10, "bold"))
        style.map("Nav.TButton", background=[("active", self.CARD)], foreground=[("active", self.TEXT)])
        style.configure("NavActive.TButton", background=self.CARD, foreground=self.ACCENT, borderwidth=0,
                        bordercolor=self.CARD, lightcolor=self.CARD, darkcolor=self.CARD,
                        anchor="w", padding=(16, 12), font=("Segoe UI", 10, "bold"))
        style.map("NavActive.TButton", background=[("active", self.CARD_HOVER)],
                  foreground=[("active", self.ACCENT)])

        style.configure("TNotebook", background=self.BG, borderwidth=0, tabmargins=(0, 0, 0, 0),
                        bordercolor=self.SURFACE, lightcolor=self.SURFACE, darkcolor=self.SURFACE)
        style.layout("Sidebar.TNotebook", [("Notebook.client", {"sticky": "nswe"})])
        style.layout("Sidebar.TNotebook.Tab", [])
        style.configure("Sidebar.TNotebook", background=self.SURFACE, borderwidth=0,
                        bordercolor=self.SURFACE, lightcolor=self.SURFACE, darkcolor=self.SURFACE)
        style.configure("TNotebook.Tab", background=self.BG, foreground=self.MUTED, borderwidth=0,
                        bordercolor=self.BG, lightcolor=self.BG, darkcolor=self.BG,
                        focuscolor=self.BG, relief="flat", padding=(18, 11), font=("Segoe UI", 10, "bold"))
        style.map("TNotebook.Tab", background=[("selected", self.SURFACE), ("active", self.CARD)],
                  foreground=[("selected", self.ACCENT), ("active", self.TEXT)],
                  bordercolor=[("selected", self.SURFACE), ("active", self.CARD), ("!selected", self.BG)],
                  lightcolor=[("selected", self.SURFACE), ("active", self.CARD), ("!selected", self.BG)],
                  darkcolor=[("selected", self.SURFACE), ("active", self.CARD), ("!selected", self.BG)])

        style.configure("Treeview", background=self.CARD, fieldbackground=self.CARD, foreground=self.TEXT,
                        bordercolor=self.BORDER, lightcolor=self.BORDER, darkcolor=self.BORDER,
                        rowheight=32, relief="flat")
        style.configure("Treeview.Heading", background=self.BORDER, foreground=self.TEXT, borderwidth=0,
                        font=("Segoe UI", 9, "bold"), padding=(8, 8))
        style.map("Treeview", background=[("selected", "#0d6684")], foreground=[("selected", "#ffffff")])
        style.map("Treeview.Heading", background=[("active", self.CARD_HOVER)])

        for widget in ("TEntry", "TCombobox", "TSpinbox"):
            style.configure(widget, fieldbackground="#0a1017", background="#0a1017", foreground=self.TEXT,
                            bordercolor=self.BORDER, lightcolor=self.BORDER, darkcolor=self.BORDER,
                            arrowcolor=self.MUTED, insertcolor=self.TEXT, padding=7)
            style.map(widget, bordercolor=[("focus", self.ACCENT)], lightcolor=[("focus", self.ACCENT)],
                      darkcolor=[("focus", self.ACCENT)])
        style.map("TCombobox", fieldbackground=[("readonly", "#0a1017")],
                  foreground=[("readonly", self.TEXT)], selectbackground=[("readonly", "#0a1017")])
        style.configure("TCheckbutton", background=self.SURFACE, foreground=self.TEXT, padding=(0, 5))
        style.map("TCheckbutton", background=[("active", self.SURFACE)], foreground=[("active", self.TEXT)],
                  indicatorcolor=[("selected", self.ACCENT), ("!selected", "#0a1017")])
        style.configure("Card.TCheckbutton", background=self.CARD, foreground=self.TEXT, padding=(0, 5))
        style.map("Card.TCheckbutton", background=[("active", self.CARD)], foreground=[("active", self.TEXT)],
                  indicatorcolor=[("selected", self.ACCENT), ("!selected", "#0a1017")])
        style.configure("TSeparator", background=self.BORDER)

        self.option_add("*TCombobox*Listbox.background", self.CARD)
        self.option_add("*TCombobox*Listbox.foreground", self.TEXT)
        self.option_add("*TCombobox*Listbox.selectBackground", "#0d6684")
        self.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")

    def _enable_dark_title_bar(self) -> None:
        """Ask Windows 10/11 to render the native title bar in dark mode."""
        try:
            self.update_idletasks()
            window = ctypes.windll.user32.GetParent(self.winfo_id())
            enabled = ctypes.c_int(1)
            for attribute in (20, 19):
                result = ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    window, attribute, ctypes.byref(enabled), ctypes.sizeof(enabled)
                )
                if result == 0:
                    break
        except (AttributeError, OSError):
            pass

    def _build_ui(self) -> None:
        header = ttk.Frame(self, padding=(22, 16, 22, 12), style="Header.TFrame")
        header.pack(fill="x")
        brand = ttk.Frame(header, style="Header.TFrame")
        brand.pack(side="left")
        ttk.Label(brand, text="LDPlayer Lite Manager", style="HeaderTitle.TLabel").pack(anchor="w")
        ttk.Label(brand, text="Tối ưu LDPlayer cho vn.kvtm.js  ·  Compatibility Edition",
                  style="HeaderSub.TLabel").pack(anchor="w", pady=(2, 0))
        self.status = tk.StringVar(value="Sẵn sàng")
        ttk.Label(header, textvariable=self.status, style="Status.TLabel").pack(side="right")

        body = ttk.Frame(self, style="Root.TFrame")
        body.pack(fill="both", expand=True, padx=18, pady=(0, 18))
        self.sidebar = ttk.Frame(body, width=184, padding=(0, 16), style="Sidebar.TFrame")
        self.sidebar.pack(side="left", fill="y", padx=(0, 10))
        self.sidebar.pack_propagate(False)
        ttk.Label(self.sidebar, text="MENU", style="SidebarTitle.TLabel").pack(anchor="w", padx=16, pady=(0, 9))
        self.nav_buttons: list[ttk.Button] = []
        self.tabs = ttk.Notebook(body, style="Sidebar.TNotebook")
        self.tabs.pack(side="left", fill="both", expand=True)
        self._build_dashboard()
        self._build_instances()
        self._build_optimizer()
        self._build_adb()
        self._build_packages()
        self._build_settings()
        ttk.Label(self.sidebar, text="COMPATIBILITY EDITION\nKhông sử dụng Qt", justify="left",
                  style="SidebarFoot.TLabel").pack(side="bottom", anchor="w", padx=16, pady=(12, 0))
        self.tabs.bind("<<NotebookTabChanged>>", self._sync_navigation)
        self._select_tab(0)

    def _tab(self, title: str) -> ttk.Frame:
        frame = ttk.Frame(self.tabs, padding=(22, 20), style="Page.TFrame")
        self.tabs.add(frame, text=title)
        icons = {
            "Tổng quan": "▦",
            "Instances": "▣",
            "Tối ưu": "⚡",
            "ADB": ">_",
            "Ứng dụng": "◉",
            "Cài đặt": "⚙",
        }
        index = len(self.nav_buttons)
        button = ttk.Button(
            self.sidebar,
            text=f"{icons.get(title, '•')}   {title}",
            style="Nav.TButton",
            command=lambda tab=index: self._select_tab(tab),
        )
        button.pack(fill="x", padx=8, pady=2)
        self.nav_buttons.append(button)
        return frame

    def _select_tab(self, index: int) -> None:
        self.tabs.select(index)
        for position, button in enumerate(self.nav_buttons):
            button.configure(style="NavActive.TButton" if position == index else "Nav.TButton")

    def _sync_navigation(self, _event: Any = None) -> None:
        selected = self.tabs.select()
        if not selected:
            return
        index = self.tabs.index(selected)
        for position, button in enumerate(self.nav_buttons):
            button.configure(style="NavActive.TButton" if position == index else "Nav.TButton")

    def _page_header(self, parent: ttk.Frame, title: str, description: str) -> None:
        ttk.Label(parent, text=title, style="Title.TLabel").pack(anchor="w")
        ttk.Label(parent, text=description, style="Subtitle.TLabel").pack(anchor="w", pady=(3, 16))

    def _stat_card(self, parent: ttk.Frame, title: str, variable: tk.StringVar) -> ttk.Frame:
        card = ttk.Frame(parent, padding=(18, 15), style="Card.TFrame")
        ttk.Label(card, text=title.upper(), style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(card, textvariable=variable, style="CardValue.TLabel").pack(anchor="w", pady=(7, 0))
        return card

    def _build_dashboard(self) -> None:
        frame = self._tab("Tổng quan")
        self._page_header(frame, "Tổng quan", "Theo dõi nhanh trạng thái LDPlayer và các phiên đang chạy.")
        self.ld_status = tk.StringVar(value="Đang kiểm tra…")
        self.adb_status = tk.StringVar(value="Đang kiểm tra…")
        self.instance_status = tk.StringVar(value="Chưa có dữ liệu")
        cards = ttk.Frame(frame)
        cards.pack(fill="x")
        for column in range(3):
            cards.columnconfigure(column, weight=1, uniform="dashboard")
        self._stat_card(cards, "LDPlayer", self.ld_status).grid(row=0, column=0, sticky="ew", padx=(0, 7))
        self._stat_card(cards, "ADB", self.adb_status).grid(row=0, column=1, sticky="ew", padx=7)
        self._stat_card(cards, "Instances", self.instance_status).grid(row=0, column=2, sticky="ew", padx=(7, 0))
        ttk.Label(frame, text="THAO TÁC NHANH", style="Section.TLabel").pack(anchor="w", pady=(28, 10))
        actions = ttk.Frame(frame, style="Actions.TFrame")
        actions.pack(anchor="w")
        ttk.Button(actions, text="▶  Khởi động tất cả", command=self.start_all, style="Primary.TButton").pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="■  Dừng tất cả", command=self.stop_all, style="Danger.TButton").pack(side="left", padx=4)
        ttk.Button(actions, text="⚡  Tối ưu tất cả", command=lambda: self.apply_profile(True)).pack(side="left", padx=4)
        ttk.Button(actions, text="↻  Làm mới", command=self.refresh_all).pack(side="left", padx=4)

    def _build_instances(self) -> None:
        frame = self._tab("Instances")
        self._page_header(frame, "Quản lý instance", "Khởi động, dừng và theo dõi từng phiên LDPlayer.")
        columns = ("id", "name", "status", "screen", "pid")
        self.instance_tree = ttk.Treeview(frame, columns=columns, show="headings", selectmode="extended")
        for column, text, width in (
            ("id", "ID", 60), ("name", "Tên", 250), ("status", "Trạng thái", 110),
            ("screen", "Màn hình", 180), ("pid", "PID", 100),
        ):
            self.instance_tree.heading(column, text=text)
            self.instance_tree.column(column, width=width, anchor="center" if column != "name" else "w")
        self.instance_tree.pack(fill="both", expand=True, pady=(0, 12))
        actions = ttk.Frame(frame)
        actions.pack(fill="x")
        ttk.Button(actions, text="↻  Làm mới", command=self.refresh_instances).pack(side="left", padx=(0, 5))
        ttk.Button(actions, text="▶  Khởi động", command=lambda: self.instance_action("start"), style="Primary.TButton").pack(side="left", padx=5)
        ttk.Button(actions, text="■  Dừng", command=lambda: self.instance_action("stop"), style="Danger.TButton").pack(side="left", padx=5)
        ttk.Button(actions, text="↻  Khởi động lại", command=lambda: self.instance_action("restart")).pack(side="left", padx=5)

    def _build_optimizer(self) -> None:
        frame = self._tab("Tối ưu")
        heading = ttk.Frame(frame)
        heading.grid(row=0, column=0, columnspan=4, sticky="ew")
        ttk.Label(heading, text="Tối ưu hiệu năng", style="Title.TLabel").pack(anchor="w")
        ttk.Label(heading, text="Điều chỉnh tài nguyên để chạy vn.kvtm.js nhẹ và ổn định hơn.",
                  style="Subtitle.TLabel").pack(anchor="w", pady=(3, 12))
        self.profile_name = tk.StringVar(value=str(self.config_store.data.get("default_profile", "Lite")))
        self.cpu_var = tk.IntVar(value=1)
        self.ram_var = tk.StringVar(value="512")
        self.width_var = tk.IntVar(value=800)
        self.height_var = tk.IntVar(value=800)
        self.dpi_var = tk.IntVar(value=240)
        self.fps_var = tk.StringVar(value="20")
        self.animation_var = tk.BooleanVar(value=False)
        self.memory_var = tk.BooleanVar(value=False)
        self.priority_var = tk.StringVar(value="normal")
        fields = ttk.Frame(frame, padding=(18, 14), style="Card.TFrame")
        fields.grid(row=1, column=0, sticky="nw", pady=(4, 16))
        self._combo_row(fields, 0, "Profile", self.profile_name, list(self.profiles), self._profile_selected)
        self._spin_row(fields, 1, "CPU", self.cpu_var, 1, 16)
        self._combo_row(fields, 2, "RAM (MB)", self.ram_var, ["512", "768", "1024", "1536", "2048", "4096", "8192"])
        self._spin_row(fields, 3, "Chiều rộng", self.width_var, 240, 3840)
        self._spin_row(fields, 4, "Chiều cao", self.height_var, 240, 3840)
        self._spin_row(fields, 5, "DPI", self.dpi_var, 80, 640)
        self._combo_row(fields, 6, "FPS", self.fps_var, ["10", "15", "20", "30", "60"])
        self._combo_row(fields, 7, "Ưu tiên", self.priority_var, ["normal", "below_normal", "idle"])
        ttk.Checkbutton(fields, text="Giữ hiệu ứng Android", variable=self.animation_var,
                        style="Card.TCheckbutton").grid(row=8, column=0, columnspan=2, sticky="w", pady=4)
        ttk.Checkbutton(fields, text="Tối ưu RAM/GPU đa phiên", variable=self.memory_var,
                        style="Card.TCheckbutton").grid(row=9, column=0, columnspan=2, sticky="w", pady=4)
        actions = ttk.Frame(frame)
        actions.grid(row=2, column=0, sticky="w")
        ttk.Button(actions, text="✓  Áp dụng đã chọn", command=lambda: self.apply_profile(False), style="Primary.TButton").pack(side="left", padx=(0, 6))
        ttk.Button(actions, text="⚡  Tối ưu tất cả", command=lambda: self.apply_profile(True)).pack(side="left", padx=6)
        ttk.Label(frame, text="Cấu hình được tự lưu. Instance đang chạy sẽ được khởi động lại để áp dụng đầy đủ.",
                  style="Muted.TLabel").grid(row=3, column=0, sticky="w", pady=15)

    def _build_adb(self) -> None:
        frame = self._tab("ADB")
        self._page_header(frame, "ADB Console", "Chạy lệnh, kiểm tra mạng và chụp màn hình thiết bị.")
        top = ttk.Frame(frame)
        top.pack(fill="x", pady=8)
        self.adb_device = tk.StringVar()
        self.adb_combo = ttk.Combobox(top, textvariable=self.adb_device, state="readonly", width=35)
        self.adb_combo.pack(side="left", padx=4)
        ttk.Button(top, text="Làm mới thiết bị", command=self.refresh_devices).pack(side="left", padx=4)
        ttk.Button(top, text="Kiểm tra mạng", command=self.test_network).pack(side="left", padx=4)
        command_row = ttk.Frame(frame)
        command_row.pack(fill="x", pady=5)
        self.adb_command = tk.StringVar(value="getprop")
        ttk.Entry(command_row, textvariable=self.adb_command).pack(side="left", fill="x", expand=True, padx=4)
        ttk.Button(command_row, text="Chạy", command=self.run_shell).pack(side="left", padx=4)
        ttk.Button(command_row, text="Chụp màn hình", command=self.capture_screen).pack(side="left", padx=4)
        self.adb_output = tk.Text(
            frame, height=22, wrap="word", background="#080d13", foreground="#c8f7df",
            insertbackground=self.TEXT, selectbackground="#0d6684", selectforeground="#ffffff",
            relief="flat", borderwidth=0, padx=14, pady=12, font=("Cascadia Mono", 10),
            highlightthickness=1, highlightbackground=self.BORDER, highlightcolor=self.ACCENT,
        )
        self.adb_output.pack(fill="both", expand=True, pady=8)

    def _build_packages(self) -> None:
        frame = self._tab("Ứng dụng")
        self._page_header(frame, "Ứng dụng Android", "Giữ vn.kvtm.js và rà soát các package có thể vô hiệu hóa.")
        controls = ttk.Frame(frame)
        controls.pack(fill="x", pady=8)
        self.package_device = tk.StringVar()
        self.package_combo = ttk.Combobox(controls, textvariable=self.package_device, state="readonly", width=28)
        self.package_combo.pack(side="left", padx=3)
        self.target_package = tk.StringVar(value="vn.kvtm.js")
        ttk.Entry(controls, textvariable=self.target_package, width=26).pack(side="left", padx=3)
        ttk.Button(controls, text="Phân tích ứng dụng mục tiêu", command=self.analyze_packages,
                   style="Primary.TButton").pack(side="left", padx=5)
        columns = ("pick", "package", "source", "status", "recommendation")
        self.package_tree = ttk.Treeview(frame, columns=columns, show="headings", selectmode="extended")
        for column, text, width in (
            ("pick", "Chọn", 58),
            ("package", "Package", 300), ("source", "Loại", 100),
            ("status", "Trạng thái", 100), ("recommendation", "Đánh giá", 300),
        ):
            self.package_tree.heading(column, text=text)
            self.package_tree.column(column, width=width, anchor="center" if column == "pick" else "w")
        self.package_tree.bind("<Button-1>", self._toggle_package_check, add="+")
        self.package_tree.bind("<<TreeviewSelect>>", self._sync_package_checks, add="+")
        self.package_tree.pack(fill="both", expand=True, pady=8)
        buttons = ttk.Frame(frame)
        buttons.pack(fill="x")
        ttk.Button(buttons, text="☑  Chọn đề xuất", command=self.select_suggested_packages).pack(side="left", padx=(0, 3))
        ttk.Button(buttons, text="☐  Bỏ chọn", command=self.clear_package_selection).pack(side="left", padx=3)
        ttk.Button(buttons, text="Vô hiệu hóa đã chọn", command=self.disable_packages,
                   style="Danger.TButton").pack(side="left", padx=3)
        ttk.Button(buttons, text="Bật lại đã chọn", command=self.enable_packages).pack(side="left", padx=3)
        ttk.Button(buttons, text="Khôi phục backup", command=self.restore_packages).pack(side="left", padx=3)

    def _build_settings(self) -> None:
        frame = self._tab("Cài đặt")
        heading = ttk.Frame(frame)
        heading.grid(row=0, column=0, columnspan=3, sticky="ew")
        ttk.Label(heading, text="Cài đặt", style="Title.TLabel").pack(anchor="w")
        ttk.Label(heading, text="Đường dẫn công cụ và khoảng nghỉ khi khởi động nhiều phiên.",
                  style="Subtitle.TLabel").pack(anchor="w", pady=(3, 16))
        self.console_path = tk.StringVar(value=str(self.config_store.data.get("console_path", "")))
        self.adb_path = tk.StringVar(value=str(self.config_store.data.get("adb_path", "")))
        self.delay_var = tk.IntVar(value=int(self.config_store.data.get("startup_delay", 5)))
        self._path_row(frame, 1, "LDConsole", self.console_path)
        self._path_row(frame, 2, "ADB", self.adb_path)
        ttk.Label(frame, text="Trễ khởi động").grid(row=3, column=0, sticky="w", pady=8)
        ttk.Spinbox(frame, from_=0, to=120, textvariable=self.delay_var, width=12).grid(row=3, column=1, sticky="w")
        ttk.Button(frame, text="✓  Lưu cài đặt", command=self.save_settings, style="Primary.TButton").grid(row=4, column=1, sticky="w", pady=15)
        ttk.Button(frame, text="⌕  Tự động phát hiện", command=self.detect).grid(row=4, column=2, sticky="w", pady=15)
        frame.columnconfigure(1, weight=1)

    def _combo_row(self, parent: ttk.Frame, row: int, label: str, variable: tk.Variable, values: list[str], callback: Callable | None = None) -> None:
        ttk.Label(parent, text=label, style="Field.TLabel").grid(row=row, column=0, sticky="w", padx=4, pady=5)
        widget = ttk.Combobox(parent, textvariable=variable, values=values, state="readonly", width=24)
        widget.grid(row=row, column=1, sticky="w", padx=4, pady=5)
        if callback:
            widget.bind("<<ComboboxSelected>>", callback)

    def _spin_row(self, parent: ttk.Frame, row: int, label: str, variable: tk.Variable, minimum: int, maximum: int) -> None:
        ttk.Label(parent, text=label, style="Field.TLabel").grid(row=row, column=0, sticky="w", padx=4, pady=5)
        ttk.Spinbox(parent, from_=minimum, to=maximum, textvariable=variable, width=22).grid(row=row, column=1, sticky="w", padx=4, pady=5)

    def _path_row(self, parent: ttk.Frame, row: int, label: str, variable: tk.StringVar) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=8)
        ttk.Entry(parent, textvariable=variable).grid(row=row, column=1, sticky="ew", padx=8)
        ttk.Button(parent, text="Chọn…", command=lambda: self._browse(variable)).grid(row=row, column=2)

    def _browse(self, variable: tk.StringVar) -> None:
        path = filedialog.askopenfilename(filetypes=[("Executable", "*.exe"), ("All", "*.*")])
        if path:
            variable.set(path)

    def _run_async(self, message: str, function: Callable[[], Any], callback: Callable[[Any], None] | None = None) -> None:
        self.status.set(message)

        def runner() -> None:
            try:
                result = function()
                if callback:
                    self.after(0, lambda: callback(result))
            except Exception as exc:
                self.logger.exception(message)
                self.after(0, lambda error=str(exc): messagebox.showerror("Không thể thực hiện", error))
            finally:
                self.after(0, lambda: self.status.set("Sẵn sàng"))

        threading.Thread(target=runner, daemon=True).start()

    def _configure_services(self) -> None:
        console = Path(self.console_path.get())
        adb = Path(self.adb_path.get())
        if not console.is_file():
            installation = detect_ldplayer()
            if installation:
                console = installation.console
                adb = installation.adb or adb
                self.console_path.set(str(console))
                self.adb_path.set(str(adb) if adb.is_file() else "")
                self.save_settings(refresh=False)
        self.console = LDPlayerConsole(console) if console.is_file() else None
        self.adb = ADBManager(adb) if adb.is_file() else None
        self.optimizer = Optimizer(self.console, self.adb) if self.console else None
        self.package_manager = PackageManager(self.adb) if self.adb else None
        self.ld_status.set("✓ Sẵn sàng" if self.console else "✕ Chưa phát hiện")
        self.adb_status.set("✓ Sẵn sàng" if self.adb else "✕ Chưa phát hiện")
        self.refresh_all()

    def detect(self) -> None:
        installation = detect_ldplayer(self.console_path.get() or None)
        if not installation:
            messagebox.showwarning("Phát hiện LDPlayer", "Không tìm thấy LDPlayer. Hãy chọn ldconsole.exe thủ công.")
            return
        self.console_path.set(str(installation.console))
        self.adb_path.set(str(installation.adb or ""))
        self.save_settings()

    def save_settings(self, *, refresh: bool = True) -> None:
        self._save_profile()
        self.config_store.update(
            console_path=self.console_path.get().strip(),
            adb_path=self.adb_path.get().strip(),
            startup_delay=self.delay_var.get(),
        )
        if refresh:
            self._configure_services()

    def _profile_selected(self, _event: Any = None) -> None:
        values = self.profiles.get(self.profile_name.get())
        if values:
            self._set_profile(OptimizationProfile.from_dict(values))

    def _set_profile(self, profile: OptimizationProfile) -> None:
        self.cpu_var.set(profile.cpu); self.ram_var.set(str(profile.ram))
        self.width_var.set(profile.width); self.height_var.set(profile.height); self.dpi_var.set(profile.dpi)
        self.fps_var.set(str(profile.fps)); self.animation_var.set(profile.animation)
        self.memory_var.set(profile.memory_optimization); self.priority_var.set(profile.process_priority)

    def _current_profile(self) -> OptimizationProfile:
        profile = OptimizationProfile(
            cpu=self.cpu_var.get(), ram=int(self.ram_var.get()), width=self.width_var.get(),
            height=self.height_var.get(), dpi=self.dpi_var.get(), fps=int(self.fps_var.get()),
            animation=self.animation_var.get(), audio=False,
            memory_optimization=self.memory_var.get(), process_priority=self.priority_var.get(),
        )
        profile.validate()
        return profile

    def _load_saved_profile(self) -> None:
        saved = self.config_store.data.get("last_optimization_profile", {})
        try:
            profile = OptimizationProfile.from_dict(saved) if saved else OptimizationProfile.from_dict(self.profiles["Lite"])
            self._set_profile(profile)
        except (ValueError, TypeError):
            pass

    def _save_profile(self) -> None:
        try:
            p = self._current_profile()
        except (ValueError, tk.TclError):
            return
        self.config_store.update(default_profile=self.profile_name.get(), last_optimization_profile={
            "cpu": p.cpu, "ram": p.ram, "width": p.width, "height": p.height,
            "dpi": p.dpi, "fps": p.fps, "animation": p.animation, "audio": p.audio,
            "memory_optimization": p.memory_optimization, "process_priority": p.process_priority,
        })

    def refresh_all(self) -> None:
        if self.console: self.refresh_instances()
        if self.adb: self.refresh_devices()

    def refresh_instances(self) -> None:
        if not self.console: return
        def done(instances: list[Instance]) -> None:
            self.instances = instances
            self.instance_tree.delete(*self.instance_tree.get_children())
            for item in instances:
                screen = f"{item.width}×{item.height} · {item.dpi} DPI" if item.width else "—"
                self.instance_tree.insert("", "end", iid=str(item.index), values=(item.index, item.name, "RUN" if item.running else "STOP", screen, item.process_id or "—"))
            self.instance_status.set(f"{len(instances)} tổng · {sum(x.running for x in instances)} đang chạy")
            if self.adb_devices:
                self._populate_device_choices()
        self._run_async("Đang đọc instances…", self.console.list_instances, done)

    def _selected_indices(self) -> list[int]:
        return [int(item) for item in self.instance_tree.selection()]

    def instance_action(self, action: str) -> None:
        if not self.console: return
        indices = self._selected_indices()
        if not indices:
            messagebox.showinfo("Instances", "Hãy chọn ít nhất một instance."); return
        def execute() -> None:
            for index in indices:
                if action == "start": self.console.start(index)
                elif action == "stop": self.console.stop(index)
                else: self.console.restart(index)
        self._run_async("Đang điều khiển instance…", execute, lambda _: self.refresh_instances())

    def start_all(self) -> None:
        if not self.console or not self.optimizer: return
        profile = self._current_profile(); indices = [x.index for x in self.instances if not x.running]
        def execute() -> dict[int, float]:
            self.optimizer.configure_multi_instance(profile)
            return self.console.start_sequential(indices, self.delay_var.get(), after_start=lambda i: self.optimizer.apply_runtime(i, profile))
        self._run_async("Đang khởi động tuần tự…", execute, lambda _: self.refresh_instances())

    def stop_all(self) -> None:
        if self.console: self._run_async("Đang dừng tất cả…", self.console.stop_all, lambda _: self.refresh_instances())

    def apply_profile(self, all_instances: bool) -> None:
        if not self.optimizer: return
        targets = [x.index for x in self.instances] if all_instances else self._selected_indices()
        if not targets:
            messagebox.showinfo("Tối ưu", "Hãy chọn ít nhất một instance."); return
        profile = self._current_profile(); self._save_profile()
        def execute() -> list[Any]:
            return [self.optimizer.apply(index, profile, configure_global=position == 0) for position, index in enumerate(targets)]
        self._run_async("Đang áp dụng profile…", execute, lambda result: (self.refresh_instances(), messagebox.showinfo("Tối ưu", f"Đã tối ưu {len(result)} instance.")))

    def refresh_devices(self) -> None:
        if not self.adb: return
        def done(devices: list[Any]) -> None:
            self.adb_devices = [device for device in devices if device.state == "device"]
            self._populate_device_choices()
        self._run_async("Đang đọc ADB…", self.adb.devices, done)

    def _populate_device_choices(self) -> None:
        old_adb_serial = self._selected_serial(self.adb_device)
        old_package_serial = self._selected_serial(self.package_device)
        all_instances = sorted(self.instances, key=lambda item: item.index)
        by_index = {item.index: item for item in all_instances}
        assigned: dict[str, Instance] = {}
        used_indices: set[int] = set()

        for device in self.adb_devices:
            index = ldplayer_index_from_serial(device.serial)
            instance = by_index.get(index) if index is not None else None
            if instance:
                assigned[device.serial] = instance
                used_indices.add(instance.index)

        remaining_instances = [item for item in all_instances if item.index not in used_indices]
        remaining_devices = [device for device in self.adb_devices if device.serial not in assigned]
        for device, instance in zip(remaining_devices, remaining_instances):
            assigned[device.serial] = instance
            used_indices.add(instance.index)

        choices: list[str] = []
        mapping: dict[str, str] = {}
        for device in self.adb_devices:
            instance = assigned.get(device.serial)
            label = f"{instance.name} ({device.serial})" if instance else device.serial
            choices.append(label)
            mapping[label] = device.serial
            if instance:
                mapping[instance.name] = device.serial

        unconnected_instances = [item for item in all_instances if item.index not in used_indices]
        for instance in unconnected_instances:
            label = f"{instance.name} · Đang tắt"
            choices.append(label)
            mapping[label] = ""

        self.device_serials_by_name = mapping
        self.adb_combo["values"] = choices
        self.package_combo["values"] = choices
        self._restore_device_choice(self.adb_device, old_adb_serial, choices)
        self._restore_device_choice(self.package_device, old_package_serial, choices)

    def _restore_device_choice(self, variable: tk.StringVar, serial: str, choices: list[str]) -> None:
        matching = next((name for name, value in self.device_serials_by_name.items() if value == serial), None)
        variable.set(matching or (choices[0] if choices else ""))

    def _selected_serial(self, variable: tk.StringVar) -> str:
        selected = variable.get().strip()
        return self.device_serials_by_name.get(selected, selected)

    def _require_selected_serial(self, variable: tk.StringVar, title: str) -> str:
        selected = variable.get().strip()
        serial = self._selected_serial(variable)
        if not selected:
            messagebox.showinfo(title, "Chưa có instance để chọn.")
        elif not serial:
            messagebox.showinfo(title, "Instance này đang tắt hoặc chưa kết nối ADB. Hãy khởi động instance rồi bấm Làm mới.")
        return serial

    def run_shell(self) -> None:
        serial = self._require_selected_serial(self.adb_device, "ADB")
        if not self.adb or not serial: return
        command = self.adb_command.get(); self.adb_output.insert("end", f"> {command}\n")
        self._run_async("Đang chạy ADB…", lambda: self.adb.shell(serial, command), lambda text: self.adb_output.insert("end", text + "\n"))

    def test_network(self) -> None:
        serial = self._require_selected_serial(self.adb_device, "ADB")
        if self.adb and serial:
            self._run_async("Đang kiểm tra mạng…", lambda: self.adb.network_diagnostics(serial), lambda text: self.adb_output.insert("end", text + "\n"))

    def capture_screen(self) -> None:
        serial = self._require_selected_serial(self.adb_device, "ADB")
        if self.adb and serial:
            self._run_async("Đang chụp màn hình…", lambda: self.adb.screenshot(serial), lambda path: self.adb_output.insert("end", f"Đã lưu: {path}\n"))

    def analyze_packages(self) -> None:
        serial = self._require_selected_serial(self.package_device, "Ứng dụng")
        if not self.package_manager or not serial: return
        def done(packages: list[AndroidPackage]) -> None:
            self.package_tree.delete(*self.package_tree.get_children()); suggested=[]
            for p in packages:
                self.package_tree.insert("", "end", iid=p.name, values=("☐", p.name, p.source, "Đã tắt" if p.disabled else "Đang bật", p.recommendation))
                if p.review_suggested and not p.disabled: suggested.append(p.name)
            self.package_suggestions = suggested
            self.package_tree.selection_set(suggested)
            self._sync_package_checks()
        self._run_async("Đang phân tích package…", lambda: self.package_manager.analyze_for_target(serial, self.target_package.get()), done)

    def _toggle_package_check(self, event: tk.Event) -> str | None:
        if self.package_tree.identify_region(event.x, event.y) != "cell":
            return None
        if self.package_tree.identify_column(event.x) != "#1":
            return None
        item = self.package_tree.identify_row(event.y)
        if not item:
            return "break"
        selected = set(self.package_tree.selection())
        if item in selected:
            self.package_tree.selection_remove(item)
        else:
            self.package_tree.selection_add(item)
        self._sync_package_checks()
        return "break"

    def _sync_package_checks(self, _event: Any = None) -> None:
        selected = set(self.package_tree.selection())
        for item in self.package_tree.get_children():
            values = list(self.package_tree.item(item, "values"))
            if values:
                values[0] = "☑" if item in selected else "☐"
                self.package_tree.item(item, values=values)

    def select_suggested_packages(self) -> None:
        self.package_tree.selection_set(self.package_suggestions)
        self._sync_package_checks()

    def clear_package_selection(self) -> None:
        selected = self.package_tree.selection()
        if selected:
            self.package_tree.selection_remove(*selected)
        self._sync_package_checks()

    def _selected_packages(self) -> list[str]:
        return list(self.package_tree.selection())

    def disable_packages(self) -> None:
        packages=self._selected_packages(); serial=self._require_selected_serial(self.package_device, "Ứng dụng")
        if not self.package_manager or not packages: return
        if not messagebox.askyesno("Ứng dụng", f"Vô hiệu hóa {len(packages)} package? Manager sẽ tạo backup."): return
        self._run_async("Đang vô hiệu hóa…", lambda: self.package_manager.disable(serial, packages), lambda _: self.analyze_packages())

    def enable_packages(self) -> None:
        packages=self._selected_packages(); serial=self._require_selected_serial(self.package_device, "Ứng dụng")
        if self.package_manager and packages:
            self._run_async("Đang bật lại…", lambda: self.package_manager.enable(serial, packages), lambda _: self.analyze_packages())

    def restore_packages(self) -> None:
        if not self.package_manager: return
        path=filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if path: self._run_async("Đang khôi phục…", lambda: self.package_manager.restore(path), lambda _: messagebox.showinfo("Ứng dụng", "Đã khôi phục trạng thái package."))

    def _close(self) -> None:
        self._save_profile()
        self.destroy()


def run_tk_gui() -> int:
    app = CompatApp()
    app.mainloop()
    return 0
