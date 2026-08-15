"""Application entry point."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="JetBrains vmoptions Tuner")
    parser.add_argument(
        "--background",
        action="store_true",
        help="синхронизировать файлы без открытия окна",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.background:
        from jetbrains_vmoptions_tuner.background import run_background

        return run_background()

    if sys.platform != "win32":
        print("UI JetBrains vmoptions Tuner запускается только в Windows 11.", file=sys.stderr)
        return 2

    from jetbrains_vmoptions_tuner.ui import run_ui

    return run_ui(Path(__file__).resolve())


if __name__ == "__main__":
    raise SystemExit(main())
