from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

from ddc_corpus import read_ddc_records, read_dxf_entities
from ddc_number_codec import (
    ddc_number_mantissa_digits,
    ddc_number_mantissa_integer,
    decode_ddc_number_fraction,
)
from path_safety import assert_w_drive_write_allowed
from write_native_sym_prototype import encode_geometry_data


GEOMETRY_SLOTS_BY_TYPE: dict[str, dict[int, str]] = {
    "LINE": {
        0: "start_x",
        1: "start_y",
        2: "delta_x",
        3: "delta_y",
    },
    "ARC": {
        0: "start_x",
        1: "start_y",
        2: "delta_x",
        3: "delta_y",
        4: "center_delta_x",
        5: "center_delta_y",
        6: "one_a",
        9: "one_b",
    },
    "CIRCLE": {
        0: "start_x",
        1: "start_y",
        4: "center_delta_x",
        5: "center_delta_y",
        6: "one_a",
        9: "one_b",
    },
}


def _rounded_float(value: float, digits: int = 9) -> float:
    rounded = round(float(value), digits)
    if rounded == 0:
        return 0.0
    return rounded


def value_key(value: float, *, digits: int = 6) -> str:
    rounded = round(float(value), int(digits))
    if rounded == 0:
        rounded = 0.0
    return f"{rounded:.{int(digits)}f}"


def _slot_role(entity_type: str, slot: int) -> str:
    return GEOMETRY_SLOTS_BY_TYPE.get(str(entity_type), {}).get(int(slot), f"slot_{slot}")


def slot_values_for_dxf_row(dxf_row: dict[str, Any]) -> dict[int, float]:
    entity_type = str(dxf_row["type"])
    if entity_type == "LINE":
        start = [float(value) for value in dxf_row["normalized_start"]]
        end = [float(value) for value in dxf_row["normalized_end"]]
        return {
            0: _rounded_float(start[0]),
            1: _rounded_float(start[1]),
            2: _rounded_float(end[0] - start[0]),
            3: _rounded_float(end[1] - start[1]),
        }

    if entity_type == "ARC":
        start = [float(value) for value in dxf_row["normalized_start_point"]]
        end = [float(value) for value in dxf_row["normalized_end_point"]]
        center = [float(value) for value in dxf_row["normalized_center"]]
        return {
            0: _rounded_float(start[0]),
            1: _rounded_float(start[1]),
            2: _rounded_float(end[0] - start[0]),
            3: _rounded_float(end[1] - start[1]),
            4: _rounded_float(center[0] - start[0]),
            5: _rounded_float(center[1] - start[1]),
            6: 1.0,
            9: 1.0,
        }

    if entity_type == "CIRCLE":
        center = [float(value) for value in dxf_row["normalized_center"]]
        radius = float(dxf_row["radius"])
        start_x = center[0] + radius
        start_y = center[1]
        return {
            0: _rounded_float(start_x),
            1: _rounded_float(start_y),
            4: _rounded_float(center[0] - start_x),
            5: _rounded_float(center[1] - start_y),
            6: 1.0,
            9: 1.0,
        }

    raise ValueError(f"Unsupported DXF entity type: {entity_type}")


def _decode_token(token: str) -> float:
    if token == "":
        return 0.0
    return float(decode_ddc_number_fraction(token))


def _mantissa_delta(good_token: str, current_token: str) -> int | None:
    if not good_token or not current_token:
        return None
    pad_to = max(len(ddc_number_mantissa_digits(good_token)), len(ddc_number_mantissa_digits(current_token)))
    return ddc_number_mantissa_integer(good_token, pad_to=pad_to) - ddc_number_mantissa_integer(
        current_token,
        pad_to=pad_to,
    )


def _token_deltas(good_token: str, current_token: str) -> dict[str, Any]:
    good_value = _decode_token(good_token)
    current_value = _decode_token(current_token)
    return {
        "good_decoded": good_value,
        "current_decoded": current_value,
        "good_minus_current_decoded": good_value - current_value,
        "token_length_delta": len(good_token) - len(current_token),
        "same_prefix_except_last_char": (
            bool(good_token)
            and bool(current_token)
            and len(good_token) == len(current_token)
            and good_token[:-1] == current_token[:-1]
        ),
        "last_char_delta": (
            ord(good_token[-1]) - ord(current_token[-1])
            if good_token
            and current_token
            and len(good_token) == len(current_token)
            and good_token[:-1] == current_token[:-1]
            else None
        ),
        "mantissa_delta_units": _mantissa_delta(good_token, current_token),
    }


