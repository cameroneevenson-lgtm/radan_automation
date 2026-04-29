from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from fractions import Fraction
from pathlib import Path
from typing import Any, Callable

from ddc_corpus import read_ddc_records, read_dxf_entities
from ddc_number_codec import decode_ddc_number_fraction, encode_ddc_number_fraction
from path_safety import assert_w_drive_write_allowed


def value_key(value: float, *, digits: int = 6) -> str:
    rounded = round(float(value), int(digits))
    if rounded == 0:
        rounded = 0.0
    return f"{rounded:.{int(digits)}f}"


def token_fraction(token: str) -> Fraction:
    return decode_ddc_number_fraction(token) if token else Fraction(0)


def min_continuation_digits(token: str) -> int:
    return max(0, len(token) - 3) if token else 0


def token_at(row: dict[str, Any], slot: int) -> str:
    tokens = list(row.get("tokens") or [])
    return str(tokens[slot]) if slot < len(tokens) else ""


def slot_role(entity_type: str, slot: int) -> str:
    if entity_type == "LINE":
        return {0: "start_x", 1: "start_y", 2: "delta_x", 3: "delta_y"}.get(slot, f"slot_{slot}")
    if entity_type == "ARC":
        return {
            0: "start_x",
            1: "start_y",
            2: "delta_x",
            3: "delta_y",
            4: "center_delta_x",
            5: "center_delta_y",
            6: "one_a",
            9: "one_b",
        }.get(slot, f"slot_{slot}")
    if entity_type == "CIRCLE":
        return {
            0: "start_x",
            1: "start_y",
            4: "center_delta_x",
            5: "center_delta_y",
            6: "one_a",
            9: "one_b",
        }.get(slot, f"slot_{slot}")
    return f"slot_{slot}"


def _add_coordinate(
    rows: list[dict[str, Any]],
    *,
    part: str,
    axis: str,
    visible_value: float,
    fraction: Fraction,
    value_digits: int,
) -> None:
    rows.append(
        {
            "part": part,
            "axis": axis,
            "value_key": value_key(visible_value, digits=value_digits),
            "fraction": fraction,
        }
    )


