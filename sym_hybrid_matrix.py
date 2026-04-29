from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

from path_safety import assert_w_drive_write_allowed
from radan_sym_analysis import DDC_BLOCK_RE, ddc_nonempty_lines, diff_sym_sections, extract_ddc_text, write_json


def _write_text(path: Path, text: str) -> None:
    assert_w_drive_write_allowed(path, operation="write SYM hybrid")
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.tmp")
    temp_path.write_text(text, encoding="utf-8")
    temp_path.replace(path)


def _replace_ddc_text(sym_text: str, ddc_text: str) -> str:
    if not DDC_BLOCK_RE.search(sym_text):
        raise RuntimeError("No DDC block found in symbol text.")
    return DDC_BLOCK_RE.sub(lambda match: f"{match.group(1)}{ddc_text}{match.group(3)}", sym_text, count=1)


def _geometry_record_type(line: str) -> str:
    record = line.split(",", 1)[0].strip()
    return record if record in {"G", "H"} else ""


def _merge_geometry_lines(base_ddc: str, geometry_source_ddc: str) -> str:
    source_geometry = [line for line in ddc_nonempty_lines(geometry_source_ddc) if _geometry_record_type(line)]
    source_index = 0
    output_lines: list[str] = []
    for line in base_ddc.splitlines():
        if _geometry_record_type(line):
            if source_index >= len(source_geometry):
                raise RuntimeError("Geometry source has fewer G/H records than base DDC.")
            output_lines.append(source_geometry[source_index])
            source_index += 1
        else:
            output_lines.append(line)
    if source_index != len(source_geometry):
        raise RuntimeError("Geometry source has more G/H records than base DDC.")
    newline = "\r\n" if "\r\n" in base_ddc else "\n"
    trailing_newline = ""
    if base_ddc.endswith("\r\n"):
        trailing_newline = "\r\n"
    elif base_ddc.endswith("\n"):
        trailing_newline = "\n"
    return newline.join(output_lines) + trailing_newline


def build_hybrid_matrix(*, good_path: Path, compare_path: Path, out_dir: Path) -> dict[str, Any]:
    assert_w_drive_write_allowed(out_dir, operation="write SYM hybrid matrix")
    out_dir.mkdir(parents=True, exist_ok=True)
    good_text = good_path.read_text(encoding="utf-8", errors="replace")
    compare_text = compare_path.read_text(encoding="utf-8", errors="replace")
    good_ddc = extract_ddc_text(good_text)
    compare_ddc = extract_ddc_text(compare_text)
    if not good_ddc or not compare_ddc:
        raise RuntimeError("Both good and compare symbols must contain DDC blocks.")

    variants = [
        {
            "name": "good_exact_copy",
            "description": "Known-good symbol copied unchanged.",
            "text": good_text,
        },
        {
            "name": "compare_exact_copy",
            "description": "Synthetic/suspect symbol copied unchanged.",
            "text": compare_text,
        },
        {
            "name": "good_wrapper_compare_full_ddc",
            "description": "Known-good wrapper/history/attributes with the full compare DDC block.",
            "text": _replace_ddc_text(good_text, compare_ddc),
        },
        {
            "name": "compare_wrapper_good_full_ddc",
            "description": "Compare wrapper/history/attributes with the full known-good DDC block.",
            "text": _replace_ddc_text(compare_text, good_ddc),
        },
        {
            "name": "good_wrapper_compare_geometry_only",
            "description": "Known-good DDC non-geometry lines with compare G/H geometry records.",
            "text": _replace_ddc_text(good_text, _merge_geometry_lines(good_ddc, compare_ddc)),
        },
        {
            "name": "compare_wrapper_good_geometry_only",
            "description": "Compare DDC non-geometry lines with known-good G/H geometry records.",
            "text": _replace_ddc_text(compare_text, _merge_geometry_lines(compare_ddc, good_ddc)),
        },
    ]

    written: list[dict[str, Any]] = []
    stem = good_path.stem
    for variant in variants:
        path = out_dir / f"{stem}__{variant['name']}.sym"
        _write_text(path, str(variant["text"]))
        diff = diff_sym_sections(good_path, path)
        diff_path = out_dir / f"{stem}__{variant['name']}.diff.json"
        write_json(diff_path, diff)
        ddc = diff["ddc_comparison"]
        written.append(
            {
                "name": variant["name"],
                "description": variant["description"],
                "path": str(path),
                "diff_path": str(diff_path),
                "difference_localization": diff["difference_localization"],
                "token_match_ratio": ddc["token_match_ratio"],
                "exact_geometry_data_matches": ddc["exact_geometry_data_matches"],
                "paired_record_count": ddc["paired_record_count"],
                "pen_sequence_match": ddc["pen_sequence_match"],
                "token_mismatch_shape_counts": ddc["token_mismatch_shape_counts"],
            }
        )

    manifest = {
        "schema_version": 1,
        "good_path": str(good_path),
        "compare_path": str(compare_path),
        "out_dir": str(out_dir),
        "variants": written,
    }
    write_json(out_dir / "hybrid_matrix.json", manifest)
    shutil.copyfile(good_path, out_dir / f"{stem}__source_good_original.sym")
    shutil.copyfile(compare_path, out_dir / f"{stem}__source_compare_original.sym")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Create lab-only SYM hybrid variants for later RADAN validation.")
    parser.add_argument("--good", type=Path, required=True, help="Known-good RADAN-created .sym.")
    parser.add_argument("--compare", type=Path, required=True, help="Synthetic or suspect .sym.")
    parser.add_argument("--out-dir", type=Path, required=True, help="Output folder for lab-only hybrid symbols.")
    args = parser.parse_args()

    payload = build_hybrid_matrix(good_path=args.good, compare_path=args.compare, out_dir=args.out_dir)
    print(json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
