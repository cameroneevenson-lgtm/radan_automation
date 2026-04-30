from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from ddc_corpus import read_dxf_entities
from path_safety import assert_w_drive_write_allowed


GEOMETRY_TYPES = {"LINE", "ARC", "CIRCLE"}
SALIENT_GROUPS = {
    "LINE": ("8", "10", "20", "11", "21"),
    "ARC": ("8", "10", "20", "40", "50", "51"),
    "CIRCLE": ("8", "10", "20", "40"),
}


def _pairs_from_text(text: str) -> list[dict[str, Any]]:
    lines = text.splitlines()
    pairs: list[dict[str, Any]] = []
    index = 0
    while index + 1 < len(lines):
        code = lines[index].strip()
        value = lines[index + 1].strip()
        pairs.append({"code": code, "value": value, "line_number": index + 1})
        index += 2
    return pairs


def _first_value(groups: list[dict[str, Any]], code: str) -> str:
    for group in groups:
        if str(group["code"]) == str(code):
            return str(group["value"])
    return ""


def _float_or_none(value: str) -> float | None:
    try:
        return float(value)
    except Exception:
        return None


def read_raw_dxf_entities(path: Path) -> list[dict[str, Any]]:
    pairs = _pairs_from_text(path.read_text(encoding="utf-8", errors="replace"))
    entities: list[dict[str, Any]] = []
    in_entities = False
    pending_section = False
    current: dict[str, Any] | None = None

    def finish_current() -> None:
        nonlocal current
        if current is not None:
            current["row_index"] = len(entities) + 1
            entities.append(current)
            current = None

    for pair in pairs:
        code = str(pair["code"])
        value = str(pair["value"])
        if code == "0" and value == "SECTION":
            pending_section = True
            finish_current()
            continue
        if pending_section and code == "2":
            in_entities = value == "ENTITIES"
            pending_section = False
            continue
        if code == "0" and value == "ENDSEC":
            finish_current()
            in_entities = False
            continue
        if not in_entities:
            continue
        if code == "0":
            finish_current()
            if value in GEOMETRY_TYPES:
                current = {
                    "type": value,
                    "start_line_number": pair["line_number"],
                    "groups": [],
                }
            continue
        if current is not None:
            current["groups"].append(pair)

    finish_current()
    return [summarize_raw_entity(entity) for entity in entities]


def summarize_raw_entity(entity: dict[str, Any]) -> dict[str, Any]:
    entity_type = str(entity["type"])
    groups = list(entity.get("groups") or [])
    salient_codes = SALIENT_GROUPS.get(entity_type, ())
    salient = [{"code": code, "value": _first_value(groups, code)} for code in salient_codes]
    return {
        "row_index": entity["row_index"],
        "type": entity_type,
        "start_line_number": entity["start_line_number"],
        "handle": _first_value(groups, "5"),
        "layer": _first_value(groups, "8"),
        "salient_groups": salient,
        "salient_numeric": [{"code": row["code"], "value": _float_or_none(row["value"])} for row in salient],
        "raw_group_count": len(groups),
        "raw_groups": [{"code": str(row["code"]), "value": str(row["value"])} for row in groups],
    }


def _normalized_geometry_row(dxf_path: Path, row_index: int) -> dict[str, Any]:
    rows, bounds = read_dxf_entities(dxf_path)
    row = dict(rows[row_index - 1])
    row["bounds"] = bounds.as_dict()
    return row


def _part_path(dxf_folder: Path, part: str) -> Path:
    path = dxf_folder / f"{part}.dxf"
    if path.exists():
        return path
    matches = {candidate.stem.casefold(): candidate for candidate in dxf_folder.glob("*.dxf")}
    try:
        return matches[part.casefold()]
    except KeyError:
        raise FileNotFoundError(f"No DXF found for part {part!r} in {dxf_folder}") from None


def _parse_focus(value: str) -> tuple[str, int]:
    if ":" not in value:
        raise argparse.ArgumentTypeError("Focus must be PART:ROW.")
    part, row_text = value.rsplit(":", 1)
    if not part.strip():
        raise argparse.ArgumentTypeError("Focus part cannot be empty.")
    row_index = int(row_text)
    if row_index <= 0:
        raise argparse.ArgumentTypeError("Focus row must be 1-based and positive.")
    return part.strip(), row_index


def _parse_compare(value: str) -> tuple[tuple[str, int], tuple[str, int]]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("Compare must be LEFT_PART:ROW=RIGHT_PART:ROW.")
    left, right = value.split("=", 1)
    return _parse_focus(left), _parse_focus(right)


def load_focus_entity(dxf_folder: Path, part: str, row_index: int) -> dict[str, Any]:
    dxf_path = _part_path(dxf_folder, part)
    raw_rows = read_raw_dxf_entities(dxf_path)
    if row_index > len(raw_rows):
        raise IndexError(f"{part} has {len(raw_rows)} raw DXF geometry rows, not row {row_index}.")
    raw = raw_rows[row_index - 1]
    normalized = _normalized_geometry_row(dxf_path, row_index)
    return {
        "part": part,
        "row_index": row_index,
        "dxf_path": str(dxf_path),
        "raw": raw,
        "normalized": normalized,
    }


