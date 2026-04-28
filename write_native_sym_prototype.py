from __future__ import annotations

import argparse
import json
import re
from fractions import Fraction
from pathlib import Path
from typing import Any

from ddc_corpus import DDC_RE, KNOWN_PEN_BY_LAYER, Bounds, build_part_corpus, read_dxf_entities
from ddc_number_codec import decode_ddc_number_fraction, encode_ddc_number, encode_ddc_number_fraction
from path_safety import assert_w_drive_write_allowed


DEFAULT_LAB_ROOT = Path(__file__).resolve().parent / "_sym_lab"
CANONICAL_ENDPOINT_CONTINUATION_DIGITS = 8
CANONICAL_DELTA_CONTINUATION_DIGITS = 12
DDC_BLOCK_RE = re.compile(
    r'(<RadanFile\s+extension="ddc"\s*>\s*<!\[CDATA\[)(.*?)(\]\]>\s*</RadanFile>)',
    re.DOTALL,
)
DDC_LINE_DEFINITION = r"B,G,N,?,@,E1,R1,J,V,W,I,l1,O,P,Q,R,V1,W1,A2,B2,C2,D2,E2,F2,G2,H2,O2,P2,Q2,R2,W2,[2,\2,"
DDC_ARC_DEFINITION = "B,H,N,?,@,E1,R1,J,V,W,I,F,O,P,Q,R,S,T,X,Y,Z,[,V1,W1,A2,B2,C2,D2,E2,F2,G2,H2,W2,"


def _round_optional(value: float, digits: int | None) -> float:
    if digits is None:
        return float(value)
    rounded = round(float(value), int(digits))
    if rounded == 0:
        return 0.0
    return rounded


def _pad_tokens(tokens: dict[int, float], length: int) -> list[str]:
    padded = [""] * length
    for index, value in tokens.items():
        if index >= length:
            padded.extend([""] * (index - length + 1))
        padded[index] = encode_ddc_number(value)
    return padded


def _pad_fraction_tokens(tokens: dict[int, Fraction], length: int, *, continuation_digits: int = 8) -> list[str]:
    padded = [""] * length
    for index, value in tokens.items():
        if index >= length:
            padded.extend([""] * (index - length + 1))
        padded[index] = encode_ddc_number_fraction(value, continuation_digits=continuation_digits)
    return padded


def _decimal_fraction(value: float, digits: int | None) -> Fraction:
    return Fraction(str(_round_optional(value, digits)))


def _canonical_encoded_fraction(
    value: float,
    *,
    coordinate_digits: int | None,
    continuation_digits: int = 8,
) -> Fraction:
    token = encode_ddc_number_fraction(
        _decimal_fraction(value, coordinate_digits),
        continuation_digits=continuation_digits,
    )
    return decode_ddc_number_fraction(token)


