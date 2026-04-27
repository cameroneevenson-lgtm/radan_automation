from __future__ import annotations

import argparse
import colorsys
import csv
import ctypes
import datetime as dt
import hashlib
import json
import os
import shutil
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from radan_com import list_visible_radan_sessions, open_application


UNIT_TO_RADAN = {"mm": 0, "in": 1, "swg": 2}
DEFAULT_ORIENTATION = 3
RADAN_PROJECT_NS = "http://www.radan.com/ns/project"
ET.register_namespace("", RADAN_PROJECT_NS)


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
            self.log_file.parent.mkdir(parents=True, exist_ok=True)
            self.log_file.write_text("", encoding="utf-8")

    def write(self, message: str) -> None:
        stamp = dt.datetime.now().strftime("%H:%M:%S")
        line = f"[{stamp}] {message}"
        print(line, flush=True)
        if self.log_file is not None:
            with self.log_file.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")


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


def read_import_csv(csv_path: Path) -> list[ImportPart]:
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
    backup_path = project_path.with_name(f"{project_path.stem}_before_headless_import_{stamp}{project_path.suffix}")
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


def _convert_dxf_to_symbol(app: Any, mac: Any, part: ImportPart, symbol_path: Path, logger: _Logger) -> dict[str, Any]:
    logger.write(f"Converting {part.dxf_path.name} -> {symbol_path.name}")
    if symbol_path.exists():
        backup_dir = symbol_path.parent / "_headless_import_backups" / dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = _backup_file(symbol_path, backup_dir)
        logger.write(f"Backed up existing symbol: {backup_path}")
        symbol_path.unlink()

    app.open_symbol(str(part.dxf_path), read_only=False)
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
    return {
        "part": part.part_name,
        "symbol_path": str(symbol_path),
        "symbol_size": symbol_path.stat().st_size,
        "attributes_written": bool(attr_ok),
    }


def _project_tag(name: str) -> str:
    return f"{{{RADAN_PROJECT_NS}}}{name}"


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


def _project_part_color(part_id: int) -> str:
    # RADAN stores these as "R, G, B". Keep colors print-friendly and deterministic.
    hue = (int(part_id) * 0.618033988749895) % 1.0
    saturation = 0.72 + ((int(part_id) * 17) % 4) * 0.06
    value = 0.82 + ((int(part_id) * 29) % 3) * 0.06
    red, green, blue = colorsys.hsv_to_rgb(hue, min(saturation, 0.9), min(value, 0.94))
    channels = [
        max(31, min(223, int(round(channel * 255))))
        for channel in (red, green, blue)
    ]
    return f"{channels[0]}, {channels[1]}, {channels[2]}"


def _build_project_part_element(part_id: int, part: ImportPart, symbol_path: Path) -> ET.Element:
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
    _set_child(node, "ColourWhenPartSaved", _project_part_color(part_id))
    _set_child(node, "NestMode", "multi-part")
    _set_child(node, "Made", 0)
    return node


def _update_project_file_direct(project_path: Path, parts: list[ImportPart], output_folder: Path) -> list[dict[str, Any]]:
    tree = ET.parse(project_path)
    root = tree.getroot()
    project_parts = root.find(_project_tag("Parts"))
    if project_parts is None:
        raise RuntimeError(f"RPD project is missing root Parts element: {project_path}")
    next_id_node = project_parts.find(_project_tag("NextID"))
    if next_id_node is None:
        next_id_node = ET.Element(_project_tag("NextID"))
        project_parts.insert(0, next_id_node)

    existing_ids = [
        _parse_int_text(part_node.findtext(_project_tag("ID")), 0)
        for part_node in project_parts.findall(_project_tag("Part"))
    ]
    first_new_id = max(_parse_int_text(next_id_node.text, 1), max(existing_ids, default=0) + 1)
    added: list[dict[str, Any]] = []
    for offset, part in enumerate(parts):
        part_id = first_new_id + offset
        symbol_path = part.symbol_path(output_folder)
        project_parts.append(_build_project_part_element(part_id, part, symbol_path))
        added.append(
            {
                "part": part.part_name,
                "symbol_path": str(symbol_path),
                "project_part_id": part_id,
                "colour_when_part_saved": _project_part_color(part_id),
            }
        )
    next_id_node.text = str(first_new_id + len(parts))

    ET.indent(tree, space="  ")
    temp_path = project_path.with_name(f"{project_path.name}.tmp-{os.getpid()}")
    tree.write(temp_path, encoding="utf-8", xml_declaration=True)
    os.replace(temp_path, project_path)
    return added


def _missing_symbol_paths(parts: list[ImportPart], output_folder: Path) -> list[Path]:
    return [
        part.symbol_path(output_folder)
        for part in parts
        if not part.symbol_path(output_folder).exists()
    ]


