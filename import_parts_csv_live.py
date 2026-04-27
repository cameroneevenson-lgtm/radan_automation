from __future__ import annotations

import argparse
import ctypes
import datetime as dt
import json
import os
import time
from ctypes import wintypes
from pathlib import Path
from typing import Any

import comtypes.client
import win32api
import win32clipboard
import win32con
import win32gui
import win32process
from comtypes import POINTER
from comtypes.automation import IDispatch


IMPORT_BUTTON_TEXT = "rpr_parts_list_import_parts_button"
IMPORT_DIALOG_TITLE = "Import Parts"
IMPORT_PARENT_CLASS_PREFIX = "WindowsForms10.Window"
IDOK = 1
COMMON_DIALOG_FILE_NAME_COMBO_ID = 1148
GW_OWNER = 4
VK_RETURN = 0x0D
VK_CONTROL = 0x11
VK_V = 0x56
VK_RIGHT = 0x27
VK_TAB = 0x09
SELFLAG_TAKEFOCUS = 0x1
SELFLAG_TAKESELECTION = 0x2

OBJID_CLIENT = 0xFFFFFFFC
oleacc = ctypes.OleDLL("oleacc")
oleacc.AccessibleObjectFromWindow.argtypes = [
    wintypes.HWND,
    wintypes.DWORD,
    ctypes.POINTER(type(IDispatch._iid_)),
    ctypes.POINTER(ctypes.c_void_p),
]
oleacc.AccessibleObjectFromWindow.restype = ctypes.c_long
user32 = ctypes.WinDLL("user32", use_last_error=True)


class _GUITHREADINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("hwndActive", wintypes.HWND),
        ("hwndFocus", wintypes.HWND),
        ("hwndCapture", wintypes.HWND),
        ("hwndMenuOwner", wintypes.HWND),
        ("hwndMoveSize", wintypes.HWND),
        ("hwndCaret", wintypes.HWND),
        ("rcCaret", wintypes.RECT),
    ]


class _Logger:
    def __init__(self, log_file: Path | None = None) -> None:
        self.log_file = log_file
        if self.log_file is not None:
            self.log_file.parent.mkdir(parents=True, exist_ok=True)
            self.log_file.write_text("", encoding="utf-8")

    def write(self, message: str) -> None:
        stamp = dt.datetime.now().strftime("%H:%M:%S")
        line = f"[{stamp}] {message}"
        print(line, flush=True)
        if self.log_file is not None:
            with self.log_file.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")


def _top_level_windows_for_pid(process_id: int | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    def _callback(hwnd: int, _: object) -> bool:
        try:
            found_pid = win32process.GetWindowThreadProcessId(hwnd)[1]
        except Exception:
            return True
        if process_id is not None and found_pid != process_id:
            return True
        rows.append(
            {
                "hwnd": hwnd,
                "process_id": found_pid,
                "title": win32gui.GetWindowText(hwnd),
                "class_name": win32gui.GetClassName(hwnd),
                "visible": bool(win32gui.IsWindowVisible(hwnd)),
                "enabled": bool(win32gui.IsWindowEnabled(hwnd)),
                "rect": win32gui.GetWindowRect(hwnd),
            }
        )
        return True

    win32gui.EnumWindows(_callback, None)
    return rows


def _visible_windows_for_pid(process_id: int | None = None) -> list[dict[str, Any]]:
    return [row for row in _top_level_windows_for_pid(process_id) if row["visible"]]


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
        if row["visible"] and row["enabled"] and row["text"] == text:
            return row
    return None


def _find_visible_children_by_class(hwnd: int, class_name: str) -> list[dict[str, Any]]:
    return [
        row
        for row in _walk_children(hwnd)
        if row["visible"] and row["enabled"] and row["class_name"] == class_name
    ]


def _normalize_button_text(value: object) -> str:
    return str(value or "").replace("&", "").strip().casefold()


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


def _set_clipboard_text(text: str) -> None:
    win32clipboard.OpenClipboard()
    try:
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, text)
    finally:
        win32clipboard.CloseClipboard()


def _press_key(vk: int) -> None:
    win32api.keybd_event(vk, 0, 0, 0)
    time.sleep(0.05)
    win32api.keybd_event(vk, 0, win32con.KEYEVENTF_KEYUP, 0)


def _press_enter() -> None:
    _press_key(VK_RETURN)


def _press_right() -> None:
    _press_key(VK_RIGHT)


def _press_tab() -> None:
    _press_key(VK_TAB)


def _paste_clipboard() -> None:
    win32api.keybd_event(VK_CONTROL, 0, 0, 0)
    time.sleep(0.05)
    win32api.keybd_event(VK_V, 0, 0, 0)
    time.sleep(0.05)
    win32api.keybd_event(VK_V, 0, win32con.KEYEVENTF_KEYUP, 0)
    time.sleep(0.05)
    win32api.keybd_event(VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)


def _visible_nest_editors(process_id: int | None) -> list[dict[str, Any]]:
    return [
        row
        for row in _visible_windows_for_pid(process_id)
        if row["class_name"] == "myframe" and "Nest Editor" in row["title"]
    ]


def _title_key(value: object) -> str:
    text = str(value or "").casefold()
    return " ".join("".join(ch if ch.isalnum() else " " for ch in text).split())


