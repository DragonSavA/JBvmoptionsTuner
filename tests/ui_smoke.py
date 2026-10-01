"""Opt-in WinUI smoke test; uses only temporary settings and desktop links."""

from __future__ import annotations

import os
import sys
import tempfile
import traceback
from datetime import timedelta
from pathlib import Path
from typing import override
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    if os.name != "nt":
        print("This smoke test requires Windows.")
        return 2

    from winui3.microsoft.ui.xaml import Application, DispatcherTimer
    from winui3.microsoft.windows.applicationmodel.dynamicdependency.bootstrap import initialize

    from jetbrains_vmoptions_tuner import desktop_shortcut, ui
    from jetbrains_vmoptions_tuner.config import ConfigStore, default_config

    errors: list[str] = []
    image_opened = False

    class SmokeApp(ui.App):
        @override
        def _on_launched(self, args) -> None:
            try:
                super()._on_launched(args)
                icon = self._controller._find(self._controller.root, "AppIcon", ui.Image)

                def opened(_sender, _args):
                    nonlocal image_opened
                    image_opened = True

                def failed(_sender, args):
                    errors.append(f"SVG load failed: {args.error_message}")

                self._callbacks = [opened, failed]
                icon.add_image_opened(opened)
                icon.add_image_failed(failed)
                self._timer = DispatcherTimer()
                self._timer.interval = timedelta(seconds=2)

                def verify(_sender, _args):
                    self._timer.stop()
                    try:
                        controller = self._controller
                        assert image_opened, "Application SVG did not render"
                        assert not errors, errors
                        assert controller.desktop_shortcut_toggle.is_on
                        assert desktop_shortcut.is_enabled()
                        controller.desktop_shortcut_toggle.is_on = False
                        assert not desktop_shortcut.is_enabled()
                        assert not controller.store.load()["settings"]["desktop_shortcut"]
                        controller.desktop_shortcut_toggle.is_on = True
                        assert desktop_shortcut.is_enabled()
                        assert controller.store.load()["settings"]["desktop_shortcut"]
                        print("PASS: WinUI window, SVG and desktop toggle persistence", flush=True)
                    except Exception:
                        errors.append(traceback.format_exc())
                    finally:
                        self._window.close()

                self._callbacks.append(verify)
                self._timer.add_tick(verify)
                self._timer.start()
            except Exception:
                errors.append(traceback.format_exc())
                if self._window:
                    self._window.close()
                else:
                    self.exit()

    with tempfile.TemporaryDirectory() as directory:
        temp_root = Path(directory)
        store = ConfigStore(temp_root / "config.json")
        config = default_config()
        config["settings"]["first_run_completed"] = True
        store.save(config)
        with patch.object(ui, "ConfigStore", return_value=store):
            with patch.object(desktop_shortcut, "get_desktop_path", return_value=temp_root):
                with patch.object(ui.autostart, "is_enabled", return_value=True):
                    with initialize():

                        def start(_params):
                            SmokeApp.startup_entry_script = ROOT / "main.py"
                            SmokeApp()

                        Application.start(start)
    for error in errors:
        print(error, file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
