from __future__ import annotations

import csv
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Sequence

from ddc_corpus import read_ddc_records
from ddc_number_codec import decode_ddc_number
from path_safety import assert_w_drive_write_allowed


DDC_BLOCK_RE = re.compile(
    r'(<RadanFile\s+extension="ddc"\s*>\s*<!\[CDATA\[)(.*?)(\]\]>\s*</RadanFile>)',
    re.DOTALL,
)
HISTORY_BLOCK_RE = re.compile(r"(<History>\s*<!\[CDATA\[)(.*?)(\]\]>\s*</History>)", re.DOTALL)
GEOMETRY_RECORD_TYPES = {"G", "H"}
VOLATILE_ATTR_NUMS = {"101", "102", "103"}
IMPORTANT_ATTR_NUMS = {"101", "102", "103", "110", "119", "120", "121", "122", "146", "164"}


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _local_name(tag: str) -> str:
    return str(tag).rsplit("}", 1)[-1]


def _attr_value(attrs: dict[str, dict[str, str]], num: str) -> str:
    return attrs.get(str(num), {}).get("value", "")


def extract_ddc_text(text: str) -> str:
    match = DDC_BLOCK_RE.search(text)
    return match.group(2) if match else ""


def extract_history_text(text: str) -> str:
    match = HISTORY_BLOCK_RE.search(text)
    return match.group(2) if match else ""


def _replace_ddc_with_marker(text: str) -> str:
    return DDC_BLOCK_RE.sub(r"\1<DDC_BLOCK_REMOVED>\3", text)


def _replace_history_with_marker(text: str) -> str:
    return HISTORY_BLOCK_RE.sub(r"\1<HISTORY_BLOCK_REMOVED>\3", text)


def _normalize_volatile_attrs(text: str) -> str:
    normalized = text
    for num in sorted(VOLATILE_ATTR_NUMS):
        pattern = re.compile(
            rf'(<Attr\b(?=[^>]*\bnum="{re.escape(num)}")[^>]*\bvalue=)(["\'])(.*?)(\2)',
            re.DOTALL,
        )
        normalized = pattern.sub(r"\1\2<VOLATILE>\4", normalized)
    return normalized


def parse_sym_attrs(text: str) -> dict[str, dict[str, str]]:
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return {}

    attrs: dict[str, dict[str, str]] = {}

    def walk(node: ET.Element, group: dict[str, str] | None = None) -> None:
        local = _local_name(node.tag)
        current_group = group
        if local == "Group":
            current_group = {
                "group_class": str(node.attrib.get("class", "")),
                "group_name": str(node.attrib.get("name", "")),
            }
        elif local == "Attr":
            num = str(node.attrib.get("num", ""))
            if num:
                entry = {str(key): str(value) for key, value in node.attrib.items()}
                if current_group:
                    entry.update(current_group)
                attrs[num] = entry
        for child in list(node):
            walk(child, current_group)

    walk(root)
    return attrs


def ddc_nonempty_lines(ddc_text: str) -> list[str]:
    return [line for line in ddc_text.splitlines() if line.strip()]


def ddc_geometry_lines(ddc_text: str) -> list[str]:
    rows = []
    for line in ddc_nonempty_lines(ddc_text):
        record_type = line.split(",", 1)[0]
        if record_type in GEOMETRY_RECORD_TYPES:
            rows.append(line)
    return rows


def ddc_non_geometry_lines(ddc_text: str) -> list[str]:
    rows = []
    for line in ddc_nonempty_lines(ddc_text):
        record_type = line.split(",", 1)[0]
        if record_type not in GEOMETRY_RECORD_TYPES:
            rows.append(line)
    return rows


def classify_sym_path(path: Path, *, attrs: dict[str, dict[str, str]] | None = None) -> tuple[str, tuple[str, ...]]:
    attrs = attrs or {}
    reasons: list[str] = []
    path_text = str(path).replace("/", "\\").casefold()
    name_text = path.name.casefold()
    attr_110 = _attr_value(attrs, "110").casefold()

    if name_text == "donor.sym" or attr_110 == "donor":
        reasons.append("universal donor file name or Attr 110 donor")
        return "donor", tuple(reasons)

    synthetic_markers = (
        "generated_syms",
        "synthetic_",
        "encoder_noepsilon",
        "bad_native_quarantine",
        "_sym_probe",
        "_sym_probe_",
        "_sym_probe_copy",
    )
    if any(marker in path_text for marker in synthetic_markers):
        reasons.append("path matches synthetic/quarantine marker")
        return "synthetic", tuple(reasons)

    if "radan_known_good" in path_text or "radan_oracle" in path_text or "oracle_by_cleaned_stem" in path_text:
        reasons.append("path marked as RADAN oracle/known-good")
        return "lab-oracle", tuple(reasons)

    if "\\_headless_import_backups\\" in path_text:
        reasons.append("path is under headless import backups")
        return "backup-good", tuple(reasons)

    if path_text.startswith("l:\\") and "\\_sym_lab\\" not in path_text:
        reasons.append("L-side non-lab symbol")
        return "production-good", tuple(reasons)

    reasons.append("no trusted oracle marker")
    return "unknown", tuple(reasons)