def _matches_project_title(row: dict[str, Any], project_path: Path | None) -> bool:
    if project_path is None:
        return False
    title_key = _title_key(row["title"])
    candidates = [
        _title_key(project_path.stem),
        _title_key(project_path.parent.name),
    ]
    return any(candidate and candidate in title_key for candidate in candidates)


def _select_nest_editor(
    process_id: int | None,
    *,
    project_path: Path | None,
    before_hwnds: set[int] | None = None,
) -> dict[str, Any] | None:
    matches = _visible_nest_editors(process_id)
    if project_path is not None:
        project_matches = [row for row in matches if _matches_project_title(row, project_path)]
        if len(project_matches) == 1:
            return project_matches[0]
        if len(project_matches) > 1:
            project_matches.sort(key=lambda row: (row["title"], row["hwnd"]))
            return project_matches[0]

    if before_hwnds is not None:
        new_matches = [row for row in matches if int(row["hwnd"]) not in before_hwnds]
        if len(new_matches) == 1:
            return new_matches[0]
        if project_path is not None and len(new_matches) > 1:
            titled_new_matches = [row for row in new_matches if _matches_project_title(row, project_path)]
            if titled_new_matches:
                titled_new_matches.sort(key=lambda row: (row["title"], row["hwnd"]))
                return titled_new_matches[0]

    if len(matches) == 1:
        return matches[0]
    return None


def _format_nest_editor_choices(process_id: int | None) -> str:
    matches = _visible_nest_editors(process_id)
    if not matches:
        return "(none)"
    return "\n".join(f"PID {row['process_id']}: {row['title']}" for row in matches)


def _open_project_if_needed(
    *,
    project_path: Path | None,
    process_id: int | None,
    timeout_sec: float,
    logger: _Logger,
) -> dict[str, Any]:
    logger.write("Looking for a visible RADAN Nest Editor session...")
    selected = _select_nest_editor(process_id, project_path=project_path)
    if selected is not None:
        logger.write(f"Using Nest Editor: {selected['title']}")
        return selected
    if project_path is None:
        raise RuntimeError(
            "Could not choose a RADAN Nest Editor session. Visible sessions:\n"
            + _format_nest_editor_choices(process_id)
        )

    before_hwnds = {int(row["hwnd"]) for row in _visible_nest_editors(process_id)}
    logger.write(f"No matching Nest Editor found. Opening project: {project_path}")
    os.startfile(str(project_path))  # type: ignore[attr-defined]
    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        selected = _select_nest_editor(
            process_id,
            project_path=project_path,
            before_hwnds=before_hwnds,
        )
        if selected is not None:
            logger.write(f"RADAN Nest Editor is visible: {selected['title']}")
            return selected
        time.sleep(0.5)

    raise RuntimeError(
        f"Opened project but timed out choosing the matching RADAN Nest Editor:\n{project_path}\n\n"
        "Visible Nest Editor sessions:\n"
        + _format_nest_editor_choices(process_id)
    )


def _wait_for_top_window(
    *,
    process_id: int,
    title: str,
    class_name: str | None = None,
    class_prefix: str | None = None,
    enabled: bool | None = None,
    timeout_sec: float,
    logger: _Logger | None = None,
) -> dict[str, Any]:
    if logger is not None:
        logger.write(f"Waiting for window {title!r}...")
    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        for row in _visible_windows_for_pid(process_id):
            if row["title"] != title:
                continue
            if class_name is not None and row["class_name"] != class_name:
                continue
            if class_prefix is not None and not str(row["class_name"]).startswith(class_prefix):
                continue
            if enabled is not None and bool(row["enabled"]) != enabled:
                continue
            if logger is not None:
                logger.write(f"Found window {title!r} ({row['class_name']}).")
            return row
        time.sleep(0.2)
    raise RuntimeError(f"Timed out waiting for {title!r}.")


def _wait_for_child_by_text(hwnd: int, text: str, *, timeout_sec: float, logger: _Logger) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_sec
    next_status_at = time.monotonic() + 10.0
    while time.monotonic() < deadline:
        row = _find_visible_child_by_text(hwnd, text)
        if row is not None:
            logger.write(f"Found control {text!r}.")
            return row
        if time.monotonic() >= next_status_at:
            logger.write(f"Still waiting for control {text!r}...")
            next_status_at = time.monotonic() + 10.0
        time.sleep(0.5)
    raise RuntimeError(f"Timed out waiting for enabled control {text!r}.")


def _click_button_by_text(hwnd: int, text: str) -> dict[str, Any]:
    wanted = _normalize_button_text(text)
    button = None
    for row in _walk_children(hwnd):
        if not row["visible"] or not row["enabled"]:
            continue
        if row["class_name"] != "Button":
            continue
        if _normalize_button_text(row["text"]) == wanted:
            button = row
            break
    if button is None:
        raise RuntimeError(f"Could not find enabled button/control {text!r}.")
    _foreground(hwnd)
    win32gui.PostMessage(int(button["hwnd"]), win32con.BM_CLICK, 0, 0)
    time.sleep(0.15)
    return button


def _visible_button_summary(hwnd: int) -> str:
    buttons = [
        f"{row['text']!r} enabled={row['enabled']} rect={row['rect']}"
        for row in _walk_children(hwnd)
        if row["visible"] and row["class_name"] == "Button"
    ]
    return "\n".join(buttons) if buttons else "(no visible Button controls)"


