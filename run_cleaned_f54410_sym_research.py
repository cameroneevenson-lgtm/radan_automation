from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from analyze_ddc_tokens import analyze_corpus
from analyze_radan_token_choices import analyze_many
from clean_dxf_outer_profile import clean_outer_profile, preprocessed_output_paths
from compare_ddc_geometry import compare_part
from ddc_corpus import build_corpus, build_part_corpus, read_ddc_records, read_dxf_entities
from path_safety import assert_w_drive_write_allowed
from validate_native_sym import validate_native_sym
from write_native_sym_prototype import write_native_prototype


DEFAULT_CSV = Path(
    r"L:\BATTLESHIELD\F-LARGE FLEET\F54410\PAINT PACK\F54410 PAINT PACK\F54410-PAINT PACK-BOM_Radan.csv"
)
DEFAULT_PROJECT_FOLDER = Path(
    r"L:\BATTLESHIELD\F-LARGE FLEET\F54410\PAINT PACK\F54410 PAINT PACK"
)
DEFAULT_L_SIDE_SYMBOL_FOLDER = Path(r"L:\BATTLESHIELD\F-LARGE FLEET\F54410\PAINT PACK")
DEFAULT_LAB_ROOT = Path(__file__).resolve().parent / "_sym_lab"
DEFAULT_TARGETS = (
    "F54410-B-49",
    "B-17",
    "B-27",
    "B-28",
    "B-30",
    "F54410-B-41",
    "B-14",
)
PROCESS_PATTERN = "radan|radraft|radnest|radpunch"
WINDOW_PATTERN = "RADAN|Radraft|RADRAFT"


@dataclass(frozen=True)
class CsvPartRow:
    part_name: str
    raw_dxf_path: Path
    columns: list[str]


def _timestamp() -> str:
    return dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def _json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    return str(value)


def write_json_file(path: Path, payload: Any) -> None:
    assert_w_drive_write_allowed(path, operation="write cleaned SYM research artifact")
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.tmp")
    temp_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True, default=_json_default) + "\n",
        encoding="utf-8",
    )
    temp_path.replace(path)


def append_note(out_dir: Path, text: str) -> None:
    assert_w_drive_write_allowed(out_dir / "notes.md", operation="write cleaned SYM research notes")
    with (out_dir / "notes.md").open("a", encoding="utf-8") as handle:
        handle.write(text.rstrip() + "\n")


def _run_powershell_json(command: str) -> list[dict[str, Any]]:
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    output = result.stdout.strip()
    if not output:
        return []
    payload = json.loads(output)
    if isinstance(payload, dict):
        return [payload]
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def list_radan_processes() -> list[dict[str, Any]]:
    command = (
        "Get-Process | Where-Object { "
        f"$_.ProcessName -match '{PROCESS_PATTERN}' -or "
        f"$_.MainWindowTitle -match '{WINDOW_PATTERN}' "
        "} | Select-Object @{Name='Id';Expression={$_.Id}}, "
        "@{Name='ProcessName';Expression={$_.ProcessName}}, "
        "@{Name='Path';Expression={$_.Path}}, "
        "@{Name='MainWindowTitle';Expression={$_.MainWindowTitle}} | "
        "ConvertTo-Json -Depth 4"
    )
    processes = _run_powershell_json(command)
    for process in processes:
        process["kill_eligible"] = _is_kill_eligible_radan_process(process)
    return processes


def _is_kill_eligible_radan_process(process: dict[str, Any]) -> bool:
    name = str(process.get("ProcessName") or "")
    path = str(process.get("Path") or "")
    haystack = f"{name}\n{Path(path).name if path else ''}".casefold()
    return re.search(PROCESS_PATTERN, haystack, flags=re.IGNORECASE) is not None


