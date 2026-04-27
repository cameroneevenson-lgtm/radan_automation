from __future__ import annotations

import argparse
import csv
import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import ezdxf


DDC_RE = re.compile(
    r'<RadanFile\s+extension="ddc">\s*<!\[CDATA\[(.*?)\]\]>\s*</RadanFile>',
    re.DOTALL,
)

GEOMETRY_TYPES = {"LINE", "ARC", "CIRCLE"}
EXPECTED_RECORD_BY_DXF = {
    "LINE": "G",
    "ARC": "H",
    "CIRCLE": "H",
}
KNOWN_PEN_BY_LAYER = {
    "IV_INTERIOR_PROFILES": "1",
    "IV_MARK_SURFACE": "7",
}


@dataclass(frozen=True)
class Bounds:
    min_x: float
    min_y: float
    max_x: float
    max_y: float

    @property
    def width(self) -> float:
        return self.max_x - self.min_x

    @property
    def height(self) -> float:
        return self.max_y - self.min_y

    def as_dict(self) -> dict[str, float]:
        return {
            "min_x": self.min_x,
            "min_y": self.min_y,
            "max_x": self.max_x,
            "max_y": self.max_y,
            "width": self.width,
            "height": self.height,
        }


def _round_float(value: float, digits: int = 9) -> float:
    rounded = round(float(value), digits)
    if rounded == 0:
        return 0.0
    return rounded


def _point2(values: Any) -> list[float]:
    return [_round_float(values[0]), _round_float(values[1])]


def _angle_norm(angle: float) -> float:
    return float(angle) % 360.0


def _angle_on_ccw_sweep(angle: float, start: float, end: float, *, epsilon: float = 1e-9) -> bool:
    angle = _angle_norm(angle)
    start = _angle_norm(start)
    end = _angle_norm(end)
    sweep = (end - start) % 360.0
    offset = (angle - start) % 360.0
    return offset <= sweep + epsilon


def _arc_point(center: Any, radius: float, angle_degrees: float) -> list[float]:
    radians = math.radians(float(angle_degrees))
    return [
        _round_float(float(center[0]) + float(radius) * math.cos(radians)),
        _round_float(float(center[1]) + float(radius) * math.sin(radians)),
    ]


def _entity_extent_points(entity: Any) -> list[list[float]]:
    entity_type = entity.dxftype()
    if entity_type == "LINE":
        return [_point2(entity.dxf.start), _point2(entity.dxf.end)]
    if entity_type == "CIRCLE":
        center = entity.dxf.center
        radius = float(entity.dxf.radius)
        return [
            [_round_float(float(center[0]) - radius), _round_float(float(center[1]))],
            [_round_float(float(center[0]) + radius), _round_float(float(center[1]))],
            [_round_float(float(center[0])), _round_float(float(center[1]) - radius)],
            [_round_float(float(center[0])), _round_float(float(center[1]) + radius)],
        ]
    if entity_type == "ARC":
        center = entity.dxf.center
        radius = float(entity.dxf.radius)
        start = float(entity.dxf.start_angle)
        end = float(entity.dxf.end_angle)
        angles = [start, end]
        for cardinal in (0.0, 90.0, 180.0, 270.0):
            if _angle_on_ccw_sweep(cardinal, start, end):
                angles.append(cardinal)
        return [_arc_point(center, radius, angle) for angle in angles]
    return []


def _bounds_for_entities(entities: list[Any]) -> Bounds:
    points: list[list[float]] = []
    for entity in entities:
        points.extend(_entity_extent_points(entity))
    if not points:
        return Bounds(0.0, 0.0, 0.0, 0.0)
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return Bounds(min(xs), min(ys), max(xs), max(ys))


def _normalize_point(point: list[float], bounds: Bounds) -> list[float]:
    return [_round_float(point[0] - bounds.min_x), _round_float(point[1] - bounds.min_y)]


