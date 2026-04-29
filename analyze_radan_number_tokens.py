from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from fractions import Fraction
from pathlib import Path
from typing import Any

from ddc_number_codec import (
    ddc_number_mantissa_digits,
    ddc_number_mantissa_integer,
    decode_ddc_number_fraction,
)
from path_safety import assert_w_drive_write_allowed


def _is_power_of_two(value: int) -> bool:
    return value > 0 and (value & (value - 1)) == 0


def is_dyadic_decimal(value: float | str) -> bool:
    fraction = Fraction(str(value))
    return _is_power_of_two(fraction.denominator)


def token_delta_row(row: dict[str, Any]) -> dict[str, Any]:
    value = row["width"]
    radan_token = str(row["radan_width_token"])
    current_token = str(row["current_width_token"])
    radan_fraction = decode_ddc_number_fraction(radan_token)
    current_fraction = decode_ddc_number_fraction(current_token)
    target_fraction = Fraction(str(value))
    pad_to = max(
        len(ddc_number_mantissa_digits(radan_token)),
        len(ddc_number_mantissa_digits(current_token)),
    )
    radan_digits = ddc_number_mantissa_digits(radan_token, pad_to=pad_to)
    current_digits = ddc_number_mantissa_digits(current_token, pad_to=pad_to)
    digit_deltas = [left - right for left, right in zip(radan_digits, current_digits)]
    mantissa_delta_units = ddc_number_mantissa_integer(radan_token, pad_to=pad_to) - ddc_number_mantissa_integer(
        current_token,
        pad_to=pad_to,
    )

    return {
        "stem": row.get("stem", ""),
        "value": value,
        "value_fraction": f"{target_fraction.numerator}/{target_fraction.denominator}",
        "dyadic_decimal": is_dyadic_decimal(value),
        "radan_token": radan_token,
        "current_token": current_token,
        "match": radan_token == current_token,
        "radan_decoded": float(radan_fraction),
        "current_decoded": float(current_fraction),
        "radan_minus_target": float(radan_fraction - target_fraction),
        "current_minus_target": float(current_fraction - target_fraction),
        "radan_minus_current": float(radan_fraction - current_fraction),
        "mantissa_pad_width": pad_to,
        "mantissa_delta_units": mantissa_delta_units,
        "radan_mantissa_digits": radan_digits,
        "current_mantissa_digits": current_digits,
        "mantissa_digit_deltas": digit_deltas,
    }


def analyze_decimal_sweep(rows: list[dict[str, Any]]) -> dict[str, Any]:
    analyzed = [token_delta_row(row) for row in rows]
    match_counts = Counter("match" if row["match"] else "mismatch" for row in analyzed)
    dyadic_counts = Counter(
        ("dyadic" if row["dyadic_decimal"] else "non_dyadic", "match" if row["match"] else "mismatch")
        for row in analyzed
    )
    delta_counts = Counter(str(row["mantissa_delta_units"]) for row in analyzed)
    examples_by_delta: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in analyzed:
        key = str(row["mantissa_delta_units"])
        if len(examples_by_delta[key]) < 5:
            examples_by_delta[key].append(
                {
                    "value": row["value"],
                    "radan_token": row["radan_token"],
                    "current_token": row["current_token"],
                    "radan_minus_target": row["radan_minus_target"],
                }
            )

    return {
        "schema_version": 1,
        "row_count": len(analyzed),
        "match_count": match_counts["match"],
        "mismatch_count": match_counts["mismatch"],
        "dyadic_match_count": dyadic_counts[("dyadic", "match")],
        "dyadic_mismatch_count": dyadic_counts[("dyadic", "mismatch")],
        "non_dyadic_match_count": dyadic_counts[("non_dyadic", "match")],
        "non_dyadic_mismatch_count": dyadic_counts[("non_dyadic", "mismatch")],
        "mantissa_delta_unit_counts": dict(sorted(delta_counts.items(), key=lambda item: int(item[0]))),
        "mantissa_delta_examples": dict(sorted(examples_by_delta.items(), key=lambda item: int(item[0]))),
        "rows": analyzed,
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    assert_w_drive_write_allowed(path, operation="write RADAN number-token analysis CSV")
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "stem",
        "value",
        "dyadic_decimal",
        "match",
        "radan_token",
        "current_token",
        "radan_minus_target",
        "radan_minus_current",
        "mantissa_delta_units",
        "mantissa_digit_deltas",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            out = {key: row.get(key, "") for key in fieldnames}
            out["mantissa_digit_deltas"] = " ".join(str(value) for value in row["mantissa_digit_deltas"])
            writer.writerow(out)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Analyze RADAN compact-number token choices against the current DDC encoder.",
    )
    parser.add_argument(
        "--decimal-sweep",
        type=Path,
        required=True,
        help="Path to decimal_sweep_token_summary.json from a RADAN micro-oracle run.",
    )
    parser.add_argument("--out-json", type=Path, help="Optional JSON output path.")
    parser.add_argument("--out-csv", type=Path, help="Optional CSV output path.")
    args = parser.parse_args()

    rows = json.loads(args.decimal_sweep.read_text(encoding="utf-8"))
    payload = analyze_decimal_sweep(rows)
    if args.out_json:
        assert_w_drive_write_allowed(args.out_json, operation="write RADAN number-token analysis JSON")
        args.out_json.parent.mkdir(parents=True, exist_ok=True)
        args.out_json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.out_csv:
        write_csv(args.out_csv, payload["rows"])
    print(json.dumps({key: value for key, value in payload.items() if key != "rows"}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
