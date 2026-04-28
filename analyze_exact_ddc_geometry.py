from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any

from ddc_corpus import read_ddc_records, read_dxf_entities
from ddc_number_codec import decode_ddc_number_fraction
from path_safety import assert_w_drive_write_allowed


PROFILE_LAYER = "IV_INTERIOR_PROFILES"


@dataclass(frozen=True)
class Endpoint:
    x: Fraction
    y: Fraction

    def as_float_pair(self) -> list[float]:
        return [float(self.x), float(self.y)]

    def as_exact_pair(self) -> list[str]:
        return [f"{self.x.numerator}/{self.x.denominator}", f"{self.y.numerator}/{self.y.denominator}"]


def _token_fraction(tokens: list[str], index: int) -> Fraction:
    if index >= len(tokens):
        return Fraction(0, 1)
    return decode_ddc_number_fraction(tokens[index])


def _line_endpoints(tokens: list[str]) -> tuple[Endpoint, Endpoint]:
    x = _token_fraction(tokens, 0)
    y = _token_fraction(tokens, 1)
    dx = _token_fraction(tokens, 2)
    dy = _token_fraction(tokens, 3)
    return Endpoint(x, y), Endpoint(x + dx, y + dy)


def _arc_endpoints(tokens: list[str]) -> tuple[Endpoint, Endpoint]:
    x = _token_fraction(tokens, 0)
    y = _token_fraction(tokens, 1)
    dx = _token_fraction(tokens, 2)
    dy = _token_fraction(tokens, 3)
    return Endpoint(x, y), Endpoint(x + dx, y + dy)


def _expected_record(dxf_type: str) -> str:
    if dxf_type == "LINE":
        return "G"
    if dxf_type in {"ARC", "CIRCLE"}:
        return "H"
    return ""


def _profile_endpoints_for_pairs(pairs: list[tuple[dict[str, Any], dict[str, Any]]]) -> list[dict[str, Any]]:
    endpoints: list[dict[str, Any]] = []
    for index, (dxf, ddc) in enumerate(pairs, start=1):
        if str(dxf.get("layer")) != PROFILE_LAYER:
            continue
        dxf_type = str(dxf.get("type"))
        tokens = list(ddc.get("tokens") or [])
        if dxf_type == "LINE":
            start, end = _line_endpoints(tokens)
        elif dxf_type == "ARC":
            start, end = _arc_endpoints(tokens)
        elif dxf_type == "CIRCLE":
            continue
        else:
            continue
        endpoints.append({"index": index, "role": "start", "point": start, "record": ddc.get("record"), "identifier": ddc.get("identifier")})
        endpoints.append({"index": index, "role": "end", "point": end, "record": ddc.get("record"), "identifier": ddc.get("identifier")})
    return endpoints


def _odd_profile_endpoint_summary(pairs: list[tuple[dict[str, Any], dict[str, Any]]]) -> dict[str, Any]:
    endpoint_rows = _profile_endpoints_for_pairs(pairs)
    counts: Counter[Endpoint] = Counter(row["point"] for row in endpoint_rows)
    refs: dict[Endpoint, list[dict[str, Any]]] = defaultdict(list)
    for row in endpoint_rows:
        refs[row["point"]].append(
            {
                "index": row["index"],
                "role": row["role"],
                "record": row["record"],
                "identifier": row["identifier"],
            }
        )
    odd = [
        {
            "point_float": point.as_float_pair(),
            "point_exact": point.as_exact_pair(),
            "count": count,
            "refs": refs[point][:8],
        }
        for point, count in counts.items()
        if count % 2
    ]
    odd.sort(key=lambda row: (row["point_float"][0], row["point_float"][1], row["count"]))
    return {
        "profile_endpoint_count": len(endpoint_rows),
        "profile_unique_endpoint_count": len(counts),
        "profile_odd_endpoint_count": len(odd),
        "profile_odd_endpoint_examples": odd[:20],
    }


def _geometry_shape_summary(pairs: list[tuple[dict[str, Any], dict[str, Any]]]) -> dict[str, Any]:
    pair_counts = Counter((str(ddc.get("record")), str(dxf.get("type"))) for dxf, ddc in pairs)
    token_shapes = Counter(
        (
            str(ddc.get("record")),
            str(dxf.get("type")),
            len(list(ddc.get("tokens") or [])),
            tuple(i for i, token in enumerate(list(ddc.get("tokens") or [])) if token),
        )
        for dxf, ddc in pairs
    )
    return {
        "pair_counts": [
            {"ddc_record": key[0], "dxf_type": key[1], "count": count}
            for key, count in pair_counts.most_common()
        ],
        "top_token_shapes": [
            {
                "ddc_record": key[0],
                "dxf_type": key[1],
                "token_count": key[2],
                "non_empty_slots": list(key[3]),
                "count": count,
            }
            for key, count in token_shapes.most_common(20)
        ],
    }


def _part_pairs(dxf_path: Path, sym_path: Path) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    dxf_rows, _bounds = read_dxf_entities(dxf_path)
    ddc_rows = read_ddc_records(sym_path)
    return list(zip(dxf_rows, ddc_rows))