def coordinate_entries_for_part(
    *,
    part: str,
    dxf_rows: list[dict[str, Any]],
    ddc_rows: list[dict[str, Any]],
    value_digits: int = 6,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for dxf_row, ddc_row in zip(dxf_rows, ddc_rows):
        entity_type = str(dxf_row["type"])
        if entity_type == "LINE":
            start_x = token_fraction(token_at(ddc_row, 0))
            start_y = token_fraction(token_at(ddc_row, 1))
            end_x = start_x + token_fraction(token_at(ddc_row, 2))
            end_y = start_y + token_fraction(token_at(ddc_row, 3))
            _add_coordinate(
                rows,
                part=part,
                axis="x",
                visible_value=float(dxf_row["normalized_start"][0]),
                fraction=start_x,
                value_digits=value_digits,
            )
            _add_coordinate(
                rows,
                part=part,
                axis="y",
                visible_value=float(dxf_row["normalized_start"][1]),
                fraction=start_y,
                value_digits=value_digits,
            )
            _add_coordinate(
                rows,
                part=part,
                axis="x",
                visible_value=float(dxf_row["normalized_end"][0]),
                fraction=end_x,
                value_digits=value_digits,
            )
            _add_coordinate(
                rows,
                part=part,
                axis="y",
                visible_value=float(dxf_row["normalized_end"][1]),
                fraction=end_y,
                value_digits=value_digits,
            )
        elif entity_type == "ARC":
            start_x = token_fraction(token_at(ddc_row, 0))
            start_y = token_fraction(token_at(ddc_row, 1))
            end_x = start_x + token_fraction(token_at(ddc_row, 2))
            end_y = start_y + token_fraction(token_at(ddc_row, 3))
            center_x = start_x + token_fraction(token_at(ddc_row, 4))
            center_y = start_y + token_fraction(token_at(ddc_row, 5))
            for axis, visible_value, fraction in (
                ("x", dxf_row["normalized_start_point"][0], start_x),
                ("y", dxf_row["normalized_start_point"][1], start_y),
                ("x", dxf_row["normalized_end_point"][0], end_x),
                ("y", dxf_row["normalized_end_point"][1], end_y),
                ("x", dxf_row["normalized_center"][0], center_x),
                ("y", dxf_row["normalized_center"][1], center_y),
            ):
                _add_coordinate(
                    rows,
                    part=part,
                    axis=axis,
                    visible_value=float(visible_value),
                    fraction=fraction,
                    value_digits=value_digits,
                )
        elif entity_type == "CIRCLE":
            start_x = token_fraction(token_at(ddc_row, 0))
            start_y = token_fraction(token_at(ddc_row, 1))
            center_x = start_x + token_fraction(token_at(ddc_row, 4))
            center_y = start_y + token_fraction(token_at(ddc_row, 5))
            radius = float(dxf_row["radius"])
            visible_start_x = float(dxf_row["normalized_center"][0]) + radius
            visible_start_y = float(dxf_row["normalized_center"][1])
            for axis, visible_value, fraction in (
                ("x", visible_start_x, start_x),
                ("y", visible_start_y, start_y),
                ("x", dxf_row["normalized_center"][0], center_x),
                ("y", dxf_row["normalized_center"][1], center_y),
            ):
                _add_coordinate(
                    rows,
                    part=part,
                    axis=axis,
                    visible_value=float(visible_value),
                    fraction=fraction,
                    value_digits=value_digits,
                )
    return rows


def _choose_fraction(candidates: list[Fraction], visible_value_key: str) -> Fraction:
    if not candidates:
        return Fraction(visible_value_key)
    counts = Counter(candidates)
    target = Fraction(visible_value_key)
    return sorted(counts.items(), key=lambda item: (-item[1], abs(float(item[0] - target))))[0][0]


def _build_coordinate_lookup(
    coordinate_entries: list[dict[str, Any]],
) -> dict[tuple[str, str], dict[str, Fraction]]:
    by_key: dict[tuple[str, str], list[tuple[str, Fraction]]] = defaultdict(list)
    for row in coordinate_entries:
        by_key[(str(row["axis"]), str(row["value_key"]))].append((str(row["part"]), row["fraction"]))

    lookup: dict[tuple[str, str], dict[str, Fraction]] = {}
    for key, rows in by_key.items():
        by_excluded_part: dict[str, Fraction] = {}
        for part in {part for part, _ in rows}:
            candidates = [fraction for candidate_part, fraction in rows if candidate_part != part]
            if candidates:
                by_excluded_part[part] = _choose_fraction(candidates, key[1])
        lookup[key] = by_excluded_part
    return lookup


def _build_coordinate_fallback_lookup(coordinate_entries: list[dict[str, Any]]) -> dict[tuple[str, str], Fraction]:
    by_key: dict[tuple[str, str], list[Fraction]] = defaultdict(list)
    for row in coordinate_entries:
        by_key[(str(row["axis"]), str(row["value_key"]))].append(row["fraction"])
    return {key: _choose_fraction(candidates, key[1]) for key, candidates in by_key.items()}


def _pick_coordinate_fraction(
    *,
    coordinate_lookup: dict[tuple[str, str], dict[str, Fraction]],
    coordinate_fallback_lookup: dict[tuple[str, str], Fraction] | None = None,
    allow_same_part_fallback: bool = False,
    coordinate_entries: list[dict[str, Any]],
    part: str,
    axis: str,
    visible_value: float,
    value_digits: int,
) -> tuple[Fraction, bool]:
    key = (axis, value_key(visible_value, digits=value_digits))
    if part in coordinate_lookup.get(key, {}):
        return coordinate_lookup[key][part], True
    if allow_same_part_fallback and coordinate_fallback_lookup and key in coordinate_fallback_lookup:
        return coordinate_fallback_lookup[key], True
    candidates = [row["fraction"] for row in coordinate_entries if (row["axis"], row["value_key"]) == key]
    if allow_same_part_fallback and candidates:
        return _choose_fraction(candidates, key[1]), True
    return Fraction(key[1]), False


def predicted_slot_fractions(
    *,
    part: str,
    dxf_row: dict[str, Any],
    coordinate_lookup: dict[tuple[str, str], dict[str, Fraction]],
    coordinate_entries: list[dict[str, Any]],
    coordinate_fallback_lookup: dict[tuple[str, str], Fraction] | None = None,
    allow_same_part_fallback: bool = False,
    value_digits: int,
) -> dict[int, tuple[Fraction, str, bool]]:
    entity_type = str(dxf_row["type"])

    def pick(axis: str, value: float) -> tuple[Fraction, bool]:
        return _pick_coordinate_fraction(
            coordinate_lookup=coordinate_lookup,
            coordinate_fallback_lookup=coordinate_fallback_lookup,
            allow_same_part_fallback=allow_same_part_fallback,
            coordinate_entries=coordinate_entries,
            part=part,
            axis=axis,
            visible_value=value,
            value_digits=value_digits,
        )

    if entity_type == "LINE":
        start_x, start_x_covered = pick("x", float(dxf_row["normalized_start"][0]))
        start_y, start_y_covered = pick("y", float(dxf_row["normalized_start"][1]))
        end_x, end_x_covered = pick("x", float(dxf_row["normalized_end"][0]))
        end_y, end_y_covered = pick("y", float(dxf_row["normalized_end"][1]))
        return {
            0: (start_x, value_key(float(dxf_row["normalized_start"][0]), digits=value_digits), start_x_covered),
            1: (start_y, value_key(float(dxf_row["normalized_start"][1]), digits=value_digits), start_y_covered),
            2: (
                end_x - start_x,
                value_key(float(dxf_row["normalized_end"][0]) - float(dxf_row["normalized_start"][0]), digits=value_digits),
                start_x_covered and end_x_covered,
            ),
            3: (
                end_y - start_y,
                value_key(float(dxf_row["normalized_end"][1]) - float(dxf_row["normalized_start"][1]), digits=value_digits),
                start_y_covered and end_y_covered,
            ),
        }

    if entity_type == "ARC":
        start_x, start_x_covered = pick("x", float(dxf_row["normalized_start_point"][0]))
        start_y, start_y_covered = pick("y", float(dxf_row["normalized_start_point"][1]))
        end_x, end_x_covered = pick("x", float(dxf_row["normalized_end_point"][0]))
        end_y, end_y_covered = pick("y", float(dxf_row["normalized_end_point"][1]))
        center_x, center_x_covered = pick("x", float(dxf_row["normalized_center"][0]))
        center_y, center_y_covered = pick("y", float(dxf_row["normalized_center"][1]))
        return {
            0: (start_x, value_key(float(dxf_row["normalized_start_point"][0]), digits=value_digits), start_x_covered),
            1: (start_y, value_key(float(dxf_row["normalized_start_point"][1]), digits=value_digits), start_y_covered),
            2: (
                end_x - start_x,
                value_key(
                    float(dxf_row["normalized_end_point"][0]) - float(dxf_row["normalized_start_point"][0]),
                    digits=value_digits,
                ),
                start_x_covered and end_x_covered,
            ),
            3: (
                end_y - start_y,
                value_key(
                    float(dxf_row["normalized_end_point"][1]) - float(dxf_row["normalized_start_point"][1]),
                    digits=value_digits,
                ),
                start_y_covered and end_y_covered,
            ),
            4: (
                center_x - start_x,
                value_key(
                    float(dxf_row["normalized_center"][0]) - float(dxf_row["normalized_start_point"][0]),
                    digits=value_digits,
                ),
                center_x_covered and start_x_covered,
            ),
            5: (
                center_y - start_y,
                value_key(
                    float(dxf_row["normalized_center"][1]) - float(dxf_row["normalized_start_point"][1]),
                    digits=value_digits,
                ),
                center_y_covered and start_y_covered,
            ),
            6: (Fraction(1), value_key(1.0, digits=value_digits), True),
            9: (Fraction(1), value_key(1.0, digits=value_digits), True),
        }

    if entity_type == "CIRCLE":
        radius = float(dxf_row["radius"])
        visible_start_x = float(dxf_row["normalized_center"][0]) + radius
        visible_start_y = float(dxf_row["normalized_center"][1])
        start_x, start_x_covered = pick("x", visible_start_x)
        start_y, start_y_covered = pick("y", visible_start_y)
        center_x, center_x_covered = pick("x", float(dxf_row["normalized_center"][0]))
        center_y, center_y_covered = pick("y", float(dxf_row["normalized_center"][1]))
        return {
            0: (start_x, value_key(visible_start_x, digits=value_digits), start_x_covered),
            1: (start_y, value_key(visible_start_y, digits=value_digits), start_y_covered),
            4: (
                center_x - start_x,
                value_key(float(dxf_row["normalized_center"][0]) - visible_start_x, digits=value_digits),
                center_x_covered and start_x_covered,
            ),
            5: (
                center_y - start_y,
                value_key(float(dxf_row["normalized_center"][1]) - visible_start_y, digits=value_digits),
                center_y_covered and start_y_covered,
            ),
            6: (Fraction(1), value_key(1.0, digits=value_digits), True),
            9: (Fraction(1), value_key(1.0, digits=value_digits), True),
        }

    return {}


def _length_key(row: dict[str, Any], mode: str) -> tuple[Any, ...]:
    if mode == "default":
        return ("__none__",)
    if mode == "value":
        return (row["visible_value_key"],)
    if mode == "type_role":
        return (row["dxf_type"], row["role"])
    if mode == "type_role_value":
        return (row["dxf_type"], row["role"], row["visible_value_key"])
    raise ValueError(f"Unsupported length mode: {mode}")


def _choose_min_continuation(rows: list[dict[str, Any]], *, target: dict[str, Any], mode: str) -> int:
    if mode == "default":
        return 0
    candidates = [
        int(row["good_min_continuation_digits"])
        for row in rows
        if row["part"] != target["part"] and _length_key(row, mode) == _length_key(target, mode)
    ]
    if not candidates:
        return 0
    return Counter(candidates).most_common(1)[0][0]


def _build_min_continuation_lookup(
    rows: list[dict[str, Any]],
    *,
    mode: str,
) -> dict[tuple[str, tuple[Any, ...]], int]:
    if mode == "default":
        return {}

    by_key: dict[tuple[Any, ...], list[tuple[str, int]]] = defaultdict(list)
    for row in rows:
        by_key[_length_key(row, mode)].append((str(row["part"]), int(row["good_min_continuation_digits"])))

    lookup: dict[tuple[str, tuple[Any, ...]], int] = {}
    for key, entries in by_key.items():
        for part in {part for part, _digits in entries}:
            candidates = [digits for candidate_part, digits in entries if candidate_part != part]
            if candidates:
                lookup[(part, key)] = Counter(candidates).most_common(1)[0][0]
    return lookup


def evaluate_coordinate_token_model(
    *,
    dxf_folder: Path,
    sym_folder: Path,
    value_digits: int = 6,
    allow_same_part_fallback: bool = False,
) -> dict[str, Any]:
    part_pairs: list[dict[str, Any]] = []
    coordinate_entries: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []

    dxf_paths = {path.stem.casefold(): path for path in dxf_folder.glob("*.dxf")}
    sym_paths = {path.stem.casefold(): path for path in sym_folder.glob("*.sym")}
    for key in sorted(set(dxf_paths) | set(sym_paths)):
        dxf_path = dxf_paths.get(key)
        sym_path = sym_paths.get(key)
        if dxf_path is None or sym_path is None:
            skipped.append({"part": key, "reason": "missing_dxf" if dxf_path is None else "missing_sym"})
            continue
        dxf_rows, _bounds = read_dxf_entities(dxf_path)
        ddc_rows = read_ddc_records(sym_path)
        part_pairs.append({"part": dxf_path.stem, "dxf_rows": dxf_rows, "ddc_rows": ddc_rows})
        coordinate_entries.extend(
            coordinate_entries_for_part(
                part=dxf_path.stem,
                dxf_rows=dxf_rows,
                ddc_rows=ddc_rows,
                value_digits=value_digits,
            )
        )

    coordinate_lookup = _build_coordinate_lookup(coordinate_entries)
    coordinate_fallback_lookup = _build_coordinate_fallback_lookup(coordinate_entries)
    slot_rows: list[dict[str, Any]] = []
    for pair in part_pairs:
        part = str(pair["part"])
        for row_index, (dxf_row, ddc_row) in enumerate(zip(pair["dxf_rows"], pair["ddc_rows"]), start=1):
            predictions = predicted_slot_fractions(
                part=part,
                dxf_row=dxf_row,
                coordinate_lookup=coordinate_lookup,
                coordinate_entries=coordinate_entries,
                coordinate_fallback_lookup=coordinate_fallback_lookup,
                allow_same_part_fallback=allow_same_part_fallback,
                value_digits=value_digits,
            )
            for slot, (fraction, visible_value_key, covered) in predictions.items():
                good_token = token_at(ddc_row, slot)
                if not good_token:
                    continue
                slot_rows.append(
                    {
                        "part": part,
                        "row_index": row_index,
                        "dxf_type": str(dxf_row["type"]),
                        "slot": slot,
                        "role": slot_role(str(dxf_row["type"]), slot),
                        "visible_value_key": visible_value_key,
                        "predicted_fraction": fraction,
                        "coordinate_covered": covered,
                        "good_token": good_token,
                        "good_fraction": token_fraction(good_token),
                        "good_min_continuation_digits": min_continuation_digits(good_token),
                    }
                )

    evaluations = []
    for mode in ("default", "type_role", "type_role_value", "value"):
        min_continuation_lookup = _build_min_continuation_lookup(slot_rows, mode=mode)
        exact = 0
        decoded_equal = 0
        decoded_close = 0
        covered = 0
        examples: list[dict[str, Any]] = []
        for row in slot_rows:
            if mode == "default":
                min_digits = 0
            else:
                min_digits = min_continuation_lookup.get((str(row["part"]), _length_key(row, mode)), 0)
            predicted_token = encode_ddc_number_fraction(
                row["predicted_fraction"],
                continuation_digits=8,
                min_continuation_digits=min_digits,
            )
            is_exact = predicted_token == row["good_token"]
            exact += int(is_exact)
            decoded_equal += int(token_fraction(predicted_token) == row["good_fraction"])
            decoded_abs_diff = abs(float(token_fraction(predicted_token) - row["good_fraction"]))
            decoded_close += int(decoded_abs_diff <= 1e-12)
            covered += int(row["coordinate_covered"])
            if not is_exact and len(examples) < 20:
                examples.append(
                    {
                        "part": row["part"],
                        "row_index": row["row_index"],
                        "dxf_type": row["dxf_type"],
                        "slot": row["slot"],
                        "role": row["role"],
                        "visible_value_key": row["visible_value_key"],
                        "good_token": row["good_token"],
                        "predicted_token": predicted_token,
                        "decoded_abs_diff": decoded_abs_diff,
                    }
                )
        total = len(slot_rows)
        evaluations.append(
            {
                "length_mode": mode,
                "slot_count": total,
                "coordinate_coverage": covered / total if total else 0.0,
                "exact_token_match_count": exact,
                "exact_token_match_rate": exact / total if total else 0.0,
                "decoded_equal_count": decoded_equal,
                "decoded_equal_rate": decoded_equal / total if total else 0.0,
                "decoded_close_1e_12_count": decoded_close,
                "decoded_close_1e_12_rate": decoded_close / total if total else 0.0,
                "mismatch_examples": examples,
            }
        )

    coord_groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in coordinate_entries:
        coord_groups[(str(row["axis"]), str(row["value_key"]))].append(row)
    ambiguity_counts = Counter(len({row["fraction"] for row in rows}) for rows in coord_groups.values())

    return {
        "schema_version": 1,
        "dxf_folder": str(dxf_folder),
        "sym_folder": str(sym_folder),
        "value_digits": value_digits,
        "allow_same_part_fallback": allow_same_part_fallback,
        "part_count": len(part_pairs),
        "skipped": skipped,
        "coordinate_key_count": len(coord_groups),
        "coordinate_fraction_ambiguity_counts": dict(sorted(ambiguity_counts.items())),
        "supported_slot_count": len(slot_rows),
        "evaluations": evaluations,
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    assert_w_drive_write_allowed(path, operation="write exported coordinate-token model JSON")
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.tmp")
    temp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True) + "\n", encoding="utf-8")
    temp_path.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate a hidden-coordinate-first DDC token model using exported DXFs and known-good SYMs.",
    )
    parser.add_argument("--dxf-folder", type=Path, required=True)
    parser.add_argument("--sym-folder", type=Path, required=True)
    parser.add_argument("--out-json", type=Path)
    parser.add_argument("--value-digits", type=int, default=6)
    parser.add_argument(
        "--allow-same-part-fallback",
        action="store_true",
        help="Allow oracle-style fallback to hidden coordinates from the same part when no other part has that visible coordinate.",
    )
    args = parser.parse_args()

    payload = evaluate_coordinate_token_model(
        dxf_folder=args.dxf_folder,
        sym_folder=args.sym_folder,
        value_digits=args.value_digits,
        allow_same_part_fallback=bool(args.allow_same_part_fallback),
    )
    if args.out_json:
        write_json(args.out_json, payload)
    print(json.dumps({key: value for key, value in payload.items() if key != "skipped"}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