def _wait_for_window_closed(hwnd: int, *, timeout_sec: float) -> bool:
    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        try:
            if not win32gui.IsWindow(hwnd) or not win32gui.IsWindowVisible(hwnd):
                return True
        except Exception:
            return True
        time.sleep(0.1)
    try:
        return not win32gui.IsWindow(hwnd) or not win32gui.IsWindowVisible(hwnd)
    except Exception:
        return True


def _first_enabled_edit_under(hwnd: int) -> dict[str, Any] | None:
    edits = _find_visible_children_by_class(hwnd, "Edit")
    return edits[0] if edits else None


def _file_name_edit(file_picker_hwnd: int) -> dict[str, Any]:
    try:
        file_name_combo = win32gui.GetDlgItem(file_picker_hwnd, COMMON_DIALOG_FILE_NAME_COMBO_ID)
    except Exception:
        file_name_combo = 0
    if file_name_combo:
        edit = _first_enabled_edit_under(int(file_name_combo))
        if edit is not None:
            return edit

    edits = _find_visible_children_by_class(file_picker_hwnd, "Edit")
    if edits:
        return edits[0]
    raise RuntimeError("Could not find the file-name field in the Import Parts file picker.")


def _click_dialog_ok(file_picker_hwnd: int, *, logger: _Logger, timeout_sec: float = 20.0) -> None:
    def _picker_closed() -> bool:
        try:
            return not win32gui.IsWindow(file_picker_hwnd) or not win32gui.IsWindowVisible(file_picker_hwnd)
        except Exception:
            return True

    def _wait_after_action(seconds: float = 4.0) -> bool:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if _picker_closed():
                return True
            time.sleep(0.1)
        return _picker_closed()

    deadline = time.monotonic() + timeout_sec
    next_status_at = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        try:
            ok_hwnd = win32gui.GetDlgItem(file_picker_hwnd, IDOK)
        except Exception:
            ok_hwnd = 0
        if ok_hwnd:
            try:
                if win32gui.IsWindowVisible(ok_hwnd) and win32gui.IsWindowEnabled(ok_hwnd):
                    rect = win32gui.GetWindowRect(ok_hwnd)
                    logger.write("Clicking dialog OK/Open button by standard IDOK.")
                    _foreground(file_picker_hwnd)
                    _click_rect_center(rect)
                    if _wait_after_action():
                        return

                    logger.write("The picker is still open; posting BM_CLICK to IDOK.")
                    win32gui.PostMessage(ok_hwnd, win32con.BM_CLICK, 0, 0)
                    if _wait_after_action():
                        return

                    logger.write("The picker is still open; sending WM_COMMAND IDOK to the dialog.")
                    win32gui.PostMessage(file_picker_hwnd, win32con.WM_COMMAND, IDOK, ok_hwnd)
                    if _wait_after_action():
                        return

                    logger.write("The picker is still open; pressing Enter as a final Open fallback.")
                    _foreground(file_picker_hwnd)
                    _press_enter()
                    if _wait_after_action():
                        return
            except Exception:
                pass

        try:
            _click_button_by_text(file_picker_hwnd, "Open")
            logger.write("Clicked Open button by text fallback.")
            if _wait_after_action():
                return
        except RuntimeError:
            pass

        if time.monotonic() >= next_status_at:
            logger.write("Still waiting for the file picker Open button to become enabled...")
            next_status_at = time.monotonic() + 5.0
        time.sleep(0.25)

    raise RuntimeError(
        "Could not find an enabled Open/OK button in the file picker. Visible buttons:\n"
        + _visible_button_summary(file_picker_hwnd)
    )


def _submit_file_picker(file_picker_hwnd: int, csv_path: Path, logger: _Logger) -> None:
    logger.write("Filling the Import Parts file picker with the CSV path...")
    edit = _file_name_edit(file_picker_hwnd)
    win32gui.SendMessage(int(edit["hwnd"]), win32con.WM_SETTEXT, 0, str(csv_path))
    time.sleep(0.5)
    logger.write("Triggering Open in the file picker.")
    _click_dialog_ok(file_picker_hwnd, logger=logger)


def _wait_for_browse_ready(parent_hwnd: int, timeout_sec: float, logger: _Logger) -> dict[str, Any]:
    logger.write("Waiting for RADAN to finish reading the CSV. Browse... is the readiness signal.")
    deadline = time.monotonic() + timeout_sec
    last_seen: dict[str, Any] | None = None
    next_status_at = time.monotonic() + 10.0
    while time.monotonic() < deadline:
        browse = _find_visible_child_by_text(parent_hwnd, "Browse...")
        if browse is not None:
            logger.write("Browse... is enabled. CSV rows are ready.")
            return browse
        for row in _walk_children(parent_hwnd):
            if row["text"] == "Browse...":
                last_seen = row
                break
        if time.monotonic() >= next_status_at:
            logger.write("Still waiting for Browse... to become enabled...")
            next_status_at = time.monotonic() + 10.0
        time.sleep(0.5)
    if last_seen is not None:
        raise RuntimeError("Timed out waiting for Browse... to become enabled after CSV ingest.")
    raise RuntimeError("Could not find the Browse... button on the Import Parts dialog.")


