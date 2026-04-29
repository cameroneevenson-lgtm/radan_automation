from __future__ import annotations

import argparse
import json
import shutil
import time
from pathlib import Path
from typing import Any

from ddc_corpus import read_ddc_records
from import_parts_csv_headless import DEFAULT_ORIENTATION, UNIT_TO_RADAN, _mac_object
from path_safety import assert_w_drive_write_allowed
from radan_com import open_application
from radan_sym_analysis import diff_sym_sections


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    assert_w_drive_write_allowed(path, operation="write RADAN DXF string micro-oracle JSON")
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.tmp")
    temp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True) + "\n", encoding="utf-8")
    temp_path.replace(path)


def _radan_processes() -> list[dict[str, Any]]:
    try:
        import subprocess

        command = (
            "Get-Process | Where-Object { "
            "$_.ProcessName -match 'radan|radraft|radnest|radpunch' -or "
            "$_.MainWindowTitle -match 'RADAN|Radraft|RADRAFT' "
            "} | Select-Object Id,ProcessName,Path,MainWindowTitle | ConvertTo-Json -Depth 3"
        )
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", command],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        text = result.stdout.strip()
        if not text:
            return []
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return [parsed]
        return list(parsed)
    except Exception as exc:
        return [{"error": str(exc)}]


def _mutate_text(text: str, replacements: dict[str, str]) -> str:
    mutated = text
    for source, target in replacements.items():
        mutated = mutated.replace(source, target)
    return mutated


def _mutate_group_value(text: str, *, group_code: str, source_value: str, target_value: str) -> str:
    lines = text.splitlines()
    output = list(lines)
    for index in range(0, len(lines) - 1):
        if lines[index].strip() == str(group_code) and lines[index + 1].strip() == source_value:
            output[index + 1] = target_value
    newline = "\n" if text.endswith("\n") else ""
    return "\n".join(output) + newline


def _apply_variant_mutations(text: str, variant: dict[str, Any]) -> str:
    mutated = _mutate_text(text, dict(variant.get("replacements") or {}))
    for group_replacement in variant.get("group_value_replacements") or []:
        mutated = _mutate_group_value(
            mutated,
            group_code=str(group_replacement["group_code"]),
            source_value=str(group_replacement["source_value"]),
            target_value=str(group_replacement["target_value"]),
        )
    return mutated


def _variant_definitions() -> list[dict[str, Any]]:
    return [
        {"stem": "M01", "description": "B-17 exported DXF copied byte-for-byte", "replacements": {}},
        {
            "stem": "M02",
            "description": "Same numeric values with explicit trailing decimal zeros",
            "replacements": {
                "0.025000": "0.025000000000",
                "2.024219": "2.024219000000",
                "2.049219": "2.049219000000",
                "10.037500": "10.037500000000",
                "10.062500": "10.062500000000",
            },
        },
        {
            "stem": "M03",
            "description": "B-17 y/top values nudged down by one picounit",
            "replacements": {
                "2.024219": "2.024218999999",
                "2.049219": "2.049218999999",
            },
        },
        {
            "stem": "M04",
            "description": "B-17 y/top values nudged up by one picounit",
            "replacements": {
                "2.024219": "2.024219000001",
                "2.049219": "2.049219000001",
            },
        },
        {
            "stem": "M05",
            "description": "B-17 small radius and offsets nudged down by one picounit",
            "replacements": {
                "0.025000": "0.024999999999",
            },
        },
        {
            "stem": "M06",
            "description": "B-17 small radius and offsets nudged up by one picounit",
            "replacements": {
                "0.025000": "0.025000000001",
            },
        },
        {
            "stem": "M07",
            "description": "B-17 small radius and offsets nudged down by one tenth picounit",
            "replacements": {
                "0.025000": "0.0249999999999",
            },
        },
        {
            "stem": "M08",
            "description": "B-17 small radius and offsets nudged up by one tenth picounit",
            "replacements": {
                "0.025000": "0.0250000000001",
            },
        },
        {
            "stem": "M09",
            "description": "B-17 small radius and offsets nudged down by half picounit",
            "replacements": {
                "0.025000": "0.0249999999995",
            },
        },
        {
            "stem": "M10",
            "description": "B-17 small radius and offsets nudged up by half picounit",
            "replacements": {
                "0.025000": "0.0250000000005",
            },
        },
        {
            "stem": "M11",
            "description": "B-17 small radius and offsets nudged down by ten picounits",
            "replacements": {
                "0.025000": "0.024999999990",
            },
        },
        {
            "stem": "M12",
            "description": "B-17 small radius and offsets nudged up by ten picounits",
            "replacements": {
                "0.025000": "0.025000000010",
            },
        },
        {
            "stem": "M13",
            "description": "Only B-17 2.024219 values nudged up by one picounit",
            "replacements": {
                "2.024219": "2.024219000001",
            },
        },
        {
            "stem": "M14",
            "description": "Only B-17 2.049219 values nudged up by one picounit",
            "replacements": {
                "2.049219": "2.049219000001",
            },
        },
        {
            "stem": "M15",
            "description": "Only B-17 10.037500 values nudged up by one picounit",
            "replacements": {
                "10.037500": "10.037500000001",
            },
        },
        {
            "stem": "M16",
            "description": "Only B-17 10.062500 values nudged up by one picounit",
            "replacements": {
                "10.062500": "10.062500000001",
            },
        },
        {
            "stem": "M17",
            "description": "Only B-17 ARC radius group 40 values nudged up by one picounit",
            "group_value_replacements": [
                {"group_code": "40", "source_value": "0.025000", "target_value": "0.025000000001"},
            ],
        },
        {
            "stem": "M18",
            "description": "Only B-17 non-radius group 10/20 coordinate 0.025000 values nudged up by one picounit",
            "group_value_replacements": [
                {"group_code": "10", "source_value": "0.025000", "target_value": "0.025000000001"},
                {"group_code": "20", "source_value": "0.025000", "target_value": "0.025000000001"},
            ],
        },
    ]


