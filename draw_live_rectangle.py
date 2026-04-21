from __future__ import annotations

import argparse
import json
import sys

from radan_com import RadanComError, attach_live_application


def _session_payload(result: object) -> dict[str, object]:
    session = result.session
    return {
        "pid": session.process_id,
        "title": session.window_title,
        "mode": session.editor_mode,
        "backend": session.application.backend,
        "pattern": session.pattern,
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


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Draw a rectangle into the currently attached live RADAN Part Editor session.",
    )
    parser.add_argument("--backend", help="Optional backend override, for example win32com or powershell.")
    parser.add_argument("--expect-pid", type=int, help="Fail unless the attached RADAN PID matches this value.")
    parser.add_argument(
        "--window-title-contains",
        help="Fail unless the attached RADAN window title contains this text.",
    )
    parser.add_argument("--width", type=float, default=25.0)
    parser.add_argument("--height", type=float, default=25.0)
    parser.add_argument("--gap", type=float, default=10.0)
    parser.add_argument("--x", type=float)
    parser.add_argument("--y", type=float)
    parser.add_argument("--center-on-bounds", action="store_true")
    parser.add_argument("--use-explicit-position", action="store_true")
    args = parser.parse_args()

    if args.use_explicit_position and (args.x is None or args.y is None):
        parser.error("--use-explicit-position requires both --x and --y.")
    if (args.x is not None or args.y is not None) and not args.use_explicit_position:
        parser.error("Pass --use-explicit-position when supplying --x/--y.")

    try:
        with attach_live_application(
            backend=args.backend,
            expected_process_id=args.expect_pid,
            window_title_contains=args.window_title_contains,
            require_part_editor=True,
        ) as live:
            if args.center_on_bounds:
                result = live.draw_rectangle_centered(width=args.width, height=args.height)
            elif args.use_explicit_position:
                result = live.draw_rectangle_at(x=args.x, y=args.y, width=args.width, height=args.height)
            else:
                result = live.draw_rectangle_right_of_bounds(
                    width=args.width,
                    height=args.height,
                    gap=args.gap,
                )
    except RadanComError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    payload = {
        "x": result.x,
        "y": result.y,
        "width": result.width,
        "height": result.height,
        "session": _session_payload(result),
    }
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
