from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from fractions import Fraction
from pathlib import Path
from typing import Any, Callable

from ddc_corpus import read_ddc_records, read_dxf_entities
from ddc_number_codec import _prefix_from_exponent, encode_ddc_number
from path_safety import assert_w_drive_write_allowed
from write_native_sym_prototype import (
    _rows_with_rounded_source_coordinates,
    _rows_with_topology_snapped_endpoints,
    encode_geometry_data,
)


def _csv_dxf_paths(csv_path: Path) -> list[Path]:
    paths: list[Path] = []
    with csv_path.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.reader(handle):
            if not row or not any(cell.strip() for cell in row):
                continue
            paths.append(Path(row[0].strip()))
    return paths


def _find_oracle_sym(
    part_name: str,
    *,
    oracle_sym_folder: Path | None,
    backup_root: Path | None,
) -> Path:
    if oracle_sym_folder is not None:
        candidate = oracle_sym_folder / f"{part_name}.sym"
        if candidate.exists():
            return candidate
    if backup_root is not None:
        matches = sorted(
            backup_root.glob(f"**/{part_name}.sym"),
            key=lambda path: (path.stat().st_mtime_ns, str(path)),
        )
        if matches:
            return matches[-1]
    raise FileNotFoundError(f"Could not find oracle symbol for {part_name}.")


def _encode_float_fixed8(value: float) -> str:
    value = float(value)
    if value == 0.0:
        return ""

    sign = -1 if value < 0 else 1
    absolute = abs(value)
    exponent = math.floor(math.log(absolute, 2))
    if absolute >= 2.0 ** (exponent + 1):
        exponent += 1
    prefix = _prefix_from_exponent(exponent)

    remainder = (absolute / (2.0**exponent) - 1.0) * 16.0
    first_digit = int(math.floor(remainder))
    remainder -= first_digit
    first_char = chr((80 if sign < 0 else 48) + first_digit)
    if remainder == 0.0:
        return prefix + first_char

    digits: list[str] = []
    for _ in range(8):
        remainder *= 64.0
        digit = int(math.floor(remainder))
        digit = max(0, min(63, digit))
        digits.append(chr(48 + digit))
        remainder -= digit
    return prefix + first_char + "".join(digits)


def _line_values(row: dict[str, Any]) -> list[float]:
    start_x, start_y = row["normalized_start"]
    end_x, end_y = row["normalized_end"]
    return [float(start_x), float(start_y), float(end_x) - float(start_x), float(end_y) - float(start_y)]


def _arc_values(row: dict[str, Any]) -> list[float]:
    start_x, start_y = row["normalized_start_point"]
    end_x, end_y = row["normalized_end_point"]
    center_x, center_y = row["normalized_center"]
    return [
        float(start_x),
        float(start_y),
        float(end_x) - float(start_x),
        float(end_y) - float(start_y),
        float(center_x) - float(start_x),
        float(center_y) - float(start_y),
        1.0,
        0.0,
        0.0,
        1.0,
    ]


def _circle_values(row: dict[str, Any]) -> list[float]:
    center_x, center_y = row["normalized_center"]
    radius = float(row["radius"])
    return [
        float(center_x) + radius,
        float(center_y),
        0.0,
        0.0,
        -radius,
        0.0,
        1.0,
        0.0,
        0.0,
        1.0,
    ]


def _fixed8_geometry_data(row: dict[str, Any], *, token_count: int) -> str:
    entity_type = str(row["type"])
    if entity_type == "LINE":
        values = _line_values(row)
    elif entity_type == "ARC":
        values = _arc_values(row)
    elif entity_type == "CIRCLE":
        values = _circle_values(row)
    else:
        values = []
    tokens = [_encode_float_fixed8(value) for value in values]
    if len(tokens) < token_count:
        tokens.extend([""] * (token_count - len(tokens)))
    return ".".join(tokens[:token_count])


def _current_geometry_data(row: dict[str, Any], *, token_count: int) -> str:
    return encode_geometry_data(row, token_count=token_count)


def _current_float_geometry_data(row: dict[str, Any], *, token_count: int) -> str:
    entity_type = str(row["type"])
    if entity_type == "LINE":
        values = _line_values(row)
    elif entity_type == "ARC":
        values = _arc_values(row)
    elif entity_type == "CIRCLE":
        values = _circle_values(row)
    else:
        values = []
    tokens = [encode_ddc_number(value) for value in values]
    if len(tokens) < token_count:
        tokens.extend([""] * (token_count - len(tokens)))
    return ".".join(tokens[:token_count])


def _is_dyadic_decimal_6(value: float) -> bool:
    denominator = Fraction(str(round(float(value), 6))).denominator
    while denominator > 1 and denominator % 2 == 0:
        denominator //= 2
    return denominator == 1


