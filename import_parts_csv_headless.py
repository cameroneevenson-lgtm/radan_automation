from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from radan_com import open_application


UNIT_TO_RADAN = {"mm": 0, "in": 1, "swg": 2}
DEFAULT_ORIENTATION = 3


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


def _launch_kitter(kitter_launcher: Path | None, project_path: Path, logger: _Logger) -> None:
    if kitter_launcher is None:
        logger.write("No RADAN Kitter launcher was provided; skipping Kitter launch.")
        return
    suffix = kitter_launcher.suffix.casefold()
    if suffix in {".bat", ".cmd"}:
        command = ["cmd.exe", "/c", str(kitter_launcher), str(project_path)]
    else:
        command = [str(kitter_launcher), str(project_path)]
    logger.write(f"Launching RADAN Kitter: {' '.join(command)}")
    subprocess.Popen(
        command,
        cwd=str(kitter_launcher.parent),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


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


def _add_part_to_project(mac: Any, part: ImportPart, symbol_path: Path) -> int:
    mac.prj_clear_part_data()
    mac.PRJ_PART_FILENAME = str(symbol_path)
    mac.PRJ_PART_KIT_FILENAME = ""
    mac.PRJ_PART_NUMBER_REQUIRED = int(part.quantity)
    mac.PRJ_PART_EXTRA_ALLOWED = 0
    mac.PRJ_PART_PRIORITY = 5
    mac.PRJ_PART_BIN = 0
    mac.PRJ_PART_ORIENT = DEFAULT_ORIENTATION
    mac.PRJ_PART_ORIENTATION_MODE = 0
    mac.PRJ_PART_MIRROR = False
    mac.PRJ_PART_COMMON_CUT = 0
    mac.PRJ_PART_MAX_COMMON_CUT = 2
    mac.PRJ_PART_PICKING_CLUSTER = False
    mac.PRJ_PART_MATERIAL = part.material
    mac.PRJ_PART_THICKNESS = float(part.thickness)
    mac.PRJ_PART_THICK_UNITS = part.unit
    mac.PRJ_PART_STRATEGY = part.strategy
    try:
        mac.PRJ_PART_NEST_MODE = mac.PRJ_PART_MULTI
    except Exception:
        pass
    mac.PRJ_PART_EXCLUDE = False
    return int(mac.prj_add_part())


def run_headless_import(
    *,
    csv_path: Path,
    output_folder: Path,
    project_path: Path,
    kitter_launcher: Path | None,
    logger: _Logger,
    backend: str = "win32com",
) -> dict[str, Any]:
    started_at = time.perf_counter()
    parts = read_import_csv(csv_path)
    logger.write(f"Read {len(parts)} part row(s) from {csv_path.name}.")
    project_backup = _backup_project(project_path, logger)
    converted: list[dict[str, Any]] = []
    added: list[dict[str, Any]] = []
    conversion_started_at = 0.0
    conversion_elapsed = 0.0
    project_elapsed = 0.0

    app = None
    try:
        app = open_application(backend=backend, force_new_instance=True)
        info = app.info()
        logger.write(f"Started hidden RADAN automation instance PID {info.process_id}.")
        app.visible = False
        app.interactive = False
        mac = _mac_object(app)

        conversion_started_at = time.perf_counter()
        for index, part in enumerate(parts, start=1):
            symbol_path = part.symbol_path(output_folder)
            part_started_at = time.perf_counter()
            converted_row = _convert_dxf_to_symbol(app, mac, part, symbol_path, logger)
            part_elapsed = time.perf_counter() - part_started_at
            converted_row["elapsed_sec"] = round(part_elapsed, 3)
            converted.append(converted_row)
            logger.write(
                f"Converted {index}/{len(parts)}: {part.part_name} "
                f"({symbol_path.stat().st_size} bytes, {_format_elapsed(part_elapsed)})"
            )
        conversion_elapsed = time.perf_counter() - conversion_started_at

        project_started_at = time.perf_counter()
        logger.write(f"Opening project: {project_path}")
        if not mac.prj_open(str(project_path)):
            raise RuntimeError(f"RADAN could not open project: {project_path}")
        for index, part in enumerate(parts, start=1):
            add_started_at = time.perf_counter()
            symbol_path = part.symbol_path(output_folder)
            add_result = _add_part_to_project(mac, part, symbol_path)
            add_elapsed = time.perf_counter() - add_started_at
            added.append(
                {
                    "part": part.part_name,
                    "symbol_path": str(symbol_path),
                    "add_result": add_result,
                    "elapsed_sec": round(add_elapsed, 3),
                }
            )
            if add_result <= 0:
                raise RuntimeError(f"RADAN did not add part {part.part_name}; prj_add_part returned {add_result}.")
            logger.write(f"Added {index}/{len(parts)} to project: {part.part_name} ({_format_elapsed(add_elapsed)})")

        edited_before_save = bool(mac.prj_is_edited())
        logger.write("Saving RADAN project.")
        if not mac.prj_save():
            raise RuntimeError(f"RADAN could not save project: {project_path}")
        edited_after_save = bool(mac.prj_is_edited())
        if not mac.prj_close():
            raise RuntimeError("RADAN could not close the project.")
        quit_result = app.quit()
        project_elapsed = time.perf_counter() - project_started_at
    finally:
        if app is not None:
            try:
                app.close()
            except Exception:
                pass

    _launch_kitter(kitter_launcher, project_path, logger)
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
        "project_backup": str(project_backup),
        "part_count": len(parts),
        "conversion_elapsed_sec": round(conversion_elapsed, 3),
        "project_elapsed_sec": round(project_elapsed, 3),
        "total_elapsed_sec": round(total_elapsed, 3),
        "converted": converted,
        "added": added,
        "edited_before_save": edited_before_save,
        "edited_after_save": edited_after_save,
        "quit_result": bool(quit_result),
        "kitter_launcher": None if kitter_launcher is None else str(kitter_launcher),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Headlessly import an inventor_to_radan CSV into a RADAN project.")
    parser.add_argument("--csv", required=True, help="Generated inventor_to_radan _Radan.csv path.")
    parser.add_argument("--output-folder", required=True, help="Folder where generated RADAN symbols should be saved.")
    parser.add_argument("--project", required=True, help="RPD project to update.")
    parser.add_argument("--kitter-launcher", help="RADAN Kitter launcher to start after save/close.")
    parser.add_argument("--backend", default="win32com", help="RADAN COM backend to use.")
    parser.add_argument("--log-file", help="Optional progress log file for Truck Nest Explorer.")
    args = parser.parse_args()

    csv_path = Path(args.csv).expanduser().resolve()
    output_folder = Path(args.output_folder).expanduser().resolve()
    project_path = Path(args.project).expanduser().resolve()
    kitter_launcher = Path(args.kitter_launcher).expanduser().resolve() if args.kitter_launcher else None
    logger = _Logger(Path(args.log_file).expanduser().resolve() if args.log_file else None)

    if not csv_path.exists():
        raise SystemExit(f"CSV not found: {csv_path}")
    if not output_folder.exists():
        raise SystemExit(f"Output folder not found: {output_folder}")
    if not project_path.exists():
        raise SystemExit(f"Project not found: {project_path}")
    if kitter_launcher is not None and not kitter_launcher.exists():
        raise SystemExit(f"RADAN Kitter launcher not found: {kitter_launcher}")

    payload = run_headless_import(
        csv_path=csv_path,
        output_folder=output_folder,
        project_path=project_path,
        kitter_launcher=kitter_launcher,
        logger=logger,
        backend=args.backend,
    )
    logger.write("Headless RADAN CSV import completed.")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