def encode_geometry_data(
    dxf_row: dict[str, Any],
    *,
    token_count: int,
    coordinate_digits: int | None = None,
    canonicalize_endpoints: bool = False,
    continuation_digits: int = CANONICAL_DELTA_CONTINUATION_DIGITS,
) -> str:
    entity_type = str(dxf_row["type"])
    if entity_type == "LINE":
        start = [_round_optional(value, coordinate_digits) for value in dxf_row["normalized_start"]]
        end = [_round_optional(value, coordinate_digits) for value in dxf_row["normalized_end"]]
        if canonicalize_endpoints:
            start_x = _canonical_encoded_fraction(
                float(start[0]),
                coordinate_digits=None,
                continuation_digits=CANONICAL_ENDPOINT_CONTINUATION_DIGITS,
            )
            start_y = _canonical_encoded_fraction(
                float(start[1]),
                coordinate_digits=None,
                continuation_digits=CANONICAL_ENDPOINT_CONTINUATION_DIGITS,
            )
            end_x = _canonical_encoded_fraction(
                float(end[0]),
                coordinate_digits=None,
                continuation_digits=CANONICAL_ENDPOINT_CONTINUATION_DIGITS,
            )
            end_y = _canonical_encoded_fraction(
                float(end[1]),
                coordinate_digits=None,
                continuation_digits=CANONICAL_ENDPOINT_CONTINUATION_DIGITS,
            )
            tokens = {
                0: start_x,
                1: start_y,
                2: end_x - start_x,
                3: end_y - start_y,
            }
            return ".".join(_pad_fraction_tokens(tokens, token_count, continuation_digits=continuation_digits))
        tokens = {
            0: float(start[0]),
            1: float(start[1]),
            2: float(end[0]) - float(start[0]),
            3: float(end[1]) - float(start[1]),
        }
        return ".".join(_pad_tokens(tokens, token_count))

    if entity_type == "CIRCLE":
        center = [_round_optional(value, coordinate_digits) for value in dxf_row["normalized_center"]]
        radius = _round_optional(float(dxf_row["radius"]), coordinate_digits)
        if canonicalize_endpoints:
            start_x = _canonical_encoded_fraction(
                float(center[0]) + radius,
                coordinate_digits=None,
                continuation_digits=CANONICAL_ENDPOINT_CONTINUATION_DIGITS,
            )
            start_y = _canonical_encoded_fraction(
                float(center[1]),
                coordinate_digits=None,
                continuation_digits=CANONICAL_ENDPOINT_CONTINUATION_DIGITS,
            )
            center_x = _canonical_encoded_fraction(
                float(center[0]),
                coordinate_digits=None,
                continuation_digits=CANONICAL_ENDPOINT_CONTINUATION_DIGITS,
            )
            center_y = _canonical_encoded_fraction(
                float(center[1]),
                coordinate_digits=None,
                continuation_digits=CANONICAL_ENDPOINT_CONTINUATION_DIGITS,
            )
            tokens = {
                0: start_x,
                1: start_y,
                4: center_x - start_x,
                5: center_y - start_y,
                6: Fraction(1, 1),
                9: Fraction(1, 1),
            }
            return ".".join(_pad_fraction_tokens(tokens, token_count, continuation_digits=continuation_digits))
        tokens = {
            0: float(center[0]) + radius,
            1: float(center[1]),
            4: -radius,
            6: 1.0,
            9: 1.0,
        }
        return ".".join(_pad_tokens(tokens, token_count))

    if entity_type == "ARC":
        start = [_round_optional(value, coordinate_digits) for value in dxf_row["normalized_start_point"]]
        end = [_round_optional(value, coordinate_digits) for value in dxf_row["normalized_end_point"]]
        center = [_round_optional(value, coordinate_digits) for value in dxf_row["normalized_center"]]
        if canonicalize_endpoints:
            start_x = _canonical_encoded_fraction(
                float(start[0]),
                coordinate_digits=None,
                continuation_digits=CANONICAL_ENDPOINT_CONTINUATION_DIGITS,
            )
            start_y = _canonical_encoded_fraction(
                float(start[1]),
                coordinate_digits=None,
                continuation_digits=CANONICAL_ENDPOINT_CONTINUATION_DIGITS,
            )
            end_x = _canonical_encoded_fraction(
                float(end[0]),
                coordinate_digits=None,
                continuation_digits=CANONICAL_ENDPOINT_CONTINUATION_DIGITS,
            )
            end_y = _canonical_encoded_fraction(
                float(end[1]),
                coordinate_digits=None,
                continuation_digits=CANONICAL_ENDPOINT_CONTINUATION_DIGITS,
            )
            center_x = _canonical_encoded_fraction(
                float(center[0]),
                coordinate_digits=None,
                continuation_digits=CANONICAL_ENDPOINT_CONTINUATION_DIGITS,
            )
            center_y = _canonical_encoded_fraction(
                float(center[1]),
                coordinate_digits=None,
                continuation_digits=CANONICAL_ENDPOINT_CONTINUATION_DIGITS,
            )
            tokens = {
                0: start_x,
                1: start_y,
                2: end_x - start_x,
                3: end_y - start_y,
                4: center_x - start_x,
                5: center_y - start_y,
                6: Fraction(1, 1),
                9: Fraction(1, 1),
            }
            return ".".join(_pad_fraction_tokens(tokens, token_count, continuation_digits=continuation_digits))
        tokens = {
            0: float(start[0]),
            1: float(start[1]),
            2: float(end[0]) - float(start[0]),
            3: float(end[1]) - float(start[1]),
            4: float(center[0]) - float(start[0]),
            5: float(center[1]) - float(start[1]),
            6: 1.0,
            9: 1.0,
        }
        return ".".join(_pad_tokens(tokens, token_count))

    raise ValueError(f"Unsupported DXF entity type: {entity_type}")