def _dxf_entity_row(entity: Any, bounds: Bounds) -> dict[str, Any]:
    entity_type = entity.dxftype()
    row: dict[str, Any] = {
        "type": entity_type,
        "layer": str(entity.dxf.layer),
    }
    if entity_type == "LINE":
        start = _point2(entity.dxf.start)
        end = _point2(entity.dxf.end)
        row["start"] = start
        row["end"] = end
        row["normalized_start"] = _normalize_point(start, bounds)
        row["normalized_end"] = _normalize_point(end, bounds)
    elif entity_type == "ARC":
        center = _point2(entity.dxf.center)
        row["center"] = center
        row["normalized_center"] = _normalize_point(center, bounds)
        row["radius"] = _round_float(float(entity.dxf.radius))
        row["start_angle"] = _round_float(float(entity.dxf.start_angle))
        row["end_angle"] = _round_float(float(entity.dxf.end_angle))
        row["normalized_start_point"] = _normalize_point(
            _arc_point(entity.dxf.center, float(entity.dxf.radius), float(entity.dxf.start_angle)),
            bounds,
        )
        row["normalized_end_point"] = _normalize_point(
            _arc_point(entity.dxf.center, float(entity.dxf.radius), float(entity.dxf.end_angle)),
            bounds,
        )
    elif entity_type == "CIRCLE":
        center = _point2(entity.dxf.center)
        row["center"] = center
        row["normalized_center"] = _normalize_point(center, bounds)
        row["radius"] = _round_float(float(entity.dxf.radius))
    return row


def read_dxf_entities(path: Path) -> tuple[list[dict[str, Any]], Bounds]:
    doc = ezdxf.readfile(path)
    entities = [entity for entity in doc.modelspace() if entity.dxftype() in GEOMETRY_TYPES]
    bounds = _bounds_for_entities(entities)
    return [_dxf_entity_row(entity, bounds) for entity in entities], bounds


