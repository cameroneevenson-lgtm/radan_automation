from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import datetime as dt
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import comtypes.client
import win32api
import win32con
import win32gui
import win32process
from comtypes import POINTER
from comtypes.automation import IDispatch


OBJID_CLIENT = 0xFFFFFFFC
SELFLAG_TAKEFOCUS = 0x1
SELFLAG_TAKESELECTION = 0x2

oleacc = ctypes.OleDLL("oleacc")
oleacc.AccessibleObjectFromWindow.argtypes = [
    wintypes.HWND,
    wintypes.DWORD,
    ctypes.POINTER(type(IDispatch._iid_)),
    ctypes.POINTER(ctypes.c_void_p),
]
oleacc.AccessibleObjectFromWindow.restype = ctypes.c_long


def _top_level_windows_for_pid(process_id: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    def _callback(hwnd: int, _: object) -> bool:
        try:
            found_pid = win32process.GetWindowThreadProcessId(hwnd)[1]
        except Exception:
            return True
        if found_pid != process_id:
            return True
        rows.append(
            {
                "hwnd": hwnd,
                "title": win32gui.GetWindowText(hwnd),
                "class_name": win32gui.GetClassName(hwnd),
                "visible": bool(win32gui.IsWindowVisible(hwnd)),
                "enabled": bool(win32gui.IsWindowEnabled(hwnd)),
                "owner": win32gui.GetWindow(hwnd, 4),
                "rect": win32gui.GetWindowRect(hwnd),
            }
        )
        return True

    win32gui.EnumWindows(_callback, None)
    return rows


def _visible_windows_for_pid(process_id: int) -> list[dict[str, Any]]:
    rows = [row for row in _top_level_windows_for_pid(process_id) if row["visible"]]
    rows.sort(key=lambda row: (row["title"], row["hwnd"]))
    return rows


def _find_visible_frame(process_id: int, title_contains: str) -> dict[str, Any] | None:
    lowered = title_contains.lower()
    for row in _visible_windows_for_pid(process_id):
        if row["class_name"] != "myframe":
            continue
        if lowered in row["title"].lower():
            return row
    return None


def _enum_children(hwnd: int) -> list[int]:
    children: list[int] = []
    win32gui.EnumChildWindows(hwnd, lambda child, param: param.append(child) or True, children)
    return children


def _walk_children(hwnd: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    def _walk(node: int, depth: int = 0) -> None:
        for child in _enum_children(node):
            try:
                row = {
                    "depth": depth,
                    "hwnd": child,
                    "class_name": win32gui.GetClassName(child),
                    "text": win32gui.GetWindowText(child),
                    "visible": bool(win32gui.IsWindowVisible(child)),
                    "enabled": bool(win32gui.IsWindowEnabled(child)),
                    "rect": win32gui.GetWindowRect(child),
                }
            except Exception:
                continue
            rows.append(row)
            _walk(child, depth + 1)

    _walk(hwnd)
    return rows


def _find_visible_child_by_text(hwnd: int, text: str) -> dict[str, Any] | None:
    for row in _walk_children(hwnd):
        if not row["visible"] or not row["enabled"]:
            continue
        if row["text"] == text:
            return row
    return None


def _find_parts_list_view(nest_hwnd: int) -> int:
    parts_area = _find_visible_child_by_text(nest_hwnd, "rpr_parts_list_controls")
    if parts_area is None:
        raise RuntimeError("Could not find the visible parts-list control area.")

    for row in _walk_children(parts_area["hwnd"]):
        if row["visible"] and row["class_name"] == "SysListView32":
            return int(row["hwnd"])
    raise RuntimeError("Could not find the visible parts-list SysListView32 control.")


def _foreground(hwnd: int) -> None:
    try:
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    except Exception:
        pass
    try:
        win32gui.BringWindowToTop(hwnd)
    except Exception:
        pass
    try:
        win32gui.SetForegroundWindow(hwnd)
    except Exception:
        pass
    time.sleep(0.25)


def _click_rect_center(rect: tuple[int, int, int, int]) -> None:
    left, top, right, bottom = rect
    x = (left + right) // 2
    y = (top + bottom) // 2
    previous = win32gui.GetCursorPos()
    try:
        win32api.SetCursorPos((x, y))
        time.sleep(0.1)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        time.sleep(0.05)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        time.sleep(0.15)
    finally:
        try:
            win32api.SetCursorPos(previous)
        except Exception:
            pass


def _get_accessible_object(hwnd: int):
    pdispatch = POINTER(IDispatch)()
    hr = oleacc.AccessibleObjectFromWindow(
        hwnd,
        OBJID_CLIENT & 0xFFFFFFFF,
        ctypes.byref(IDispatch._iid_),
        ctypes.byref(pdispatch),
    )
    if hr != 0:
        raise RuntimeError(f"AccessibleObjectFromWindow failed: 0x{ctypes.c_uint32(hr).value:08X}")
    return comtypes.client.GetBestInterface(pdispatch)


def _dump_parts_list_items(list_hwnd: int) -> list[dict[str, Any]]:
    obj = _get_accessible_object(list_hwnd)
    rows: list[dict[str, Any]] = []
    for child_id in range(1, int(obj.accChildCount) + 1):
        try:
            name = obj.accName(child_id)
            state = obj.accState(child_id)
            left, top, width, height = obj.accLocation(child_id)
        except Exception:
            continue
        if not name:
            continue
        rows.append(
            {
                "child_id": child_id,
                "name": str(name),
                "state": int(state),
                "rect": (int(left), int(top), int(width), int(height)),
            }
        )
    return rows


def _select_part_row(list_hwnd: int, part_name: str) -> dict[str, Any]:
    obj = _get_accessible_object(list_hwnd)
    items = _dump_parts_list_items(list_hwnd)
    target = next((item for item in items if item["name"] == part_name), None)
    if target is None:
        raise RuntimeError(f"Could not find {part_name!r} in the parts list.")

    try:
        obj.accSelect(SELFLAG_TAKEFOCUS | SELFLAG_TAKESELECTION, int(target["child_id"]))
        time.sleep(0.25)
    except Exception:
        pass

    refreshed = _dump_parts_list_items(list_hwnd)
    selected = next((item for item in refreshed if item["name"] == part_name), target)
    if int(selected["state"]) != 19922950:
        left, top, width, height = target["rect"]
        _click_rect_center((left, top, left + width, top + height))
        time.sleep(0.25)
        refreshed = _dump_parts_list_items(list_hwnd)
        selected = next((item for item in refreshed if item["name"] == part_name), target)
    if int(selected["state"]) != 19922950:
        raise RuntimeError(f"Could not verify that {part_name!r} became the selected parts-list row.")
    return {
        "before": target,
        "after": selected,
    }


def _wait_for_part_editor(process_id: int, expected_part_name: str, timeout_sec: float = 20.0) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_sec
    current: dict[str, Any] | None = None
    while time.monotonic() < deadline:
        current = _find_visible_frame(process_id, "Part Editor")
        if current is not None:
            if expected_part_name in current["title"]:
                return current
        time.sleep(0.2)

    if current is None:
        raise RuntimeError("Timed out waiting for a visible Part Editor frame.")

    # RADAN can briefly show an intermediate title like "Untitled" before the real part name lands.
    settle_deadline = time.monotonic() + 5.0
    while time.monotonic() < settle_deadline:
        current = _find_visible_frame(process_id, "Part Editor") or current
        if expected_part_name in current["title"]:
            return current
        time.sleep(0.2)
    return current


def _wait_for_nest_editor(process_id: int, timeout_sec: float = 20.0) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        current = _find_visible_frame(process_id, "Nest Editor")
        if current is not None:
            return current
        time.sleep(0.2)
    raise RuntimeError("Timed out waiting for a visible Nest Editor frame.")


def _find_new_visible_notice(
    process_id: int,
    before_visible_keys: set[tuple[int, str, str]],
) -> dict[str, Any] | None:
    for row in _visible_windows_for_pid(process_id):
        key = (int(row["hwnd"]), str(row["title"]), str(row["class_name"]))
        if key in before_visible_keys:
            continue
        if row["title"] == "Mazak Smart System Notice":
            return row
    return None


def _click_dialog_button(dialog_hwnd: int, wanted_text: str) -> dict[str, Any]:
    for row in _walk_children(dialog_hwnd):
        if not row["visible"] or not row["enabled"]:
            continue
        if row["class_name"] == "Button" and row["text"] == wanted_text:
            _foreground(dialog_hwnd)
            _click_rect_center(row["rect"])
            return row
    raise RuntimeError(f"Could not find the enabled {wanted_text!r} button on dialog 0x{dialog_hwnd:08X}.")


def _run_pen_remap(
    repo_root: Path,
    *,
    process_id: int,
    backend: str | None,
    source_pen: int,
    target_pen: int,
    arc_target_pen: int,
) -> dict[str, Any]:
    command = [
        sys.executable,
        str(repo_root / "remap_feature_pens_live.py"),
        "--expected-process-id",
        str(int(process_id)),
        "--source-pen",
        str(int(source_pen)),
        "--target-pen",
        str(int(target_pen)),
        "--filter-target",
        f"a={int(arc_target_pen)}",
    ]
    if backend:
        command.extend(["--backend", backend])

    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=str(repo_root),
    )

    payload: dict[str, Any] = {
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }
    stdout = completed.stdout.strip()
    if stdout:
        try:
            payload["json"] = json.loads(stdout)
        except json.JSONDecodeError:
            payload["json"] = None
    else:
        payload["json"] = None

    if completed.returncode != 0:
        raise RuntimeError(f"remap_feature_pens_live.py failed: {completed.stderr or completed.stdout}")
    return payload


def _return_to_nest(process_id: int, part_hwnd: int) -> dict[str, Any]:
    nest_button = _find_visible_child_by_text(part_hwnd, "rtl_nest_button")
    if nest_button is None:
        raise RuntimeError("Could not find the visible Part Editor Nest button.")

    before_visible = _visible_windows_for_pid(process_id)
    before_visible_keys = {
        (int(row["hwnd"]), str(row["title"]), str(row["class_name"]))
        for row in before_visible
    }

    _foreground(part_hwnd)
    _click_rect_center(nest_button["rect"])

    start = time.monotonic()
    notice: dict[str, Any] | None = None
    clicked_yes: dict[str, Any] | None = None
    while time.monotonic() - start < 20.0:
        current_nest = _find_visible_frame(process_id, "Nest Editor")
        if current_nest is not None:
            return {
                "clicked_nest_button": True,
                "save_dialog_seen": False,
                "save_dialog_clicked_yes": False,
                "nest_title": current_nest["title"],
            }

        notice = _find_new_visible_notice(process_id, before_visible_keys)
        if notice is not None:
            clicked_yes = _click_dialog_button(int(notice["hwnd"]), "Yes")
            break
        time.sleep(0.2)

    current_nest = _wait_for_nest_editor(process_id, timeout_sec=30.0)
    return {
        "clicked_nest_button": True,
        "save_dialog_seen": notice is not None,
        "save_dialog_title": None if notice is None else notice["title"],
        "save_dialog_clicked_yes": clicked_yes is not None,
        "clicked_button": None if clicked_yes is None else clicked_yes["text"],
        "nest_title": current_nest["title"],
    }


def _open_part_from_nest(process_id: int, part_name: str) -> dict[str, Any]:
    nest = _wait_for_nest_editor(process_id, timeout_sec=10.0)
    list_hwnd = _find_parts_list_view(int(nest["hwnd"]))
    selection = _select_part_row(list_hwnd, part_name)
    open_button = _find_visible_child_by_text(int(nest["hwnd"]), "rpr_parts_list_open_part_button")
    if open_button is None:
        raise RuntimeError("Could not find the visible parts-list open-part button.")

    last_error: RuntimeError | None = None
    opened: dict[str, Any] | None = None
    open_attempt_count = 0
    for attempt in range(1, 4):
        open_attempt_count = attempt
        if attempt > 1:
            nest = _wait_for_nest_editor(process_id, timeout_sec=10.0)
            list_hwnd = _find_parts_list_view(int(nest["hwnd"]))
            selection = _select_part_row(list_hwnd, part_name)
            open_button = _find_visible_child_by_text(int(nest["hwnd"]), "rpr_parts_list_open_part_button")
            if open_button is None:
                raise RuntimeError("Could not find the visible parts-list open-part button on retry.")

        _foreground(int(nest["hwnd"]))
        _click_rect_center(open_button["rect"])
        try:
            opened = _wait_for_part_editor(process_id, part_name, timeout_sec=8.0 if attempt < 3 else 20.0)
            break
        except RuntimeError as exc:
            last_error = exc
            if _find_visible_frame(process_id, "Nest Editor") is None:
                raise
            time.sleep(0.4)

    if opened is None:
        raise RuntimeError(
            f"Could not open {part_name!r} from the Nest parts list after {open_attempt_count} attempt(s)."
        ) from last_error

    return {
        "selection": selection,
        "open_button_rect": open_button["rect"],
        "open_attempt_count": open_attempt_count,
        "part_title": opened["title"],
        "part_hwnd": opened["hwnd"],
    }


def _iso_now() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Open selected parts from the live RADAN Nest parts list, remap pens, return to Nest, and time the whole batch.",
    )
    parser.add_argument(
        "--process-id",
        type=int,
        required=True,
        help="Visible RADAN PID guard.",
    )
    parser.add_argument(
        "--part",
        action="append",
        required=True,
        help="Exact part name in the Nest parts list. Repeat for each part.",
    )
    parser.add_argument("--backend", help="Optional backend override forwarded to remap_feature_pens_live.py.")
    parser.add_argument("--source-pen", type=int, default=7)
    parser.add_argument("--target-pen", type=int, default=5)
    parser.add_argument("--arc-target-pen", type=int, default=9)
    parser.add_argument("--json-out", help="Optional path to write the batch JSON result.")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent
    batch_start = time.monotonic()
    payload: dict[str, Any] = {
        "started_at": _iso_now(),
        "process_id": int(args.process_id),
        "parts": [],
        "source_pen": int(args.source_pen),
        "target_pen": int(args.target_pen),
        "arc_target_pen": int(args.arc_target_pen),
    }

    for part_name in args.part:
        part_start = time.monotonic()
        item_result: dict[str, Any] = {
            "part_name": part_name,
        }
        item_result["open"] = _open_part_from_nest(int(args.process_id), part_name)
        item_result["remap"] = _run_pen_remap(
            repo_root,
            process_id=int(args.process_id),
            backend=args.backend,
            source_pen=int(args.source_pen),
            target_pen=int(args.target_pen),
            arc_target_pen=int(args.arc_target_pen),
        )
        item_result["return_to_nest"] = _return_to_nest(
            int(args.process_id),
            int(item_result["open"]["part_hwnd"]),
        )
        item_result["elapsed_sec"] = round(time.monotonic() - part_start, 3)
        payload["parts"].append(item_result)

    payload["finished_at"] = _iso_now()
    payload["total_elapsed_sec"] = round(time.monotonic() - batch_start, 3)

    output = json.dumps(payload, indent=2, ensure_ascii=True)
    if args.json_out:
        output_path = Path(args.json_out).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output, encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
