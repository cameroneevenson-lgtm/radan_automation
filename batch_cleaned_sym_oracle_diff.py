from __future__ import annotations

import argparse
import csv
import datetime as dt
import difflib
import json
import shutil
import time
from pathlib import Path
from typing import Any

from batch_clean_dxf_diff import _summary_row
from clean_dxf_outer_profile import DEFAULT_SIMPLIFY_TOLERANCE, clean_outer_profile, _tolerance_tag
from compare_ddc_geometry import compare_part
from import_parts_csv_headless import (
    DEFAULT_ORIENTATION,
    DEFAULT_SYNTHETIC_DONOR_SYM,
    UNIT_TO_RADAN,
    _apply_created_symbol_pen_remap,
    _format_elapsed,
    _mac_object,
    _resolve_automation_instance,
    _validate_native_symbol,
    _visible_radan_process_ids,
    _write_native_sym_prototype,
    read_import_csv,
)
from path_safety import assert_w_drive_write_allowed
from radan_com import open_application


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    assert_w_drive_write_allowed(path, operation="write cleaned SYM oracle diff report")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    assert_w_drive_write_allowed(path, operation="write cleaned SYM oracle diff summary")
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys()) if rows else []
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_text_diff(*, radan_sym_path: Path, synthetic_sym_path: Path, diff_path: Path) -> dict[str, Any]:
    assert_w_drive_write_allowed(diff_path, operation="write cleaned SYM oracle text diff")
    diff_path.parent.mkdir(parents=True, exist_ok=True)
    radan_lines = radan_sym_path.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
    synthetic_lines = synthetic_sym_path.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
    diff_lines = list(
        difflib.unified_diff(
            radan_lines,
            synthetic_lines,
            fromfile=str(radan_sym_path),
            tofile=str(synthetic_sym_path),
            n=3,
        )
    )
    diff_path.write_text("".join(diff_lines), encoding="utf-8")
    return {
        "text_diff_path": str(diff_path),
        "text_diff_line_count": len(diff_lines),
        "text_diff_size_bytes": diff_path.stat().st_size,
    }


def _candidate_dxf(
    *,
    source_dxf: Path,
    part_name: str,
    out_dir: Path,
    tolerance: float,
) -> tuple[Path, dict[str, Any]]:
    candidate_path = out_dir / f"{part_name}.dxf"
    report_path = out_dir / f"{part_name}.clean_report.json"
    payload = clean_outer_profile(
        dxf_path=source_dxf,
        out_path=candidate_path,
        report_path=report_path,
        simplify_tolerance=tolerance,
    )
    if not bool(payload.get("wrote_output")):
        candidate_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_dxf, candidate_path)
        payload["fallback_copied_original"] = True
        payload["fallback_reason"] = payload.get("skipped_write_reason") or "cleaner did not produce an output DXF"
        payload["usable_preprocessed_path"] = str(candidate_path)
        payload["report_path"] = str(report_path)
        report_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    else:
        payload["fallback_copied_original"] = False
        payload["usable_preprocessed_path"] = str(candidate_path)
        payload["report_path"] = str(report_path)
    return candidate_path, payload


def _convert_with_radan(
    *,
    app: Any,
    mac: Any,
    dxf_path: Path,
    sym_path: Path,
    part_name: str,
    material: str,
    strategy: str,
    thickness: float,
    unit: str,
) -> dict[str, Any]:
    app.open_symbol(str(dxf_path), read_only=False)
    app.visible = False
    app.interactive = False
    attr_ok = mac.ped_set_attrs2(
        part_name,
        material,
        strategy,
        float(thickness),
        UNIT_TO_RADAN[unit],
        DEFAULT_ORIENTATION,
    )
    app.save_active_document_as(str(sym_path))
    app.close_active_document(True)
    if not sym_path.exists():
        raise FileNotFoundError(str(sym_path))
    return {
        "symbol_path": str(sym_path),
        "symbol_size": sym_path.stat().st_size,
        "attributes_written": bool(attr_ok),
    }


def _convert_with_synthetic(*, dxf_path: Path, sym_path: Path) -> dict[str, Any]:
    if not DEFAULT_SYNTHETIC_DONOR_SYM.exists():
        raise FileNotFoundError(f"Synthetic donor not found: {DEFAULT_SYNTHETIC_DONOR_SYM}")
    payload = _write_native_sym_prototype(
        dxf_path=dxf_path,
        template_sym=DEFAULT_SYNTHETIC_DONOR_SYM,
        out_path=sym_path,
    )
    if not sym_path.exists():
        raise FileNotFoundError(str(sym_path))
    return {
        "symbol_path": str(sym_path),
        "symbol_size": sym_path.stat().st_size,
        "template_sym": str(DEFAULT_SYNTHETIC_DONOR_SYM),
        "entity_count": payload.get("entity_count"),
        "replaced_records": payload.get("replaced_records"),
    }