def observations_for_part(
    *,
    part_name: str,
    dxf_rows: list[dict[str, Any]],
    ddc_rows: list[dict[str, Any]],
    value_digits: int = 6,
) -> list[dict[str, Any]]:
    observations: list[dict[str, Any]] = []
    for row_index, (dxf_row, ddc_row) in enumerate(zip(dxf_rows, ddc_rows), start=1):
        entity_type = str(dxf_row["type"])
        current_tokens = encode_geometry_data(
            dxf_row,
            token_count=len(ddc_row["tokens"]),
            coordinate_digits=None,
            canonicalize_endpoints=False,
        ).split(".")
        slot_values = slot_values_for_dxf_row(dxf_row)
        previous_type = str(dxf_rows[row_index - 2]["type"]) if row_index > 1 else ""
        next_type = str(dxf_rows[row_index]["type"]) if row_index < len(dxf_rows) else ""
        for slot in range(max(len(ddc_row["tokens"]), len(current_tokens))):
            good_token = str(ddc_row["tokens"][slot]) if slot < len(ddc_row["tokens"]) else ""
            current_token = str(current_tokens[slot]) if slot < len(current_tokens) else ""
            value = float(slot_values.get(slot, 0.0))
            token_delta = _token_deltas(good_token, current_token)
            observations.append(
                {
                    "part": part_name,
                    "row_index": row_index,
                    "dxf_type": entity_type,
                    "ddc_record": str(ddc_row["record"]),
                    "pen": str(ddc_row.get("pen", "")),
                    "slot": slot,
                    "role": _slot_role(entity_type, slot),
                    "previous_type": previous_type,
                    "next_type": next_type,
                    "value": value,
                    "value_key": value_key(value, digits=value_digits),
                    "good_token": good_token,
                    "current_token": current_token,
                    "token_match": good_token == current_token,
                    "nonzero_slot": bool(good_token or current_token),
                    "good_minus_visible_value": token_delta["good_decoded"] - value,
                    "current_minus_visible_value": token_delta["current_decoded"] - value,
                    **token_delta,
                }
            )
    return observations


def _choose_most_common_token(tokens: Iterable[str]) -> str:
    counts = Counter(tokens)
    if not counts:
        return ""
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0][0]


def _strategy_key(row: dict[str, Any], strategy: str) -> tuple[Any, ...]:
    if strategy == "value":
        return (row["value_key"],)
    if strategy == "record_slot_value":
        return (row["ddc_record"], row["slot"], row["value_key"])
    if strategy == "type_role_value":
        return (row["dxf_type"], row["role"], row["value_key"])
    if strategy == "type_role_neighbor_value":
        return (
            row["dxf_type"],
            row["role"],
            row["previous_type"],
            row["next_type"],
            row["value_key"],
        )
    raise ValueError(f"Unsupported strategy: {strategy}")


