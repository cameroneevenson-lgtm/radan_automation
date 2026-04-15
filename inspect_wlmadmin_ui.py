from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Iterable

import win32con
import win32gui


@dataclass(frozen=True)
class WindowInfo:
    hwnd: int
    depth: int
    class_name: str
    text: str
    rect: tuple[int, int, int, int]


def _iter_children(hwnd: int, depth: int = 0) -> Iterable[WindowInfo]:
    children: list[int] = []
    win32gui.EnumChildWindows(hwnd, lambda child, param: param.append(child) or True, children)
    for child in children:
        yield WindowInfo(
            hwnd=child,
            depth=depth,
            class_name=win32gui.GetClassName(child),
            text=win32gui.GetWindowText(child),
            rect=win32gui.GetWindowRect(child),
        )
        yield from _iter_children(child, depth + 1)


def _find_main_window(title: str) -> int:
    matches: list[int] = []

    def _callback(hwnd: int, param: list[int]) -> bool:
        if win32gui.IsWindowVisible(hwnd) and win32gui.GetWindowText(hwnd) == title:
            param.append(hwnd)
        return True

    win32gui.EnumWindows(_callback, matches)
    if not matches:
        raise SystemExit(f"Window titled {title!r} was not found.")
    return matches[0]


def _format_rect(rect: tuple[int, int, int, int]) -> str:
    left, top, right, bottom = rect
    return f"({left},{top})-({right},{bottom})"


def main() -> int:
    parser = argparse.ArgumentParser(description="Dump the visible WlmAdmin window hierarchy.")
    parser.add_argument("--title", default="WlmAdmin", help="Exact top-level window title to inspect.")
    parser.add_argument(
        "--classes",
        nargs="*",
        default=[],
        help="Optional class-name filter. Example: SysTreeView32 SysListView32 Static",
    )
    args = parser.parse_args()

    hwnd = _find_main_window(args.title)
    print(f"TopWindow hwnd=0x{hwnd:08X} title={win32gui.GetWindowText(hwnd)!r}")
    print(f"TopWindow class={win32gui.GetClassName(hwnd)!r} rect={_format_rect(win32gui.GetWindowRect(hwnd))}")

    class_filter = {name.lower() for name in args.classes}
    for info in _iter_children(hwnd, depth=1):
        if class_filter and info.class_name.lower() not in class_filter:
            continue
        indent = "  " * info.depth
        print(
            f"{indent}hwnd=0x{info.hwnd:08X} class={info.class_name!r} "
            f"text={info.text!r} rect={_format_rect(info.rect)}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
