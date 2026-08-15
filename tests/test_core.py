from __future__ import annotations

import json
import tempfile
import tomllib
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from jetbrains_vmoptions_tuner import __version__
from jetbrains_vmoptions_tuner.background import run_background
from jetbrains_vmoptions_tuner.catalog import PRODUCTS
from jetbrains_vmoptions_tuner.config import ConfigStore, default_config
from jetbrains_vmoptions_tuner.sync import (
    TextFile,
    append_missing,
    missing_lines,
    read_text_file,
    synchronize_all,
    validate_option_lines,
)


class ValidationTests(unittest.TestCase):
    def test_rejects_lines_without_dash_and_deduplicates(self) -> None:
        lines, errors = validate_option_lines("-Xmx4g\ninvalid\n-Xmx4g\n-Dfoo=true")
        self.assertEqual(lines, ["-Xmx4g", "-Dfoo=true"])
        self.assertEqual(len(errors), 1)
        self.assertIn("Строка 2", errors[0])

    def test_empty_group_is_rejected(self) -> None:
        self.assertTrue(validate_option_lines("\n\n")[1])


class FileSyncTests(unittest.TestCase):
    def test_append_missing_preserves_crlf(self) -> None:
        source = TextFile("-Xmx2g\r\n", newline="\r\n")
        updated, added = append_missing(source, ["-Xmx2g", "-Dfoo=true"])
        self.assertEqual(added, ["-Dfoo=true"])
        self.assertEqual(updated.text, "-Xmx2g\r\n-Dfoo=true\r\n")

    def test_whitespace_is_ignored_when_comparing(self) -> None:
        self.assertEqual(missing_lines("  -Xmx2g  \n", ["-Xmx2g"]), [])

    def test_sync_all_updates_only_bound_ides(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "idea.vmoptions"
            second = root / "rider.vmoptions"
            first.write_text("-Xmx2g\n", encoding="utf-8")
            second.write_text("-Xmx2g\n", encoding="utf-8")
            config = default_config()
            config["ides"] = [
                {"id": "idea", "product": "idea", "path": str(first)},
                {"id": "rider", "product": "rider", "path": str(second)},
            ]
            config["groups"] = [
                {"id": "common", "name": "Common", "lines": ["-Dfoo=true"], "ide_ids": ["idea"]}
            ]
            report = synchronize_all(config)
            self.assertEqual(report.changed_count, 1)
            self.assertIn("-Dfoo=true", first.read_text(encoding="utf-8"))
            self.assertNotIn("-Dfoo=true", second.read_text(encoding="utf-8"))

    def test_utf8_bom_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test.vmoptions"
            path.write_bytes(b"\xef\xbb\xbf-Xmx2g\r\n")
            loaded = read_text_file(path)
            updated, _ = append_missing(loaded, ["-Dfoo=true"])
            from jetbrains_vmoptions_tuner.sync import write_text_file

            write_text_file(path, updated)
            self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"))


class ConfigAndBackgroundTests(unittest.TestCase):
    def test_invalid_config_falls_back_to_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text("not-json", encoding="utf-8")
            self.assertEqual(ConfigStore(path).load()["version"], 1)

    def test_auto_timestamp_changes_only_when_file_changes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            vmoptions = root / "idea.vmoptions"
            vmoptions.write_text("-Xmx2g\n", encoding="utf-8")
            config_path = root / "config.json"
            config = default_config()
            config["ides"] = [{"id": "idea", "product": "idea", "path": str(vmoptions)}]
            config["groups"] = [
                {"id": "g", "name": "G", "lines": ["-Dfoo=true"], "ide_ids": ["idea"]}
            ]
            ConfigStore(config_path).save(config)

            self.assertEqual(run_background(config_path), 0)
            first_timestamp = json.loads(config_path.read_text(encoding="utf-8"))["last_auto_sync"]
            self.assertIsNotNone(first_timestamp)

            self.assertEqual(run_background(config_path), 0)
            second_timestamp = json.loads(config_path.read_text(encoding="utf-8"))["last_auto_sync"]
            self.assertEqual(second_timestamp, first_timestamp)


class AssetsAndMetadataTests(unittest.TestCase):
    def test_declared_product_icons_exist_and_are_valid_svg(self) -> None:
        asset_dir = Path(__file__).parents[1] / "jetbrains_vmoptions_tuner" / "assets"
        declared = {product.icon for product in PRODUCTS if product.icon}
        available = {path.name for path in asset_dir.glob("*.svg")}
        self.assertEqual(declared, available)
        self.assertEqual([product.key for product in PRODUCTS if not product.icon], ["client"])
        for icon in declared:
            root = ET.parse(asset_dir / icon).getroot()
            self.assertTrue(root.tag.endswith("svg"))

    def test_package_versions_match(self) -> None:
        project_path = Path(__file__).parents[1] / "pyproject.toml"
        project = tomllib.loads(project_path.read_text(encoding="utf-8"))
        self.assertEqual(project["project"]["version"], __version__)


if __name__ == "__main__":
    unittest.main()
