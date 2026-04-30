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
DDC_VIEW_BASE_X = Fraction("99.318474")
DDC_VIEW_BASE_Y = Fraction("70.228767")
DDC_VIEW_BASE_X_TOKEN = "5@8e67PaJPE"
DDC_VIEW_BASE_Y_TOKEN = "5@1SZ@NEmWL"
DDC_INCH_TO_MM_TOKEN = "3@9IVIVIVIV"
DDC_ONE_TOKEN = "o?0"


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


def _bounds_decimal_fraction(value: float) -> Fraction:
    return Fraction(f"{_round_optional(value, 6):.6f}")


def _symbol_view_extents(bounds: Bounds) -> tuple[Fraction, Fraction]:
    """Return the RADAN D-record view/cache extents for a lower-left-origin symbol.

    RADAN stores a padded symbol view rectangle separate from G/H cut geometry.
    The observed F54410 formula uses a 99.318474 x 70.228767 base rectangle
    with sqrt(2)-ish aspect, scaled to contain 3x the part bounding box.
    """

    width = _bounds_decimal_fraction(bounds.width)
    height = _bounds_decimal_fraction(bounds.height)
    scale = max(
        Fraction(1, 1),
        Fraction(3, 1) * width / DDC_VIEW_BASE_X,
        Fraction(3, 1) * height / DDC_VIEW_BASE_Y,
    )
    return DDC_VIEW_BASE_X * scale, DDC_VIEW_BASE_Y * scale


def _encode_view_extent(value: Fraction, *, default_value: Fraction, default_token: str) -> str:
    if abs(float(value - default_value)) <= 1e-12:
        return default_token
    return encode_ddc_number_fraction(value, continuation_digits=8)


def _symbol_view_record_field(bounds: Bounds, *, part_name: str) -> str:
    view_x, view_y = _symbol_view_extents(bounds)
    view_x_token = _encode_view_extent(
        view_x,
        default_value=DDC_VIEW_BASE_X,
        default_token=DDC_VIEW_BASE_X_TOKEN,
    )
    view_y_token = _encode_view_extent(
        view_y,
        default_value=DDC_VIEW_BASE_Y,
        default_token=DDC_VIEW_BASE_Y_TOKEN,
    )
    tokens = [
        "",
        view_x_token,
        "",
        view_y_token,
        "",
        view_x_token,
        "",
        view_y_token,
        DDC_INCH_TO_MM_TOKEN,
        DDC_ONE_TOKEN,
        DDC_ONE_TOKEN,
        "",
    ]
    return ".".join(tokens) + f"${part_name}"


def _format_sym_attr_number(value: float) -> str:
    rounded = _round_optional(value, 6)
    return f"{rounded:.6f}".rstrip("0").rstrip(".")


def _replace_attr_value(text: str, *, attr_num: str, value: str) -> str:
    pattern = re.compile(
        rf'(<Attr\b(?=[^>]*\bnum="{re.escape(str(attr_num))}")[^>]*\bvalue=)(["\'])(.*?)(\2)',
        re.DOTALL,
    )
    return pattern.sub(lambda match: f"{match.group(1)}{match.group(2)}{value}{match.group(4)}", text)


def _refresh_symbol_metadata_attrs(text: str, *, bounds: Bounds, part_name: str) -> str:
    refreshed = _replace_attr_value(text, attr_num="110", value=part_name)
    refreshed = _replace_attr_value(
        refreshed,
        attr_num="165",
        value=_format_sym_attr_number(bounds.width),
    )
    refreshed = _replace_attr_value(
        refreshed,
        attr_num="166",
        value=_format_sym_attr_number(bounds.height),
    )
    return refreshed


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


def _line_point_key(point: list[float] | tuple[float, ...], *, digits: int = 6) -> tuple[float, float]:
    return (round(float(point[0]), digits), round(float(point[1]), digits))


def _line_row_start(row: dict[str, Any]) -> tuple[float, float]:
    return _line_point_key(row["normalized_start"])


def _line_row_end(row: dict[str, Any]) -> tuple[float, float]:
    return _line_point_key(row["normalized_end"])


def _reverse_line_row(row: dict[str, Any]) -> dict[str, Any]:
    copied = dict(row)
    copied["normalized_start"], copied["normalized_end"] = list(row["normalized_end"]), list(row["normalized_start"])
    if "start" in copied and "end" in copied:
        copied["start"], copied["end"] = list(row["end"]), list(row["start"])
    return copied


def _line_profile_signature(rows: list[dict[str, Any]]) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    return [(_line_row_start(row), _line_row_end(row)) for row in rows]


def _rows_with_connected_line_profiles(dxf_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if any(str(row.get("type")) != "LINE" for row in dxf_rows):
        return list(dxf_rows), {"eligible": False, "changed": False, "chain_count": 0}

    original_signature = _line_profile_signature(dxf_rows)
    unused = [dict(row) for row in dxf_rows]
    ordered: list[dict[str, Any]] = []
    chain_count = 0
    while unused:
        chain_count += 1
        chain = [unused.pop(0)]
        chain_start = _line_row_start(chain[0])
        current_end = _line_row_end(chain[-1])
        while unused:
            match_index = None
            reverse_match = False
            for index, candidate in enumerate(unused):
                if _line_row_start(candidate) == current_end:
                    match_index = index
                    reverse_match = False
                    break
                if _line_row_end(candidate) == current_end:
                    match_index = index
                    reverse_match = True
                    break
            if match_index is None:
                break
            next_row = unused.pop(match_index)
            if reverse_match:
                next_row = _reverse_line_row(next_row)
            chain.append(next_row)
            current_end = _line_row_end(next_row)
            if current_end == chain_start:
                break
        ordered.extend(chain)

    return ordered, {
        "eligible": True,
        "changed": _line_profile_signature(ordered) != original_signature,
        "chain_count": chain_count,
    }


def _replace_ddc_geometry_block(
    template_text: str,
    dxf_rows: list[dict[str, Any]],
    *,
    bounds: Bounds | None = None,
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
            if bounds is None:
                fields[3] = re.sub(r"\$.*$", f"${part_name}", fields[3])
            else:
                fields[3] = _symbol_view_record_field(bounds, part_name=part_name)
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
    order_connected_line_profiles: bool = False,
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
    line_profile_ordering = {"eligible": False, "changed": False, "chain_count": 0}
    if order_connected_line_profiles:
        dxf_rows, line_profile_ordering = _rows_with_connected_line_profiles(dxf_rows)
    template_text = template_sym.read_text(encoding="utf-8", errors="replace")
    if DDC_RE.search(template_text) is None:
        raise RuntimeError(f"No DDC block found in template symbol: {template_sym}")
    output_text, stats = _replace_ddc_geometry_block(
        template_text,
        dxf_rows,
        bounds=bounds,
        coordinate_digits=coordinate_digits,
        canonicalize_endpoints=canonicalize_endpoints,
        part_name=out_path.stem,
    )
    output_text = _refresh_symbol_metadata_attrs(output_text, bounds=bounds, part_name=out_path.stem)
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
        "order_connected_line_profiles": order_connected_line_profiles,
        "line_profile_ordering": line_profile_ordering,
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
    parser.add_argument(
        "--order-connected-line-profiles",
        action="store_true",
        help="Lab option: order line-only DXF entities into connected profile chains before encoding.",
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
        order_connected_line_profiles=args.order_connected_line_profiles,
    )
    if args.report:
        write_json(args.report, payload)
    print(json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