def _find_folder_dialog(process_id: int, timeout_sec: float, logger: _Logger) -> dict[str, Any]:
    logger.write("Waiting for Browse For Folder dialog...")
    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        for row in _visible_windows_for_pid(process_id):
            if row["class_name"] != "#32770":
                continue
            title_key = str(row["title"] or "").casefold()
            if "browse" in title_key or "folder" in title_key:
                logger.write(f"Found folder dialog: {row['title']!r}.")
                return row
        time.sleep(0.2)
    raise RuntimeError("Timed out waiting for the Browse For Folder dialog.")


def _find_ok_button(hwnd: int) -> dict[str, Any] | None:
    for row in _walk_children(hwnd):
        if not row["visible"] or not row["enabled"]:
            continue
        if row["class_name"] != "Button":
            continue
        text = _normalize_button_text(row["text"])
        if text in {"ok", "select folder"}:
            return row
    return None


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


def _focused_hwnd_for_thread(hwnd: int) -> int:
    thread_id = win32process.GetWindowThreadProcessId(hwnd)[0]
    info = _GUITHREADINFO()
    info.cbSize = ctypes.sizeof(info)
    if not user32.GetGUIThreadInfo(thread_id, ctypes.byref(info)):
        return 0
    return int(info.hwndFocus or 0)


def _is_hwnd_or_child(parent_hwnd: int, hwnd: int) -> bool:
    if not hwnd:
        return False
    if int(parent_hwnd) == int(hwnd):
        return True
    try:
        return bool(user32.IsChild(parent_hwnd, hwnd))
    except Exception:
        return False


def _focus_tree_with_tabs(folder_hwnd: int, tree_hwnd: int, logger: _Logger) -> bool:
    logger.write("Focusing folder tree with Tab navigation.")
    _foreground(folder_hwnd)
    for attempt in range(1, 13):
        focused = _focused_hwnd_for_thread(folder_hwnd)
        if _is_hwnd_or_child(tree_hwnd, focused):
            logger.write(f"Folder tree focused after {attempt - 1} Tab press(es).")
            return True
        _press_tab()
        time.sleep(0.15)
    focused = _focused_hwnd_for_thread(folder_hwnd)
    if _is_hwnd_or_child(tree_hwnd, focused):
        logger.write("Folder tree focused after Tab navigation.")
        return True
    logger.write("Tab navigation did not report focus on the folder tree.")
    return False


def _tree_items(tree_hwnd: int) -> list[dict[str, Any]]:
    obj = _get_accessible_object(tree_hwnd)
    rows: list[dict[str, Any]] = []
    try:
        child_count = int(obj.accChildCount)
    except Exception:
        child_count = 0
    for child_id in range(1, child_count + 1):
        try:
            name = obj.accName(child_id)
            if not name:
                continue
            left, top, width, height = obj.accLocation(child_id)
        except Exception:
            continue
        rows.append(
            {
                "child_id": child_id,
                "name": str(name),
                "rect": (int(left), int(top), int(width), int(height)),
            }
        )
    return rows


def _name_key(value: object) -> str:
    return " ".join(
        "".join(ch.casefold() if ch.isalnum() else " " for ch in str(value or "")).split()
    )


def _tree_item_matches(item_name: str, wanted: str) -> bool:
    item_key = _name_key(item_name)
    wanted_key = _name_key(wanted)
    if not wanted_key:
        return False
    if wanted.endswith(":"):
        return wanted.casefold() in item_name.casefold()
    return item_key == wanted_key or item_key.endswith(f" {wanted_key}") or wanted_key in item_key.split(" ")


def _select_tree_item(tree_hwnd: int, item: dict[str, Any]) -> None:
    obj = _get_accessible_object(tree_hwnd)
    child_id = int(item["child_id"])
    try:
        obj.accSelect(SELFLAG_TAKEFOCUS | SELFLAG_TAKESELECTION, child_id)
        time.sleep(0.2)
    except Exception:
        left, top, width, height = item["rect"]
        _click_rect_center((left, top, left + width, top + height))
        time.sleep(0.2)


def _folder_tree_path_parts(output_folder: Path) -> list[str]:
    text = str(output_folder)
    lowered = text.casefold()
    unc_laser_prefix = "\\\\svrdc\\laser\\"
    if lowered.startswith(unc_laser_prefix):
        text = "L:\\" + text[len(unc_laser_prefix) :]
    elif lowered == r"\\svrdc\laser":
        text = r"L:\\"

    normalized = text.replace("/", "\\")
    if len(normalized) >= 3 and normalized[1:3] == ":\\":
        drive = normalized[:2].upper()
        rest = [part for part in normalized[3:].split("\\") if part]
        return [drive, *rest]
    if normalized.startswith("\\\\"):
        return [part for part in normalized.split("\\") if part]
    return [part for part in normalized.split("\\") if part]


def _find_tree_item(tree_hwnd: int, wanted: str) -> dict[str, Any] | None:
    for item in _tree_items(tree_hwnd):
        if _tree_item_matches(str(item["name"]), wanted):
            return item
    return None


def _wait_for_tree_item(tree_hwnd: int, wanted: str, timeout_sec: float) -> dict[str, Any] | None:
    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        item = _find_tree_item(tree_hwnd, wanted)
        if item is not None:
            return item
        time.sleep(0.25)
    return None


