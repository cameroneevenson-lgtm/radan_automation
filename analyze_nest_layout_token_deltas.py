from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import compare_nest_artifacts as compare
from ddc_number_codec import (
    ddc_number_mantissa_digits,
    ddc_number_mantissa_integer,
    decode_ddc_number_fraction,
)
from path_safety import assert_w_drive_write_allowed


LAYOUT_CLASSES = {
    "F layout entity token payload",
    "I layout annotation token payload",
    "I layout text token payload",
}


def _safe_fraction(token: str) -> Any:
    try:
        return decode_ddc_number_fraction(token)
    except Exception:
        return None


def _decoded_bucket(abs_diff: float | None) -> str:
    if abs_diff is None:
        return "decode_error"
    if abs_diff == 0:
        return "equal"
    if abs_diff <= 1e-15:
        return "close_1e-15"
    if abs_diff <= 1e-12:
        return "close_1e-12"
    return "far"


def _mantissa_delta(left_token: str, right_token: str) -> int | None:
    try:
        pad_to = max(
            len(ddc_number_mantissa_digits(left_token)),
            len(ddc_number_mantissa_digits(right_token)),
        )
        return ddc_number_mantissa_integer(left_token, pad_to=pad_to) - ddc_number_mantissa_integer(
            right_token,
            pad_to=pad_to,
        )
    except Exception:
        return None


def _top(counter: Counter[Any], *, limit: int = 20) -> list[dict[str, Any]]:
    return [{"key": str(key), "count": count} for key, count in counter.most_common(limit)]


def _split_payload_and_label(line: str) -> tuple[str, list[str], str]:
    before_label, _sep, label = line.partition("$")
    fields = before_label.split(",")
    payload = fields[-1] if fields else ""
    tokens = payload.split(".") if payload else []
    return payload, tokens, label


def _change_rows(left_path: Path, right_path: Path) -> list[dict[str, Any]]:
    left_lines = [compare.normalize_drg_text(line) for line in compare.ddc_lines(left_path)]
    right_lines = [compare.normalize_drg_text(line) for line in compare.ddc_lines(right_path)]
    rows = []
    for index in range(max(len(left_lines), len(right_lines))):
        left = left_lines[index] if index < len(left_lines) else None
        right = right_lines[index] if index < len(right_lines) else None
        if left == right:
            continue
        change_class = compare._classify_ddc_change(left, right)
        rows.append(
            {
                "index": index,
                "class": change_class,
                "left": left,
                "right": right,
            }
        )
    return rows


def _drg_paths_by_nest_id(gate_dir: Path) -> dict[int, Path]:
    result = compare.load_gate_result(gate_dir)
    paths = {}
    for path in compare._find_drg_files(gate_dir, result):
        nest_id = compare._nest_id_from_name(path.name)
        if nest_id is not None:
            paths[int(nest_id)] = path
    return paths


def _token_delta_rows(
    *,
    nest_id: int,
    line_index: int,
    change_class: str,
    left_line: str,
    right_line: str,
    left_name: str,
    right_name: str,
) -> list[dict[str, Any]]:
    _left_payload, left_tokens, left_label = _split_payload_and_label(left_line)
    _right_payload, right_tokens, right_label = _split_payload_and_label(right_line)
    label = right_label or left_label
    rows = []
    for slot in range(max(len(left_tokens), len(right_tokens))):
        left_token = left_tokens[slot] if slot < len(left_tokens) else ""
        right_token = right_tokens[slot] if slot < len(right_tokens) else ""
        if left_token == right_token:
            continue
        left_fraction = _safe_fraction(left_token)
        right_fraction = _safe_fraction(right_token)
        decoded_abs_diff = (
            None
            if left_fraction is None or right_fraction is None
            else abs(float(left_fraction - right_fraction))
        )
        same_prefix_except_last = bool(
            left_token
            and right_token
            and len(left_token) == len(right_token)
            and left_token[:-1] == right_token[:-1]
            and left_token[-1] != right_token[-1]
        )
        rows.append(
            {
                "nest_id": nest_id,
                "line_index": line_index,
                "class": change_class,
                "label": label,
                "slot": slot,
                "left_name": left_name,
                "right_name": right_name,
                "left_token": left_token,
                "right_token": right_token,
                "left_decoded": None if left_fraction is None else float(left_fraction),
                "right_decoded": None if right_fraction is None else float(right_fraction),
                "decoded_abs_diff": decoded_abs_diff,
                "decoded_bucket": _decoded_bucket(decoded_abs_diff),
                "token_length_delta": len(left_token) - len(right_token),
                "same_prefix_except_last_char": same_prefix_except_last,
                "last_char_delta": (
                    ord(left_token[-1]) - ord(right_token[-1])
                    if same_prefix_except_last
                    else None
                ),
                "mantissa_delta_units": _mantissa_delta(left_token, right_token),
            }
        )
    return rows


