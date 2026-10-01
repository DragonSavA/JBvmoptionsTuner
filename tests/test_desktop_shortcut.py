from __future__ import annotations

import ctypes
import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from ctypes import wintypes
from pathlib import Path
from unittest.mock import Mock, patch

from jetbrains_vmoptions_tuner import desktop_shortcut
from jetbrains_vmoptions_tuner.config import ConfigStore, default_config
from jetbrains_vmoptions_tuner.localization import LocalizedOSError


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
    def _read_shortcut(self, path: Path) -> dict:
        # Let Windows load the persisted .lnk through its Unicode interface.
        # WScript.Shell also cannot reliably open filenames outside the ACP.
        with desktop_shortcut._shell_link() as (link, persist):
            self.assertEqual(
                desktop_shortcut._com_call(
                    persist, 5, (wintypes.LPCWSTR, wintypes.DWORD), str(path), 0
                ),  # IPersistFile.Load / STGM_READ
                0,
            )
            values = {}
            for name, slot, extra_types, extra_args in (
                ("target", 3, (ctypes.c_void_p, wintypes.DWORD), (None, 4)),  # SLGP_RAWPATH
                ("directory", 8, (), ()),
                ("description", 6, (), ()),
            ):
                buffer = ctypes.create_unicode_buffer(32768)
                self.assertEqual(
                    desktop_shortcut._com_call(
                        link,
                        slot,
                        (wintypes.LPWSTR, ctypes.c_int, *extra_types),
                        buffer,
                        len(buffer),
                        *extra_args,
                    ),
                    0,
                )
                values[name] = buffer.value
            buffer = ctypes.create_unicode_buffer(32768)
            icon_index = ctypes.c_int(-1)
            self.assertEqual(
                desktop_shortcut._com_call(
                    link,
                    16,  # IShellLinkW.GetIconLocation
                    (wintypes.LPWSTR, ctypes.c_int, ctypes.POINTER(ctypes.c_int)),
                    buffer,
                    len(buffer),
                    ctypes.byref(icon_index),
                ),
                0,
            )
            values["icon"] = f"{buffer.value},{icon_index.value}"
            show_command = ctypes.c_int()
            self.assertEqual(
                desktop_shortcut._com_call(
                    link, 14, (ctypes.POINTER(ctypes.c_int),), ctypes.byref(show_command)
                ),
                0,
            )
            values["show_command"] = show_command.value
            return values

    def _assert_round_trip(self, root: Path) -> None:
        launcher = root / "start.bat"
        launcher.write_text("@echo off\n", encoding="ascii")
        unrelated = root / "keep.txt"
        unrelated.touch()
        icon = root / "Icon 中文 🐉.ico"
        icon.write_bytes(desktop_shortcut.APP_ICON.read_bytes())
        with (
            patch.object(desktop_shortcut, "get_desktop_path", return_value=root),
            patch.object(desktop_shortcut, "APP_ICON", icon),
        ):
            # Creating a link twice must also update an existing shortcut.
            for _ in range(2):
                desktop_shortcut.enable(root / "main.py")
                self.assertTrue(desktop_shortcut.is_enabled())
                link = self._read_shortcut(desktop_shortcut.get_shortcut_path())
                self.assertEqual(Path(link["target"]).resolve(), launcher.resolve())
                self.assertEqual(Path(link["directory"]).resolve(), root.resolve())
                self.assertEqual(link["icon"], f"{icon},0")
                self.assertEqual(link["description"], "Launch vmoptions Tuner")
                self.assertEqual(link["show_command"], 1)
            desktop_shortcut.disable()
            self.assertFalse(desktop_shortcut.is_enabled())
            desktop_shortcut.disable()
            self.assertTrue(unrelated.exists())

    def test_real_shortcut_round_trip_with_special_characters(self) -> None:
        for name in (
            "ASCII vmoptions & user's files",
            "Тест vmoptions & user's files",
            "中文 vmoptions & user's files",
            "🐉 vmoptions & user's files",
        ):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory) / name
                root.mkdir()
                self._assert_round_trip(root)

    def test_creation_preserves_an_existing_com_apartment(self) -> None:
        def round_trip(mode: int) -> None:
            ole32 = ctypes.WinDLL("ole32")
            ole32.CoInitializeEx.argtypes = [ctypes.c_void_p, wintypes.DWORD]
            ole32.CoInitializeEx.restype = ctypes.c_long
            ole32.CoUninitialize.argtypes = []
            ole32.CoUninitialize.restype = None
            self.assertEqual(ole32.CoInitializeEx(None, mode), 0)
            try:
                with tempfile.TemporaryDirectory() as directory:
                    self._assert_round_trip(Path(directory))
                initialized = ole32.CoInitializeEx(None, mode)
                try:
                    self.assertEqual(initialized, 1)  # S_FALSE: still initialized.
                finally:
                    if initialized >= 0:
                        ole32.CoUninitialize()
            finally:
                ole32.CoUninitialize()

        for mode in (0, 2):  # COINIT_MULTITHREADED and COINIT_APARTMENTTHREADED
            with self.subTest(mode=mode), ThreadPoolExecutor(max_workers=1) as pool:
                pool.submit(round_trip, mode).result(timeout=30)

    def test_save_failure_reports_the_operation_and_hresult_in_both_languages(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "start.bat").write_text("@echo off\n", encoding="ascii")
            # A directory at the .lnk path cannot be overwritten with a file.
            (root / desktop_shortcut.SHORTCUT_NAME).mkdir()
            with patch.object(desktop_shortcut, "get_desktop_path", return_value=root):
                with self.assertRaises(LocalizedOSError) as failure:
                    desktop_shortcut.enable(root / "main.py")
            error = failure.exception
            self.assertEqual(error.key, "shortcut_failed_hresult")
            self.assertEqual(error.values["operation"], "IPersistFile.Save")
            for language in ("en", "ru"):
                self.assertIn("IPersistFile.Save", error.message(language))
                self.assertIn(f"0x{error.values['hresult']:08X}", error.message(language))

    def test_resolves_real_known_folder(self) -> None:
        self.assertTrue(desktop_shortcut.get_desktop_path().is_absolute())


if __name__ == "__main__":
    unittest.main()
