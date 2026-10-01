"""Application entry point."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="JetBrains vmoptions Tuner")
    parser.add_argument(
        "--background",
        action="store_true",
        help="synchronize files without opening the window",
    )
    return parser.parse_args()


def main() -> int:
    entry_script = Path(__file__).resolve()
    project_python = entry_script.parent / ".venv" / "Scripts" / "python.exe"
    if Path(sys.executable).name.lower() == "pythonw.exe":
        project_python = project_python.with_name("pythonw.exe")
    if os.name == "nt" and project_python.is_file():
        if Path(sys.executable).resolve() != project_python.resolve():
            # Direct `python path/to/main.py` uses the dependencies prepared by
            # start.bat, even if the shell's Python is a different installation.
            return subprocess.run(
                [str(project_python), str(entry_script), *sys.argv[1:]], check=False
            ).returncode
    if sys.version_info < (3, 13):
        print("Python 3.13+ is required. Run start.bat to set up the application.", file=sys.stderr)
        return 2
    args = parse_args()
    if args.background:
        from jetbrains_vmoptions_tuner.background import run_background

        return run_background()

    if sys.platform != "win32":
        print("The JetBrains vmoptions Tuner UI requires Windows 11.", file=sys.stderr)
        return 2

    from jetbrains_vmoptions_tuner.ui import run_ui

    return run_ui(entry_script)


if __name__ == "__main__":
    raise SystemExit(main())
