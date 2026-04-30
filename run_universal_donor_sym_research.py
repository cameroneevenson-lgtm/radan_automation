from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from copied_project_nester_gate import (
    DEFAULT_OVERSIZED_EXCLUDES,
    assert_lab_output_path,
    list_radan_processes,
    run_gate,
    sanitize_label,
    select_parts,
)
from ddc_corpus import DDC_RE, read_ddc_records, read_dxf_entities
from ddc_number_codec import decode_ddc_number
from import_parts_csv_headless import read_import_csv
from validate_native_sym import validate_native_sym
from write_native_sym_prototype import _rows_with_topology_snapped_endpoints, write_native_prototype


DEFAULT_DONOR_SYM = Path(__file__).resolve().parent / "donor.sym"
DEFAULT_LAB_ROOT = Path(__file__).resolve().parent / "_sym_lab"
DEFAULT_SOURCE_RPD = Path(
    r"L:\BATTLESHIELD\F-LARGE FLEET\F54410\PAINT PACK\F54410 PAINT PACK\F54410 PAINT PACK.rpd"
)
TEMPLATE_SOURCE = "universal_donor"
DEFAULT_WRITER_OPTIONS: dict[str, Any] = {
    "coordinate_digits": None,
    "source_coordinate_digits": 6,
    "source_coordinate_entity_types": None,
    "canonicalize_endpoints": True,
    "topology_snap_endpoints": True,
    "order_connected_line_profiles": True,
    "rotate_connected_line_profile_start": False,
    "normalize_collinear_line_chains": False,
    "normalize_collinear_boundary_chains": False,
    "collinear_endpoint_tolerance": 1e-6,
    "collinear_deviation_tolerance": 1e-8,
}

LADDER_RUNGS: dict[str, dict[str, Any]] = {
    "b10": {"include_parts": ("B-10",), "label_suffix": "b10"},
    "b14": {"include_parts": ("B-14",), "label_suffix": "b14"},
    "b49": {"include_parts": ("F54410-B-49",), "label_suffix": "b49"},
    "canary3": {"include_parts": ("B-14", "B-17", "F54410-B-49"), "label_suffix": "canary3"},
    "hard7": {
        "include_parts": (
            "B-14",
            "B-17",
            "B-27",
            "B-30",
            "F54410-B-49",
            "F54410-B-12",
            "F54410-B-27",
        ),
        "label_suffix": "hard7",
    },
    "arc_stress": {
        "include_parts": ("B-27", "B-28", "B-30", "F54410-B-41", "F54410-B-02", "F54410-B-35"),
        "label_suffix": "arc_stress",
    },
    "first10": {"max_parts": 10, "label_suffix": "first10"},
    "quarter25": {"max_parts": 25, "label_suffix": "quarter25"},
    "half49": {"max_parts": 49, "label_suffix": "half49"},
    "proven95": {
        "exclude_parts": DEFAULT_OVERSIZED_EXCLUDES,
        "label_suffix": "proven95",
    },
}

ATTR_VALUE_RE_TEMPLATE = r'(<Attr\b(?=[^>]*\bnum="{attr_num}")[^>]*\bvalue=)(["\'])(.*?)(\2)'


def timestamp() -> str:
    return dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def _resolve_lab_path(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    assert_lab_output_path(resolved, lab_root=DEFAULT_LAB_ROOT, operation="write universal donor research output")
    return resolved


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    _resolve_lab_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.tmp")
    temp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True) + "\n", encoding="utf-8")
    temp_path.replace(path)


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    _resolve_lab_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row})
    temp_path = path.with_name(f"{path.name}.tmp")
    with temp_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    temp_path.replace(path)


def _write_text(path: Path, text: str) -> None:
    _resolve_lab_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.tmp")
    temp_path.write_text(text, encoding="utf-8")
    temp_path.replace(path)


def _attr_value(text: str, attr_num: str) -> str | None:
    pattern = re.compile(ATTR_VALUE_RE_TEMPLATE.format(attr_num=re.escape(str(attr_num))), re.DOTALL)
    match = pattern.search(text)
    if match is None:
        return None
    return str(match.group(3))