def evaluate_lookup_strategy(
    observations: list[dict[str, Any]],
    *,
    strategy: str,
    nonzero_only: bool = True,
) -> dict[str, Any]:
    rows = [row for row in observations if (row["nonzero_slot"] or not nonzero_only)]
    tokens_by_part_key: dict[str, dict[tuple[Any, ...], list[str]]] = defaultdict(lambda: defaultdict(list))
    tokens_by_key: dict[tuple[Any, ...], list[str]] = defaultdict(list)
    for row in rows:
        key = _strategy_key(row, strategy)
        tokens_by_part_key[str(row["part"])][key].append(str(row["good_token"]))
        tokens_by_key[key].append(str(row["good_token"]))

    predicted = 0
    exact = 0
    ambiguous_predictions = 0
    no_prediction_examples: list[dict[str, Any]] = []
    mismatch_examples: list[dict[str, Any]] = []
    for row in rows:
        key = _strategy_key(row, strategy)
        training_tokens: list[str] = []
        for part, part_tokens_by_key in tokens_by_part_key.items():
            if part == row["part"]:
                continue
            training_tokens.extend(part_tokens_by_key.get(key, []))
        if not training_tokens:
            if len(no_prediction_examples) < 20:
                no_prediction_examples.append(
                    {
                        "part": row["part"],
                        "row_index": row["row_index"],
                        "slot": row["slot"],
                        "role": row["role"],
                        "value_key": row["value_key"],
                    }
                )
            continue
        predicted += 1
        if len(set(training_tokens)) > 1:
            ambiguous_predictions += 1
        token = _choose_most_common_token(training_tokens)
        if token == row["good_token"]:
            exact += 1
        elif len(mismatch_examples) < 20:
            mismatch_examples.append(
                {
                    "part": row["part"],
                    "row_index": row["row_index"],
                    "slot": row["slot"],
                    "role": row["role"],
                    "value_key": row["value_key"],
                    "expected": row["good_token"],
                    "predicted": token,
                    "candidate_count": len(training_tokens),
                    "unique_candidate_count": len(set(training_tokens)),
                }
            )

    ambiguous_keys = sum(1 for tokens in tokens_by_key.values() if len(set(tokens)) > 1)
    return {
        "strategy": strategy,
        "evaluated_slot_count": len(rows),
        "covered_slot_count": predicted,
        "coverage": predicted / len(rows) if rows else 0.0,
        "exact_match_count": exact,
        "exact_match_rate_on_covered": exact / predicted if predicted else 0.0,
        "exact_match_rate_overall": exact / len(rows) if rows else 0.0,
        "ambiguous_prediction_count": ambiguous_predictions,
        "key_count": len(tokens_by_key),
        "ambiguous_key_count": ambiguous_keys,
        "ambiguous_key_rate": ambiguous_keys / len(tokens_by_key) if tokens_by_key else 0.0,
        "no_prediction_examples": no_prediction_examples,
        "mismatch_examples": mismatch_examples,
    }


def summarize_observations(observations: list[dict[str, Any]]) -> dict[str, Any]:
    nonzero = [row for row in observations if row["nonzero_slot"]]
    current_matches = sum(1 for row in nonzero if row["token_match"])
    by_role: dict[str, dict[str, Any]] = {}
    for key, rows in _group_rows(nonzero, lambda row: f"{row['dxf_type']}:{row['role']}").items():
        by_role[key] = {
            "slot_count": len(rows),
            "current_match_count": sum(1 for row in rows if row["token_match"]),
            "current_match_rate": sum(1 for row in rows if row["token_match"]) / len(rows) if rows else 0.0,
            "last_char_delta_counts": dict(
                sorted(
                    Counter(str(row["last_char_delta"]) for row in rows if row["last_char_delta"] is not None).items(),
                    key=lambda item: int(item[0]),
                )
            ),
            "token_length_delta_counts": dict(sorted(Counter(str(row["token_length_delta"]) for row in rows).items())),
        }
    return {
        "observation_count": len(observations),
        "nonzero_observation_count": len(nonzero),
        "current_encoder_match_count": current_matches,
        "current_encoder_match_rate": current_matches / len(nonzero) if nonzero else 0.0,
        "same_prefix_except_last_char_count": sum(1 for row in nonzero if row["same_prefix_except_last_char"]),
        "by_role": dict(sorted(by_role.items())),
        "lookup_evaluations": [
            evaluate_lookup_strategy(nonzero, strategy=strategy)
            for strategy in (
                "value",
                "record_slot_value",
                "type_role_value",
                "type_role_neighbor_value",
            )
        ],
    }


