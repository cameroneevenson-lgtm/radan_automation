from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

from ddc_corpus import read_ddc_records
from path_safety import assert_w_drive_write_allowed
from radan_sym_analysis import diff_sym_sections, write_json


def _geometry_counter(path: Path, *, include_pen: bool = False) -> Counter[tuple[str, ...]]:
    rows = read_ddc_records(path)
    if include_pen:
        return Counter((str(row["record"]), str(row["pen"]), str(row["geometry_data"])) for row in rows)
    return Counter((str(row["record"]), str(row["geometry_data"])) for row in rows)


def _type_counter(path: Path) -> Counter[str]:
    return Counter(str(row["record"]) for row in read_ddc_records(path))


def _counter_common_count(left: Counter[Any], right: Counter[Any]) -> int:
    return sum((left & right).values())


def _multiset_stats(good_path: Path, compare_path: Path) -> dict[str, Any]:
    good_geometry = _geometry_counter(good_path)
    compare_geometry = _geometry_counter(compare_path)
    good_geometry_with_pen = _geometry_counter(good_path, include_pen=True)
    compare_geometry_with_pen = _geometry_counter(compare_path, include_pen=True)
    good_count = sum(good_geometry.values())
    compare_count = sum(compare_geometry.values())
    common_without_pen = _counter_common_count(good_geometry, compare_geometry)
    common_with_pen = _counter_common_count(good_geometry_with_pen, compare_geometry_with_pen)
    paired_count = min(good_count, compare_count)
    missing_without_pen = good_geometry - compare_geometry
    extra_without_pen = compare_geometry - good_geometry
    return {
        "good_record_count": good_count,
        "compare_record_count": compare_count,
        "record_count_delta": compare_count - good_count,
        "type_counter_match": _type_counter(good_path) == _type_counter(compare_path),
        "geometry_multiset_common_without_pen": common_without_pen,
        "geometry_multiset_common_with_pen": common_with_pen,
        "geometry_multiset_match_without_pen": good_geometry == compare_geometry,
        "geometry_multiset_match_with_pen": good_geometry_with_pen == compare_geometry_with_pen,
        "geometry_multiset_ratio_without_pen": common_without_pen / paired_count if paired_count else 0.0,
        "geometry_multiset_ratio_with_pen": common_with_pen / paired_count if paired_count else 0.0,
        "missing_geometry_type_counts_without_pen": dict(
            sorted(Counter(record for record, _geometry in missing_without_pen.elements()).items())
        ),
        "extra_geometry_type_counts_without_pen": dict(
            sorted(Counter(record for record, _geometry in extra_without_pen.elements()).items())
        ),
    }


def _ddc_metrics(good_path: Path, compare_path: Path) -> dict[str, Any]:
    ddc = diff_sym_sections(good_path, compare_path)["ddc_comparison"]
    metrics = {
        "count_match": bool(ddc["count_match"]),
        "type_sequence_match": bool(ddc["type_sequence_match"]),
        "pen_sequence_match": bool(ddc["pen_sequence_match"]),
        "paired_record_count": int(ddc["paired_record_count"]),
        "exact_geometry_data_matches": int(ddc["exact_geometry_data_matches"]),
        "exact_geometry_data_ratio": (
            int(ddc["exact_geometry_data_matches"]) / int(ddc["paired_record_count"])
            if int(ddc["paired_record_count"])
            else 0.0
        ),
        "token_match_slots": int(ddc["token_match_slots"]),
        "total_token_slots": int(ddc["total_token_slots"]),
        "token_match_ratio": float(ddc["token_match_ratio"]),
        "max_decoded_abs_diff": float(ddc["max_decoded_abs_diff"]),
        "decoded_error_slots": int(ddc["decoded_error_slots"]),
        "token_mismatch_shape_counts": ddc["token_mismatch_shape_counts"],
    }
    metrics.update(_multiset_stats(good_path, compare_path))
    return metrics