def _normalize_rounded_source_point(point: list[float], bounds: Bounds, digits: int) -> list[float]:
    min_x = _round_optional(bounds.min_x, digits)
    min_y = _round_optional(bounds.min_y, digits)
    return [
        _round_optional(point[0], digits) - min_x,
        _round_optional(point[1], digits) - min_y,
    ]


def _source_point_from_normalized(point: list[float], bounds: Bounds) -> list[float]:
    return [float(point[0]) + float(bounds.min_x), float(point[1]) + float(bounds.min_y)]


def _rounded_min_bounds(bounds: Bounds, digits: int) -> tuple[float, float]:
    return _round_optional(bounds.min_x, digits), _round_optional(bounds.min_y, digits)


def _normalize_source_point(point: list[float], min_x: float, min_y: float) -> list[float]:
    return [float(point[0]) - min_x, float(point[1]) - min_y]


def _rows_with_rounded_source_coordinates(
    dxf_rows: list[dict[str, Any]],
    bounds: Bounds,
    *,
    digits: int,
    entity_types: set[str] | None = None,
) -> list[dict[str, Any]]:
    rounded_rows: list[dict[str, Any]] = []
    for row in dxf_rows:
        copied = dict(row)
        entity_type = str(copied["type"])
        if entity_types is not None and entity_type not in entity_types:
            rounded_rows.append(copied)
            continue
        if entity_type == "LINE":
            copied["normalized_start"] = _normalize_rounded_source_point(copied["start"], bounds, digits)
            copied["normalized_end"] = _normalize_rounded_source_point(copied["end"], bounds, digits)
        elif entity_type == "CIRCLE":
            copied["normalized_center"] = _normalize_rounded_source_point(copied["center"], bounds, digits)
        elif entity_type == "ARC":
            copied["normalized_center"] = _normalize_rounded_source_point(copied["center"], bounds, digits)
            copied["normalized_start_point"] = _normalize_rounded_source_point(
                _source_point_from_normalized(copied["normalized_start_point"], bounds),
                bounds,
                digits,
            )
            copied["normalized_end_point"] = _normalize_rounded_source_point(
                _source_point_from_normalized(copied["normalized_end_point"], bounds),
                bounds,
                digits,
            )
        rounded_rows.append(copied)
    return rounded_rows


def _endpoint_entries(dxf_rows: list[dict[str, Any]], bounds: Bounds) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for row_index, row in enumerate(dxf_rows):
        entity_type = str(row["type"])
        if entity_type == "LINE":
            entries.append(
                {
                    "row_index": row_index,
                    "field": "normalized_start",
                    "source_point": list(row["start"]),
                    "entity_type": entity_type,
                    "layer": str(row.get("layer", "")),
                }
            )
            entries.append(
                {
                    "row_index": row_index,
                    "field": "normalized_end",
                    "source_point": list(row["end"]),
                    "entity_type": entity_type,
                    "layer": str(row.get("layer", "")),
                }
            )
        elif entity_type == "ARC":
            entries.append(
                {
                    "row_index": row_index,
                    "field": "normalized_start_point",
                    "source_point": _source_point_from_normalized(row["normalized_start_point"], bounds),
                    "entity_type": entity_type,
                    "layer": str(row.get("layer", "")),
                }
            )
            entries.append(
                {
                    "row_index": row_index,
                    "field": "normalized_end_point",
                    "source_point": _source_point_from_normalized(row["normalized_end_point"], bounds),
                    "entity_type": entity_type,
                    "layer": str(row.get("layer", "")),
                }
            )
    return entries


def _points_close(left: list[float], right: list[float], tolerance: float) -> bool:
    return abs(float(left[0]) - float(right[0])) <= tolerance and abs(float(left[1]) - float(right[1])) <= tolerance


def _cluster_endpoint_entries(entries: list[dict[str, Any]], *, tolerance: float) -> list[list[dict[str, Any]]]:
    clusters: list[list[dict[str, Any]]] = []
    for entry in entries:
        for cluster in clusters:
            first = cluster[0]
            if str(first["layer"]) == str(entry["layer"]) and _points_close(
                first["source_point"],
                entry["source_point"],
                tolerance,
            ):
                cluster.append(entry)
                break
        else:
            clusters.append([entry])
    return clusters


