from __future__ import annotations

import argparse
import csv
import json
import math
import shutil
from pathlib import Path
from typing import Any

from ddc_corpus import read_dxf_entities
from ddc_number_codec import decode_ddc_number_fraction, encode_ddc_number
from path_safety import assert_w_drive_write_allowed
from write_native_sym_prototype import DEFAULT_LAB_ROOT, DDC_BLOCK_RE, _symbol_view_extents


def _assert_lab_output(path: Path) -> None:
    assert_w_drive_write_allowed(path, operation="write lab D-record variant")
    resolved = path.resolve()
    lab_root = DEFAULT_LAB_ROOT.resolve()
    if resolved != lab_root and lab_root not in resolved.parents:
        raise RuntimeError(f"Refusing to write D-record variant outside lab root {lab_root}: {path}")


def _read_csv_dxf_paths(csv_path: Path) -> dict[str, Path]:
    paths: dict[str, Path] = {}
    with csv_path.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.reader(handle):
            if not row or all(not cell.strip() for cell in row):
                continue
            dxf_path = Path(row[0].strip())
            paths[dxf_path.stem.casefold()] = dxf_path
    return paths


def _decode_token(token: str) -> float | None:
    if not token:
        return None
    try:
        return float(decode_ddc_number_fraction(token))
    except Exception:
        return None


def _view_token(value: float, *, half_x_down: bool = False) -> str:
    rounded = round(float(value), 6)
    if half_x_down:
        doubled = rounded * 2.0
        if math.isclose(doubled, round(doubled), rel_tol=0.0, abs_tol=1e-9) and int(round(doubled)) % 2 == 1:
            rounded = math.nextafter(rounded, -math.inf)
    return encode_ddc_number(rounded)


def _replace_d_record_field(text: str, *, part: str, dxf_path: Path, mode: str) -> tuple[str, dict[str, Any]]:
    match = DDC_BLOCK_RE.search(text)
    if match is None:
        raise RuntimeError(f"No DDC block found while patching {part}.")

    _rows, bounds = read_dxf_entities(dxf_path)
    view_x, view_y = _symbol_view_extents(bounds)
    ddc_body = match.group(2)
    lines = ddc_body.splitlines()
    trailing_newline = ""
    if ddc_body.endswith("\r\n"):
        trailing_newline = "\r\n"
    elif ddc_body.endswith("\n"):
        trailing_newline = "\n"
    changed = False
    result: dict[str, Any] = {
        "part": part,
        "dxf_path": str(dxf_path),
        "mode": mode,
        "bounds": bounds.as_dict(),
        "calculated_view_x": float(view_x),
        "calculated_view_y": float(view_y),
    }

    for line_index, line in enumerate(lines):
        fields = line.split(",")
        if not fields or fields[0] != "D" or len(fields) <= 3:
            continue
        old_field = fields[3]
        old_tokens = old_field.split(".")
        while len(old_tokens) <= 11:
            old_tokens.append("")
        new_tokens = list(old_tokens)

        if mode == "float6":
            new_tokens[1] = _view_token(float(view_x))
            new_tokens[3] = _view_token(float(view_y))
        elif mode == "float6-y-only":
            new_tokens[3] = _view_token(float(view_y))
        elif mode == "float6-half-x-down":
            new_tokens[1] = _view_token(float(view_x), half_x_down=True)
            new_tokens[3] = _view_token(float(view_y))
        else:
            raise ValueError(f"Unsupported D-record variant mode: {mode}")

        new_tokens[5] = new_tokens[1]
        new_tokens[7] = new_tokens[3]
        if new_tokens[11].startswith("$"):
            new_tokens[11] = f"${part}"
        new_field = ".".join(new_tokens).rstrip(".")
        fields[3] = new_field
        lines[line_index] = ",".join(fields)
        changed = old_field != new_field
        result.update(
            {
                "old_field": old_field,
                "new_field": new_field,
                "old_tokens": old_tokens,
                "new_tokens": new_tokens,
                "old_view_x": _decode_token(old_tokens[1]),
                "old_view_y": _decode_token(old_tokens[3]),
                "new_view_x": _decode_token(new_tokens[1]),
                "new_view_y": _decode_token(new_tokens[3]),
                "changed": changed,
            }
        )
        break
    else:
        raise RuntimeError(f"No D record found while patching {part}.")

    newline = "\r\n" if "\r\n" in ddc_body else "\n"
    patched_body = newline.join(lines) + trailing_newline
    patched_text = DDC_BLOCK_RE.sub(
        lambda current: f"{current.group(1)}{patched_body}{current.group(3)}",
        text,
        count=1,
    )
    return patched_text, result


def build_d_record_variant(
    *,
    base_folder: Path,
    csv_path: Path,
    out_dir: Path,
    parts: list[str],
    mode: str,
) -> dict[str, Any]:
    _assert_lab_output(out_dir)
    if out_dir.exists():
        raise RuntimeError(f"Refusing to overwrite existing D-record variant: {out_dir}")
    out_dir.mkdir(parents=True)

    dxf_paths = _read_csv_dxf_paths(csv_path)
    copied = 0
    for path in sorted(base_folder.glob("*.sym"), key=lambda item: item.name.casefold()):
        shutil.copy2(path, out_dir / path.name)
        copied += 1

    patch_results: list[dict[str, Any]] = []
    for part in parts:
        target_path = out_dir / f"{part}.sym"
        if not target_path.exists():
            raise RuntimeError(f"Target symbol not found in base copy: {target_path}")
        dxf_path = dxf_paths.get(part.casefold())
        if dxf_path is None:
            raise RuntimeError(f"No DXF path found in CSV for {part}.")
        text = target_path.read_text(encoding="utf-8", errors="replace")
        patched_text, result = _replace_d_record_field(text, part=part, dxf_path=dxf_path, mode=mode)
        target_path.write_text(patched_text, encoding="utf-8")
        patch_results.append(result)

    manifest = {
        "schema_version": 1,
        "base_folder": str(base_folder),
        "csv_path": str(csv_path),
        "out_dir": str(out_dir),
        "mode": mode,
        "copied_symbol_count": copied,
        "part_count": len(parts),
        "changed_part_count": sum(1 for row in patch_results if row.get("changed")),
        "parts": parts,
        "patches": patch_results,
    }
    (out_dir / "d_record_variant_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=True, sort_keys=True),
        encoding="utf-8",
    )
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build lab-only generated D-record spelling variants.")
    parser.add_argument("--base-folder", type=Path, required=True)
    parser.add_argument("--csv", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--part", action="append", required=True)
    parser.add_argument(
        "--mode",
        choices=("float6", "float6-y-only", "float6-half-x-down"),
        required=True,
    )
    args = parser.parse_args(argv)

    manifest = build_d_record_variant(
        base_folder=args.base_folder,
        csv_path=args.csv,
        out_dir=args.out_dir,
        parts=list(args.part),
        mode=args.mode,
    )
    print(json.dumps(manifest, indent=2, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
