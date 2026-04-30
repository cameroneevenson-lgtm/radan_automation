from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

from ddc_corpus import read_ddc_records, read_dxf_entities
from ddc_number_codec import decode_ddc_number_fraction
from evaluate_exported_coordinate_token_model import slot_role, value_key
from path_safety import assert_w_drive_write_allowed


DEFAULT_LAB_ROOT = Path(__file__).resolve().parent / "_sym_lab"


def _token(row: dict[str, Any], slot: int) -> str:
    tokens = list(row.get("tokens") or [])
    return str(tokens[slot]) if slot < len(tokens) else ""


def _safe_fraction(token: str) -> Any:
    try:
        return decode_ddc_number_fraction(token)
    except Exception:
        return None


def _fraction_text(value: Any) -> str:
    if value is None:
        return ""
    return f"{value.numerator}/{value.denominator}"


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def _decoded_bucket(abs_diff: float | None) -> str:
    if abs_diff is None:
        return "decode_error"
    if abs_diff == 0:
        return "equal"
    if abs_diff <= 1e-15:
        return "close_1e-15"
    if abs_diff <= 1e-12:
        return "close_1e-12"
    return "far"


def _role_key(entity_type: str, slot: int) -> str:
    return f"{entity_type}:{slot_role(entity_type, slot)}"


def _normalize_role_filters(values: Iterable[str]) -> set[str]:
    filters: set[str] = set()
    for value in values:
        text = str(value).strip()
        if not text:
            continue
        filters.add(text.casefold())
    return filters


def _role_allowed(entity_type: str, role: str, filters: set[str]) -> bool:
    if not filters:
        return True
    return role.casefold() in filters or f"{entity_type}:{role}".casefold() in filters


def slot_visible_value(dxf_row: dict[str, Any], slot: int) -> float | None:
    entity_type = str(dxf_row.get("type", ""))
    if entity_type == "LINE":
        start_x, start_y = [float(value) for value in dxf_row["normalized_start"]]
        end_x, end_y = [float(value) for value in dxf_row["normalized_end"]]
        return {
            0: start_x,
            1: start_y,
            2: end_x - start_x,
            3: end_y - start_y,
        }.get(slot)
    if entity_type == "ARC":
        start_x, start_y = [float(value) for value in dxf_row["normalized_start_point"]]
        end_x, end_y = [float(value) for value in dxf_row["normalized_end_point"]]
        center_x, center_y = [float(value) for value in dxf_row["normalized_center"]]
        return {
            0: start_x,
            1: start_y,
            2: end_x - start_x,
            3: end_y - start_y,
            4: center_x - start_x,
            5: center_y - start_y,
            6: 1.0,
            9: 1.0,
        }.get(slot)
    if entity_type == "CIRCLE":
        center_x, center_y = [float(value) for value in dxf_row["normalized_center"]]
        radius = float(dxf_row["radius"])
        return {
            0: center_x + radius,
            1: center_y,
            4: -radius,
            5: 0.0,
            6: 1.0,
            9: 1.0,
        }.get(slot)
    return None