def _classify_part(
    *,
    before: dict[str, Any],
    after: dict[str, Any],
    decoded_tolerance: float,
) -> str:
    if not after["count_match"]:
        return "destructive_radan_repair_row_count_changed"
    if not after["type_sequence_match"]:
        if after["geometry_multiset_match_without_pen"]:
            return "row_order_changed"
        return "type_sequence_changed"
    if after["max_decoded_abs_diff"] > decoded_tolerance:
        if after["geometry_multiset_match_without_pen"]:
            return "row_order_changed"
        return "geometry_changed_after_save"
    if after["exact_geometry_data_matches"] == after["paired_record_count"]:
        return "exact_after_save"
    if after["token_match_ratio"] > before["token_match_ratio"]:
        return "canonicalized_closer"
    if after["token_match_ratio"] < before["token_match_ratio"]:
        return "decoded_close_but_token_worse"
    return "decoded_close_no_token_change"


def _part_names(good_folder: Path, before_folder: Path, after_folder: Path) -> list[str]:
    good_parts = {path.stem for path in good_folder.glob("*.sym")}
    before_parts = {path.stem for path in before_folder.glob("*.sym")}
    after_parts = {path.stem for path in after_folder.glob("*.sym")}
    return sorted(good_parts & before_parts & after_parts, key=str.casefold)


def analyze_radan_save_canonicalization(
    *,
    good_folder: Path,
    before_folder: Path,
    after_folder: Path,
    decoded_tolerance: float = 1e-12,
) -> dict[str, Any]:
    parts = _part_names(good_folder, before_folder, after_folder)
    rows: list[dict[str, Any]] = []
    missing = {
        "good_only": sorted({path.stem for path in good_folder.glob("*.sym")} - set(parts), key=str.casefold),
        "before_only": sorted({path.stem for path in before_folder.glob("*.sym")} - set(parts), key=str.casefold),
        "after_only": sorted({path.stem for path in after_folder.glob("*.sym")} - set(parts), key=str.casefold),
    }

    for part in parts:
        good_path = good_folder / f"{part}.sym"
        before_path = before_folder / f"{part}.sym"
        after_path = after_folder / f"{part}.sym"
        before = _ddc_metrics(good_path, before_path)
        after = _ddc_metrics(good_path, after_path)
        rows.append(
            {
                "part": part,
                "good_path": str(good_path),
                "before_path": str(before_path),
                "after_path": str(after_path),
                "classification": _classify_part(
                    before=before,
                    after=after,
                    decoded_tolerance=decoded_tolerance,
                ),
                "token_ratio_delta": after["token_match_ratio"] - before["token_match_ratio"],
                "exact_record_delta": after["exact_geometry_data_matches"] - before["exact_geometry_data_matches"],
                "before": before,
                "after": after,
            }
        )

    classification_counts = Counter(str(row["classification"]) for row in rows)
    before_token_matches = sum(int(row["before"]["token_match_slots"]) for row in rows)
    before_token_slots = sum(int(row["before"]["total_token_slots"]) for row in rows)
    after_token_matches = sum(int(row["after"]["token_match_slots"]) for row in rows)
    after_token_slots = sum(int(row["after"]["total_token_slots"]) for row in rows)
    before_exact_records = sum(int(row["before"]["exact_geometry_data_matches"]) for row in rows)
    before_paired_records = sum(int(row["before"]["paired_record_count"]) for row in rows)
    after_exact_records = sum(int(row["after"]["exact_geometry_data_matches"]) for row in rows)
    after_paired_records = sum(int(row["after"]["paired_record_count"]) for row in rows)

    return {
        "schema_version": 1,
        "good_folder": str(good_folder),
        "before_folder": str(before_folder),
        "after_folder": str(after_folder),
        "decoded_tolerance": decoded_tolerance,
        "part_count": len(rows),
        "missing": missing,
        "summary": {
            "classification_counts": dict(sorted(classification_counts.items())),
            "before_token_match_slots": before_token_matches,
            "before_total_token_slots": before_token_slots,
            "before_token_match_ratio": before_token_matches / before_token_slots if before_token_slots else 0.0,
            "after_token_match_slots": after_token_matches,
            "after_total_token_slots": after_token_slots,
            "after_token_match_ratio": after_token_matches / after_token_slots if after_token_slots else 0.0,
            "before_exact_geometry_data_matches": before_exact_records,
            "before_paired_record_count": before_paired_records,
            "before_exact_geometry_data_ratio": (
                before_exact_records / before_paired_records if before_paired_records else 0.0
            ),
            "after_exact_geometry_data_matches": after_exact_records,
            "after_paired_record_count": after_paired_records,
            "after_exact_geometry_data_ratio": after_exact_records / after_paired_records if after_paired_records else 0.0,
            "parts_token_ratio_improved": sum(1 for row in rows if row["token_ratio_delta"] > 0),
            "parts_token_ratio_worsened": sum(1 for row in rows if row["token_ratio_delta"] < 0),
            "parts_exact_record_count_improved": sum(1 for row in rows if row["exact_record_delta"] > 0),
            "parts_exact_record_count_worsened": sum(1 for row in rows if row["exact_record_delta"] < 0),
        },
        "top_token_ratio_improvements": sorted(rows, key=lambda row: row["token_ratio_delta"], reverse=True)[:15],
        "top_token_ratio_regressions": sorted(rows, key=lambda row: row["token_ratio_delta"])[:15],
        "destructive_or_changed_parts": [
            row
            for row in rows
            if row["classification"]
            in {
                "destructive_radan_repair_row_count_changed",
                "type_sequence_changed",
                "row_order_changed",
                "geometry_changed_after_save",
            }
        ],
        "canaries": [
            row
            for row in rows
            if row["part"] in {"B-14", "B-17", "F54410-B-49", "B-27", "F54410-B-12", "F54410-B-27"}
        ],
        "parts": rows,
    }


