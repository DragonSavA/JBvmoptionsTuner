from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from jetbrains_vmoptions_tuner import desktop_shortcut
from jetbrains_vmoptions_tuner.config import ConfigStore, default_config


class DesktopPreferenceTests(unittest.TestCase):
    def test_new_and_legacy_configs_enable_shortcut_by_default(self) -> None:
        self.assertTrue(default_config()["settings"]["desktop_shortcut"])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text('{"settings": {"first_run_completed": true}}', encoding="utf-8")
            loaded = ConfigStore(path).load()
            self.assertTrue(loaded["settings"]["desktop_shortcut"])
            self.assertTrue(loaded["settings"]["first_run_completed"])

    def test_disabled_shortcut_stays_disabled_after_restart(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = ConfigStore(root / "config.json")
            config = default_config()
            with patch.object(desktop_shortcut, "get_desktop_path", return_value=root):
                shortcut = root / desktop_shortcut.SHORTCUT_NAME
                shortcut.touch()
                desktop_shortcut.set_enabled(False, config, store, root / "main.py")
                self.assertFalse(shortcut.exists())
                loaded = store.load()
                self.assertFalse(loaded["settings"]["desktop_shortcut"])
                # Reconcile also removes a stale shortcut while disabled.
                shortcut.touch()
                with patch.object(desktop_shortcut, "enable") as enable:
                    desktop_shortcut.reconcile(loaded, root / "main.py")
                    enable.assert_not_called()
                self.assertFalse(shortcut.exists())
                desktop_shortcut.reconcile(loaded, root / "main.py")

    def test_failed_creation_does_not_change_saved_preference(self) -> None:
        config = default_config()
        config["settings"]["desktop_shortcut"] = False
        store = Mock()
        with patch.object(desktop_shortcut, "enable", side_effect=OSError("desktop is read-only")):
            with self.assertRaises(OSError):
                desktop_shortcut.set_enabled(True, config, store, Path("main.py"))
        self.assertFalse(config["settings"]["desktop_shortcut"])
        store.save.assert_not_called()

    def test_failed_save_restores_preference_and_shortcut(self) -> None:
        config = default_config()
        store = Mock()
        store.save.side_effect = OSError("config is read-only")
        with (
            patch.object(desktop_shortcut, "disable"),
            patch.object(desktop_shortcut, "enable") as enable,
        ):
            with self.assertRaises(OSError):
                desktop_shortcut.set_enabled(False, config, store, Path("main.py"))
            enable.assert_called_once()
        self.assertTrue(config["settings"]["desktop_shortcut"])


@unittest.skipUnless(os.name == "nt", "Requires Windows shell")
class WindowsShortcutTests(unittest.TestCase):
    def test_real_shortcut_round_trip_with_special_characters(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "Тест vmoptions & user's files"
            root.mkdir()
            launcher = root / "start.bat"
            launcher.write_text("@echo off\n", encoding="ascii")
            unrelated = root / "keep.txt"
            unrelated.touch()
            with patch.object(desktop_shortcut, "get_desktop_path", return_value=root):
                desktop_shortcut.enable(root / "main.py")
                self.assertTrue(desktop_shortcut.is_enabled())
                env = os.environ.copy()
                env["VMOPT_SHORTCUT_PATH"] = str(desktop_shortcut.get_shortcut_path())
                code = (
                    "[Console]::OutputEncoding = New-Object Text.UTF8Encoding $false; "
                    "$link = (New-Object -ComObject WScript.Shell).CreateShortcut($env:VMOPT_SHORTCUT_PATH); "
                    "@{target=$link.TargetPath; directory=$link.WorkingDirectory; icon=$link.IconLocation} | ConvertTo-Json"
                )
                output = subprocess.run(
                    [str(desktop_shortcut.powershell_executable()), "-NoProfile", "-Command", code],
                    env=env,
                    check=True,
                    capture_output=True,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
                link = json.loads(output.stdout.decode("utf-8-sig"))
                self.assertEqual(Path(link["target"]).resolve(), launcher.resolve())
                self.assertEqual(Path(link["directory"]).resolve(), root.resolve())
                self.assertEqual(link["icon"], f"{desktop_shortcut.APP_ICON},0")
                desktop_shortcut.disable()
                self.assertFalse(desktop_shortcut.is_enabled())
                desktop_shortcut.disable()
                self.assertTrue(unrelated.exists())

    def test_resolves_real_known_folder(self) -> None:
        self.assertTrue(desktop_shortcut.get_desktop_path().is_absolute())


if __name__ == "__main__":
    unittest.main()
