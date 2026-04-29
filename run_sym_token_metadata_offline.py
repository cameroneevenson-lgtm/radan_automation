from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence

from path_safety import assert_w_drive_write_allowed
from radan_sym_analysis import build_sym_index, diff_sym_sections, write_index_csv, write_json


DEFAULT_TARGETS = (
    "B-17",
    "B-27",
    "B-28",
    "B-30",
    "F54410-B-41",
    "F54410-B-49",
    "B-14",
    "B-10",
    "B-16",
)
CLASSIFICATION_RANK = {
    "production-good": 0,
    "backup-good": 1,
    "lab-oracle": 2,
}


def _default_out_dir() -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Path(__file__).resolve().parent / "_sym_lab" / f"token_metadata_{stamp}"


def _target_key(value: str) -> str:
    return str(value or "").strip().casefold()


def _matches_target(part_name: str, target: str) -> bool:
    part_key = _target_key(part_name)
    target_key = _target_key(target)
    return part_key == target_key or part_key.startswith(f"{target_key}_")


def _select_good_symbol(symbols: Sequence[dict[str, Any]], target: str) -> dict[str, Any] | None:
    candidates = [
        row
        for row in symbols
        if bool(row.get("safe_oracle")) and _target_key(str(row.get("part_name", ""))) == _target_key(target)
    ]
    candidates.sort(
        key=lambda row: (
            CLASSIFICATION_RANK.get(str(row.get("classification", "")), 99),
            str(row.get("path", "")).casefold(),
        )
    )
    return candidates[0] if candidates else None


def _select_compare_symbols(symbols: Sequence[dict[str, Any]], target: str, *, max_candidates: int) -> list[dict[str, Any]]:
    candidates = [
        row
        for row in symbols
        if not bool(row.get("safe_oracle"))
        and str(row.get("classification", "")) != "donor"
        and _matches_target(str(row.get("part_name", "")), target)
    ]
    candidates.sort(
        key=lambda row: (
            0 if "\\synthetic_topology_canonical_source6_preserve_radius_full_20260427\\" in str(row.get("path", "")).replace("/", "\\").casefold() else 1,
            str(row.get("path", "")).casefold(),
        )
    )
    if max_candidates > 0:
        return candidates[:max_candidates]
    return candidates


def _safe_filename(text: str) -> str:
    return "".join(char if char.isalnum() or char in {"-", "_", "."} else "_" for char in text)


def _diff_summary(payload: dict[str, Any]) -> dict[str, Any]:
    ddc = payload["ddc_comparison"]
    return {
        "good_path": payload["good_path"],
        "compare_path": payload["compare_path"],
        "difference_localization": payload["difference_localization"],
        "classification": payload["compare"]["classification"],
        "count_match": ddc["count_match"],
        "type_sequence_match": ddc["type_sequence_match"],
        "pen_sequence_match": ddc["pen_sequence_match"],
        "paired_record_count": ddc["paired_record_count"],
        "exact_raw_record_matches": ddc["exact_raw_record_matches"],
        "exact_geometry_data_matches": ddc["exact_geometry_data_matches"],
        "token_match_ratio": ddc["token_match_ratio"],
        "token_mismatch_shape_counts": ddc["token_mismatch_shape_counts"],
        "max_decoded_abs_diff": ddc["max_decoded_abs_diff"],
        "important_attr_diff_count": len(payload["important_attr_diffs"]),
        "normalized_wrapper_equal": payload["section_equalities"]["normalized_wrapper_without_ddc_or_history"],
        "history_equal": payload["section_equalities"]["history"],
        "ddc_non_geometry_equal": payload["section_equalities"]["ddc_non_geometry_lines"],
    }


