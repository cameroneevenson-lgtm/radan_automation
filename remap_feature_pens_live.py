from __future__ import annotations

import argparse
import json
from collections import Counter
from typing import Any

from radan_com import RadanLiveSessionInfo, RadanTargetMismatchError, attach_application, describe_live_session


def _parse_filter_override(value: str) -> tuple[str, int]:
    token, separator, pen_text = value.partition("=")
    token = token.strip()
    pen_text = pen_text.strip()
    if separator != "=" or not token or not pen_text:
        raise argparse.ArgumentTypeError("Expected filter override in the form <filter>=<pen>.")
    try:
        pen = int(pen_text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Invalid pen number in {value!r}.") from exc
    return token, pen


def _normalize_scan_filters(raw_filters: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for raw_filter in raw_filters:
        for token in (part.strip() for part in raw_filter.split(",")):
            if not token or token in seen:
                continue
            normalized.append(token)
            seen.add(token)
    return normalized


def _resolve_pattern(explicit_pattern: str | None, mac: Any) -> str:
    if explicit_pattern:
        return explicit_pattern
    for candidate in (
        mac.current_pattern_path,
        mac.open_pattern_path,
        mac.part_pattern,
    ):
        if candidate:
            return candidate
    raise RuntimeError("Could not determine an active pattern path for the attached part.")


def _assert_attached_app_matches_session(
    app: Any,
    session: RadanLiveSessionInfo,
    *,
    expected_process_id: int | None = None,
) -> None:
    info = app.info()
    attached_pid = info.process_id
    required_pid = expected_process_id if expected_process_id is not None else session.process_id

    if required_pid is not None and attached_pid != required_pid:
        raise RadanTargetMismatchError(
            f"Write-capable RADAN attach resolved PID {attached_pid}, expected PID {required_pid}."
        )
    if session.process_id is not None and attached_pid != session.process_id:
        raise RadanTargetMismatchError(
            f"Write-capable RADAN attach resolved PID {attached_pid}, "
            f"but the validated live session was PID {session.process_id}."
        )


def _scan_filter(mac: Any, pattern: str, feature_filter: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    started = bool(mac.scan(pattern, feature_filter, 0))
    if not started:
        return rows

    try:
        # In live testing, scan() armed the iterator but left FI0/FP0 on the prior feature.
        # Advancing with next() first avoided a stale off-by-one row.
        while mac.next():
            rows.append(
                {
                    "filter": feature_filter,
                    "identifier": mac.current_feature_identifier,
                    "pen": mac.current_feature_pen,
                    "feature_type": mac.current_feature_type,
                    "line_type": mac.current_feature_line_type,
                    "x": mac.current_feature_x,
                    "y": mac.current_feature_y,
                }
            )
    finally:
        mac.end_scan()

    return rows


def _scan_summary(mac: Any, pattern: str, scan_filters: list[str]) -> dict[str, dict[str, Any]]:
    summary: dict[str, dict[str, Any]] = {}
    for feature_filter in scan_filters:
        rows = _scan_filter(mac, pattern, feature_filter)
        pen_counts = Counter(row["pen"] for row in rows)
        summary[feature_filter] = {
            "count": len(rows),
            "pens": {str(pen): count for pen, count in sorted(pen_counts.items(), key=lambda item: str(item[0]))},
        }
    return summary


def _build_candidates(
    mac: Any,
    *,
    pattern: str,
    scan_filters: list[str],
    source_pen: int,
    target_pen: int,
    filter_target_overrides: dict[str, int],
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for feature_filter in scan_filters:
        rows = _scan_filter(mac, pattern, feature_filter)
        for row in rows:
            if row["pen"] != source_pen:
                continue
            resolved_target_pen = filter_target_overrides.get(feature_filter, target_pen)
            if resolved_target_pen == source_pen:
                continue
            if not row["identifier"] or row["x"] is None or row["y"] is None:
                continue
            row["target_pen"] = resolved_target_pen
            candidates.append(row)
    return candidates


def _apply_candidate(mac: Any, candidate: dict[str, Any]) -> dict[str, Any]:
    identifier = str(candidate["identifier"])
    x = float(candidate["x"])
    y = float(candidate["y"])
    target_pen = int(candidate["target_pen"])

    marked = bool(mac.find_xy_identifier(identifier, x, y))
    if not marked:
        return {
            "identifier": identifier,
            "filter": candidate["filter"],
            "from_pen": candidate["pen"],
            "to_pen": target_pen,
            "ok": False,
            "stage": "find_xy_identifier",
            "prompt": mac.prompt_string,
        }

    keystroke_result = mac.keystroke(f"e\\?P,{target_pen}?")
    ok = bool(keystroke_result)
    return {
        "identifier": identifier,
        "filter": candidate["filter"],
        "from_pen": candidate["pen"],
        "to_pen": target_pen,
        "ok": ok,
        "stage": "rfmac",
        "keystroke_result": keystroke_result,
        "prompt": mac.prompt_string,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Attach to an open RADAN Part Editor session and remap feature pens using scan + find_xy_identifier + rfmac.",
    )
    parser.add_argument("--backend", help="Optional backend override, for example win32com or powershell.")
    parser.add_argument("--expected-process-id", type=int, help="Optional live RADAN PID guard.")
    parser.add_argument("--window-title-contains", help="Optional live RADAN title guard.")
    parser.add_argument(
        "--pattern",
        help="Optional explicit pattern path. Defaults to current, then open, then part pattern.",
    )
    parser.add_argument("--source-pen", type=int, required=True, help="Only features on this logical pen are considered.")
    parser.add_argument("--target-pen", type=int, required=True, help="Default destination logical pen.")
    parser.add_argument(
        "--scan-filter",
        action="append",
        default=["l", "a"],
        help="Feature scan filter token to inspect. Repeat or pass a comma-separated list. Defaults to l,a.",
    )
    parser.add_argument(
        "--filter-target",
        action="append",
        type=_parse_filter_override,
        default=[],
        help="Per-filter target override in the form <filter>=<pen>, for example a=9.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Report planned edits without changing the part.")
    args = parser.parse_args()

    scan_filters = _normalize_scan_filters(list(args.scan_filter))
    if not scan_filters:
        raise SystemExit("At least one scan filter is required.")

    filter_target_overrides = dict(args.filter_target)
    session = describe_live_session(
        backend=args.backend,
        expected_process_id=args.expected_process_id,
        window_title_contains=args.window_title_contains,
        require_part_editor=True,
    )

    with attach_application(backend=args.backend) as app:
        _assert_attached_app_matches_session(
            app,
            session,
            expected_process_id=args.expected_process_id,
        )
        mac = app.mac
        pattern = _resolve_pattern(args.pattern, mac)
        before = _scan_summary(mac, pattern, scan_filters)
        candidates = _build_candidates(
            mac,
            pattern=pattern,
            scan_filters=scan_filters,
            source_pen=int(args.source_pen),
            target_pen=int(args.target_pen),
            filter_target_overrides=filter_target_overrides,
        )

        payload: dict[str, Any] = {
            "session": {
                "process_id": session.process_id,
                "window_title": session.window_title,
                "editor_mode": session.editor_mode,
                "pattern": session.pattern,
            },
            "resolved_pattern": pattern,
            "source_pen": int(args.source_pen),
            "target_pen": int(args.target_pen),
            "scan_filters": scan_filters,
            "filter_target_overrides": {key: value for key, value in sorted(filter_target_overrides.items())},
            "dry_run": bool(args.dry_run),
            "before": before,
            "candidate_count": len(candidates),
            "candidate_counts_by_filter": dict(Counter(candidate["filter"] for candidate in candidates)),
            "candidate_counts_by_target_pen": {
                str(pen): count for pen, count in sorted(Counter(candidate["target_pen"] for candidate in candidates).items())
            },
        }

        if args.dry_run:
            payload["results"] = []
            payload["after"] = before
            print(json.dumps(payload, indent=2, ensure_ascii=True))
            return 0

        results = [_apply_candidate(mac, candidate) for candidate in candidates]
        payload["results"] = results
        payload["success_count"] = sum(1 for result in results if result["ok"])
        payload["failure_count"] = sum(1 for result in results if not result["ok"])
        payload["after"] = _scan_summary(mac, pattern, scan_filters)
        print(json.dumps(payload, indent=2, ensure_ascii=True))
        return 0 if payload["failure_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