def summarize_token_delta_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_class: dict[str, dict[str, Any]] = {}
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["class"])].append(row)
    for change_class, class_rows in sorted(grouped.items()):
        by_class[change_class] = {
            "token_mismatch_count": len(class_rows),
            "decoded_bucket_counts": dict(sorted(Counter(str(row["decoded_bucket"]) for row in class_rows).items())),
            "same_prefix_except_last_char_count": sum(
                1 for row in class_rows if row["same_prefix_except_last_char"]
            ),
            "top_last_char_delta": _top(
                Counter(str(row["last_char_delta"]) for row in class_rows if row["last_char_delta"] is not None),
                limit=10,
            ),
            "top_mantissa_delta_units": _top(
                Counter(
                    str(row["mantissa_delta_units"])
                    for row in class_rows
                    if row["mantissa_delta_units"] is not None
                ),
                limit=10,
            ),
        }

    return {
        "token_mismatch_count": len(rows),
        "decoded_bucket_counts": dict(sorted(Counter(str(row["decoded_bucket"]) for row in rows).items())),
        "same_prefix_except_last_char_count": sum(1 for row in rows if row["same_prefix_except_last_char"]),
        "token_length_delta_counts": dict(sorted(Counter(str(row["token_length_delta"]) for row in rows).items())),
        "top_last_char_delta": _top(
            Counter(str(row["last_char_delta"]) for row in rows if row["last_char_delta"] is not None)
        ),
        "top_mantissa_delta_units": _top(
            Counter(str(row["mantissa_delta_units"]) for row in rows if row["mantissa_delta_units"] is not None)
        ),
        "top_labels": _top(Counter(str(row["label"]) for row in rows), limit=20),
        "by_class": by_class,
        "examples": rows[:25],
    }


def analyze_pair_dirs(
    left_dir: Path,
    right_dir: Path,
    *,
    left_name: str = "left",
    right_name: str = "right",
) -> dict[str, Any]:
    left_paths = _drg_paths_by_nest_id(left_dir)
    right_paths = _drg_paths_by_nest_id(right_dir)
    ids = sorted(set(left_paths) & set(right_paths))
    ddc_changed_by_class: Counter[str] = Counter()
    layout_changed_by_class: Counter[str] = Counter()
    token_rows: list[dict[str, Any]] = []
    for nest_id in ids:
        for row in _change_rows(left_paths[nest_id], right_paths[nest_id]):
            change_class = str(row["class"])
            ddc_changed_by_class[change_class] += 1
            if change_class not in LAYOUT_CLASSES:
                continue
            layout_changed_by_class[change_class] += 1
            if row["left"] is None or row["right"] is None:
                continue
            token_rows.extend(
                _token_delta_rows(
                    nest_id=nest_id,
                    line_index=int(row["index"]),
                    change_class=change_class,
                    left_line=str(row["left"]),
                    right_line=str(row["right"]),
                    left_name=left_name,
                    right_name=right_name,
                )
            )

    return {
        "schema_version": 1,
        "left_dir": str(left_dir),
        "right_dir": str(right_dir),
        "left_name": left_name,
        "right_name": right_name,
        "paired_drg_count": len(ids),
        "ddc_changed_by_class": dict(sorted(ddc_changed_by_class.items())),
        "layout_changed_by_class": dict(sorted(layout_changed_by_class.items())),
        "layout_changed_rows": sum(layout_changed_by_class.values()),
        "layout_token_summary": summarize_token_delta_rows(token_rows),
    }


