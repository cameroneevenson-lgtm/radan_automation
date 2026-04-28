from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path
from typing import Any

from clean_dxf_outer_profile import DEFAULT_SIMPLIFY_TOLERANCE, clean_outer_profile, _tolerance_tag
from import_parts_csv_headless import read_import_csv
from path_safety import assert_w_drive_write_allowed


def _safe_part_stem(value: str) -> str:
    return "".join(character if character.isalnum() or character in {"-", "_", " "} else "_" for character in value).strip()


def _summary_row(part_name: str, payload: dict[str, Any], *, original_path: Path, cleaned_path: Path) -> dict[str, Any]:
    simplification = payload.get("simplification", {})
    skipped_reason = str(payload.get("skipped_write_reason") or "")
    wrote_output = bool(payload.get("wrote_output"))
    removed_vertices = int(simplification.get("removed_vertices", 0) or 0)
    if wrote_output and removed_vertices > 0:
        status = "cleaned_changed"
    elif wrote_output:
        status = "cleaned_no_geometry_change"
    elif skipped_reason:
        status = "skipped"
    else:
        status = "not_written"

    return {
        "part": part_name,
        "status": status,
        "wrote_output": wrote_output,
        "skipped_reason": skipped_reason,
        "source_dxf": str(original_path),
        "cleaned_dxf": str(cleaned_path) if wrote_output else "",
        "original_size_bytes": original_path.stat().st_size if original_path.exists() else "",
        "cleaned_size_bytes": cleaned_path.stat().st_size if wrote_output and cleaned_path.exists() else "",
        "profile_entity_count": payload.get("profile_entity_count", ""),
        "loop_count": payload.get("loop_count", ""),
        "outside_entity_count": payload.get("selected_outside_entity_count", ""),
        "outside_entity_types": "|".join(str(value) for value in payload.get("selected_outside_entity_types", [])),
        "input_vertices": simplification.get("input_vertices", ""),
        "output_vertices": simplification.get("output_vertices", ""),
        "removed_vertices": removed_vertices,
        "max_removed_local_deviation": simplification.get("max_removed_local_deviation", ""),
        "max_final_vertex_deviation": simplification.get("max_final_vertex_deviation", ""),
        "area_before_abs": simplification.get("area_before_abs", ""),
        "area_after_abs": simplification.get("area_after_abs", ""),
        "area_delta_abs": simplification.get("area_delta_abs", ""),
    }


def run_batch_diff(
    *,
    csv_path: Path,
    project_folder: Path,
    out_dir: Path | None = None,
    tolerance: float = DEFAULT_SIMPLIFY_TOLERANCE,
) -> dict[str, Any]:
    parts = read_import_csv(csv_path)
    tag = _tolerance_tag(tolerance)
    if out_dir is None:
        stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        out_dir = project_folder / "_preprocessed_dxfs" / f"diff_{stamp}_{tag}"
    assert_w_drive_write_allowed(out_dir, operation="write batch cleaned DXF diff")
    out_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for index, part in enumerate(parts, start=1):
        safe_stem = _safe_part_stem(part.part_name) or f"part_{index}"
        cleaned_path = out_dir / f"{safe_stem}_outer_cleaned_{tag}.dxf"
        report_path = out_dir / f"{safe_stem}_outer_cleaned_{tag}.report.json"
        try:
            payload = clean_outer_profile(
                dxf_path=part.dxf_path,
                out_path=cleaned_path,
                report_path=report_path,
                simplify_tolerance=tolerance,
            )
            payload["part"] = part.part_name
            payload["line_number"] = index
            report_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            rows.append(_summary_row(part.part_name, payload, original_path=part.dxf_path, cleaned_path=cleaned_path))
        except Exception as exc:
            error_payload = {
                "part": part.part_name,
                "source_dxf": str(part.dxf_path),
                "error": f"{type(exc).__name__}: {exc}",
            }
            errors.append(error_payload)
            rows.append(
                {
                    "part": part.part_name,
                    "status": "error",
                    "wrote_output": False,
                    "skipped_reason": error_payload["error"],
                    "source_dxf": str(part.dxf_path),
                    "cleaned_dxf": "",
                    "original_size_bytes": part.dxf_path.stat().st_size if part.dxf_path.exists() else "",
                    "cleaned_size_bytes": "",
                    "profile_entity_count": "",
                    "loop_count": "",
                    "outside_entity_count": "",
                    "outside_entity_types": "",
                    "input_vertices": "",
                    "output_vertices": "",
                    "removed_vertices": "",
                    "max_removed_local_deviation": "",
                    "max_final_vertex_deviation": "",
                    "area_before_abs": "",
                    "area_after_abs": "",
                    "area_delta_abs": "",
                }
            )

    summary_csv = out_dir / f"dxf_clean_diff_summary_{tag}.csv"
    assert_w_drive_write_allowed(summary_csv, operation="write batch cleaned DXF diff summary")
    fieldnames = list(rows[0].keys()) if rows else []
    with summary_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    counts: dict[str, int] = {}
    for row in rows:
        status = str(row["status"])
        counts[status] = counts.get(status, 0) + 1

    changed_rows = [row for row in rows if row["status"] == "cleaned_changed"]
    payload = {
        "csv_path": str(csv_path),
        "project_folder": str(project_folder),
        "out_dir": str(out_dir),
        "summary_csv": str(summary_csv),
        "tolerance": tolerance,
        "part_count": len(parts),
        "counts": counts,
        "errors": errors,
        "top_removed_vertices": sorted(
            changed_rows,
            key=lambda row: (int(row.get("removed_vertices") or 0), float(row.get("area_delta_abs") or 0.0)),
            reverse=True,
        )[:20],
    }
    summary_json = out_dir / f"dxf_clean_diff_summary_{tag}.json"
    assert_w_drive_write_allowed(summary_json, operation="write batch cleaned DXF diff summary")
    summary_json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    payload["summary_json"] = str(summary_json)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Batch compare original DXFs against ezdxf outside-profile cleaned copies.")
    parser.add_argument("--csv", type=Path, required=True, help="Inventor-to-RADAN CSV.")
    parser.add_argument("--project-folder", type=Path, required=True, help="L-side RADAN project folder.")
    parser.add_argument("--out-dir", type=Path, help="Optional output folder. Defaults under project _preprocessed_dxfs.")
    parser.add_argument("--tolerance", type=float, default=0.002, help="Local simplification tolerance in drawing units.")
    args = parser.parse_args()

    payload = run_batch_diff(
        csv_path=args.csv,
        project_folder=args.project_folder,
        out_dir=args.out_dir,
        tolerance=args.tolerance,
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if not payload["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
