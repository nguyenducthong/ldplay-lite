from __future__ import annotations

import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from core.adb import ADBManager, ldplayer_index_from_serial, parse_devices
from core.detector import detect_ldplayer
from core.instance import parse_list2
from core.optimizer import OptimizationProfile
from core.ldplayer import LDPlayerConsole
from core.packages import is_protected_package, parse_package_list
from utils.process import CommandResult


class InstanceParsingTests(unittest.TestCase):
    def test_parse_list2(self) -> None:
        output = '0,LD-01,101,102,1,400,500,800,800,240\n1,"LD, Backup",0,0,0,0,0\n'
        instances = parse_list2(output)
        self.assertEqual([item.index for item in instances], [0, 1])
        self.assertEqual(instances[1].name, "LD, Backup")
        self.assertTrue(instances[0].running)
        self.assertFalse(instances[1].running)
        self.assertEqual(
            (instances[0].width, instances[0].height, instances[0].dpi),
            (800, 800, 240),
        )

    def test_ignores_malformed_rows(self) -> None:
        self.assertEqual(parse_list2("error\n"), [])


class ADBParsingTests(unittest.TestCase):
    def test_parse_devices(self) -> None:
        output = "List of devices attached\n127.0.0.1:5555 device product:a model:b\nemulator-5556 offline\n"
        devices = parse_devices(output)
        self.assertEqual(devices[0].serial, "127.0.0.1:5555")
        self.assertEqual(devices[0].state, "device")
        self.assertEqual(devices[1].state, "offline")

    def test_maps_adb_serial_to_ldplayer_index(self) -> None:
        self.assertEqual(ldplayer_index_from_serial("emulator-5554"), 0)
        self.assertEqual(ldplayer_index_from_serial("emulator-5558"), 2)
        self.assertEqual(ldplayer_index_from_serial("127.0.0.1:5557"), 1)
        self.assertIsNone(ldplayer_index_from_serial("USB123"))

    @patch.object(ADBManager, "_run")
    def test_shell_command_parsing(self, run_mock) -> None:
        run_mock.return_value = CommandResult(("adb",), 0, "mock_output", "")
        adb = ADBManager("adb.exe")

        # Plain shell command
        adb.shell("emulator-5554", "getprop ro.build.version.release")
        run_mock.assert_called_with("-s", "emulator-5554", "shell", "getprop", "ro.build.version.release")

        # logcat command
        adb.shell("emulator-5554", "logcat -b crash -d")
        run_mock.assert_called_with("-s", "emulator-5554", "logcat", "-b", "crash", "-d")

        # Full command pasted with exe and placeholder
        adb.shell("emulator-5554", r"d:\LDPlayer\LDPlayer9\adb.exe -s <tên_serial_ví_dụ_emulator-5554> logcat -b crash -d")
        run_mock.assert_called_with("-s", "emulator-5554", "logcat", "-b", "crash", "-d")

        # Full command pasted with serial when no serial was pre-selected
        adb.shell("", r"d:\LDPlayer\LDPlayer9\adb.exe -s emulator-5566 logcat -b crash -d")
        run_mock.assert_called_with("-s", "emulator-5566", "logcat", "-b", "crash", "-d")

    @patch.object(ADBManager, "shell")
    def test_network_diagnostics_runs_ip_and_dns_checks(self, shell_mock) -> None:
        shell_mock.return_value = "ok"
        output = ADBManager("adb.exe").network_diagnostics("emulator-5554")
        commands = [call.args[1] for call in shell_mock.call_args_list]
        self.assertIn("ping -c 4 -W 2 1.1.1.1", commands)
        self.assertIn("ping -c 4 -W 2 google.com", commands)
        self.assertIn("[Ping DNS]", output)


class ProfileTests(unittest.TestCase):
    def test_resolution_string_is_supported(self) -> None:
        profile = OptimizationProfile.from_dict(
            {"cpu": 1, "ram": 512, "resolution": "540x960", "dpi": 160, "fps": 20}
        )
        self.assertEqual((profile.width, profile.height), (540, 960))

    def test_invalid_fps_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            OptimizationProfile(1, 512, 540, 960, 160, 25).validate()


