from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from copied_project_nester_gate import assert_lab_output_path, list_radan_processes


REPO_ROOT = Path(__file__).resolve().parent
DEFAULT_LAB_ROOT = REPO_ROOT / "_sym_lab"
DEFAULT_PYTHON = Path(r"C:\Tools\.venv\Scripts\python.exe")
DEFAULT_CSV = Path(
    r"L:\BATTLESHIELD\F-LARGE FLEET\F54410\PAINT PACK\F54410 PAINT PACK\F54410-PAINT PACK-BOM_Radan.csv"
)
DEFAULT_SOURCE_RPD = Path(
    r"L:\BATTLESHIELD\F-LARGE FLEET\F54410\PAINT PACK\F54410 PAINT PACK\F54410 PAINT PACK.rpd"
)
DEFAULT_ORACLE_SYM_FOLDER = Path(r"L:\BATTLESHIELD\F-LARGE FLEET\F54410\PAINT PACK")
DEFAULT_DXF_FOLDER = DEFAULT_LAB_ROOT / "universal_donor_predictability_20260430_1128" / "dxf_95"
DEFAULT_OVERSIZED_EXCLUDES = ("F54410-B-09", "F54410-B-11", "F54410-B-17")
ROWCOUNT_TRIO = ("F54410-B-39", "F54410-B-37", "F54410-B-38")


def timestamp() -> str:
    return dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def write_json(path: Path, payload: Any) -> None:
    assert_lab_output_path(path, operation="write overnight JSON")
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.tmp")
    temp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True) + "\n", encoding="utf-8")
    temp_path.replace(path)


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    assert_lab_output_path(path, operation="write overnight CSV")
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row})
    temp_path = path.with_name(f"{path.name}.tmp")
    with temp_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    temp_path.replace(path)


def write_filtered_radan_csv(*, source_csv: Path, out_csv: Path, include_parts: tuple[str, ...]) -> None:
    assert_lab_output_path(out_csv, operation="write filtered overnight CSV")
    include_keys = {part.casefold() for part in include_parts}
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    selected: list[list[str]] = []
    with source_csv.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.reader(handle):
            if not row or not row[0].strip():
                continue
            if Path(row[0].strip()).stem.casefold() in include_keys:
                selected.append(row)
    missing = sorted(include_keys - {Path(row[0].strip()).stem.casefold() for row in selected})
    if missing:
        raise RuntimeError(f"Filtered CSV missed requested part(s): {', '.join(missing)}")
    temp_path = out_csv.with_name(f"{out_csv.name}.tmp")
    with temp_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerows(selected)
    temp_path.replace(out_csv)


def append_log(out_dir: Path, *, track: str, hypothesis: str, command: str = "", conclusion: str = "") -> None:
    assert_lab_output_path(out_dir / "OVERNIGHT_LOG.md", operation="write overnight log")
    out_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        f"## {dt.datetime.now().isoformat(timespec='seconds')}",
        "",
        f"- Track: `{track}`",
        f"- Hypothesis: {hypothesis}",
    ]
    if command:
        lines.append(f"- Command: `{command}`")
    if conclusion:
        lines.append(f"- Conclusion: {conclusion}")
    lines.append("")
    with (out_dir / "OVERNIGHT_LOG.md").open("a", encoding="utf-8") as handle:
        handle.write("\n".join(lines))


def command_text(command: list[str | Path]) -> str:
    return " ".join(f'"{str(item)}"' if " " in str(item) else str(item) for item in command)


