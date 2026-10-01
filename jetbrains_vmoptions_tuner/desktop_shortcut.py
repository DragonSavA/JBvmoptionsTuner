"""Current-user desktop shortcut, including redirected/OneDrive desktops."""

from __future__ import annotations

import ctypes
import os
from contextlib import contextmanager
from ctypes import wintypes
from pathlib import Path
from typing import Any, Iterator
from uuid import UUID

from .config import ConfigStore
from .localization import LocalizedOSError


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


def _com_call(interface: ctypes.c_void_p, slot: int, argtypes: tuple, *args: Any) -> int:
    """Call a COM vtable method with the Windows stdcall ABI."""
    vtable = ctypes.cast(interface, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    method = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, *argtypes)(vtable[slot])
    return method(interface, *args)


def _check_hresult(result: int, operation: str) -> None:
    if result < 0:
        raise LocalizedOSError(
            "shortcut_failed_hresult", operation=operation, hresult=result & 0xFFFFFFFF
        )


@contextmanager
def _shell_link() -> Iterator[tuple[ctypes.c_void_p, ctypes.c_void_p]]:
    """Own IShellLinkW/IPersistFile references without changing the caller's apartment."""
    ole32 = ctypes.WinDLL("ole32")
    ole32.CoInitializeEx.argtypes = [ctypes.c_void_p, wintypes.DWORD]
    ole32.CoInitializeEx.restype = ctypes.c_long
    ole32.CoUninitialize.argtypes = []
    ole32.CoUninitialize.restype = None
    ole32.CoCreateInstance.argtypes = [
        ctypes.POINTER(GUID),
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(GUID),
        ctypes.POINTER(ctypes.c_void_p),
    ]
    ole32.CoCreateInstance.restype = ctypes.c_long
    initialized = ole32.CoInitializeEx(None, 2)  # COINIT_APARTMENTTHREADED
    # WinUI/PyWinRT may already have initialized COM with another model.
    # RPC_E_CHANGED_MODE leaves that apartment intact and needs no uninitialize.
    if initialized & 0xFFFFFFFF != 0x80010106:
        _check_hresult(initialized, "CoInitializeEx")
    link = ctypes.c_void_p()
    persist = ctypes.c_void_p()
    try:
        clsid = GUID.from_buffer_copy(UUID("00021401-0000-0000-C000-000000000046").bytes_le)
        iid_link = GUID.from_buffer_copy(UUID("000214F9-0000-0000-C000-000000000046").bytes_le)
        iid_persist = GUID.from_buffer_copy(UUID("0000010B-0000-0000-C000-000000000046").bytes_le)
        _check_hresult(
            ole32.CoCreateInstance(
                ctypes.byref(clsid), None, 1, ctypes.byref(iid_link), ctypes.byref(link)
            ),  # CLSCTX_INPROC_SERVER
            "CoCreateInstance(IShellLinkW)",
        )
        _check_hresult(
            _com_call(
                link,
                0,  # IUnknown.QueryInterface
                (ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p)),
                ctypes.byref(iid_persist),
                ctypes.byref(persist),
            ),
            "QueryInterface(IPersistFile)",
        )
        yield link, persist
    finally:
        if persist.value:
            _com_call(persist, 2, ())  # IUnknown.Release
        if link.value:
            _com_call(link, 2, ())
        if initialized >= 0:  # Balance S_OK and S_FALSE, but not RPC_E_CHANGED_MODE.
            ole32.CoUninitialize()


def powershell_executable() -> Path:
    return Path(os.environ.get("SystemRoot", r"C:\Windows")) / (
        r"System32\WindowsPowerShell\v1.0\powershell.exe"
    )


def get_desktop_path() -> Path:
    if os.name != "nt":
        raise LocalizedOSError("desktop_windows_only")
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
            raise LocalizedOSError("desktop_not_found", hresult=result & 0xFFFFFFFF)
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
        raise LocalizedOSError("launcher_not_found", path=launcher)
    if not APP_ICON.is_file():
        raise LocalizedOSError("icon_not_found", path=APP_ICON)
    shortcut = get_shortcut_path()
    shortcut.parent.mkdir(parents=True, exist_ok=True)
    # WScript.Shell uses the system ANSI code page for shortcut filenames.
    # IShellLinkW and IPersistFile use UTF-16 for every path, including Save.
    with _shell_link() as (link, persist):
        for slot, operation, value in (
            (20, "SetPath", str(launcher)),
            (9, "SetWorkingDirectory", str(launcher.parent)),
            (7, "SetDescription", "Launch vmoptions Tuner"),
        ):
            _check_hresult(
                _com_call(link, slot, (wintypes.LPCWSTR,), value), f"IShellLinkW.{operation}"
            )
        _check_hresult(
            _com_call(link, 17, (wintypes.LPCWSTR, ctypes.c_int), str(APP_ICON), 0),
            "IShellLinkW.SetIconLocation",
        )
        _check_hresult(
            _com_call(link, 15, (ctypes.c_int,), 1),
            "IShellLinkW.SetShowCmd",  # SW_SHOWNORMAL
        )
        _check_hresult(
            _com_call(persist, 6, (wintypes.LPCWSTR, wintypes.BOOL), str(shortcut), True),
            "IPersistFile.Save",
        )
    if not shortcut.is_file():
        raise LocalizedOSError("shortcut_failed")


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