def read_ddc_records(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8", errors="replace")
    match = DDC_RE.search(text)
    if match is None:
        raise RuntimeError(f"No DDC RadanFile block found in {path}")

    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(match.group(1).splitlines(), start=1):
        if not line.strip():
            continue
        fields = line.split(",")
        record_type = fields[0]
        if record_type not in {"G", "H"}:
            continue
        geometry_data = fields[10] if len(fields) > 10 else ""
        records.append(
            {
                "line_number": line_number,
                "record": record_type,
                "identifier": fields[3] if len(fields) > 3 else "",
                "pen": fields[8] if len(fields) > 8 else "",
                "geometry_data": geometry_data,
                "tokens": geometry_data.split(".") if geometry_data else [],
                "field_count": len(fields),
                "raw": line,
            }
        )
    return records


def _pair_rows(dxf_rows: list[dict[str, Any]], ddc_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    pairs: list[dict[str, Any]] = []
    for index, (dxf_row, ddc_row) in enumerate(zip(dxf_rows, ddc_rows), start=1):
        expected_record = EXPECTED_RECORD_BY_DXF.get(str(dxf_row["type"]), "")
        expected_pen = KNOWN_PEN_BY_LAYER.get(str(dxf_row["layer"]))
        pairs.append(
            {
                "index": index,
                "expected_record": expected_record,
                "type_match": ddc_row["record"] == expected_record,
                "expected_pen": expected_pen,
                "known_pen_match": expected_pen is None or str(ddc_row["pen"]) == expected_pen,
                "dxf": dxf_row,
                "ddc": ddc_row,
            }
        )
    return pairs


def build_part_corpus(dxf_path: Path, sym_path: Path) -> dict[str, Any]:
    dxf_rows, bounds = read_dxf_entities(dxf_path)
    ddc_rows = read_ddc_records(sym_path)
    pairs = _pair_rows(dxf_rows, ddc_rows)
    count_match = len(dxf_rows) == len(ddc_rows)
    type_mismatch_count = sum(1 for pair in pairs if not pair["type_match"])
    known_pen_mismatch_count = sum(1 for pair in pairs if not pair["known_pen_match"])
    return {
        "part": dxf_path.stem,
        "dxf_path": str(dxf_path),
        "sym_path": str(sym_path),
        "bounds": bounds.as_dict(),
        "dxf_count": len(dxf_rows),
        "ddc_count": len(ddc_rows),
        "count_match": count_match,
        "type_mismatch_count": type_mismatch_count,
        "known_pen_mismatch_count": known_pen_mismatch_count,
        "pairs": pairs,
    }


def _iter_csv_dxf_paths(csv_path: Path) -> list[Path]:
    paths: list[Path] = []
    with csv_path.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.reader(handle):
            if not row or all(not cell.strip() for cell in row):
                continue
            paths.append(Path(row[0].strip()))
    return paths


def build_corpus(csv_path: Path, sym_folder: Path) -> dict[str, Any]:
    parts: list[dict[str, Any]] = []
    count_mismatches: list[dict[str, Any]] = []
    type_mismatches: list[dict[str, Any]] = []
    known_pen_mismatches: list[dict[str, Any]] = []
    layer_record_pen_counts: Counter[tuple[str, str, str, str]] = Counter()
    token_slot_counts: Counter[tuple[str, str, int, str]] = Counter()

    for dxf_path in _iter_csv_dxf_paths(csv_path):
        sym_path = sym_folder / f"{dxf_path.stem}.sym"
        part = build_part_corpus(dxf_path, sym_path)
        parts.append(part)
        if not part["count_match"]:
            count_mismatches.append(
                {
                    "part": part["part"],
                    "dxf_count": part["dxf_count"],
                    "ddc_count": part["ddc_count"],
                }
            )
        for pair in part["pairs"]:
            dxf = pair["dxf"]
            ddc = pair["ddc"]
            if not pair["type_match"]:
                type_mismatches.append(
                    {
                        "part": part["part"],
                        "index": pair["index"],
                        "dxf_type": dxf["type"],
                        "ddc_record": ddc["record"],
                    }
                )
            if not pair["known_pen_match"]:
                known_pen_mismatches.append(
                    {
                        "part": part["part"],
                        "index": pair["index"],
                        "dxf_layer": dxf["layer"],
                        "expected_pen": pair["expected_pen"],
                        "ddc_pen": ddc["pen"],
                    }
                )
            layer_record_pen_counts[(dxf["type"], dxf["layer"], ddc["record"], str(ddc["pen"]))] += 1
            for slot_index, token in enumerate(ddc["tokens"]):
                token_slot_counts[(ddc["record"], dxf["type"], slot_index, token)] += 1

    total_dxf_entities = sum(int(part["dxf_count"]) for part in parts)
    total_ddc_records = sum(int(part["ddc_count"]) for part in parts)
    return {
        "schema_version": 1,
        "csv_path": str(csv_path),
        "sym_folder": str(sym_folder),
        "part_count": len(parts),
        "total_dxf_entities": total_dxf_entities,
        "total_ddc_records": total_ddc_records,
        "count_mismatches": count_mismatches,
        "type_mismatches": type_mismatches,
        "known_pen_mismatches": known_pen_mismatches,
        "layer_record_pen_counts": [
            {
                "count": count,
                "dxf_type": key[0],
                "dxf_layer": key[1],
                "ddc_record": key[2],
                "ddc_pen": key[3],
            }
            for key, count in layer_record_pen_counts.most_common()
        ],
        "token_slot_counts": [
            {
                "count": count,
                "ddc_record": key[0],
                "dxf_type": key[1],
                "slot": key[2],
                "token": key[3],
            }
            for key, count in token_slot_counts.most_common()
        ],
        "parts": parts,
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.tmp")
    temp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True) + "\n", encoding="utf-8")
    temp_path.replace(path)


def _print_summary(payload: dict[str, Any]) -> None:
    summary = {
        "part_count": payload["part_count"],
        "total_dxf_entities": payload["total_dxf_entities"],
        "total_ddc_records": payload["total_ddc_records"],
        "count_mismatch_count": len(payload["count_mismatches"]),
        "type_mismatch_count": len(payload["type_mismatches"]),
        "known_pen_mismatch_count": len(payload["known_pen_mismatches"]),
        "layer_record_pen_counts": payload["layer_record_pen_counts"],
    }
    print(json.dumps(summary, indent=2, ensure_ascii=True, sort_keys=True))


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a paired DXF/DDC corpus from RADAN-generated .sym files.")
    parser.add_argument("--csv", type=Path, required=True, help="Inventor-to-RADAN CSV with source DXF paths.")
    parser.add_argument("--sym-folder", type=Path, required=True, help="Folder containing generated .sym files.")
    parser.add_argument("--out", type=Path, help="Optional JSON output path.")
    args = parser.parse_args()

    payload = build_corpus(args.csv, args.sym_folder)
    if args.out:
        write_json(args.out, payload)
    _print_summary(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
