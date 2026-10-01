from __future__ import annotations

import json
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from string import Formatter
from unittest.mock import patch

from jetbrains_vmoptions_tuner import native_picker
from jetbrains_vmoptions_tuner.config import ConfigStore, default_config
from jetbrains_vmoptions_tuner.localization import (
    MESSAGES,
    XAML_STRINGS,
    LocalizedOSError,
    translate,
)
from jetbrains_vmoptions_tuner.sync import synchronize_all, validate_option_lines


class LanguageSettingsTests(unittest.TestCase):
    def test_first_launch_and_legacy_configs_default_to_english(self) -> None:
        self.assertEqual(default_config()["settings"]["language"], "en")
        with tempfile.TemporaryDirectory() as directory:
            store = ConfigStore(Path(directory) / "config.json")
            self.assertEqual(store.load()["settings"]["language"], "en")
            legacy = default_config()
            del legacy["settings"]["language"]
            legacy["settings"]["desktop_shortcut"] = False
            legacy["groups"] = [{"id": "g", "name": "Мой набор", "lines": ["-Xmx4g"]}]
            store.save(legacy)
            loaded = store.load()
            self.assertEqual(loaded["settings"]["language"], "en")
            self.assertFalse(loaded["settings"]["desktop_shortcut"])
            self.assertEqual(loaded["groups"], legacy["groups"])

    def test_language_is_persisted_and_invalid_values_fall_back_to_english(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = ConfigStore(Path(directory) / "config.json")
            for language, expected in (
                ("ru", "ru"),
                ("en", "en"),
                ("de", "en"),
                ([], "en"),
                (None, "en"),
            ):
                with self.subTest(language=language):
                    store.path.write_text(
                        json.dumps({"settings": {"language": language}}), encoding="utf-8"
                    )
                    self.assertEqual(store.load()["settings"]["language"], expected)


class TranslationTests(unittest.TestCase):
    def test_languages_have_matching_messages_and_format_parameters(self) -> None:
        self.assertEqual(MESSAGES["en"].keys(), MESSAGES["ru"].keys())
        formatter = Formatter()
        for key, english in MESSAGES["en"].items():
            with self.subTest(key=key):
                fields = {field for _, field, _, _ in formatter.parse(english) if field}
                russian = MESSAGES["ru"][key]
                self.assertEqual(
                    fields, {field for _, field, _, _ in formatter.parse(russian) if field}
                )
                values = {
                    field: 2 if field in {"count", "number", "hresult"} else "Example"
                    for field in fields
                }
                for language in MESSAGES:
                    self.assertTrue(translate(key, language, **values))
        self.assertEqual(translate("settings", "unsupported"), "Settings")

    def test_xaml_bindings_match_controls_and_cover_all_translatable_text(self) -> None:
        xaml = Path(__file__).parents[1] / "jetbrains_vmoptions_tuner" / "main_window.xaml"
        elements = list(ET.parse(xaml).iter())
        name_attr = "{http://schemas.microsoft.com/winfx/2006/xaml}Name"
        named = {
            element.attrib[name_attr]: element
            for element in elements
            if name_attr in element.attrib
        }
        attributes = {
            "text": "Text",
            "content": "Content",
            "header": "Header",
            "placeholder_text": "PlaceholderText",
            "on_content": "OnContent",
            "off_content": "OffContent",
        }
        bound = set()
        for control, name, prop, key in XAML_STRINGS:
            with self.subTest(name=name, property=prop):
                element = named[name]
                self.assertEqual(element.tag.rsplit("}", 1)[-1], control)
                self.assertEqual(element.attrib[attributes[prop]], translate(key))
                bound.add((name, attributes[prop]))
        invariant = {
            "vmoptions Tuner",
            "ENG",
            "RUS",
            "|",
            "IDE",
            "#00FF00",
            "D:\\Apps\\JetBrains\\...\\product64.exe.vmoptions",
            "-Xmx4096m\n-Dexample=true",
        }
        for element in elements:
            for attr in attributes.values():
                text = element.attrib.get(attr)
                if text and text not in invariant:
                    self.assertIn((element.attrib.get(name_attr), attr), bound)

    def test_validation_and_sync_errors_use_the_selected_language(self) -> None:
        for language, prefix in (("en", "Line 2"), ("ru", "Строка 2")):
            with self.subTest(language=language):
                lines, errors = validate_option_lines("-Xmx4g\ninvalid", language)
                self.assertEqual(lines, ["-Xmx4g"])
                self.assertTrue(errors[0].startswith(prefix))
                self.assertEqual(
                    validate_option_lines("", language)[1],
                    [translate("options_required", language)],
                )
                config = default_config()
                config["settings"]["language"] = language
                config["ides"] = [{"id": "idea", "path": "unused.vmoptions"}]
                config["groups"] = [{"ide_ids": ["idea"], "lines": ["-Xmx4g", "invalid"]}]
                self.assertTrue(synchronize_all(config).errors[0].error.startswith(prefix))

    def test_os_errors_can_be_translated_when_displayed(self) -> None:
        error = LocalizedOSError("launcher_not_found", path="Example/start.bat")
        self.assertIsInstance(error, OSError)
        self.assertEqual(str(error), "Launcher file not found: Example/start.bat")
        self.assertEqual(error.message("ru"), "Не найден файл запуска: Example/start.bat")

    @unittest.skipUnless(hasattr(native_picker.ctypes, "windll"), "Requires Windows")
    def test_native_picker_uses_the_selected_language(self) -> None:
        for language in MESSAGES:

            def cancel(dialog_pointer):
                dialog = dialog_pointer._obj
                self.assertEqual(dialog.lpstrTitle, translate("picker_title", language))
                self.assertEqual(dialog.lpstrDefExt, "vmoptions")
                return 0

            with self.subTest(language=language):
                with patch.object(
                    native_picker.ctypes.windll.comdlg32, "GetOpenFileNameW", side_effect=cancel
                ):
                    self.assertIsNone(native_picker.choose_vmoptions_file(language))


if __name__ == "__main__":
    unittest.main()