def _write_csv(path: Path, payload: dict[str, Any]) -> None:
    assert_w_drive_write_allowed(path, operation="write RADAN save canonicalization CSV")
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "part",
        "classification",
        "before_records",
        "after_records",
        "record_count_delta_after",
        "before_token_match_ratio",
        "after_token_match_ratio",
        "token_ratio_delta",
        "before_exact_geometry_data_matches",
        "after_exact_geometry_data_matches",
        "exact_record_delta",
        "after_max_decoded_abs_diff",
        "after_geometry_multiset_common_without_pen",
        "after_geometry_multiset_ratio_without_pen",
    ]
    temp_path = path.with_name(f"{path.name}.tmp")
    with temp_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in payload["parts"]:
            writer.writerow(
                {
                    "part": row["part"],
                    "classification": row["classification"],
                    "before_records": row["before"]["compare_record_count"],
                    "after_records": row["after"]["compare_record_count"],
                    "record_count_delta_after": row["after"]["record_count_delta"],
                    "before_token_match_ratio": row["before"]["token_match_ratio"],
                    "after_token_match_ratio": row["after"]["token_match_ratio"],
                    "token_ratio_delta": row["token_ratio_delta"],
                    "before_exact_geometry_data_matches": row["before"]["exact_geometry_data_matches"],
                    "after_exact_geometry_data_matches": row["after"]["exact_geometry_data_matches"],
                    "exact_record_delta": row["exact_record_delta"],
                    "after_max_decoded_abs_diff": row["after"]["max_decoded_abs_diff"],
                    "after_geometry_multiset_common_without_pen": row["after"]["geometry_multiset_common_without_pen"],
                    "after_geometry_multiset_ratio_without_pen": row["after"]["geometry_multiset_ratio_without_pen"],
                }
            )
    temp_path.replace(path)


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    assert_w_drive_write_allowed(path, operation="write RADAN save canonicalization report")
    summary = payload["summary"]
    lines = [
        "# RADAN Save Canonicalization Analysis",
        "",
        "Baseline: L-side known-good F54410 symbols.",
        "",
        "## Aggregate",
        "",
        f"- parts compared: `{payload['part_count']}`",
        f"- before token ratio: `{summary['before_token_match_ratio']:.6f}`",
        f"- after token ratio: `{summary['after_token_match_ratio']:.6f}`",
        f"- before exact geometry-data ratio: `{summary['before_exact_geometry_data_ratio']:.6f}`",
        f"- after exact geometry-data ratio: `{summary['after_exact_geometry_data_ratio']:.6f}`",
        f"- parts with improved token ratio: `{summary['parts_token_ratio_improved']}`",
        f"- parts with worsened token ratio: `{summary['parts_token_ratio_worsened']}`",
        "",
        "## Classifications",
        "",
    ]
    for key, count in summary["classification_counts"].items():
        lines.append(f"- `{key}`: `{count}`")
    lines.extend(["", "## Top Improvements", ""])
    for row in payload["top_token_ratio_improvements"][:10]:
        lines.append(
            f"- `{row['part']}`: `{row['before']['token_match_ratio']:.6f}` -> "
            f"`{row['after']['token_match_ratio']:.6f}`, records "
            f"`{row['before']['exact_geometry_data_matches']}` -> "
            f"`{row['after']['exact_geometry_data_matches']}`"
        )
    lines.extend(["", "## Destructive Or Changed Parts", ""])
    for row in payload["destructive_or_changed_parts"]:
        missing_counts = row["after"]["missing_geometry_type_counts_without_pen"]
        extra_counts = row["after"]["extra_geometry_type_counts_without_pen"]
        lines.append(
            f"- `{row['part']}`: `{row['classification']}`, records "
            f"`{row['before']['compare_record_count']}` -> `{row['after']['compare_record_count']}`, "
            f"max row-pair decoded diff `{row['after']['max_decoded_abs_diff']}`, "
            f"missing `{missing_counts}`, extra `{extra_counts}`"
        )
    lines.extend(["", "## Canaries", ""])
    for row in payload["canaries"]:
        lines.append(
            f"- `{row['part']}`: `{row['classification']}`, token ratio "
            f"`{row['before']['token_match_ratio']:.6f}` -> `{row['after']['token_match_ratio']:.6f}`, "
            f"exact records `{row['before']['exact_geometry_data_matches']}` -> "
            f"`{row['after']['exact_geometry_data_matches']}`"
        )
    lines.extend(
        [
            "",
            "## Conclusion",
            "",
            "- RADAN save canonicalization is useful as a reverse-engineering oracle.",
            "- It is not safe as a production repair path because several symbols are repaired into different row counts.",
            "- The best next target is token-delta mining on the `canonicalized_closer` and `exact_after_save` groups.",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.tmp")
    temp_path.write_text("\n".join(lines), encoding="utf-8")
    temp_path.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Analyze RADAN open/save canonicalization of synthetic SYM files against known-good symbols.",
    )
    parser.add_argument("--good-folder", type=Path, required=True, help="Known-good RADAN .sym folder.")
    parser.add_argument("--before-folder", type=Path, required=True, help="Synthetic .sym folder before RADAN save.")
    parser.add_argument("--after-folder", type=Path, required=True, help="Copied .sym folder after RADAN save.")
    parser.add_argument("--out-dir", type=Path, required=True, help="Output folder for JSON/CSV/report.")
    parser.add_argument("--decoded-tolerance", type=float, default=1e-12)
    args = parser.parse_args()

    payload = analyze_radan_save_canonicalization(
        good_folder=args.good_folder,
        before_folder=args.before_folder,
        after_folder=args.after_folder,
        decoded_tolerance=float(args.decoded_tolerance),
    )
    args.out_dir.mkdir(parents=True, exist_ok=True)
    write_json(args.out_dir / "radan_save_canonicalization_analysis.json", payload)
    _write_csv(args.out_dir / "radan_save_canonicalization_analysis.csv", payload)
    _write_report(args.out_dir / "RADAN_SAVE_CANONICALIZATION_ANALYSIS.md", payload)
    print(json.dumps({"part_count": payload["part_count"], **payload["summary"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
