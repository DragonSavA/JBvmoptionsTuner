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

    from winrt.system import unbox_string
    from winui3.microsoft.ui.xaml import Application, DispatcherTimer
    from winui3.microsoft.ui.xaml.controls import ScrollViewer
    from winui3.microsoft.windows.applicationmodel.dynamicdependency.bootstrap import initialize

    from jetbrains_vmoptions_tuner import desktop_shortcut, ui
    from jetbrains_vmoptions_tuner.config import ConfigStore, default_config
    from jetbrains_vmoptions_tuner.localization import XAML_STRINGS, translate

    errors: list[str] = []
    image_opened = False
    branding_opened: set[str] = set()

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
                for name in ("AuthorIcon", "CodexIcon", "GitHubIcon"):
                    brand_image = self._controller._find(self._controller.root, name, ui.Image)

                    def brand_opened(_sender, _args, image_name=name):
                        branding_opened.add(image_name)

                    self._callbacks.append(brand_opened)
                    brand_image.add_image_opened(brand_opened)
                    brand_image.add_image_failed(failed)
                self._controller.root.update_layout()
                scroller = self._controller._find(
                    self._controller.root, "MainScrollViewer", ScrollViewer
                )
                scroller.change_view(None, scroller.scrollable_height, None)
                self._timer = DispatcherTimer()
                self._timer.interval = timedelta(seconds=4)

                def verify(_sender, _args):
                    self._timer.stop()
                    try:
                        controller = self._controller
                        assert image_opened, "Application SVG did not render"
                        assert not errors, errors
                        assert branding_opened == {"AuthorIcon", "CodexIcon", "GitHubIcon"}, (
                            branding_opened
                        )
                        assert (
                            controller.repository_link.navigate_uri.absolute_uri
                            == "https://github.com/DragonSavA/JBvmotionsTuner"
                        )
                        assert (
                            controller.author_link.navigate_uri.absolute_uri
                            == "https://github.com/DragonSavA?tab=overview"
                        )

                        def verify_language(language):
                            assert controller.language == language
                            assert controller.english_language_button.is_checked == (
                                language == "en"
                            )
                            assert controller.russian_language_button.is_checked == (
                                language == "ru"
                            )
                            for kind, name, prop, key in XAML_STRINGS:
                                control = controller._find(
                                    controller.root, name, ui.LOCALIZABLE_CONTROLS[kind]
                                )
                                value = getattr(control, prop)
                                if prop in {"content", "header", "on_content", "off_content"}:
                                    value = unbox_string(value)
                                assert value == translate(key, language), (
                                    name,
                                    prop,
                                )
                            assert (
                                translate("never_synced", language)
                                in controller.last_manual_text.text
                            )
                            assert controller.missing_text.text == translate(
                                "missing_lines", language, count=1
                            )
                            assert controller.desktop_shortcut_hint.text == translate(
                                "desktop_on_hint", language
                            )

                        verify_language("en")
                        controller.ide_list.selected_index = 0
                        controller.product_picker.selected_index = 1
                        controller.ide_path_box.text = "Unsaved IDE path"
                        controller.group_list.selected_index = 0
                        controller.group_name_box.text = "Несохранённый набор / Draft"
                        controller.group_lines_box.text = "invalid draft"
                        controller._group_ide_buttons["idea"].is_checked = False
                        draft = "-Xmx2g\n-Ddraft=true"
                        controller.options_editor.document.set_text(ui.TextSetOptions.NONE, draft)
                        # RichEditBox queues TextChanged until the next dispatcher turn.
                        controller.on_editor_changed(None, None)
                        assert controller._editor_dirty

                        def verify_drafts():
                            assert controller.ide_path_box.text == "Unsaved IDE path"
                            assert controller.product_picker.selected_index == 1
                            assert controller.group_name_box.text == "Несохранённый набор / Draft"
                            assert controller.group_lines_box.text == "invalid draft"
                            assert not controller._group_ide_buttons["idea"].is_checked
                            assert controller._selected_group_id == "common"
                            assert controller._editor_text() == draft
                            assert controller._editor_dirty
                            assert controller.save_panel.visibility == ui.Visibility.VISIBLE
                            assert vmoptions.read_text(encoding="utf-8") == "-Xmx2g\n"

                        controller.on_russian_language(None, None)
                        verify_language("ru")
                        verify_drafts()
                        assert controller.group_validation.text == translate(
                            "line_needs_dash", "ru"
                        )
                        assert controller.store.load()["settings"]["language"] == "ru"
                        assert controller._error_text(
                            ui.LocalizedOSError("shortcut_failed")
                        ) == translate("shortcut_failed", "ru")
                        assert controller.status_info.message == translate("language_changed", "ru")
                        try:
                            controller.on_sync_all(None, None)
                        except ValueError as error:
                            assert str(error) == translate("save_manual_first", "ru")
                        else:
                            raise AssertionError("Synchronization must protect unsaved edits")

                        reopened_window = ui.XamlReader.load(
                            (ROOT / "jetbrains_vmoptions_tuner" / "main_window.xaml").read_text(
                                encoding="utf-8"
                            )
                        ).as_(ui.Window)
                        try:
                            reopened = ui.MainController(reopened_window, store, ROOT / "main.py")
                            reopened.initialize()
                            assert reopened.language == "ru"
                            assert unbox_string(reopened.sync_all_top.content) == translate(
                                "sync_all", "ru"
                            )
                            assert reopened.russian_language_button.is_checked
                            reopened_window.activate()
                        finally:
                            reopened_window.close()

                        controller.on_english_language(None, None)
                        verify_language("en")
                        verify_drafts()
                        assert controller.store.load()["settings"]["language"] == "en"
                        controller.english_language_button.is_checked = False
                        controller.on_english_language(None, None)
                        assert controller.english_language_button.is_checked
                        with patch.object(
                            controller.store, "save", side_effect=OSError("Read-only settings")
                        ):
                            try:
                                controller.on_russian_language(None, None)
                            except OSError:
                                pass
                            else:
                                raise AssertionError("Failed preference save must be reported")
                        verify_language("en")
                        verify_drafts()
                        assert controller.config["settings"]["language"] == "en"

                        assert controller.desktop_shortcut_toggle.is_on
                        assert desktop_shortcut.is_enabled()
                        controller.desktop_shortcut_toggle.is_on = False
                        assert not desktop_shortcut.is_enabled()
                        assert not controller.store.load()["settings"]["desktop_shortcut"]
                        controller.desktop_shortcut_toggle.is_on = True
                        assert desktop_shortcut.is_enabled()
                        assert controller.store.load()["settings"]["desktop_shortcut"]
                        for index, suffix in ((2, "-white"), (1, "")):
                            controller.theme_picker.selected_index = index
                            controller.apply_appearance(save=False)
                            for name, image in (
                                ("github", controller.github_icon),
                                ("codex", controller.codex_icon),
                            ):
                                uri = image.source.as_(ui.SvgImageSource).uri_source.absolute_uri
                                assert uri.endswith(f"/{name}{suffix}.svg"), uri
                        print(
                            "PASS: WinUI, author/repository links, branding SVG, light/dark marks, ENG/RUS and persistence, unsaved drafts, desktop toggle",
                            flush=True,
                        )
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
        vmoptions = temp_root / "idea.vmoptions"
        vmoptions.write_text("-Xmx2g\n", encoding="utf-8")
        config["ides"] = [{"id": "idea", "product": "idea", "path": str(vmoptions)}]
        config["groups"] = [
            {"id": "common", "name": "Common", "lines": ["-Drequired=true"], "ide_ids": ["idea"]}
        ]
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