def compare_focus_entities(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    left_raw = left["raw"]
    right_raw = right["raw"]
    left_salient = [(row["code"], row["value"]) for row in left_raw["salient_groups"]]
    right_salient = [(row["code"], row["value"]) for row in right_raw["salient_groups"]]
    left_numeric = [(row["code"], row["value"]) for row in left_raw["salient_numeric"]]
    right_numeric = [(row["code"], row["value"]) for row in right_raw["salient_numeric"]]
    diffs = []
    for index in range(max(len(left_salient), len(right_salient))):
        left_row = left_salient[index] if index < len(left_salient) else ("", "")
        right_row = right_salient[index] if index < len(right_salient) else ("", "")
        if left_row != right_row:
            diffs.append({"index": index, "left": left_row, "right": right_row})
    return {
        "left": {"part": left["part"], "row_index": left["row_index"]},
        "right": {"part": right["part"], "row_index": right["row_index"]},
        "same_type": left_raw["type"] == right_raw["type"],
        "same_layer": left_raw["layer"] == right_raw["layer"],
        "same_salient_raw_values": left_salient == right_salient,
        "same_salient_numeric_values": left_numeric == right_numeric,
        "same_raw_group_sequence": left_raw["raw_groups"] == right_raw["raw_groups"],
        "salient_diffs": diffs,
    }


def analyze_dxf_entity_provenance(
    *,
    dxf_folder: Path,
    focuses: list[tuple[str, int]],
    comparisons: list[tuple[tuple[str, int], tuple[str, int]]],
) -> dict[str, Any]:
    focus_entities = {
        f"{part}:{row_index}": load_focus_entity(dxf_folder, part, row_index)
        for part, row_index in focuses
    }
    comparison_rows = []
    for left_key, right_key in comparisons:
        left_label = f"{left_key[0]}:{left_key[1]}"
        right_label = f"{right_key[0]}:{right_key[1]}"
        left = focus_entities.get(left_label) or load_focus_entity(dxf_folder, *left_key)
        right = focus_entities.get(right_label) or load_focus_entity(dxf_folder, *right_key)
        focus_entities[left_label] = left
        focus_entities[right_label] = right
        comparison_rows.append(compare_focus_entities(left, right))
    return {
        "schema_version": 1,
        "dxf_folder": str(dxf_folder),
        "focuses": list(focus_entities.values()),
        "comparisons": comparison_rows,
    }


def write_markdown(payload: dict[str, Any], path: Path) -> None:
    assert_w_drive_write_allowed(path, operation="write DXF entity provenance markdown")
    lines = [
        "# DXF Entity Provenance Analysis",
        "",
        f"- DXF folder: `{payload['dxf_folder']}`",
        "",
        "## Focus Rows",
        "",
    ]
    for row in payload["focuses"]:
        raw = row["raw"]
        normalized = row["normalized"]
        lines.append(f"### {row['part']} row {row['row_index']}")
        lines.append(f"- Type/layer: `{raw['type']}` / `{raw['layer']}`")
        lines.append(f"- Handle: `{raw['handle']}`")
        lines.append(f"- Bounds: `{normalized.get('bounds')}`")
        lines.append("- Salient raw groups:")
        for group in raw["salient_groups"]:
            lines.append(f"  - `{group['code']}` = `{group['value']}`")
        lines.append("")

    lines.extend(["## Comparisons", ""])
    for row in payload["comparisons"]:
        left = f"{row['left']['part']}:{row['left']['row_index']}"
        right = f"{row['right']['part']}:{row['right']['row_index']}"
        lines.append(f"### {left} vs {right}")
        lines.append(f"- Same type: `{row['same_type']}`")
        lines.append(f"- Same layer: `{row['same_layer']}`")
        lines.append(f"- Same salient raw values: `{row['same_salient_raw_values']}`")
        lines.append(f"- Same salient numeric values: `{row['same_salient_numeric_values']}`")
        lines.append(f"- Same full raw group sequence: `{row['same_raw_group_sequence']}`")
        if row["salient_diffs"]:
            lines.append("- Salient diffs:")
            for diff in row["salient_diffs"]:
                lines.append(f"  - `{diff['left']}` vs `{diff['right']}`")
        lines.append("")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _assert_sym_lab_output(path: Path) -> None:
    assert_w_drive_write_allowed(path, operation="write DXF entity provenance output")
    lab_root = (Path(__file__).resolve().parent / "_sym_lab").resolve()
    resolved = path.resolve()
    if resolved == lab_root or lab_root in resolved.parents:
        return
    raise RuntimeError(f"Refusing to write DXF entity provenance output outside _sym_lab: {path}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect raw DXF group-code provenance for geometry entity rows.")
    parser.add_argument("--dxf-folder", type=Path, required=True)
    parser.add_argument("--focus", action="append", type=_parse_focus, default=[])
    parser.add_argument("--compare", action="append", type=_parse_compare, default=[])
    parser.add_argument("--out-json", type=Path, required=True)
    parser.add_argument("--out-md", type=Path)
    args = parser.parse_args(argv)

    for path in [args.out_json, args.out_md]:
        if path is not None:
            _assert_sym_lab_output(path)
            path.parent.mkdir(parents=True, exist_ok=True)

    payload = analyze_dxf_entity_provenance(
        dxf_folder=args.dxf_folder,
        focuses=args.focus,
        comparisons=args.compare,
    )
    args.out_json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.out_md:
        write_markdown(payload, args.out_md)
    print(json.dumps({key: value for key, value in payload.items() if key != "focuses"}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