def _geometry_context(dxf_row: dict[str, Any]) -> dict[str, Any]:
    context = {
        "radius": None,
        "normalized_start_x": None,
        "normalized_start_y": None,
        "normalized_end_x": None,
        "normalized_end_y": None,
        "normalized_center_x": None,
        "normalized_center_y": None,
        "dxf_delta_x": None,
        "dxf_delta_y": None,
        "dxf_center_delta_x": None,
        "dxf_center_delta_y": None,
        "arc_start_angle": None,
        "arc_end_angle": None,
        "circle_start_x": None,
        "circle_start_y": None,
    }
    entity_type = str(dxf_row.get("type"))
    if entity_type == "LINE":
        start_x, start_y = [float(value) for value in dxf_row["normalized_start"]]
        end_x, end_y = [float(value) for value in dxf_row["normalized_end"]]
        context.update(
            {
                "normalized_start_x": start_x,
                "normalized_start_y": start_y,
                "normalized_end_x": end_x,
                "normalized_end_y": end_y,
                "dxf_delta_x": end_x - start_x,
                "dxf_delta_y": end_y - start_y,
            }
        )
        return context
    if entity_type == "ARC":
        start_x, start_y = [float(value) for value in dxf_row["normalized_start_point"]]
        end_x, end_y = [float(value) for value in dxf_row["normalized_end_point"]]
        center_x, center_y = [float(value) for value in dxf_row["normalized_center"]]
        context.update(
            {
                "radius": float(dxf_row["radius"]),
                "normalized_start_x": start_x,
                "normalized_start_y": start_y,
                "normalized_end_x": end_x,
                "normalized_end_y": end_y,
                "normalized_center_x": center_x,
                "normalized_center_y": center_y,
                "dxf_delta_x": end_x - start_x,
                "dxf_delta_y": end_y - start_y,
                "dxf_center_delta_x": center_x - start_x,
                "dxf_center_delta_y": center_y - start_y,
                "arc_start_angle": float(dxf_row["start_angle"]),
                "arc_end_angle": float(dxf_row["end_angle"]),
            }
        )
        return context
    if entity_type != "CIRCLE":
        return context
    center_x, center_y = [float(value) for value in dxf_row["normalized_center"]]
    radius = float(dxf_row["radius"])
    start_x = center_x + radius
    return {
        **context,
        "radius": radius,
        "normalized_start_x": start_x,
        "normalized_start_y": center_y,
        "normalized_center_x": center_x,
        "normalized_center_y": center_y,
        "dxf_center_delta_x": -radius,
        "dxf_center_delta_y": 0.0,
        "circle_start_x": start_x,
        "circle_start_y": center_y,
    }


def _topology_context(dxf_rows: list[dict[str, Any]], row_index: int) -> dict[str, Any]:
    zero_index = int(row_index) - 1
    entity_type = str(dxf_rows[zero_index].get("type", ""))
    type_sequence = [str(row.get("type", "")) for row in dxf_rows]
    prefix = type_sequence[:zero_index]
    suffix = type_sequence[zero_index + 1 :]
    same_type_before = sum(1 for value in prefix if value == entity_type)
    return {
        "entity_count": len(dxf_rows),
        "row_position_from_end": len(dxf_rows) - zero_index,
        "same_type_ordinal": same_type_before + 1,
        "same_type_remaining": sum(1 for value in suffix if value == entity_type),
        "prefix_line_count": sum(1 for value in prefix if value == "LINE"),
        "prefix_arc_count": sum(1 for value in prefix if value == "ARC"),
        "prefix_circle_count": sum(1 for value in prefix if value == "CIRCLE"),
        "previous_two_dxf_types": "/".join(type_sequence[max(0, zero_index - 2) : zero_index]),
        "next_two_dxf_types": "/".join(type_sequence[zero_index + 1 : zero_index + 3]),
        "type_sequence_signature": "".join(value[:1] for value in type_sequence),
        "prefix_type_signature": "".join(value[:1] for value in prefix),
    }


