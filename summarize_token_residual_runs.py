from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_run(label: str, path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    summary = payload.get("summary", {})
    return {
        "label": label,
        "path": str(path),
        "part_count": payload.get("part_count", 0),
        "slot_count": summary.get("slot_count", 0),
        "exact_token_count": summary.get("exact_token_count", 0),
        "exact_token_rate": summary.get("exact_token_rate", 0.0),
        "mismatch_count": summary.get("mismatch_count", 0),
        "close_mismatch_count": summary.get("close_mismatch_count", 0),
        "far_mismatch_count": summary.get("far_mismatch_count", 0),
        "same_prefix_except_last_char_count": summary.get("same_prefix_except_last_char_count", 0),
        "token_length_delta_counts": summary.get("token_length_delta_counts", {}),
        "top_roles_by_mismatch": summary.get("top_roles_by_mismatch", [])[:10],
        "top_mantissa_delta_units": summary.get("top_mantissa_delta_units", [])[:10],
        "top_last_char_delta": summary.get("top_last_char_delta", [])[:10],
    }


def summarize_runs(runs: list[tuple[str, Path]]) -> dict[str, Any]:
    rows = [load_run(label, path) for label, path in runs]
    return {
        "schema_version": 1,
        "runs": rows,
    }


def write_markdown(payload: dict[str, Any], path: Path) -> None:
    rows = payload["runs"]
    lines = [
        "# Token Residual Accepted-Subset Summary",
        "",
        "| Run | Parts | Slots | Exact tokens | Exact rate | Mismatches | Close mismatches | Far mismatches | Last-char-ish |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            "| `{label}` | `{part_count}` | `{slot_count}` | `{exact_token_count}` | `{exact_token_rate:.6f}` | "
            "`{mismatch_count}` | `{close_mismatch_count}` | `{far_mismatch_count}` | "
            "`{same_prefix_except_last_char_count}` |".format(**row)
        )
    lines.extend(["", "## Top Roles By Mismatch", ""])
    for row in rows:
        lines.append(f"### {row['label']}")
        if not row["top_roles_by_mismatch"]:
            lines.append("")
            lines.append("- none")
            lines.append("")
            continue
        for item in row["top_roles_by_mismatch"]:
            lines.append(f"- `{item['key']}`: `{item['count']}`")
        lines.append("")
    lines.extend(["## Top Mantissa Deltas", ""])
    for row in rows:
        deltas = ", ".join(f"`{item['key']}`={item['count']}" for item in row["top_mantissa_delta_units"])
        lines.append(f"- `{row['label']}`: {deltas}")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _parse_run(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("Run must be LABEL=PATH.")
    label, path = value.split("=", 1)
    if not label.strip():
        raise argparse.ArgumentTypeError("Run label cannot be empty.")
    return label.strip(), Path(path.strip())


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize multiple token residual JSON runs.")
    parser.add_argument("--run", action="append", type=_parse_run, required=True, help="LABEL=path/to/residual.json")
    parser.add_argument("--out-json", type=Path)
    parser.add_argument("--out-md", type=Path)
    args = parser.parse_args()

    payload = summarize_runs(args.run)
    if args.out_json:
        args.out_json.parent.mkdir(parents=True, exist_ok=True)
        args.out_json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.out_md:
        args.out_md.parent.mkdir(parents=True, exist_ok=True)
        write_markdown(payload, args.out_md)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
