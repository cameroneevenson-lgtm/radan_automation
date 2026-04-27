from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from ddc_corpus import DDC_RE, KNOWN_PEN_BY_LAYER, build_part_corpus, read_dxf_entities
from ddc_number_codec import encode_ddc_number


DEFAULT_LAB_ROOT = Path(__file__).resolve().parent / "_sym_lab"
DDC_BLOCK_RE = re.compile(
    r'(<RadanFile\s+extension="ddc"\s*>\s*<!\[CDATA\[)(.*?)(\]\]>\s*</RadanFile>)',
    re.DOTALL,
)


def _pad_tokens(tokens: dict[int, float], length: int) -> list[str]:
    padded = [""] * length
    for index, value in tokens.items():
        if index >= length:
            padded.extend([""] * (index - length + 1))
        padded[index] = encode_ddc_number(value)
    return padded


def encode_geometry_data(dxf_row: dict[str, Any], *, token_count: int) -> str:
    entity_type = str(dxf_row["type"])
    if entity_type == "LINE":
        start = dxf_row["normalized_start"]
        end = dxf_row["normalized_end"]
        tokens = {
            0: float(start[0]),
            1: float(start[1]),
            2: float(end[0]) - float(start[0]),
            3: float(end[1]) - float(start[1]),
        }
        return ".".join(_pad_tokens(tokens, token_count))

    if entity_type == "CIRCLE":
        center = dxf_row["normalized_center"]
        radius = float(dxf_row["radius"])
        tokens = {
            0: float(center[0]) + radius,
            1: float(center[1]),
            4: -radius,
            6: 1.0,
            9: 1.0,
        }
        return ".".join(_pad_tokens(tokens, token_count))

    if entity_type == "ARC":
        start = dxf_row["normalized_start_point"]
        end = dxf_row["normalized_end_point"]
        center = dxf_row["normalized_center"]
        tokens = {
            0: float(start[0]),
            1: float(start[1]),
            2: float(end[0]) - float(start[0]),
            3: float(end[1]) - float(start[1]),
            4: float(center[0]) - float(start[0]),
            5: float(center[1]) - float(start[1]),
            6: 1.0,
            9: 1.0,
        }
        return ".".join(_pad_tokens(tokens, token_count))

    raise ValueError(f"Unsupported DXF entity type: {entity_type}")


def _replace_ddc_geometry_block(template_text: str, dxf_rows: list[dict[str, Any]]) -> tuple[str, dict[str, Any]]:
    match = DDC_BLOCK_RE.search(template_text)
    if match is None:
        raise RuntimeError("No DDC CDATA block found in template symbol.")

    geometry_index = 0
    replaced_records = 0
    lines: list[str] = []
    for line in match.group(2).splitlines():
        fields = line.split(",")
        if fields and fields[0] in {"G", "H"}:
            if geometry_index >= len(dxf_rows):
                raise RuntimeError("Template contains more DDC geometry records than the source DXF.")
            dxf_row = dxf_rows[geometry_index]
            expected_record = "G" if dxf_row["type"] == "LINE" else "H"
            if fields[0] != expected_record:
                raise RuntimeError(
                    f"Record type mismatch at geometry index {geometry_index + 1}: "
                    f"template={fields[0]!r}, dxf={dxf_row['type']!r}."
                )
            while len(fields) <= 10:
                fields.append("")
            original_token_count = len(fields[10].split(".")) if fields[10] else (17 if fields[0] == "G" else 21)
            fields[8] = KNOWN_PEN_BY_LAYER.get(str(dxf_row.get("layer", "")), fields[8])
            fields[10] = encode_geometry_data(dxf_row, token_count=original_token_count)
            line = ",".join(fields)
            geometry_index += 1
            replaced_records += 1
        lines.append(line)

    if geometry_index != len(dxf_rows):
        raise RuntimeError(
            f"Source DXF has {len(dxf_rows)} geometry entities but template had {geometry_index} DDC records."
        )

    new_block = "\n".join(lines)
    if match.group(2).endswith("\n"):
        new_block += "\n"
    output_text = template_text[: match.start(2)] + new_block + template_text[match.end(2) :]
    return output_text, {"replaced_records": replaced_records}


def _ensure_lab_output(path: Path, *, allow_outside_lab: bool = False) -> None:
    if allow_outside_lab:
        return
    resolved = path.resolve()
    lab_root = DEFAULT_LAB_ROOT.resolve()
    if resolved != lab_root and lab_root not in resolved.parents:
        raise RuntimeError(f"Prototype output must stay under {lab_root} unless --allow-outside-lab is used.")


def write_native_prototype(
    *,
    dxf_path: Path,
    template_sym: Path,
    out_path: Path,
    allow_outside_lab: bool = False,
) -> dict[str, Any]:
    _ensure_lab_output(out_path, allow_outside_lab=allow_outside_lab)
    dxf_rows, bounds = read_dxf_entities(dxf_path)
    template_text = template_sym.read_text(encoding="utf-8", errors="replace")
    if DDC_RE.search(template_text) is None:
        raise RuntimeError(f"No DDC block found in template symbol: {template_sym}")
    output_text, stats = _replace_ddc_geometry_block(template_text, dxf_rows)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = out_path.with_name(f"{out_path.name}.tmp")
    temp_path.write_text(output_text, encoding="utf-8")
    temp_path.replace(out_path)
    validation = build_part_corpus(dxf_path, out_path)
    return {
        "dxf_path": str(dxf_path),
        "template_sym": str(template_sym),
        "out_path": str(out_path),
        "bounds": bounds.as_dict(),
        "entity_count": len(dxf_rows),
        "replaced_records": stats["replaced_records"],
        "validation": {
            "dxf_count": validation["dxf_count"],
            "ddc_count": validation["ddc_count"],
            "count_match": validation["count_match"],
            "type_mismatch_count": validation["type_mismatch_count"],
            "known_pen_mismatch_count": validation["known_pen_mismatch_count"],
        },
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.tmp")
    temp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True) + "\n", encoding="utf-8")
    temp_path.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Write a lab-only native .sym prototype from DXF geometry.")
    parser.add_argument("--dxf", type=Path, required=True, help="Source DXF path.")
    parser.add_argument("--template-sym", type=Path, required=True, help="Known-good template .sym to clone.")
    parser.add_argument("--out", type=Path, required=True, help=f"Output .sym path under {DEFAULT_LAB_ROOT}.")
    parser.add_argument("--report", type=Path, help="Optional JSON report path.")
    parser.add_argument("--allow-outside-lab", action="store_true", help=f"Allow output outside {DEFAULT_LAB_ROOT}.")
    args = parser.parse_args()

    payload = write_native_prototype(
        dxf_path=args.dxf,
        template_sym=args.template_sym,
        out_path=args.out,
        allow_outside_lab=bool(args.allow_outside_lab),
    )
    if args.report:
        write_json(args.report, payload)
    print(json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
