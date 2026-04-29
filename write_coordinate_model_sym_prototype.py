from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any

from ddc_corpus import read_ddc_records, read_dxf_entities
from ddc_number_codec import decode_ddc_number_fraction, encode_ddc_number_fraction
from evaluate_exported_coordinate_token_model import (
    _build_coordinate_fallback_lookup,
    _build_coordinate_lookup,
    coordinate_entries_for_part,
    predicted_slot_fractions,
    slot_role,
    token_fraction,
)
from path_safety import assert_w_drive_write_allowed
from write_native_sym_prototype import DDC_BLOCK_RE, DEFAULT_LAB_ROOT, _ensure_lab_output


@dataclass(frozen=True)
class PartPair:
    part: str
    dxf_path: Path
    sym_path: Path
    dxf_rows: list[dict[str, Any]]
    ddc_rows: list[dict[str, Any]]


CONTEXT_COORDINATE_SOURCES = (
    "entity_role_point_value",
    "entity_role_neighbors_value",
    "entity_role_radius_value",
    "entity_role_value",
    "role_value",
    "plain_value",
)


def _record_for_dxf_type(entity_type: str) -> str:
    return "G" if str(entity_type) == "LINE" else "H"


def _token_at(row: dict[str, Any], slot: int) -> str:
    tokens = list(row.get("tokens") or [])
    return str(tokens[slot]) if slot < len(tokens) else ""


def _value_key(value: float, *, digits: int) -> str:
    rounded = round(float(value), int(digits))
    if rounded == 0:
        rounded = 0.0
    return f"{rounded:.{int(digits)}f}"


def _point_key(x_value: float, y_value: float, *, digits: int) -> str:
    return f"{_value_key(x_value, digits=digits)},{_value_key(y_value, digits=digits)}"


def _is_power_of_two(value: int) -> bool:
    return value > 0 and (value & (value - 1)) == 0


def _visible_dyadic_fraction(value: float, *, digits: int, max_denominator: int = 4096) -> Fraction | None:
    fraction = Fraction(_value_key(value, digits=digits))
    if fraction.denominator <= max_denominator and _is_power_of_two(fraction.denominator):
        return fraction
    return None


def _is_cardinal_angle(value: float, *, tolerance: float = 1e-9) -> bool:
    return abs((float(value) / 90.0) - round(float(value) / 90.0)) <= tolerance


def _arc_has_cardinal_endpoints(dxf_row: dict[str, Any]) -> bool:
    return _is_cardinal_angle(float(dxf_row.get("start_angle", 0.0))) and _is_cardinal_angle(
        float(dxf_row.get("end_angle", 0.0))
    )


def _row_type_at(dxf_rows: list[dict[str, Any]], index: int) -> str:
    if index < 0 or index >= len(dxf_rows):
        return ""
    return str(dxf_rows[index]["type"])


def _row_context(dxf_rows: list[dict[str, Any]], row_index: int, *, value_digits: int) -> dict[str, Any]:
    row = dxf_rows[row_index]
    entity_type = str(row["type"])
    return {
        "row_index": row_index + 1,
        "dxf_type": entity_type,
        "previous_type": _row_type_at(dxf_rows, row_index - 1),
        "next_type": _row_type_at(dxf_rows, row_index + 1),
        "radius_key": _value_key(float(row.get("radius", 0.0)), digits=value_digits)
        if entity_type in {"ARC", "CIRCLE"}
        else "",
        "start_angle_key": _value_key(float(row.get("start_angle", 0.0)), digits=value_digits)
        if entity_type == "ARC"
        else "",
        "end_angle_key": _value_key(float(row.get("end_angle", 0.0)), digits=value_digits)
        if entity_type == "ARC"
        else "",
    }


def _load_training_pairs(dxf_folder: Path, sym_folder: Path) -> tuple[list[PartPair], list[dict[str, str]]]:
    dxf_by_part = {path.stem.casefold(): path for path in Path(dxf_folder).glob("*.dxf")}
    sym_by_part = {path.stem.casefold(): path for path in Path(sym_folder).glob("*.sym")}
    pairs: list[PartPair] = []
    skipped: list[dict[str, str]] = []

    for key in sorted(set(dxf_by_part) | set(sym_by_part)):
        dxf_path = dxf_by_part.get(key)
        sym_path = sym_by_part.get(key)
        if dxf_path is None or sym_path is None:
            skipped.append({"part": key, "reason": "missing_dxf" if dxf_path is None else "missing_sym"})
            continue
        dxf_rows, _bounds = read_dxf_entities(dxf_path)
        ddc_rows = read_ddc_records(sym_path)
        type_sequence = [_record_for_dxf_type(str(row["type"])) for row in dxf_rows]
        ddc_sequence = [str(row["record"]) for row in ddc_rows]
        if len(dxf_rows) != len(ddc_rows) or type_sequence != ddc_sequence:
            skipped.append({"part": dxf_path.stem, "reason": "count_or_type_sequence_mismatch"})
            continue
        pairs.append(
            PartPair(
                part=dxf_path.stem,
                dxf_path=dxf_path,
                sym_path=sym_path,
                dxf_rows=dxf_rows,
                ddc_rows=ddc_rows,
            )
        )
    return pairs, skipped


