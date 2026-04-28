from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from ddc_corpus import read_ddc_records, read_dxf_entities
from ddc_number_codec import decode_ddc_number
from path_safety import assert_w_drive_write_allowed


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = int(round((len(ordered) - 1) * percentile))
    return ordered[max(0, min(len(ordered) - 1, index))]


def _csv_dxf_paths(csv_path: Path) -> list[Path]:
    paths: list[Path] = []
    with csv_path.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.reader(handle):
            if not row or not any(cell.strip() for cell in row):
                continue
            paths.append(Path(row[0].strip()))
    return paths


def _token(tokens: list[str], index: int) -> str:
    if index >= len(tokens):
        return ""
    return tokens[index]


def _decoded_diff(oracle_token: str, compare_token: str) -> tuple[float, float, float]:
    oracle_value = decode_ddc_number(oracle_token)
    compare_value = decode_ddc_number(compare_token)
    return oracle_value, compare_value, abs(oracle_value - compare_value)


def _add_example(bucket: dict[str, Any], example: dict[str, Any], *, limit: int) -> None:
    examples = bucket.setdefault("top_abs_diff_examples", [])
    examples.append(example)
    examples.sort(key=lambda row: row["abs_diff"], reverse=True)
    del examples[limit:]


def compare_part(dxf_path: Path, oracle_sym_path: Path, compare_sym_path: Path, *, top: int = 10) -> dict[str, Any]:
    dxf_rows, bounds = read_dxf_entities(dxf_path)
    oracle_rows = read_ddc_records(oracle_sym_path)
    compare_rows = read_ddc_records(compare_sym_path)

    groups: dict[tuple[str, str, int], dict[str, Any]] = defaultdict(
        lambda: {
            "count": 0,
            "token_match_count": 0,
            "nonzero_abs_diff_count": 0,
            "abs_diffs": [],
            "max_abs_diff": 0.0,
        }
    )
    changed_geometry_records = 0
    changed_token_records = 0
    total_slots = 0
    token_match_slots = 0
    decoded_nonzero_diff_slots = 0
    max_abs_diff = 0.0
    part_examples: list[dict[str, Any]] = []

    for index, (dxf_row, oracle_row, compare_row) in enumerate(zip(dxf_rows, oracle_rows, compare_rows), start=1):
        if oracle_row.get("geometry_data") != compare_row.get("geometry_data"):
            changed_geometry_records += 1
        if oracle_row.get("tokens") != compare_row.get("tokens"):
            changed_token_records += 1

        oracle_tokens = list(oracle_row.get("tokens") or [])
        compare_tokens = list(compare_row.get("tokens") or [])
        slot_count = max(len(oracle_tokens), len(compare_tokens))
        for slot in range(slot_count):
            oracle_token = _token(oracle_tokens, slot)
            compare_token = _token(compare_tokens, slot)
            oracle_value, compare_value, abs_diff = _decoded_diff(oracle_token, compare_token)
            key = (str(oracle_row.get("record")), str(dxf_row.get("type")), slot)
            bucket = groups[key]
            bucket["count"] += 1
            bucket["abs_diffs"].append(abs_diff)
            bucket["max_abs_diff"] = max(float(bucket["max_abs_diff"]), abs_diff)
            total_slots += 1
            max_abs_diff = max(max_abs_diff, abs_diff)
            if oracle_token == compare_token:
                bucket["token_match_count"] += 1
                token_match_slots += 1
            if abs_diff:
                bucket["nonzero_abs_diff_count"] += 1
                decoded_nonzero_diff_slots += 1
            if abs_diff:
                example = {
                    "part": dxf_path.stem,
                    "index": index,
                    "record": oracle_row.get("record"),
                    "identifier": oracle_row.get("identifier"),
                    "dxf_type": dxf_row.get("type"),
                    "dxf_layer": dxf_row.get("layer"),
                    "slot": slot,
                    "oracle_token": oracle_token,
                    "compare_token": compare_token,
                    "oracle_value": oracle_value,
                    "compare_value": compare_value,
                    "abs_diff": abs_diff,
                }
                _add_example(bucket, example, limit=top)
                part_examples.append(example)
                part_examples.sort(key=lambda row: row["abs_diff"], reverse=True)
                del part_examples[top:]

    group_rows: list[dict[str, Any]] = []
    for (record, dxf_type, slot), bucket in sorted(groups.items()):
        diffs = list(bucket["abs_diffs"])
        group_rows.append(
            {
                "record": record,
                "dxf_type": dxf_type,
                "slot": slot,
                "count": bucket["count"],
                "token_match_count": bucket["token_match_count"],
                "token_match_ratio": bucket["token_match_count"] / bucket["count"] if bucket["count"] else 0.0,
                "nonzero_abs_diff_count": bucket["nonzero_abs_diff_count"],
                "max_abs_diff": bucket["max_abs_diff"],
                "p95_abs_diff": _percentile(diffs, 0.95),
                "p99_abs_diff": _percentile(diffs, 0.99),
                "top_abs_diff_examples": bucket.get("top_abs_diff_examples", []),
                "_abs_diffs": diffs,
            }
        )

    return {
        "part": dxf_path.stem,
        "dxf_path": str(dxf_path),
        "oracle_sym_path": str(oracle_sym_path),
        "compare_sym_path": str(compare_sym_path),
        "bounds": bounds.as_dict(),
        "dxf_count": len(dxf_rows),
        "oracle_ddc_count": len(oracle_rows),
        "compare_ddc_count": len(compare_rows),
        "changed_geometry_records": changed_geometry_records,
        "changed_token_records": changed_token_records,
        "total_slots": total_slots,
        "token_match_slots": token_match_slots,
        "decoded_nonzero_diff_slots": decoded_nonzero_diff_slots,
        "max_abs_diff": max_abs_diff,
        "top_abs_diff_examples": part_examples,
        "groups": group_rows,
    }