def _cluster_representative_source_point(cluster: list[dict[str, Any]], *, digits: int) -> list[float]:
    line_entries = [entry for entry in cluster if entry["entity_type"] == "LINE"]
    if line_entries:
        point = line_entries[0]["source_point"]
        return [_round_optional(point[0], digits), _round_optional(point[1], digits)]
    count = len(cluster)
    return [
        sum(float(entry["source_point"][0]) for entry in cluster) / count,
        sum(float(entry["source_point"][1]) for entry in cluster) / count,
    ]


def _rows_with_topology_snapped_endpoints(
    dxf_rows: list[dict[str, Any]],
    bounds: Bounds,
    *,
    digits: int,
    tolerance: float | None = None,
) -> list[dict[str, Any]]:
    snapped_rows: list[dict[str, Any]] = []
    min_x, min_y = _rounded_min_bounds(bounds, digits)
    for row in dxf_rows:
        copied = dict(row)
        entity_type = str(copied["type"])
        if entity_type == "ARC":
            copied["normalized_center"] = _normalize_rounded_source_point(copied["center"], bounds, digits)
        elif entity_type == "CIRCLE":
            copied["normalized_center"] = _normalize_rounded_source_point(copied["center"], bounds, digits)
        snapped_rows.append(copied)

    endpoint_tolerance = tolerance if tolerance is not None else 10 ** (-int(digits))
    for cluster in _cluster_endpoint_entries(_endpoint_entries(dxf_rows, bounds), tolerance=endpoint_tolerance):
        representative = _cluster_representative_source_point(cluster, digits=digits)
        normalized = _normalize_source_point(representative, min_x, min_y)
        for entry in cluster:
            snapped_rows[int(entry["row_index"])][str(entry["field"])] = list(normalized)
    return snapped_rows