def run_oracle_diff(
    *,
    csv_path: Path,
    project_folder: Path,
    out_dir: Path | None = None,
    tolerance: float = DEFAULT_SIMPLIFY_TOLERANCE,
    backend: str = "win32com",
    limit: int | None = None,
) -> dict[str, Any]:
    started_at = time.perf_counter()
    parts = read_import_csv(csv_path)
    if limit is not None:
        parts = parts[: max(0, int(limit))]

    tag = _tolerance_tag(tolerance)
    if out_dir is None:
        stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        out_dir = project_folder / "_sym_oracle_diff" / f"cleaned_{stamp}_{tag}"
    assert_w_drive_write_allowed(out_dir, operation="write cleaned SYM oracle diff")
    candidate_dir = out_dir / "candidate_dxfs"
    radan_sym_dir = out_dir / "radan_syms"
    synthetic_sym_dir = out_dir / "synthetic_syms"
    text_diff_dir = out_dir / "text_diffs"
    report_dir = out_dir / "reports"
    for folder in (candidate_dir, radan_sym_dir, synthetic_sym_dir, text_diff_dir, report_dir):
        folder.mkdir(parents=True, exist_ok=True)

    preexisting_visible = _visible_radan_process_ids()
    if preexisting_visible:
        raise RuntimeError(
            "Visible RADAN sessions are open; refusing oracle diff so user sessions are not disturbed. "
            + ", ".join(str(pid) for pid in sorted(preexisting_visible))
        )

    app = None
    rows: list[dict[str, Any]] = []
    part_payloads: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    try:
        app = open_application(backend=backend, force_new_instance=True)
        info, should_quit = _resolve_automation_instance(app, preexisting_visible, _StdoutLogger())
        app.visible = False
        app.interactive = False
        mac = _mac_object(app)

        for index, part in enumerate(parts, start=1):
            part_started = time.perf_counter()
            part_name = part.part_name
            candidate_path = candidate_dir / f"{part_name}.dxf"
            radan_sym_path = radan_sym_dir / f"{part_name}.sym"
            synthetic_sym_path = synthetic_sym_dir / f"{part_name}.sym"
            text_diff_path = text_diff_dir / f"{part_name}.radan_vs_synthetic.diff"
            row: dict[str, Any] = {
                "part": part_name,
                "source_dxf": str(part.dxf_path),
                "candidate_dxf": str(candidate_path),
                "radan_sym": str(radan_sym_path),
                "synthetic_sym": str(synthetic_sym_path),
                "text_diff": str(text_diff_path),
                "status": "ok",
            }
            try:
                candidate_path, clean_payload = _candidate_dxf(
                    source_dxf=part.dxf_path,
                    part_name=part_name,
                    out_dir=candidate_dir,
                    tolerance=tolerance,
                )
                clean_row = _summary_row(part_name, clean_payload, original_path=part.dxf_path, cleaned_path=candidate_path)
                row.update({f"clean_{key}": value for key, value in clean_row.items() if key not in {"part"}})

                radan_payload = _convert_with_radan(
                    app=app,
                    mac=mac,
                    dxf_path=candidate_path,
                    sym_path=radan_sym_path,
                    part_name=part_name,
                    material=part.material,
                    strategy=part.strategy,
                    thickness=part.thickness,
                    unit=part.unit,
                )
                radan_remap = _apply_created_symbol_pen_remap(radan_sym_path, _StdoutLogger(prefix=f"{part_name} RADAN"))

                synthetic_payload = _convert_with_synthetic(dxf_path=candidate_path, sym_path=synthetic_sym_path)
                synthetic_validation = _validate_native_symbol(dxf_path=candidate_path, sym_path=synthetic_sym_path)
                synthetic_remap = _apply_created_symbol_pen_remap(
                    synthetic_sym_path,
                    _StdoutLogger(prefix=f"{part_name} SYNTH"),
                )

                diff_payload = compare_part(candidate_path, radan_sym_path, synthetic_sym_path, top=5)
                text_diff_payload = _write_text_diff(
                    radan_sym_path=radan_sym_path,
                    synthetic_sym_path=synthetic_sym_path,
                    diff_path=text_diff_path,
                )
                part_report = report_dir / f"{part_name}.oracle_diff.json"
                _write_json(
                    part_report,
                    {
                        "part": part_name,
                        "clean": clean_payload,
                        "radan": {**radan_payload, "pen_remap": radan_remap},
                        "synthetic": {
                            **synthetic_payload,
                            "validation": synthetic_validation,
                            "pen_remap": synthetic_remap,
                        },
                        "diff": diff_payload,
                        "text_diff": text_diff_payload,
                    },
                )
                row.update(
                    {
                        "clean_status": clean_row["status"],
                        "clean_removed_vertices": clean_row["removed_vertices"],
                        "radan_size_bytes": radan_sym_path.stat().st_size,
                        "synthetic_size_bytes": synthetic_sym_path.stat().st_size,
                        "synthetic_validation_passed": bool(synthetic_validation.get("passed")),
                        "ddc_records": diff_payload["dxf_count"],
                        "changed_geometry_records": diff_payload["changed_geometry_records"],
                        "changed_token_records": diff_payload["changed_token_records"],
                        "total_slots": diff_payload["total_slots"],
                        "token_match_slots": diff_payload["token_match_slots"],
                        "token_match_ratio": diff_payload["token_match_slots"] / diff_payload["total_slots"]
                        if diff_payload["total_slots"]
                        else 0.0,
                        "decoded_nonzero_diff_slots": diff_payload["decoded_nonzero_diff_slots"],
                        "max_abs_diff": diff_payload["max_abs_diff"],
                        "text_diff_line_count": text_diff_payload["text_diff_line_count"],
                        "text_diff_size_bytes": text_diff_payload["text_diff_size_bytes"],
                        "part_report": str(part_report),
                        "elapsed_sec": round(time.perf_counter() - part_started, 3),
                    }
                )
                part_payloads.append(diff_payload)
            except Exception as exc:
                row["status"] = "error"
                row["error"] = f"{type(exc).__name__}: {exc}"
                errors.append({"part": part_name, "error": row["error"]})
            rows.append(row)
            print(
                f"[{dt.datetime.now().strftime('%H:%M:%S')}] "
                f"{index}/{len(parts)} {part_name}: {row['status']} ({_format_elapsed(time.perf_counter() - part_started)})",
                flush=True,
            )

        if should_quit:
            try:
                app.quit()
            except Exception:
                pass
    finally:
        if app is not None:
            try:
                app.close()
            except Exception:
                pass

    summary_csv = out_dir / "cleaned_sym_oracle_diff_summary.csv"
    _write_csv(summary_csv, rows)

    total_records = sum(int(part.get("dxf_count", 0)) for part in part_payloads)
    total_slots = sum(int(part.get("total_slots", 0)) for part in part_payloads)
    token_match_slots = sum(int(part.get("token_match_slots", 0)) for part in part_payloads)
    payload = {
        "csv_path": str(csv_path),
        "project_folder": str(project_folder),
        "out_dir": str(out_dir),
        "candidate_dxf_folder": str(candidate_dir),
        "radan_sym_folder": str(radan_sym_dir),
        "synthetic_sym_folder": str(synthetic_sym_dir),
        "text_diff_folder": str(text_diff_dir),
        "summary_csv": str(summary_csv),
        "part_count": len(parts),
        "ok_count": sum(1 for row in rows if row.get("status") == "ok"),
        "error_count": len(errors),
        "errors": errors,
        "total_dxf_records": total_records,
        "changed_geometry_records": sum(int(part.get("changed_geometry_records", 0)) for part in part_payloads),
        "changed_token_records": sum(int(part.get("changed_token_records", 0)) for part in part_payloads),
        "total_slots": total_slots,
        "token_match_slots": token_match_slots,
        "token_match_ratio": token_match_slots / total_slots if total_slots else 0.0,
        "decoded_nonzero_diff_slots": sum(int(part.get("decoded_nonzero_diff_slots", 0)) for part in part_payloads),
        "max_abs_diff": max((float(part.get("max_abs_diff", 0.0)) for part in part_payloads), default=0.0),
        "worst_parts_by_changed_geometry": sorted(
            rows,
            key=lambda row: int(row.get("changed_geometry_records") or 0),
            reverse=True,
        )[:20],
        "elapsed_sec": round(time.perf_counter() - started_at, 3),
    }
    summary_json = out_dir / "cleaned_sym_oracle_diff_summary.json"
    _write_json(summary_json, payload)
    payload["summary_json"] = str(summary_json)
    return payload


class _StdoutLogger:
    def __init__(self, prefix: str = "") -> None:
        self.prefix = prefix

    def write(self, message: str) -> None:
        prefix = f"{self.prefix}: " if self.prefix else ""
        print(f"[{dt.datetime.now().strftime('%H:%M:%S')}] {prefix}{message}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Create RADAN and synthetic SYMs from cleaned DXFs and compare them.")
    parser.add_argument("--csv", type=Path, required=True)
    parser.add_argument("--project-folder", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path)
    parser.add_argument("--tolerance", type=float, default=0.002)
    parser.add_argument("--backend", default="win32com")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()

    payload = run_oracle_diff(
        csv_path=args.csv,
        project_folder=args.project_folder,
        out_dir=args.out_dir,
        tolerance=args.tolerance,
        backend=args.backend,
        limit=args.limit,
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["error_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