def _replace_attr_value(text: str, attr_num: str, value: str) -> tuple[str, bool]:
    pattern = re.compile(ATTR_VALUE_RE_TEMPLATE.format(attr_num=re.escape(str(attr_num))), re.DOTALL)
    changed = False

    def replace(match: re.Match[str]) -> str:
        nonlocal changed
        changed = True
        return f"{match.group(1)}{match.group(2)}{value}{match.group(4)}"

    return pattern.sub(replace, text), changed


def _format_thickness(value: float) -> str:
    return f"{float(value):.9f}".rstrip("0").rstrip(".")


def _write_symbol_text(path: Path, text: str) -> None:
    _resolve_lab_path(path)
    temp_path = path.with_name(f"{path.name}.tmp")
    temp_path.write_text(text, encoding="utf-8")
    temp_path.replace(path)


def refresh_generated_symbol_bom_metadata(path: Path, part: Any) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="replace")
    requested = {
        "119": str(part.material),
        "120": _format_thickness(float(part.thickness)),
        "121": str(part.unit),
        "146": str(part.strategy),
    }
    refreshed = text
    updated: dict[str, bool] = {}
    for attr_num, value in requested.items():
        refreshed, updated[attr_num] = _replace_attr_value(refreshed, attr_num, value)
    if refreshed != text:
        _write_symbol_text(path, refreshed)
    return {
        "requested": requested,
        "updated": updated,
        "all_present": all(updated.values()),
    }


def _decode_token(token: str) -> float:
    return 0.0 if not token else float(decode_ddc_number(token))


def _segment_key(start: tuple[float, float], end: tuple[float, float], *, digits: int = 5) -> tuple[tuple[float, float], ...]:
    a = (round(float(start[0]), digits), round(float(start[1]), digits))
    b = (round(float(end[0]), digits), round(float(end[1]), digits))
    return tuple(sorted((a, b)))


def unordered_line_geometry_check(*, dxf_path: Path, sym_path: Path) -> dict[str, Any]:
    dxf_rows, bounds = read_dxf_entities(dxf_path)
    if any(str(row.get("type")) != "LINE" for row in dxf_rows):
        return {"eligible": False, "passed": False, "reason": "non_line_dxf_rows"}
    dxf_rows = _rows_with_topology_snapped_endpoints(dxf_rows, bounds, digits=6)
    ddc_rows = read_ddc_records(sym_path)
    if any(str(row.get("record")) != "G" for row in ddc_rows):
        return {"eligible": False, "passed": False, "reason": "non_line_ddc_rows"}
    dxf_segments = Counter(
        _segment_key(tuple(row["normalized_start"]), tuple(row["normalized_end"])) for row in dxf_rows
    )
    ddc_segments = Counter()
    for row in ddc_rows:
        tokens = list(row.get("tokens") or [])
        start = (_decode_token(tokens[0] if len(tokens) > 0 else ""), _decode_token(tokens[1] if len(tokens) > 1 else ""))
        end = (
            start[0] + _decode_token(tokens[2] if len(tokens) > 2 else ""),
            start[1] + _decode_token(tokens[3] if len(tokens) > 3 else ""),
        )
        ddc_segments[_segment_key(start, end)] += 1
    missing = dxf_segments - ddc_segments
    extra = ddc_segments - dxf_segments
    return {
        "eligible": True,
        "passed": not missing and not extra,
        "dxf_segment_count": sum(dxf_segments.values()),
        "ddc_segment_count": sum(ddc_segments.values()),
        "missing_count": sum(missing.values()),
        "extra_count": sum(extra.values()),
    }


def _ddc_record_counts(text: str) -> dict[str, int]:
    match = DDC_RE.search(text)
    if match is None:
        return {}
    counter: Counter[str] = Counter()
    for raw_line in match.group(1).splitlines():
        line = raw_line.strip()
        if not line:
            continue
        counter[line.split(",", 1)[0]] += 1
    return dict(sorted(counter.items()))


