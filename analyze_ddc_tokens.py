from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from ddc_number_codec import decode_ddc_number


LINE_SLOT_FIELDS = {
    0: "start_x",
    1: "start_y",
    2: "end_x",
    3: "end_y",
}
LINE_DELTA_SLOT_FIELDS = {
    0: "start_x",
    1: "start_y",
    2: "delta_x",
    3: "delta_y",
}
CIRCLE_SLOT_FIELDS = {
    0: "start_x",
    1: "start_y",
    4: "center_delta_x",
}


def _value_key(value: float | int | str | None, *, digits: int = 6) -> str:
    if value is None:
        return ""
    if isinstance(value, (float, int)):
        rounded = round(float(value), digits)
        if rounded == 0:
            rounded = 0.0
        return f"{rounded:.{digits}f}".rstrip("0").rstrip(".")
    return str(value)


def _line_field_value(dxf: dict[str, Any], field: str) -> str:
    if field == "start_x":
        return _value_key(dxf.get("normalized_start", ["", ""])[0])
    if field == "start_y":
        return _value_key(dxf.get("normalized_start", ["", ""])[1])
    if field == "end_x":
        return _value_key(dxf.get("normalized_end", ["", ""])[0])
    if field == "end_y":
        return _value_key(dxf.get("normalized_end", ["", ""])[1])
    if field == "delta_x":
        start_x = float(dxf.get("normalized_start", [0.0, 0.0])[0])
        end_x = float(dxf.get("normalized_end", [0.0, 0.0])[0])
        return _value_key(end_x - start_x)
    if field == "delta_y":
        start_y = float(dxf.get("normalized_start", [0.0, 0.0])[1])
        end_y = float(dxf.get("normalized_end", [0.0, 0.0])[1])
        return _value_key(end_y - start_y)
    return ""


def _circle_field_value(dxf: dict[str, Any], field: str) -> str:
    if field == "start_x":
        return _value_key(float(dxf.get("normalized_center", ["", ""])[0]) + float(dxf.get("radius", 0.0)))
    if field == "start_y":
        return _value_key(dxf.get("normalized_center", ["", ""])[1])
    if field == "center_delta_x":
        return _value_key(-float(dxf.get("radius", 0.0)))
    return ""


def _tokens_for_pair(pair: dict[str, Any]) -> list[str]:
    tokens = pair.get("ddc", {}).get("tokens", [])
    return [str(token) for token in tokens]


def _non_empty_positions(tokens: list[str]) -> tuple[int, ...]:
    return tuple(index for index, token in enumerate(tokens) if token)


def _counter_rows(counter: Counter[Any], limit: int | None = None) -> list[dict[str, Any]]:
    rows = [{"key": key, "count": count} for key, count in counter.most_common(limit)]
    return rows


def _slot_profiles(pairs: list[dict[str, Any]], *, top: int) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, int], Counter[str]] = defaultdict(Counter)
    records_by_group: Counter[tuple[str, str]] = Counter()
    for pair in pairs:
        dxf_type = str(pair["dxf"]["type"])
        ddc_record = str(pair["ddc"]["record"])
        records_by_group[(ddc_record, dxf_type)] += 1
        for slot, token in enumerate(_tokens_for_pair(pair)):
            grouped[(ddc_record, dxf_type, slot)][token] += 1

    rows: list[dict[str, Any]] = []
    for key in sorted(grouped, key=lambda item: (item[0], item[1], item[2])):
        ddc_record, dxf_type, slot = key
        counter = grouped[key]
        rows.append(
            {
                "ddc_record": ddc_record,
                "dxf_type": dxf_type,
                "slot": slot,
                "record_count": records_by_group[(ddc_record, dxf_type)],
                "token_count": sum(counter.values()),
                "non_empty_count": sum(count for token, count in counter.items() if token),
                "unique_tokens": len(counter),
                "unique_non_empty_tokens": len([token for token in counter if token]),
                "top_tokens": [
                    {"token": token, "count": count}
                    for token, count in counter.most_common(top)
                ],
            }
        )
    return rows