def _try_folder_dialog_msaa_tree_path(folder_hwnd: int, output_folder: Path, logger: _Logger) -> bool:
    trees = _find_visible_children_by_class(folder_hwnd, "SysTreeView32")
    if not trees:
        logger.write("Folder dialog has no visible SysTreeView32 tree to navigate.")
        return False

    tree = trees[0]
    tree_hwnd = int(tree["hwnd"])
    parts = _folder_tree_path_parts(output_folder)
    if not parts:
        return False
    logger.write("Navigating Browse For Folder tree with MSAA selection and keyboard expansion.")
    logger.write("Tree route: " + " > ".join(parts))
    if not _focus_tree_with_tabs(folder_hwnd, tree_hwnd, logger):
        logger.write("Falling back to focusing the tree control directly.")
        _foreground(folder_hwnd)
        try:
            user32.SetFocus(tree_hwnd)
        except Exception:
            pass
        time.sleep(0.3)

    for index, part in enumerate(parts):
        item = _wait_for_tree_item(tree_hwnd, part, timeout_sec=8.0)
        if item is None and index == 0 and part.endswith(":"):
            for root_name in ("This PC", "Computer", "Desktop"):
                root_item = _find_tree_item(tree_hwnd, root_name)
                if root_item is None:
                    continue
                logger.write(f"Expanding tree root: {root_item['name']}")
                _select_tree_item(tree_hwnd, root_item)
                _press_right()
                time.sleep(0.8)
                item = _wait_for_tree_item(tree_hwnd, part, timeout_sec=8.0)
                if item is not None:
                    break
        if item is None:
            logger.write(f"Could not find tree segment {part!r}.")
            return False
        logger.write(f"Selecting tree segment: {item['name']}")
        _select_tree_item(tree_hwnd, item)
        if index < len(parts) - 1:
            _press_right()
            time.sleep(0.6)

    return _confirm_folder_dialog(folder_hwnd, logger)


def _confirm_folder_dialog(folder_hwnd: int, logger: _Logger) -> bool:
    ok_button = _find_ok_button(folder_hwnd)
    if ok_button is not None:
        logger.write("Confirming folder dialog with OK.")
        _foreground(folder_hwnd)
        _click_rect_center(ok_button["rect"])
        return _wait_for_window_closed(folder_hwnd, timeout_sec=8.0)

    logger.write("Could not find OK button text; pressing Enter in folder dialog.")
    _foreground(folder_hwnd)
    _press_enter()
    return _wait_for_window_closed(folder_hwnd, timeout_sec=8.0)


def _try_folder_dialog_edit_path(folder_hwnd: int, output_folder: Path, logger: _Logger) -> bool:
    edits = _find_visible_children_by_class(folder_hwnd, "Edit")
    if not edits:
        logger.write("Folder dialog has no visible edit field for direct path entry.")
        return False

    logger.write("Setting output folder through folder dialog edit field.")
    edit = edits[0]
    win32gui.SendMessage(int(edit["hwnd"]), win32con.WM_SETTEXT, 0, str(output_folder))
    time.sleep(0.3)
    return _confirm_folder_dialog(folder_hwnd, logger)


def _try_folder_dialog_clipboard_path(folder_hwnd: int, output_folder: Path, logger: _Logger) -> bool:
    trees = _find_visible_children_by_class(folder_hwnd, "SysTreeView32")
    if not trees:
        logger.write("Folder dialog has no visible SysTreeView32 tree to focus.")
        return False

    logger.write("Trying folder tree focus plus clipboard paste for output folder.")
    _set_clipboard_text(str(output_folder))
    tree = trees[0]
    _foreground(folder_hwnd)
    _click_rect_center(tree["rect"])
    time.sleep(0.2)
    _paste_clipboard()
    time.sleep(0.5)
    return _confirm_folder_dialog(folder_hwnd, logger)


def _assign_output_folder(
    *,
    process_id: int,
    parent_hwnd: int,
    browse_button: dict[str, Any],
    output_folder: Path,
    logger: _Logger,
    folder_timeout_sec: float,
) -> None:
    logger.write(f"Output folder target for RADAN symbols: {output_folder}")
    logger.write("Clicking Browse... to assign the output folder.")
    _foreground(parent_hwnd)
    _click_rect_center(browse_button["rect"])

    folder_dialog = _find_folder_dialog(process_id, folder_timeout_sec, logger)
    folder_hwnd = int(folder_dialog["hwnd"])
    if _try_folder_dialog_edit_path(folder_hwnd, output_folder, logger):
        logger.write("Output folder dialog closed after direct edit assignment.")
        return
    if _try_folder_dialog_msaa_tree_path(folder_hwnd, output_folder, logger):
        logger.write("Output folder dialog closed after MSAA tree assignment.")
        return

    raise RuntimeError(
        "Could not assign the output folder automatically. "
        "The Browse For Folder dialog is still open. "
        "Select this exact folder and click OK:\n"
        f"{output_folder}"
    )


def _window_contains_text(hwnd: int, text: str) -> bool:
    wanted = str(text or "").casefold()
    if wanted in win32gui.GetWindowText(hwnd).casefold():
        return True
    for row in _walk_children(hwnd):
        if wanted in str(row["text"] or "").casefold():
            return True
    return False


