from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from ddc_corpus import read_ddc_records, read_dxf_entities
from ddc_number_codec import (
    ddc_number_mantissa_digits,
    ddc_number_mantissa_integer,
    decode_ddc_number_fraction,
)
from evaluate_exported_coordinate_token_model import slot_role, value_key
from path_safety import assert_w_drive_write_allowed


def _token(tokens: list[str], index: int) -> str:
    return str(tokens[index]) if index < len(tokens) else ""


def _exponent_prefix(token: str) -> str:
    return str(token[:2]) if token else ""


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


def _mantissa_delta(oracle_token: str, generated_token: str) -> tuple[int, int, list[int], int | None]:
    try:
        pad_to = max(
            len(ddc_number_mantissa_digits(oracle_token)),
            len(ddc_number_mantissa_digits(generated_token)),
        )
        oracle_digits = ddc_number_mantissa_digits(oracle_token, pad_to=pad_to)
        generated_digits = ddc_number_mantissa_digits(generated_token, pad_to=pad_to)
        digit_deltas = [left - right for left, right in zip(oracle_digits, generated_digits)]
        delta_units = ddc_number_mantissa_integer(oracle_token, pad_to=pad_to) - ddc_number_mantissa_integer(
            generated_token,
            pad_to=pad_to,
        )
        return pad_to, delta_units, digit_deltas, None
    except Exception:
        return 0, 0, [], 1


def token_residual_row(
    *,
    part: str,
    row_index: int,
    dxf_type: str,
    slot: int,
    oracle_token: str,
    generated_token: str,
    visible_value_key: str = "",
) -> dict[str, Any]:
    oracle_fraction = _safe_fraction(oracle_token)
    generated_fraction = _safe_fraction(generated_token)
    decoded_abs_diff = (
        None
        if oracle_fraction is None or generated_fraction is None
        else abs(float(oracle_fraction - generated_fraction))
    )
    pad_to, mantissa_delta_units, digit_deltas, mantissa_error = _mantissa_delta(oracle_token, generated_token)
    same_length = len(oracle_token) == len(generated_token)
    same_prefix_except_last = bool(
        oracle_token
        and generated_token
        and same_length
        and oracle_token[:-1] == generated_token[:-1]
        and oracle_token[-1] != generated_token[-1]
    )

    return {
        "part": part,
        "row_index": row_index,
        "dxf_type": dxf_type,
        "slot": slot,
        "role": slot_role(dxf_type, slot),
        "visible_value_key": visible_value_key,
        "oracle_token": oracle_token,
        "generated_token": generated_token,
        "token_match": oracle_token == generated_token,
        "oracle_fraction": _fraction_text(oracle_fraction),
        "generated_fraction": _fraction_text(generated_fraction),
        "oracle_decoded": _float_or_none(oracle_fraction),
        "generated_decoded": _float_or_none(generated_fraction),
        "decoded_abs_diff": decoded_abs_diff,
        "decoded_bucket": _decoded_bucket(decoded_abs_diff),
        "same_exponent_prefix": _exponent_prefix(oracle_token) == _exponent_prefix(generated_token),
        "oracle_exponent_prefix": _exponent_prefix(oracle_token),
        "generated_exponent_prefix": _exponent_prefix(generated_token),
        "token_length_delta": len(oracle_token) - len(generated_token),
        "same_prefix_except_last_char": same_prefix_except_last,
        "last_char_delta": (
            ord(oracle_token[-1]) - ord(generated_token[-1])
            if same_prefix_except_last
            else None
        ),
        "mantissa_pad_width": pad_to,
        "mantissa_delta_units": None if mantissa_error else mantissa_delta_units,
        "mantissa_digit_deltas": digit_deltas,
    }


