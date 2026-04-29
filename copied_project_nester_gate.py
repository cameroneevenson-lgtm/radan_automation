from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import time
import xml.etree.ElementTree as ET
from dataclasses import asdict
from pathlib import Path
from typing import Any, Iterable

from import_parts_csv_headless import (
    DEFAULT_ORIENTATION,
    PROJECT_SHEETS_REFRESH_MAC_LINE,
    _Logger,
    _mac_object,
    _resolve_automation_instance,
    _visible_radan_process_ids,
    read_import_csv,
)
from path_safety import assert_w_drive_write_allowed, is_w_drive_path
from radan_com import open_application


RADAN_PROJECT_NS = "http://www.radan.com/ns/project"
DEFAULT_LAB_ROOT = Path(__file__).resolve().parent / "_sym_lab"
DEFAULT_OVERSIZED_EXCLUDES = ("F54410-B-09", "F54410-B-11", "F54410-B-17")
RADAN_PROCESS_PATTERN = r"(?i)radan|radraft|radnest|radpunch|radbend|mazak"
REPORT_FILE_TYPE_PDF = 4

ET.register_namespace("", RADAN_PROJECT_NS)


def timestamp() -> str:
    return dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def sanitize_label(value: str) -> str:
    label = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value).strip())
    return label.strip("._") or "nester_gate"


def assert_lab_output_path(path: Path, *, lab_root: Path | None = None, operation: str = "write lab nester output") -> None:
    assert_w_drive_write_allowed(path, operation=operation)
    resolved = path.expanduser().resolve()
    root = (lab_root or DEFAULT_LAB_ROOT).expanduser().resolve()
    if resolved != root and root not in resolved.parents:
        raise RuntimeError(f"Refusing to {operation} outside lab root {root}: {path}")


def _project_tag(name: str) -> str:
    return f"{{{RADAN_PROJECT_NS}}}{name}"


def _local_name(node: ET.Element) -> str:
    if "}" in node.tag:
        return node.tag.rsplit("}", 1)[1]
    return node.tag


def _direct_child(parent: ET.Element, name: str) -> ET.Element | None:
    for child in list(parent):
        if _local_name(child) == name:
            return child
    return None


def _find_root_child(root: ET.Element, name: str) -> ET.Element:
    child = _direct_child(root, name)
    if child is not None:
        return child
    fallback = ET.SubElement(root, _project_tag(name))
    return fallback


def _parse_int(value: str | None, default: int = 0) -> int:
    try:
        return int(str(value or "").strip())
    except ValueError:
        return default


def project_snapshot(project_path: Path) -> dict[str, Any]:
    root = ET.parse(project_path).getroot()
    parts = _direct_child(root, "Parts")
    sheets = _direct_child(root, "Sheets")
    nests = _direct_child(root, "Nests")
    made_values = [(node.text or "").strip() for node in root.findall(f".//{_project_tag('Made')}")]
    return {
        "project_path": str(project_path),
        "size": project_path.stat().st_size if project_path.exists() else 0,
        "part_count": 0 if parts is None else sum(1 for child in list(parts) if _local_name(child) == "Part"),
        "sheet_count": 0 if sheets is None else sum(1 for child in list(sheets) if _local_name(child) == "Sheet"),
        "nest_count": 0 if nests is None else sum(1 for child in list(nests) if _local_name(child) == "Nest"),
        "used_nest_count": sum(
            1
            for node in root.findall(f".//{_project_tag('Used')}")
            if (node.text or "").strip() not in {"", "0"}
        ),
        "made_nonzero_count": sum(1 for value in made_values if value and value != "0"),
        "next_id": [(node.text or "").strip() for node in root.findall(f".//{_project_tag('NextID')}")[:1]],
        "next_nest_num": [(node.text or "").strip() for node in root.findall(f".//{_project_tag('NextNestNum')}")[:1]],
    }


def prepare_copied_project(source_rpd: Path, project_path: Path, *, label: str) -> dict[str, Any]:
    if not source_rpd.exists():
        raise FileNotFoundError(f"Source RPD not found: {source_rpd}")
    assert_lab_output_path(project_path, operation="write copied project RPD")
    project_path.parent.mkdir(parents=True, exist_ok=True)

    tree = ET.parse(source_rpd)
    root = tree.getroot()
    for node in root.findall(f".//{_project_tag('JobName')}"):
        if node.text:
            node.text = f"{node.text} {label}"

    parts = _find_root_child(root, "Parts")
    for child in list(parts):
        parts.remove(child)
    ET.SubElement(parts, _project_tag("NextID")).text = "1"

    sheets = _find_root_child(root, "Sheets")
    for child in list(sheets):
        sheets.remove(child)

    ET.indent(tree, space="  ")
    tree.write(project_path, encoding="UTF-8", xml_declaration=True)
    return project_snapshot(project_path)