def _wait_for_import_completion(process_id: int, timeout_sec: float, logger: _Logger) -> dict[str, Any]:
    logger.write("Waiting for Import All completion modal...")
    deadline = time.monotonic() + timeout_sec
    next_status_at = time.monotonic() + 15.0
    while time.monotonic() < deadline:
        for row in _visible_windows_for_pid(process_id):
            if row["title"] != IMPORT_DIALOG_TITLE or row["class_name"] != "#32770":
                continue
            if _window_contains_text(int(row["hwnd"]), "Number of parts added"):
                logger.write("Import completion modal appeared.")
                return row
        if time.monotonic() >= next_status_at:
            logger.write("Still waiting for Import All completion modal...")
            next_status_at = time.monotonic() + 15.0
        time.sleep(0.5)
    raise RuntimeError("Timed out waiting for the Import All completion modal.")


def _acknowledge_completion_modal(modal: dict[str, Any], logger: _Logger) -> None:
    logger.write("Acknowledging Import Parts completion modal.")
    hwnd = int(modal["hwnd"])
    ok_button = _find_ok_button(hwnd)
    if ok_button is not None:
        _foreground(hwnd)
        _click_rect_center(ok_button["rect"])
    else:
        _foreground(hwnd)
        _press_enter()
    _wait_for_window_closed(hwnd, timeout_sec=15.0)


def _run_import_all(
    *,
    process_id: int,
    parent_hwnd: int,
    timeout_sec: float,
    logger: _Logger,
) -> dict[str, Any]:
    logger.write("Looking for Import All button...")
    import_all = _wait_for_child_by_text(
        parent_hwnd,
        "Import All",
        timeout_sec=60.0,
        logger=logger,
    )
    logger.write("Clicking Import All.")
    _foreground(parent_hwnd)
    _click_rect_center(import_all["rect"])
    completion = _wait_for_import_completion(process_id, timeout_sec, logger)
    completion_texts = [
        str(row["text"])
        for row in _walk_children(int(completion["hwnd"]))
        if str(row["text"] or "").strip()
    ]
    _acknowledge_completion_modal(completion, logger)
    return {
        "button_rect": import_all["rect"],
        "completion_text": "\n".join(completion_texts),
    }


def _close_import_parent_if_open(parent_hwnd: int, logger: _Logger) -> None:
    try:
        if not win32gui.IsWindow(parent_hwnd) or not win32gui.IsWindowVisible(parent_hwnd):
            return
    except Exception:
        return
    logger.write("Closing Import Parts parent dialog.")
    for label in ("Close", "Cancel"):
        try:
            button = _click_button_by_text(parent_hwnd, label)
            if button is not None and _wait_for_window_closed(parent_hwnd, timeout_sec=10.0):
                return
        except RuntimeError:
            continue
    try:
        win32gui.PostMessage(parent_hwnd, win32con.WM_CLOSE, 0, 0)
        _wait_for_window_closed(parent_hwnd, timeout_sec=10.0)
    except Exception:
        pass


def _is_owned_by(hwnd: int, owner_hwnd: int | None) -> bool:
    if owner_hwnd is None:
        return True
    seen: set[int] = set()
    current = hwnd
    for _ in range(8):
        if not current or current in seen:
            return False
        if current == owner_hwnd:
            return True
        seen.add(current)
        try:
            owner = win32gui.GetWindow(current, GW_OWNER)
        except Exception:
            owner = 0
        try:
            parent = win32gui.GetParent(current)
        except Exception:
            parent = 0
        current = int(owner or parent or 0)
    return False


def _dialog_text(hwnd: int) -> str:
    pieces = [win32gui.GetWindowText(hwnd)]
    for row in _walk_children(hwnd):
        if row["visible"] and row["text"]:
            pieces.append(str(row["text"]))
    return "\n".join(pieces).casefold()


def _is_save_or_notice_dialog(row: dict[str, Any]) -> bool:
    title = str(row["title"] or "").casefold()
    if "save project" in title or "notice" in title or "mazak" in title:
        return True
    text = _dialog_text(int(row["hwnd"]))
    return "do you want to save the changes to the current project" in text


def _click_notice_button(
    process_id: int,
    text: str,
    timeout_sec: float,
    logger: _Logger,
    *,
    owner_hwnd: int | None = None,
    stop_if_closed_hwnd: int | None = None,
) -> bool:
    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        if stop_if_closed_hwnd is not None and not win32gui.IsWindow(stop_if_closed_hwnd):
            return False
        for row in _visible_windows_for_pid(process_id):
            if row["class_name"] != "#32770":
                continue
            if not _is_owned_by(int(row["hwnd"]), owner_hwnd):
                continue
            if not _is_save_or_notice_dialog(row):
                continue
            try:
                button = _click_button_by_text(int(row["hwnd"]), text)
                logger.write(f"Clicking {text!r} on {row['title']!r}.")
                _wait_for_window_closed(int(row["hwnd"]), timeout_sec=10.0)
                return True
            except RuntimeError:
                continue
        time.sleep(0.2)
    return False


def _clean_menu_label(text: str) -> str:
    return text.split("\t", 1)[0].replace("&", "").strip().casefold()


