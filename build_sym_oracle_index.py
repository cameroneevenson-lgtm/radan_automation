from __future__ import annotations

import argparse
import json
from pathlib import Path

from radan_sym_analysis import build_sym_index, write_index_csv, write_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Index RADAN .sym files and classify safe donor/oracle candidates.")
    parser.add_argument(
        "--root",
        type=Path,
        action="append",
        required=True,
        help="File or folder to scan for .sym files. May be passed more than once.",
    )
    parser.add_argument("--out-json", type=Path, required=True, help="JSON index output path.")
    parser.add_argument("--out-csv", type=Path, help="Optional CSV index output path.")
    args = parser.parse_args()

    payload = build_sym_index(args.root)
    write_json(args.out_json, payload)
    if args.out_csv:
        write_index_csv(args.out_csv, payload["symbols"])

    summary = {
        "symbol_count": payload["symbol_count"],
        "safe_oracle_count": payload["safe_oracle_count"],
        "classification_counts": payload["classification_counts"],
        "duplicate_part_count": payload["duplicate_part_count"],
        "out_json": str(args.out_json),
        "out_csv": str(args.out_csv) if args.out_csv else "",
    }
    print(json.dumps(summary, indent=2, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