def _normalize_part_name(value: str) -> str:
    return str(value).strip().casefold()


def select_parts(
    parts: list[Any],
    *,
    include_parts: Iterable[str] = (),
    exclude_parts: Iterable[str] = (),
    max_parts: int | None = None,
) -> tuple[list[Any], list[str]]:
    include_keys = {_normalize_part_name(name) for name in include_parts if str(name).strip()}
    exclude_keys = {_normalize_part_name(name) for name in exclude_parts if str(name).strip()}
    candidates = [
        part
        for part in parts
        if (not include_keys or _normalize_part_name(part.part_name) in include_keys)
        and _normalize_part_name(part.part_name) not in exclude_keys
    ]
    selected = list(candidates)
    if max_parts is not None:
        if max_parts <= 0:
            raise ValueError("max_parts must be greater than zero.")
        selected = selected[:max_parts]
    found_keys = {_normalize_part_name(part.part_name) for part in candidates}
    missing = sorted(name for name in include_keys if name not in found_keys)
    return selected, missing


def missing_symbol_paths(parts: list[Any], symbol_folder: Path) -> list[str]:
    return [
        str(part.symbol_path(symbol_folder))
        for part in parts
        if not part.symbol_path(symbol_folder).exists()
    ]


def list_radan_processes() -> list[dict[str, Any]]:
    if os.name != "nt":
        return []
    script = rf"""
$ErrorActionPreference = 'SilentlyContinue'
Get-Process | Where-Object {{ $_.ProcessName -match '{RADAN_PROCESS_PATTERN}' }} |
    Select-Object @{{Name='id';Expression={{$_.Id}}}},
                  @{{Name='process_name';Expression={{$_.ProcessName}}}},
                  @{{Name='path';Expression={{$_.Path}}}},
                  @{{Name='main_window_title';Expression={{$_.MainWindowTitle}}}},
                  @{{Name='start_time';Expression={{$_.StartTime.ToString('o')}}}} |
    ConvertTo-Json -Depth 3
"""
    completed = subprocess.run(
        ["powershell", "-NoProfile", "-Command", script],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    text = completed.stdout.strip()
    if not text:
        return []
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return [{"parse_error": text, "stderr": completed.stderr.strip()}]
    if isinstance(payload, dict):
        return [payload]
    if isinstance(payload, list):
        return payload
    return []


def terminate_processes(processes: list[dict[str, Any]], *, timeout_sec: float = 10.0) -> dict[str, Any]:
    ids = [int(row["id"]) for row in processes if str(row.get("id", "")).strip().isdigit()]
    if not ids or os.name != "nt":
        return {"requested_ids": ids, "stopped": [], "after": list_radan_processes()}
    id_list = ",".join(str(value) for value in ids)
    script = f"Stop-Process -Id {id_list} -Force -ErrorAction SilentlyContinue"
    subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, timeout=30, check=False)
    deadline = time.time() + timeout_sec
    after = list_radan_processes()
    while after and time.time() < deadline:
        time.sleep(0.25)
        after = list_radan_processes()
    return {"requested_ids": ids, "stopped": ids, "after": after}


def _set_mac_property(mac: Any, name: str, value: Any) -> bool:
    try:
        setattr(mac, name, value)
    except Exception:
        return False
    return True


def _get_mac_property(mac: Any, name: str, default: Any) -> Any:
    try:
        return getattr(mac, name)
    except Exception:
        return default


def _add_part_rows(mac: Any, parts: list[Any], symbol_folder: Path, logger: _Logger) -> list[dict[str, Any]]:
    part_multi = _get_mac_property(mac, "PRJ_PART_MULTI", 0)
    orient_mode_free = _get_mac_property(mac, "NSM_ORIENTATION_MODE_FREE", 0)
    added: list[dict[str, Any]] = []
    total = len(parts)
    for index, part in enumerate(parts, start=1):
        try:
            mac.prj_clear_part_data()
        except Exception:
            pass
        symbol_path = part.symbol_path(symbol_folder)
        properties = [
            ("PRJ_PART_FILENAME", str(symbol_path)),
            ("PRJ_PART_KIT_FILENAME", ""),
            ("PRJ_PART_MATERIAL", part.material),
            ("PRJ_PART_THICKNESS", float(part.thickness)),
            ("PRJ_PART_THICK_UNITS", part.unit),
            ("PRJ_PART_STRATEGY", part.strategy),
            ("PRJ_PART_NUMBER_REQUIRED", int(part.quantity)),
            ("PRJ_PART_EXTRA_ALLOWED", 0),
            ("PRJ_PART_ORIENT", DEFAULT_ORIENTATION),
            ("PRJ_PART_ORIENTATION_MODE", orient_mode_free),
            ("PRJ_PART_PRIORITY", 5),
            ("PRJ_PART_BIN", 0),
            ("PRJ_PART_MIRROR", 0),
            ("PRJ_PART_COMMON_CUT", 0),
            ("PRJ_PART_MAX_COMMON_CUT", 2),
            ("PRJ_PART_PICKING_CLUSTER", 0),
            ("PRJ_PART_NEST_MODE", part_multi),
        ]
        set_results = {name: _set_mac_property(mac, name, value) for name, value in properties}
        result = mac.prj_add_part()
        added.append({"part": part.part_name, "symbol_path": str(symbol_path), "result": result, "set_results": set_results})
        if index % 10 == 0 or index == total:
            logger.write(f"Added PRJ part {index}/{total}: {part.part_name} result={result}")
    return added


