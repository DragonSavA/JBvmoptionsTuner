"""Current-user desktop shortcut, including redirected/OneDrive desktops."""

from __future__ import annotations

import ctypes
import os
import subprocess
from ctypes import wintypes
from pathlib import Path
from typing import Any
from uuid import UUID

from .config import ConfigStore


SHORTCUT_NAME = "vmoptions Tuner.lnk"
PACKAGE_DIR = Path(__file__).resolve().parent
APP_ICON = PACKAGE_DIR / "assets" / "vmopt.ico"
APP_SVG = PACKAGE_DIR / "assets" / "vmopt.svg"


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", ctypes.c_ubyte * 8),
    ]


def powershell_executable() -> Path:
    return Path(os.environ.get("SystemRoot", r"C:\Windows")) / (
        r"System32\WindowsPowerShell\v1.0\powershell.exe"
    )


def get_desktop_path() -> Path:
    if os.name != "nt":
        raise OSError("Ярлык на рабочем столе поддерживается только в Windows.")
    # FOLDERID_Desktop resolves the actual current-user desktop, even when it
    # has been redirected. USERPROFILE/Desktop is not reliable for OneDrive.
    folder_id = GUID.from_buffer_copy(UUID("B4BFCC3A-DB2C-424C-B029-7FE99A87C641").bytes_le)
    shell32 = ctypes.WinDLL("shell32", use_last_error=True)
    ole32 = ctypes.WinDLL("ole32", use_last_error=True)
    shell32.SHGetKnownFolderPath.argtypes = [
        ctypes.POINTER(GUID),
        wintypes.DWORD,
        wintypes.HANDLE,
        ctypes.POINTER(ctypes.c_void_p),
    ]
    shell32.SHGetKnownFolderPath.restype = ctypes.c_long
    ole32.CoTaskMemFree.argtypes = [ctypes.c_void_p]
    ole32.CoTaskMemFree.restype = None
    buffer = ctypes.c_void_p()
    result = shell32.SHGetKnownFolderPath(ctypes.byref(folder_id), 0, None, ctypes.byref(buffer))
    try:
        if result < 0:
            raise OSError(f"Не удалось найти рабочий стол (HRESULT 0x{result & 0xFFFFFFFF:08X}).")
        return Path(ctypes.wstring_at(buffer))
    finally:
        if buffer.value:
            ole32.CoTaskMemFree(buffer)


def get_shortcut_path() -> Path:
    return get_desktop_path() / SHORTCUT_NAME


def is_enabled() -> bool:
    return get_shortcut_path().is_file()


def enable(entry_script: Path) -> None:
    launcher = entry_script.resolve().with_name("start.bat")
    if not launcher.is_file():
        raise OSError(f"Не найден файл запуска: {launcher}")
    if not APP_ICON.is_file():
        raise OSError(f"Не найдена иконка приложения: {APP_ICON}")
    shortcut = get_shortcut_path()
    shortcut.parent.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    # Paths are data, never interpolated into PowerShell source code. This
    # also handles Cyrillic, apostrophes, ampersands and spaces in paths.
    env.update(
        {
            "VMOPT_SHORTCUT_PATH": str(shortcut),
            "VMOPT_LAUNCHER_PATH": str(launcher),
            "VMOPT_ICON_PATH": str(APP_ICON),
        }
    )
    try:
        result = subprocess.run(
            [
                str(powershell_executable()),
                "-NoLogo",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(PACKAGE_DIR / "desktop_shortcut.ps1"),
            ],
            env=env,
            check=False,
            capture_output=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            timeout=30,
        )
    except subprocess.TimeoutExpired as error:
        raise OSError("Windows не завершила создание ярлыка за 30 секунд.") from error
    if result.returncode or not shortcut.is_file():
        raise OSError("Windows не удалось создать ярлык vmoptions Tuner на рабочем столе.")


def disable() -> None:
    get_shortcut_path().unlink(missing_ok=True)


def reconcile(config: dict[str, Any], entry_script: Path) -> None:
    """Repair a moved/missing shortcut, or remove it when explicitly disabled."""
    if config["settings"]["desktop_shortcut"]:
        enable(entry_script)
    else:
        disable()


def set_enabled(
    enabled: bool, config: dict[str, Any], store: ConfigStore, entry_script: Path
) -> None:
    previous = config["settings"]["desktop_shortcut"]
    if enabled:
        enable(entry_script)
    else:
        disable()
    config["settings"]["desktop_shortcut"] = enabled
    try:
        store.save(config)
    except OSError:
        config["settings"]["desktop_shortcut"] = previous
        try:
            reconcile(config, entry_script)
        except OSError:
            pass
        raise