def inspect_symbol(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="replace")
    counts = _ddc_record_counts(text)
    return {
        "path": str(path),
        "exists": path.exists(),
        "size": path.stat().st_size if path.exists() else 0,
        "attr_110": _attr_value(text, "110"),
        "attr_165": _attr_value(text, "165"),
        "attr_166": _attr_value(text, "166"),
        "ddc_record_counts": counts,
        "geometry_record_count": int(counts.get("G", 0)) + int(counts.get("H", 0)),
    }


def inspect_donor(donor_sym: Path) -> dict[str, Any]:
    if not donor_sym.exists():
        raise FileNotFoundError(f"Universal donor SYM not found: {donor_sym}")
    return inspect_symbol(donor_sym)


def ensure_blank_universal_donor(donor_sym: Path) -> dict[str, Any]:
    donor = inspect_donor(donor_sym)
    counts = donor["ddc_record_counts"]
    if not counts:
        raise RuntimeError(f"Universal donor has no DDC block: {donor_sym}")
    if int(counts.get("G", 0)) or int(counts.get("H", 0)):
        raise RuntimeError(
            "Universal donor must be a blank-style donor with no G/H geometry records; "
            f"found G={counts.get('G', 0)} H={counts.get('H', 0)} in {donor_sym}"
        )
    return donor


def _generation_row_ok(row: dict[str, Any]) -> bool:
    geometry_passed = bool(row.get("validation_passed")) or bool(
        (row.get("unordered_line_geometry") or {}).get("passed")
    )
    normalization = row.get("collinear_normalization") or {}
    if normalization.get("enabled"):
        geometry_passed = "validation_tiers" in row
    return (
        bool(row.get("write_ok"))
        and geometry_passed
        and not bool(row.get("retained_donor_attr_110"))
        and int(row.get("generated_geometry_records", 0)) > 0
    )


def _normal_writer_options(writer_options: dict[str, Any] | None = None) -> dict[str, Any]:
    options = dict(DEFAULT_WRITER_OPTIONS)
    if writer_options:
        options.update(writer_options)
    entity_types = options.get("source_coordinate_entity_types")
    if entity_types is not None:
        options["source_coordinate_entity_types"] = sorted(str(value) for value in entity_types)
    return options


def _writer_entity_types(options: dict[str, Any]) -> set[str] | None:
    entity_types = options.get("source_coordinate_entity_types")
    if entity_types is None:
        return None
    return {str(value) for value in entity_types}