def _slot_visible_values(dxf_row: dict[str, Any], *, digits: int) -> dict[int, str]:
    entity_type = str(dxf_row["type"])
    if entity_type == "LINE":
        start = [float(value) for value in dxf_row["normalized_start"]]
        end = [float(value) for value in dxf_row["normalized_end"]]
        return {
            0: value_key(start[0], digits=digits),
            1: value_key(start[1], digits=digits),
            2: value_key(end[0] - start[0], digits=digits),
            3: value_key(end[1] - start[1], digits=digits),
        }
    if entity_type == "ARC":
        start = [float(value) for value in dxf_row["normalized_start_point"]]
        end = [float(value) for value in dxf_row["normalized_end_point"]]
        center = [float(value) for value in dxf_row["normalized_center"]]
        return {
            0: value_key(start[0], digits=digits),
            1: value_key(start[1], digits=digits),
            2: value_key(end[0] - start[0], digits=digits),
            3: value_key(end[1] - start[1], digits=digits),
            4: value_key(center[0] - start[0], digits=digits),
            5: value_key(center[1] - start[1], digits=digits),
            6: value_key(1.0, digits=digits),
            9: value_key(1.0, digits=digits),
        }
    if entity_type == "CIRCLE":
        center = [float(value) for value in dxf_row["normalized_center"]]
        radius = float(dxf_row["radius"])
        return {
            0: value_key(center[0] + radius, digits=digits),
            1: value_key(center[1], digits=digits),
            4: value_key(-radius, digits=digits),
            5: value_key(0.0, digits=digits),
            6: value_key(1.0, digits=digits),
            9: value_key(1.0, digits=digits),
        }
    return {}


def _top_counter(counter: Counter[Any], *, limit: int = 25) -> list[dict[str, Any]]:
    return [{"key": str(key), "count": count} for key, count in counter.most_common(limit)]


def _add_example(bucket: dict[str, list[dict[str, Any]]], key: str, row: dict[str, Any], *, limit: int) -> None:
    examples = bucket.setdefault(key, [])
    if len(examples) >= limit:
        return
    examples.append(
        {
            "part": row["part"],
            "row_index": row["row_index"],
            "dxf_type": row["dxf_type"],
            "slot": row["slot"],
            "role": row["role"],
            "visible_value_key": row["visible_value_key"],
            "oracle_token": row["oracle_token"],
            "generated_token": row["generated_token"],
            "decoded_abs_diff": row["decoded_abs_diff"],
            "mantissa_delta_units": row["mantissa_delta_units"],
            "last_char_delta": row["last_char_delta"],
        }
    )


