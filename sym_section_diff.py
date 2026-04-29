from __future__ import annotations

import argparse
import json
from pathlib import Path

from radan_sym_analysis import diff_sym_sections, write_json


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare a known-good RADAN .sym against a synthetic or suspect .sym by section."
    )
    parser.add_argument("--good", type=Path, required=True, help="Known-good RADAN-created .sym.")
    parser.add_argument("--compare", type=Path, required=True, help="Synthetic or suspect .sym to compare.")
    parser.add_argument("--out", type=Path, help="Optional JSON diff output path.")
    args = parser.parse_args()

    payload = diff_sym_sections(args.good, args.compare)
    if args.out:
        write_json(args.out, payload)

    ddc = payload["ddc_comparison"]
    summary = {
        "good": str(args.good),
        "compare": str(args.compare),
        "difference_localization": payload["difference_localization"],
        "section_equalities": payload["section_equalities"],
        "attr_diff_count": payload["attr_diff_count"],
        "important_attr_diff_count": len(payload["important_attr_diffs"]),
        "ddc_count_match": ddc["count_match"],
        "ddc_type_sequence_match": ddc["type_sequence_match"],
        "ddc_pen_sequence_match": ddc["pen_sequence_match"],
        "exact_geometry_data_matches": ddc["exact_geometry_data_matches"],
        "paired_record_count": ddc["paired_record_count"],
        "token_match_ratio": ddc["token_match_ratio"],
        "max_decoded_abs_diff": ddc["max_decoded_abs_diff"],
        "out": str(args.out) if args.out else "",
    }
    print(json.dumps(summary, indent=2, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