def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    assert_w_drive_write_allowed(path, operation="write nest layout token delta csv")
    fieldnames = [
        "nest_id",
        "line_index",
        "class",
        "label",
        "slot",
        "left_name",
        "right_name",
        "left_token",
        "right_token",
        "left_decoded",
        "right_decoded",
        "decoded_abs_diff",
        "decoded_bucket",
        "token_length_delta",
        "same_prefix_except_last_char",
        "last_char_delta",
        "mantissa_delta_units",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(summary: dict[str, Any], path: Path) -> None:
    assert_w_drive_write_allowed(path, operation="write nest layout token delta markdown")
    token_summary = summary["layout_token_summary"]
    lines = [
        "# Nest Layout Token Delta Analysis",
        "",
        f"- Left: `{summary['left_name']}`",
        f"- Right: `{summary['right_name']}`",
        f"- Paired DRGs: `{summary['paired_drg_count']}`",
        f"- Layout changed rows: `{summary['layout_changed_rows']}`",
        f"- Layout token mismatches: `{token_summary['token_mismatch_count']}`",
        "",
        "## DDC Changed By Class",
        "",
    ]
    for key, count in summary["ddc_changed_by_class"].items():
        lines.append(f"- `{key}`: `{count}`")
    lines.extend(["", "## Layout Token Decoded Buckets", ""])
    for key, count in token_summary["decoded_bucket_counts"].items():
        lines.append(f"- `{key}`: `{count}`")
    lines.extend(["", "## Layout Rows By Class", ""])
    for key, count in summary["layout_changed_by_class"].items():
        lines.append(f"- `{key}`: `{count}`")
    lines.extend(["", "## Top Labels", ""])
    for row in token_summary["top_labels"]:
        lines.append(f"- `{row['key']}`: `{row['count']}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _assert_sym_lab_output(path: Path) -> None:
    assert_w_drive_write_allowed(path, operation="write nest layout token delta output")
    lab_root = (Path(__file__).resolve().parent / "_sym_lab").resolve()
    resolved = path.resolve()
    if resolved == lab_root or lab_root in resolved.parents:
        return
    raise RuntimeError(f"Refusing to write analyzer output outside _sym_lab: {path}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Analyze compact-token deltas in paired nest DRG layout rows.")
    parser.add_argument("--left-dir", required=True, type=Path)
    parser.add_argument("--right-dir", required=True, type=Path)
    parser.add_argument("--left-name", default="left")
    parser.add_argument("--right-name", default="right")
    parser.add_argument("--out-json", required=True, type=Path)
    parser.add_argument("--out-csv", type=Path)
    parser.add_argument("--out-md", type=Path)
    args = parser.parse_args(argv)

    for path in [args.out_json, args.out_csv, args.out_md]:
        if path is not None:
            _assert_sym_lab_output(path)
            path.parent.mkdir(parents=True, exist_ok=True)

    summary = analyze_pair_dirs(
        args.left_dir,
        args.right_dir,
        left_name=args.left_name,
        right_name=args.right_name,
    )
    args.out_json.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    token_rows = summary["layout_token_summary"]["examples"]
    all_rows: list[dict[str, Any]] = []
    for nest_id, left_path in _drg_paths_by_nest_id(args.left_dir).items():
        right_path = _drg_paths_by_nest_id(args.right_dir).get(nest_id)
        if right_path is None:
            continue
        for row in _change_rows(left_path, right_path):
            if row["class"] not in LAYOUT_CLASSES or row["left"] is None or row["right"] is None:
                continue
            all_rows.extend(
                _token_delta_rows(
                    nest_id=nest_id,
                    line_index=int(row["index"]),
                    change_class=str(row["class"]),
                    left_line=str(row["left"]),
                    right_line=str(row["right"]),
                    left_name=args.left_name,
                    right_name=args.right_name,
                )
            )
    summary["layout_token_summary"]["examples"] = token_rows
    if args.out_csv:
        write_csv(all_rows, args.out_csv)
    if args.out_md:
        write_markdown(summary, args.out_md)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