def _replace_ddc_geometry_block(
    template_text: str,
    dxf_rows: list[dict[str, Any]],
    *,
    coordinate_digits: int | None = None,
    canonicalize_endpoints: bool = False,
    part_name: str | None = None,
) -> tuple[str, dict[str, Any]]:
    match = DDC_BLOCK_RE.search(template_text)
    if match is None:
        raise RuntimeError("No DDC CDATA block found in template symbol.")

    source_lines = match.group(2).splitlines()
    need_line_definition = any(str(row["type"]) == "LINE" for row in dxf_rows)
    need_arc_definition = any(str(row["type"]) != "LINE" for row in dxf_rows)
    has_line_definition = any(line.startswith("B,G,") for line in source_lines)
    has_arc_definition = any(line.startswith("B,H,") for line in source_lines)
    existing_geometry_lines = [
        line for line in source_lines if line.split(",", 1)[0] in {"G", "H"}
    ]
    reuse_existing_geometry = len(existing_geometry_lines) == len(dxf_rows) and all(
        line.split(",", 1)[0] == ("G" if dxf_row["type"] == "LINE" else "H")
        for line, dxf_row in zip(existing_geometry_lines, dxf_rows)
    )

    body_lines: list[str] = []
    definition_inserted = False
    geometry_inserted = False
    generated_records = 0
    geometry_index = 0

    def generated_geometry_lines() -> list[str]:
        nonlocal generated_records
        rows: list[str] = []
        generated_records = 0
        for index, dxf_row in enumerate(dxf_rows, start=3):
            record = "G" if dxf_row["type"] == "LINE" else "H"
            token_count = 17 if record == "G" else 21
            pen = KNOWN_PEN_BY_LAYER.get(str(dxf_row.get("layer", "")), "1")
            geometry_data = encode_geometry_data(
                dxf_row,
                token_count=token_count,
                coordinate_digits=coordinate_digits,
                canonicalize_endpoints=canonicalize_endpoints,
            )
            identifier = _encode_ddc_small_int(index)
            if record == "G":
                rows.append(f"G,,1,{identifier},,1,,,{pen},,{geometry_data},.,,,")
            else:
                rows.append(f"H,,1,{identifier},,1,,,{pen},1,{geometry_data},")
            generated_records += 1
        return rows

    geometry_lines = [] if reuse_existing_geometry else generated_geometry_lines()

    for line in source_lines:
        fields = line.split(",")
        if fields and fields[0] in {"G", "H"}:
            if reuse_existing_geometry:
                dxf_row = dxf_rows[geometry_index]
                while len(fields) <= 10:
                    fields.append("")
                original_token_count = len(fields[10].split(".")) if fields[10] else (17 if fields[0] == "G" else 21)
                fields[8] = KNOWN_PEN_BY_LAYER.get(str(dxf_row.get("layer", "")), fields[8])
                fields[10] = encode_geometry_data(
                    dxf_row,
                    token_count=original_token_count,
                    coordinate_digits=coordinate_digits,
                    canonicalize_endpoints=canonicalize_endpoints,
                )
                body_lines.append(",".join(fields))
                geometry_index += 1
                generated_records += 1
            elif not geometry_inserted:
                body_lines.extend(geometry_lines)
                geometry_inserted = True
            continue
        if line.startswith("B,G,") and not need_line_definition:
            continue
        if line.startswith("B,H,") and not need_arc_definition:
            continue
        if fields and fields[0] == "A" and len(fields) > 1:
            fields[1] = str(
                sum(
                    1
                    for candidate in source_lines
                    if candidate.startswith("B,")
                    and not (
                        (candidate.startswith("B,G,") and not need_line_definition)
                        or (candidate.startswith("B,H,") and not need_arc_definition)
                    )
                )
                + (1 if need_line_definition and not has_line_definition else 0)
                + (1 if need_arc_definition and not has_arc_definition else 0)
            )
            line = ",".join(fields)
        elif fields and fields[0] == "E" and len(fields) > 3:
            fields[3] = _encode_ddc_small_int(len(dxf_rows) + 2)
            line = ",".join(fields)
        elif fields and fields[0] == "D" and len(fields) > 3 and part_name:
            fields[3] = re.sub(r"\$.*$", f"${part_name}", fields[3])
            line = ",".join(fields)
        body_lines.append(line)
        if fields and fields[0] == "B":
            continue
        if not definition_inserted:
            insert_at_end_of_definitions = not fields or fields[0] not in {"A", "B"}
            if insert_at_end_of_definitions:
                if need_line_definition and not has_line_definition:
                    body_lines.insert(len(body_lines) - 1, DDC_LINE_DEFINITION)
                if need_arc_definition and not has_arc_definition:
                    body_lines.insert(len(body_lines) - 1, DDC_ARC_DEFINITION)
                definition_inserted = True

    if not reuse_existing_geometry and not geometry_inserted:
        body_lines.extend(geometry_lines)

    new_block = "\n".join(body_lines)
    if match.group(2).endswith("\n"):
        new_block += "\n"
    output_text = template_text[: match.start(2)] + new_block + template_text[match.end(2) :]
    return output_text, {"replaced_records": generated_records}


def _encode_ddc_small_int(value: int) -> str:
    value = int(value)
    if value < 0:
        raise ValueError("DDC small integer cannot be negative.")
    digits: list[str] = []
    while True:
        digits.append(chr(48 + (value % 64)))
        value //= 64
        if value == 0:
            return "".join(digits)


def _ensure_lab_output(path: Path, *, allow_outside_lab: bool = False) -> None:
    assert_w_drive_write_allowed(path, operation="write synthetic SYM prototype")
    if allow_outside_lab:
        return
    resolved = path.resolve()
    lab_root = DEFAULT_LAB_ROOT.resolve()
    if resolved != lab_root and lab_root not in resolved.parents:
        raise RuntimeError(f"Prototype output must stay under {lab_root} unless --allow-outside-lab is used.")


