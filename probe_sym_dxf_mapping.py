from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

import ezdxf


DDC_RE = re.compile(
    r'<RadanFile\s+extension="ddc">\s*<!\[CDATA\[(.*?)\]\]>\s*</RadanFile>',
    re.DOTALL,
)


def _dxf_entities(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    doc = ezdxf.readfile(path)
    for entity in doc.modelspace():
        entity_type = entity.dxftype()
        if entity_type not in {"LINE", "ARC", "CIRCLE"}:
            continue
        row: dict[str, Any] = {
            "type": entity_type,
            "layer": entity.dxf.layer,
        }
        if entity_type == "LINE":
            row["start"] = [float(value) for value in entity.dxf.start]
            row["end"] = [float(value) for value in entity.dxf.end]
        elif entity_type == "ARC":
            row["center"] = [float(value) for value in entity.dxf.center]
            row["radius"] = float(entity.dxf.radius)
            row["start_angle"] = float(entity.dxf.start_angle)
            row["end_angle"] = float(entity.dxf.end_angle)
        elif entity_type == "CIRCLE":
            row["center"] = [float(value) for value in entity.dxf.center]
            row["radius"] = float(entity.dxf.radius)
        rows.append(row)
    return rows


def _ddc_records(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8", errors="replace")
    match = DDC_RE.search(text)
    if match is None:
        raise RuntimeError(f"No DDC RadanFile block found in {path}")
    rows: list[dict[str, Any]] = []
    for line in match.group(1).splitlines():
        if not line.strip():
            continue
        fields = line.split(",")
        record_type = fields[0]
        if record_type not in {"G", "H"}:
            continue
        rows.append(
            {
                "record": record_type,
                "identifier": fields[3] if len(fields) > 3 else "",
                "pen": fields[8] if len(fields) > 8 else "",
                "geometry_data": fields[10] if len(fields) > 10 else "",
                "field_count": len(fields),
            }
        )
    return rows


def compare_pair(dxf_path: Path, sym_path: Path) -> dict[str, Any]:
    dxf_rows = _dxf_entities(dxf_path)
    ddc_rows = _ddc_records(sym_path)
    pairs = []
    for dxf_row, ddc_row in zip(dxf_rows, ddc_rows):
        pairs.append(
            {
                "dxf_type": dxf_row["type"],
                "dxf_layer": dxf_row["layer"],
                "ddc_record": ddc_row["record"],
                "ddc_pen": ddc_row["pen"],
                "ddc_identifier": ddc_row["identifier"],
            }
        )
    return {
        "dxf_path": str(dxf_path),
        "sym_path": str(sym_path),
        "dxf_count": len(dxf_rows),
        "ddc_count": len(ddc_rows),
        "counts_match": len(dxf_rows) == len(ddc_rows),
        "pairs": pairs,
    }


def summarize_csv(csv_path: Path, output_folder: Path) -> dict[str, Any]:
    layer_record_pen_counts: Counter[tuple[str, str, str, str]] = Counter()
    count_mismatches: list[dict[str, Any]] = []
    type_mismatches: list[dict[str, Any]] = []
    part_count = 0
    total_dxf_entities = 0
    total_ddc_records = 0
    with csv_path.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.reader(handle):
            if not row or all(not cell.strip() for cell in row):
                continue
            dxf_path = Path(row[0].strip())
            sym_path = output_folder / f"{dxf_path.stem}.sym"
            part_count += 1
            dxf_rows = _dxf_entities(dxf_path)
            ddc_rows = _ddc_records(sym_path)
            total_dxf_entities += len(dxf_rows)
            total_ddc_records += len(ddc_rows)
            if len(dxf_rows) != len(ddc_rows):
                count_mismatches.append(
                    {
                        "part": dxf_path.stem,
                        "dxf_count": len(dxf_rows),
                        "ddc_count": len(ddc_rows),
                    }
                )
                continue
            for dxf_row, ddc_row in zip(dxf_rows, ddc_rows):
                expected_record = "G" if dxf_row["type"] == "LINE" else "H"
                if ddc_row["record"] != expected_record:
                    type_mismatches.append(
                        {
                            "part": dxf_path.stem,
                            "dxf_type": dxf_row["type"],
                            "ddc_record": ddc_row["record"],
                        }
                    )
                layer_record_pen_counts[
                    (
                        str(dxf_row["type"]),
                        str(dxf_row["layer"]),
                        str(ddc_row["record"]),
                        str(ddc_row["pen"]),
                    )
                ] += 1
    return {
        "csv_path": str(csv_path),
        "output_folder": str(output_folder),
        "part_count": part_count,
        "total_dxf_entities": total_dxf_entities,
        "total_ddc_records": total_ddc_records,
        "count_mismatches": count_mismatches,
        "type_mismatches": type_mismatches,
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
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare source DXF entities with generated RADAN .sym DDC records.")
    parser.add_argument("--csv", type=Path, help="Inventor-to-RADAN CSV with source DXF paths.")
    parser.add_argument("--output-folder", type=Path, help="Folder containing generated .sym files.")
    parser.add_argument("--dxf", type=Path, help="Single DXF path to compare.")
    parser.add_argument("--sym", type=Path, help="Single SYM path to compare.")
    args = parser.parse_args()

    if args.csv and args.output_folder:
        payload = summarize_csv(args.csv, args.output_folder)
    elif args.dxf and args.sym:
        payload = compare_pair(args.dxf, args.sym)
    else:
        parser.error("Pass either --csv/--output-folder or --dxf/--sym.")
    print(json.dumps(payload, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