def _context_row(
    *,
    part: str,
    row_index: int,
    dxf_rows: list[dict[str, Any]],
    generated_row: dict[str, Any],
    oracle_row: dict[str, Any],
    slot: int,
    value_digits: int,
    bounds: Any | None = None,
) -> dict[str, Any]:
    dxf_row = dxf_rows[row_index - 1]
    entity_type = str(dxf_row.get("type", ""))
    role = slot_role(entity_type, slot)
    generated_token = _token(generated_row, slot)
    oracle_token = _token(oracle_row, slot)
    generated_fraction = _safe_fraction(generated_token)
    oracle_fraction = _safe_fraction(oracle_token)
    decoded_abs_diff = (
        None
        if generated_fraction is None or oracle_fraction is None
        else abs(float(oracle_fraction - generated_fraction))
    )
    visible = slot_visible_value(dxf_row, slot)
    previous_dxf_type = str(dxf_rows[row_index - 2].get("type", "")) if row_index > 1 else ""
    next_dxf_type = str(dxf_rows[row_index].get("type", "")) if row_index < len(dxf_rows) else ""
    row = {
        "part": part,
        "row_index": row_index,
        "is_first_geometry": row_index == 1,
        "is_last_geometry": row_index == len(dxf_rows),
        "previous_dxf_type": previous_dxf_type,
        "next_dxf_type": next_dxf_type,
        "dxf_type": entity_type,
        "layer": str(dxf_row.get("layer", "")),
        "ddc_record": str(generated_row.get("record", "")),
        "ddc_identifier": str(generated_row.get("identifier", "")),
        "slot": slot,
        "role": role,
        "role_key": _role_key(entity_type, slot),
        "visible_value": visible,
        "visible_value_key": "" if visible is None else value_key(float(visible), digits=value_digits),
        "generated_token": generated_token,
        "oracle_token": oracle_token,
        "token_match": generated_token == oracle_token,
        "generated_fraction": _fraction_text(generated_fraction),
        "oracle_fraction": _fraction_text(oracle_fraction),
        "generated_decoded": _float_or_none(generated_fraction),
        "oracle_decoded": _float_or_none(oracle_fraction),
        "decoded_abs_diff": decoded_abs_diff,
        "decoded_bucket": _decoded_bucket(decoded_abs_diff),
        "token_length_delta": len(oracle_token) - len(generated_token),
    }
    row.update(_geometry_context(dxf_row))
    row.update(_topology_context(dxf_rows, row_index))
    if bounds is not None:
        row.update(
            {
                "bounds_min_x": float(bounds.min_x),
                "bounds_min_y": float(bounds.min_y),
                "bounds_max_x": float(bounds.max_x),
                "bounds_max_y": float(bounds.max_y),
                "bounds_width": float(bounds.width),
                "bounds_height": float(bounds.height),
            }
        )
    return row


def analyze_symbol_token_context(
    *,
    dxf_folder: Path,
    generated_sym_folder: Path,
    oracle_sym_folder: Path,
    parts: list[str] | None = None,
    exclude_parts: list[str] | None = None,
    roles: list[str] | None = None,
    value_digits: int = 15,
) -> dict[str, Any]:
    dxf_by_part = {path.stem.casefold(): path for path in dxf_folder.glob("*.dxf")}
    generated_by_part = {path.stem.casefold(): path for path in generated_sym_folder.glob("*.sym")}
    oracle_by_part = {path.stem.casefold(): path for path in oracle_sym_folder.glob("*.sym")}
    requested = [part.casefold() for part in parts] if parts else sorted(set(dxf_by_part) & set(generated_by_part) & set(oracle_by_part))
    excluded = {part.casefold() for part in (exclude_parts or [])}
    requested = [part for part in requested if part not in excluded]
    role_filters = _normalize_role_filters(roles or [])

    rows: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    for key in requested:
        dxf_path = dxf_by_part.get(key)
        generated_path = generated_by_part.get(key)
        oracle_path = oracle_by_part.get(key)
        if dxf_path is None or generated_path is None or oracle_path is None:
            skipped.append({"part": key, "reason": "missing_dxf_or_sym"})
            continue
        dxf_rows, bounds = read_dxf_entities(dxf_path)
        generated_rows = read_ddc_records(generated_path)
        oracle_rows = read_ddc_records(oracle_path)
        if len(dxf_rows) != len(generated_rows) or len(dxf_rows) != len(oracle_rows):
            skipped.append(
                {
                    "part": dxf_path.stem,
                    "reason": f"row_count_mismatch:dxf={len(dxf_rows)} generated={len(generated_rows)} oracle={len(oracle_rows)}",
                }
            )
            continue
        for row_index, (generated_row, oracle_row) in enumerate(zip(generated_rows, oracle_rows), start=1):
            dxf_type = str(dxf_rows[row_index - 1].get("type", ""))
            max_slots = max(len(generated_row.get("tokens") or []), len(oracle_row.get("tokens") or []))
            for slot in range(max_slots):
                role = slot_role(dxf_type, slot)
                if not _role_allowed(dxf_type, role, role_filters):
                    continue
                rows.append(
                    _context_row(
                        part=dxf_path.stem,
                        row_index=row_index,
                        dxf_rows=dxf_rows,
                        generated_row=generated_row,
                        oracle_row=oracle_row,
                        slot=slot,
                        value_digits=value_digits,
                        bounds=bounds,
                    )
                )

    return {
        "schema_version": 1,
        "dxf_folder": str(dxf_folder),
        "generated_sym_folder": str(generated_sym_folder),
        "oracle_sym_folder": str(oracle_sym_folder),
        "parts_requested": parts or [],
        "exclude_parts": exclude_parts or [],
        "roles": roles or [],
        "value_digits": value_digits,
        "rows": rows,
        "skipped": skipped,
        "summary": summarize_context_rows(rows),
    }