def write_native_prototype(
    *,
    dxf_path: Path,
    template_sym: Path,
    out_path: Path,
    allow_outside_lab: bool = False,
    coordinate_digits: int | None = None,
    source_coordinate_digits: int | None = None,
    source_coordinate_entity_types: set[str] | None = None,
    canonicalize_endpoints: bool = False,
    topology_snap_endpoints: bool = False,
) -> dict[str, Any]:
    _ensure_lab_output(out_path, allow_outside_lab=allow_outside_lab)
    dxf_rows, bounds = read_dxf_entities(dxf_path)
    if topology_snap_endpoints:
        if source_coordinate_digits is None:
            raise RuntimeError("--topology-snap-endpoints requires --source-coordinate-digits.")
        dxf_rows = _rows_with_topology_snapped_endpoints(
            dxf_rows,
            bounds,
            digits=int(source_coordinate_digits),
        )
    elif source_coordinate_digits is not None:
        dxf_rows = _rows_with_rounded_source_coordinates(
            dxf_rows,
            bounds,
            digits=int(source_coordinate_digits),
            entity_types=source_coordinate_entity_types,
        )
    template_text = template_sym.read_text(encoding="utf-8", errors="replace")
    if DDC_RE.search(template_text) is None:
        raise RuntimeError(f"No DDC block found in template symbol: {template_sym}")
    output_text, stats = _replace_ddc_geometry_block(
        template_text,
        dxf_rows,
        coordinate_digits=coordinate_digits,
        canonicalize_endpoints=canonicalize_endpoints,
        part_name=out_path.stem,
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = out_path.with_name(f"{out_path.name}.tmp")
    temp_path.write_text(output_text, encoding="utf-8")
    temp_path.replace(out_path)
    validation = build_part_corpus(dxf_path, out_path)
    return {
        "dxf_path": str(dxf_path),
        "template_sym": str(template_sym),
        "out_path": str(out_path),
        "bounds": bounds.as_dict(),
        "entity_count": len(dxf_rows),
        "replaced_records": stats["replaced_records"],
        "coordinate_digits": coordinate_digits,
        "source_coordinate_digits": source_coordinate_digits,
        "source_coordinate_entity_types": (
            None if source_coordinate_entity_types is None else sorted(source_coordinate_entity_types)
        ),
        "canonicalize_endpoints": canonicalize_endpoints,
        "topology_snap_endpoints": topology_snap_endpoints,
        "validation": {
            "dxf_count": validation["dxf_count"],
            "ddc_count": validation["ddc_count"],
            "count_match": validation["count_match"],
            "type_mismatch_count": validation["type_mismatch_count"],
            "known_pen_mismatch_count": validation["known_pen_mismatch_count"],
        },
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    assert_w_drive_write_allowed(path, operation="write synthetic SYM report")
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.tmp")
    temp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True) + "\n", encoding="utf-8")
    temp_path.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Write a lab-only native .sym prototype from DXF geometry.")
    parser.add_argument("--dxf", type=Path, required=True, help="Source DXF path.")
    parser.add_argument("--template-sym", type=Path, required=True, help="Known-good template .sym to clone.")
    parser.add_argument("--out", type=Path, required=True, help=f"Output .sym path under {DEFAULT_LAB_ROOT}.")
    parser.add_argument("--report", type=Path, help="Optional JSON report path.")
    parser.add_argument("--allow-outside-lab", action="store_true", help=f"Allow output outside {DEFAULT_LAB_ROOT}.")
    parser.add_argument(
        "--coordinate-digits",
        type=int,
        help="Lab option: round normalized DXF coordinates to this many decimal digits before encoding.",
    )
    parser.add_argument(
        "--source-coordinate-digits",
        type=int,
        help=(
            "Lab option: round source DXF coordinates and source min bounds before normalizing, "
            "matching the observed RADAN import order."
        ),
    )
    parser.add_argument(
        "--source-coordinate-entity-type",
        action="append",
        choices=["LINE", "ARC", "CIRCLE"],
        help="Limit --source-coordinate-digits to one or more DXF entity types. Defaults to all geometry types.",
    )
    parser.add_argument(
        "--canonicalize-endpoints",
        action="store_true",
        help=(
            "Lab option: encode deltas from exact encoded endpoint fractions so shared endpoints close exactly."
        ),
    )
    parser.add_argument(
        "--topology-snap-endpoints",
        action="store_true",
        help=(
            "Lab option: cluster shared line/arc endpoints before encoding. Requires --source-coordinate-digits."
        ),
    )
    args = parser.parse_args()

    payload = write_native_prototype(
        dxf_path=args.dxf,
        template_sym=args.template_sym,
        out_path=args.out,
        allow_outside_lab=bool(args.allow_outside_lab),
        coordinate_digits=args.coordinate_digits,
        source_coordinate_digits=args.source_coordinate_digits,
        source_coordinate_entity_types=(
            None if args.source_coordinate_entity_type is None else set(args.source_coordinate_entity_type)
        ),
        canonicalize_endpoints=args.canonicalize_endpoints,
        topology_snap_endpoints=args.topology_snap_endpoints,
    )
    if args.report:
        write_json(args.report, payload)
    print(json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