def run_command(
    *,
    out_dir: Path,
    name: str,
    command: list[str | Path],
    timeout_seconds: int,
    candidate_matrix: list[dict[str, Any]],
) -> dict[str, Any]:
    commands_dir = out_dir / "commands"
    commands_dir.mkdir(parents=True, exist_ok=True)
    started = dt.datetime.now()
    preflight = list_radan_processes()
    write_json(commands_dir / f"{name}_process_preflight.json", preflight)
    append_log(
        out_dir,
        track="command",
        hypothesis=f"Run {name}",
        command=command_text(command),
        conclusion=f"Started with {len(preflight)} RADAN-family process(es).",
    )
    completed = subprocess.run(
        [str(item) for item in command],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        timeout=timeout_seconds,
    )
    finished = dt.datetime.now()
    final_processes = list_radan_processes()
    payload = {
        "name": name,
        "command": [str(item) for item in command],
        "started": started.isoformat(timespec="seconds"),
        "finished": finished.isoformat(timespec="seconds"),
        "elapsed_seconds": (finished - started).total_seconds(),
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "process_preflight": preflight,
        "process_final": final_processes,
    }
    write_json(commands_dir / f"{name}.json", payload)
    write_json(commands_dir / f"{name}_process_final.json", final_processes)
    append_log(
        out_dir,
        track="command",
        hypothesis=f"Run {name}",
        command=command_text(command),
        conclusion=f"Return code {completed.returncode}; final RADAN-family process count {len(final_processes)}.",
    )
    candidate_matrix.append(
        {
            "candidate": name,
            "command": command_text(command),
            "returncode": completed.returncode,
            "elapsed_seconds": payload["elapsed_seconds"],
            "process_preflight_count": len(preflight),
            "process_final_count": len(final_processes),
        }
    )
    return payload


def read_json_if_exists(path: Path) -> Any:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def summarize_generation(out_dir: Path, candidate_matrix: list[dict[str, Any]], *, name: str, generation_dir: Path) -> None:
    manifest = read_json_if_exists(generation_dir / "manifest.json") or {}
    symbols = manifest.get("symbol_dir")
    for row in manifest.get("rows", []):
        normalization = row.get("collinear_normalization") or {}
        candidate_matrix.append(
            {
                "candidate": name,
                "part": row.get("part"),
                "symbol_folder": symbols,
                "candidate_type": "normalized_generated_donor_only",
                "same_part_oracle_text_used": False,
                "source_entity_count": row.get("source_entity_count"),
                "part_row_count": row.get("generated_geometry_records"),
                "validation_passed": row.get("validation_passed"),
                "accepted_merge_count": normalization.get("accepted_merge_count"),
                "row_delta": normalization.get("row_delta"),
                "ok": row.get("ok"),
            }
        )


def summarize_nester(candidate_matrix: list[dict[str, Any]], *, name: str, nester_dir: Path, part: str) -> bool:
    result = read_json_if_exists(nester_dir / "result.json") or {}
    after = result.get("after") or {}
    reports = result.get("reports") or {}
    candidate_matrix.append(
        {
            "candidate": name,
            "part": part,
            "candidate_type": "copied_project_nester_gate",
            "rpd_path": result.get("project_path"),
            "ok": result.get("ok"),
            "part_rows": after.get("part_count"),
            "sheet_rows": after.get("sheet_count"),
            "nest_rows": after.get("nest_count"),
            "made_nonzero_count": after.get("made_nonzero_count"),
            "next_nest_num": after.get("next_nest_num"),
            "drg_count": result.get("drg_count"),
            "report_status": reports,
            "lay_run_nest_return": result.get("lay_run_nest_return"),
        }
    )
    return bool(result.get("ok"))


