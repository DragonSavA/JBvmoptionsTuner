"""Dependency and desktop setup used by start.bat; never imported by the UI."""

from __future__ import annotations

import importlib.util
import inspect
import subprocess
import sys
import sysconfig
from pathlib import Path

from . import desktop_shortcut
from .config import ConfigStore


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def ensure_python_dependencies() -> None:
    if importlib.util.find_spec("pip") is None:
        subprocess.run([sys.executable, "-m", "ensurepip", "--upgrade"], check=True)
    # pip checks every declared version and installs only missing/incompatible
    # dependencies. Satisfied requirements also work without Internet access.
    print("Checking Python dependencies...", flush=True)
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--quiet",
            "--disable-pip-version-check",
            "--only-binary=:all:",
            "-r",
            str(PROJECT_ROOT / "requirements.txt"),
        ],
        check=True,
    )
    subprocess.run([sys.executable, "-m", "pip", "check"], check=True)


def ensure_windows_runtime() -> None:
    from winui3.microsoft.windows.applicationmodel.dynamicdependency.bootstrap import initialize

    try:
        with initialize():
            return
    except OSError:
        release = inspect.signature(initialize).parameters["version"].default
    # The runtime release must match the installed PyWinRT projections;
    # installing only the newest Windows App Runtime may not satisfy them.
    print(f"Installing Windows App Runtime {release}...", flush=True)
    architecture = {"win32": "x86", "win-amd64": "x64", "win-arm64": "arm64"}[
        sysconfig.get_platform()
    ]
    subprocess.run(
        [
            str(desktop_shortcut.powershell_executable()),
            "-NoLogo",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(Path(__file__).with_name("install_runtime.ps1")),
            "-Release",
            release,
            "-Architecture",
            architecture,
        ],
        check=True,
    )
    with initialize():
        pass


def main() -> int:
    if sys.platform != "win32" or sys.version_info < (3, 13):
        print("Setup requires Windows and CPython 3.13+.", file=sys.stderr)
        return 2
    try:
        ensure_python_dependencies()
        ensure_windows_runtime()
    except (OSError, ImportError, subprocess.CalledProcessError) as error:
        print(f"Setup failed: {error}", file=sys.stderr)
        return 1
    try:
        desktop_shortcut.reconcile(ConfigStore().load(), PROJECT_ROOT / "main.py")
    except OSError as error:
        # A read-only desktop must not prevent launching the application.
        print(f"Desktop shortcut could not be updated: {error}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
