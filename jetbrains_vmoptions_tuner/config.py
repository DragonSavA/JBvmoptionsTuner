"""JSON configuration persistence with small, explicit schema validation."""

from __future__ import annotations

import json
import os
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any

from .localization import DEFAULT_LANGUAGE, normalize_language

APP_DIR_NAME = "JetBrainsVmoptionsTuner"
CONFIG_FILE_NAME = "config.json"
SCHEMA_VERSION = 1


def default_config() -> dict[str, Any]:
    return {
        "version": SCHEMA_VERSION,
        "settings": {
            "language": DEFAULT_LANGUAGE,
            "theme": "system",
            "accent_color": "#4F7CFF",
            "desktop_shortcut": True,
            "first_run_completed": False,
        },
        "ides": [],
        "groups": [],
        "last_manual_sync": None,
        "last_auto_sync": None,
    }


def get_config_path() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / APP_DIR_NAME / CONFIG_FILE_NAME
    # This fallback keeps the core testable outside Windows and gives a useful
    # error-free behavior for portable Python installations.
    return Path.home() / ".config" / APP_DIR_NAME / CONFIG_FILE_NAME


def _merge_and_sanitize(raw: object) -> dict[str, Any]:
    cfg = default_config()
    if not isinstance(raw, dict):
        return cfg

    settings = raw.get("settings")
    if isinstance(settings, dict):
        cfg["settings"]["language"] = normalize_language(settings.get("language"))
        theme = settings.get("theme")
        if theme in {"system", "light", "dark"}:
            cfg["settings"]["theme"] = theme
        accent = settings.get("accent_color")
        if isinstance(accent, str):
            cfg["settings"]["accent_color"] = accent
        desktop_shortcut = settings.get("desktop_shortcut")
        if isinstance(desktop_shortcut, bool):
            cfg["settings"]["desktop_shortcut"] = desktop_shortcut
        cfg["settings"]["first_run_completed"] = bool(settings.get("first_run_completed", False))

    ides = raw.get("ides")
    if isinstance(ides, list):
        cfg["ides"] = [deepcopy(item) for item in ides if isinstance(item, dict)]

    groups = raw.get("groups")
    if isinstance(groups, list):
        cfg["groups"] = [deepcopy(item) for item in groups if isinstance(item, dict)]

    for key in ("last_manual_sync", "last_auto_sync"):
        value = raw.get(key)
        cfg[key] = value if isinstance(value, str) else None
    return cfg


class ConfigStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or get_config_path()

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return default_config()
        try:
            with self.path.open("r", encoding="utf-8") as stream:
                return _merge_and_sanitize(json.load(stream))
        except (OSError, UnicodeError, json.JSONDecodeError):
            # Preserve a broken file for manual recovery and start from safe
            # defaults.  We never overwrite it merely by loading.
            return default_config()

    def save(self, config: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(config, ensure_ascii=False, indent=2) + "\n"
        handle, temporary_name = tempfile.mkstemp(
            prefix=f".{self.path.name}.", suffix=".tmp", dir=self.path.parent
        )
        try:
            with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary_name, self.path)
        except BaseException:
            try:
                os.unlink(temporary_name)
            except OSError:
                pass
            raise