def _attempt_reports(app: Any, report_dir: Path, logger: _Logger) -> list[dict[str, Any]]:
    assert_lab_output_path(report_dir, operation="write nester report output")
    report_dir.mkdir(parents=True, exist_ok=True)
    attempts = [
        ("project", "Project Report", report_dir / "project_report.pdf", app.mac.output_project_report),
        ("setup", "Setup Sheet", report_dir / "setup_sheet.pdf", app.mac.output_setup_report),
    ]
    results: list[dict[str, Any]] = []
    for kind, report_name, path, method in attempts:
        try:
            result = method(report_name, str(path), REPORT_FILE_TYPE_PDF)
            row = {
                "kind": kind,
                "report_name": report_name,
                "path": str(path),
                "ok": result.ok,
                "error_message": result.error_message,
                "exists": path.exists(),
                "size": path.stat().st_size if path.exists() else 0,
            }
        except Exception as exc:
            row = {
                "kind": kind,
                "report_name": report_name,
                "path": str(path),
                "ok": False,
                "error": f"{type(exc).__name__}: {exc}",
                "exists": path.exists(),
                "size": path.stat().st_size if path.exists() else 0,
            }
        logger.write(f"Report attempt {kind}: ok={row.get('ok')} exists={row.get('exists')}")
        results.append(row)
    return results


