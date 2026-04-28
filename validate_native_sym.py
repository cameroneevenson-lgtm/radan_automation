from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from analyze_ddc_tokens import analyze_corpus
from ddc_corpus import build_part_corpus
from path_safety import assert_w_drive_write_allowed


def validate_native_sym(*, dxf_path: Path, sym_path: Path) -> dict[str, Any]:
    part = build_part_corpus(dxf_path, sym_path)
    corpus = {
        "csv_path": None,
        "sym_folder": str(sym_path.parent),
        "part_count": 1,
        "total_dxf_entities": part["dxf_count"],
        "total_ddc_records": part["ddc_count"],
        "parts": [part],
    }
    analysis = analyze_corpus(corpus, top=5)
    decoded_checks = analysis["decoded_geometry_checks"]
    tiers = [
        {
            "name": "record_count",
            "passed": bool(part["count_match"]),
            "detail": {
                "dxf_count": part["dxf_count"],
                "ddc_count": part["ddc_count"],
            },
        },
        {
            "name": "record_type_sequence",
            "passed": int(part["type_mismatch_count"]) == 0,
            "detail": {"type_mismatch_count": part["type_mismatch_count"]},
        },
        {
            "name": "known_layer_pen_mapping",
            "passed": int(part["known_pen_mismatch_count"]) == 0,
            "detail": {"known_pen_mismatch_count": part["known_pen_mismatch_count"]},
        },
        {
            "name": "decoded_geometry",
            "passed": all(int(check["failure_count"]) == 0 for check in decoded_checks),
            "detail": {
                "checks": [
                    {
                        "name": check["name"],
                        "record_count": check["record_count"],
                        "failure_count": check["failure_count"],
                        "max_abs_error": check["max_abs_error"],
                    }
                    for check in decoded_checks
                    if check["record_count"]
                ]
            },
        },
    ]
    return {
        "dxf_path": str(dxf_path),
        "sym_path": str(sym_path),
        "part": part["part"],
        "bounds": part["bounds"],
        "passed": all(bool(tier["passed"]) for tier in tiers),
        "tiers": tiers,
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    assert_w_drive_write_allowed(path, operation="write native SYM validation report")
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.tmp")
    temp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True) + "\n", encoding="utf-8")
    temp_path.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a native/generated RADAN .sym against its source DXF.")
    parser.add_argument("--dxf", type=Path, required=True, help="Source DXF path.")
    parser.add_argument("--sym", type=Path, required=True, help="Generated or template .sym path.")
    parser.add_argument("--out", type=Path, help="Optional JSON output path.")
    args = parser.parse_args()

    payload = validate_native_sym(dxf_path=args.dxf, sym_path=args.sym)
    if args.out:
        write_json(args.out, payload)
    print(json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True))
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