class PackageManagerTests(unittest.TestCase):
    def test_parse_package_list_with_and_without_apk_path(self) -> None:
        output = "package:com.example.app\npackage:/data/app/base.apk=com.vendor.store\nnoise\n"
        self.assertEqual(
            parse_package_list(output),
            {"com.example.app", "com.vendor.store"},
        )

    def test_essential_packages_are_protected(self) -> None:
        self.assertTrue(is_protected_package("com.android.systemui"))
        self.assertTrue(is_protected_package("com.android.providers.settings"))
        self.assertTrue(is_protected_package("com.example.launcher"))
        self.assertTrue(is_protected_package("com.android.vending"))
        self.assertTrue(is_protected_package("com.android.webview"))
        self.assertFalse(is_protected_package("com.android.chrome"))
        self.assertTrue(is_protected_package("android.ext.shared"))
        self.assertTrue(is_protected_package("com.google.android.play.games"))
        self.assertTrue(is_protected_package("com.android.phone"))
        self.assertFalse(is_protected_package("com.example.optionalapp"))

    def test_target_analysis_keeps_dependencies_and_marks_optional_apps(self) -> None:
        from core.packages import PackageManager

        adb = ADBManager("adb.exe")

        def shell(_serial: str, command: str) -> str:
            if command == "pm list packages -3":
                return "package:vn.kvtm.js\npackage:com.google.ar.core\n"
            if command == "pm list packages -s":
                return "package:com.android.vending\npackage:com.android.ld.appstore\n"
            return ""

        with patch.object(adb, "shell", side_effect=shell):
            packages = PackageManager(adb).analyze_for_target("emulator-5554", "vn.kvtm.js")
        by_name = {package.name: package for package in packages}
        self.assertTrue(by_name["vn.kvtm.js"].protected)
        self.assertTrue(by_name["com.android.vending"].protected)
        self.assertTrue(by_name["com.google.ar.core"].review_suggested)
        self.assertTrue(by_name["com.android.ld.appstore"].review_suggested)


class DetectorTests(unittest.TestCase):
    def test_manual_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "ldconsole.exe").touch()
            (root / "adb.exe").touch()
            installation = detect_ldplayer(root)
            self.assertIsNotNone(installation)
            assert installation is not None
            self.assertEqual(installation.console.name, "ldconsole.exe")
            self.assertEqual(installation.adb.name, "adb.exe")


class ConsoleCommandTests(unittest.TestCase):
    def test_list_instances_merges_stopped_vms_from_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config_dir = root / "vms" / "config"
            config_dir.mkdir(parents=True)
            for index in range(6):
                (config_dir / f"leidian{index}.config").write_text(
                    '{"statusSettings":{"playerName":"May %d"}}' % (index + 1),
                    encoding="utf-8",
                )
            console = LDPlayerConsole(root / "ldconsole.exe")
            list2 = "\n".join(
                f"{index},May {index + 1},0,0,1,{100 + index},0,800,800,240"
                for index in range(3)
            )
            with patch.object(console, "_run", return_value=CommandResult(("ldconsole", "list2"), 0, list2, "")):
                instances = console.list_instances()
            self.assertEqual(len(instances), 6)
            self.assertEqual([item.name for item in instances], [f"May {index}" for index in range(1, 7)])
            self.assertEqual(sum(item.running for item in instances), 3)

    @patch("core.ldplayer.run_command")
    def test_modify_uses_argument_list(self, run_command_mock) -> None:
        run_command_mock.return_value = CommandResult(("ldconsole.exe",), 0, "", "")
        console = LDPlayerConsole("ldconsole.exe")
        console.modify(2, cpu=1, memory=512, width=540, height=960, dpi=160)
        command = run_command_mock.call_args.args[0]
        self.assertEqual(command[:3], (Path("ldconsole.exe"), "modify", "--index"))
        self.assertIn("540,960,160", command)
        self.assertNotIn("--fps", command)

    @patch("core.ldplayer.run_command")
    def test_global_optimization_uses_supported_command(self, run_command_mock) -> None:
        run_command_mock.return_value = CommandResult(("ldconsole.exe",), 0, "", "")
        console = LDPlayerConsole("ldconsole.exe")
        console.global_settings(fps=20, audio=False, fastplay=True, cleanmode=True)
        command = run_command_mock.call_args.args[0]
        self.assertEqual(command[1], "globalsetting")
        self.assertEqual(command[command.index("--fps") + 1], "20")
        self.assertEqual(command[command.index("--audio") + 1], "0")

    @patch("core.ldplayer.run_command")
    def test_adb_shell_is_scoped_to_instance(self, run_command_mock) -> None:
        run_command_mock.return_value = CommandResult(("ldconsole.exe",), 0, "ok", "")
        console = LDPlayerConsole("ldconsole.exe")
        output = console.adb_shell(3, "shell getprop")
        command = run_command_mock.call_args.args[0]
        self.assertEqual(command[1:], ("adb", "--index", "3", "--command", "shell getprop"))
        self.assertEqual(output, "ok")


if __name__ == "__main__":
    unittest.main()