def run_headless_import(
    *,
    csv_path: Path,
    output_folder: Path,
    project_path: Path,
    logger: _Logger,
    backend: str = "win32com",
    allow_visible_radan: bool = False,
    rebuild_symbols: bool = False,
) -> dict[str, Any]:
    started_at = time.perf_counter()
    parts = read_import_csv(csv_path)
    logger.write(f"Read {len(parts)} part row(s) from {csv_path.name}.")
    parts_to_convert = [
        part
        for part in parts
        if rebuild_symbols or not part.symbol_path(output_folder).exists()
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
    if skipped_conversion:
        logger.write(f"Reusing {len(skipped_conversion)} existing symbol(s); conversion is only needed for missing symbols.")
    if parts_to_convert:
        logger.write(f"Conversion needed for {len(parts_to_convert)} symbol(s).")
    else:
        logger.write("All symbols already exist; skipping conversion stage.")
    project_backup: Path | None = None
    converted: list[dict[str, Any]] = []
    added: list[dict[str, Any]] = []
    conversion_started_at = 0.0
    conversion_elapsed = 0.0
    project_elapsed = 0.0
    edited_before_save = False
    edited_after_save = False

    preexisting_visible_pids = _visible_radan_process_ids()
    if preexisting_visible_pids:
        logger.write(
            "Visible RADAN session(s) already open before import: "
            + ", ".join(str(pid) for pid in sorted(preexisting_visible_pids))
        )
        if parts_to_convert and not allow_visible_radan:
            sample = ", ".join(part.part_name for part in parts_to_convert[:12])
            if len(parts_to_convert) > 12:
                sample += f", ... (+{len(parts_to_convert) - 12} more)"
            raise RuntimeError(
                "A visible RADAN session is already open, and this import still needs to convert "
                f"{len(parts_to_convert)} symbol(s): {sample}. The conversion stage can repeatedly redraw or "
                "steal focus from open RADAN windows. Existing symbols are reused automatically, so rerun after "
                "the missing symbols exist, close RADAN first, or rerun with --allow-visible-radan if you "
                "intentionally accept that transient UI disturbance."
            )
        if parts_to_convert:
            logger.write("WARNING: --allow-visible-radan was used; open RADAN windows may redraw or steal focus during conversion.")
        else:
            logger.write("Visible RADAN sessions are open, but no symbol conversion is needed; continuing to project update.")

    app = None
    quit_result = None
    try:
        if parts_to_convert:
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
                converted_row = _convert_dxf_to_symbol(app, mac, part, symbol_path, logger)
                part_elapsed = time.perf_counter() - part_started_at
                converted_row["elapsed_sec"] = round(part_elapsed, 3)
                converted.append(converted_row)
                logger.write(
                    f"Converted {index}/{len(parts_to_convert)}: {part.part_name} "
                    f"({symbol_path.stat().st_size} bytes, {_format_elapsed(part_elapsed)})"
                )
            if should_quit_app:
                quit_result = app.quit()
            else:
                logger.write("Skipping RADAN Quit() because automation ownership was not proven.")
        conversion_elapsed = time.perf_counter() - conversion_started_at if parts_to_convert else 0.0
        logger.write(
            "Conversion stage complete: "
            f"created={len(converted)}, reused={len(skipped_conversion)}, expected_total={len(parts)}."
        )

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
        logger.write(f"Adding {len(parts)} part row(s) to project file without opening RADAN.")
        added = _update_project_file_direct(project_path, parts, output_folder)
        project_elapsed = time.perf_counter() - project_started_at
        for index, row in enumerate(added, start=1):
            logger.write(
                f"Added {index}/{len(parts)} to project file: "
                f"{row['part']} (ID {row['project_part_id']})"
            )
    finally:
        if app is not None:
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
        "project_backup": "" if project_backup is None else str(project_backup),
        "part_count": len(parts),
        "conversion_elapsed_sec": round(conversion_elapsed, 3),
        "project_elapsed_sec": round(project_elapsed, 3),
        "total_elapsed_sec": round(total_elapsed, 3),
        "converted": converted,
        "skipped_conversion": skipped_conversion,
        "added": added,
        "project_update_method": "direct_xml",
        "edited_before_save": edited_before_save,
        "edited_after_save": edited_after_save,
        "quit_result": bool(quit_result),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Headlessly import an inventor_to_radan CSV into a RADAN project.")
    parser.add_argument("--csv", required=True, help="Generated inventor_to_radan _Radan.csv path.")
    parser.add_argument("--output-folder", required=True, help="Folder where generated RADAN symbols should be saved.")
    parser.add_argument("--project", required=True, help="RPD project to update.")
    parser.add_argument("--kitter-launcher", help=argparse.SUPPRESS)
    parser.add_argument("--backend", default="win32com", help="RADAN COM backend to use.")
    parser.add_argument("--log-file", help="Optional progress log file for Truck Nest Explorer.")
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
    args = parser.parse_args()

    csv_path = Path(args.csv).expanduser().resolve()
    output_folder = Path(args.output_folder).expanduser().resolve()
    project_path = Path(args.project).expanduser().resolve()
    logger = _Logger(Path(args.log_file).expanduser().resolve() if args.log_file else None)

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
            )
    except Exception as exc:
        logger.write(f"ERROR: {type(exc).__name__}: {exc}")
        return 1
    logger.write("Headless RADAN CSV import completed.")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
