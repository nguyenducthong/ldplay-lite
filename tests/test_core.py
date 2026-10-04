from __future__ import annotations

import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from core.adb import parse_devices
from core.detector import detect_ldplayer
from core.instance import parse_list2
from core.optimizer import OptimizationProfile
from core.ldplayer import LDPlayerConsole
from utils.process import CommandResult


class InstanceParsingTests(unittest.TestCase):
    def test_parse_list2(self) -> None:
        output = '0,LD-01,101,102,1,400,500\n1,"LD, Backup",0,0,0,0,0\n'
        instances = parse_list2(output)
        self.assertEqual([item.index for item in instances], [0, 1])
        self.assertEqual(instances[1].name, "LD, Backup")
        self.assertTrue(instances[0].running)
        self.assertFalse(instances[1].running)

    def test_ignores_malformed_rows(self) -> None:
        self.assertEqual(parse_list2("error\n"), [])


class ADBParsingTests(unittest.TestCase):
    def test_parse_devices(self) -> None:
        output = "List of devices attached\n127.0.0.1:5555 device product:a model:b\nemulator-5556 offline\n"
        devices = parse_devices(output)
        self.assertEqual(devices[0].serial, "127.0.0.1:5555")
        self.assertEqual(devices[0].state, "device")
        self.assertEqual(devices[1].state, "offline")


class ProfileTests(unittest.TestCase):
    def test_resolution_string_is_supported(self) -> None:
        profile = OptimizationProfile.from_dict(
            {"cpu": 1, "ram": 512, "resolution": "540x960", "dpi": 160, "fps": 20}
        )
        self.assertEqual((profile.width, profile.height), (540, 960))

    def test_invalid_fps_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            OptimizationProfile(1, 512, 540, 960, 160, 25).validate()


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
    @patch("core.ldplayer.run_command")
    def test_modify_uses_argument_list(self, run_command_mock) -> None:
        run_command_mock.return_value = CommandResult(("ldconsole.exe",), 0, "", "")
        console = LDPlayerConsole("ldconsole.exe")
        console.modify(2, cpu=1, memory=512, width=540, height=960, dpi=160, fps=20)
        command = run_command_mock.call_args.args[0]
        self.assertEqual(command[:3], (Path("ldconsole.exe"), "modify", "--index"))
        self.assertIn("540,960,160", command)
        self.assertIn("20", command)

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
