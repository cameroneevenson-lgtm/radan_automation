from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from radan_com import attach_application, list_visible_radan_sessions


DEFAULT_MAC_FIELDS = (
    "PRS",
    "COP",
    "CUP",
    "PART_PATTERN",
    "FI0",
    "FP0",
    "FT0",
    "LT0",
    "S0X",
    "S0Y",
    "TS0X",
    "TS0Y",
    "TE0X",
    "TE0Y",
)


def _read_mac_fields(app: Any, fields: tuple[str, ...] = DEFAULT_MAC_FIELDS) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for field in fields:
        try:
            values[field] = app._backend.get_path_property(("Mac",), field)
        except Exception as exc:  # pragma: no cover - live probe utility
            values[field] = f"ERR:{exc}"
    return values


def _active_document_state(app: Any) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for field in ("Type", "Dirty"):
        try:
            values[field] = app._backend.get_path_property(("ActiveDocument",), field)
        except Exception as exc:  # pragma: no cover - live probe utility
            values[field] = f"ERR:{exc}"
    return values


def _scan(app: Any, *, path: str, feature_filter: str) -> dict[str, Any]:
    mac = app.mac
    rows: list[dict[str, Any]] = []
    started = bool(mac.scan(path, feature_filter, 0))
    if started:
        try:
            while bool(mac.next()):
                rows.append(_read_mac_fields(app))
        finally:
            mac.end_scan()
    return {
        "path": path,
        "filter": feature_filter,
        "started": started,
        "row_count": len(rows),
        "rows": rows,
    }


def probe_hidden_symbol(
    *,
    sym_path: Path,
    expected_pid: int,
    scan_paths: list[str],
    filters: list[str],
    backend: str | None = None,
    allow_visible_sessions: bool = False,
) -> dict[str, Any]:
    visible_sessions = list_visible_radan_sessions()
    blocking_sessions = [
        session
        for session in visible_sessions
        if session.process_id != expected_pid
    ]
    if blocking_sessions and not allow_visible_sessions:
        sessions = ", ".join(
            f"{session.process_id}:{session.window_title}"
            for session in blocking_sessions
        )
        raise RuntimeError(
            "Visible RADAN session(s) are open, so the hidden scan probe was not run: "
            f"{sessions}"
        )

    with attach_application(backend=backend) as app:
        info = app.info()
        if info.process_id != expected_pid:
            raise RuntimeError(
                f"Attached RADAN PID {info.process_id} did not match expected hidden PID {expected_pid}."
            )
        if info.visible:
            raise RuntimeError(f"Expected PID {expected_pid} is visible; refusing to probe it.")

        before_mac = _read_mac_fields(app)
        app.open_symbol(str(sym_path), True, "")
        after_open_info = app.info()
        after_open_mac = _read_mac_fields(app)
        active_document = _active_document_state(app)
        scans: list[dict[str, Any]] = []
        try:
            for scan_path in scan_paths:
                for feature_filter in filters:
                    scans.append(_scan(app, path=scan_path, feature_filter=feature_filter))
        finally:
            try:
                app.close_active_document(True)
            except Exception:
                pass

        return {
            "sym_path": str(sym_path),
            "expected_pid": expected_pid,
            "attached_info": info.__dict__,
            "after_open_info": after_open_info.__dict__,
            "before_mac": before_mac,
            "after_open_mac": after_open_mac,
            "active_document": active_document,
            "scans": scans,
        }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.tmp")
    temp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True) + "\n", encoding="utf-8")
    temp_path.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe a copied .sym via a known hidden RADAN process.")
    parser.add_argument("--sym", type=Path, required=True, help="Copied .sym file to open.")
    parser.add_argument("--expected-pid", type=int, required=True, help="Expected hidden automation-owned RADAN PID.")
    parser.add_argument("--out", type=Path, help="Optional JSON output path.")
    parser.add_argument("--backend", help="Optional COM backend, for example win32com or comtypes.")
    parser.add_argument(
        "--scan-path",
        action="append",
        dest="scan_paths",
        default=None,
        help="Scan path to try. Can be passed more than once.",
    )
    parser.add_argument(
        "--filter",
        action="append",
        dest="filters",
        default=None,
        help="Scan filter to try. Can be passed more than once. Empty string is included by default.",
    )
    parser.add_argument(
        "--allow-visible-sessions",
        action="store_true",
        help="Allow probe to run even when other visible RADAN sessions exist.",
    )
    args = parser.parse_args()

    payload = probe_hidden_symbol(
        sym_path=args.sym,
        expected_pid=int(args.expected_pid),
        scan_paths=args.scan_paths or ["/symbol editor"],
        filters=args.filters if args.filters is not None else ["l", "a", ""],
        backend=args.backend,
        allow_visible_sessions=bool(args.allow_visible_sessions),
    )
    if args.out:
        write_json(args.out, payload)
    print(
        json.dumps(
            {
                "sym_path": payload["sym_path"],
                "expected_pid": payload["expected_pid"],
                "scan_counts": [
                    {
                        "path": scan["path"],
                        "filter": scan["filter"],
                        "started": scan["started"],
                        "row_count": scan["row_count"],
                    }
                    for scan in payload["scans"]
                ],
            },
            indent=2,
            ensure_ascii=True,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
