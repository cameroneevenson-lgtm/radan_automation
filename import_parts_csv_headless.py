from __future__ import annotations

import argparse
import csv
import ctypes
import datetime as dt
import hashlib
import importlib.util
import json
import os
import shutil
import sys
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from path_safety import assert_w_drive_write_allowed
from radan_com import list_visible_radan_sessions, open_application


UNIT_TO_RADAN = {"mm": 0, "in": 1, "swg": 2}
DEFAULT_ORIENTATION = 3
RADAN_PROJECT_NS = "http://www.radan.com/ns/project"
ET.register_namespace("", RADAN_PROJECT_NS)
DEFAULT_PREPROCESS_DXF_TOLERANCE = 0.002
DEFAULT_SYNTHETIC_DONOR_SYM = Path(__file__).resolve().parent / "donor.sym"
DEFAULT_PROJECT_PART_COLOR = "31, 223, 223"
PROJECT_UPDATE_METHOD_DIRECT_XML = "direct-xml"
PROJECT_UPDATE_METHOD_RADAN_NST = "radan-nst"
PROJECT_UPDATE_METHODS = {
    PROJECT_UPDATE_METHOD_DIRECT_XML,
    PROJECT_UPDATE_METHOD_RADAN_NST,
}

PROJECT_PART_COLOR_PALETTE = (
    "55, 31, 223",
    "91, 223, 31",
    "31, 115, 223",
    "31, 43, 223",
    "31, 223, 187",
    "223, 31, 211",
    "223, 31, 31",
    "223, 31, 139",
    "223, 175, 31",
    "127, 31, 223",
    "223, 211, 31",
    "223, 103, 31",
    "55, 223, 31",
    "223, 139, 31",
    "223, 31, 67",
    "31, 223, 115",
    "223, 31, 175",
    "199, 223, 31",
    "223, 67, 31",
    "31, 187, 223",
    "223, 31, 103",
    "163, 223, 31",
    "31, 79, 223",
    "199, 31, 223",
    "127, 223, 31",
    "31, 223, 151",
    "91, 31, 223",
    "31, 223, 223",
    "31, 223, 79",
    "31, 151, 223",
    "31, 223, 43",
    "163, 31, 223",
)


@dataclass(frozen=True)
class ImportPart:
    dxf_path: Path
    quantity: int
    material: str
    thickness: float
    unit: str
    strategy: str

    @property
    def part_name(self) -> str:
        return self.dxf_path.stem

    def symbol_path(self, output_folder: Path) -> Path:
        return output_folder / f"{self.part_name}.sym"


class _Logger:
    def __init__(self, log_file: Path | None = None) -> None:
        self.log_file = log_file
        if self.log_file is not None:
            assert_w_drive_write_allowed(self.log_file, operation="write RADAN CSV import log")
            self.log_file.parent.mkdir(parents=True, exist_ok=True)
            self.log_file.write_text("", encoding="utf-8")

    def write(self, message: str) -> None:
        stamp = dt.datetime.now().strftime("%H:%M:%S")
        line = f"[{stamp}] {message}"
        if self.log_file is not None:
            with self.log_file.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        else:
            print(line, flush=True)


def _parse_quantity(value: str, *, line_number: int) -> int:
    try:
        quantity = int(float(str(value).strip()))
    except ValueError as exc:
        raise ValueError(f"Line {line_number}: invalid quantity {value!r}.") from exc
    if quantity <= 0:
        raise ValueError(f"Line {line_number}: quantity must be greater than zero.")
    return quantity


def _parse_thickness(value: str, *, line_number: int) -> float:
    try:
        thickness = float(str(value).strip())
    except ValueError as exc:
        raise ValueError(f"Line {line_number}: invalid thickness {value!r}.") from exc
    if thickness <= 0:
        raise ValueError(f"Line {line_number}: thickness must be greater than zero.")
    return thickness


def read_import_csv(csv_path: Path, *, max_parts: int | None = None) -> list[ImportPart]:
    if max_parts is not None and max_parts <= 0:
        raise ValueError("max_parts must be greater than zero when supplied.")
    parts: list[ImportPart] = []
    with csv_path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.reader(handle)
        for line_number, row in enumerate(reader, start=1):
            if not row or all(not cell.strip() for cell in row):
                continue
            if len(row) != 6:
                raise ValueError(f"Line {line_number}: expected 6 columns, found {len(row)}.")
            raw_unit = row[4].strip().casefold()
            if raw_unit not in UNIT_TO_RADAN:
                raise ValueError(f"Line {line_number}: unsupported thickness unit {row[4]!r}.")
            part = ImportPart(
                dxf_path=Path(row[0].strip()),
                quantity=_parse_quantity(row[1], line_number=line_number),
                material=row[2].strip(),
                thickness=_parse_thickness(row[3], line_number=line_number),
                unit=raw_unit,
                strategy=row[5].strip(),
            )
            if not part.dxf_path.exists():
                raise FileNotFoundError(str(part.dxf_path))
            parts.append(part)
            if max_parts is not None and len(parts) >= max_parts:
                break
    if not parts:
        raise ValueError(f"No importable parts were found in {csv_path}.")
    return parts


def _backup_file(path: Path, backup_dir: Path) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / path.name
    if backup_path.exists():
        stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = backup_dir / f"{path.stem}_{stamp}{path.suffix}"
    shutil.copy2(path, backup_path)
    return backup_path


def _backup_project(project_path: Path, logger: _Logger) -> Path:
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = project_path.parent / "_bak"
    backup_dir.mkdir(parents=True, exist_ok=True)
    assert_w_drive_write_allowed(backup_dir, operation="write RADAN project backup")
    backup_path = backup_dir / f"{project_path.stem}_before_headless_import_{stamp}{project_path.suffix}"
    if backup_path.exists():
        backup_path = backup_dir / (
            f"{project_path.stem}_before_headless_import_{dt.datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
            f"{project_path.suffix}"
        )
    shutil.copy2(project_path, backup_path)
    logger.write(f"Backed up project: {backup_path}")
    return backup_path


def _process_exists(process_id: int) -> bool:
    if process_id <= 0:
        return False
    if os.name == "nt":
        process_query_limited_information = 0x1000
        handle = ctypes.windll.kernel32.OpenProcess(
            process_query_limited_information,
            False,
            int(process_id),
        )
        if not handle:
            return False
        ctypes.windll.kernel32.CloseHandle(handle)
        return True
    try:
        os.kill(int(process_id), 0)
    except OSError:
        return False
    return True


class _ImportLock:
    def __init__(self, project_path: Path, logger: _Logger) -> None:
        digest = hashlib.sha1(str(project_path).casefold().encode("utf-8")).hexdigest()[:16]
        self.path = Path(os.environ.get("TEMP", str(project_path.parent))) / f"radan_csv_import_{digest}.lock"
        self.logger = logger
        self.fd: int | None = None

    def _try_acquire(self) -> None:
        self.fd = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(self.fd, str(os.getpid()).encode("ascii", errors="ignore"))

    def _read_existing_pid(self) -> int | None:
        try:
            text = self.path.read_text(encoding="ascii", errors="ignore").strip()
        except OSError:
            return None
        try:
            return int(text)
        except ValueError:
            return None

    def _remove_stale_lock(self) -> bool:
        existing_pid = self._read_existing_pid()
        if existing_pid is not None and _process_exists(existing_pid):
            return False
        try:
            self.path.unlink()
        except OSError:
            return False
        if existing_pid is None:
            self.logger.write(f"Removed stale RADAN import lock with no live PID: {self.path}")
        else:
            self.logger.write(f"Removed stale RADAN import lock for dead PID {existing_pid}: {self.path}")
        return True

    def __enter__(self) -> "_ImportLock":
        try:
            self._try_acquire()
        except FileExistsError as exc:
            if self._remove_stale_lock():
                try:
                    self._try_acquire()
                except FileExistsError:
                    pass
                else:
                    self.logger.write(f"Acquired import lock: {self.path}")
                    return self
            raise RuntimeError(
                f"Another RADAN CSV import appears to be running for this project: {self.path}"
            ) from exc
        self.logger.write(f"Acquired import lock: {self.path}")
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        if self.fd is not None:
            try:
                os.close(self.fd)
            except OSError:
                pass
            self.fd = None
        try:
            self.path.unlink()
            self.logger.write(f"Released import lock: {self.path}")
        except OSError:
            pass