def _convert_dxf_to_sym(
    *,
    app: Any,
    dxf_path: Path,
    sym_path: Path,
    part_name: str,
) -> None:
    app.open_symbol(str(dxf_path), read_only=False)
    app.visible = False
    app.interactive = False
    mac = _mac_object(app)
    mac.ped_set_attrs2(
        part_name,
        "LAB",
        "",
        0.125,
        UNIT_TO_RADAN["in"],
        DEFAULT_ORIENTATION,
    )
    app.save_active_document_as(str(sym_path))
    app.close_active_document(True)
    if not sym_path.exists():
        raise FileNotFoundError(str(sym_path))


def _geometry_rows(path: Path) -> list[dict[str, Any]]:
    rows = []
    for index, row in enumerate(read_ddc_records(path), start=1):
        rows.append(
            {
                "index": index,
                "record": row["record"],
                "pen": row["pen"],
                "tokens": row["tokens"],
                "geometry_data": row["geometry_data"],
            }
        )
    return rows


def run_micro_oracles(
    *,
    source_dxf: Path,
    known_good_sym: Path,
    out_dir: Path,
    backend: str = "win32com",
) -> dict[str, Any]:
    assert_w_drive_write_allowed(out_dir, operation="write RADAN DXF string micro-oracle outputs")
    out_dir.mkdir(parents=True, exist_ok=True)
    dxf_dir = out_dir / "dxfs"
    sym_dir = out_dir / "syms"
    diff_dir = out_dir / "diffs"
    for folder in (dxf_dir, sym_dir, diff_dir):
        folder.mkdir(parents=True, exist_ok=True)

    source_text = source_dxf.read_text(encoding="utf-8", errors="replace")
    variants = _variant_definitions()
    for variant in variants:
        dxf_path = dxf_dir / f"{variant['stem']}.dxf"
        if variant.get("replacements") or variant.get("group_value_replacements"):
            dxf_path.write_text(_apply_variant_mutations(source_text, variant), encoding="utf-8")
        else:
            shutil.copy2(source_dxf, dxf_path)
        variant["dxf_path"] = str(dxf_path)

    process_start = _radan_processes()
    _write_json(out_dir / "process_start.json", {"processes": process_start})
    if process_start:
        raise RuntimeError(f"RADAN/Radraft processes are already running: {process_start}")

    app = None
    created_pid = None
    started = time.perf_counter()
    try:
        app = open_application(backend=backend, force_new_instance=True)
        try:
            info = app.info()
            created_pid = info.process_id
        except Exception:
            created_pid = None
        app.visible = False
        app.interactive = False
        for variant in variants:
            sym_path = sym_dir / f"{variant['stem']}.sym"
            variant["sym_path"] = str(sym_path)
            try:
                _convert_dxf_to_sym(
                    app=app,
                    dxf_path=Path(variant["dxf_path"]),
                    sym_path=sym_path,
                    part_name=str(variant["stem"]),
                )
                variant["status"] = "ok"
                variant["geometry_rows"] = _geometry_rows(sym_path)
                diff = diff_sym_sections(known_good_sym, sym_path)
                diff_path = diff_dir / f"{variant['stem']}_vs_known_good.json"
                _write_json(diff_path, diff)
                variant["diff_path"] = str(diff_path)
                variant["exact_geometry_data_matches"] = diff["ddc_comparison"]["exact_geometry_data_matches"]
                variant["paired_record_count"] = diff["ddc_comparison"]["paired_record_count"]
                variant["token_match_ratio"] = diff["ddc_comparison"]["token_match_ratio"]
                variant["max_decoded_abs_diff"] = diff["ddc_comparison"]["max_decoded_abs_diff"]
            except Exception as exc:
                variant["status"] = "error"
                variant["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        if app is not None:
            try:
                app.quit()
            except Exception:
                pass

    process_end = _radan_processes()
    _write_json(out_dir / "process_end.json", {"processes": process_end, "created_pid": created_pid})
    payload = {
        "schema_version": 1,
        "source_dxf": str(source_dxf),
        "known_good_sym": str(known_good_sym),
        "out_dir": str(out_dir),
        "backend": backend,
        "created_pid": created_pid,
        "elapsed_seconds": time.perf_counter() - started,
        "variants": variants,
        "process_start": process_start,
        "process_end": process_end,
    }
    _write_json(out_dir / "micro_oracle_summary.json", payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Run RADAN micro-oracles for DXF numeric string variants.")
    parser.add_argument("--source-dxf", type=Path, required=True)
    parser.add_argument("--known-good-sym", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--backend", default="win32com")
    args = parser.parse_args()
    payload = run_micro_oracles(
        source_dxf=args.source_dxf,
        known_good_sym=args.known_good_sym,
        out_dir=args.out_dir,
        backend=args.backend,
    )
    print(
        json.dumps(
            {
                "elapsed_seconds": payload["elapsed_seconds"],
                "created_pid": payload["created_pid"],
                "variants": [
                    {
                        "stem": row["stem"],
                        "status": row["status"],
                        "exact_geometry_data_matches": row.get("exact_geometry_data_matches"),
                        "paired_record_count": row.get("paired_record_count"),
                        "token_match_ratio": row.get("token_match_ratio"),
                        "max_decoded_abs_diff": row.get("max_decoded_abs_diff"),
                        "error": row.get("error"),
                    }
                    for row in payload["variants"]
                ],
                "process_end": payload["process_end"],
            },
            indent=2,
            ensure_ascii=True,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