def _pad_non_dyadic_full8(token: str, value: float) -> str:
    if not token or len(token) >= 11 or _is_dyadic_decimal_6(value):
        return token
    return token + ("0" * (11 - len(token)))


def _current_float_full8_non_dyadic_geometry_data(row: dict[str, Any], *, token_count: int) -> str:
    entity_type = str(row["type"])
    if entity_type == "LINE":
        values = _line_values(row)
    elif entity_type == "ARC":
        values = _arc_values(row)
    elif entity_type == "CIRCLE":
        values = _circle_values(row)
    else:
        values = []
    tokens = [_pad_non_dyadic_full8(encode_ddc_number(value), value) for value in values]
    if len(tokens) < token_count:
        tokens.extend([""] * (token_count - len(tokens)))
    return ".".join(tokens[:token_count])


CandidateEncoder = Callable[[dict[str, Any], int], str]


def _compare_candidate(
    *,
    name: str,
    dxf_rows: list[dict[str, Any]],
    oracle_rows: list[dict[str, Any]],
    encoder: CandidateEncoder,
    top: int,
) -> dict[str, Any]:
    token_match_slots = 0
    total_slots = 0
    geometry_match_records = 0
    changed_records = 0
    last_char_delta_counts: Counter[int] = Counter()
    mismatch_shape_counts: Counter[str] = Counter()
    examples: list[dict[str, Any]] = []
    groups: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)

    for index, (dxf_row, oracle_row) in enumerate(zip(dxf_rows, oracle_rows), start=1):
        oracle_tokens = list(oracle_row.get("tokens") or [])
        token_count = len(oracle_tokens)
        generated = encoder(dxf_row, token_count).split(".")
        if generated == oracle_tokens:
            geometry_match_records += 1
        else:
            changed_records += 1

        group_key = (str(oracle_row.get("record")), str(dxf_row.get("type")))
        for slot in range(max(len(generated), len(oracle_tokens))):
            generated_token = generated[slot] if slot < len(generated) else ""
            oracle_token = oracle_tokens[slot] if slot < len(oracle_tokens) else ""
            total_slots += 1
            if generated_token == oracle_token:
                token_match_slots += 1
                groups[group_key]["match"] += 1
                continue

            groups[group_key]["mismatch"] += 1
            if len(generated_token) == len(oracle_token) and generated_token[:-1] == oracle_token[:-1]:
                delta = ord(oracle_token[-1]) - ord(generated_token[-1])
                last_char_delta_counts[delta] += 1
                mismatch_shape = "last_char_delta"
            else:
                mismatch_shape = "other"
            mismatch_shape_counts[mismatch_shape] += 1
            if len(examples) < top:
                examples.append(
                    {
                        "index": index,
                        "slot": slot,
                        "record": oracle_row.get("record"),
                        "dxf_type": dxf_row.get("type"),
                        "oracle_token": oracle_token,
                        "generated_token": generated_token,
                        "shape": mismatch_shape,
                    }
                )

    group_rows = [
        {
            "record": key[0],
            "dxf_type": key[1],
            "match": counts["match"],
            "mismatch": counts["mismatch"],
        }
        for key, counts in sorted(groups.items())
    ]
    return {
        "name": name,
        "geometry_match_records": geometry_match_records,
        "changed_records": changed_records,
        "token_match_slots": token_match_slots,
        "total_slots": total_slots,
        "token_match_ratio": token_match_slots / total_slots if total_slots else 0.0,
        "mismatch_shape_counts": dict(mismatch_shape_counts),
        "last_char_delta_counts": {str(key): value for key, value in sorted(last_char_delta_counts.items())},
        "groups": group_rows,
        "examples": examples,
    }