def generate_donor_symbol(
    *,
    part: Any,
    donor_sym: Path,
    symbol_dir: Path,
    writer_options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    _resolve_lab_path(symbol_dir)
    out_path = part.symbol_path(symbol_dir)
    _resolve_lab_path(out_path)
    options = _normal_writer_options(writer_options)
    row: dict[str, Any] = {
        "part": part.part_name,
        "dxf_path": str(part.dxf_path),
        "output_sym": str(out_path),
        "template_source": TEMPLATE_SOURCE,
        "template_sym": str(donor_sym),
        "writer_options": options,
    }
    try:
        payload = write_native_prototype(
            dxf_path=part.dxf_path,
            template_sym=donor_sym,
            out_path=out_path,
            allow_outside_lab=True,
            coordinate_digits=options["coordinate_digits"],
            source_coordinate_digits=options["source_coordinate_digits"],
            source_coordinate_entity_types=_writer_entity_types(options),
            topology_snap_endpoints=bool(options["topology_snap_endpoints"]),
            canonicalize_endpoints=bool(options["canonicalize_endpoints"]),
            order_connected_line_profiles=bool(options["order_connected_line_profiles"]),
            rotate_connected_line_profile_start=bool(options["rotate_connected_line_profile_start"]),
            normalize_collinear_line_chains_enabled=bool(options["normalize_collinear_line_chains"]),
            normalize_collinear_boundary_chains_enabled=bool(options["normalize_collinear_boundary_chains"]),
            collinear_endpoint_tolerance=float(options["collinear_endpoint_tolerance"]),
            collinear_deviation_tolerance=float(options["collinear_deviation_tolerance"]),
        )
        bom_metadata = refresh_generated_symbol_bom_metadata(out_path, part)
        validation = validate_native_sym(dxf_path=part.dxf_path, sym_path=out_path)
        unordered_geometry = unordered_line_geometry_check(dxf_path=part.dxf_path, sym_path=out_path)
        facts = inspect_symbol(out_path)
        row.update(
            {
                "write_ok": True,
                "bom_metadata": bom_metadata,
                "line_profile_ordering": payload["line_profile_ordering"],
                "source_entity_count": payload["source_entity_count"],
                "entity_count": payload["entity_count"],
                "replaced_records": payload["replaced_records"],
                "collinear_normalization": payload["collinear_normalization"],
                "validation_passed": bool(validation["passed"]),
                "unordered_line_geometry": unordered_geometry,
                "validation_tiers": validation["tiers"],
                "output_attr_110": facts["attr_110"],
                "output_attr_165": facts["attr_165"],
                "output_attr_166": facts["attr_166"],
                "generated_geometry_records": facts["geometry_record_count"],
                "output_ddc_record_counts": facts["ddc_record_counts"],
                "retained_donor_attr_110": facts["attr_110"] == "donor",
            }
        )
    except Exception as exc:
        row.update({"write_ok": False, "error": f"{type(exc).__name__}: {exc}"})
    row["ok"] = _generation_row_ok(row)
    return row


def apply_ladder_rung(
    rung: str | None,
    *,
    label: str,
    include_parts: Iterable[str],
    exclude_parts: Iterable[str],
    max_parts: int | None,
) -> dict[str, Any]:
    requested_includes = tuple(include_parts)
    requested_excludes = tuple(exclude_parts)
    resolved: dict[str, Any] = {
        "label": label,
        "include_parts": requested_includes,
        "exclude_parts": requested_excludes,
        "max_parts": max_parts,
        "ladder_rung": rung,
    }
    if not rung:
        return resolved
    if rung not in LADDER_RUNGS:
        raise ValueError(f"Unknown ladder rung {rung!r}; choose one of {', '.join(sorted(LADDER_RUNGS))}.")
    spec = LADDER_RUNGS[rung]
    if requested_includes or requested_excludes or max_parts is not None:
        raise ValueError("--ladder-rung cannot be combined with --part, --exclude, or --max-parts.")
    resolved["include_parts"] = tuple(spec.get("include_parts", ()))
    resolved["exclude_parts"] = tuple(spec.get("exclude_parts", ()))
    resolved["max_parts"] = spec.get("max_parts")
    resolved["label"] = f"{label}_{spec['label_suffix']}"
    return resolved


def generate_symbols_from_universal_donor(
    *,
    csv_path: Path,
    donor_sym: Path,
    out_dir: Path,
    include_parts: Iterable[str] = (),
    exclude_parts: Iterable[str] = (),
    max_parts: int | None = None,
    label: str = "universal_donor",
    writer_options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    out_dir = _resolve_lab_path(out_dir)
    symbol_dir = _resolve_lab_path(out_dir / "symbols")
    out_dir.mkdir(parents=True, exist_ok=True)
    donor_sym = donor_sym.expanduser().resolve()
    donor = ensure_blank_universal_donor(donor_sym)
    all_parts = read_import_csv(csv_path)
    selected_parts, missing_in_csv = select_parts(
        all_parts,
        include_parts=include_parts,
        exclude_parts=exclude_parts,
        max_parts=max_parts,
    )
    if missing_in_csv:
        raise RuntimeError(f"Requested part(s) missing from CSV: {', '.join(missing_in_csv)}")
    if not selected_parts:
        raise RuntimeError("No parts selected for universal donor generation.")

    options = _normal_writer_options(writer_options)
    rows = [
        generate_donor_symbol(part=part, donor_sym=donor_sym, symbol_dir=symbol_dir, writer_options=options)
        for part in selected_parts
    ]
    failures = [row for row in rows if not row.get("ok")]
    payload: dict[str, Any] = {
        "schema_version": 1,
        "label": sanitize_label(label),
        "csv_path": str(csv_path),
        "out_dir": str(out_dir),
        "symbol_dir": str(symbol_dir),
        "donor": donor,
        "template_source": TEMPLATE_SOURCE,
        "writer_options": options,
        "include_parts": list(include_parts),
        "exclude_parts": list(exclude_parts),
        "max_parts": max_parts,
        "selected_part_count": len(selected_parts),
        "selected_parts": [part.part_name for part in selected_parts],
        "missing_in_csv": missing_in_csv,
        "generated_count": len(rows),
        "passed_count": len(rows) - len(failures),
        "failed_count": len(failures),
        "rows": rows,
        "ok": not failures,
    }
    collinear_rows = [
        {
            "part": row.get("part"),
            "dxf_path": row.get("dxf_path"),
            "output_sym": row.get("output_sym"),
            "normalization": row.get("collinear_normalization"),
        }
        for row in rows
        if (row.get("collinear_normalization") or {}).get("enabled")
    ]
    if collinear_rows:
        _write_json(
            out_dir / "collinear_normalization_manifest.json",
            {
                "schema_version": 1,
                "label": sanitize_label(label),
                "csv_path": str(csv_path),
                "symbol_dir": str(symbol_dir),
                "writer_options": options,
                "parts": collinear_rows,
            },
        )
    _write_json(out_dir / "manifest.json", payload)
    _write_csv(out_dir / "manifest.csv", rows)
    return payload


def _process_log_payload(stage: str) -> dict[str, Any]:
    return {"stage": stage, "timestamp": dt.datetime.now().isoformat(timespec="seconds"), "processes": list_radan_processes()}


def write_summary(out_dir: Path, payload: dict[str, Any]) -> None:
    generation = payload["generation"]
    donor = generation["donor"]
    lines = [
        "# Universal Donor SYM Research",
        "",
        f"- Label: `{payload['label']}`",
        f"- OK: `{payload['ok']}`",
        f"- CSV: `{generation['csv_path']}`",
        f"- Donor: `{donor['path']}`",
        f"- Symbol folder: `{generation['symbol_dir']}`",
        f"- Template source: `{generation['template_source']}`",
        f"- Writer options: `{generation.get('writer_options')}`",
        f"- Selected parts: `{generation['selected_part_count']}`",
        f"- Generated/pass/fail: `{generation['generated_count']}` / `{generation['passed_count']}` / `{generation['failed_count']}`",
        f"- Donor Attr 110: `{donor.get('attr_110')}`",
        f"- Donor DDC counts: `{donor.get('ddc_record_counts')}`",
        "",
        "## Candidate Table",
        "",
        "| Part | OK | Source entities | Output rows | G/H records | Attr 110 | Validation | Merges | Notes |",
        "| --- | ---: | ---: | ---: | ---: | --- | ---: | ---: | --- |",
    ]
    for row in generation["rows"]:
        notes = row.get("error", "")
        if row.get("retained_donor_attr_110"):
            notes = (notes + " retained donor Attr 110").strip()
        normalization = row.get("collinear_normalization") or {}
        lines.append(
            "| {part} | {ok} | {source_entities} | {entities} | {records} | {attr110} | {validation} | {merges} | {notes} |".format(
                part=row.get("part", ""),
                ok=str(bool(row.get("ok"))),
                source_entities=row.get("source_entity_count", row.get("entity_count", "")),
                entities=row.get("entity_count", ""),
                records=row.get("generated_geometry_records", ""),
                attr110=row.get("output_attr_110", ""),
                validation=str(bool(row.get("validation_passed"))),
                merges=normalization.get("accepted_merge_count", ""),
                notes=str(notes).replace("|", "\\|"),
            )
        )
    nester = payload.get("nester")
    if nester:
        lines.extend(
            [
                "",
                "## Nester Gate",
                "",
                f"- Run: `{nester.get('out_dir')}`",
                f"- OK: `{nester.get('ok')}`",
                f"- Project: `{nester.get('project_path')}`",
                f"- Part rows: `{nester.get('after', {}).get('part_count')}`",
                f"- Sheet rows: `{nester.get('after', {}).get('sheet_count')}`",
                f"- Nest rows: `{nester.get('after', {}).get('nest_count')}`",
                f"- Made nonzero count: `{nester.get('after', {}).get('made_nonzero_count')}`",
                f"- NextNestNum: `{nester.get('after', {}).get('next_nest_num')}`",
                f"- DRG count: `{nester.get('drg_count')}`",
                f"- Report status: `{nester.get('reports')}`",
            ]
        )
    else:
        lines.extend(["", "## Nester Gate", "", "- Not requested or skipped."])
    lines.append("")
    _write_text(out_dir / "UNIVERSAL_DONOR_RESEARCH_SUMMARY.md", "\n".join(lines))


def run_research(
    *,
    csv_path: Path,
    out_dir: Path,
    donor_sym: Path = DEFAULT_DONOR_SYM,
    source_rpd: Path | None = None,
    label: str = "universal_donor",
    include_parts: Iterable[str] = (),
    exclude_parts: Iterable[str] = (),
    max_parts: int | None = None,
    run_nester_gate: bool = False,
    backend: str = "win32com",
    kill_existing_radan: bool = False,
    attempt_reports: bool = False,
    finish_nesting_before_reports: bool = False,
    writer_options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    out_dir = _resolve_lab_path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    safe_label = sanitize_label(label)
    _write_json(out_dir / "radan_processes_before_generation.json", _process_log_payload("before_generation"))
    generation = generate_symbols_from_universal_donor(
        csv_path=csv_path.expanduser().resolve(),
        donor_sym=donor_sym,
        out_dir=out_dir,
        include_parts=include_parts,
        exclude_parts=exclude_parts,
        max_parts=max_parts,
        label=safe_label,
        writer_options=writer_options,
    )
    _write_json(out_dir / "radan_processes_after_generation.json", _process_log_payload("after_generation"))
    payload: dict[str, Any] = {
        "schema_version": 1,
        "label": safe_label,
        "out_dir": str(out_dir),
        "generation": generation,
        "nester": None,
        "ok": bool(generation["ok"]),
    }
    if run_nester_gate:
        if source_rpd is None:
            raise RuntimeError("--source-rpd is required with --run-nester.")
        if not generation["ok"]:
            payload["nester"] = {"skipped": True, "reason": "generation_failed"}
            payload["ok"] = False
        else:
            nester_out = _resolve_lab_path(out_dir / f"nester_{safe_label}")
            payload["nester"] = run_gate(
                source_rpd=source_rpd.expanduser().resolve(),
                csv_path=csv_path.expanduser().resolve(),
                symbol_folder=Path(generation["symbol_dir"]).expanduser().resolve(),
                out_dir=nester_out,
                label=safe_label,
                include_parts=include_parts,
                exclude_parts=exclude_parts,
                max_parts=max_parts,
                backend=backend,
                kill_existing_radan=kill_existing_radan,
                attempt_reports=attempt_reports,
                finish_nesting_before_reports=finish_nesting_before_reports,
            )
            payload["ok"] = bool(generation["ok"]) and bool(payload["nester"].get("ok"))
    _write_json(out_dir / "result.json", payload)
    write_summary(out_dir, payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate and validate RADAN SYMs from one universal donor template.")
    parser.add_argument("--csv", type=Path, required=True, help="DXF/BOM CSV in the RADAN import format.")
    parser.add_argument("--out-dir", type=Path, help="Lab output folder under _sym_lab.")
    parser.add_argument("--donor-sym", type=Path, default=DEFAULT_DONOR_SYM)
    parser.add_argument("--source-rpd", type=Path, default=DEFAULT_SOURCE_RPD)
    parser.add_argument("--label", default="universal_donor")
    parser.add_argument("--part", action="append", default=[], help="Part name to include. Defaults to all CSV rows.")
    parser.add_argument("--exclude", action="append", default=[], help="Part name to exclude.")
    parser.add_argument("--include-default-oversized-excludes", action="store_true")
    parser.add_argument("--max-parts", type=int)
    parser.add_argument("--ladder-rung", choices=sorted(LADDER_RUNGS))
    parser.add_argument("--run-nester", action="store_true")
    parser.add_argument("--backend", default="win32com")
    parser.add_argument("--kill-existing-radan", action="store_true")
    parser.add_argument("--attempt-reports", action="store_true")
    parser.add_argument("--finish-nesting-before-reports", action="store_true")
    parser.add_argument(
        "--coordinate-digits",
        type=int,
        help="Lab option passed to the donor writer: round normalized DXF coordinates before encoding.",
    )
    parser.add_argument(
        "--source-coordinate-digits",
        type=int,
        default=6,
        help="Lab option passed to the donor writer. Defaults to the current donor harness behavior.",
    )
    parser.add_argument(
        "--no-source-coordinate-digits",
        action="store_true",
        help="Disable source-coordinate rounding before normalization.",
    )
    parser.add_argument(
        "--source-coordinate-entity-type",
        action="append",
        choices=["LINE", "ARC", "CIRCLE"],
        help="Limit source-coordinate rounding to one or more DXF entity types.",
    )
    parser.add_argument(
        "--no-topology-snap-endpoints",
        action="store_true",
        help="Disable endpoint topology snapping in the donor writer.",
    )
    parser.add_argument(
        "--no-canonicalize-endpoints",
        action="store_true",
        help="Disable endpoint-fraction canonicalization in the donor writer.",
    )
    parser.add_argument(
        "--no-order-connected-line-profiles",
        action="store_true",
        help="Disable connected line-profile ordering in the donor writer.",
    )
    parser.add_argument(
        "--rotate-connected-line-profile-start",
        action="store_true",
        help="Rotate a closed connected line profile to the lowest-Y/rightmost start point.",
    )
    parser.add_argument(
        "--normalize-collinear-line-chains",
        action="store_true",
        help="Lab-only: merge adjacent same-layer/same-pen collinear LINE fragments before DDC generation.",
    )
    parser.add_argument(
        "--normalize-collinear-boundary-chains",
        action="store_true",
        help="Lab-only: merge same-axis boundary-style LINE fragments before DDC generation.",
    )
    parser.add_argument(
        "--collinear-endpoint-tolerance",
        type=float,
        default=1e-6,
        help="Endpoint tolerance for --normalize-collinear-line-chains.",
    )
    parser.add_argument(
        "--collinear-deviation-tolerance",
        type=float,
        default=1e-8,
        help="Perpendicular deviation tolerance for --normalize-collinear-line-chains.",
    )
    args = parser.parse_args()

    excludes = list(args.exclude)
    if args.include_default_oversized_excludes:
        excludes.extend(DEFAULT_OVERSIZED_EXCLUDES)
    resolved = apply_ladder_rung(
        args.ladder_rung,
        label=args.label,
        include_parts=args.part,
        exclude_parts=excludes,
        max_parts=args.max_parts,
    )
    out_dir = args.out_dir
    if out_dir is None:
        out_dir = DEFAULT_LAB_ROOT / f"universal_donor_sym_research_{timestamp()}_{sanitize_label(resolved['label'])}"
    writer_options = {
        "coordinate_digits": args.coordinate_digits,
        "source_coordinate_digits": None if args.no_source_coordinate_digits else args.source_coordinate_digits,
        "source_coordinate_entity_types": args.source_coordinate_entity_type,
        "topology_snap_endpoints": not bool(args.no_topology_snap_endpoints),
        "canonicalize_endpoints": not bool(args.no_canonicalize_endpoints),
        "order_connected_line_profiles": not bool(args.no_order_connected_line_profiles),
        "rotate_connected_line_profile_start": bool(args.rotate_connected_line_profile_start),
        "normalize_collinear_line_chains": bool(args.normalize_collinear_line_chains),
        "normalize_collinear_boundary_chains": bool(args.normalize_collinear_boundary_chains),
        "collinear_endpoint_tolerance": float(args.collinear_endpoint_tolerance),
        "collinear_deviation_tolerance": float(args.collinear_deviation_tolerance),
    }
    payload = run_research(
        csv_path=args.csv,
        out_dir=out_dir,
        donor_sym=args.donor_sym,
        source_rpd=args.source_rpd,
        label=resolved["label"],
        include_parts=resolved["include_parts"],
        exclude_parts=resolved["exclude_parts"],
        max_parts=resolved["max_parts"],
        run_nester_gate=args.run_nester,
        backend=str(args.backend),
        kill_existing_radan=bool(args.kill_existing_radan),
        attempt_reports=bool(args.attempt_reports),
        finish_nesting_before_reports=bool(args.finish_nesting_before_reports),
        writer_options=writer_options,
    )
    print(json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