def _top(counter: Counter[Any], *, limit: int = 20) -> list[dict[str, Any]]:
    return [{"key": str(key), "count": count} for key, count in counter.most_common(limit)]


def _example(row: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "part",
        "row_index",
        "dxf_type",
        "role",
        "slot",
        "visible_value_key",
        "generated_token",
        "oracle_token",
        "decoded_abs_diff",
        "previous_dxf_type",
        "next_dxf_type",
        "is_first_geometry",
        "radius",
        "normalized_start_x",
        "normalized_start_y",
        "normalized_end_x",
        "normalized_end_y",
        "normalized_center_x",
        "normalized_center_y",
        "dxf_delta_x",
        "dxf_delta_y",
        "dxf_center_delta_x",
        "dxf_center_delta_y",
        "arc_start_angle",
        "arc_end_angle",
        "entity_count",
        "row_position_from_end",
        "same_type_ordinal",
        "same_type_remaining",
        "prefix_line_count",
        "prefix_arc_count",
        "prefix_circle_count",
        "previous_two_dxf_types",
        "next_two_dxf_types",
        "type_sequence_signature",
        "prefix_type_signature",
        "bounds_width",
        "bounds_height",
    ]
    return {key: row.get(key) for key in keys}


def _code(value: Any) -> str:
    text = str(value)
    if "`" not in text:
        return f"`{text}`"
    longest = 0
    current = 0
    for char in text:
        if char == "`":
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    fence = "`" * (longest + 1)
    return f"{fence} {text} {fence}"


def _summarize_focus(rows: list[dict[str, Any]], focus: dict[str, Any]) -> dict[str, Any]:
    same_value = [
        row
        for row in rows
        if row["role_key"] == focus["role_key"] and row["visible_value_key"] == focus["visible_value_key"]
    ]
    same_role = [row for row in rows if row["role_key"] == focus["role_key"]]
    context_counter = Counter(
        (
            row["previous_dxf_type"],
            row["next_dxf_type"],
            row["is_first_geometry"],
            row.get("radius"),
            row["generated_token"],
            row["oracle_token"],
        )
        for row in same_value
    )
    return {
        "focus": _example(focus),
        "same_role_count": len(same_role),
        "same_value_count": len(same_value),
        "same_value_mismatch_count": sum(1 for row in same_value if not row["token_match"]),
        "same_value_generated_token_counts": _top(Counter(row["generated_token"] for row in same_value), limit=20),
        "same_value_oracle_token_counts": _top(Counter(row["oracle_token"] for row in same_value), limit=20),
        "same_value_generated_to_oracle_counts": _top(
            Counter(f"{row['generated_token']} -> {row['oracle_token']}" for row in same_value),
            limit=20,
        ),
        "same_value_context_counts": _top(context_counter, limit=20),
        "same_value_examples": [_example(row) for row in same_value[:25]],
    }