def _format_elapsed(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes, remainder = divmod(seconds, 60.0)
    if minutes < 60:
        return f"{int(minutes)}m {remainder:.1f}s"
    hours, minutes = divmod(int(minutes), 60)
    return f"{hours}h {minutes}m {remainder:.1f}s"


def _mac_object(app: Any) -> Any:
    return app._backend._resolve_path(("Mac",))


def _visible_radan_process_ids() -> set[int]:
    return {
        int(session.process_id)
        for session in list_visible_radan_sessions()
        if session.process_id is not None
    }


def _resolve_automation_instance(app: Any, preexisting_visible_pids: set[int], logger: _Logger) -> tuple[Any, bool]:
    info = app.info()
    process_id = info.process_id
    logger.write(
        "Resolved RADAN automation COM object: "
        f"PID {process_id}, created_new_instance={bool(app.created_new_instance)}."
    )
    if process_id is None:
        logger.write("RADAN did not report a process ID; this session will not be quit automatically.")
        return info, False
    if int(process_id) in preexisting_visible_pids:
        raise RuntimeError(
            "RADAN automation resolved to an already-open visible RADAN session "
            f"(PID {process_id}). The import was aborted so that user session is not modified or closed. "
            "Close RADAN and run the import again, or use the live/import workflow intentionally."
        )
    return info, bool(app.created_new_instance)


def _apply_created_symbol_pen_remap(symbol_path: Path, logger: _Logger) -> dict[str, Any]:
    from remap_feature_pens_file import remap_file

    result = remap_file(symbol_path, source_pen=7, target_pen=5, arc_target_pen=9, backup_suffix=None)
    changed = result.get("changed", {})
    line_changed = int(changed.get("l", 0))
    arc_changed = int(changed.get("a", 0))
    changed_total = int(result.get("changed_total", 0))
    if changed_total:
        logger.write(
            "Applied feature pen remap to created symbol: "
            f"lines 7->5={line_changed}, arcs 7->9={arc_changed}."
        )
    else:
        logger.write("Feature pen remap checked: no line/arc pen 7 records needed remapping.")
    return result


def _convert_dxf_to_symbol(
    app: Any,
    mac: Any,
    part: ImportPart,
    symbol_path: Path,
    logger: _Logger,
    *,
    source_dxf_path: Path | None = None,
) -> dict[str, Any]:
    dxf_path = source_dxf_path or part.dxf_path
    logger.write(f"Converting {dxf_path.name} -> {symbol_path.name}")
    if symbol_path.exists():
        backup_dir = symbol_path.parent / "_headless_import_backups" / dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = _backup_file(symbol_path, backup_dir)
        logger.write(f"Backed up existing symbol: {backup_path}")
        symbol_path.unlink()

    app.open_symbol(str(dxf_path), read_only=False)
    app.visible = False
    app.interactive = False
    attr_ok = mac.ped_set_attrs2(
        part.part_name,
        part.material,
        part.strategy,
        float(part.thickness),
        UNIT_TO_RADAN[part.unit],
        DEFAULT_ORIENTATION,
    )
    app.save_active_document_as(str(symbol_path))
    app.close_active_document(True)
    if not symbol_path.exists():
        raise FileNotFoundError(str(symbol_path))
    pen_remap = _apply_created_symbol_pen_remap(symbol_path, logger)
    return {
        "part": part.part_name,
        "source_dxf_path": str(dxf_path),
        "symbol_path": str(symbol_path),
        "symbol_size": symbol_path.stat().st_size,
        "attributes_written": bool(attr_ok),
        "pen_remap": pen_remap,
    }


def _refresh_symbol_metadata_with_radan(app: Any, symbol_path: Path, logger: _Logger) -> dict[str, Any]:
    logger.write(f"Refreshing RADAN-derived symbol state: {symbol_path.name}")
    app.open_symbol(str(symbol_path), read_only=False)
    app.visible = False
    app.interactive = False
    app.save_active_document()
    app.close_active_document(True)
    return {
        "symbol_path": str(symbol_path),
        "refreshed": True,
        "symbol_size": symbol_path.stat().st_size if symbol_path.exists() else 0,
    }


def _write_native_sym_prototype(*, dxf_path: Path, template_sym: Path, out_path: Path) -> dict[str, Any]:
    from write_native_sym_prototype import write_native_prototype

    return write_native_prototype(
        dxf_path=dxf_path,
        template_sym=template_sym,
        out_path=out_path,
        allow_outside_lab=True,
        source_coordinate_digits=6,
        topology_snap_endpoints=True,
        canonicalize_endpoints=True,
    )


def _validate_native_symbol(*, dxf_path: Path, sym_path: Path) -> dict[str, Any]:
    from validate_native_sym import validate_native_sym

    return validate_native_sym(dxf_path=dxf_path, sym_path=sym_path)


def _preprocess_dxf_for_import(
    *,
    part: ImportPart,
    project_folder: Path,
    logger: _Logger,
    tolerance: float,
) -> dict[str, Any]:
    from clean_dxf_outer_profile import clean_outer_profile, preprocessed_output_paths

    cleaned_path, report_path = preprocessed_output_paths(
        dxf_path=part.dxf_path,
        project_folder=project_folder,
        tolerance=tolerance,
    )
    assert_w_drive_write_allowed(cleaned_path, operation="write preprocessed DXF working copy")
    assert_w_drive_write_allowed(report_path, operation="write DXF preprocessing report")
    logger.write(f"Preprocessing DXF outside profile: {part.dxf_path.name} -> {cleaned_path}")

    try:
        payload = clean_outer_profile(
            dxf_path=part.dxf_path,
            project_folder=project_folder,
            simplify_tolerance=tolerance,
        )
    except Exception as exc:
        payload = {
            "dxf_path": str(part.dxf_path),
            "out_path": str(cleaned_path),
            "project_folder": str(project_folder),
            "preprocessed_folder": str(cleaned_path.parent),
            "report_path": str(report_path),
            "wrote_output": False,
            "skipped_write_reason": f"{type(exc).__name__}: {exc}",
            "preprocess_error": True,
        }

    wrote_cleaned_output = bool(payload.get("wrote_output")) and cleaned_path.exists()
    if not wrote_cleaned_output:
        cleaned_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(part.dxf_path, cleaned_path)
        payload["fallback_copied_original"] = True
        payload["fallback_reason"] = payload.get("skipped_write_reason") or "cleaner did not produce an output DXF"
        payload["usable_preprocessed_path"] = str(cleaned_path)
        payload["report_path"] = str(report_path)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        logger.write(
            f"DXF preprocessing used an unsimplified L-side copy for {part.part_name}: {payload['fallback_reason']}"
        )
    else:
        payload["fallback_copied_original"] = False
        payload["usable_preprocessed_path"] = str(cleaned_path)
        payload["report_path"] = str(report_path)
        stats = payload.get("simplification", {})
        logger.write(
            f"DXF preprocessing wrote {cleaned_path.name}: "
            f"removed_vertices={stats.get('removed_vertices', 0)}, "
            f"max_deviation={stats.get('max_final_vertex_deviation', 0)}"
        )

    return {
        "source_dxf_path": cleaned_path,
        "report_path": report_path,
        "payload": payload,
    }


def _preprocess_dxf_for_synthetic_sym(
    *,
    part: ImportPart,
    project_folder: Path,
    logger: _Logger,
    tolerance: float,
) -> dict[str, Any]:
    return _preprocess_dxf_for_import(
        part=part,
        project_folder=project_folder,
        logger=logger,
        tolerance=tolerance,
    )


def _convert_dxf_to_symbol_native(
    part: ImportPart,
    symbol_path: Path,
    logger: _Logger,
    *,
    source_dxf_path: Path | None = None,
    donor_sym_path: Path | None = None,
    allow_donor: bool = False,
) -> dict[str, Any]:
    dxf_path = source_dxf_path or part.dxf_path
    donor_sym_path = donor_sym_path or DEFAULT_SYNTHETIC_DONOR_SYM
    logger.write(f"Synthetic SYM experimental: {dxf_path.name} -> {symbol_path.name}")

    backup_path: Path | None = None
    if symbol_path.exists():
        backup_dir = symbol_path.parent / "_headless_import_backups" / dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = _backup_file(symbol_path, backup_dir)
        template_path = backup_path
        template_source = "existing_symbol_backup"
        logger.write(f"Backed up existing symbol template: {backup_path}")
    else:
        if not allow_donor:
            raise RuntimeError(
                "Synthetic SYM donor creation is disabled for the Truck Nest Explorer button because donor-created "
                f"symbols failed visible RADAN validation. Missing template: {symbol_path}"
            )
        if not donor_sym_path.exists():
            raise FileNotFoundError(f"Synthetic SYM donor template not found: {donor_sym_path}")
        template_path = donor_sym_path
        template_source = "universal_donor"
        logger.write(f"LAB ONLY: using universal synthetic SYM donor template: {donor_sym_path}")

    try:
        prototype = _write_native_sym_prototype(
            dxf_path=dxf_path,
            template_sym=template_path,
            out_path=symbol_path,
        )
        validation = _validate_native_symbol(dxf_path=dxf_path, sym_path=symbol_path)
        if not bool(validation.get("passed")):
            failed_tiers = [
                str(tier.get("name"))
                for tier in validation.get("tiers", [])
                if not bool(tier.get("passed"))
            ]
            failed_text = ", ".join(failed_tiers) if failed_tiers else "unknown validation tier"
            raise RuntimeError(f"Synthetic SYM validation failed for {symbol_path.name}: {failed_text}")
        pen_remap = _apply_created_symbol_pen_remap(symbol_path, logger)
    except Exception:
        if backup_path is not None and backup_path.exists():
            shutil.copy2(backup_path, symbol_path)
            logger.write(f"Restored original symbol after native SYM failure: {symbol_path}")
        elif symbol_path.exists():
            symbol_path.unlink()
            logger.write(f"Removed failed synthetic symbol output: {symbol_path}")
        raise

    return {
        "part": part.part_name,
        "source_dxf_path": str(dxf_path),
        "symbol_path": str(symbol_path),
        "symbol_size": symbol_path.stat().st_size,
        "attributes_written": False,
        "conversion_method": "native_sym_experimental",
        "template_symbol_path": str(template_path),
        "template_source": template_source,
        "backup_symbol_path": "" if backup_path is None else str(backup_path),
        "entity_count": prototype.get("entity_count"),
        "replaced_records": prototype.get("replaced_records"),
        "pen_remap": pen_remap,
        "native_validation_passed": True,
    }


def _project_tag(name: str) -> str:
    return f"{{{RADAN_PROJECT_NS}}}{name}"


def _local_name(node: ET.Element) -> str:
    return str(node.tag).split("}", 1)[-1]


def _direct_child(parent: ET.Element, name: str) -> ET.Element | None:
    child = parent.find(_project_tag(name))
    if child is not None:
        return child
    for candidate in list(parent):
        if _local_name(candidate) == name:
            return candidate
    return None


def _set_child(parent: ET.Element, name: str, value: object) -> ET.Element:
    child = ET.SubElement(parent, _project_tag(name))
    child.text = str(value)
    return child


def _format_number(value: float) -> str:
    return f"{float(value):g}"


def _parse_int_text(value: str | None, default: int = 0) -> int:
    try:
        return int(str(value or "").strip())
    except ValueError:
        return default


def _canonical_project_path_key(value: str | Path | None) -> str:
    text = str(value or "").strip().replace("/", "\\")
    if text.startswith("\\\\?\\"):
        text = text[4:]
    if len(text) >= 2 and text[1] == ":":
        drive = text[:2].casefold()
        rest = text[2:].lstrip("\\")
        if drive == "l:":
            text = "\\\\SVRDC\\Laser" + ("\\" + rest if rest else "")
        elif drive == "w:":
            text = "\\\\SVRDC\\Workshop" + ("\\" + rest if rest else "")
    return text.rstrip("\\").casefold()


def _find_project_parts(root: ET.Element) -> ET.Element:
    project_parts = _direct_child(root, "Parts")
    if project_parts is not None:
        return project_parts

    fallback: ET.Element | None = None
    for node in root.iter():
        if _local_name(node) != "Parts":
            continue
        if fallback is None:
            fallback = node
        if _direct_child(node, "NextID") is not None or any(_local_name(child) == "Part" for child in list(node)):
            return node
    if fallback is None:
        raise RuntimeError("RPD project is missing root Parts element.")
    return fallback


def _find_project_sheets(root: ET.Element) -> ET.Element | None:
    sheets = _direct_child(root, "Sheets")
    if sheets is not None:
        return sheets

    for node in root.iter():
        if _local_name(node) != "Sheets":
            continue
        if _direct_child(node, "NextID") is not None or any(_local_name(child) == "Sheet" for child in list(node)):
            return node
    return None


def _child_text(node: ET.Element, name: str) -> str:
    child = _direct_child(node, name)
    return "" if child is None or child.text is None else str(child.text)


def _project_part_nodes(project_parts: ET.Element) -> list[ET.Element]:
    return [node for node in list(project_parts) if _local_name(node) == "Part"]


def _project_sheet_nodes(project_sheets: ET.Element | None) -> list[ET.Element]:
    if project_sheets is None:
        return []
    return [node for node in list(project_sheets) if _local_name(node) == "Sheet"]


def _project_symbol_counts(project_parts: ET.Element) -> dict[str, int]:
    counts: dict[str, int] = {}
    for part_node in _project_part_nodes(project_parts):
        symbol = _child_text(part_node, "Symbol")
        if not symbol:
            continue
        key = _canonical_project_path_key(symbol)
        counts[key] = counts.get(key, 0) + 1
    return counts


def _project_part_id_by_symbol(project_parts: ET.Element) -> dict[str, int]:
    ids: dict[str, int] = {}
    for part_node in _project_part_nodes(project_parts):
        symbol = _child_text(part_node, "Symbol")
        if not symbol:
            continue
        ids[_canonical_project_path_key(symbol)] = _parse_int_text(_child_text(part_node, "ID"), 0)
    return ids


def _project_sheet_snapshot(project_path: Path) -> dict[str, Any]:
    root = ET.parse(project_path).getroot()
    project_sheets = _find_project_sheets(root)
    sheet_nodes = _project_sheet_nodes(project_sheets)
    rows = []
    for sheet_node in sheet_nodes:
        rows.append(
            {
                "material": _child_text(sheet_node, "Material"),
                "thickness": _child_text(sheet_node, "Thickness"),
                "thick_units": _child_text(sheet_node, "ThickUnits"),
                "sheet_x": _child_text(sheet_node, "SheetX"),
                "sheet_y": _child_text(sheet_node, "SheetY"),
                "sheet_units": _child_text(sheet_node, "SheetUnits"),
                "available": _child_text(sheet_node, "NumAvailable"),
                "used": _child_text(sheet_node, "Used"),
            }
        )
    return {"sheet_count": len(sheet_nodes), "sheets": rows}


def _project_part_color(part_id: int) -> str:
    # RADAN stores these as "R, G, B". Cycle a palette observed in RADAN-created project rows.
    return PROJECT_PART_COLOR_PALETTE[(int(part_id) * 7) % len(PROJECT_PART_COLOR_PALETTE)]


def _build_project_part_element(
    part_id: int,
    part: ImportPart,
    symbol_path: Path,
    *,
    assign_project_colors: bool = False,
) -> ET.Element:
    project_color = _project_part_color(part_id) if assign_project_colors else DEFAULT_PROJECT_PART_COLOR
    node = ET.Element(_project_tag("Part"))
    _set_child(node, "ID", int(part_id))
    _set_child(node, "Symbol", str(symbol_path))
    _set_child(node, "Kit", "-")
    _set_child(node, "Number", int(part.quantity))
    _set_child(node, "NumExtra", 0)
    _set_child(node, "Priority", 5)
    _set_child(node, "Bin", 0)
    _set_child(node, "Orient", DEFAULT_ORIENTATION)
    _set_child(node, "OrientationMode", 0)
    _set_child(node, "Mirror", "n")
    _set_child(node, "CCut", "none")
    _set_child(node, "MaxCCut", 2)
    _set_child(node, "PickingCluster", "n")
    _set_child(node, "Material", part.material)
    _set_child(node, "Thickness", _format_number(part.thickness))
    _set_child(node, "ThickUnits", part.unit)
    _set_child(node, "Strategy", part.strategy)
    _set_child(node, "Exclude", "n")
    _set_child(node, "ColourWhenPartSaved", project_color)
    _set_child(node, "NestMode", "multi-part")
    _set_child(node, "Made", int(part.quantity))
    _set_child(node, "UsedInNests", "")
    return node


def _update_project_file_direct(
    project_path: Path,
    parts: list[ImportPart],
    output_folder: Path,
    *,
    assign_project_colors: bool = False,
) -> dict[str, Any]:
    tree = ET.parse(project_path)
    root = tree.getroot()
    project_parts = _find_project_parts(root)
    next_id_node = _direct_child(project_parts, "NextID")
    if next_id_node is None:
        next_id_node = ET.Element(_project_tag("NextID"))
        project_parts.insert(0, next_id_node)

    existing_ids = [
        _parse_int_text(_child_text(part_node, "ID"), 0)
        for part_node in _project_part_nodes(project_parts)
    ]
    existing_symbol_counts = _project_symbol_counts(project_parts)
    first_new_id = max(_parse_int_text(next_id_node.text, 1), max(existing_ids, default=0) + 1)
    added: list[dict[str, Any]] = []
    skipped_existing: list[dict[str, Any]] = []
    next_part_id = first_new_id
    for part in parts:
        symbol_path = part.symbol_path(output_folder)
        symbol_key = _canonical_project_path_key(symbol_path)
        if existing_symbol_counts.get(symbol_key, 0) > 0:
            skipped_existing.append(
                {
                    "part": part.part_name,
                    "symbol_path": str(symbol_path),
                    "reason": "symbol_already_in_project",
                    "existing_project_count": existing_symbol_counts[symbol_key],
                }
            )
            continue
        part_id = next_part_id
        next_part_id += 1
        project_color = _project_part_color(part_id) if assign_project_colors else DEFAULT_PROJECT_PART_COLOR
        project_parts.append(
            _build_project_part_element(
                part_id,
                part,
                symbol_path,
                assign_project_colors=assign_project_colors,
            )
        )
        existing_symbol_counts[symbol_key] = 1
        added.append(
            {
                "part": part.part_name,
                "symbol_path": str(symbol_path),
                "project_part_id": part_id,
                "colour_when_part_saved": project_color,
            }
        )
    next_id_node.text = str(next_part_id)

    if added:
        ET.indent(tree, space="  ")
        temp_path = project_path.with_name(f"{project_path.name}.tmp-{os.getpid()}")
        tree.write(temp_path, encoding="utf-8", xml_declaration=True)
        os.replace(temp_path, project_path)
    return {"added": added, "skipped_existing_project_rows": skipped_existing}


def _mac_status_ok(value: Any) -> bool:
    if value is None:
        return True
    try:
        return int(value) == 0
    except Exception:
        return bool(value)


def _set_optional_mac_property(mac: Any, name: str, value: Any, logger: _Logger) -> bool:
    try:
        setattr(mac, name, value)
    except Exception as exc:
        logger.write(f"RADAN NST optional property {name} was not set: {type(exc).__name__}: {exc}")
        return False
    return True


def _update_project_file_via_radan_nst(
    app: Any,
    project_path: Path,
    parts: list[ImportPart],
    output_folder: Path,
    *,
    logger: _Logger,
    assign_project_colors: bool = False,
) -> dict[str, Any]:
    tree = ET.parse(project_path)
    root = tree.getroot()
    project_parts = _find_project_parts(root)
    existing_symbol_counts = _project_symbol_counts(project_parts)
    added_candidates: list[ImportPart] = []
    skipped_existing: list[dict[str, Any]] = []
    for part in parts:
        symbol_path = part.symbol_path(output_folder)
        symbol_key = _canonical_project_path_key(symbol_path)
        if existing_symbol_counts.get(symbol_key, 0) > 0:
            skipped_existing.append(
                {
                    "part": part.part_name,
                    "symbol_path": str(symbol_path),
                    "reason": "symbol_already_in_project",
                    "existing_project_count": existing_symbol_counts[symbol_key],
                }
            )
            continue
        added_candidates.append(part)

    before_sheets = _project_sheet_snapshot(project_path)
    if not added_candidates:
        logger.write(
            "RADAN NST project update skipped: all CSV symbols already exist in the project."
        )
        return {
            "added": [],
            "skipped_existing_project_rows": skipped_existing,
            "sheet_observation": {
                "before": before_sheets,
                "after": before_sheets,
                "sheet_calls_made": False,
            },
        }

    logger.write(
        "Updating project through RADAN NST schedule API: "
        f"adding {len(added_candidates)} part row(s), no sheet API calls."
    )
    logger.write(f"RADAN NST sheet observation before part add: {before_sheets['sheet_count']} sheet row(s).")
    if assign_project_colors:
        logger.write("Project recoloring is not applied in RADAN NST mode; RADAN will own any row colors.")

    mac = _mac_object(app)
    if not bool(mac.prj_open(str(project_path))):
        raise RuntimeError(f"RADAN prj_open failed for {project_path}")
    start_result = mac.nst_start_adding_parts()
    if not _mac_status_ok(start_result):
        raise RuntimeError(f"RADAN nst_start_adding_parts failed with status {start_result!r}")

    added: list[dict[str, Any]] = []
    try:
        for part in added_candidates:
            symbol_path = part.symbol_path(output_folder)
            mac.NST_NAME = str(symbol_path)
            mac.NST_KIT = "-"
            mac.NST_MATERIAL = part.material
            mac.NST_THICKNESS = float(part.thickness)
            mac.NST_THICK_UNITS = part.unit
            mac.NST_STRATEGY = part.strategy
            mac.NST_NUMBER = int(part.quantity)
            mac.NST_EXTRA = 0
            mac.NST_ORIENT = DEFAULT_ORIENTATION
            mac.NST_ORIENTATION_MODE = 0
            mac.NST_PRIORITY = 5
            mac.NST_BIN = 0
            mac.NST_MIRROR = 0
            mac.NST_COMMON_CUT = 0
            _set_optional_mac_property(mac, "NST_MAX_COMMON_CUT", 2, logger)
            _set_optional_mac_property(mac, "NST_PICKING_CLUSTER", 0, logger)
            try:
                mac.PRJ_PART_NEST_MODE = mac.PRJ_PART_MULTI
            except Exception:
                _set_optional_mac_property(mac, "PRJ_PART_NEST_MODE", 0, logger)
            try:
                mac.PRJ_PART_ORIENTATION_MODE = mac.NSM_ORIENTATION_MODE_FREE
            except Exception:
                _set_optional_mac_property(mac, "PRJ_PART_ORIENTATION_MODE", 0, logger)

            add_result = mac.nst_add_part()
            if not _mac_status_ok(add_result):
                raise RuntimeError(f"RADAN nst_add_part failed for {part.part_name} with status {add_result!r}")
            added.append(
                {
                    "part": part.part_name,
                    "symbol_path": str(symbol_path),
                    "project_part_id": None,
                    "colour_when_part_saved": "RADAN NST",
                }
            )

        finish_result = mac.nst_finish_adding_parts()
        if not _mac_status_ok(finish_result):
            raise RuntimeError(f"RADAN nst_finish_adding_parts failed with status {finish_result!r}")
        if not bool(mac.prj_save()):
            raise RuntimeError("RADAN prj_save failed after NST part update.")
    finally:
        try:
            mac.prj_close()
        except Exception:
            pass

    after_sheets = _project_sheet_snapshot(project_path)
    logger.write(f"RADAN NST sheet observation after part add/save: {after_sheets['sheet_count']} sheet row(s).")
    if after_sheets["sheet_count"] == before_sheets["sheet_count"]:
        logger.write("RADAN NST observation: adding parts did not populate additional sheet rows.")
    else:
        logger.write(
            "RADAN NST observation: sheet row count changed by "
            f"{after_sheets['sheet_count'] - before_sheets['sheet_count']} without explicit sheet API calls."
        )

    refreshed_tree = ET.parse(project_path)
    refreshed_parts = _find_project_parts(refreshed_tree.getroot())
    ids_by_symbol = _project_part_id_by_symbol(refreshed_parts)
    for row in added:
        row["project_part_id"] = ids_by_symbol.get(_canonical_project_path_key(row["symbol_path"]), None)

    return {
        "added": added,
        "skipped_existing_project_rows": skipped_existing,
        "sheet_observation": {
            "before": before_sheets,
            "after": after_sheets,
            "sheet_calls_made": False,
        },
    }


def _validate_project_file_after_write(
    project_path: Path,
    parts: list[ImportPart],
    output_folder: Path,
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    root = ET.parse(project_path).getroot()
    project_parts = _find_project_parts(root)
    project_sheets = _find_project_sheets(root)
    part_nodes = _project_part_nodes(project_parts)
    sheet_nodes = _project_sheet_nodes(project_sheets)
    ids = [_parse_int_text(_child_text(part_node, "ID"), 0) for part_node in part_nodes]
    nonzero_ids = [part_id for part_id in ids if part_id > 0]
    duplicate_ids = sorted({part_id for part_id in nonzero_ids if nonzero_ids.count(part_id) > 1})
    if duplicate_ids:
        errors.append("Duplicate project part IDs: " + ", ".join(str(part_id) for part_id in duplicate_ids[:20]))
    next_id = _parse_int_text(_child_text(project_parts, "NextID"), 1)
    max_id = max(nonzero_ids, default=0)
    if next_id <= max_id:
        errors.append(f"NextID {next_id} is not greater than max part ID {max_id}.")

    symbol_counts = _project_symbol_counts(project_parts)
    missing_project_symbols: list[str] = []
    duplicate_expected_symbols: list[str] = []
    missing_symbol_files: list[str] = []
    for part in parts:
        symbol_path = part.symbol_path(output_folder)
        key = _canonical_project_path_key(symbol_path)
        count = symbol_counts.get(key, 0)
        if count < 1:
            missing_project_symbols.append(str(symbol_path))
        elif count > 1:
            duplicate_expected_symbols.append(f"{symbol_path} ({count})")
        if not symbol_path.exists():
            missing_symbol_files.append(str(symbol_path))
    if missing_project_symbols:
        errors.append(
            "Expected imported symbols missing from project: "
            + "; ".join(missing_project_symbols[:20])
        )
    if duplicate_expected_symbols:
        errors.append(
            "Expected imported symbols appear more than once in project: "
            + "; ".join(duplicate_expected_symbols[:20])
        )
    if missing_symbol_files:
        errors.append("Expected symbol files missing on disk: " + "; ".join(missing_symbol_files[:20]))

    return {
        "passed": not errors,
        "project_part_count": len(part_nodes),
        "project_sheet_count": len(sheet_nodes),
        "next_id": next_id,
        "max_part_id": max_id,
        "expected_symbol_count": len(parts),
        "errors": errors,
        "warnings": warnings,
    }


def _missing_symbol_paths(parts: list[ImportPart], output_folder: Path) -> list[Path]:
    return [
        part.symbol_path(output_folder)
        for part in parts
        if not part.symbol_path(output_folder).exists()
    ]


def _doctor_add(
    checks: list[dict[str, Any]],
    *,
    code: str,
    status: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> None:
    checks.append(
        {
            "code": code,
            "status": status,
            "message": message,
            "details": details or {},
        }
    )


def _module_available(module_name: str) -> tuple[bool, str]:
    try:
        spec = importlib.util.find_spec(module_name)
    except (ImportError, AttributeError, ValueError) as exc:
        return False, str(exc)
    if spec is None:
        return False, "module was not found"
    origin = str(spec.origin or "")
    return True, origin


def _path_from_optional_arg(value: str | None) -> Path | None:
    if value is None or not str(value).strip():
        return None
    return Path(value).expanduser().resolve()


def run_preflight_doctor(
    *,
    csv_path: Path | None = None,
    output_folder: Path | None = None,
    project_path: Path | None = None,
    backend: str = "win32com",
    allow_visible_radan: bool = False,
    native_sym_experimental: bool = False,
    preprocess_dxf_outer_profile: bool = False,
    preprocess_dxf_tolerance: float = DEFAULT_PREPROCESS_DXF_TOLERANCE,
    allow_synthetic_donor: bool = False,
    max_parts: int | None = None,
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    expected_venv = Path(r"C:\Tools\.venv").resolve()
    executable = Path(sys.executable).resolve()
    prefix = Path(sys.prefix).resolve()
    virtual_env = os.environ.get("VIRTUAL_ENV", "")
    expected_venv_key = str(expected_venv).casefold()
    venv_ok = (
        str(executable).casefold().startswith(expected_venv_key)
        or str(prefix).casefold().startswith(expected_venv_key)
        or str(Path(virtual_env).resolve()).casefold().startswith(expected_venv_key)
    )
    _doctor_add(
        checks,
        code="python_venv",
        status="pass" if venv_ok else "fail",
        message=(
            "Python is running inside the shared C:\\Tools venv."
            if venv_ok
            else "Python is not running inside the shared C:\\Tools venv."
        ),
        details={
            "expected_venv": str(expected_venv),
            "sys_executable": str(executable),
            "sys_prefix": str(prefix),
            "sys_base_prefix": str(Path(sys.base_prefix).resolve()),
            "virtual_env": virtual_env,
        },
    )

    required_modules: list[str] = []
    if preprocess_dxf_outer_profile:
        required_modules.append("clean_dxf_outer_profile")
    if native_sym_experimental:
        required_modules.extend(["ezdxf", "write_native_sym_prototype", "validate_native_sym"])
        _doctor_add(
            checks,
            code="synthetic_donor_sym",
            status="pass" if DEFAULT_SYNTHETIC_DONOR_SYM.exists() else "fail",
            message=(
                f"Synthetic donor template exists: {DEFAULT_SYNTHETIC_DONOR_SYM}"
                if DEFAULT_SYNTHETIC_DONOR_SYM.exists()
                else f"Synthetic donor template is missing: {DEFAULT_SYNTHETIC_DONOR_SYM}"
            ),
            details={"path": str(DEFAULT_SYNTHETIC_DONOR_SYM)},
        )
    else:
        required_modules.extend(["win32com.client", "pythoncom"])
    for module_name in required_modules:
        found, origin = _module_available(module_name)
        _doctor_add(
            checks,
            code=f"module_{module_name.replace('.', '_')}",
            status="pass" if found else "fail",
            message=f"Required module {module_name} is available." if found else f"Required module {module_name} is missing.",
            details={"origin": origin},
        )

    parts: list[ImportPart] | None = None
    if csv_path is None:
        _doctor_add(
            checks,
            code="csv_path",
            status="info",
            message="No CSV path was supplied; skipping CSV-specific checks.",
        )
    elif not csv_path.exists():
        _doctor_add(
            checks,
            code="csv_path",
            status="fail",
            message=f"CSV path does not exist: {csv_path}",
        )
    else:
        try:
            parts = read_import_csv(csv_path, max_parts=max_parts)
        except Exception as exc:
            _doctor_add(
                checks,
                code="csv_parse",
                status="fail",
                message=f"CSV could not be parsed: {type(exc).__name__}: {exc}",
                details={"csv_path": str(csv_path)},
            )
        else:
            _doctor_add(
                checks,
                code="csv_parse",
                status="pass",
                message=f"CSV parsed successfully with {len(parts)} part row(s).",
                details={"csv_path": str(csv_path), "part_count": len(parts), "max_parts": max_parts},
            )

    output_exists = False
    if output_folder is None:
        _doctor_add(
            checks,
            code="output_folder",
            status="info",
            message="No output folder was supplied; skipping symbol-folder checks.",
        )
    elif not output_folder.exists():
        _doctor_add(
            checks,
            code="output_folder",
            status="fail",
            message=f"Output folder does not exist: {output_folder}",
        )
    elif not output_folder.is_dir():
        _doctor_add(
            checks,
            code="output_folder",
            status="fail",
            message=f"Output folder is not a directory: {output_folder}",
        )
    else:
        output_exists = True
        _doctor_add(
            checks,
            code="output_folder",
            status="pass",
            message=f"Output folder exists: {output_folder}",
        )
        try:
            assert_w_drive_write_allowed(output_folder, operation="write RADAN symbol output")
        except RuntimeError as exc:
            _doctor_add(
                checks,
                code="w_drive_output_guard",
                status="fail",
                message=str(exc),
            )
        else:
            _doctor_add(
                checks,
                code="w_drive_output_guard",
                status="pass",
                message="Symbol output folder is not on W:.",
            )
        if preprocess_dxf_outer_profile:
            preprocessed_root = (project_path.parent if project_path is not None else output_folder) / "_preprocessed_dxfs"
            try:
                assert_w_drive_write_allowed(
                    preprocessed_root,
                    operation="write preprocessed DXF working copies",
                )
            except RuntimeError as exc:
                _doctor_add(
                    checks,
                    code="preprocessed_dxf_folder",
                    status="fail",
                    message=str(exc),
                )
            else:
                _doctor_add(
                    checks,
                    code="preprocessed_dxf_folder",
                    status="pass",
                    message=(
                        "Preprocessed DXF working copies will be written under "
                        f"{preprocessed_root}."
                    ),
                    details={"tolerance": preprocess_dxf_tolerance},
                )

    missing_symbols: list[Path] = []
    if parts is not None and output_folder is not None and output_exists:
        missing_symbols = _missing_symbol_paths(parts, output_folder)
        if missing_symbols and native_sym_experimental:
            if allow_synthetic_donor:
                _doctor_add(
                    checks,
                    code="synthetic_missing_symbols",
                    status="warn",
                    message=(
                        f"{len(missing_symbols)} symbol file(s) are missing; LAB ONLY donor mode would create them "
                        f"from {DEFAULT_SYNTHETIC_DONOR_SYM}."
                    ),
                    details={"missing_symbol_paths": [str(path) for path in missing_symbols[:20]]},
                )
            else:
                _doctor_add(
                    checks,
                    code="synthetic_missing_symbols",
                    status="fail",
                    message=(
                        f"{len(missing_symbols)} symbol file(s) are missing. Synthetic donor creation is disabled "
                        "for the Truck Nest Explorer button after visible RADAN validation failures; create symbols "
                        "with the RADAN import path first, or use the lab-only --allow-synthetic-donor CLI flag."
                    ),
                    details={"missing_symbol_paths": [str(path) for path in missing_symbols[:20]]},
                )
        elif missing_symbols:
            _doctor_add(
                checks,
                code="symbol_files",
                status="warn",
                message=f"{len(missing_symbols)} symbol file(s) are missing and will require RADAN conversion.",
                details={"missing_symbol_paths": [str(path) for path in missing_symbols[:20]]},
            )
        else:
            _doctor_add(
                checks,
                code="symbol_files",
                status="pass",
                message=f"All {len(parts)} expected symbol file(s) exist.",
            )

    if project_path is None:
        _doctor_add(
            checks,
            code="project_path",
            status="info",
            message="No RPD project was supplied; skipping project checks.",
        )
    elif not project_path.exists():
        _doctor_add(
            checks,
            code="project_path",
            status="fail",
            message=f"RPD project does not exist: {project_path}",
        )
    else:
        try:
            assert_w_drive_write_allowed(project_path, operation="write RADAN project")
        except RuntimeError as exc:
            _doctor_add(
                checks,
                code="w_drive_project_guard",
                status="fail",
                message=str(exc),
            )
        else:
            _doctor_add(
                checks,
                code="w_drive_project_guard",
                status="pass",
                message="RPD project path is not on W:.",
            )
        try:
            root = ET.parse(project_path).getroot()
            project_parts = _find_project_parts(root)
            part_nodes = _project_part_nodes(project_parts)
            ids = [_parse_int_text(_child_text(part_node, "ID"), 0) for part_node in part_nodes]
            nonzero_ids = [part_id for part_id in ids if part_id > 0]
            duplicate_ids = sorted({part_id for part_id in nonzero_ids if nonzero_ids.count(part_id) > 1})
            next_id = _parse_int_text(_child_text(project_parts, "NextID"), 1)
            max_id = max(nonzero_ids, default=0)
            if duplicate_ids:
                _doctor_add(
                    checks,
                    code="project_duplicate_ids",
                    status="fail",
                    message="RPD project has duplicate part IDs: "
                    + ", ".join(str(part_id) for part_id in duplicate_ids[:20]),
                )
            elif next_id <= max_id:
                _doctor_add(
                    checks,
                    code="project_next_id",
                    status="fail",
                    message=f"RPD NextID {next_id} is not greater than max part ID {max_id}.",
                )
            else:
                _doctor_add(
                    checks,
                    code="project_ids",
                    status="pass",
                    message=f"RPD project IDs look sane; part rows={len(part_nodes)}, NextID={next_id}.",
                )
            if parts is not None and output_folder is not None:
                symbol_counts = _project_symbol_counts(project_parts)
                existing = []
                duplicate_expected = []
                for part in parts:
                    symbol_path = part.symbol_path(output_folder)
                    count = symbol_counts.get(_canonical_project_path_key(symbol_path), 0)
                    if count > 1:
                        duplicate_expected.append(f"{symbol_path} ({count})")
                    elif count == 1:
                        existing.append(str(symbol_path))
                if duplicate_expected:
                    _doctor_add(
                        checks,
                        code="project_duplicate_expected_symbols",
                        status="fail",
                        message=(
                            "One or more expected import symbols already appears more than once in the RPD."
                        ),
                        details={"duplicate_symbols": duplicate_expected[:20]},
                    )
                elif existing:
                    _doctor_add(
                        checks,
                        code="project_existing_symbols",
                        status="warn",
                        message=(
                            f"{len(existing)} expected symbol row(s) already exist in the RPD; "
                            "repeat import will skip those rows."
                        ),
                        details={"existing_symbols": existing[:20]},
                    )
                else:
                    _doctor_add(
                        checks,
                        code="project_existing_symbols",
                        status="pass",
                        message="No expected import symbols are already present in the RPD.",
                    )
        except Exception as exc:
            _doctor_add(
                checks,
                code="project_parse",
                status="fail",
                message=f"RPD project could not be parsed: {type(exc).__name__}: {exc}",
                details={"project_path": str(project_path)},
            )

        import_lock = _ImportLock(project_path, _Logger())
        if import_lock.path.exists():
            existing_pid = import_lock._read_existing_pid()
            live = existing_pid is not None and _process_exists(existing_pid)
            _doctor_add(
                checks,
                code="import_lock",
                status="fail" if live else "warn",
                message=(
                    f"Live import lock exists for PID {existing_pid}: {import_lock.path}"
                    if live
                    else f"Stale import lock exists and can be removed on next import: {import_lock.path}"
                ),
                details={"lock_path": str(import_lock.path), "process_id": existing_pid},
            )
        else:
            _doctor_add(
                checks,
                code="import_lock",
                status="pass",
                message=f"No active import lock was found for this project.",
                details={"lock_path": str(import_lock.path)},
            )

    try:
        visible_pids = sorted(_visible_radan_process_ids())
    except Exception as exc:
        _doctor_add(
            checks,
            code="visible_radan_sessions",
            status="warn",
            message=f"Could not inspect visible RADAN sessions: {type(exc).__name__}: {exc}",
        )
    else:
        if not visible_pids:
            _doctor_add(
                checks,
                code="visible_radan_sessions",
                status="pass",
                message="No visible RADAN sessions were detected.",
            )
        elif native_sym_experimental:
            _doctor_add(
                checks,
                code="visible_radan_sessions",
                status="pass",
                message=(
                    "Visible RADAN session(s) are open, but synthetic mode does not use RADAN COM conversion."
                ),
                details={"process_ids": visible_pids},
            )
        elif missing_symbols and not allow_visible_radan:
            _doctor_add(
                checks,
                code="visible_radan_sessions",
                status="fail",
                message=(
                    "Visible RADAN session(s) are open and missing symbols would require COM conversion; "
                    "the import will block unless --allow-visible-radan is used."
                ),
                details={"process_ids": visible_pids},
            )
        elif missing_symbols:
            _doctor_add(
                checks,
                code="visible_radan_sessions",
                status="warn",
                message=(
                    "Visible RADAN session(s) are open; --allow-visible-radan permits conversion but windows may redraw."
                ),
                details={"process_ids": visible_pids},
            )
        else:
            _doctor_add(
                checks,
                code="visible_radan_sessions",
                status="warn",
                message="Visible RADAN session(s) are open, but no conversion appears necessary.",
                details={"process_ids": visible_pids},
            )

    failed = [check for check in checks if check["status"] == "fail"]
    warned = [check for check in checks if check["status"] == "warn"]
    return {
        "ok": not failed,
        "command": "doctor",
        "backend": backend,
        "native_sym_experimental": bool(native_sym_experimental),
        "preprocess_dxf_outer_profile": bool(preprocess_dxf_outer_profile),
        "preprocess_dxf_tolerance": preprocess_dxf_tolerance,
        "allow_synthetic_donor": bool(allow_synthetic_donor),
        "allow_visible_radan": bool(allow_visible_radan),
        "max_parts": max_parts,
        "csv_path": "" if csv_path is None else str(csv_path),
        "output_folder": "" if output_folder is None else str(output_folder),
        "project_path": "" if project_path is None else str(project_path),
        "fail_count": len(failed),
        "warn_count": len(warned),
        "checks": checks,
    }


def run_headless_import(
    *,
    csv_path: Path,
    output_folder: Path,
    project_path: Path,
    logger: _Logger,
    backend: str = "win32com",
    allow_visible_radan: bool = False,
    rebuild_symbols: bool = False,
    native_sym_experimental: bool = False,
    preprocess_dxf_outer_profile: bool = False,
    preprocess_dxf_tolerance: float = DEFAULT_PREPROCESS_DXF_TOLERANCE,
    allow_synthetic_donor: bool = False,
    assign_project_colors: bool = False,
    project_update_method: str = PROJECT_UPDATE_METHOD_DIRECT_XML,
    max_parts: int | None = None,
) -> dict[str, Any]:
    started_at = time.perf_counter()
    project_update_method = str(project_update_method or PROJECT_UPDATE_METHOD_DIRECT_XML).strip()
    if project_update_method not in PROJECT_UPDATE_METHODS:
        raise ValueError(
            f"Unsupported project update method {project_update_method!r}; "
            f"expected one of {', '.join(sorted(PROJECT_UPDATE_METHODS))}."
        )
    if max_parts is not None and max_parts <= 0:
        raise ValueError("max_parts must be greater than zero when supplied.")
    assert_w_drive_write_allowed(output_folder, operation="write RADAN symbol output")
    assert_w_drive_write_allowed(project_path, operation="write RADAN project")
    parts = read_import_csv(csv_path, max_parts=max_parts)
    if max_parts is not None:
        logger.write(f"Temporary part limit enabled: first {max_parts} importable CSV row(s).")
    logger.write(f"Read {len(parts)} part row(s) from {csv_path.name}.")
    parts_to_convert = [
        part
        for part in parts
        if native_sym_experimental or rebuild_symbols or not part.symbol_path(output_folder).exists()
    ]
    skipped_conversion = [
        {
            "part": part.part_name,
            "symbol_path": str(part.symbol_path(output_folder)),
            "reason": "symbol_exists",
        }
        for part in parts
        if part not in parts_to_convert
    ]
    if native_sym_experimental:
        missing_templates = [
            part.symbol_path(output_folder)
            for part in parts_to_convert
            if not part.symbol_path(output_folder).exists()
        ]
        if missing_templates and not allow_synthetic_donor:
            sample = "\n".join(str(path) for path in missing_templates[:20])
            more = len(missing_templates) - min(len(missing_templates), 20)
            if more > 0:
                sample += f"\n... (+{more} more)"
            raise RuntimeError(
                "Synthetic donor creation is disabled for the Truck Nest Explorer button because donor-created "
                "symbols failed visible RADAN validation. Create the missing symbols with the RADAN import path "
                f"first, or use the lab-only --allow-synthetic-donor CLI flag. Missing {len(missing_templates)} "
                f"template(s):\n{sample}"
            )
        if missing_templates and allow_synthetic_donor and not DEFAULT_SYNTHETIC_DONOR_SYM.exists():
            raise FileNotFoundError(f"Synthetic SYM donor template not found: {DEFAULT_SYNTHETIC_DONOR_SYM}")
        logger.write(
            "Synthetic SYM experimental mode enabled; rebuilding symbols from DXF using existing .sym files."
        )
        if missing_templates and allow_synthetic_donor:
            logger.write(
                f"LAB ONLY: {len(missing_templates)} missing symbol(s) will use donor template {DEFAULT_SYNTHETIC_DONOR_SYM}."
            )
    if preprocess_dxf_outer_profile:
        logger.write(
            "DXF preprocessing enabled; cleaned working DXF copies and reports will be written under "
            f"{project_path.parent / '_preprocessed_dxfs'} with tolerance {preprocess_dxf_tolerance}."
        )
    if assign_project_colors:
        logger.write(
            "Project part recoloring enabled; new RPD rows will use the deterministic varied color palette."
        )
    else:
        logger.write(
            "Project part recoloring disabled; new RPD rows will use the default RADAN project color."
        )
    if project_update_method == PROJECT_UPDATE_METHOD_RADAN_NST:
        logger.write(
            "Project update method: RADAN NST schedule API. Parts will be added through RADAN; "
            "sheet APIs will not be called during this test."
        )
    else:
        logger.write("Project update method: direct RPD XML reconciliation.")
    if skipped_conversion:
        logger.write(f"Reusing {len(skipped_conversion)} existing symbol(s); conversion is only needed for missing symbols.")
    if parts_to_convert:
        logger.write(f"Conversion needed for {len(parts_to_convert)} symbol(s).")
    else:
        logger.write("All symbols already exist; skipping conversion stage.")
    project_backup: Path | None = None
    converted: list[dict[str, Any]] = []
    added: list[dict[str, Any]] = []
    skipped_existing_project_rows: list[dict[str, Any]] = []
    project_validation: dict[str, Any] = {}
    conversion_started_at = 0.0
    conversion_elapsed = 0.0
    project_elapsed = 0.0
    edited_before_save = False
    edited_after_save = False

    preexisting_visible_pids = _visible_radan_process_ids()
    should_quit_app = False
    if preexisting_visible_pids:
        logger.write(
            "Visible RADAN session(s) already open before import: "
            + ", ".join(str(pid) for pid in sorted(preexisting_visible_pids))
        )
        if native_sym_experimental:
            logger.write("Synthetic SYM experimental mode does not use RADAN COM for conversion; continuing.")
        elif (parts_to_convert or project_update_method == PROJECT_UPDATE_METHOD_RADAN_NST) and not allow_visible_radan:
            sample = ", ".join(part.part_name for part in parts_to_convert[:12])
            if len(parts_to_convert) > 12:
                sample += f", ... (+{len(parts_to_convert) - 12} more)"
            if parts_to_convert:
                raise RuntimeError(
                    "A visible RADAN session is already open, and this import still needs to convert "
                    f"{len(parts_to_convert)} symbol(s): {sample}. RADAN COM automation can repeatedly redraw or "
                    "steal focus from open RADAN windows. Existing symbols are reused automatically, so rerun after "
                    "the missing symbols exist, close RADAN first, or rerun with --allow-visible-radan if you "
                    "intentionally accept that transient UI disturbance."
                )
            raise RuntimeError(
                "A visible RADAN session is already open, and this import still needs RADAN automation for "
                "project part update via RADAN NST. RADAN COM automation can repeatedly redraw or steal focus from "
                "open RADAN windows. Close RADAN first, or rerun with --allow-visible-radan if you intentionally "
                "accept that transient UI disturbance."
            )
        elif parts_to_convert or project_update_method == PROJECT_UPDATE_METHOD_RADAN_NST:
            logger.write("WARNING: --allow-visible-radan was used; open RADAN windows may redraw or steal focus during RADAN automation.")
        else:
            logger.write("Visible RADAN sessions are open, but no symbol conversion is needed; continuing to project update.")

    app = None
    quit_result = None
    quit_attempted = False
    try:
        if parts_to_convert and native_sym_experimental:
            conversion_started_at = time.perf_counter()
            for index, part in enumerate(parts_to_convert, start=1):
                symbol_path = part.symbol_path(output_folder)
                part_started_at = time.perf_counter()
                preprocess_result: dict[str, Any] | None = None
                source_dxf_path = part.dxf_path
                if preprocess_dxf_outer_profile:
                    preprocess_result = _preprocess_dxf_for_import(
                        part=part,
                        project_folder=project_path.parent,
                        logger=logger,
                        tolerance=preprocess_dxf_tolerance,
                    )
                    source_dxf_path = Path(preprocess_result["source_dxf_path"])
                converted_row = _convert_dxf_to_symbol_native(
                    part,
                    symbol_path,
                    logger,
                    source_dxf_path=source_dxf_path,
                    allow_donor=allow_synthetic_donor,
                )
                if preprocess_result is not None:
                    converted_row["preprocessed_dxf_path"] = str(preprocess_result["source_dxf_path"])
                    converted_row["preprocess_report_path"] = str(preprocess_result["report_path"])
                    converted_row["preprocess"] = preprocess_result["payload"]
                part_elapsed = time.perf_counter() - part_started_at
                converted_row["elapsed_sec"] = round(part_elapsed, 3)
                converted.append(converted_row)
                logger.write(
                    f"Synthetic generated {index}/{len(parts_to_convert)}: {part.part_name} "
                    f"({symbol_path.stat().st_size} bytes, {_format_elapsed(part_elapsed)})"
                )
        elif parts_to_convert:
            app = open_application(backend=backend, force_new_instance=True)
            info, should_quit_app = _resolve_automation_instance(app, preexisting_visible_pids, logger)
            logger.write(f"Started hidden RADAN automation instance PID {info.process_id}.")
            app.visible = False
            app.interactive = False
            mac = _mac_object(app)

            conversion_started_at = time.perf_counter()
            for index, part in enumerate(parts_to_convert, start=1):
                symbol_path = part.symbol_path(output_folder)
                part_started_at = time.perf_counter()
                preprocess_result: dict[str, Any] | None = None
                source_dxf_path = part.dxf_path
                if preprocess_dxf_outer_profile:
                    preprocess_result = _preprocess_dxf_for_import(
                        part=part,
                        project_folder=project_path.parent,
                        logger=logger,
                        tolerance=preprocess_dxf_tolerance,
                    )
                    source_dxf_path = Path(preprocess_result["source_dxf_path"])
                converted_row = _convert_dxf_to_symbol(
                    app,
                    mac,
                    part,
                    symbol_path,
                    logger,
                    source_dxf_path=source_dxf_path,
                )
                if preprocess_result is not None:
                    converted_row["preprocessed_dxf_path"] = str(preprocess_result["source_dxf_path"])
                    converted_row["preprocess_report_path"] = str(preprocess_result["report_path"])
                    converted_row["preprocess"] = preprocess_result["payload"]
                part_elapsed = time.perf_counter() - part_started_at
                converted_row["elapsed_sec"] = round(part_elapsed, 3)
                converted.append(converted_row)
                logger.write(
                    f"Converted {index}/{len(parts_to_convert)}: {part.part_name} "
                    f"({symbol_path.stat().st_size} bytes, {_format_elapsed(part_elapsed)})"
                )
        conversion_elapsed = time.perf_counter() - conversion_started_at if parts_to_convert else 0.0
        logger.write(
            "Conversion stage complete: "
            f"created={len(converted)}, reused={len(skipped_conversion)}, expected_total={len(parts)}."
        )
        symbol_refresh_rows: list[tuple[dict[str, Any], Path]] = []
        if not native_sym_experimental:
            for row in converted:
                pen_remap = row.get("pen_remap", {})
                if int(pen_remap.get("changed_total", 0) or 0) > 0:
                    symbol_path = Path(str(row["symbol_path"]))
                    row["requires_radan_resave"] = bool(pen_remap.get("requires_radan_resave"))
                    symbol_refresh_rows.append((row, symbol_path))
        if skipped_conversion:
            logger.write(f"Checking feature pen remap on {len(skipped_conversion)} reused symbol(s).")
            for index, row in enumerate(skipped_conversion, start=1):
                symbol_path = Path(str(row["symbol_path"]))
                logger.write(
                    f"Checking reused symbol pen remap {index}/{len(skipped_conversion)}: {symbol_path.name}"
                )
                pen_remap = _apply_created_symbol_pen_remap(symbol_path, logger)
                row["pen_remap"] = pen_remap
                row["pen_remap_changed_total"] = int(pen_remap.get("changed_total", 0) or 0)
                if int(pen_remap.get("changed_total", 0) or 0) > 0:
                    row["requires_radan_resave"] = bool(pen_remap.get("requires_radan_resave"))
                    symbol_refresh_rows.append((row, symbol_path))
        if symbol_refresh_rows:
            if preexisting_visible_pids and not allow_visible_radan:
                logger.write(
                    "WARNING: Direct pen remap changed "
                    f"{len(symbol_refresh_rows)} symbol(s), but RADAN open/save refresh was skipped "
                    "because visible RADAN sessions were already open. The file data is updated, but RADAN warnings "
                    "or thumbnails may remain stale until those symbols are opened and saved in RADAN."
                )
            else:
                if app is None:
                    app = open_application(backend=backend, force_new_instance=True)
                    info, should_quit_app = _resolve_automation_instance(app, preexisting_visible_pids, logger)
                    logger.write(
                        f"Started hidden RADAN automation instance PID {info.process_id} for symbol refresh."
                    )
                    app.visible = False
                    app.interactive = False
                logger.write(
                    "Refreshing RADAN-derived state for "
                    f"{len(symbol_refresh_rows)} remapped symbol(s)."
                )
                for index, (row, symbol_path) in enumerate(symbol_refresh_rows, start=1):
                    logger.write(
                        f"Refreshing remapped symbol {index}/{len(symbol_refresh_rows)}: "
                        f"{symbol_path.name}"
                    )
                    try:
                        row["radan_refresh"] = _refresh_symbol_metadata_with_radan(
                            app,
                            symbol_path,
                            logger,
                        )
                    except Exception as exc:
                        row["radan_refresh"] = {
                            "refreshed": False,
                            "symbol_path": str(symbol_path),
                            "error": f"{type(exc).__name__}: {exc}",
                        }
                        remaining = len(symbol_refresh_rows) - index
                        logger.write(
                            "WARNING: RADAN symbol refresh failed for "
                            f"{symbol_path.name}: {type(exc).__name__}: {exc}. "
                            "Continuing to project update; symbol file pen data is already remapped, but "
                            "RADAN warnings or thumbnails may remain stale until the symbol is opened and saved."
                        )
                        if remaining > 0:
                            logger.write(
                                f"WARNING: Skipping RADAN refresh for {remaining} remaining remapped symbol(s) "
                                "after the first refresh failure."
                            )
                            for skipped_row, skipped_symbol_path in symbol_refresh_rows[index:]:
                                skipped_row["radan_refresh"] = {
                                    "refreshed": False,
                                    "symbol_path": str(skipped_symbol_path),
                                    "skipped_after_error": True,
                                }
                        break
        if app is not None and project_update_method != PROJECT_UPDATE_METHOD_RADAN_NST:
            if should_quit_app:
                try:
                    quit_result = app.quit()
                except Exception as exc:
                    quit_result = False
                    logger.write(f"WARNING: RADAN Quit() failed after conversion stage: {type(exc).__name__}: {exc}")
                quit_attempted = True
            else:
                logger.write("Skipping RADAN Quit() because automation ownership was not proven.")
                quit_attempted = True

        missing_symbols = _missing_symbol_paths(parts, output_folder)
        if missing_symbols:
            sample = "\n".join(str(path) for path in missing_symbols[:20])
            more = len(missing_symbols) - min(len(missing_symbols), 20)
            if more > 0:
                sample += f"\n... (+{more} more)"
            raise RuntimeError(
                f"Cannot update RPD because {len(missing_symbols)} expected symbol file(s) are missing:\n{sample}"
            )
        logger.write(f"Verified {len(parts)} symbol file(s); starting RPD project update.")

        project_backup = _backup_project(project_path, logger)
        project_started_at = time.perf_counter()
        if project_update_method == PROJECT_UPDATE_METHOD_RADAN_NST:
            if app is None:
                app = open_application(backend=backend, force_new_instance=True)
                info, should_quit_app = _resolve_automation_instance(app, preexisting_visible_pids, logger)
                logger.write(f"Started hidden RADAN automation instance PID {info.process_id} for project update.")
                app.visible = False
                app.interactive = False
            logger.write(f"Reconciling {len(parts)} part row(s) into project through RADAN NST.")
            update_result = _update_project_file_via_radan_nst(
                app,
                project_path,
                parts,
                output_folder,
                logger=logger,
                assign_project_colors=assign_project_colors,
            )
        else:
            logger.write(f"Reconciling {len(parts)} part row(s) into project file without opening RADAN.")
            update_result = _update_project_file_direct(
                project_path,
                parts,
                output_folder,
                assign_project_colors=assign_project_colors,
            )
        added = list(update_result.get("added", []))
        skipped_existing_project_rows = list(update_result.get("skipped_existing_project_rows", []))
        if skipped_existing_project_rows:
            logger.write(
                f"Skipped {len(skipped_existing_project_rows)} project row(s) already present in the RPD."
            )
            for index, row in enumerate(skipped_existing_project_rows[:20], start=1):
                logger.write(
                    f"Skipped existing project row {index}/{len(skipped_existing_project_rows)}: "
                    f"{row['part']} ({row['symbol_path']})"
                )
            if len(skipped_existing_project_rows) > 20:
                logger.write(
                    "Skipped existing project row log truncated: "
                    f"{len(skipped_existing_project_rows) - 20} more row(s)."
                )
        project_validation = _validate_project_file_after_write(project_path, parts, output_folder)
        if not bool(project_validation.get("passed")):
            for error in project_validation.get("errors", []):
                logger.write(f"RPD post-write validation error: {error}")
            if project_backup is not None and project_backup.exists():
                shutil.copy2(project_backup, project_path)
                logger.write(f"Restored project backup after failed post-write validation: {project_backup}")
            raise RuntimeError("RPD post-write validation failed; restored project backup.")
        project_elapsed = time.perf_counter() - project_started_at
        logger.write(
            "RPD post-write validation passed: "
            f"{project_validation.get('expected_symbol_count', len(parts))} expected symbol(s), "
            f"{project_validation.get('project_part_count', 0)} project part row(s), "
            f"{project_validation.get('project_sheet_count', 0)} sheet row(s), "
            f"NextID {project_validation.get('next_id', '')}."
        )
        if project_update_method == PROJECT_UPDATE_METHOD_RADAN_NST:
            sheet_observation = update_result.get("sheet_observation", {})
            before_sheet_count = int(sheet_observation.get("before", {}).get("sheet_count", 0) or 0)
            after_sheet_count = int(sheet_observation.get("after", {}).get("sheet_count", 0) or 0)
            logger.write(
                "RADAN NST project update completed: "
                f"added={len(added)}, sheets_before={before_sheet_count}, sheets_after={after_sheet_count}, "
                "sheet_calls_made=false."
            )
        elif assign_project_colors:
            assigned_colors = {
                str(row.get("colour_when_part_saved", ""))
                for row in added
                if row.get("colour_when_part_saved")
            }
            logger.write(
                "Project part colors assigned: "
                f"{len(assigned_colors)} unique color(s) across {len(added)} added part row(s)."
            )
        else:
            logger.write(
                "Project part recoloring stayed off: "
                f"{len(added)} added part row(s) use {DEFAULT_PROJECT_PART_COLOR}."
            )
        for index, row in enumerate(added, start=1):
            logger.write(
                f"Added {index}/{len(added)} to project file: "
                f"{row['part']} (ID {row.get('project_part_id')}, color {row.get('colour_when_part_saved')})"
            )
        if app is not None and not quit_attempted:
            if should_quit_app:
                quit_result = app.quit()
                quit_attempted = True
            else:
                logger.write("Skipping RADAN Quit() because automation ownership was not proven.")
                quit_attempted = True
    finally:
        if app is not None:
            if should_quit_app and not quit_attempted:
                try:
                    quit_result = app.quit()
                except Exception:
                    pass
                quit_attempted = True
            try:
                app.close()
            except Exception:
                pass

    total_elapsed = time.perf_counter() - started_at
    logger.write(
        "Headless timing: "
        f"conversion={_format_elapsed(conversion_elapsed)}, "
        f"project={_format_elapsed(project_elapsed)}, "
        f"total={_format_elapsed(total_elapsed)}."
    )
    return {
        "ok": True,
        "csv_path": str(csv_path),
        "output_folder": str(output_folder),
        "project_path": str(project_path),
        "preprocess_dxf_outer_profile": bool(preprocess_dxf_outer_profile),
        "preprocess_dxf_tolerance": preprocess_dxf_tolerance,
        "allow_synthetic_donor": bool(allow_synthetic_donor),
        "assign_project_colors": bool(assign_project_colors),
        "project_update_method": project_update_method,
        "max_parts": max_parts,
        "project_backup": "" if project_backup is None else str(project_backup),
        "part_count": len(parts),
        "conversion_elapsed_sec": round(conversion_elapsed, 3),
        "project_elapsed_sec": round(project_elapsed, 3),
        "total_elapsed_sec": round(total_elapsed, 3),
        "converted": converted,
        "skipped_conversion": skipped_conversion,
        "added": added,
        "skipped_existing_project_rows": skipped_existing_project_rows,
        "project_validation": project_validation,
        "conversion_method": "native_sym_experimental" if native_sym_experimental else "radan_com",
        "edited_before_save": edited_before_save,
        "edited_after_save": edited_after_save,
        "quit_result": bool(quit_result),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Headlessly import an inventor_to_radan CSV into a RADAN project.")
    parser.add_argument("--csv", help="Generated inventor_to_radan _Radan.csv path.")
    parser.add_argument("--output-folder", help="Folder where generated RADAN symbols should be saved.")
    parser.add_argument("--project", help="RPD project to update.")
    parser.add_argument("--kitter-launcher", help=argparse.SUPPRESS)
    parser.add_argument("--backend", default="win32com", help="RADAN COM backend to use.")
    parser.add_argument("--log-file", help="Optional progress log file for Truck Nest Explorer.")
    parser.add_argument(
        "--doctor",
        action="store_true",
        help="Run environment and import preflight checks without modifying symbols or the RPD.",
    )
    parser.add_argument(
        "--allow-visible-radan",
        action="store_true",
        help="Allow import while visible RADAN sessions are open; this may cause those windows to redraw or steal focus.",
    )
    parser.add_argument(
        "--rebuild-symbols",
        action="store_true",
        help="Recreate symbols even when matching .sym files already exist.",
    )
    parser.add_argument(
        "--native-sym-experimental",
        action="store_true",
        help=(
            "Rebuild symbols with the experimental synthetic DXF-to-SYM writer using existing .sym files as templates; "
            "does not use RADAN COM during conversion."
        ),
    )
    parser.add_argument(
        "--preprocess-dxf-outer-profile",
        action="store_true",
        help=(
            "Before symbol generation, write an ezdxf-cleaned L-side working DXF under "
            "_preprocessed_dxfs and ask the selected converter to use that copy."
        ),
    )
    parser.add_argument(
        "--preprocess-dxf-tolerance",
        type=float,
        default=DEFAULT_PREPROCESS_DXF_TOLERANCE,
        help="Local outside-profile simplification tolerance for --preprocess-dxf-outer-profile.",
    )
    parser.add_argument(
        "--allow-synthetic-donor",
        action="store_true",
        help=(
            "LAB ONLY: allow missing symbols to be created from donor.sym. "
            "This is disabled for the Truck Nest Explorer button after visible RADAN validation failures."
        ),
    )
    parser.add_argument(
        "--assign-project-colors",
        action="store_true",
        help="Assign deterministic varied ColourWhenPartSaved values to new RPD project rows.",
    )
    parser.add_argument(
        "--project-update-method",
        choices=sorted(PROJECT_UPDATE_METHODS),
        default=PROJECT_UPDATE_METHOD_DIRECT_XML,
        help=(
            "How to reconcile imported symbols into the project: direct-xml edits the RPD directly; "
            "radan-nst uses RADAN's NST schedule API to add parts and observes sheets without calling sheet APIs."
        ),
    )
    parser.add_argument(
        "--max-parts",
        type=int,
        help="Temporary test limiter: import only the first N importable CSV rows.",
    )
    args = parser.parse_args()

    logger = _Logger(Path(args.log_file).expanduser().resolve() if args.log_file else None)

    if args.doctor:
        payload = run_preflight_doctor(
            csv_path=_path_from_optional_arg(args.csv),
            output_folder=_path_from_optional_arg(args.output_folder),
            project_path=_path_from_optional_arg(args.project),
            backend=args.backend,
            allow_visible_radan=bool(args.allow_visible_radan),
            native_sym_experimental=bool(args.native_sym_experimental),
            preprocess_dxf_outer_profile=bool(args.preprocess_dxf_outer_profile),
            preprocess_dxf_tolerance=float(args.preprocess_dxf_tolerance),
            allow_synthetic_donor=bool(args.allow_synthetic_donor),
            max_parts=args.max_parts,
        )
        logger.write(
            "RADAN CSV import doctor complete: "
            f"ok={payload['ok']}, fail_count={payload['fail_count']}, warn_count={payload['warn_count']}."
        )
        for check in payload["checks"]:
            logger.write(f"Doctor {check['status'].upper()}: {check['code']} - {check['message']}")
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0 if bool(payload["ok"]) else 1

    missing_required = [
        option
        for option, value in (
            ("--csv", args.csv),
            ("--output-folder", args.output_folder),
            ("--project", args.project),
        )
        if value is None or not str(value).strip()
    ]
    if missing_required:
        parser.error("the following arguments are required unless --doctor is used: " + ", ".join(missing_required))

    csv_path = Path(args.csv).expanduser().resolve()
    output_folder = Path(args.output_folder).expanduser().resolve()
    project_path = Path(args.project).expanduser().resolve()

    if not csv_path.exists():
        raise SystemExit(f"CSV not found: {csv_path}")
    if not output_folder.exists():
        raise SystemExit(f"Output folder not found: {output_folder}")
    if not project_path.exists():
        raise SystemExit(f"Project not found: {project_path}")
    try:
        with _ImportLock(project_path, logger):
            payload = run_headless_import(
                csv_path=csv_path,
                output_folder=output_folder,
                project_path=project_path,
                logger=logger,
                backend=args.backend,
                allow_visible_radan=bool(args.allow_visible_radan),
                rebuild_symbols=bool(args.rebuild_symbols),
                native_sym_experimental=bool(args.native_sym_experimental),
                preprocess_dxf_outer_profile=bool(args.preprocess_dxf_outer_profile),
                preprocess_dxf_tolerance=float(args.preprocess_dxf_tolerance),
                allow_synthetic_donor=bool(args.allow_synthetic_donor),
                assign_project_colors=bool(args.assign_project_colors),
                project_update_method=str(args.project_update_method),
                max_parts=args.max_parts,
            )
    except Exception as exc:
        logger.write(f"ERROR: {type(exc).__name__}: {exc}")
        return 1
    logger.write("Headless RADAN CSV import completed.")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