def _group_rows(rows: Iterable[dict[str, Any]], key_func: Any) -> dict[Any, list[dict[str, Any]]]:
    grouped: dict[Any, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[key_func(row)].append(row)
    return grouped


def build_exported_token_corpus(
    *,
    dxf_folder: Path,
    sym_folder: Path,
    part_names: list[str] | None = None,
    value_digits: int = 6,
) -> dict[str, Any]:
    dxf_by_part = {path.stem.casefold(): path for path in dxf_folder.glob("*.dxf")}
    sym_by_part = {path.stem.casefold(): path for path in sym_folder.glob("*.sym")}
    requested = [part.casefold() for part in part_names] if part_names else sorted(set(dxf_by_part) & set(sym_by_part))
    parts: list[dict[str, Any]] = []
    observations: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []

    for key in requested:
        dxf_path = dxf_by_part.get(key)
        sym_path = sym_by_part.get(key)
        if dxf_path is None or sym_path is None:
            skipped.append(
                {
                    "part": key,
                    "reason": "missing_dxf" if dxf_path is None else "missing_sym",
                }
            )
            continue
        dxf_rows, bounds = read_dxf_entities(dxf_path)
        ddc_rows = read_ddc_records(sym_path)
        part_observations = observations_for_part(
            part_name=dxf_path.stem,
            dxf_rows=dxf_rows,
            ddc_rows=ddc_rows,
            value_digits=value_digits,
        )
        observations.extend(part_observations)
        nonzero = [row for row in part_observations if row["nonzero_slot"]]
        parts.append(
            {
                "part": dxf_path.stem,
                "dxf_path": str(dxf_path),
                "sym_path": str(sym_path),
                "bounds": bounds.as_dict(),
                "dxf_count": len(dxf_rows),
                "ddc_count": len(ddc_rows),
                "count_match": len(dxf_rows) == len(ddc_rows),
                "type_sequence_match": [
                    "G" if str(row["type"]) == "LINE" else "H" for row in dxf_rows
                ]
                == [str(row["record"]) for row in ddc_rows],
                "nonzero_slot_count": len(nonzero),
                "current_encoder_match_count": sum(1 for row in nonzero if row["token_match"]),
                "current_encoder_match_rate": (
                    sum(1 for row in nonzero if row["token_match"]) / len(nonzero) if nonzero else 0.0
                ),
            }
        )

    return {
        "schema_version": 1,
        "dxf_folder": str(dxf_folder),
        "sym_folder": str(sym_folder),
        "value_digits": value_digits,
        "part_count": len(parts),
        "skipped": skipped,
        "parts": sorted(parts, key=lambda row: str(row["part"]).casefold()),
        "summary": summarize_observations(observations),
        "observations": observations,
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    assert_w_drive_write_allowed(path, operation="write exported DXF token corpus JSON")
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.tmp")
    temp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True) + "\n", encoding="utf-8")
    temp_path.replace(path)


def write_observations_csv(path: Path, observations: list[dict[str, Any]]) -> None:
    assert_w_drive_write_allowed(path, operation="write exported DXF token observations CSV")
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "part",
        "row_index",
        "dxf_type",
        "ddc_record",
        "slot",
        "role",
        "previous_type",
        "next_type",
        "value_key",
        "good_token",
        "current_token",
        "token_match",
        "good_minus_visible_value",
        "current_minus_visible_value",
        "good_minus_current_decoded",
        "token_length_delta",
        "last_char_delta",
        "mantissa_delta_units",
    ]
    temp_path = path.with_name(f"{path.name}.tmp")
    with temp_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in observations:
            writer.writerow({field: row.get(field, "") for field in fields})
    temp_path.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Analyze RADAN DDC token choices using RADAN-exported DXFs paired with known-good SYMs.",
    )
    parser.add_argument("--dxf-folder", type=Path, required=True, help="Folder containing RADAN-exported DXFs.")
    parser.add_argument("--sym-folder", type=Path, required=True, help="Folder containing known-good RADAN SYMs.")
    parser.add_argument("--out-json", type=Path, help="Optional JSON output path.")
    parser.add_argument("--out-csv", type=Path, help="Optional observation CSV output path.")
    parser.add_argument("--value-digits", type=int, default=6, help="Visible DXF coordinate rounding key digits.")
    parser.add_argument("--part", action="append", help="Limit analysis to one or more part names/stems.")
    args = parser.parse_args()

    payload = build_exported_token_corpus(
        dxf_folder=args.dxf_folder,
        sym_folder=args.sym_folder,
        part_names=args.part,
        value_digits=args.value_digits,
    )
    if args.out_json:
        write_json(args.out_json, payload)
    if args.out_csv:
        write_observations_csv(args.out_csv, payload["observations"])
    printable = {
        "part_count": payload["part_count"],
        "skipped_count": len(payload["skipped"]),
        "summary": {
            key: value
            for key, value in payload["summary"].items()
            if key not in {"by_role", "lookup_evaluations"}
        },
        "lookup_evaluations": payload["summary"]["lookup_evaluations"],
    }
    print(json.dumps(printable, indent=2, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
