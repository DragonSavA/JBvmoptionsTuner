"""Background synchronization entry point."""

from __future__ import annotations

from pathlib import Path

from .config import ConfigStore
from .sync import now_iso, synchronize_all


def run_background(config_path: Path | None = None) -> int:
    store = ConfigStore(config_path)
    config = store.load()
    report = synchronize_all(config)
    # An automatic timestamp represents a useful repair, not merely a login.
    if report.changed:
        config["last_auto_sync"] = now_iso()
        store.save(config)
    return 1 if report.errors else 0

