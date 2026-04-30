from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from ddc_corpus import read_ddc_records
from ddc_number_codec import decode_ddc_number_fraction
from path_safety import assert_w_drive_write_allowed


def _token(row: dict[str, Any], slot: int) -> str:
    tokens = list(row.get("tokens") or [])
    return str(tokens[slot]) if slot < len(tokens) else ""


def _decode(token: str) -> dict[str, Any]:
    try:
        value = decode_ddc_number_fraction(token)
    except Exception as exc:
        return {
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "float": None,
            "fraction": None,
        }
    return {
        "ok": True,
        "error": None,
        "float": float(value),
        "fraction": f"{value.numerator}/{value.denominator}",
    }


def _decoded_abs_diff(left_token: str, right_token: str) -> float | None:
    try:
        return abs(float(decode_ddc_number_fraction(left_token) - decode_ddc_number_fraction(right_token)))
    except Exception:
        return None


def _slot_count(left: dict[str, Any], right: dict[str, Any]) -> int:
    return max(len(list(left.get("tokens") or [])), len(list(right.get("tokens") or [])))


def _compare_rows(
    left_rows: list[dict[str, Any]],
    right_rows: list[dict[str, Any]],
    *,
    example_limit: int,
) -> dict[str, Any]:
    total_slots = 0
    exact_slots = 0
    decoded_close_slots = 0
    changed_rows: set[int] = set()
    changed_slots = 0
    max_decoded_abs_diff = 0.0
    max_decoded_abs_diff_slot: dict[str, Any] | None = None
    by_record_slot: Counter[str] = Counter()
    examples: list[dict[str, Any]] = []
    decoded_nonclose_examples: list[dict[str, Any]] = []
    decoded_diff_examples: list[dict[str, Any]] = []
    row_total = max(len(left_rows), len(right_rows))

    for row_index in range(row_total):
        left_row = left_rows[row_index] if row_index < len(left_rows) else {"record": None, "tokens": []}
        right_row = right_rows[row_index] if row_index < len(right_rows) else {"record": None, "tokens": []}
        slot_total = _slot_count(left_row, right_row)
        total_slots += slot_total
        record = str(left_row.get("record") or right_row.get("record") or "")
        for slot in range(slot_total):
            left_token = _token(left_row, slot)
            right_token = _token(right_row, slot)
            if left_token == right_token:
                exact_slots += 1
                decoded_close_slots += 1
                continue
            changed_slots += 1
            changed_rows.add(row_index + 1)
            by_record_slot[f"{record}{slot}"] += 1
            decoded_abs_diff = _decoded_abs_diff(left_token, right_token)
            if decoded_abs_diff is not None and decoded_abs_diff <= 1e-12:
                decoded_close_slots += 1
            elif len(decoded_nonclose_examples) < example_limit:
                decoded_nonclose_examples.append(
                    {
                        "row_index": row_index + 1,
                        "record": record,
                        "slot": slot,
                        "left_token": left_token,
                        "right_token": right_token,
                        "decoded_abs_diff": decoded_abs_diff,
                    }
                )
            if decoded_abs_diff is not None and decoded_abs_diff > max_decoded_abs_diff:
                max_decoded_abs_diff = decoded_abs_diff
                max_decoded_abs_diff_slot = {
                    "row_index": row_index + 1,
                    "record": record,
                    "slot": slot,
                    "left_token": left_token,
                    "right_token": right_token,
                    "decoded_abs_diff": decoded_abs_diff,
                }
            if decoded_abs_diff is not None and decoded_abs_diff > 0:
                decoded_diff_examples.append(
                    {
                        "row_index": row_index + 1,
                        "record": record,
                        "slot": slot,
                        "left_token": left_token,
                        "right_token": right_token,
                        "decoded_abs_diff": decoded_abs_diff,
                    }
                )
            if len(examples) < example_limit:
                examples.append(
                    {
                        "row_index": row_index + 1,
                        "record": record,
                        "slot": slot,
                        "left_token": left_token,
                        "right_token": right_token,
                        "left_decoded": _decode(left_token),
                        "right_decoded": _decode(right_token),
                        "decoded_abs_diff": decoded_abs_diff,
                    }
                )

    return {
        "left_row_count": len(left_rows),
        "right_row_count": len(right_rows),
        "total_slots": total_slots,
        "exact_slots": exact_slots,
        "exact_slot_ratio": exact_slots / total_slots if total_slots else 0.0,
        "decoded_close_1e_12_slots": decoded_close_slots,
        "decoded_close_1e_12_ratio": decoded_close_slots / total_slots if total_slots else 0.0,
        "changed_slot_count": changed_slots,
        "changed_row_count": len(changed_rows),
        "changed_rows": sorted(changed_rows),
        "changed_slots_by_record_slot": [
            {"record_slot": key, "count": count} for key, count in sorted(by_record_slot.items())
        ],
        "max_decoded_abs_diff": max_decoded_abs_diff,
        "max_decoded_abs_diff_slot": max_decoded_abs_diff_slot,
        "decoded_nonclose_examples": decoded_nonclose_examples,
        "top_decoded_abs_diff_slots": sorted(
            decoded_diff_examples,
            key=lambda row: float(row["decoded_abs_diff"]),
            reverse=True,
        )[:example_limit],
        "examples": examples,
    }