def _record_shapes(pairs: list[dict[str, Any]], *, top: int) -> list[dict[str, Any]]:
    counters: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    for pair in pairs:
        key = (str(pair["ddc"]["record"]), str(pair["dxf"]["type"]))
        tokens = _tokens_for_pair(pair)
        shape = ",".join(str(index) for index in _non_empty_positions(tokens))
        counters[key][shape] += 1

    rows: list[dict[str, Any]] = []
    for key in sorted(counters, key=lambda item: (item[0], item[1])):
        ddc_record, dxf_type = key
        rows.append(
            {
                "ddc_record": ddc_record,
                "dxf_type": dxf_type,
                "shapes": [
                    {"non_empty_slots": shape, "count": count}
                    for shape, count in counters[key].most_common(top)
                ],
            }
        )
    return rows


def _slot_field_analysis(
    pairs: list[dict[str, Any]],
    *,
    ddc_record: str,
    dxf_type: str,
    slot_fields: dict[int, str],
    value_getter: Any,
    top: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    filtered = [
        pair
        for pair in pairs
        if str(pair["ddc"]["record"]) == ddc_record and str(pair["dxf"]["type"]) == dxf_type
    ]
    for slot, field in sorted(slot_fields.items()):
        token_to_values: dict[str, Counter[str]] = defaultdict(Counter)
        value_to_tokens: dict[str, Counter[str]] = defaultdict(Counter)
        empty_token_nonzero = 0
        missing_slot_count = 0
        for pair in filtered:
            tokens = _tokens_for_pair(pair)
            if slot >= len(tokens):
                missing_slot_count += 1
                token = ""
            else:
                token = tokens[slot]
            value = value_getter(pair["dxf"], field)
            token_to_values[token][value] += 1
            value_to_tokens[value][token] += 1
            if not token and value not in {"", "0"}:
                empty_token_nonzero += 1

        ambiguous_tokens = {
            token: values
            for token, values in token_to_values.items()
            if len(values) > 1 and token
        }
        ambiguous_values = {
            value: tokens
            for value, tokens in value_to_tokens.items()
            if len([token for token in tokens if token]) > 1
        }
        rows.append(
            {
                "ddc_record": ddc_record,
                "dxf_type": dxf_type,
                "slot": slot,
                "assumed_field": field,
                "record_count": len(filtered),
                "missing_slot_count": missing_slot_count,
                "distinct_tokens": len(token_to_values),
                "distinct_non_empty_tokens": len([token for token in token_to_values if token]),
                "distinct_values": len(value_to_tokens),
                "ambiguous_non_empty_token_count": len(ambiguous_tokens),
                "ambiguous_value_count": len(ambiguous_values),
                "empty_token_nonzero_count": empty_token_nonzero,
                "top_token_to_values": [
                    {
                        "token": token,
                        "count": sum(values.values()),
                        "values": [
                            {"value": value, "count": count}
                            for value, count in values.most_common(top)
                        ],
                    }
                    for token, values in sorted(
                        token_to_values.items(),
                        key=lambda item: (-sum(item[1].values()), item[0]),
                    )[:top]
                ],
                "ambiguous_value_examples": [
                    {
                        "value": value,
                        "tokens": [
                            {"token": token, "count": count}
                            for token, count in tokens.most_common(top)
                            if token
                        ],
                    }
                    for value, tokens in sorted(
                        ambiguous_values.items(),
                        key=lambda item: (-sum(item[1].values()), item[0]),
                    )[:top]
                ],
            }
        )
    return rows


def _flatten_pairs(corpus: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for part in corpus.get("parts", []):
        for pair in part.get("pairs", []):
            item = dict(pair)
            item["part"] = part.get("part")
            rows.append(item)
    return rows


def _decoded_geometry_checks(pairs: list[dict[str, Any]], *, tolerance: float = 1e-5) -> list[dict[str, Any]]:
    checks = [
        {
            "name": "G/LINE decoded slots",
            "ddc_record": "G",
            "dxf_type": "LINE",
            "slots": {
                0: ("start_x", lambda dxf: float(dxf["normalized_start"][0])),
                1: ("start_y", lambda dxf: float(dxf["normalized_start"][1])),
                2: ("delta_x", lambda dxf: float(dxf["normalized_end"][0]) - float(dxf["normalized_start"][0])),
                3: ("delta_y", lambda dxf: float(dxf["normalized_end"][1]) - float(dxf["normalized_start"][1])),
            },
        },
        {
            "name": "H/CIRCLE decoded slots",
            "ddc_record": "H",
            "dxf_type": "CIRCLE",
            "slots": {
                0: ("start_x", lambda dxf: float(dxf["normalized_center"][0]) + float(dxf["radius"])),
                1: ("start_y", lambda dxf: float(dxf["normalized_center"][1])),
                2: ("end_delta_x", lambda dxf: 0.0),
                3: ("end_delta_y", lambda dxf: 0.0),
                4: ("center_delta_x", lambda dxf: -float(dxf["radius"])),
                5: ("center_delta_y", lambda dxf: 0.0),
                6: ("const_1", lambda dxf: 1.0),
                9: ("const_1", lambda dxf: 1.0),
            },
        },
        {
            "name": "H/ARC decoded slots",
            "ddc_record": "H",
            "dxf_type": "ARC",
            "slots": {
                0: ("start_x", lambda dxf: float(dxf["normalized_start_point"][0])),
                1: ("start_y", lambda dxf: float(dxf["normalized_start_point"][1])),
                2: (
                    "end_delta_x",
                    lambda dxf: float(dxf["normalized_end_point"][0]) - float(dxf["normalized_start_point"][0]),
                ),
                3: (
                    "end_delta_y",
                    lambda dxf: float(dxf["normalized_end_point"][1]) - float(dxf["normalized_start_point"][1]),
                ),
                4: (
                    "center_delta_x",
                    lambda dxf: float(dxf["normalized_center"][0]) - float(dxf["normalized_start_point"][0]),
                ),
                5: (
                    "center_delta_y",
                    lambda dxf: float(dxf["normalized_center"][1]) - float(dxf["normalized_start_point"][1]),
                ),
                6: ("const_1", lambda dxf: 1.0),
                9: ("const_1", lambda dxf: 1.0),
            },
        },
    ]

    results: list[dict[str, Any]] = []
    for check in checks:
        filtered = [
            pair
            for pair in pairs
            if str(pair["ddc"]["record"]) == check["ddc_record"] and str(pair["dxf"]["type"]) == check["dxf_type"]
        ]
        slot_rows: list[dict[str, Any]] = []
        total_failures = 0
        max_abs_error = 0.0
        for slot, (field, getter) in check["slots"].items():
            failures: list[dict[str, Any]] = []
            slot_max_error = 0.0
            for pair in filtered:
                tokens = _tokens_for_pair(pair)
                token = tokens[slot] if slot < len(tokens) else ""
                decoded = decode_ddc_number(token)
                expected = float(getter(pair["dxf"]))
                error = abs(decoded - expected)
                slot_max_error = max(slot_max_error, error)
                max_abs_error = max(max_abs_error, error)
                if error > tolerance and len(failures) < 10:
                    failures.append(
                        {
                            "part": pair.get("part"),
                            "slot": slot,
                            "field": field,
                            "token": token,
                            "decoded": decoded,
                            "expected": expected,
                            "abs_error": error,
                        }
                    )
            failure_count = sum(
                1
                for pair in filtered
                if abs(
                    decode_ddc_number((_tokens_for_pair(pair)[slot] if slot < len(_tokens_for_pair(pair)) else ""))
                    - float(getter(pair["dxf"]))
                )
                > tolerance
            )
            total_failures += failure_count
            slot_rows.append(
                {
                    "slot": slot,
                    "field": field,
                    "record_count": len(filtered),
                    "max_abs_error": slot_max_error,
                    "failure_count": failure_count,
                    "failure_examples": failures,
                }
            )
        results.append(
            {
                "name": check["name"],
                "ddc_record": check["ddc_record"],
                "dxf_type": check["dxf_type"],
                "record_count": len(filtered),
                "tolerance": tolerance,
                "max_abs_error": max_abs_error,
                "failure_count": total_failures,
                "slots": slot_rows,
            }
        )
    return results


def analyze_corpus(corpus: dict[str, Any], *, top: int = 10) -> dict[str, Any]:
    pairs = _flatten_pairs(corpus)
    pair_counts = Counter((str(pair["ddc"]["record"]), str(pair["dxf"]["type"])) for pair in pairs)
    layer_pen_counts = Counter(
        (
            str(pair["dxf"]["type"]),
            str(pair["dxf"]["layer"]),
            str(pair["ddc"]["record"]),
            str(pair["ddc"]["pen"]),
        )
        for pair in pairs
    )
    return {
        "schema_version": 1,
        "source_corpus": {
            "csv_path": corpus.get("csv_path"),
            "sym_folder": corpus.get("sym_folder"),
            "part_count": corpus.get("part_count"),
            "total_dxf_entities": corpus.get("total_dxf_entities"),
            "total_ddc_records": corpus.get("total_ddc_records"),
        },
        "pair_counts": [
            {"ddc_record": key[0], "dxf_type": key[1], "count": count}
            for key, count in pair_counts.most_common()
        ],
        "layer_pen_counts": [
            {
                "dxf_type": key[0],
                "dxf_layer": key[1],
                "ddc_record": key[2],
                "ddc_pen": key[3],
                "count": count,
            }
            for key, count in layer_pen_counts.most_common()
        ],
        "record_shapes": _record_shapes(pairs, top=top),
        "slot_profiles": _slot_profiles(pairs, top=top),
        "line_slot_hypothesis": _slot_field_analysis(
            pairs,
            ddc_record="G",
            dxf_type="LINE",
            slot_fields=LINE_SLOT_FIELDS,
            value_getter=_line_field_value,
            top=top,
        ),
        "line_delta_slot_hypothesis": _slot_field_analysis(
            pairs,
            ddc_record="G",
            dxf_type="LINE",
            slot_fields=LINE_DELTA_SLOT_FIELDS,
            value_getter=_line_field_value,
            top=top,
        ),
        "circle_slot_hypothesis": _slot_field_analysis(
            pairs,
            ddc_record="H",
            dxf_type="CIRCLE",
            slot_fields=CIRCLE_SLOT_FIELDS,
            value_getter=_circle_field_value,
            top=top,
        ),
        "decoded_geometry_checks": _decoded_geometry_checks(pairs),
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.tmp")
    temp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True) + "\n", encoding="utf-8")
    temp_path.replace(path)


def _print_summary(payload: dict[str, Any]) -> None:
    summary = {
        "source_corpus": payload["source_corpus"],
        "pair_counts": payload["pair_counts"],
        "line_slot_hypothesis": [
            {
                "slot": row["slot"],
                "assumed_field": row["assumed_field"],
                "record_count": row["record_count"],
                "distinct_non_empty_tokens": row["distinct_non_empty_tokens"],
                "distinct_values": row["distinct_values"],
                "ambiguous_non_empty_token_count": row["ambiguous_non_empty_token_count"],
                "ambiguous_value_count": row["ambiguous_value_count"],
                "empty_token_nonzero_count": row["empty_token_nonzero_count"],
            }
            for row in payload["line_slot_hypothesis"]
        ],
        "line_delta_slot_hypothesis": [
            {
                "slot": row["slot"],
                "assumed_field": row["assumed_field"],
                "record_count": row["record_count"],
                "distinct_non_empty_tokens": row["distinct_non_empty_tokens"],
                "distinct_values": row["distinct_values"],
                "ambiguous_non_empty_token_count": row["ambiguous_non_empty_token_count"],
                "ambiguous_value_count": row["ambiguous_value_count"],
                "empty_token_nonzero_count": row["empty_token_nonzero_count"],
            }
            for row in payload["line_delta_slot_hypothesis"]
        ],
        "circle_slot_hypothesis": [
            {
                "slot": row["slot"],
                "assumed_field": row["assumed_field"],
                "record_count": row["record_count"],
                "distinct_non_empty_tokens": row["distinct_non_empty_tokens"],
                "distinct_values": row["distinct_values"],
                "ambiguous_non_empty_token_count": row["ambiguous_non_empty_token_count"],
                "ambiguous_value_count": row["ambiguous_value_count"],
                "empty_token_nonzero_count": row["empty_token_nonzero_count"],
            }
            for row in payload["circle_slot_hypothesis"]
        ],
        "decoded_geometry_checks": [
            {
                "name": row["name"],
                "record_count": row["record_count"],
                "max_abs_error": row["max_abs_error"],
                "failure_count": row["failure_count"],
            }
            for row in payload["decoded_geometry_checks"]
        ],
    }
    print(json.dumps(summary, indent=2, ensure_ascii=True, sort_keys=True))


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze DDC geometry tokens from a DXF/DDC corpus JSON.")
    parser.add_argument("--corpus", type=Path, required=True, help="Corpus JSON produced by ddc_corpus.py.")
    parser.add_argument("--out", type=Path, help="Optional JSON output path.")
    parser.add_argument("--top", type=int, default=10, help="Number of examples to include per bucket.")
    args = parser.parse_args()

    corpus = json.loads(args.corpus.read_text(encoding="utf-8"))
    payload = analyze_corpus(corpus, top=max(1, int(args.top)))
    if args.out:
        write_json(args.out, payload)
    _print_summary(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