def compare_corpus(csv_path: Path, oracle_sym_folder: Path, compare_sym_folder: Path, *, top: int = 10) -> dict[str, Any]:
    part_rows = [
        compare_part(
            dxf_path,
            oracle_sym_folder / f"{dxf_path.stem}.sym",
            compare_sym_folder / f"{dxf_path.stem}.sym",
            top=top,
        )
        for dxf_path in _csv_dxf_paths(csv_path)
    ]

    aggregate: dict[tuple[str, str, int], dict[str, Any]] = defaultdict(
        lambda: {
            "count": 0,
            "token_match_count": 0,
            "nonzero_abs_diff_count": 0,
            "abs_diffs": [],
            "max_abs_diff": 0.0,
            "top_abs_diff_examples": [],
        }
    )
    top_examples: list[dict[str, Any]] = []
    for part in part_rows:
        for example in part["top_abs_diff_examples"]:
            top_examples.append(example)
            top_examples.sort(key=lambda row: row["abs_diff"], reverse=True)
            del top_examples[top:]
        for group in part["groups"]:
            key = (group["record"], group["dxf_type"], int(group["slot"]))
            bucket = aggregate[key]
            bucket["count"] += group["count"]
            bucket["token_match_count"] += group["token_match_count"]
            bucket["nonzero_abs_diff_count"] += group["nonzero_abs_diff_count"]
            bucket["max_abs_diff"] = max(float(bucket["max_abs_diff"]), float(group["max_abs_diff"]))
            bucket["abs_diffs"].extend(float(value) for value in group.get("_abs_diffs", []))
            for example in group.get("top_abs_diff_examples", []):
                _add_example(bucket, example, limit=top)

    for part in part_rows:
        for group in part["groups"]:
            group.pop("_abs_diffs", None)

    aggregate_rows = []
    for (record, dxf_type, slot), bucket in sorted(aggregate.items()):
        diffs = list(bucket["abs_diffs"])
        aggregate_rows.append(
            {
                "record": record,
                "dxf_type": dxf_type,
                "slot": slot,
                "count": bucket["count"],
                "token_match_count": bucket["token_match_count"],
                "token_match_ratio": bucket["token_match_count"] / bucket["count"] if bucket["count"] else 0.0,
                "nonzero_abs_diff_count": bucket["nonzero_abs_diff_count"],
                "max_abs_diff": bucket["max_abs_diff"],
                "p95_abs_diff": _percentile(diffs, 0.95),
                "p99_abs_diff": _percentile(diffs, 0.99),
                "top_abs_diff_examples": bucket["top_abs_diff_examples"],
            }
        )

    total_slots = sum(int(part["total_slots"]) for part in part_rows)
    token_match_slots = sum(int(part["token_match_slots"]) for part in part_rows)
    return {
        "csv_path": str(csv_path),
        "oracle_sym_folder": str(oracle_sym_folder),
        "compare_sym_folder": str(compare_sym_folder),
        "part_count": len(part_rows),
        "total_dxf_records": sum(int(part["dxf_count"]) for part in part_rows),
        "changed_geometry_records": sum(int(part["changed_geometry_records"]) for part in part_rows),
        "changed_token_records": sum(int(part["changed_token_records"]) for part in part_rows),
        "total_slots": total_slots,
        "token_match_slots": token_match_slots,
        "token_match_ratio": token_match_slots / total_slots if total_slots else 0.0,
        "decoded_nonzero_diff_slots": sum(int(part["decoded_nonzero_diff_slots"]) for part in part_rows),
        "max_abs_diff": max((float(part["max_abs_diff"]) for part in part_rows), default=0.0),
        "top_abs_diff_examples": top_examples,
        "aggregate_groups": aggregate_rows,
        "parts": part_rows,
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    assert_w_drive_write_allowed(path, operation="write DDC geometry comparison")
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.tmp")
    temp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True) + "\n", encoding="utf-8")
    temp_path.replace(path)


def _print_summary(payload: dict[str, Any]) -> None:
    interesting_groups = [
        row
        for row in payload["aggregate_groups"]
        if row["record"] == "H" and row["dxf_type"] == "ARC" and row["slot"] in {0, 1, 2, 3, 4, 5}
    ]
    summary = {
        "part_count": payload["part_count"],
        "total_dxf_records": payload["total_dxf_records"],
        "changed_geometry_records": payload["changed_geometry_records"],
        "token_match_ratio": payload["token_match_ratio"],
        "decoded_nonzero_diff_slots": payload["decoded_nonzero_diff_slots"],
        "max_abs_diff": payload["max_abs_diff"],
        "arc_h_groups": [
            {
                "slot": row["slot"],
                "count": row["count"],
                "token_match_ratio": row["token_match_ratio"],
                "max_abs_diff": row["max_abs_diff"],
                "p95_abs_diff": row["p95_abs_diff"],
                "p99_abs_diff": row["p99_abs_diff"],
            }
            for row in interesting_groups
        ],
        "top_abs_diff_examples": payload["top_abs_diff_examples"],
    }
    print(json.dumps(summary, indent=2, ensure_ascii=True, sort_keys=True))


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare decoded DDC geometry slots between two SYM folders.")
    parser.add_argument("--csv", type=Path, required=True)
    parser.add_argument("--oracle-sym-folder", type=Path, required=True)
    parser.add_argument("--compare-sym-folder", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--top", type=int, default=10)
    args = parser.parse_args()

    payload = compare_corpus(
        args.csv,
        args.oracle_sym_folder,
        args.compare_sym_folder,
        top=max(1, int(args.top)),
    )
    if args.out:
        write_json(args.out, payload)
    _print_summary(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