def summarize_residual_rows(rows: list[dict[str, Any]], *, example_limit: int = 10) -> dict[str, Any]:
    total = len(rows)
    mismatches = [row for row in rows if not row["token_match"]]
    close_mismatches = [row for row in mismatches if row["decoded_bucket"] in {"equal", "close_1e-15", "close_1e-12"}]
    far_mismatches = [row for row in mismatches if row["decoded_bucket"] == "far"]

    role_counts = Counter(f"{row['dxf_type']}:{row['role']}" for row in mismatches)
    bucket_counts = Counter(str(row["decoded_bucket"]) for row in rows)
    mismatch_bucket_counts = Counter(str(row["decoded_bucket"]) for row in mismatches)
    last_char_counts = Counter(str(row["last_char_delta"]) for row in mismatches if row["last_char_delta"] is not None)
    length_delta_counts = Counter(str(row["token_length_delta"]) for row in mismatches)
    mantissa_delta_counts = Counter(
        str(row["mantissa_delta_units"])
        for row in mismatches
        if row["mantissa_delta_units"] is not None
    )

    examples: dict[str, list[dict[str, Any]]] = {}
    for row in mismatches:
        if row["same_prefix_except_last_char"]:
            _add_example(examples, "same_prefix_except_last_char", row, limit=example_limit)
        if row["decoded_bucket"] == "equal":
            _add_example(examples, "alternate_spelling_equal_decoded", row, limit=example_limit)
        elif row["decoded_bucket"] in {"close_1e-15", "close_1e-12"}:
            _add_example(examples, "close_decoded", row, limit=example_limit)
        elif row["decoded_bucket"] == "far":
            _add_example(examples, "far_decoded", row, limit=example_limit)

    by_role: dict[str, dict[str, Any]] = {}
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[f"{row['dxf_type']}:{row['role']}"].append(row)
    for role, role_rows in sorted(grouped.items()):
        role_mismatches = [row for row in role_rows if not row["token_match"]]
        by_role[role] = {
            "slot_count": len(role_rows),
            "exact_token_count": len(role_rows) - len(role_mismatches),
            "mismatch_count": len(role_mismatches),
            "exact_token_rate": (len(role_rows) - len(role_mismatches)) / len(role_rows) if role_rows else 0.0,
            "decoded_bucket_counts": dict(sorted(Counter(str(row["decoded_bucket"]) for row in role_rows).items())),
            "top_mantissa_delta_units": _top_counter(
                Counter(
                    str(row["mantissa_delta_units"])
                    for row in role_mismatches
                    if row["mantissa_delta_units"] is not None
                ),
                limit=10,
            ),
            "top_last_char_delta": _top_counter(
                Counter(str(row["last_char_delta"]) for row in role_mismatches if row["last_char_delta"] is not None),
                limit=10,
            ),
        }

    return {
        "slot_count": total,
        "exact_token_count": total - len(mismatches),
        "mismatch_count": len(mismatches),
        "exact_token_rate": (total - len(mismatches)) / total if total else 0.0,
        "decoded_close_1e_12_count": sum(
            1 for row in rows if row["decoded_bucket"] in {"equal", "close_1e-15", "close_1e-12"}
        ),
        "decoded_bucket_counts": dict(sorted(bucket_counts.items())),
        "mismatch_decoded_bucket_counts": dict(sorted(mismatch_bucket_counts.items())),
        "close_mismatch_count": len(close_mismatches),
        "far_mismatch_count": len(far_mismatches),
        "same_prefix_except_last_char_count": sum(1 for row in mismatches if row["same_prefix_except_last_char"]),
        "token_length_delta_counts": dict(sorted(length_delta_counts.items())),
        "top_roles_by_mismatch": _top_counter(role_counts),
        "top_last_char_delta": _top_counter(last_char_counts),
        "top_mantissa_delta_units": _top_counter(mantissa_delta_counts),
        "examples": examples,
        "by_role": by_role,
    }


