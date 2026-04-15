from __future__ import annotations

import ctypes
from ctypes import wintypes
import argparse
from dataclasses import asdict, dataclass
import json
from typing import Any

import comtypes
import comtypes.client
from comtypes import GUID, POINTER
from comtypes.automation import IDispatch
import win32gui
import win32process


OBJIDS = {
    "OBJID_WINDOW": 0x00000000,
    "OBJID_SYSMENU": 0xFFFFFFFF,
    "OBJID_TITLEBAR": 0xFFFFFFFE,
    "OBJID_MENU": 0xFFFFFFFD,
    "OBJID_CLIENT": 0xFFFFFFFC,
    "OBJID_VSCROLL": 0xFFFFFFFB,
    "OBJID_HSCROLL": 0xFFFFFFFA,
    "OBJID_SIZEGRIP": 0xFFFFFFF9,
    "OBJID_CARET": 0xFFFFFFF8,
    "OBJID_CURSOR": 0xFFFFFFF7,
    "OBJID_ALERT": 0xFFFFFFF6,
    "OBJID_SOUND": 0xFFFFFFF5,
    "OBJID_QUERYCLASSNAMEIDX": 0xFFFFFFF4,
    "OBJID_NATIVEOM": 0xFFFFFFF0,
}


@dataclass(frozen=True)
class WindowAutomationProbe:
    hwnd: int
    pid: int
    title: str
    class_name: str
    objid_name: str
    ok: bool
    com_type: str | None = None
    attrs: list[str] | None = None
    error: str | None = None


oleacc = ctypes.OleDLL("oleacc")
HRESULT = ctypes.c_long
oleacc.AccessibleObjectFromWindow.argtypes = [
    wintypes.HWND,
    wintypes.DWORD,
    ctypes.POINTER(GUID),
    ctypes.POINTER(ctypes.c_void_p),
]
oleacc.AccessibleObjectFromWindow.restype = HRESULT


def _probe_window(hwnd: int, objid_name: str, objid: int) -> WindowAutomationProbe:
    pid = win32process.GetWindowThreadProcessId(hwnd)[1]
    title = win32gui.GetWindowText(hwnd)
    class_name = win32gui.GetClassName(hwnd)
    dispatch = POINTER(IDispatch)()

    try:
        hr = oleacc.AccessibleObjectFromWindow(
            hwnd,
            objid & 0xFFFFFFFF,
            ctypes.byref(IDispatch._iid_),
            ctypes.byref(dispatch),
        )
    except OSError as exc:
        return WindowAutomationProbe(
            hwnd=hwnd,
            pid=pid,
            title=title,
            class_name=class_name,
            objid_name=objid_name,
            ok=False,
            error=f"{exc.__class__.__name__}: {exc}",
        )
    if hr != 0:
        return WindowAutomationProbe(
            hwnd=hwnd,
            pid=pid,
            title=title,
            class_name=class_name,
            objid_name=objid_name,
            ok=False,
            error=f"HRESULT=0x{ctypes.c_uint32(hr).value:08X}",
        )

    try:
        best = comtypes.client.GetBestInterface(dispatch)
        attrs = [name for name in dir(best) if not name.startswith("_")]
        return WindowAutomationProbe(
            hwnd=hwnd,
            pid=pid,
            title=title,
            class_name=class_name,
            objid_name=objid_name,
            ok=True,
            com_type=type(best).__name__,
            attrs=attrs[:40],
        )
    except Exception as exc:  # pragma: no cover - exploratory probe
        return WindowAutomationProbe(
            hwnd=hwnd,
            pid=pid,
            title=title,
            class_name=class_name,
            objid_name=objid_name,
            ok=False,
            error=str(exc),
        )


def _iter_radan_windows() -> list[int]:
    matches: list[int] = []

    def _callback(hwnd: int, param: list[int]) -> bool:
        title = win32gui.GetWindowText(hwnd)
        if not title:
            return True
        class_name = win32gui.GetClassName(hwnd)
        if "Mazak Smart System" in title or class_name.startswith("Afx:"):
            pid = win32process.GetWindowThreadProcessId(hwnd)[1]
            try:
                _, found_pid = win32process.GetWindowThreadProcessId(hwnd)
            except Exception:
                return True
            if pid == found_pid:
                param.append(hwnd)
        return True

    win32gui.EnumWindows(_callback, matches)
    unique: list[int] = []
    seen: set[int] = set()
    for hwnd in matches:
        if hwnd not in seen:
            seen.add(hwnd)
            unique.append(hwnd)
    return unique


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe live RADAN windows for window-handle automation objects.")
    parser.add_argument(
        "--all-objids",
        action="store_true",
        help="Probe every known object id instead of just WINDOW/CLIENT/NATIVEOM.",
    )
    args = parser.parse_args()

    selected_objids = OBJIDS
    if not args.all_objids:
        selected_objids = {
            "OBJID_WINDOW": OBJIDS["OBJID_WINDOW"],
            "OBJID_CLIENT": OBJIDS["OBJID_CLIENT"],
            "OBJID_NATIVEOM": OBJIDS["OBJID_NATIVEOM"],
        }

    comtypes.CoInitialize()
    try:
        windows = _iter_radan_windows()
        payload: dict[str, Any] = {"window_count": len(windows), "probes": []}
        for hwnd in windows:
            for objid_name, objid in selected_objids.items():
                payload["probes"].append(asdict(_probe_window(hwnd, objid_name, objid)))
        print(json.dumps(payload, indent=2))
        return 0
    finally:
        comtypes.CoUninitialize()


if __name__ == "__main__":
    raise SystemExit(main())