def _write_report(path: Path, payload: dict[str, Any]) -> None:
    assert_w_drive_write_allowed(path, operation="write token metadata offline report")
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    lines.append("# SYM Token and Metadata Offline Report")
    lines.append("")
    lines.append(f"Run folder: `{payload['out_dir']}`")
    lines.append("")
    lines.append("## Oracle Index")
    lines.append("")
    index = payload["index_summary"]
    lines.append(f"- Symbols indexed: `{index['symbol_count']}`")
    lines.append(f"- Safe oracles: `{index['safe_oracle_count']}`")
    lines.append(f"- Duplicate part groups: `{index['duplicate_part_count']}`")
    lines.append(f"- Classifications: `{json.dumps(index['classification_counts'], sort_keys=True)}`")
    lines.append("")
    lines.append("## Target Results")
    lines.append("")
    for target in payload["targets"]:
        lines.append(f"### {target['target']}")
        if target.get("status") != "diffed":
            lines.append("")
            lines.append(f"- Status: `{target.get('status')}`")
            lines.append(f"- Reason: {target.get('reason', '')}")
            lines.append("")
            continue
        lines.append("")
        lines.append(f"- Good oracle: `{target['good_path']}`")
        lines.append(f"- Compare candidates: `{len(target['diffs'])}`")
        for diff in target["diffs"]:
            compare_name = Path(diff["compare_path"]).parent.name + "/" + Path(diff["compare_path"]).name
            lines.append(
                "- "
                f"`{compare_name}`: "
                f"localization=`{diff['difference_localization']}`, "
                f"records={diff['exact_geometry_data_matches']}/{diff['paired_record_count']}, "
                f"token_ratio={diff['token_match_ratio']:.6f}, "
                f"max_decoded_diff={diff['max_decoded_abs_diff']}, "
                f"shapes=`{json.dumps(diff['token_mismatch_shape_counts'], sort_keys=True)}`"
            )
        lines.append("")
    lines.append("## Next RADAN-Gated Questions")
    lines.append("")
    lines.append("- Do RADAN-visible failures follow DDC geometry text only, or also wrapper/history/cache fields?")
    lines.append("- Which non-geometry fields change when RADAN opens and resaves a lab copy?")
    lines.append("- Can tiny RADAN-generated one-line/one-arc oracles reveal the token choice rule?")
    temp_path = path.with_name(f"{path.name}.tmp")
    temp_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    temp_path.replace(path)


def run_offline_research(
    *,
    roots: Sequence[Path],
    out_dir: Path,
    targets: Sequence[str],
    max_candidates: int,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    index = build_sym_index(roots)
    index_json = out_dir / "sym_oracle_index.json"
    index_csv = out_dir / "sym_oracle_index.csv"
    write_json(index_json, index)
    write_index_csv(index_csv, index["symbols"])

    diff_dir = out_dir / "section_diffs"
    diff_dir.mkdir(parents=True, exist_ok=True)
    target_payloads: list[dict[str, Any]] = []
    for target in targets:
        good = _select_good_symbol(index["symbols"], target)
        if good is None:
            target_payloads.append({"target": target, "status": "skipped", "reason": "missing safe oracle"})
            continue
        compares = _select_compare_symbols(index["symbols"], target, max_candidates=max_candidates)
        if not compares:
            target_payloads.append(
                {
                    "target": target,
                    "status": "skipped",
                    "reason": "missing synthetic/suspect compare candidate",
                    "good_path": good["path"],
                }
            )
            continue
        diff_summaries = []
        for compare in compares:
            diff = diff_sym_sections(Path(good["path"]), Path(compare["path"]))
            compare_parent = Path(compare["path"]).parent.name
            diff_path = diff_dir / f"{_safe_filename(target)}__{_safe_filename(compare_parent)}__{_safe_filename(Path(compare['path']).stem)}.json"
            write_json(diff_path, diff)
            summary = _diff_summary(diff)
            summary["diff_path"] = str(diff_path)
            diff_summaries.append(summary)
        target_payloads.append(
            {
                "target": target,
                "status": "diffed",
                "good_path": good["path"],
                "diffs": diff_summaries,
            }
        )

    run_payload = {
        "schema_version": 1,
        "out_dir": str(out_dir),
        "roots": [str(root) for root in roots],
        "targets": target_payloads,
        "index_json": str(index_json),
        "index_csv": str(index_csv),
        "index_summary": {
            "symbol_count": index["symbol_count"],
            "safe_oracle_count": index["safe_oracle_count"],
            "classification_counts": index["classification_counts"],
            "duplicate_part_count": index["duplicate_part_count"],
        },
    }
    write_json(out_dir / "run_summary.json", run_payload)
    _write_report(out_dir / "SYM_TOKEN_METADATA_OFFLINE_REPORT.md", run_payload)
    return run_payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the offline SYM token/metadata research pass.")
    parser.add_argument("--root", type=Path, action="append", required=True, help="SYM root/file to index.")
    parser.add_argument("--out-dir", type=Path, default=_default_out_dir(), help="Research artifact output folder.")
    parser.add_argument("--target", action="append", help="Part target to diff. Defaults to known canaries.")
    parser.add_argument(
        "--max-candidates",
        type=int,
        default=6,
        help="Max synthetic/suspect compare candidates per target. Use 0 for all.",
    )
    args = parser.parse_args()

    payload = run_offline_research(
        roots=args.root,
        out_dir=args.out_dir,
        targets=tuple(args.target or DEFAULT_TARGETS),
        max_candidates=int(args.max_candidates),
    )
    print(json.dumps(payload["index_summary"], indent=2, ensure_ascii=True, sort_keys=True))
    print(f"Report: {payload['out_dir']}\\SYM_TOKEN_METADATA_OFFLINE_REPORT.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
