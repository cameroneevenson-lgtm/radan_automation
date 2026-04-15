from __future__ import annotations

import argparse
import json

from radan_com import describe_live_session, list_visible_radan_sessions


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read-only probe of the active live RADAN UI session.",
    )
    parser.add_argument(
        "--backend",
        help="Optional backend override, for example win32com, comtypes, or powershell.",
    )
    parser.add_argument(
        "--expect-pid",
        type=int,
        help="Fail unless the attached RADAN PID matches this process ID.",
    )
    parser.add_argument(
        "--window-title-contains",
        help="Fail unless the attached RADAN window title contains this text.",
    )
    parser.add_argument(
        "--require-part-editor",
        action="store_true",
        help="Fail unless the attached RADAN session is in Part Editor mode.",
    )
    parser.add_argument(
        "--list-visible-sessions",
        action="store_true",
        help="List visible RADAN UI sessions instead of attaching to the active automation object.",
    )
    args = parser.parse_args()

    if args.list_visible_sessions:
        sessions = list_visible_radan_sessions()
        payload = [
            {
                "pid": session.process_id,
                "title": session.window_title,
                "mode": session.editor_mode,
            }
            for session in sessions
        ]
        print(json.dumps(payload, indent=2))
        return 0

    session = describe_live_session(
        backend=args.backend,
        expected_process_id=args.expect_pid,
        window_title_contains=args.window_title_contains,
        require_part_editor=args.require_part_editor,
    )

    payload = {
        "pid": session.process_id,
        "title": session.window_title,
        "mode": session.editor_mode,
        "pattern": session.pattern,
        "visible": session.visible,
        "interactive": session.interactive,
        "backend": session.application.backend,
        "software_version": session.application.software_version,
        "bounds": None
        if session.bounds is None
        else {
            "left": session.bounds.left,
            "bottom": session.bounds.bottom,
            "right": session.bounds.right,
            "top": session.bounds.top,
            "width": session.bounds.width,
            "height": session.bounds.height,
            "center_x": session.bounds.center_x,
            "center_y": session.bounds.center_y,
        },
    }
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