def _menu_label_matches(text: str, target: str) -> bool:
    clean = _clean_menu_label(text)
    expected = target.strip().casefold()
    return clean == expected or clean.startswith(f"{expected} ")


def _find_menu_command_id(menu: int, path: tuple[str, ...]) -> int | None:
    if not path:
        return None
    try:
        count = win32gui.GetMenuItemCount(menu)
    except Exception:
        return None
    for index in range(count):
        try:
            label = win32gui.GetMenuString(menu, index, win32con.MF_BYPOSITION)
        except Exception:
            continue
        if not _menu_label_matches(str(label or ""), path[0]):
            continue
        if len(path) == 1:
            try:
                command_id = win32gui.GetMenuItemID(menu, index)
            except Exception:
                return None
            return int(command_id) if command_id >= 0 else None
        try:
            submenu = win32gui.GetSubMenu(menu, index)
        except Exception:
            submenu = 0
        if submenu:
            return _find_menu_command_id(submenu, path[1:])
    return None


def _invoke_file_exit(nest_hwnd: int, logger: _Logger) -> bool:
    try:
        menu = win32gui.GetMenu(nest_hwnd)
    except Exception:
        menu = 0
    if not menu:
        logger.write("RADAN menu was not available; cannot invoke File > Exit.")
        return False
    command_id = _find_menu_command_id(menu, ("File", "Exit"))
    if command_id is None:
        logger.write("RADAN File > Exit menu command was not found.")
        return False
    logger.write("Invoking RADAN File > Exit menu command.")
    _foreground(nest_hwnd)
    win32gui.PostMessage(nest_hwnd, win32con.WM_COMMAND, command_id, 0)
    return True


def _save_and_close_radan_project(
    *,
    nest_hwnd: int,
    process_id: int,
    logger: _Logger,
) -> None:
    logger.write("Closing RADAN through File > Exit and accepting RADAN's save prompt.")
    if not _invoke_file_exit(nest_hwnd, logger):
        logger.write("Falling back to targeted WM_CLOSE on the RADAN project window.")
        _foreground(nest_hwnd)
        win32gui.PostMessage(nest_hwnd, win32con.WM_CLOSE, 0, 0)
    if _click_notice_button(
        process_id,
        "Yes",
        20.0,
        logger,
        owner_hwnd=nest_hwnd,
        stop_if_closed_hwnd=nest_hwnd,
    ):
        logger.write("Accepted RADAN save prompt.")
    if not _wait_for_window_closed(nest_hwnd, timeout_sec=45.0):
        logger.write("RADAN project window is still open; checking once more for a save prompt.")
        _click_notice_button(
            process_id,
            "Yes",
            10.0,
            logger,
            owner_hwnd=nest_hwnd,
            stop_if_closed_hwnd=nest_hwnd,
        )
        if not _wait_for_window_closed(nest_hwnd, timeout_sec=30.0):
            raise RuntimeError("RADAN project window did not close after File > Exit / targeted close attempts.")
    logger.write("RADAN project window closed.")


