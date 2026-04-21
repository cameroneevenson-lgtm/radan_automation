from __future__ import annotations

import argparse
import json
import time
from typing import Any

from radan_com import attach_application


_MAC_FIELDS = (
    "PRS",
    "CUP",
    "COP",
    "PART_PATTERN",
    "PCC_PATTERN_LAYOUT",
    "FI0",
    "FT0",
    "TF0",
    "FP0",
    "LL0",
    "LT0",
    "MT0",
    "S0X",
    "S0Y",
    "TE0X",
    "TE0Y",
    "TS0X",
    "TS0Y",
)


def _read_state(*, backend: str | None = None) -> dict[str, Any]:
    with attach_application(backend=backend) as app:
        info = app.info()
        backend_impl = app._backend

        mac_values: dict[str, Any] = {}
        for name in _MAC_FIELDS:
            try:
                mac_values[name] = backend_impl.get_path_property(("Mac",), name)
            except Exception as exc:  # pragma: no cover - live probe utility
                mac_values[name] = f"ERR:{exc}"

        return {
            "backend": app.backend_name,
            "process_id": info.process_id,
            "visible": info.visible,
            "interactive": info.interactive,
            "gui_state": info.gui_state,
            "gui_sub_state": info.gui_sub_state,
            "prompt": mac_values["PRS"],
            "current_pattern_path": mac_values["CUP"],
            "open_pattern_path": mac_values["COP"],
            "part_pattern": mac_values["PART_PATTERN"],
            "layout_pattern": mac_values["PCC_PATTERN_LAYOUT"],
            "mac": mac_values,
        }


def _state_signature(state: dict[str, Any]) -> str:
    return json.dumps(state, sort_keys=True, ensure_ascii=True, default=str)


def _changed_fields(previous: dict[str, Any] | None, current: dict[str, Any]) -> list[str]:
    if previous is None:
        return sorted(current.keys())
    return sorted(name for name in current if previous.get(name) != current.get(name))


def _watch_live_session(
    *,
    seconds: float,
    interval: float,
    backend: str | None = None,
) -> list[dict[str, Any]]:
    deadline = time.monotonic() + seconds
    rows: list[dict[str, Any]] = []
    last_state: dict[str, Any] | None = None
    last_signature: str | None = None

    while time.monotonic() < deadline:
        timestamp = time.time()
        try:
            state = _read_state(backend=backend)
        except Exception as exc:  # pragma: no cover - live probe utility
            state = {"error": str(exc)}

        signature = _state_signature(state)
        if signature != last_signature:
            rows.append(
                {
                    "ts": timestamp,
                    "changed_fields": _changed_fields(last_state, state),
                    "state": state,
                }
            )
            last_state = state
            last_signature = signature

        time.sleep(interval)

    return rows


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Watch an attached live RADAN session and emit only real state transitions.",
    )
    parser.add_argument(
        "--seconds",
        type=float,
        default=30.0,
        help="How long to watch for transitions.",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=0.2,
        help="Sampling interval in seconds.",
    )
    parser.add_argument(
        "--backend",
        help="Optional backend override, for example powershell or win32com.",
    )
    args = parser.parse_args()

    rows = _watch_live_session(
        seconds=max(0.1, float(args.seconds)),
        interval=max(0.05, float(args.interval)),
        backend=args.backend,
    )
    print(json.dumps(rows, indent=2, ensure_ascii=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