def analyze_part(
    dxf_path: Path,
    oracle_sym_path: Path,
    *,
    top: int = 10,
) -> dict[str, Any]:
    raw_rows, bounds = read_dxf_entities(dxf_path)
    oracle_rows = read_ddc_records(oracle_sym_path)
    source_round6_rows = _rows_with_rounded_source_coordinates(raw_rows, bounds, digits=6)
    topology_round6_rows = _rows_with_topology_snapped_endpoints(raw_rows, bounds, digits=6)

    candidates = [
        (
            "raw_current",
            raw_rows,
            lambda row, token_count: _current_geometry_data(row, token_count=token_count),
        ),
        (
            "source_round6_current",
            source_round6_rows,
            lambda row, token_count: _current_geometry_data(row, token_count=token_count),
        ),
        (
            "source_round6_float_fixed8",
            source_round6_rows,
            lambda row, token_count: _fixed8_geometry_data(row, token_count=token_count),
        ),
        (
            "topology_round6_float_fixed8",
            topology_round6_rows,
            lambda row, token_count: _fixed8_geometry_data(row, token_count=token_count),
        ),
        (
            "source_round6_float_current",
            source_round6_rows,
            lambda row, token_count: _current_float_geometry_data(row, token_count=token_count),
        ),
        (
            "source_round6_float_full8_non_dyadic",
            source_round6_rows,
            lambda row, token_count: _current_float_full8_non_dyadic_geometry_data(row, token_count=token_count),
        ),
    ]
    return {
        "part": dxf_path.stem,
        "dxf_path": str(dxf_path),
        "oracle_sym_path": str(oracle_sym_path),
        "bounds": bounds.as_dict(),
        "dxf_count": len(raw_rows),
        "oracle_ddc_count": len(oracle_rows),
        "candidates": [
            _compare_candidate(
                name=name,
                dxf_rows=rows,
                oracle_rows=oracle_rows,
                encoder=encoder,
                top=top,
            )
            for name, rows, encoder in candidates
        ],
    }


def analyze_many(
    dxf_paths: list[Path],
    *,
    oracle_sym_folder: Path | None,
    backup_root: Path | None,
    top: int = 10,
) -> dict[str, Any]:
    parts = [
        analyze_part(
            dxf_path,
            _find_oracle_sym(dxf_path.stem, oracle_sym_folder=oracle_sym_folder, backup_root=backup_root),
            top=top,
        )
        for dxf_path in dxf_paths
    ]
    aggregate: dict[str, Counter[str]] = defaultdict(Counter)
    aggregate_shapes: dict[str, Counter[str]] = defaultdict(Counter)
    aggregate_deltas: dict[str, Counter[str]] = defaultdict(Counter)
    for part in parts:
        for candidate in part["candidates"]:
            name = str(candidate["name"])
            aggregate[name]["geometry_match_records"] += int(candidate["geometry_match_records"])
            aggregate[name]["changed_records"] += int(candidate["changed_records"])
            aggregate[name]["token_match_slots"] += int(candidate["token_match_slots"])
            aggregate[name]["total_slots"] += int(candidate["total_slots"])
            aggregate_shapes[name].update(
                {str(key): int(value) for key, value in candidate["mismatch_shape_counts"].items()}
            )
            aggregate_deltas[name].update(
                {str(key): int(value) for key, value in candidate["last_char_delta_counts"].items()}
            )
    return {
        "part_count": len(parts),
        "aggregate": [
            {
                "name": name,
                "geometry_match_records": counts["geometry_match_records"],
                "changed_records": counts["changed_records"],
                "token_match_slots": counts["token_match_slots"],
                "total_slots": counts["total_slots"],
                "token_match_ratio": counts["token_match_slots"] / counts["total_slots"]
                if counts["total_slots"]
                else 0.0,
                "mismatch_shape_counts": dict(aggregate_shapes[name]),
                "last_char_delta_counts": dict(sorted(aggregate_deltas[name].items(), key=lambda item: int(item[0]))),
            }
            for name, counts in sorted(aggregate.items())
        ],
        "parts": parts,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare candidate DDC token encoders against RADAN oracle SYMs.")
    parser.add_argument("--csv", type=Path, help="CSV whose first column contains DXF paths.")
    parser.add_argument("--dxf", type=Path, action="append", help="Single DXF path to analyze; may be repeated.")
    parser.add_argument("--oracle-sym-folder", type=Path, help="Folder containing oracle .sym files.")
    parser.add_argument("--backup-root", type=Path, help="Recursive backup root to search for oracle .sym files.")
    parser.add_argument("--out", type=Path, help="Optional JSON output path.")
    parser.add_argument("--top", type=int, default=10, help="Number of mismatch examples per candidate.")
    args = parser.parse_args()

    dxf_paths: list[Path] = []
    if args.csv is not None:
        dxf_paths.extend(_csv_dxf_paths(args.csv))
    if args.dxf:
        dxf_paths.extend(args.dxf)
    if not dxf_paths:
        parser.error("Provide --csv or at least one --dxf.")
    if args.oracle_sym_folder is None and args.backup_root is None:
        parser.error("Provide --oracle-sym-folder or --backup-root.")

    payload = analyze_many(
        dxf_paths,
        oracle_sym_folder=args.oracle_sym_folder,
        backup_root=args.backup_root,
        top=max(0, int(args.top)),
    )
    text = json.dumps(payload, indent=2, sort_keys=True)
    if args.out is not None:
        assert_w_drive_write_allowed(args.out, operation="write DDC token-choice analysis")
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
