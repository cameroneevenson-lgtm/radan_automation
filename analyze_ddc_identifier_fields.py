from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

from ddc_corpus import read_ddc_records
from path_safety import assert_w_drive_write_allowed


def decode_ddc_small_identifier(value: str) -> int | None:
    if value == "":
        return None
    total = 0
    multiplier = 1
    for char in value:
        digit = ord(char) - 48
        if digit < 0 or digit >= 64:
            return None
        total += digit * multiplier
        multiplier *= 64
    return total


def encode_ddc_small_identifier(value: int) -> str:
    value = int(value)
    if value < 0:
        raise ValueError("DDC small identifier cannot be negative.")
    chars: list[str] = []
    while True:
        chars.append(chr(48 + (value % 64)))
        value //= 64
        if value == 0:
            return "".join(chars)


def expected_geometry_identifier(row_index: int) -> str:
    return encode_ddc_small_identifier(int(row_index) + 2)


def _sym_paths(folder: Path) -> dict[str, Path]:
    return {path.stem: path for path in sorted(folder.glob("*.sym"), key=lambda item: item.name.casefold())}


def scan_identifier_rows(label: str, folder: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for part, path in _sym_paths(folder).items():
        records = read_ddc_records(path)
        identifiers = [str(record.get("identifier", "")) for record in records]
        duplicate_ids = {identifier for identifier, count in Counter(identifiers).items() if identifier and count > 1}
        for row_index, record in enumerate(records, start=1):
            identifier = str(record.get("identifier", ""))
            expected = expected_geometry_identifier(row_index)
            rows.append(
                {
                    "label": label,
                    "folder": str(folder),
                    "part": part,
                    "row_index": row_index,
                    "record": record.get("record", ""),
                    "identifier": identifier,
                    "decoded_identifier": decode_ddc_small_identifier(identifier),
                    "expected_identifier": expected,
                    "expected_decoded_identifier": row_index + 2,
                    "sequential_match": identifier == expected,
                    "duplicate_in_part": identifier in duplicate_ids,
                }
            )
    return rows


def _folder_summary(label: str, folder: Path, rows: list[dict[str, Any]]) -> dict[str, Any]:
    parts = sorted({str(row["part"]) for row in rows}, key=str.casefold)
    bad_rows = [row for row in rows if not row["sequential_match"]]
    duplicate_rows = [row for row in rows if row["duplicate_in_part"]]
    return {
        "label": label,
        "folder": str(folder),
        "part_count": len(parts),
        "row_count": len(rows),
        "sequential_match_count": len(rows) - len(bad_rows),
        "nonsequential_count": len(bad_rows),
        "duplicate_identifier_row_count": len(duplicate_rows),
        "nonsequential_examples": bad_rows[:20],
        "duplicate_examples": duplicate_rows[:20],
    }


def _reference_comparison(
    *,
    label: str,
    folder: Path,
    rows: list[dict[str, Any]],
    reference_label: str,
    reference_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    ref_by_key = {
        (str(row["part"]), int(row["row_index"])): row
        for row in reference_rows
    }
    rows_by_key = {(str(row["part"]), int(row["row_index"])): row for row in rows}
    mismatches = []
    for key in sorted(set(rows_by_key) & set(ref_by_key), key=lambda item: (item[0].casefold(), item[1])):
        row = rows_by_key[key]
        ref = ref_by_key[key]
        if row["identifier"] == ref["identifier"] and row["record"] == ref["record"]:
            continue
        mismatches.append(
            {
                "part": key[0],
                "row_index": key[1],
                "record": row["record"],
                "reference_record": ref["record"],
                "identifier": row["identifier"],
                "reference_identifier": ref["identifier"],
                "sequential_match": row["sequential_match"],
            }
        )

    missing_keys = sorted(set(ref_by_key) - set(rows_by_key), key=lambda item: (item[0].casefold(), item[1]))
    extra_keys = sorted(set(rows_by_key) - set(ref_by_key), key=lambda item: (item[0].casefold(), item[1]))
    return {
        "label": label,
        "folder": str(folder),
        "reference_label": reference_label,
        "compared_rows": len(set(rows_by_key) & set(ref_by_key)),
        "identifier_or_record_mismatch_count": len(mismatches),
        "missing_reference_row_count": len(missing_keys),
        "extra_row_count": len(extra_keys),
        "mismatch_examples": mismatches[:50],
        "missing_reference_examples": [{"part": key[0], "row_index": key[1]} for key in missing_keys[:20]],
        "extra_examples": [{"part": key[0], "row_index": key[1]} for key in extra_keys[:20]],
    }


def analyze_folders(
    folders: list[tuple[str, Path]],
    *,
    reference_label: str | None = None,
) -> dict[str, Any]:
    if not folders:
        raise ValueError("At least one folder is required.")
    labels = [label for label, _folder in folders]
    if len(labels) != len(set(labels)):
        raise ValueError("Folder labels must be unique.")
    if reference_label is None:
        reference_label = labels[0]
    if reference_label not in labels:
        raise ValueError(f"Reference label {reference_label!r} is not one of: {', '.join(labels)}")

    rows_by_label: dict[str, list[dict[str, Any]]] = {}
    summaries: list[dict[str, Any]] = []
    for label, folder in folders:
        rows = scan_identifier_rows(label, folder)
        rows_by_label[label] = rows
        summaries.append(_folder_summary(label, folder, rows))

    reference_rows = rows_by_label[reference_label]
    comparisons = [
        _reference_comparison(
            label=label,
            folder=folder,
            rows=rows_by_label[label],
            reference_label=reference_label,
            reference_rows=reference_rows,
        )
        for label, folder in folders
        if label != reference_label
    ]

    return {
        "schema_version": 1,
        "reference_label": reference_label,
        "folders": summaries,
        "comparisons": comparisons,
        "rows": [row for label in labels for row in rows_by_label[label]],
    }


def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    assert_w_drive_write_allowed(path, operation="write DDC identifier CSV")
    fieldnames = [
        "label",
        "folder",
        "part",
        "row_index",
        "record",
        "identifier",
        "decoded_identifier",
        "expected_identifier",
        "expected_decoded_identifier",
        "sequential_match",
        "duplicate_in_part",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(payload: dict[str, Any], path: Path) -> None:
    assert_w_drive_write_allowed(path, operation="write DDC identifier markdown")
    lines = [
        "# DDC Field-3 Identifier Analysis",
        "",
        f"- Reference: `{payload['reference_label']}`",
        "",
        "## Folder Summary",
        "",
        "| Folder | Parts | Rows | Sequential | Nonsequential | Duplicate ID rows |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in payload["folders"]:
        lines.append(
            "| `{label}` | `{part_count}` | `{row_count}` | `{sequential_match_count}` | "
            "`{nonsequential_count}` | `{duplicate_identifier_row_count}` |".format(**row)
        )

    lines.extend(["", "## Reference Comparisons", ""])
    if not payload["comparisons"]:
        lines.append("- no comparison folders")
    for row in payload["comparisons"]:
        lines.append(
            "- `{label}` vs `{reference_label}`: `{identifier_or_record_mismatch_count}` mismatched rows, "
            "`{missing_reference_row_count}` missing reference rows, `{extra_row_count}` extra rows".format(**row)
        )
        for example in row["mismatch_examples"][:10]:
            lines.append(
                "  - `{part}` row `{row_index}`: `{identifier}` vs ref `{reference_identifier}` "
                "(record `{record}` vs `{reference_record}`)".format(**example)
            )

    lines.extend(["", "## Nonsequential Examples", ""])
    for folder in payload["folders"]:
        examples = folder["nonsequential_examples"]
        if not examples:
            continue
        lines.append(f"### {folder['label']}")
        for example in examples[:10]:
            lines.append(
                "- `{part}` row `{row_index}`: `{identifier}` expected `{expected_identifier}`".format(**example)
            )
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _assert_sym_lab_output(path: Path) -> None:
    assert_w_drive_write_allowed(path, operation="write DDC identifier analyzer output")
    lab_root = (Path(__file__).resolve().parent / "_sym_lab").resolve()
    resolved = path.resolve()
    if resolved == lab_root or lab_root in resolved.parents:
        return
    raise RuntimeError(f"Refusing to write analyzer output outside _sym_lab: {path}")


def _parse_folder(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("Folder must be LABEL=PATH.")
    label, path = value.split("=", 1)
    if not label.strip():
        raise argparse.ArgumentTypeError("Folder label cannot be empty.")
    return label.strip(), Path(path.strip())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Analyze DDC geometry row field-3 identifiers across SYM folders.")
    parser.add_argument("--folder", action="append", type=_parse_folder, required=True, help="LABEL=folder")
    parser.add_argument("--reference-label")
    parser.add_argument("--out-json", required=True, type=Path)
    parser.add_argument("--out-csv", type=Path)
    parser.add_argument("--out-md", type=Path)
    args = parser.parse_args(argv)

    for path in [args.out_json, args.out_csv, args.out_md]:
        if path is not None:
            _assert_sym_lab_output(path)
            path.parent.mkdir(parents=True, exist_ok=True)

    payload = analyze_folders(args.folder, reference_label=args.reference_label)
    args.out_json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.out_csv:
        write_csv(payload["rows"], args.out_csv)
    if args.out_md:
        write_markdown(payload, args.out_md)
    print(json.dumps({key: value for key, value in payload.items() if key != "rows"}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