def analyze_part(dxf_path: Path, sym_path: Path, *, compare_sym_path: Path | None = None) -> dict[str, Any]:
    dxf_rows, bounds = read_dxf_entities(dxf_path)
    ddc_rows = read_ddc_records(sym_path)
    pairs = list(zip(dxf_rows, ddc_rows))
    result: dict[str, Any] = {
        "part": dxf_path.stem,
        "dxf_path": str(dxf_path),
        "sym_path": str(sym_path),
        "bounds": bounds.as_dict(),
        "dxf_count": len(dxf_rows),
        "ddc_count": len(ddc_rows),
        "count_match": len(dxf_rows) == len(ddc_rows),
        "type_mismatch_count": sum(
            1 for dxf, ddc in pairs if str(ddc.get("record")) != _expected_record(str(dxf.get("type")))
        ),
        **_geometry_shape_summary(pairs),
        **_odd_profile_endpoint_summary(pairs),
    }

    if compare_sym_path is not None and compare_sym_path.exists():
        compare_rows = read_ddc_records(compare_sym_path)
        compare_pairs = list(zip(dxf_rows, compare_rows))
        compare_summary = _odd_profile_endpoint_summary(compare_pairs)
        changed_geometry_records = 0
        changed_token_records = 0
        for live, compare in zip(ddc_rows, compare_rows):
            if live.get("geometry_data") != compare.get("geometry_data"):
                changed_geometry_records += 1
            if live.get("tokens") != compare.get("tokens"):
                changed_token_records += 1
        result["compare_sym_path"] = str(compare_sym_path)
        result["compare_ddc_count"] = len(compare_rows)
        result["compare_profile_odd_endpoint_count"] = compare_summary["profile_odd_endpoint_count"]
        result["compare_profile_odd_endpoint_examples"] = compare_summary["profile_odd_endpoint_examples"]
        result["compare_changed_geometry_records"] = changed_geometry_records
        result["compare_changed_token_records"] = changed_token_records
    return result


def _csv_pairs(csv_path: Path, sym_folder: Path) -> list[tuple[Path, Path]]:
    pairs: list[tuple[Path, Path]] = []
    with csv_path.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.reader(handle):
            if not row or not any(cell.strip() for cell in row):
                continue
            dxf_path = Path(row[0].strip())
            pairs.append((dxf_path, sym_folder / f"{dxf_path.stem}.sym"))
    return pairs


def analyze_corpus(csv_path: Path, sym_folder: Path, *, compare_folder: Path | None = None) -> dict[str, Any]:
    part_results: list[dict[str, Any]] = []
    for dxf_path, sym_path in _csv_pairs(csv_path, sym_folder):
        compare_path = compare_folder / sym_path.name if compare_folder is not None else None
        part_results.append(analyze_part(dxf_path, sym_path, compare_sym_path=compare_path))

    odd_parts = [row for row in part_results if row["profile_odd_endpoint_count"]]
    compare_odd_parts = [row for row in part_results if row.get("compare_profile_odd_endpoint_count", 0)]
    return {
        "csv_path": str(csv_path),
        "sym_folder": str(sym_folder),
        "compare_folder": None if compare_folder is None else str(compare_folder),
        "part_count": len(part_results),
        "total_dxf_records": sum(int(row["dxf_count"]) for row in part_results),
        "total_ddc_records": sum(int(row["ddc_count"]) for row in part_results),
        "count_mismatch_parts": [row["part"] for row in part_results if not row["count_match"]],
        "type_mismatch_parts": [
            {"part": row["part"], "type_mismatch_count": row["type_mismatch_count"]}
            for row in part_results
            if row["type_mismatch_count"]
        ],
        "profile_odd_endpoint_part_count": len(odd_parts),
        "profile_odd_endpoint_parts": [
            {"part": row["part"], "odd": row["profile_odd_endpoint_count"]}
            for row in odd_parts
        ],
        "compare_profile_odd_endpoint_part_count": len(compare_odd_parts),
        "compare_profile_odd_endpoint_parts": [
            {
                "part": row["part"],
                "odd": row.get("compare_profile_odd_endpoint_count", 0),
                "changed_geometry_records": row.get("compare_changed_geometry_records", 0),
            }
            for row in compare_odd_parts
        ],
        "parts": part_results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze exact RADAN DDC profile closure against source DXFs.")
    parser.add_argument("--csv", type=Path, required=True)
    parser.add_argument("--sym-folder", type=Path, required=True)
    parser.add_argument("--compare-folder", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    payload = analyze_corpus(args.csv, args.sym_folder, compare_folder=args.compare_folder)
    text = json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True)
    if args.out:
        assert_w_drive_write_allowed(args.out, operation="write exact DDC geometry analysis")
        args.out.parent.mkdir(parents=True, exist_ok=True)
        temp_path = args.out.with_name(f"{args.out.name}.tmp")
        temp_path.write_text(text + "\n", encoding="utf-8")
        temp_path.replace(args.out)
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