def run_gate(
    *,
    source_rpd: Path,
    csv_path: Path,
    symbol_folder: Path,
    out_dir: Path,
    label: str,
    include_parts: Iterable[str] = (),
    exclude_parts: Iterable[str] = DEFAULT_OVERSIZED_EXCLUDES,
    max_parts: int | None = None,
    backend: str = "win32com",
    kill_existing_radan: bool = False,
    attempt_reports: bool = False,
) -> dict[str, Any]:
    safe_label = sanitize_label(label)
    assert_lab_output_path(out_dir, operation="write copied-project nester gate")
    if is_w_drive_path(source_rpd) or is_w_drive_path(csv_path) or is_w_drive_path(symbol_folder):
        # Reading W: source truth is allowed by the overnight plan, but call it out in the artifact.
        pass
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV not found: {csv_path}")
    if not symbol_folder.exists():
        raise FileNotFoundError(f"Symbol folder not found: {symbol_folder}")

    out_dir.mkdir(parents=True, exist_ok=True)
    logger = _Logger(out_dir / "progress.log")
    copied_csv = out_dir / csv_path.name
    if csv_path.resolve() != copied_csv.resolve():
        shutil.copy2(csv_path, copied_csv)
    project_path = out_dir / f"{source_rpd.stem}.{safe_label}.rpd"

    all_parts = read_import_csv(csv_path)
    selected_parts, missing_in_csv = select_parts(
        all_parts,
        include_parts=include_parts,
        exclude_parts=exclude_parts,
        max_parts=max_parts,
    )
    missing_symbols = missing_symbol_paths(selected_parts, symbol_folder)
    if missing_in_csv:
        raise RuntimeError(f"Requested part(s) missing from CSV: {', '.join(missing_in_csv)}")
    if missing_symbols:
        raise RuntimeError(f"Missing {len(missing_symbols)} symbol(s) for gate; first: {missing_symbols[0]}")

    preflight_processes = list_radan_processes()
    cleanup_before = terminate_processes(preflight_processes) if kill_existing_radan else None
    preexisting_visible_pids = _visible_radan_process_ids()
    before_snapshot = prepare_copied_project(source_rpd, project_path, label=safe_label)
    payload: dict[str, Any] = {
        "schema_version": 1,
        "label": safe_label,
        "source_rpd": str(source_rpd),
        "project_path": str(project_path),
        "csv_path": str(csv_path),
        "copied_csv": str(copied_csv),
        "symbol_folder": str(symbol_folder),
        "out_dir": str(out_dir),
        "include_parts": list(include_parts),
        "exclude_parts": list(exclude_parts),
        "max_parts": max_parts,
        "part_names": [part.part_name for part in selected_parts],
        "part_count": len(selected_parts),
        "handler": PROJECT_SHEETS_REFRESH_MAC_LINE,
        "process_preflight": preflight_processes,
        "process_cleanup_before": cleanup_before,
        "before": before_snapshot,
    }

    app = None
    quit_attempted = False
    should_quit_app = False
    try:
        app = open_application(backend=backend, force_new_instance=True)
        info, should_quit_app = _resolve_automation_instance(app, preexisting_visible_pids, logger)
        payload["automation_info"] = asdict(info)
        app.visible = False
        try:
            app.interactive = False
        except Exception:
            pass
        mac = _mac_object(app)
        payload["prj_open"] = bool(mac.prj_open(str(project_path)))
        if not payload["prj_open"]:
            raise RuntimeError(f"RADAN prj_open failed for copied project: {project_path}")

        payload["added_parts"] = _add_part_rows(mac, selected_parts, symbol_folder, logger)
        payload["save_after_parts"] = bool(mac.prj_save())
        payload["after_parts_save"] = project_snapshot(project_path)
        logger.write(f"Saved part rows: {payload['after_parts_save']}")

        payload["update_sheets_result"] = bool(mac.Execute(PROJECT_SHEETS_REFRESH_MAC_LINE))
        payload["save_after_update_sheets"] = bool(mac.prj_save())
        payload["after_update_sheets_save"] = project_snapshot(project_path)
        logger.write(f"Updated sheets: {payload['after_update_sheets_save']}")

        logger.write("Starting lay_run_nest(0).")
        start = time.time()
        payload["lay_run_nest_return"] = mac.lay_run_nest(0)
        payload["lay_run_nest_elapsed_sec"] = round(time.time() - start, 3)
        logger.write(
            f"lay_run_nest(0) returned {payload['lay_run_nest_return']} "
            f"in {payload['lay_run_nest_elapsed_sec']}s."
        )
        payload["save_after_lay"] = bool(mac.prj_save())
        payload["after"] = project_snapshot(project_path)
        payload["drg_files"] = sorted(str(path) for path in out_dir.rglob("*.drg"))
        payload["drg_count"] = len(payload["drg_files"])

        if attempt_reports:
            payload["reports"] = _attempt_reports(app, out_dir / "reports", logger)
        else:
            payload["reports"] = []

        try:
            payload["prj_close"] = bool(mac.prj_close())
        except Exception as exc:
            payload["prj_close_error"] = f"{type(exc).__name__}: {exc}"
        if should_quit_app:
            payload["quit_result"] = app.quit()
            quit_attempted = True
        payload["ok"] = int(payload.get("lay_run_nest_return", -1)) == 0 and payload["drg_count"] > 0
    except Exception as exc:
        payload["ok"] = False
        payload["error"] = f"{type(exc).__name__}: {exc}"
        logger.write(f"ERROR: {payload['error']}")
    finally:
        if app is not None and not quit_attempted:
            if should_quit_app:
                try:
                    payload["quit_after_error"] = app.quit()
                except Exception as exc:
                    payload["quit_after_error_error"] = f"{type(exc).__name__}: {exc}"
            try:
                app.close()
            except Exception:
                pass
        payload["process_cleanup_after_quit"] = terminate_processes(list_radan_processes())
        payload["process_final"] = list_radan_processes()
        (out_dir / "result.json").write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        logger.write("Finished copied-project nester gate.")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a lab-only copied-project RADAN nester gate.")
    parser.add_argument("--source-rpd", type=Path, required=True)
    parser.add_argument("--csv", type=Path, required=True)
    parser.add_argument("--symbol-folder", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--part", action="append", default=[], help="Part name to include. Defaults to all CSV rows.")
    parser.add_argument("--exclude", action="append", default=[], help="Part name to exclude.")
    parser.add_argument("--include-default-oversized-excludes", action="store_true")
    parser.add_argument("--max-parts", type=int)
    parser.add_argument("--backend", default="win32com")
    parser.add_argument("--kill-existing-radan", action="store_true")
    parser.add_argument("--attempt-reports", action="store_true")
    args = parser.parse_args()

    excludes = list(args.exclude)
    if args.include_default_oversized_excludes:
        excludes.extend(DEFAULT_OVERSIZED_EXCLUDES)
    payload = run_gate(
        source_rpd=args.source_rpd.expanduser().resolve(),
        csv_path=args.csv.expanduser().resolve(),
        symbol_folder=args.symbol_folder.expanduser().resolve(),
        out_dir=args.out_dir.expanduser().resolve(),
        label=args.label,
        include_parts=args.part,
        exclude_parts=excludes,
        max_parts=args.max_parts,
        backend=str(args.backend),
        kill_existing_radan=bool(args.kill_existing_radan),
        attempt_reports=bool(args.attempt_reports),
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if "error" not in payload else 1


if __name__ == "__main__":
    raise SystemExit(main())