def summarize_context_rows(
    rows: list[dict[str, Any]],
    *,
    focus_part: str | None = None,
    focus_row: int | None = None,
    focus_slot: int | None = None,
) -> dict[str, Any]:
    mismatches = [row for row in rows if not row["token_match"]]
    by_role: dict[str, dict[str, Any]] = {}
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["role_key"])].append(row)
    for role_key, role_rows in sorted(grouped.items()):
        role_mismatches = [row for row in role_rows if not row["token_match"]]
        by_role[role_key] = {
            "slot_count": len(role_rows),
            "mismatch_count": len(role_mismatches),
            "exact_token_rate": (len(role_rows) - len(role_mismatches)) / len(role_rows) if role_rows else 0.0,
            "generated_token_counts": _top(Counter(row["generated_token"] for row in role_rows), limit=10),
            "oracle_token_counts": _top(Counter(row["oracle_token"] for row in role_rows), limit=10),
        }

    summary: dict[str, Any] = {
        "slot_count": len(rows),
        "exact_token_count": len(rows) - len(mismatches),
        "mismatch_count": len(mismatches),
        "exact_token_rate": (len(rows) - len(mismatches)) / len(rows) if rows else 0.0,
        "decoded_bucket_counts": dict(sorted(Counter(str(row["decoded_bucket"]) for row in rows).items())),
        "mismatch_decoded_bucket_counts": dict(sorted(Counter(str(row["decoded_bucket"]) for row in mismatches).items())),
        "top_roles_by_mismatch": _top(Counter(row["role_key"] for row in mismatches), limit=20),
        "top_generated_to_oracle_mismatches": _top(
            Counter(f"{row['generated_token']} -> {row['oracle_token']}" for row in mismatches),
            limit=20,
        ),
        "by_role": by_role,
        "examples": [_example(row) for row in mismatches[:25]],
    }

    if focus_part is not None and focus_row is not None and focus_slot is not None:
        focus_matches = [
            row
            for row in rows
            if row["part"].casefold() == focus_part.casefold()
            and int(row["row_index"]) == int(focus_row)
            and int(row["slot"]) == int(focus_slot)
        ]
        if focus_matches:
            summary["focus"] = _summarize_focus(rows, focus_matches[0])
        else:
            summary["focus"] = {
                "requested": {"part": focus_part, "row_index": focus_row, "slot": focus_slot},
                "found": False,
            }
    return summary


CSV_FIELDNAMES = [
    "part",
    "row_index",
    "is_first_geometry",
    "is_last_geometry",
    "previous_dxf_type",
    "next_dxf_type",
    "dxf_type",
    "layer",
    "ddc_record",
    "ddc_identifier",
    "slot",
    "role",
    "role_key",
    "visible_value",
    "visible_value_key",
    "generated_token",
    "oracle_token",
    "token_match",
    "generated_fraction",
    "oracle_fraction",
    "generated_decoded",
    "oracle_decoded",
    "decoded_abs_diff",
    "decoded_bucket",
    "token_length_delta",
    "radius",
    "normalized_start_x",
    "normalized_start_y",
    "normalized_end_x",
    "normalized_end_y",
    "normalized_center_x",
    "normalized_center_y",
    "dxf_delta_x",
    "dxf_delta_y",
    "dxf_center_delta_x",
    "dxf_center_delta_y",
    "arc_start_angle",
    "arc_end_angle",
    "circle_start_x",
    "circle_start_y",
    "entity_count",
    "row_position_from_end",
    "same_type_ordinal",
    "same_type_remaining",
    "prefix_line_count",
    "prefix_arc_count",
    "prefix_circle_count",
    "previous_two_dxf_types",
    "next_two_dxf_types",
    "type_sequence_signature",
    "prefix_type_signature",
    "bounds_min_x",
    "bounds_min_y",
    "bounds_max_x",
    "bounds_max_y",
    "bounds_width",
    "bounds_height",
]


def _assert_sym_lab_output(path: Path) -> None:
    assert_w_drive_write_allowed(path, operation="write symbol token context output")
    lab_root = DEFAULT_LAB_ROOT.resolve()
    resolved = path.resolve()
    if resolved == lab_root or lab_root in resolved.parents:
        return
    raise RuntimeError(f"Refusing to write symbol token context output outside _sym_lab: {path}")


def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    _assert_sym_lab_output(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDNAMES)
        writer.writeheader()
        writer.writerows([{key: row.get(key) for key in CSV_FIELDNAMES} for row in rows])