def _launch_kitter(kitter_launcher: Path | None, project_path: Path | None, logger: _Logger) -> None:
    if kitter_launcher is None:
        logger.write("No RADAN Kitter launcher was provided; skipping Kitter launch.")
        return
    if project_path is None:
        raise RuntimeError("Cannot launch RADAN Kitter because no project path was provided.")
    if not kitter_launcher.exists():
        raise RuntimeError(f"RADAN Kitter launcher not found: {kitter_launcher}")
    logger.write(f"Launching RADAN Kitter: {kitter_launcher} {project_path}")
    suffix = kitter_launcher.suffix.casefold()
    if suffix in {".bat", ".cmd"}:
        command = ["cmd.exe", "/c", str(kitter_launcher), str(project_path)]
    else:
        command = [str(kitter_launcher), str(project_path)]
    import subprocess

    subprocess.Popen(
        command,
        cwd=str(kitter_launcher.parent),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _run(
    csv_path: Path,
    output_folder: Path,
    process_id: int | None,
    ingest_timeout_sec: float,
    project_path: Path | None,
    project_open_timeout_sec: float,
    launcher_timeout_sec: float,
    file_picker_timeout_sec: float,
    parent_timeout_sec: float,
    folder_timeout_sec: float,
    import_timeout_sec: float,
    kitter_launcher: Path | None,
    logger: _Logger,
) -> dict[str, Any]:
    logger.write(f"CSV: {csv_path}")
    logger.write(f"Output folder: {output_folder}")
    nest = _open_project_if_needed(
        project_path=project_path,
        process_id=process_id,
        timeout_sec=project_open_timeout_sec,
        logger=logger,
    )
    actual_pid = int(nest["process_id"])
    logger.write(f"Target RADAN PID: {actual_pid}")
    logger.write("Looking for RADAN's Import Parts launcher button...")
    import_button = _wait_for_child_by_text(
        int(nest["hwnd"]),
        IMPORT_BUTTON_TEXT,
        timeout_sec=launcher_timeout_sec,
        logger=logger,
    )

    logger.write("Clicking Import Parts launcher...")
    _foreground(int(nest["hwnd"]))
    _click_rect_center(import_button["rect"])

    file_picker = _wait_for_top_window(
        process_id=actual_pid,
        title=IMPORT_DIALOG_TITLE,
        class_name="#32770",
        enabled=True,
        timeout_sec=file_picker_timeout_sec,
        logger=logger,
    )
    _submit_file_picker(int(file_picker["hwnd"]), csv_path, logger)

    parent = _wait_for_top_window(
        process_id=actual_pid,
        title=IMPORT_DIALOG_TITLE,
        class_prefix=IMPORT_PARENT_CLASS_PREFIX,
        enabled=True,
        timeout_sec=parent_timeout_sec,
        logger=logger,
    )
    browse = _wait_for_browse_ready(int(parent["hwnd"]), ingest_timeout_sec, logger)
    _assign_output_folder(
        process_id=actual_pid,
        parent_hwnd=int(parent["hwnd"]),
        browse_button=browse,
        output_folder=output_folder,
        logger=logger,
        folder_timeout_sec=folder_timeout_sec,
    )
    logger.write("Output folder assignment step completed.")
    import_result = _run_import_all(
        process_id=actual_pid,
        parent_hwnd=int(parent["hwnd"]),
        timeout_sec=import_timeout_sec,
        logger=logger,
    )
    logger.write("Import All completed.")
    _close_import_parent_if_open(int(parent["hwnd"]), logger)
    _save_and_close_radan_project(
        nest_hwnd=int(nest["hwnd"]),
        process_id=actual_pid,
        logger=logger,
    )
    _launch_kitter(kitter_launcher, project_path, logger)

    return {
        "ok": True,
        "process_id": actual_pid,
        "nest_title": nest["title"],
        "csv_path": str(csv_path),
        "project_path": None if project_path is None else str(project_path),
        "output_folder": str(output_folder),
        "import_button_rect": import_button["rect"],
        "parent_hwnd": parent["hwnd"],
        "browse_button_rect": browse["rect"],
        "import_all": import_result,
        "kitter_launcher": None if kitter_launcher is None else str(kitter_launcher),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Open RADAN Nest Import Parts for a generated _Radan.csv and wait until "
            "the CSV rows are ready for output-folder assignment."
        )
    )
    parser.add_argument("--csv", required=True, help="Generated inventor_to_radan _Radan.csv path.")
    parser.add_argument("--output-folder", required=True, help="Expected RADAN symbol output folder.")
    parser.add_argument("--project", help="RPD project to open if RADAN is not already in Nest Editor.")
    parser.add_argument("--kitter-launcher", help="RADAN Kitter launcher to start after save/close.")
    parser.add_argument("--process-id", type=int, help="Optional visible RADAN Nest Editor PID guard.")
    parser.add_argument("--ingest-timeout-sec", type=float, default=420.0)
    parser.add_argument("--project-open-timeout-sec", type=float, default=180.0)
    parser.add_argument("--launcher-timeout-sec", type=float, default=180.0)
    parser.add_argument("--file-picker-timeout-sec", type=float, default=90.0)
    parser.add_argument("--parent-timeout-sec", type=float, default=120.0)
    parser.add_argument("--folder-timeout-sec", type=float, default=120.0)
    parser.add_argument("--import-timeout-sec", type=float, default=420.0)
    parser.add_argument("--log-file", help="Optional progress log file for Truck Nest Explorer.")
    args = parser.parse_args()

    logger = _Logger(Path(args.log_file).expanduser().resolve() if args.log_file else None)
    csv_path = Path(args.csv).expanduser().resolve()
    output_folder = Path(args.output_folder).expanduser().resolve()
    project_path = Path(args.project).expanduser().resolve() if args.project else None
    kitter_launcher = Path(args.kitter_launcher).expanduser().resolve() if args.kitter_launcher else None
    if not csv_path.exists():
        raise SystemExit(f"CSV not found: {csv_path}")
    if not output_folder.exists():
        raise SystemExit(f"Output folder not found: {output_folder}")
    if project_path is not None and not project_path.exists():
        raise SystemExit(f"Project not found: {project_path}")
    if kitter_launcher is not None and not kitter_launcher.exists():
        raise SystemExit(f"RADAN Kitter launcher not found: {kitter_launcher}")

    try:
        payload = _run(
            csv_path=csv_path,
            output_folder=output_folder,
            process_id=args.process_id,
            ingest_timeout_sec=max(5.0, float(args.ingest_timeout_sec)),
            project_path=project_path,
            project_open_timeout_sec=max(5.0, float(args.project_open_timeout_sec)),
            launcher_timeout_sec=max(5.0, float(args.launcher_timeout_sec)),
            file_picker_timeout_sec=max(5.0, float(args.file_picker_timeout_sec)),
            parent_timeout_sec=max(5.0, float(args.parent_timeout_sec)),
            folder_timeout_sec=max(5.0, float(args.folder_timeout_sec)),
            import_timeout_sec=max(5.0, float(args.import_timeout_sec)),
            kitter_launcher=kitter_launcher,
            logger=logger,
        )
    except Exception as exc:
        logger.write(f"ERROR: {exc}")
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2, ensure_ascii=True))
        return 1

    logger.write("Done.")
    print(json.dumps(payload, indent=2, ensure_ascii=True))
    print()
    print("CSV rows are ready in RADAN Import Parts.")
    print(f"Import completed, RADAN project closed, and Kitter launch requested for: {project_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
