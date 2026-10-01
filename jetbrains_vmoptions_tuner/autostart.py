"""Current-user Windows autostart registration."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from .localization import LocalizedOSError

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "JetBrainsVmoptionsTuner"


def _winreg():
    if os.name != "nt":
        return None
    import winreg

    return winreg


def build_autostart_command(entry_script: Path | None = None) -> str:
    if getattr(sys, "frozen", False):
        parts = [str(Path(sys.executable).resolve()), "--background"]
    else:
        script = (entry_script or Path(sys.argv[0])).resolve()
        executable = Path(sys.executable).resolve()
        pythonw = executable.with_name("pythonw.exe")
        if pythonw.exists():
            executable = pythonw
        parts = [str(executable), str(script), "--background"]
    return subprocess.list2cmdline(parts)


def get_registered_command() -> str | None:
    winreg = _winreg()
    if winreg is None:
        return None
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            value, _ = winreg.QueryValueEx(key, VALUE_NAME)
        return str(value)
    except OSError:
        return None


def is_enabled() -> bool:
    return get_registered_command() is not None


def enable(entry_script: Path | None = None) -> None:
    winreg = _winreg()
    if winreg is None:
        raise LocalizedOSError("autostart_windows_only")
    command = build_autostart_command(entry_script)
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
        winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, command)


def disable() -> None:
    winreg = _winreg()
    if winreg is None:
        raise LocalizedOSError("autostart_windows_only")
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, VALUE_NAME)
    except FileNotFoundError:
        pass