def is_safe_oracle_classification(classification: str) -> bool:
    return classification in {"production-good", "backup-good", "lab-oracle"}


def summarize_sym(path: Path) -> dict[str, Any]:
    raw_bytes = path.read_bytes()
    text = raw_bytes.decode("utf-8", errors="replace")
    attrs = parse_sym_attrs(text)
    classification, reasons = classify_sym_path(path, attrs=attrs)
    ddc_text = extract_ddc_text(text)
    history_text = extract_history_text(text)
    no_ddc_text = _replace_ddc_with_marker(text)
    no_ddc_no_history_text = _replace_history_with_marker(no_ddc_text)
    normalized_no_ddc_no_history = _normalize_volatile_attrs(no_ddc_no_history_text)

    try:
        records = read_ddc_records(path)
        parse_error = ""
    except Exception as exc:
        records = []
        parse_error = str(exc)

    type_sequence = "".join(str(row.get("record", "")) for row in records)
    pen_counts = Counter(str(row.get("pen", "")) for row in records)
    token_counts = [len(row.get("tokens") or []) for row in records]
    geometry_lines = ddc_geometry_lines(ddc_text)
    non_geometry_lines = ddc_non_geometry_lines(ddc_text)
    geometry_data_text = "\n".join(str(row.get("geometry_data", "")) for row in records)

    return {
        "path": str(path),
        "name": path.name,
        "part_name": path.stem,
        "classification": classification,
        "classification_reasons": list(reasons),
        "safe_oracle": is_safe_oracle_classification(classification),
        "file_size": len(raw_bytes),
        "full_sha256": sha256_bytes(raw_bytes),
        "ddc_raw_sha256": sha256_text(ddc_text),
        "ddc_geometry_lines_sha256": sha256_text("\n".join(geometry_lines)),
        "ddc_geometry_data_sha256": sha256_text(geometry_data_text),
        "ddc_non_geometry_lines_sha256": sha256_text("\n".join(non_geometry_lines)),
        "history_sha256": sha256_text(history_text),
        "no_ddc_sha256": sha256_text(no_ddc_text),
        "no_ddc_no_history_sha256": sha256_text(no_ddc_no_history_text),
        "normalized_no_ddc_no_history_sha256": sha256_text(normalized_no_ddc_no_history),
        "attr_fingerprint_sha256": sha256_text(
            json.dumps(attrs, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        ),
        "attr_count": len(attrs),
        "important_attrs": {
            num: attrs[num]
            for num in sorted(IMPORTANT_ATTR_NUMS, key=lambda value: int(value))
            if num in attrs
        },
        "attr_110_file_name": _attr_value(attrs, "110"),
        "attr_119_material": _attr_value(attrs, "119"),
        "attr_120_thickness": _attr_value(attrs, "120"),
        "attr_121_units": _attr_value(attrs, "121"),
        "attr_146_strategy": _attr_value(attrs, "146"),
        "ddc_parse_error": parse_error,
        "ddc_record_count": len(records),
        "ddc_type_sequence": type_sequence,
        "ddc_type_counts": dict(Counter(str(row.get("record", "")) for row in records)),
        "ddc_pen_counts": dict(sorted(pen_counts.items())),
        "ddc_geometry_line_count": len(geometry_lines),
        "ddc_non_geometry_line_count": len(non_geometry_lines),
        "ddc_token_slot_count": sum(token_counts),
        "ddc_min_token_count": min(token_counts) if token_counts else 0,
        "ddc_max_token_count": max(token_counts) if token_counts else 0,
    }


def iter_sym_files(roots: Sequence[Path]) -> list[Path]:
    files: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        candidate = Path(root)
        if candidate.is_file() and candidate.suffix.casefold() == ".sym":
            resolved = str(candidate.resolve()).casefold()
            if resolved not in seen:
                seen.add(resolved)
                files.append(candidate)
            continue
        if not candidate.exists():
            continue
        for path in candidate.rglob("*.sym"):
            resolved = str(path.resolve()).casefold()
            if resolved in seen:
                continue
            seen.add(resolved)
            files.append(path)
    return sorted(files, key=lambda path: str(path).casefold())


def build_sym_index(roots: Sequence[Path]) -> dict[str, Any]:
    symbols = [summarize_sym(path) for path in iter_sym_files(roots)]
    by_part: dict[str, list[dict[str, Any]]] = {}
    for row in symbols:
        by_part.setdefault(str(row["part_name"]).casefold(), []).append(row)
    duplicate_parts = [
        {
            "part_name": rows[0]["part_name"],
            "count": len(rows),
            "safe_oracle_count": sum(1 for row in rows if row["safe_oracle"]),
            "classifications": dict(Counter(str(row["classification"]) for row in rows)),
            "ddc_geometry_fingerprints": sorted({str(row["ddc_geometry_lines_sha256"]) for row in rows}),
        }
        for rows in by_part.values()
        if len(rows) > 1
    ]
    classification_counts = Counter(str(row["classification"]) for row in symbols)
    return {
        "schema_version": 1,
        "roots": [str(Path(root)) for root in roots],
        "symbol_count": len(symbols),
        "safe_oracle_count": sum(1 for row in symbols if row["safe_oracle"]),
        "classification_counts": dict(sorted(classification_counts.items())),
        "duplicate_part_count": len(duplicate_parts),
        "duplicate_parts": sorted(duplicate_parts, key=lambda row: str(row["part_name"]).casefold()),
        "symbols": symbols,
    }


def _token(row: dict[str, Any], index: int) -> str:
    tokens = list(row.get("tokens") or [])
    return str(tokens[index]) if index < len(tokens) else ""


def _decoded_token_diff(good_token: str, compare_token: str) -> tuple[float | None, float | None, float | None, str]:
    try:
        good_value = decode_ddc_number(good_token)
        compare_value = decode_ddc_number(compare_token)
    except Exception as exc:
        return None, None, None, str(exc)
    return good_value, compare_value, abs(good_value - compare_value), ""


def _same_with_trailing_zero_padding(left: str, right: str) -> bool:
    if left == right:
        return True
    shorter, longer = (left, right) if len(left) < len(right) else (right, left)
    return bool(shorter) and longer.startswith(shorter) and set(longer[len(shorter) :]) <= {"0"}


def _token_mismatch_shape(
    good_token: str,
    compare_token: str,
    *,
    abs_diff: float | None,
    error: str,
) -> str:
    if error:
        return "decode_error"
    if good_token == "" or compare_token == "":
        return "empty_vs_nonempty"
    if abs_diff == 0:
        if _same_with_trailing_zero_padding(good_token, compare_token):
            return "trailing_zero_padding_only"
        return "same_decoded_value_different_token"
    if abs_diff is not None and abs_diff <= 1e-12:
        if len(good_token) == len(compare_token) and good_token[:-1] == compare_token[:-1]:
            return "last_char_delta_tiny_diff"
        return "tiny_decoded_diff"
    if abs_diff is not None and abs_diff <= 1e-6:
        return "small_decoded_diff"
    return "meaningful_decoded_diff"


def _compare_ddc_records(good_path: Path, compare_path: Path) -> dict[str, Any]:
    good_rows = read_ddc_records(good_path)
    compare_rows = read_ddc_records(compare_path)
    total_pairs = min(len(good_rows), len(compare_rows))
    exact_raw_matches = 0
    exact_geometry_data_matches = 0
    record_type_matches = 0
    pen_matches = 0
    total_slots = 0
    token_match_slots = 0
    decoded_nonzero_diff_slots = 0
    decoded_error_slots = 0
    max_decoded_abs_diff = 0.0
    token_mismatch_shape_counts: Counter[str] = Counter()
    last_char_delta_counts: Counter[str] = Counter()
    token_length_delta_counts: Counter[str] = Counter()
    top_decoded_diffs: list[dict[str, Any]] = []
    mismatch_examples: list[dict[str, Any]] = []
    pen_mismatch_examples: list[dict[str, Any]] = []

    for index, (good_row, compare_row) in enumerate(zip(good_rows, compare_rows), start=1):
        if good_row.get("raw") == compare_row.get("raw"):
            exact_raw_matches += 1
        if good_row.get("geometry_data") == compare_row.get("geometry_data"):
            exact_geometry_data_matches += 1
        if good_row.get("record") == compare_row.get("record"):
            record_type_matches += 1
        if str(good_row.get("pen", "")) == str(compare_row.get("pen", "")):
            pen_matches += 1
        elif len(pen_mismatch_examples) < 25:
            pen_mismatch_examples.append(
                {
                    "index": index,
                    "record": good_row.get("record"),
                    "good_pen": str(good_row.get("pen", "")),
                    "compare_pen": str(compare_row.get("pen", "")),
                    "good_identifier": good_row.get("identifier"),
                    "compare_identifier": compare_row.get("identifier"),
                }
            )

        slot_count = max(len(good_row.get("tokens") or []), len(compare_row.get("tokens") or []))
        for slot in range(slot_count):
            total_slots += 1
            good_token = _token(good_row, slot)
            compare_token = _token(compare_row, slot)
            if good_token == compare_token:
                token_match_slots += 1
                continue
            good_value, compare_value, abs_diff, error = _decoded_token_diff(good_token, compare_token)
            shape = _token_mismatch_shape(good_token, compare_token, abs_diff=abs_diff, error=error)
            token_mismatch_shape_counts[shape] += 1
            token_length_delta_counts[str(len(good_token) - len(compare_token))] += 1
            if shape == "last_char_delta_tiny_diff":
                last_char_delta_counts[str(ord(good_token[-1]) - ord(compare_token[-1]))] += 1
            example = {
                "index": index,
                "slot": slot,
                "record": good_row.get("record"),
                "good_token": good_token,
                "compare_token": compare_token,
                "good_value": good_value,
                "compare_value": compare_value,
                "abs_diff": abs_diff,
                "decode_error": error,
                "shape": shape,
            }
            if len(mismatch_examples) < 25:
                mismatch_examples.append(example)
            if error:
                decoded_error_slots += 1
                continue
            decoded_nonzero_diff_slots += 1 if abs_diff else 0
            max_decoded_abs_diff = max(max_decoded_abs_diff, float(abs_diff or 0.0))
            top_decoded_diffs.append(example)
            top_decoded_diffs.sort(key=lambda row: float(row.get("abs_diff") or 0.0), reverse=True)
            del top_decoded_diffs[25:]

    return {
        "good_record_count": len(good_rows),
        "compare_record_count": len(compare_rows),
        "paired_record_count": total_pairs,
        "count_match": len(good_rows) == len(compare_rows),
        "type_sequence_match": [row.get("record") for row in good_rows] == [row.get("record") for row in compare_rows],
        "pen_sequence_match": [str(row.get("pen", "")) for row in good_rows]
        == [str(row.get("pen", "")) for row in compare_rows],
        "exact_raw_record_matches": exact_raw_matches,
        "exact_geometry_data_matches": exact_geometry_data_matches,
        "record_type_matches": record_type_matches,
        "pen_matches": pen_matches,
        "total_token_slots": total_slots,
        "token_match_slots": token_match_slots,
        "token_match_ratio": token_match_slots / total_slots if total_slots else 0.0,
        "token_mismatch_shape_counts": dict(sorted(token_mismatch_shape_counts.items())),
        "last_char_delta_counts": dict(sorted(last_char_delta_counts.items())),
        "token_length_delta_counts": dict(sorted(token_length_delta_counts.items(), key=lambda item: int(item[0]))),
        "decoded_nonzero_diff_slots": decoded_nonzero_diff_slots,
        "decoded_error_slots": decoded_error_slots,
        "max_decoded_abs_diff": max_decoded_abs_diff,
        "pen_mismatch_examples": pen_mismatch_examples,
        "top_decoded_diffs": top_decoded_diffs,
        "token_mismatch_examples": mismatch_examples,
    }


def _diff_attrs(good_attrs: dict[str, dict[str, str]], compare_attrs: dict[str, dict[str, str]]) -> list[dict[str, Any]]:
    diffs: list[dict[str, Any]] = []
    for num in sorted(set(good_attrs) | set(compare_attrs), key=lambda value: int(value) if value.isdigit() else value):
        good = good_attrs.get(num, {})
        compare = compare_attrs.get(num, {})
        keys = sorted(set(good) | set(compare))
        changed = {key: {"good": good.get(key, ""), "compare": compare.get(key, "")} for key in keys if good.get(key, "") != compare.get(key, "")}
        if changed:
            diffs.append(
                {
                    "num": num,
                    "name": good.get("name") or compare.get("name") or "",
                    "group_name": good.get("group_name") or compare.get("group_name") or "",
                    "changed": changed,
                    "important": num in IMPORTANT_ATTR_NUMS,
                    "volatile": num in VOLATILE_ATTR_NUMS,
                }
            )
    return diffs


def diff_sym_sections(good_path: Path, compare_path: Path) -> dict[str, Any]:
    good_summary = summarize_sym(good_path)
    compare_summary = summarize_sym(compare_path)
    good_text = Path(good_path).read_text(encoding="utf-8", errors="replace")
    compare_text = Path(compare_path).read_text(encoding="utf-8", errors="replace")
    good_attrs = parse_sym_attrs(good_text)
    compare_attrs = parse_sym_attrs(compare_text)
    attr_diffs = _diff_attrs(good_attrs, compare_attrs)
    ddc_comparison = _compare_ddc_records(Path(good_path), Path(compare_path))

    section_equalities = {
        "full_file": good_summary["full_sha256"] == compare_summary["full_sha256"],
        "ddc_raw": good_summary["ddc_raw_sha256"] == compare_summary["ddc_raw_sha256"],
        "ddc_geometry_lines": good_summary["ddc_geometry_lines_sha256"]
        == compare_summary["ddc_geometry_lines_sha256"],
        "ddc_geometry_data": good_summary["ddc_geometry_data_sha256"] == compare_summary["ddc_geometry_data_sha256"],
        "ddc_non_geometry_lines": good_summary["ddc_non_geometry_lines_sha256"]
        == compare_summary["ddc_non_geometry_lines_sha256"],
        "history": good_summary["history_sha256"] == compare_summary["history_sha256"],
        "wrapper_without_ddc": good_summary["no_ddc_sha256"] == compare_summary["no_ddc_sha256"],
        "wrapper_without_ddc_or_history": good_summary["no_ddc_no_history_sha256"]
        == compare_summary["no_ddc_no_history_sha256"],
        "normalized_wrapper_without_ddc_or_history": good_summary["normalized_no_ddc_no_history_sha256"]
        == compare_summary["normalized_no_ddc_no_history_sha256"],
        "attr_fingerprint": good_summary["attr_fingerprint_sha256"] == compare_summary["attr_fingerprint_sha256"],
    }

    if section_equalities["full_file"]:
        localization = "identical"
    elif section_equalities["ddc_geometry_lines"] and not section_equalities["normalized_wrapper_without_ddc_or_history"]:
        localization = "metadata_or_wrapper_difference"
    elif not section_equalities["ddc_geometry_lines"] and section_equalities["normalized_wrapper_without_ddc_or_history"]:
        localization = "ddc_geometry_difference"
    elif not section_equalities["ddc_geometry_lines"]:
        localization = "mixed_ddc_and_metadata_difference"
    else:
        localization = "non_geometry_ddc_history_or_volatile_difference"

    return {
        "schema_version": 1,
        "good_path": str(good_path),
        "compare_path": str(compare_path),
        "good": good_summary,
        "compare": compare_summary,
        "section_equalities": section_equalities,
        "difference_localization": localization,
        "attr_diff_count": len(attr_diffs),
        "important_attr_diffs": [row for row in attr_diffs if row["important"]],
        "attr_diffs": attr_diffs,
        "ddc_comparison": ddc_comparison,
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    assert_w_drive_write_allowed(path, operation="write SYM analysis JSON")
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.tmp")
    temp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True) + "\n", encoding="utf-8")
    temp_path.replace(path)


def write_index_csv(path: Path, symbols: Iterable[dict[str, Any]]) -> None:
    assert_w_drive_write_allowed(path, operation="write SYM oracle index CSV")
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "part_name",
        "path",
        "classification",
        "safe_oracle",
        "file_size",
        "ddc_record_count",
        "ddc_geometry_line_count",
        "ddc_type_counts",
        "ddc_pen_counts",
        "ddc_geometry_lines_sha256",
        "normalized_no_ddc_no_history_sha256",
        "attr_110_file_name",
        "attr_119_material",
        "attr_120_thickness",
        "attr_121_units",
        "attr_146_strategy",
        "classification_reasons",
    ]
    temp_path = path.with_name(f"{path.name}.tmp")
    with temp_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in symbols:
            flat = {field: row.get(field, "") for field in fields}
            for field in ("ddc_type_counts", "ddc_pen_counts", "classification_reasons"):
                flat[field] = json.dumps(flat[field], ensure_ascii=True, sort_keys=True)
            writer.writerow(flat)
    temp_path.replace(path)