def _token_observations(pairs: list[PartPair]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for pair in pairs:
        for dxf_row, ddc_row in zip(pair.dxf_rows, pair.ddc_rows):
            entity_type = str(dxf_row["type"])
            for slot, token in enumerate(list(ddc_row.get("tokens") or [])):
                if not token:
                    continue
                rows.append(
                    {
                        "part": pair.part,
                        "dxf_type": entity_type,
                        "role": slot_role(entity_type, slot),
                        "slot": slot,
                        "token": str(token),
                        "fraction": token_fraction(str(token)),
                    }
                )
    return rows


def _add_point_observation(
    rows: list[dict[str, Any]],
    *,
    part: str,
    row_context: dict[str, Any],
    point_role: str,
    point_x: float,
    point_y: float,
    x_fraction: Fraction,
    y_fraction: Fraction,
    value_digits: int,
) -> None:
    point_key = _point_key(point_x, point_y, digits=value_digits)
    for axis, visible_value, fraction in (
        ("x", point_x, x_fraction),
        ("y", point_y, y_fraction),
    ):
        rows.append(
            {
                "part": part,
                "axis": axis,
                "value_key": _value_key(float(visible_value), digits=value_digits),
                "fraction": fraction,
                "point_role": point_role,
                "visible_point_key": point_key,
                **row_context,
            }
        )


def _coordinate_point_observations_for_pair(
    pair: PartPair,
    *,
    value_digits: int = 6,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row_index, (dxf_row, ddc_row) in enumerate(zip(pair.dxf_rows, pair.ddc_rows)):
        entity_type = str(dxf_row["type"])
        context = _row_context(pair.dxf_rows, row_index, value_digits=value_digits)
        if entity_type == "LINE":
            start_x = token_fraction(_token_at(ddc_row, 0))
            start_y = token_fraction(_token_at(ddc_row, 1))
            end_x = start_x + token_fraction(_token_at(ddc_row, 2))
            end_y = start_y + token_fraction(_token_at(ddc_row, 3))
            _add_point_observation(
                rows,
                part=pair.part,
                row_context=context,
                point_role="start",
                point_x=float(dxf_row["normalized_start"][0]),
                point_y=float(dxf_row["normalized_start"][1]),
                x_fraction=start_x,
                y_fraction=start_y,
                value_digits=value_digits,
            )
            _add_point_observation(
                rows,
                part=pair.part,
                row_context=context,
                point_role="end",
                point_x=float(dxf_row["normalized_end"][0]),
                point_y=float(dxf_row["normalized_end"][1]),
                x_fraction=end_x,
                y_fraction=end_y,
                value_digits=value_digits,
            )
        elif entity_type == "ARC":
            start_x = token_fraction(_token_at(ddc_row, 0))
            start_y = token_fraction(_token_at(ddc_row, 1))
            end_x = start_x + token_fraction(_token_at(ddc_row, 2))
            end_y = start_y + token_fraction(_token_at(ddc_row, 3))
            center_x = start_x + token_fraction(_token_at(ddc_row, 4))
            center_y = start_y + token_fraction(_token_at(ddc_row, 5))
            for point_role, point, x_fraction, y_fraction in (
                ("start", dxf_row["normalized_start_point"], start_x, start_y),
                ("end", dxf_row["normalized_end_point"], end_x, end_y),
                ("center", dxf_row["normalized_center"], center_x, center_y),
            ):
                _add_point_observation(
                    rows,
                    part=pair.part,
                    row_context=context,
                    point_role=point_role,
                    point_x=float(point[0]),
                    point_y=float(point[1]),
                    x_fraction=x_fraction,
                    y_fraction=y_fraction,
                    value_digits=value_digits,
                )
        elif entity_type == "CIRCLE":
            start_x = token_fraction(_token_at(ddc_row, 0))
            start_y = token_fraction(_token_at(ddc_row, 1))
            center_x = start_x + token_fraction(_token_at(ddc_row, 4))
            center_y = start_y + token_fraction(_token_at(ddc_row, 5))
            radius = float(dxf_row["radius"])
            _add_point_observation(
                rows,
                part=pair.part,
                row_context=context,
                point_role="start",
                point_x=float(dxf_row["normalized_center"][0]) + radius,
                point_y=float(dxf_row["normalized_center"][1]),
                x_fraction=start_x,
                y_fraction=start_y,
                value_digits=value_digits,
            )
            _add_point_observation(
                rows,
                part=pair.part,
                row_context=context,
                point_role="center",
                point_x=float(dxf_row["normalized_center"][0]),
                point_y=float(dxf_row["normalized_center"][1]),
                x_fraction=center_x,
                y_fraction=center_y,
                value_digits=value_digits,
            )
    return rows


def _context_coordinate_key(row: dict[str, Any], source: str) -> tuple[Any, ...]:
    if source == "entity_role_point_value":
        return (
            row["axis"],
            row["value_key"],
            row["dxf_type"],
            row["point_role"],
            row["visible_point_key"],
        )
    if source == "entity_role_neighbors_value":
        return (
            row["axis"],
            row["value_key"],
            row["dxf_type"],
            row["point_role"],
            row["previous_type"],
            row["next_type"],
        )
    if source == "entity_role_radius_value":
        return (
            row["axis"],
            row["value_key"],
            row["dxf_type"],
            row["point_role"],
            row["radius_key"],
        )
    if source == "entity_role_value":
        return (row["axis"], row["value_key"], row["dxf_type"], row["point_role"])
    if source == "role_value":
        return (row["axis"], row["value_key"], row["point_role"])
    if source == "plain_value":
        return (row["axis"], row["value_key"])
    raise ValueError(f"Unsupported context coordinate source: {source}")


def _choose_coordinate_fraction(candidates: list[Fraction], visible_value_key: str) -> Fraction:
    if not candidates:
        return Fraction(visible_value_key)
    counts = Counter(candidates)
    target = Fraction(visible_value_key)
    return sorted(counts.items(), key=lambda item: (-item[1], abs(float(item[0] - target))))[0][0]


def _build_context_coordinate_lookup(
    rows: list[dict[str, Any]],
) -> dict[str, dict[tuple[Any, ...], list[tuple[str, Fraction]]]]:
    lookup: dict[str, dict[tuple[Any, ...], list[tuple[str, Fraction]]]] = {
        source: {} for source in CONTEXT_COORDINATE_SOURCES
    }
    for row in rows:
        for source in CONTEXT_COORDINATE_SOURCES:
            lookup[source].setdefault(_context_coordinate_key(row, source), []).append(
                (str(row["part"]), row["fraction"])
            )
    return lookup


def _build_same_part_coordinate_lookup(rows: list[dict[str, Any]]) -> dict[tuple[str, int, str, str], Fraction]:
    lookup: dict[tuple[str, int, str, str], Fraction] = {}
    for row in rows:
        key = (str(row["part"]), int(row["row_index"]), str(row["point_role"]), str(row["axis"]))
        lookup[key] = row["fraction"]
    return lookup


def _build_token_lookup(token_observations: list[dict[str, Any]]) -> dict[str, dict[tuple[Any, ...], list[tuple[str, str]]]]:
    lookup: dict[str, dict[tuple[Any, ...], list[tuple[str, str]]]] = {
        "same_type_role_fraction": {},
        "same_role_fraction": {},
        "same_fraction": {},
    }
    for row in token_observations:
        part = str(row["part"])
        token = str(row["token"])
        fraction = row["fraction"]
        keys = {
            "same_type_role_fraction": (row["dxf_type"], row["role"], fraction),
            "same_role_fraction": (row["role"], fraction),
            "same_fraction": (fraction,),
        }
        for source, key in keys.items():
            lookup[source].setdefault(key, []).append((part, token))
    return lookup


def _slot_visible_values(dxf_row: dict[str, Any], *, value_digits: int) -> dict[int, str]:
    entity_type = str(dxf_row["type"])
    if entity_type == "LINE":
        start = [float(value) for value in dxf_row["normalized_start"]]
        end = [float(value) for value in dxf_row["normalized_end"]]
        return {
            0: _value_key(start[0], digits=value_digits),
            1: _value_key(start[1], digits=value_digits),
            2: _value_key(end[0] - start[0], digits=value_digits),
            3: _value_key(end[1] - start[1], digits=value_digits),
        }
    if entity_type == "ARC":
        start = [float(value) for value in dxf_row["normalized_start_point"]]
        end = [float(value) for value in dxf_row["normalized_end_point"]]
        center = [float(value) for value in dxf_row["normalized_center"]]
        return {
            0: _value_key(start[0], digits=value_digits),
            1: _value_key(start[1], digits=value_digits),
            2: _value_key(end[0] - start[0], digits=value_digits),
            3: _value_key(end[1] - start[1], digits=value_digits),
            4: _value_key(center[0] - start[0], digits=value_digits),
            5: _value_key(center[1] - start[1], digits=value_digits),
            6: _value_key(1.0, digits=value_digits),
            9: _value_key(1.0, digits=value_digits),
        }
    if entity_type == "CIRCLE":
        center = [float(value) for value in dxf_row["normalized_center"]]
        radius = float(dxf_row["radius"])
        return {
            0: _value_key(center[0] + radius, digits=value_digits),
            1: _value_key(center[1], digits=value_digits),
            4: _value_key(-radius, digits=value_digits),
            5: _value_key(0.0, digits=value_digits),
            6: _value_key(1.0, digits=value_digits),
            9: _value_key(1.0, digits=value_digits),
        }
    return {}


def _slot_fraction_observations(pairs: list[PartPair], *, value_digits: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for pair in pairs:
        for dxf_row, ddc_row in zip(pair.dxf_rows, pair.ddc_rows):
            entity_type = str(dxf_row["type"])
            visible_values = _slot_visible_values(dxf_row, value_digits=value_digits)
            for slot, visible_value_key in visible_values.items():
                token = _token_at(ddc_row, slot)
                if not token:
                    fraction = Fraction(0)
                else:
                    fraction = token_fraction(token)
                rows.append(
                    {
                        "part": pair.part,
                        "dxf_type": entity_type,
                        "role": slot_role(entity_type, slot),
                        "slot": slot,
                        "visible_value_key": visible_value_key,
                        "fraction": fraction,
                    }
                )
    return rows


def _build_slot_fraction_lookup(rows: list[dict[str, Any]]) -> dict[str, dict[tuple[Any, ...], list[tuple[str, Fraction]]]]:
    lookup: dict[str, dict[tuple[Any, ...], list[tuple[str, Fraction]]]] = {
        "type_role_value": {},
        "role_value": {},
        "value": {},
    }
    for row in rows:
        entries = {
            "type_role_value": (row["dxf_type"], row["role"], row["visible_value_key"]),
            "role_value": (row["role"], row["visible_value_key"]),
            "value": (row["visible_value_key"],),
        }
        for source, key in entries.items():
            lookup[source].setdefault(key, []).append((str(row["part"]), row["fraction"]))
    return lookup


def _pick_slot_fraction(
    *,
    target_part: str,
    dxf_row: dict[str, Any],
    slot: int,
    visible_value_key: str,
    model: dict[str, Any],
) -> tuple[Fraction | None, str]:
    entity_type = str(dxf_row["type"])
    role = slot_role(entity_type, slot)
    for source, key in (
        ("type_role_value", (entity_type, role, visible_value_key)),
        ("role_value", (role, visible_value_key)),
        ("value", (visible_value_key,)),
    ):
        entries = model.get("slot_fraction_lookup", {}).get(source, {}).get(key, [])
        candidates = [fraction for part, fraction in entries if str(part) != target_part]
        if candidates:
            return _choose_coordinate_fraction(candidates, visible_value_key), f"slot_fraction:{source}"
    return None, ""


def _min_continuation_digits(token: str) -> int:
    return max(0, len(str(token)) - 3) if token else 0


def _build_min_continuation_lookup(
    token_observations: list[dict[str, Any]],
) -> dict[str, dict[tuple[Any, ...], list[tuple[str, int]]]]:
    lookup: dict[str, dict[tuple[Any, ...], list[tuple[str, int]]]] = {
        "type_role": {},
        "role": {},
    }
    for row in token_observations:
        part = str(row["part"])
        digits = _min_continuation_digits(str(row["token"]))
        keys = {
            "type_role": (row["dxf_type"], row["role"]),
            "role": (row["role"],),
        }
        for source, key in keys.items():
            lookup[source].setdefault(key, []).append((part, digits))
    return lookup


def _choose_min_continuation_digits(
    *,
    target_part: str,
    dxf_row: dict[str, Any],
    slot: int,
    min_continuation_lookup: dict[str, dict[tuple[Any, ...], list[tuple[str, int]]]] | None,
    fallback_continuation: str,
) -> int:
    if fallback_continuation == "trimmed" or min_continuation_lookup is None:
        return 0
    entity_type = str(dxf_row["type"])
    role = slot_role(entity_type, slot)
    candidate_keys = []
    if fallback_continuation == "type-role":
        candidate_keys.append(("type_role", (entity_type, role)))
        candidate_keys.append(("role", (role,)))
    elif fallback_continuation == "role":
        candidate_keys.append(("role", (role,)))
    else:
        raise ValueError(f"Unsupported fallback continuation mode: {fallback_continuation}")

    for source, key in candidate_keys:
        entries = min_continuation_lookup.get(source, {}).get(key, [])
        candidates = [digits for part, digits in entries if str(part) != target_part]
        if candidates:
            return Counter(candidates).most_common(1)[0][0]
    return 0


def build_coordinate_model(dxf_folder: Path, sym_folder: Path, *, value_digits: int = 6) -> dict[str, Any]:
    pairs, skipped = _load_training_pairs(dxf_folder, sym_folder)
    coordinate_entries: list[dict[str, Any]] = []
    coordinate_point_observations: list[dict[str, Any]] = []
    for pair in pairs:
        coordinate_entries.extend(
            coordinate_entries_for_part(
                part=pair.part,
                dxf_rows=pair.dxf_rows,
                ddc_rows=pair.ddc_rows,
                value_digits=value_digits,
            )
        )
        coordinate_point_observations.extend(
            _coordinate_point_observations_for_pair(pair, value_digits=value_digits)
        )
    token_observations = _token_observations(pairs)
    slot_fraction_observations = _slot_fraction_observations(pairs, value_digits=value_digits)
    return {
        "pairs": pairs,
        "skipped": skipped,
        "coordinate_entries": coordinate_entries,
        "coordinate_point_observations": coordinate_point_observations,
        "coordinate_lookup": _build_coordinate_lookup(coordinate_entries),
        "coordinate_fallback_lookup": _build_coordinate_fallback_lookup(coordinate_entries),
        "context_coordinate_lookup": _build_context_coordinate_lookup(coordinate_point_observations),
        "same_part_coordinate_lookup": _build_same_part_coordinate_lookup(coordinate_point_observations),
        "token_observations": token_observations,
        "token_lookup": _build_token_lookup(token_observations),
        "min_continuation_lookup": _build_min_continuation_lookup(token_observations),
        "slot_fraction_observations": slot_fraction_observations,
        "slot_fraction_lookup": _build_slot_fraction_lookup(slot_fraction_observations),
        "value_digits": value_digits,
    }


def choose_token_for_fraction(
    *,
    target_part: str,
    dxf_row: dict[str, Any],
    slot: int,
    fraction: Fraction,
    token_observations: list[dict[str, Any]],
    token_lookup: dict[str, dict[tuple[Any, ...], list[tuple[str, str]]]] | None = None,
    min_continuation_lookup: dict[str, dict[tuple[Any, ...], list[tuple[str, int]]]] | None = None,
    fallback_continuation: str = "trimmed",
    allow_same_part_token_spelling: bool = False,
) -> tuple[str, str]:
    entity_type = str(dxf_row["type"])
    role = slot_role(entity_type, slot)

    if token_lookup is not None:
        keyed_candidates = [
            ("same_type_role_fraction", (entity_type, role, fraction)),
            ("same_role_fraction", (role, fraction)),
            ("same_fraction", (fraction,)),
        ]
        for source, key in keyed_candidates:
            entries = token_lookup.get(source, {}).get(key, [])
            candidates = [
                token
                for part, token in entries
                if allow_same_part_token_spelling or str(part) != target_part
            ]
            if candidates:
                return Counter(str(token) for token in candidates).most_common(1)[0][0], source

        min_digits = _choose_min_continuation_digits(
            target_part=target_part,
            dxf_row=dxf_row,
            slot=slot,
            min_continuation_lookup=min_continuation_lookup,
            fallback_continuation=fallback_continuation,
        )
        return (
            encode_ddc_number_fraction(fraction, continuation_digits=8, min_continuation_digits=min_digits),
            f"encoded_fraction_fallback:{fallback_continuation}:{min_digits}",
        )

    candidate_sets = [
        (
            "same_type_role_fraction",
            [
                row["token"]
                for row in token_observations
                if (allow_same_part_token_spelling or str(row["part"]) != target_part)
                and row["dxf_type"] == entity_type
                and row["role"] == role
                and row["fraction"] == fraction
            ],
        ),
        (
            "same_role_fraction",
            [
                row["token"]
                for row in token_observations
                if (allow_same_part_token_spelling or str(row["part"]) != target_part)
                and row["role"] == role
                and row["fraction"] == fraction
            ],
        ),
        (
            "same_fraction",
            [
                row["token"]
                for row in token_observations
                if (allow_same_part_token_spelling or str(row["part"]) != target_part)
                and row["fraction"] == fraction
            ],
        ),
    ]
    for source, candidates in candidate_sets:
        if candidates:
            return Counter(str(token) for token in candidates).most_common(1)[0][0], source

    min_digits = _choose_min_continuation_digits(
        target_part=target_part,
        dxf_row=dxf_row,
        slot=slot,
        min_continuation_lookup=min_continuation_lookup,
        fallback_continuation=fallback_continuation,
    )
    return (
        encode_ddc_number_fraction(fraction, continuation_digits=8, min_continuation_digits=min_digits),
        f"encoded_fraction_fallback:{fallback_continuation}:{min_digits}",
    )


def _pick_context_coordinate_fraction(
    *,
    target_part: str,
    row_index: int,
    dxf_row: dict[str, Any],
    dxf_rows: list[dict[str, Any]],
    axis: str,
    point_role: str,
    visible_value: float,
    point_x: float,
    point_y: float,
    model: dict[str, Any],
    allow_same_part_coordinate_fallback: bool,
    prefer_literal_geometry: bool = False,
) -> tuple[Fraction, bool, str]:
    value_digits = int(model["value_digits"])
    value_key = _value_key(float(visible_value), digits=value_digits)
    if allow_same_part_coordinate_fallback:
        exact_key = (target_part, row_index + 1, point_role, axis)
        if exact_key in model.get("same_part_coordinate_lookup", {}):
            return model["same_part_coordinate_lookup"][exact_key], True, "same_part_exact_row"

    if prefer_literal_geometry:
        entity_type = str(dxf_row["type"])
        dyadic_fraction = _visible_dyadic_fraction(float(visible_value), digits=value_digits)
        if entity_type == "LINE" and dyadic_fraction is not None:
            return dyadic_fraction, True, "literal_dyadic_line"
        if entity_type == "ARC":
            if point_role in {"start", "end"} and not _arc_has_cardinal_endpoints(dxf_row):
                return Fraction(str(float(visible_value))), True, "literal_raw_noncardinal_arc"
            if dyadic_fraction is not None and (
                point_role == "center" or (point_role in {"start", "end"} and _arc_has_cardinal_endpoints(dxf_row))
            ):
                return dyadic_fraction, True, "literal_dyadic_cardinal_arc"
        if entity_type == "CIRCLE" and dyadic_fraction is not None:
            return dyadic_fraction, True, "literal_dyadic_circle"

    row = {
        "axis": axis,
        "value_key": value_key,
        "point_role": point_role,
        "visible_point_key": _point_key(point_x, point_y, digits=value_digits),
        **_row_context(dxf_rows, row_index, value_digits=value_digits),
    }
    for source in CONTEXT_COORDINATE_SOURCES:
        entries = model.get("context_coordinate_lookup", {}).get(source, {}).get(
            _context_coordinate_key(row, source),
            [],
        )
        candidates = [
            fraction
            for part, fraction in entries
            if allow_same_part_coordinate_fallback or str(part) != target_part
        ]
        if candidates:
            return _choose_coordinate_fraction(candidates, value_key), True, source

    return Fraction(str(float(visible_value))), False, "visible_raw_fallback"


def predicted_context_slot_fractions(
    *,
    part: str,
    dxf_rows: list[dict[str, Any]],
    row_index: int,
    model: dict[str, Any],
    allow_same_part_coordinate_fallback: bool = False,
    prefer_literal_geometry: bool = False,
) -> dict[int, tuple[Fraction, str, bool, str]]:
    dxf_row = dxf_rows[row_index]
    entity_type = str(dxf_row["type"])

    def pick(axis: str, point_role: str, point: Any) -> tuple[Fraction, bool, str]:
        value = float(point[0]) if axis == "x" else float(point[1])
        return _pick_context_coordinate_fraction(
            target_part=part,
            row_index=row_index,
            dxf_row=dxf_row,
            dxf_rows=dxf_rows,
            axis=axis,
            point_role=point_role,
            visible_value=value,
            point_x=float(point[0]),
            point_y=float(point[1]),
            model=model,
            allow_same_part_coordinate_fallback=allow_same_part_coordinate_fallback,
            prefer_literal_geometry=prefer_literal_geometry,
        )

    value_digits = int(model["value_digits"])
    if entity_type == "LINE":
        start = dxf_row["normalized_start"]
        end = dxf_row["normalized_end"]
        start_x, start_x_covered, start_x_source = pick("x", "start", start)
        start_y, start_y_covered, start_y_source = pick("y", "start", start)
        end_x, end_x_covered, end_x_source = pick("x", "end", end)
        end_y, end_y_covered, end_y_source = pick("y", "end", end)
        return {
            0: (
                start_x,
                _value_key(float(start[0]), digits=value_digits),
                start_x_covered,
                start_x_source,
            ),
            1: (
                start_y,
                _value_key(float(start[1]), digits=value_digits),
                start_y_covered,
                start_y_source,
            ),
            2: (
                end_x - start_x,
                _value_key(float(end[0]) - float(start[0]), digits=value_digits),
                start_x_covered and end_x_covered,
                f"{start_x_source}->{end_x_source}",
            ),
            3: (
                end_y - start_y,
                _value_key(float(end[1]) - float(start[1]), digits=value_digits),
                start_y_covered and end_y_covered,
                f"{start_y_source}->{end_y_source}",
            ),
        }

    if entity_type == "ARC":
        start = dxf_row["normalized_start_point"]
        end = dxf_row["normalized_end_point"]
        center = dxf_row["normalized_center"]
        start_x, start_x_covered, start_x_source = pick("x", "start", start)
        start_y, start_y_covered, start_y_source = pick("y", "start", start)
        end_x, end_x_covered, end_x_source = pick("x", "end", end)
        end_y, end_y_covered, end_y_source = pick("y", "end", end)
        center_x, center_x_covered, center_x_source = pick("x", "center", center)
        center_y, center_y_covered, center_y_source = pick("y", "center", center)
        return {
            0: (
                start_x,
                _value_key(float(start[0]), digits=value_digits),
                start_x_covered,
                start_x_source,
            ),
            1: (
                start_y,
                _value_key(float(start[1]), digits=value_digits),
                start_y_covered,
                start_y_source,
            ),
            2: (
                end_x - start_x,
                _value_key(float(end[0]) - float(start[0]), digits=value_digits),
                start_x_covered and end_x_covered,
                f"{start_x_source}->{end_x_source}",
            ),
            3: (
                end_y - start_y,
                _value_key(float(end[1]) - float(start[1]), digits=value_digits),
                start_y_covered and end_y_covered,
                f"{start_y_source}->{end_y_source}",
            ),
            4: (
                center_x - start_x,
                _value_key(float(center[0]) - float(start[0]), digits=value_digits),
                center_x_covered and start_x_covered,
                f"{start_x_source}->{center_x_source}",
            ),
            5: (
                center_y - start_y,
                _value_key(float(center[1]) - float(start[1]), digits=value_digits),
                center_y_covered and start_y_covered,
                f"{start_y_source}->{center_y_source}",
            ),
            6: (Fraction(1), _value_key(1.0, digits=value_digits), True, "constant"),
            9: (Fraction(1), _value_key(1.0, digits=value_digits), True, "constant"),
        }

    if entity_type == "CIRCLE":
        radius = float(dxf_row["radius"])
        center = dxf_row["normalized_center"]
        start = [float(center[0]) + radius, float(center[1])]
        start_x, start_x_covered, start_x_source = pick("x", "start", start)
        start_y, start_y_covered, start_y_source = pick("y", "start", start)
        center_x, center_x_covered, center_x_source = pick("x", "center", center)
        center_y, center_y_covered, center_y_source = pick("y", "center", center)
        return {
            0: (
                start_x,
                _value_key(float(start[0]), digits=value_digits),
                start_x_covered,
                start_x_source,
            ),
            1: (
                start_y,
                _value_key(float(start[1]), digits=value_digits),
                start_y_covered,
                start_y_source,
            ),
            4: (
                center_x - start_x,
                _value_key(float(center[0]) - float(start[0]), digits=value_digits),
                center_x_covered and start_x_covered,
                f"{start_x_source}->{center_x_source}",
            ),
            5: (
                center_y - start_y,
                _value_key(float(center[1]) - float(start[1]), digits=value_digits),
                center_y_covered and start_y_covered,
                f"{start_y_source}->{center_y_source}",
            ),
            6: (Fraction(1), _value_key(1.0, digits=value_digits), True, "constant"),
            9: (Fraction(1), _value_key(1.0, digits=value_digits), True, "constant"),
        }

    return {}


def predict_geometry_tokens(
    *,
    target_part: str,
    dxf_row: dict[str, Any],
    dxf_rows: list[dict[str, Any]] | None = None,
    row_index: int | None = None,
    template_ddc_row: dict[str, Any],
    model: dict[str, Any],
    coordinate_resolver: str = "value",
    fallback_continuation: str = "trimmed",
    allow_same_part_coordinate_fallback: bool = False,
    allow_same_part_token_spelling: bool = False,
    prefer_literal_geometry: bool = False,
    use_slot_value_fractions: bool = False,
) -> tuple[list[str], list[dict[str, Any]]]:
    token_count = len(list(template_ddc_row.get("tokens") or []))
    tokens = [""] * token_count
    slot_reports: list[dict[str, Any]] = []
    if coordinate_resolver == "context":
        if dxf_rows is None or row_index is None:
            raise ValueError("context coordinate resolver requires dxf_rows and row_index")
        predictions = predicted_context_slot_fractions(
            part=target_part,
            dxf_rows=dxf_rows,
            row_index=int(row_index),
            model=model,
            allow_same_part_coordinate_fallback=allow_same_part_coordinate_fallback,
            prefer_literal_geometry=prefer_literal_geometry,
        )
    elif coordinate_resolver == "value":
        predictions = {
            slot: (fraction, visible_value_key, coordinate_covered, "value")
            for slot, (fraction, visible_value_key, coordinate_covered) in predicted_slot_fractions(
                part=target_part,
                dxf_row=dxf_row,
                coordinate_lookup=model["coordinate_lookup"],
                coordinate_entries=model["coordinate_entries"],
                coordinate_fallback_lookup=model["coordinate_fallback_lookup"],
                allow_same_part_fallback=allow_same_part_coordinate_fallback,
                value_digits=int(model["value_digits"]),
            ).items()
        }
    else:
        raise ValueError(f"Unsupported coordinate resolver: {coordinate_resolver}")

    for slot, (fraction, visible_value_key, coordinate_covered, coordinate_source) in sorted(predictions.items()):
        if slot >= token_count:
            continue
        if use_slot_value_fractions:
            slot_fraction, slot_source = _pick_slot_fraction(
                target_part=target_part,
                dxf_row=dxf_row,
                slot=slot,
                visible_value_key=visible_value_key,
                model=model,
            )
            if slot_fraction is not None:
                fraction = slot_fraction
                coordinate_covered = True
                coordinate_source = f"{coordinate_source}->{slot_source}"
        token, source = choose_token_for_fraction(
            target_part=target_part,
            dxf_row=dxf_row,
            slot=slot,
            fraction=fraction,
            token_observations=model["token_observations"],
            token_lookup=model.get("token_lookup"),
            min_continuation_lookup=model.get("min_continuation_lookup"),
            fallback_continuation=fallback_continuation,
            allow_same_part_token_spelling=allow_same_part_token_spelling,
        )
        tokens[slot] = token
        slot_reports.append(
            {
                "slot": slot,
                "role": slot_role(str(dxf_row["type"]), slot),
                "visible_value_key": visible_value_key,
                "coordinate_covered": coordinate_covered,
                "coordinate_source": coordinate_source,
                "token_source": source,
                "token": token,
            }
        )
    return tokens, slot_reports


def _replace_template_geometry(
    template_text: str,
    generated_geometry_data: list[str],
) -> str:
    match = DDC_BLOCK_RE.search(template_text)
    if match is None:
        raise RuntimeError("No DDC CDATA block found in template symbol.")

    geometry_index = 0
    body_lines: list[str] = []
    for line in match.group(2).splitlines():
        fields = line.split(",")
        if fields and fields[0] in {"G", "H"}:
            if geometry_index >= len(generated_geometry_data):
                raise RuntimeError("Template has more DDC geometry rows than generated rows.")
            while len(fields) <= 10:
                fields.append("")
            fields[10] = generated_geometry_data[geometry_index]
            geometry_index += 1
            body_lines.append(",".join(fields))
            continue
        body_lines.append(line)

    if geometry_index != len(generated_geometry_data):
        raise RuntimeError("Generated more DDC geometry rows than template contains.")

    new_block = "\n".join(body_lines)
    if match.group(2).endswith("\n"):
        new_block += "\n"
    return template_text[: match.start(2)] + new_block + template_text[match.end(2) :]


def _compare_tokens(generated: list[str], oracle: list[str]) -> dict[str, Any]:
    total = max(len(generated), len(oracle))
    exact = 0
    decoded_close = 0
    examples: list[dict[str, Any]] = []
    for slot in range(total):
        generated_token = generated[slot] if slot < len(generated) else ""
        oracle_token = oracle[slot] if slot < len(oracle) else ""
        is_exact = generated_token == oracle_token
        exact += int(is_exact)
        try:
            decoded_abs_diff = abs(
                float(decode_ddc_number_fraction(generated_token) - decode_ddc_number_fraction(oracle_token))
            )
        except Exception:
            decoded_abs_diff = None
        decoded_close += int(decoded_abs_diff is not None and decoded_abs_diff <= 1e-12)
        if not is_exact and len(examples) < 20:
            examples.append(
                {
                    "slot": slot,
                    "generated_token": generated_token,
                    "oracle_token": oracle_token,
                    "decoded_abs_diff": decoded_abs_diff,
                }
            )
    return {
        "total_slots": total,
        "exact_slots": exact,
        "exact_slot_ratio": exact / total if total else 0.0,
        "decoded_close_1e_12_slots": decoded_close,
        "mismatch_examples": examples,
    }


def write_coordinate_model_prototype(
    *,
    part: str,
    dxf_path: Path,
    template_sym: Path,
    out_path: Path,
    model: dict[str, Any],
    coordinate_resolver: str = "value",
    fallback_continuation: str = "trimmed",
    allow_same_part_coordinate_fallback: bool = False,
    allow_same_part_token_spelling: bool = False,
    prefer_literal_geometry: bool = False,
    use_slot_value_fractions: bool = False,
    allow_outside_lab: bool = False,
) -> dict[str, Any]:
    _ensure_lab_output(out_path, allow_outside_lab=allow_outside_lab)
    dxf_rows, _bounds = read_dxf_entities(dxf_path)
    ddc_rows = read_ddc_records(template_sym)
    if len(dxf_rows) != len(ddc_rows):
        raise RuntimeError(f"{part}: DXF/DDC count mismatch: {len(dxf_rows)} != {len(ddc_rows)}")
    expected_sequence = [_record_for_dxf_type(str(row["type"])) for row in dxf_rows]
    template_sequence = [str(row["record"]) for row in ddc_rows]
    if expected_sequence != template_sequence:
        raise RuntimeError(f"{part}: DXF/DDC type sequence mismatch.")

    generated_geometry_data: list[str] = []
    row_reports: list[dict[str, Any]] = []
    exact_records = 0
    total_slots = 0
    exact_slots = 0
    decoded_close_slots = 0
    for row_index, (dxf_row, ddc_row) in enumerate(zip(dxf_rows, ddc_rows), start=1):
        tokens, slot_reports = predict_geometry_tokens(
            target_part=part,
            dxf_row=dxf_row,
            dxf_rows=dxf_rows,
            row_index=row_index - 1,
            template_ddc_row=ddc_row,
            model=model,
            coordinate_resolver=coordinate_resolver,
            fallback_continuation=fallback_continuation,
            allow_same_part_coordinate_fallback=allow_same_part_coordinate_fallback,
            allow_same_part_token_spelling=allow_same_part_token_spelling,
            prefer_literal_geometry=prefer_literal_geometry,
            use_slot_value_fractions=use_slot_value_fractions,
        )
        generated_geometry_data.append(".".join(tokens))
        comparison = _compare_tokens(tokens, list(ddc_row.get("tokens") or []))
        exact_records += int(tokens == list(ddc_row.get("tokens") or []))
        total_slots += int(comparison["total_slots"])
        exact_slots += int(comparison["exact_slots"])
        decoded_close_slots += int(comparison["decoded_close_1e_12_slots"])
        row_reports.append(
            {
                "row_index": row_index,
                "dxf_type": str(dxf_row["type"]),
                "record": str(ddc_row["record"]),
                "exact_record": tokens == list(ddc_row.get("tokens") or []),
                "comparison": comparison,
                "slots": slot_reports,
            }
        )

    template_text = template_sym.read_text(encoding="utf-8", errors="replace")
    output_text = _replace_template_geometry(template_text, generated_geometry_data)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = out_path.with_name(f"{out_path.name}.tmp")
    temp_path.write_text(output_text, encoding="utf-8")
    temp_path.replace(out_path)

    return {
        "part": part,
        "dxf_path": str(dxf_path),
        "template_sym": str(template_sym),
        "out_path": str(out_path),
        "entity_count": len(dxf_rows),
        "exact_geometry_records": exact_records,
        "total_geometry_records": len(ddc_rows),
        "exact_record_ratio": exact_records / len(ddc_rows) if ddc_rows else 0.0,
        "exact_slots": exact_slots,
        "total_slots": total_slots,
        "exact_slot_ratio": exact_slots / total_slots if total_slots else 0.0,
        "decoded_close_1e_12_slots": decoded_close_slots,
        "decoded_close_1e_12_ratio": decoded_close_slots / total_slots if total_slots else 0.0,
        "coordinate_resolver": coordinate_resolver,
        "fallback_continuation": fallback_continuation,
        "allow_same_part_coordinate_fallback": allow_same_part_coordinate_fallback,
        "allow_same_part_token_spelling": allow_same_part_token_spelling,
        "prefer_literal_geometry": prefer_literal_geometry,
        "use_slot_value_fractions": use_slot_value_fractions,
        "rows": row_reports,
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    assert_w_drive_write_allowed(path, operation="write coordinate-model SYM prototype report")
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.tmp")
    temp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True) + "\n", encoding="utf-8")
    temp_path.replace(path)


def _part_names(args: argparse.Namespace, dxf_folder: Path, sym_folder: Path) -> list[str]:
    if args.part:
        return [str(part) for part in args.part]
    dxf_parts = {path.stem for path in dxf_folder.glob("*.dxf")}
    sym_parts = {path.stem for path in sym_folder.glob("*.sym")}
    return sorted(dxf_parts & sym_parts, key=str.casefold)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Lab-only SYM writer using the exported-DXF hidden-coordinate token model.",
    )
    parser.add_argument("--dxf-folder", type=Path, required=True, help="Folder containing RADAN-exported DXFs.")
    parser.add_argument("--sym-folder", type=Path, required=True, help="Folder containing known-good RADAN SYMs.")
    parser.add_argument("--out-dir", type=Path, required=True, help=f"Output folder under {DEFAULT_LAB_ROOT}.")
    parser.add_argument("--part", action="append", help="Part stem to generate. Defaults to all matched parts.")
    parser.add_argument("--value-digits", type=int, default=6)
    parser.add_argument(
        "--coordinate-resolver",
        choices=("value", "context"),
        default="value",
        help="Hidden-coordinate resolver. 'value' is the baseline; 'context' adds entity/topology context.",
    )
    parser.add_argument(
        "--fallback-continuation",
        choices=("trimmed", "role", "type-role"),
        default="trimmed",
        help="How to choose continuation length when no exact token spelling is known.",
    )
    parser.add_argument(
        "--allow-same-part-coordinate-fallback",
        action="store_true",
        help="Oracle mode: allow hidden coordinates learned from the target part itself.",
    )
    parser.add_argument(
        "--allow-same-part-token-spelling",
        action="store_true",
        help="Oracle mode: allow token spelling learned from the target part itself.",
    )
    parser.add_argument(
        "--prefer-literal-geometry",
        action="store_true",
        help=(
            "Lab mode: prefer literal dyadic LINE/cardinal-arc/circle coordinates and raw non-cardinal arc "
            "points before borrowing hidden coordinates from other parts."
        ),
    )
    parser.add_argument(
        "--use-slot-value-fractions",
        action="store_true",
        help="Lab mode: use leave-one-part-out hidden fractions learned for direct slot value/type/role keys.",
    )
    parser.add_argument("--allow-outside-lab", action="store_true")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    _ensure_lab_output(out_dir / "__probe__.sym", allow_outside_lab=bool(args.allow_outside_lab))
    model = build_coordinate_model(args.dxf_folder, args.sym_folder, value_digits=int(args.value_digits))
    part_reports: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = list(model["skipped"])
    for part in _part_names(args, args.dxf_folder, args.sym_folder):
        dxf_path = Path(args.dxf_folder) / f"{part}.dxf"
        sym_path = Path(args.sym_folder) / f"{part}.sym"
        if not dxf_path.exists() or not sym_path.exists():
            skipped.append({"part": part, "reason": "missing_target_dxf_or_sym"})
            continue
        try:
            report = write_coordinate_model_prototype(
                part=part,
                dxf_path=dxf_path,
                template_sym=sym_path,
                out_path=out_dir / f"{part}.sym",
                model=model,
                coordinate_resolver=str(args.coordinate_resolver),
                fallback_continuation=str(args.fallback_continuation),
                allow_same_part_coordinate_fallback=bool(args.allow_same_part_coordinate_fallback),
                allow_same_part_token_spelling=bool(args.allow_same_part_token_spelling),
                prefer_literal_geometry=bool(args.prefer_literal_geometry),
                use_slot_value_fractions=bool(args.use_slot_value_fractions),
                allow_outside_lab=bool(args.allow_outside_lab),
            )
        except Exception as exc:
            skipped.append({"part": part, "reason": f"{type(exc).__name__}: {exc}"})
            continue
        part_reports.append(report)

    total_slots = sum(int(row["total_slots"]) for row in part_reports)
    exact_slots = sum(int(row["exact_slots"]) for row in part_reports)
    total_records = sum(int(row["total_geometry_records"]) for row in part_reports)
    exact_records = sum(int(row["exact_geometry_records"]) for row in part_reports)
    payload = {
        "schema_version": 1,
        "dxf_folder": str(args.dxf_folder),
        "sym_folder": str(args.sym_folder),
        "out_dir": str(out_dir),
        "value_digits": int(args.value_digits),
        "coordinate_resolver": str(args.coordinate_resolver),
        "fallback_continuation": str(args.fallback_continuation),
        "allow_same_part_coordinate_fallback": bool(args.allow_same_part_coordinate_fallback),
        "allow_same_part_token_spelling": bool(args.allow_same_part_token_spelling),
        "prefer_literal_geometry": bool(args.prefer_literal_geometry),
        "use_slot_value_fractions": bool(args.use_slot_value_fractions),
        "training_part_count": len(model["pairs"]),
        "coordinate_entry_count": len(model["coordinate_entries"]),
        "coordinate_point_observation_count": len(model["coordinate_point_observations"]),
        "slot_fraction_observation_count": len(model["slot_fraction_observations"]),
        "token_observation_count": len(model["token_observations"]),
        "generated_part_count": len(part_reports),
        "skipped": skipped,
        "exact_geometry_records": exact_records,
        "total_geometry_records": total_records,
        "exact_record_ratio": exact_records / total_records if total_records else 0.0,
        "exact_slots": exact_slots,
        "total_slots": total_slots,
        "exact_slot_ratio": exact_slots / total_slots if total_slots else 0.0,
        "parts": part_reports,
    }
    write_json(out_dir / "coordinate_model_writer_report.json", payload)
    print(
        json.dumps(
            {
                "generated_part_count": payload["generated_part_count"],
                "exact_record_ratio": payload["exact_record_ratio"],
                "exact_slot_ratio": payload["exact_slot_ratio"],
                "skipped_count": len(skipped),
                "report": str(out_dir / "coordinate_model_writer_report.json"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