def analyze_token_residuals(
    *,
    dxf_folder: Path,
    oracle_sym_folder: Path,
    generated_sym_folder: Path,
    parts: list[str] | None = None,
    exclude_parts: list[str] | None = None,
    value_digits: int = 6,
) -> dict[str, Any]:
    dxf_by_part = {path.stem.casefold(): path for path in Path(dxf_folder).glob("*.dxf")}
    oracle_by_part = {path.stem.casefold(): path for path in Path(oracle_sym_folder).glob("*.sym")}
    generated_by_part = {path.stem.casefold(): path for path in Path(generated_sym_folder).glob("*.sym")}
    requested = [part.casefold() for part in parts] if parts else sorted(set(dxf_by_part) & set(oracle_by_part) & set(generated_by_part))
    excluded = {part.casefold() for part in (exclude_parts or [])}
    requested = [part for part in requested if part not in excluded]

    rows: list[dict[str, Any]] = []
    part_summaries: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    for key in requested:
        dxf_path = dxf_by_part.get(key)
        oracle_path = oracle_by_part.get(key)
        generated_path = generated_by_part.get(key)
        if dxf_path is None or oracle_path is None or generated_path is None:
            skipped.append({"part": key, "reason": "missing_dxf_or_sym"})
            continue
        dxf_rows, _bounds = read_dxf_entities(dxf_path)
        oracle_rows = read_ddc_records(oracle_path)
        generated_rows = read_ddc_records(generated_path)
        if len(dxf_rows) != len(oracle_rows) or len(oracle_rows) != len(generated_rows):
            skipped.append({"part": dxf_path.stem, "reason": "count_mismatch"})
            continue

        start_index = len(rows)
        for row_index, (dxf_row, oracle_row, generated_row) in enumerate(
            zip(dxf_rows, oracle_rows, generated_rows),
            start=1,
        ):
            entity_type = str(dxf_row["type"])
            visible_values = _slot_visible_values(dxf_row, digits=value_digits)
            oracle_tokens = list(oracle_row.get("tokens") or [])
            generated_tokens = list(generated_row.get("tokens") or [])
            for slot in range(max(len(oracle_tokens), len(generated_tokens))):
                rows.append(
                    token_residual_row(
                        part=dxf_path.stem,
                        row_index=row_index,
                        dxf_type=entity_type,
                        slot=slot,
                        oracle_token=_token(oracle_tokens, slot),
                        generated_token=_token(generated_tokens, slot),
                        visible_value_key=visible_values.get(slot, ""),
                    )
                )
        part_rows = rows[start_index:]
        part_summaries.append(
            {
                "part": dxf_path.stem,
                "dxf_path": str(dxf_path),
                "oracle_sym_path": str(oracle_path),
                "generated_sym_path": str(generated_path),
                "summary": summarize_residual_rows(part_rows, example_limit=3),
            }
        )

    return {
        "schema_version": 1,
        "dxf_folder": str(dxf_folder),
        "oracle_sym_folder": str(oracle_sym_folder),
        "generated_sym_folder": str(generated_sym_folder),
        "value_digits": value_digits,
        "exclude_parts": sorted(excluded),
        "part_count": len(part_summaries),
        "skipped": skipped,
        "summary": summarize_residual_rows(rows),
        "parts": part_summaries,
        "rows": rows,
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    assert_w_drive_write_allowed(path, operation="write token residual analysis JSON")
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.tmp")
    temp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True) + "\n", encoding="utf-8")
    temp_path.replace(path)


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    assert_w_drive_write_allowed(path, operation="write token residual analysis CSV")
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "part",
        "row_index",
        "dxf_type",
        "slot",
        "role",
        "visible_value_key",
        "token_match",
        "decoded_bucket",
        "decoded_abs_diff",
        "oracle_token",
        "generated_token",
        "token_length_delta",
        "same_prefix_except_last_char",
        "last_char_delta",
        "mantissa_delta_units",
        "mantissa_digit_deltas",
        "oracle_fraction",
        "generated_fraction",
    ]
    temp_path = path.with_name(f"{path.name}.tmp")
    with temp_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            out = {field: row.get(field, "") for field in fieldnames}
            out["mantissa_digit_deltas"] = " ".join(str(value) for value in row.get("mantissa_digit_deltas", []))
            writer.writerow(out)
    temp_path.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Analyze close-but-not-exact RADAN DDC compact-token residuals.",
    )
    parser.add_argument("--dxf-folder", type=Path, required=True)
    parser.add_argument("--oracle-sym-folder", type=Path, required=True)
    parser.add_argument("--generated-sym-folder", type=Path, required=True)
    parser.add_argument("--out-json", type=Path)
    parser.add_argument("--out-csv", type=Path)
    parser.add_argument("--value-digits", type=int, default=6)
    parser.add_argument("--part", action="append", help="Limit analysis to one or more part stems.")
    parser.add_argument("--exclude-part", action="append", default=[], help="Exclude one or more part stems.")
    args = parser.parse_args()

    payload = analyze_token_residuals(
        dxf_folder=args.dxf_folder,
        oracle_sym_folder=args.oracle_sym_folder,
        generated_sym_folder=args.generated_sym_folder,
        parts=args.part,
        exclude_parts=args.exclude_part,
        value_digits=int(args.value_digits),
    )
    if args.out_json:
        write_json(args.out_json, payload)
    if args.out_csv:
        write_csv(args.out_csv, payload["rows"])
    printable = {
        "part_count": payload["part_count"],
        "skipped_count": len(payload["skipped"]),
        "summary": {
            key: value
            for key, value in payload["summary"].items()
            if key not in {"by_role", "examples"}
        },
    }
    print(json.dumps(printable, indent=2, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