def write_summary(out_dir: Path, candidate_matrix: list[dict[str, Any]]) -> None:
    lines = [
        "# Overnight F54410 Collinear Token Crack Summary",
        "",
        f"- Run folder: `{out_dir}`",
        f"- Timestamp: `{dt.datetime.now().isoformat(timespec='seconds')}`",
        f"- Candidate rows: `{len(candidate_matrix)}`",
        f"- Known nester/setup exclusions for 95-part gates: `{', '.join(DEFAULT_OVERSIZED_EXCLUDES)}`",
        "",
        "## Latest Candidate Matrix",
        "",
        "| Candidate | Part | Type | OK | Rows | Sheets | Nests | Made | DRGs |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in candidate_matrix:
        lines.append(
            "| {candidate} | {part} | {kind} | {ok} | {rows} | {sheets} | {nests} | {made} | {drgs} |".format(
                candidate=str(row.get("candidate", "")).replace("|", "\\|"),
                part=str(row.get("part", "")).replace("|", "\\|"),
                kind=str(row.get("candidate_type", "")).replace("|", "\\|"),
                ok=str(row.get("ok", row.get("returncode", ""))).replace("|", "\\|"),
                rows=row.get("part_rows", row.get("part_row_count", "")),
                sheets=row.get("sheet_rows", ""),
                nests=row.get("nest_rows", ""),
                made=row.get("made_nonzero_count", ""),
                drgs=row.get("drg_count", ""),
            )
        )
    lines.append("")
    summary_path = out_dir / "SUMMARY.md"
    assert_lab_output_path(summary_path, operation="write overnight summary")
    summary_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the lab-only overnight F54410 collinear/token crack ladder.")
    parser.add_argument("--out-dir", type=Path)
    parser.add_argument("--python", type=Path, default=DEFAULT_PYTHON)
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--source-rpd", type=Path, default=DEFAULT_SOURCE_RPD)
    parser.add_argument("--oracle-sym-folder", type=Path, default=DEFAULT_ORACLE_SYM_FOLDER)
    parser.add_argument("--dxf-folder", type=Path, default=DEFAULT_DXF_FOLDER)
    parser.add_argument("--skip-baseline", action="store_true")
    parser.add_argument("--skip-nester", action="store_true")
    parser.add_argument("--promote-95-on-trio-pass", action="store_true")
    args = parser.parse_args()

    out_dir = args.out_dir or DEFAULT_LAB_ROOT / f"overnight_f54410_collinear_token_crack_{timestamp()}"
    assert_lab_output_path(out_dir, operation="write overnight run folder")
    out_dir.mkdir(parents=True, exist_ok=True)
    candidate_matrix: list[dict[str, Any]] = []
    append_log(out_dir, track="setup", hypothesis="Create fresh overnight run folder", conclusion=str(out_dir))
    trio_csv = out_dir / "rowcount_trio_Radan.csv"
    write_filtered_radan_csv(source_csv=args.csv, out_csv=trio_csv, include_parts=ROWCOUNT_TRIO)
    append_log(
        out_dir,
        track="setup",
        hypothesis="Create a lab-local CSV for row-count trio comparisons",
        conclusion=str(trio_csv),
    )

    if not args.skip_baseline:
        run_command(
            out_dir=out_dir,
            name="baseline_unittest",
            command=[args.python, "-m", "unittest", "discover", "-v"],
            timeout_seconds=300,
            candidate_matrix=candidate_matrix,
        )

    generation_dir = out_dir / "normalized_rowcount_trio"
    generation_command: list[str | Path] = [
        args.python,
        REPO_ROOT / "run_universal_donor_sym_research.py",
        "--csv",
        trio_csv,
        "--source-rpd",
        args.source_rpd,
        "--out-dir",
        generation_dir,
        "--label",
        "normalized_collinear_trio",
        "--normalize-collinear-line-chains",
    ]
    for part in ROWCOUNT_TRIO:
        generation_command.extend(["--part", part])
    run_command(
        out_dir=out_dir,
        name="generate_normalized_rowcount_trio",
        command=generation_command,
        timeout_seconds=300,
        candidate_matrix=candidate_matrix,
    )
    summarize_generation(out_dir, candidate_matrix, name="generate_normalized_rowcount_trio", generation_dir=generation_dir)

    symbol_folder = generation_dir / "symbols"
    run_command(
        out_dir=out_dir,
        name="compare_trio_ddc_geometry",
        command=[
            args.python,
            REPO_ROOT / "compare_ddc_geometry.py",
            "--csv",
            trio_csv,
            "--oracle-sym-folder",
            args.oracle_sym_folder,
            "--compare-sym-folder",
            symbol_folder,
            "--out",
            out_dir / "compare_trio_ddc_geometry.json",
        ],
        timeout_seconds=300,
        candidate_matrix=candidate_matrix,
    )

    if args.dxf_folder.exists():
        run_command(
            out_dir=out_dir,
            name="analyze_trio_token_residuals",
            command=[
                args.python,
                REPO_ROOT / "analyze_token_residuals.py",
                "--dxf-folder",
                args.dxf_folder,
                "--oracle-sym-folder",
                args.oracle_sym_folder,
                "--generated-sym-folder",
                symbol_folder,
                "--out-json",
                out_dir / "trio_token_residuals.json",
                "--out-csv",
                out_dir / "trio_token_residuals.csv",
                "--part",
                "F54410-B-39",
                "--part",
                "F54410-B-37",
                "--part",
                "F54410-B-38",
            ],
            timeout_seconds=300,
            candidate_matrix=candidate_matrix,
        )
    else:
        append_log(
            out_dir,
            track="analyze",
            hypothesis="Run token residuals when exported DXF folder is present",
            conclusion=f"Skipped because {args.dxf_folder} does not exist.",
        )

    singleton_passes: dict[str, bool] = {}
    if not args.skip_nester:
        for part in ROWCOUNT_TRIO:
            nester_dir = out_dir / f"nester_single_{part.replace('-', '_')}"
            run_command(
                out_dir=out_dir,
                name=f"nester_single_{part.replace('-', '_')}",
                command=[
                    args.python,
                    REPO_ROOT / "copied_project_nester_gate.py",
                    "--source-rpd",
                    args.source_rpd,
                    "--csv",
                    trio_csv,
                    "--symbol-folder",
                    symbol_folder,
                    "--out-dir",
                    nester_dir,
                    "--label",
                    f"norm_{part}",
                    "--part",
                    part,
                ],
                timeout_seconds=420,
                candidate_matrix=candidate_matrix,
            )
            singleton_passes[part] = summarize_nester(
                candidate_matrix,
                name=f"nester_single_{part.replace('-', '_')}",
                nester_dir=nester_dir,
                part=part,
            )

    if args.promote_95_on_trio_pass and singleton_passes and all(singleton_passes.values()):
        generation_95_dir = out_dir / "normalized_95_excluding_known_blockers"
        command_95: list[str | Path] = [
            args.python,
            REPO_ROOT / "run_universal_donor_sym_research.py",
            "--csv",
            args.csv,
            "--source-rpd",
            args.source_rpd,
            "--out-dir",
            generation_95_dir,
            "--label",
            "normalized_collinear_95",
            "--include-default-oversized-excludes",
            "--normalize-collinear-line-chains",
        ]
        run_command(
            out_dir=out_dir,
            name="generate_normalized_95_excluding_known_blockers",
            command=command_95,
            timeout_seconds=900,
            candidate_matrix=candidate_matrix,
        )
        summarize_generation(
            out_dir,
            candidate_matrix,
            name="generate_normalized_95_excluding_known_blockers",
            generation_dir=generation_95_dir,
        )
        if not args.skip_nester:
            nester_95_dir = out_dir / "nester_95_excluding_known_blockers"
            run_command(
                out_dir=out_dir,
                name="nester_95_excluding_known_blockers",
                command=[
                    args.python,
                    REPO_ROOT / "copied_project_nester_gate.py",
                    "--source-rpd",
                    args.source_rpd,
                    "--csv",
                    args.csv,
                    "--symbol-folder",
                    generation_95_dir / "symbols",
                    "--out-dir",
                    nester_95_dir,
                    "--label",
                    "norm95",
                    "--include-default-oversized-excludes",
                ],
                timeout_seconds=1200,
                candidate_matrix=candidate_matrix,
            )
            summarize_nester(
                candidate_matrix,
                name="nester_95_excluding_known_blockers",
                nester_dir=nester_95_dir,
                part="95_excluding_B09_B11_B17",
            )

    write_json(out_dir / "candidate_matrix.json", candidate_matrix)
    write_csv(out_dir / "candidate_matrix.csv", candidate_matrix)
    write_summary(out_dir, candidate_matrix)
    return 0 if all(int(row.get("returncode", 0)) == 0 for row in candidate_matrix if "returncode" in row) else 1


if __name__ == "__main__":
    raise SystemExit(main())