def _variant_summary(name: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    record_counts = Counter(str(row.get("record", "")) for row in rows)
    token_counts = Counter()
    for row in rows:
        record = str(row.get("record", ""))
        for slot, token in enumerate(list(row.get("tokens") or [])):
            if token:
                token_counts[f"{record}{slot}"] += 1
    return {
        "name": name,
        "row_count": len(rows),
        "record_counts": dict(sorted(record_counts.items())),
        "non_empty_token_counts_by_record_slot": [
            {"record_slot": key, "count": count} for key, count in sorted(token_counts.items())
        ],
    }


def _token_match_class(tokens: dict[str, str], *, pass_names: set[str], fail_names: set[str]) -> str:
    pass_values = {tokens[name] for name in pass_names if name in tokens}
    fail_values = {tokens[name] for name in fail_names if name in tokens}
    if len(pass_values) == 1 and len(fail_values) == 1:
        pass_value = next(iter(pass_values))
        fail_value = next(iter(fail_values))
        return "pass_fail_same" if pass_value == fail_value else "pass_fail_split"
    if len(pass_values) == 1:
        return "pass_conserved"
    if len(fail_values) == 1:
        return "fail_conserved"
    return "mixed"


def _classify_slots(
    variants: dict[str, list[dict[str, Any]]],
    *,
    pass_names: set[str],
    fail_names: set[str],
    example_limit: int,
) -> dict[str, Any]:
    row_total = max((len(rows) for rows in variants.values()), default=0)
    class_counts: Counter[str] = Counter()
    record_slot_counts: Counter[str] = Counter()
    examples: list[dict[str, Any]] = []
    for row_index in range(row_total):
        slot_total = 0
        record = ""
        for rows in variants.values():
            if row_index < len(rows):
                row = rows[row_index]
                slot_total = max(slot_total, len(list(row.get("tokens") or [])))
                if not record:
                    record = str(row.get("record", ""))
        for slot in range(slot_total):
            tokens = {
                name: _token(rows[row_index], slot)
                for name, rows in variants.items()
                if row_index < len(rows)
            }
            if len(set(tokens.values())) <= 1:
                continue
            match_class = _token_match_class(tokens, pass_names=pass_names, fail_names=fail_names)
            class_counts[match_class] += 1
            record_slot_counts[f"{record}{slot}:{match_class}"] += 1
            if len(examples) < example_limit:
                examples.append(
                    {
                        "row_index": row_index + 1,
                        "record": record,
                        "slot": slot,
                        "class": match_class,
                        "tokens": tokens,
                    }
                )
    return {
        "pass_variants": sorted(pass_names),
        "fail_variants": sorted(fail_names),
        "class_counts": dict(sorted(class_counts.items())),
        "record_slot_class_counts": [
            {"record_slot_class": key, "count": count} for key, count in sorted(record_slot_counts.items())
        ],
        "examples": examples,
    }


def _parse_variant(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("variants must be NAME=PATH")
    name, path_text = value.split("=", 1)
    name = name.strip()
    if not name:
        raise argparse.ArgumentTypeError("variant NAME must not be empty")
    return name, Path(path_text)


def analyze_variants(
    variants: list[tuple[str, Path]],
    *,
    pass_names: set[str],
    fail_names: set[str],
    example_limit: int = 25,
) -> dict[str, Any]:
    loaded = {name: read_ddc_records(path) for name, path in variants}
    payload: dict[str, Any] = {
        "schema_version": 1,
        "variants": [
            {
                **_variant_summary(name, loaded[name]),
                "path": str(path),
            }
            for name, path in variants
        ],
        "pairwise": {},
        "slot_classification": _classify_slots(
            loaded,
            pass_names=pass_names,
            fail_names=fail_names,
            example_limit=example_limit,
        ),
    }
    for left_name, _left_path in variants:
        for right_name, _right_path in variants:
            if left_name >= right_name:
                continue
            key = f"{left_name}__vs__{right_name}"
            payload["pairwise"][key] = _compare_rows(
                loaded[left_name],
                loaded[right_name],
                example_limit=example_limit,
            )
    return payload


def write_json(path: Path, payload: dict[str, Any]) -> None:
    assert_w_drive_write_allowed(path, operation="write SYM variant token analysis")
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.tmp")
    temp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True) + "\n", encoding="utf-8")
    temp_path.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare geometry-token rows across lab SYM variants.")
    parser.add_argument("--variant", action="append", required=True, type=_parse_variant, help="Variant as NAME=PATH.")
    parser.add_argument("--pass-variant", action="append", default=[], help="Variant name known to pass a gate.")
    parser.add_argument("--fail-variant", action="append", default=[], help="Variant name known to fail a gate.")
    parser.add_argument("--out-json", type=Path, required=True)
    parser.add_argument("--example-limit", type=int, default=25)
    args = parser.parse_args()

    payload = analyze_variants(
        args.variant,
        pass_names=set(args.pass_variant),
        fail_names=set(args.fail_variant),
        example_limit=int(args.example_limit),
    )
    write_json(args.out_json, payload)
    print(
        json.dumps(
            {
                "out_json": str(args.out_json),
                "variant_count": len(args.variant),
                "slot_class_counts": payload["slot_classification"]["class_counts"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