def write_markdown(result: dict[str, Any], path: Path) -> None:
    _assert_sym_lab_output(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    summary = result["summary"]
    exact_rate = f"{summary['exact_token_rate']:.6f}"
    lines = [
        "# Symbol Token Context Analysis",
        "",
        f"- Generated: {_code(result['generated_sym_folder'])}",
        f"- Oracle: {_code(result['oracle_sym_folder'])}",
        f"- DXF folder: {_code(result['dxf_folder'])}",
        f"- Roles: {_code(', '.join(result['roles']) if result['roles'] else 'all')}",
        f"- Slots analyzed: {_code(summary['slot_count'])}",
        f"- Mismatches: {_code(summary['mismatch_count'])}",
        f"- Exact token rate: {_code(exact_rate)}",
        "",
        "## Top Mismatch Roles",
        "",
    ]
    for row in summary["top_roles_by_mismatch"]:
        lines.append(f"- {_code(row['key'])}: {_code(row['count'])}")
    lines.extend(["", "## Top Token Mismatches", ""])
    for row in summary["top_generated_to_oracle_mismatches"]:
        lines.append(f"- {_code(row['key'])}: {_code(row['count'])}")
    if summary.get("focus"):
        focus = summary["focus"]
        if focus.get("found") is False:
            lines.extend(["", "## Focus", "", f"- Requested focus was not found: {_code(focus['requested'])}"])
        else:
            focus_row = focus["focus"]
            focus_role = f"{focus_row['dxf_type']}:{focus_row['role']}"
            lines.extend(
                [
                    "",
                    "## Focus",
                    "",
                    f"- Part/row/slot: {_code(focus_row['part'])} row {_code(focus_row['row_index'])} slot {_code(focus_row['slot'])}",
                    f"- Role: {_code(focus_role)}",
                    f"- Token: {_code(focus_row['generated_token'])} -> {_code(focus_row['oracle_token'])}",
                    f"- Visible value: {_code(focus_row['visible_value_key'])}",
                    f"- Decoded abs diff: {_code(focus_row['decoded_abs_diff'])}",
                    f"- Same-role rows: {_code(focus['same_role_count'])}",
                    f"- Same visible-value rows: {_code(focus['same_value_count'])}",
                    f"- Same visible-value mismatches: {_code(focus['same_value_mismatch_count'])}",
                    "",
                    "### Same Visible-Value Token Counts",
                    "",
                ]
            )
            for row in focus["same_value_generated_to_oracle_counts"]:
                lines.append(f"- {_code(row['key'])}: {_code(row['count'])}")
            lines.extend(["", "### Same Visible-Value Examples", ""])
            for row in focus["same_value_examples"][:10]:
                lines.append(
                    "- "
                    f"{_code(row['part'])} row {_code(row['row_index'])} "
                    f"prev {_code(row['previous_dxf_type'] or '<start>')} next {_code(row['next_dxf_type'] or '<end>')} "
                    f"token {_code(row['generated_token'])} -> {_code(row['oracle_token'])} "
                    f"radius {_code(row['radius'])}"
                )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Analyze SYM token spellings with local DXF row context.")
    parser.add_argument("--dxf-folder", type=Path, required=True)
    parser.add_argument("--generated-sym-folder", type=Path, required=True)
    parser.add_argument("--oracle-sym-folder", type=Path, required=True)
    parser.add_argument("--part", action="append", default=[])
    parser.add_argument("--exclude-part", action="append", default=[])
    parser.add_argument("--role", action="append", default=[])
    parser.add_argument("--value-digits", type=int, default=15)
    parser.add_argument("--focus-part")
    parser.add_argument("--focus-row", type=int)
    parser.add_argument("--focus-slot", type=int)
    parser.add_argument("--out-json", type=Path, required=True)
    parser.add_argument("--out-csv", type=Path)
    parser.add_argument("--out-md", type=Path)
    args = parser.parse_args(argv)

    for path in [args.out_json, args.out_csv, args.out_md]:
        if path is not None:
            _assert_sym_lab_output(path)
            path.parent.mkdir(parents=True, exist_ok=True)

    result = analyze_symbol_token_context(
        dxf_folder=args.dxf_folder,
        generated_sym_folder=args.generated_sym_folder,
        oracle_sym_folder=args.oracle_sym_folder,
        parts=args.part or None,
        exclude_parts=args.exclude_part or None,
        roles=args.role or None,
        value_digits=args.value_digits,
    )
    result["summary"] = summarize_context_rows(
        result["rows"],
        focus_part=args.focus_part,
        focus_row=args.focus_row,
        focus_slot=args.focus_slot,
    )
    args.out_json.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    if args.out_csv:
        write_csv(result["rows"], args.out_csv)
    if args.out_md:
        write_markdown(result, args.out_md)
    print(json.dumps({"summary": result["summary"], "skipped": result["skipped"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