def _killable(processes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [process for process in processes if _is_kill_eligible_radan_process(process)]


def kill_radan_processes(processes: list[dict[str, Any]] | None = None) -> None:
    candidates = list_radan_processes() if processes is None else processes
    ids = [int(process["Id"]) for process in _killable(candidates) if str(process.get("Id", "")).isdigit()]
    if not ids:
        return
    id_list = ",".join(str(pid) for pid in ids)
    command = f"Stop-Process -Id {id_list} -Force"
    subprocess.run(["powershell", "-NoProfile", "-Command", command], check=False)


def cleanup_radan_processes(out_dir: Path, label: str, *, kill: bool) -> dict[str, Any]:
    before = list_radan_processes()
    write_json_file(out_dir / f"process_cleanup_{label}.json", before)
    if kill and before:
        kill_radan_processes(before)
        time.sleep(1.0)
    after = list_radan_processes()
    if kill:
        write_json_file(out_dir / f"process_cleanup_{label}_after_kill.json", after)
    return {
        "before": before,
        "after": after,
        "before_killable": _killable(before),
        "after_killable": _killable(after),
    }


def read_import_csv(csv_path: Path) -> list[CsvPartRow]:
    rows: list[CsvPartRow] = []
    with csv_path.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.reader(handle):
            if not row or not any(cell.strip() for cell in row):
                continue
            raw_dxf_path = Path(row[0].strip())
            rows.append(CsvPartRow(part_name=raw_dxf_path.stem, raw_dxf_path=raw_dxf_path, columns=list(row)))
    if not rows:
        raise ValueError(f"No import rows found in {csv_path}")
    return rows


def _read_json_if_exists(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _entity_summary(path: Path) -> dict[str, Any]:
    rows, _bounds = read_dxf_entities(path)
    entity_types: dict[str, int] = {}
    layer_counts: dict[str, int] = {}
    for row in rows:
        entity_types[str(row.get("type", ""))] = entity_types.get(str(row.get("type", "")), 0) + 1
        layer_counts[str(row.get("layer", ""))] = layer_counts.get(str(row.get("layer", "")), 0) + 1
    return {
        "entity_count": len(rows),
        "entity_types": entity_types,
        "layers": layer_counts,
        "line_only": bool(rows) and set(entity_types) == {"LINE"},
    }


def ensure_cleaned_dxf(
    part: CsvPartRow,
    *,
    project_folder: Path,
    tolerance: float,
) -> dict[str, Any]:
    cleaned_path, report_path = preprocessed_output_paths(
        dxf_path=part.raw_dxf_path,
        project_folder=project_folder,
        tolerance=tolerance,
    )
    assert_w_drive_write_allowed(cleaned_path, operation="write cleaned DXF working copy")
    assert_w_drive_write_allowed(report_path, operation="write cleaned DXF report")

    created_or_refreshed = False
    payload = _read_json_if_exists(report_path)
    if not cleaned_path.exists():
        try:
            payload = clean_outer_profile(
                dxf_path=part.raw_dxf_path,
                project_folder=project_folder,
                simplify_tolerance=tolerance,
            )
        except Exception as exc:
            payload = {
                "dxf_path": str(part.raw_dxf_path),
                "out_path": str(cleaned_path),
                "project_folder": str(project_folder),
                "preprocessed_folder": str(cleaned_path.parent),
                "wrote_output": False,
                "skipped_write_reason": f"{type(exc).__name__}: {exc}",
                "cleaner_error": True,
            }
        created_or_refreshed = True

    fallback_copied_original = False
    if not cleaned_path.exists():
        cleaned_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(part.raw_dxf_path, cleaned_path)
        fallback_copied_original = True
        payload["fallback_copied_original"] = True
        payload["fallback_reason"] = payload.get("skipped_write_reason") or "cleaner did not produce an output DXF"
        payload["usable_preprocessed_path"] = str(cleaned_path)
        payload["out_path"] = str(cleaned_path)
        payload["report_path"] = str(report_path)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        created_or_refreshed = True
    else:
        fallback_copied_original = bool(payload.get("fallback_copied_original", False))

    raw_summary = _entity_summary(part.raw_dxf_path)
    cleaned_summary = _entity_summary(cleaned_path)
    simplification = payload.get("simplification") if isinstance(payload.get("simplification"), dict) else {}
    return {
        "part_name": part.part_name,
        "raw_dxf_path": str(part.raw_dxf_path),
        "cleaned_dxf_path": str(cleaned_path),
        "cleaning_report_path": str(report_path),
        "created_or_refreshed": created_or_refreshed,
        "fallback_copied_original": fallback_copied_original,
        "cleaner_wrote_output": bool(payload.get("wrote_output")),
        "skipped_write_reason": payload.get("skipped_write_reason"),
        "selected_outside_entity_types": payload.get("selected_outside_entity_types", []),
        "selected_outside_entity_count": payload.get("selected_outside_entity_count"),
        "raw_entity_count": raw_summary["entity_count"],
        "cleaned_entity_count": cleaned_summary["entity_count"],
        "raw_entity_types": raw_summary["entity_types"],
        "cleaned_entity_types": cleaned_summary["entity_types"],
        "line_only_after_cleaning": bool(cleaned_summary["line_only"]),
        "entity_count_delta": int(cleaned_summary["entity_count"]) - int(raw_summary["entity_count"]),
        "removed_vertices": int(simplification.get("removed_vertices", 0) or 0),
        "max_final_vertex_deviation": float(simplification.get("max_final_vertex_deviation", 0.0) or 0.0),
        "area_delta": simplification.get("area_delta"),
        "area_delta_abs": simplification.get("area_delta_abs"),
    }


def write_manifest_csv(path: Path, manifest_rows: list[dict[str, Any]]) -> None:
    assert_w_drive_write_allowed(path, operation="write cleaned DXF manifest CSV")
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "part_name",
        "raw_dxf_path",
        "cleaned_dxf_path",
        "cleaning_report_path",
        "fallback_copied_original",
        "cleaner_wrote_output",
        "raw_entity_count",
        "cleaned_entity_count",
        "entity_count_delta",
        "removed_vertices",
        "max_final_vertex_deviation",
        "area_delta",
        "area_delta_abs",
        "selected_outside_entity_types",
        "line_only_after_cleaning",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in manifest_rows:
            output = {field: row.get(field, "") for field in fields}
            output["selected_outside_entity_types"] = ";".join(str(value) for value in output["selected_outside_entity_types"])
            writer.writerow(output)


def write_cleaned_import_csv(parts: list[CsvPartRow], manifest_by_part: dict[str, dict[str, Any]], out_path: Path) -> None:
    assert_w_drive_write_allowed(out_path, operation="write cleaned DXF import CSV")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        for part in parts:
            row = list(part.columns)
            row[0] = str(manifest_by_part[part.part_name]["cleaned_dxf_path"])
            writer.writerow(row)


def _safe_lab_oracle_dirs(lab_root: Path) -> list[Path]:
    if not lab_root.exists():
        return []
    dirs = []
    for path in lab_root.rglob("*"):
        if not path.is_dir():
            continue
        lower = str(path).casefold()
        if ("radan_known_good" in lower or "radan_oracle" in lower) and "synthetic" not in lower and "donor" not in lower:
            dirs.append(path)
    return dirs


def find_safe_oracle(part_name: str, *, l_side_symbol_folder: Path, lab_root: Path) -> Path | None:
    candidates: list[tuple[int, int, str, Path]] = []
    top_level = l_side_symbol_folder / f"{part_name}.sym"
    if top_level.exists() and top_level.name.casefold() != "donor.sym":
        candidates.append((1, top_level.stat().st_mtime_ns, str(top_level), top_level))
    for folder in _safe_lab_oracle_dirs(lab_root):
        for candidate in folder.glob(f"**/{part_name}.sym"):
            lower = str(candidate).casefold()
            if "synthetic" in lower or "donor" in lower or candidate.name.casefold() == "donor.sym":
                continue
            candidates.append((2, candidate.stat().st_mtime_ns, str(candidate), candidate))
    if not candidates:
        return None
    return sorted(candidates)[-1][3]


def build_oracle_index(
    manifest_rows: list[dict[str, Any]],
    *,
    l_side_symbol_folder: Path,
    lab_root: Path,
    out_dir: Path,
) -> tuple[dict[str, dict[str, Any]], Path]:
    oracle_folder = out_dir / "oracle_by_cleaned_stem"
    oracle_folder.mkdir(parents=True, exist_ok=True)
    index: dict[str, dict[str, Any]] = {}
    for row in manifest_rows:
        part_name = str(row["part_name"])
        oracle = find_safe_oracle(part_name, l_side_symbol_folder=l_side_symbol_folder, lab_root=lab_root)
        cleaned_stem = Path(str(row["cleaned_dxf_path"])).stem
        copied_oracle = oracle_folder / f"{cleaned_stem}.sym"
        if oracle is not None:
            shutil.copy2(oracle, copied_oracle)
        index[part_name] = {
            "part_name": part_name,
            "oracle_sym_path": None if oracle is None else str(oracle),
            "cleaned_stem_oracle_sym_path": None if oracle is None else str(copied_oracle),
            "has_oracle": oracle is not None,
        }
    return index, oracle_folder


def _record_types_align(dxf_path: Path, sym_path: Path) -> bool:
    part = build_part_corpus(dxf_path, sym_path)
    return bool(part["count_match"]) and int(part["type_mismatch_count"]) == 0


def _token_match_ratio(compare: dict[str, Any] | None) -> float | None:
    if compare is None:
        return None
    if compare.get("token_match_ratio") is not None:
        return float(compare["token_match_ratio"])
    total = int(compare.get("total_slots") or 0)
    if total <= 0:
        return None
    return float(compare.get("token_match_slots") or 0) / float(total)


def _write_cleaned_subset_csv(
    parts: list[CsvPartRow],
    manifest_by_part: dict[str, dict[str, Any]],
    allowed_parts: set[str],
    out_path: Path,
) -> None:
    assert_w_drive_write_allowed(out_path, operation="write cleaned DXF subset CSV")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        for part in parts:
            if part.part_name not in allowed_parts:
                continue
            row = list(part.columns)
            row[0] = str(manifest_by_part[part.part_name]["cleaned_dxf_path"])
            writer.writerow(row)


def run_research(
    *,
    csv_path: Path,
    project_folder: Path,
    out_dir: Path,
    tolerance: float,
    targets: list[str],
    allow_radan_oracle: bool,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    command_text = " ".join(sys.argv)
    append_note(out_dir, f"# Cleaned F54410 SYM Research Run\n\nStarted: {dt.datetime.now().isoformat()}")
    append_note(out_dir, f"- Command: {command_text}")
    process_start = cleanup_radan_processes(out_dir, "orchestrator_start", kill=True)

    parts = read_import_csv(csv_path)
    manifest_rows = [
        ensure_cleaned_dxf(part, project_folder=project_folder, tolerance=tolerance)
        for part in parts
    ]
    manifest_by_part = {str(row["part_name"]): row for row in manifest_rows}
    write_json_file(out_dir / "cleaned_manifest.json", {"parts": manifest_rows})
    write_manifest_csv(out_dir / "cleaned_manifest.csv", manifest_rows)
    cleaned_csv = out_dir / "F54410_cleaned_BOM_Radan.csv"
    write_cleaned_import_csv(parts, manifest_by_part, cleaned_csv)
    append_note(
        out_dir,
        f"- Ensured {len(manifest_rows)} cleaned DXF input(s); "
        f"{sum(1 for row in manifest_rows if int(row['entity_count_delta']) != 0)} changed entity count.",
    )

    oracle_index, oracle_folder = build_oracle_index(
        manifest_rows,
        l_side_symbol_folder=project_folder.parent,
        lab_root=DEFAULT_LAB_ROOT,
        out_dir=out_dir,
    )
    write_json_file(out_dir / "oracle_index.json", oracle_index)
    available_parts = {part for part, row in oracle_index.items() if row["has_oracle"]}
    append_note(out_dir, f"- Indexed {len(available_parts)} safe oracle/template symbol(s); donor and synthetic folders excluded.")
    oracle_available_csv = out_dir / "F54410_cleaned_oracle_available_BOM_Radan.csv"
    _write_cleaned_subset_csv(parts, manifest_by_part, available_parts, oracle_available_csv)

    corpus_payload: dict[str, Any] | None = None
    token_analysis: dict[str, Any] | None = None
    token_choice: dict[str, Any] | None = None
    comparable_parts: set[str] = set()
    if available_parts:
        corpus_payload = build_corpus(oracle_available_csv, oracle_folder)
        write_json_file(out_dir / "cleaned_oracle_available_corpus.json", corpus_payload)
        token_analysis = analyze_corpus(corpus_payload, top=20)
        write_json_file(out_dir / "cleaned_oracle_available_token_analysis.json", token_analysis)
        for part_name in sorted(available_parts):
            dxf_path = Path(str(manifest_by_part[part_name]["cleaned_dxf_path"]))
            sym_path = Path(str(oracle_index[part_name]["cleaned_stem_oracle_sym_path"]))
            if _record_types_align(dxf_path, sym_path):
                comparable_parts.add(part_name)
        comparable_csv = out_dir / "F54410_cleaned_comparable_BOM_Radan.csv"
        _write_cleaned_subset_csv(parts, manifest_by_part, comparable_parts, comparable_csv)
        if comparable_parts:
            token_choice = analyze_many(
                [Path(str(manifest_by_part[part]["cleaned_dxf_path"])) for part in sorted(comparable_parts)],
                oracle_sym_folder=oracle_folder,
                backup_root=None,
                top=20,
            )
            write_json_file(out_dir / "cleaned_comparable_token_choice_analysis.json", token_choice)
    append_note(out_dir, f"- Found {len(comparable_parts)} record-count/type comparable cleaned oracle pair(s).")

    line_only_available = [
        str(row["part_name"])
        for row in manifest_rows
        if bool(row["line_only_after_cleaning"]) and str(row["part_name"]) in available_parts
    ]
    generation_targets = []
    for part_name in list(targets) + line_only_available:
        if part_name in manifest_by_part and part_name not in generation_targets:
            generation_targets.append(part_name)

    generated_dir = out_dir / "generated_syms_by_cleaned_stem"
    generated_dir.mkdir(parents=True, exist_ok=True)
    generation_results: list[dict[str, Any]] = []
    for part_name in generation_targets:
        manifest = manifest_by_part[part_name]
        oracle = oracle_index.get(part_name, {})
        if not oracle.get("has_oracle"):
            generation_results.append(
                {
                    "part_name": part_name,
                    "status": "skipped_missing_safe_oracle_template",
                    "cleaned_dxf_path": manifest["cleaned_dxf_path"],
                }
            )
            continue
        cleaned_dxf = Path(str(manifest["cleaned_dxf_path"]))
        out_sym = generated_dir / f"{cleaned_dxf.stem}.sym"
        report_path = generated_dir / f"{cleaned_dxf.stem}.write_report.json"
        try:
            write_report = write_native_prototype(
                dxf_path=cleaned_dxf,
                template_sym=Path(str(oracle["oracle_sym_path"])),
                out_path=out_sym,
                source_coordinate_digits=6,
                topology_snap_endpoints=True,
                canonicalize_endpoints=True,
            )
            write_json_file(report_path, write_report)
            validation = validate_native_sym(dxf_path=cleaned_dxf, sym_path=out_sym)
            write_json_file(generated_dir / f"{cleaned_dxf.stem}.validation.json", validation)
            compare = None
            compare_status = "skipped_record_count_or_type_mismatch"
            oracle_by_cleaned = Path(str(oracle["cleaned_stem_oracle_sym_path"]))
            if _record_types_align(cleaned_dxf, oracle_by_cleaned):
                compare = compare_part(cleaned_dxf, oracle_by_cleaned, out_sym, top=20)
                compare_status = "compared"
                write_json_file(generated_dir / f"{cleaned_dxf.stem}.compare.json", compare)
            generation_results.append(
                {
                    "part_name": part_name,
                    "status": "generated",
                    "cleaned_dxf_path": str(cleaned_dxf),
                    "template_sym_path": oracle["oracle_sym_path"],
                    "generated_sym_path": str(out_sym),
                    "write_report_path": str(report_path),
                    "validation_passed": bool(validation.get("passed")),
                    "compare_status": compare_status,
                    "exact_geometry_record_matches": (
                        None
                        if compare is None
                        else int(compare["dxf_count"]) - int(compare["changed_geometry_records"])
                    ),
                    "token_match_ratio": _token_match_ratio(compare),
                    "max_decoded_abs_diff": None if compare is None else compare.get("max_abs_diff"),
                }
            )
        except Exception as exc:
            generation_results.append(
                {
                    "part_name": part_name,
                    "status": "error",
                    "cleaned_dxf_path": manifest["cleaned_dxf_path"],
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )

    write_json_file(out_dir / "generation_results.json", generation_results)
    append_note(
        out_dir,
        f"- Generated {sum(1 for row in generation_results if row['status'] == 'generated')} lab-only synthetic SYM prototype(s); "
        f"{sum(1 for row in generation_results if row['status'] != 'generated')} target(s) skipped/error.",
    )

    b49_note = "not present in CSV"
    if "F54410-B-49" in manifest_by_part:
        b49 = manifest_by_part["F54410-B-49"]
        b49_oracle = oracle_index.get("F54410-B-49", {})
        if not b49_oracle.get("has_oracle"):
            b49_note = "cleaned B-49 has no safe oracle/template; needs fresh cleaned RADAN oracle for exact token comparison"
        else:
            b49_cleaned = Path(str(b49["cleaned_dxf_path"]))
            b49_oracle_sym = Path(str(b49_oracle["cleaned_stem_oracle_sym_path"]))
            if _record_types_align(b49_cleaned, b49_oracle_sym):
                b49_note = "cleaned B-49 aligns with available oracle for record-count/type comparison"
            else:
                b49_note = "cleaned B-49 intentionally changes record count/type alignment; needs fresh cleaned RADAN oracle"

    final_cleanup = cleanup_radan_processes(out_dir, "end", kill=True)
    write_json_file(out_dir / "process_cleanup_end_before_kill.json", final_cleanup["before"])
    write_json_file(out_dir / "process_cleanup_end.json", final_cleanup["after"])
    report = {
        "started_process_cleanup": process_start,
        "final_process_cleanup": final_cleanup,
        "csv_path": str(csv_path),
        "project_folder": str(project_folder),
        "commands": [command_text],
        "out_dir": str(out_dir),
        "part_count": len(parts),
        "cleaned_csv": str(cleaned_csv),
        "manifest_json": str(out_dir / "cleaned_manifest.json"),
        "manifest_csv": str(out_dir / "cleaned_manifest.csv"),
        "cleaned_dxf_count": len(manifest_rows),
        "fallback_copied_count": sum(1 for row in manifest_rows if bool(row["fallback_copied_original"])),
        "simplified_count": sum(1 for row in manifest_rows if int(row["removed_vertices"]) > 0),
        "entity_count_changed_count": sum(1 for row in manifest_rows if int(row["entity_count_delta"]) != 0),
        "line_only_after_cleaning_count": sum(1 for row in manifest_rows if bool(row["line_only_after_cleaning"])),
        "oracle_available_count": len(available_parts),
        "comparable_oracle_count": len(comparable_parts),
        "generation_attempt_count": len(generation_results),
        "generation_success_count": sum(1 for row in generation_results if row["status"] == "generated"),
        "generation_validation_pass_count": sum(1 for row in generation_results if bool(row.get("validation_passed"))),
        "b49_note": b49_note,
        "allow_radan_oracle": bool(allow_radan_oracle),
        "promotion_recommendation": "do not promote",
        "next_experiment": "create a one-part cleaned RADAN oracle for F54410-B-49 in a lab folder if exact token comparison remains necessary",
        "token_choice_summary": None if token_choice is None else token_choice.get("aggregate", []),
    }
    write_json_file(out_dir / "run_summary.json", report)
    write_overnight_report(out_dir, report, generation_results, manifest_rows)
    append_note(out_dir, f"\nFinished: {dt.datetime.now().isoformat()}")
    return report


def write_overnight_report(
    out_dir: Path,
    summary: dict[str, Any],
    generation_results: list[dict[str, Any]],
    manifest_rows: list[dict[str, Any]],
) -> None:
    assert_w_drive_write_allowed(out_dir / "OVERNIGHT_CLEANED_SYM_REPORT.md", operation="write cleaned SYM report")
    simplified = [row for row in manifest_rows if int(row["removed_vertices"]) > 0]
    changed = [row for row in manifest_rows if int(row["entity_count_delta"]) != 0]
    generated = [row for row in generation_results if row["status"] == "generated"]
    skipped = [row for row in generation_results if row["status"] != "generated"]
    lines = [
        "# Overnight Cleaned SYM Report",
        "",
        f"Run folder: `{out_dir}`",
        f"Input CSV: `{summary['csv_path']}`",
        f"Cleaned CSV: `{summary['cleaned_csv']}`",
        "",
        "## Commands",
        "",
        *[f"- `{command}`" for command in summary.get("commands", [])],
        "",
        "## Process Cleanup",
        "",
        f"Start RADAN-family processes before kill: {len(summary['started_process_cleanup']['before_killable'])}",
        f"Start RADAN-family processes after kill: {len(summary['started_process_cleanup']['after_killable'])}",
        f"Final RADAN-family processes after kill: {len(summary['final_process_cleanup']['after_killable'])}",
        f"Final title/process matches logged after kill: {len(summary['final_process_cleanup']['after'])}",
        "",
        "## Cleaned DXF Manifest",
        "",
        f"Parts: {summary['part_count']}",
        f"Cleaned DXFs: {summary['cleaned_dxf_count']}",
        f"Simplified parts: {summary['simplified_count']}",
        f"Fallback-copied parts: {summary['fallback_copied_count']}",
        f"Entity-count-changed parts: {summary['entity_count_changed_count']}",
        f"Line-only after cleaning: {summary['line_only_after_cleaning_count']}",
        "",
        "Simplified/entity-changed parts:",
    ]
    for row in changed[:40]:
        lines.append(
            f"- {row['part_name']}: raw={row['raw_entity_count']}, cleaned={row['cleaned_entity_count']}, "
            f"removed_vertices={row['removed_vertices']}, max_dev={row['max_final_vertex_deviation']}"
        )
    if len(changed) > 40:
        lines.append(f"- ... {len(changed) - 40} more")
    if not changed:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Oracle / Token Results",
            "",
            f"Safe oracle/template count: {summary['oracle_available_count']}",
            f"Record-count/type comparable oracle count: {summary['comparable_oracle_count']}",
            f"B-49: {summary['b49_note']}",
            "",
            "## Native Generation",
            "",
            f"Generation attempts/skips: {summary['generation_attempt_count']}",
            f"Generated: {summary['generation_success_count']}",
            f"Validation passed: {summary['generation_validation_pass_count']}",
        ]
    )
    for row in generated:
        lines.append(
            f"- {row['part_name']}: validation={row.get('validation_passed')}, "
            f"compare={row.get('compare_status')}, token_ratio={row.get('token_match_ratio')}, "
            f"sym=`{row.get('generated_sym_path')}`"
        )
    for row in skipped[:30]:
        lines.append(f"- {row['part_name']}: {row['status']}")
    if len(skipped) > 30:
        lines.append(f"- ... {len(skipped) - 30} more skipped/error rows")
    lines.extend(
        [
            "",
            "## Recommendation",
            "",
            f"Promotion recommendation: **{summary['promotion_recommendation']}**.",
            f"Next experiment: {summary['next_experiment']}.",
        ]
    )
    (out_dir / "OVERNIGHT_CLEANED_SYM_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run cleaned-DXF-first F54410 native SYM research.")
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--project-folder", type=Path, default=DEFAULT_PROJECT_FOLDER)
    parser.add_argument("--out-dir", type=Path)
    parser.add_argument("--tolerance", type=float, default=0.002)
    parser.add_argument("--target", action="append", default=[])
    parser.add_argument("--allow-radan-oracle", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    out_dir = args.out_dir or (DEFAULT_LAB_ROOT / f"overnight_cleaned_f54410_{_timestamp()}")
    targets = list(args.target) if args.target else list(DEFAULT_TARGETS)
    summary = run_research(
        csv_path=args.csv,
        project_folder=args.project_folder,
        out_dir=out_dir,
        tolerance=float(args.tolerance),
        targets=targets,
        allow_radan_oracle=bool(args.allow_radan_oracle),
    )
    print(json.dumps(summary, indent=2, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
