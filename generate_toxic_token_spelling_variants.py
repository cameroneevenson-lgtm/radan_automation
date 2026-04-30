from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from ddc_number_codec import decode_ddc_number
from path_safety import assert_w_drive_write_allowed
from write_native_sym_prototype import DDC_BLOCK_RE, DEFAULT_LAB_ROOT


@dataclass(frozen=True)
class TokenShiftPatch:
    part: str
    row_index: int
    slot: int
    shift: int
    append_zeros: int = 0
    note: str = ""


B37_VARIANTS: dict[str, list[TokenShiftPatch]] = {
    "b37_append_zero_deltas": [
        TokenShiftPatch("F54410-B-37", 13, 3, 0, 1, "append one zero to positive vertical delta"),
        TokenShiftPatch("F54410-B-37", 19, 3, 0, 1, "append one zero to negative vertical delta"),
    ],
    "b37_delta_signed2_z1": [
        TokenShiftPatch("F54410-B-37", 13, 3, 2, 1, "positive vertical delta plus two units and one zero"),
        TokenShiftPatch("F54410-B-37", 19, 3, -2, 1, "negative vertical delta minus two units and one zero"),
    ],
    "b37_start_y_m1_only": [
        TokenShiftPatch("F54410-B-37", 13, 1, -1, 0, "row 13 start Y minus one unit"),
    ],
    "b37_delta_signed2_z1_start_y_m1": [
        TokenShiftPatch("F54410-B-37", 13, 1, -1, 0, "row 13 start Y minus one unit"),
        TokenShiftPatch("F54410-B-37", 13, 3, 2, 1, "positive vertical delta plus two units and one zero"),
        TokenShiftPatch("F54410-B-37", 19, 3, -2, 1, "negative vertical delta minus two units and one zero"),
    ],
    "b37_delta_signed4_z1_start_y_m1": [
        TokenShiftPatch("F54410-B-37", 13, 1, -1, 0, "row 13 start Y minus one unit"),
        TokenShiftPatch("F54410-B-37", 13, 3, 4, 1, "positive vertical delta plus four units and one zero"),
        TokenShiftPatch("F54410-B-37", 19, 3, -4, 1, "negative vertical delta minus four units and one zero"),
    ],
}

B38_SOURCE_LIKE_RESIDUAL_VARIANT = [
    TokenShiftPatch("F54410-B-38", 20, 0, -2, 0, "start X minus two units"),
    TokenShiftPatch("F54410-B-38", 20, 1, 1, 0, "start/end Y plus one unit"),
    TokenShiftPatch("F54410-B-38", 20, 3, 0, 1, "vertical delta spelling with one zero"),
    TokenShiftPatch("F54410-B-38", 23, 1, 1, 0, "Y plus one unit"),
    TokenShiftPatch("F54410-B-38", 23, 2, 1, 2, "horizontal delta plus one unit and two zeros"),
    TokenShiftPatch("F54410-B-38", 25, 0, -2, 0, "start X minus two units"),
    TokenShiftPatch("F54410-B-38", 25, 1, -2, 0, "Y minus two units"),
    TokenShiftPatch("F54410-B-38", 25, 2, 4, 1, "horizontal delta plus four units and one zero"),
    TokenShiftPatch("F54410-B-38", 30, 0, -1, 0, "start X minus one unit"),
    TokenShiftPatch("F54410-B-38", 30, 1, -1, 0, "Y minus one unit"),
    TokenShiftPatch("F54410-B-38", 30, 2, -12, 1, "horizontal delta minus twelve units and one zero"),
    TokenShiftPatch("F54410-B-38", 33, 0, 1, 0, "start X plus one unit"),
    TokenShiftPatch("F54410-B-38", 33, 2, 1, 2, "horizontal delta plus one unit and two zeros"),
    TokenShiftPatch("F54410-B-38", 35, 0, -1, 0, "start X minus one unit"),
    TokenShiftPatch("F54410-B-38", 35, 3, 0, 1, "vertical delta spelling with one zero"),
    TokenShiftPatch("F54410-B-38", 37, 0, -1, 0, "start X minus one unit"),
    TokenShiftPatch("F54410-B-38", 37, 1, -1, 0, "Y minus one unit"),
    TokenShiftPatch("F54410-B-38", 37, 2, 4, 1, "horizontal delta plus four units and one zero"),
    TokenShiftPatch("F54410-B-38", 199, 0, 2, 0, "start X plus two units"),
    TokenShiftPatch("F54410-B-38", 199, 1, -2, 0, "Y minus two units"),
    TokenShiftPatch("F54410-B-38", 199, 2, -12, 1, "horizontal delta minus twelve units and one zero"),
    TokenShiftPatch("F54410-B-38", 200, 0, -2, 0, "start X minus two units"),
    TokenShiftPatch("F54410-B-38", 200, 3, 0, 1, "vertical delta spelling with one zero"),
]

BUILTIN_VARIANTS: dict[str, list[TokenShiftPatch]] = {
    **B37_VARIANTS,
    "b38_source_like_residual_digits": B38_SOURCE_LIKE_RESIDUAL_VARIANT,
}


def assert_lab_output_path(path: Path, *, operation: str = "write token spelling variant") -> None:
    assert_w_drive_write_allowed(path, operation=operation)
    resolved = path.expanduser().resolve()
    root = DEFAULT_LAB_ROOT.expanduser().resolve()
    if resolved != root and root not in resolved.parents:
        raise RuntimeError(f"Refusing to {operation} outside lab root {root}: {path}")


def shift_last_continuation_digit(token: str, *, shift: int, append_zeros: int = 0) -> str:
    if token == "":
        raise ValueError("Cannot shift an empty DDC token.")
    if len(token) < 4:
        raise ValueError(f"Token has no continuation digit to shift: {token!r}")
    chars = list(token)
    new_code = ord(chars[-1]) + int(shift)
    if new_code < 48 or new_code >= 112:
        raise ValueError(f"Shift moves final continuation digit outside DDC range: {token!r}, shift={shift}")
    chars[-1] = chr(new_code)
    if append_zeros < 0:
        raise ValueError("append_zeros cannot be negative.")
    return "".join(chars) + ("0" * int(append_zeros))


def _replace_geometry_token(text: str, patch: TokenShiftPatch) -> tuple[str, dict[str, Any]]:
    match = DDC_BLOCK_RE.search(text)
    if match is None:
        raise RuntimeError(f"No DDC block found while patching {patch.part}.")

    body = match.group(2)
    newline = "\r\n" if "\r\n" in body else "\n"
    trailing_newline = body.endswith(("\r\n", "\n"))
    lines = body.splitlines()
    geometry_index = 0
    result: dict[str, Any] | None = None

    for line_index, line in enumerate(lines):
        fields = line.split(",")
        if not fields or fields[0] not in {"G", "H"}:
            continue
        geometry_index += 1
        if geometry_index != patch.row_index:
            continue
        if len(fields) <= 10:
            raise RuntimeError(f"{patch.part} row {patch.row_index} has no field 10.")
        tokens = fields[10].split(".") if fields[10] else []
        if patch.slot >= len(tokens):
            raise RuntimeError(f"{patch.part} row {patch.row_index} has no token slot {patch.slot}.")
        old_token = tokens[patch.slot]
        new_token = shift_last_continuation_digit(
            old_token,
            shift=patch.shift,
            append_zeros=patch.append_zeros,
        )
        tokens[patch.slot] = new_token
        fields[10] = ".".join(tokens)
        lines[line_index] = ",".join(fields)
        result = {
            **asdict(patch),
            "record": fields[0],
            "old_token": old_token,
            "new_token": new_token,
            "old_value": decode_ddc_number(old_token),
            "new_value": decode_ddc_number(new_token),
            "delta": decode_ddc_number(new_token) - decode_ddc_number(old_token),
            "changed": old_token != new_token,
        }
        break

    if result is None:
        raise RuntimeError(f"{patch.part} has no geometry row {patch.row_index}.")

    patched_body = newline.join(lines) + (newline if trailing_newline else "")
    patched_text = DDC_BLOCK_RE.sub(
        lambda current: f"{current.group(1)}{patched_body}{current.group(3)}",
        text,
        count=1,
    )
    return patched_text, result


def build_variant(base_folder: Path, out_dir: Path, name: str, patches: list[TokenShiftPatch]) -> dict[str, Any]:
    if not patches:
        raise ValueError(f"Variant {name!r} has no patches.")
    base_folder = base_folder.expanduser().resolve()
    variant_dir = (out_dir / name).expanduser().resolve()
    assert_lab_output_path(variant_dir)
    if variant_dir.exists():
        raise RuntimeError(f"Refusing to overwrite existing variant folder: {variant_dir}")
    shutil.copytree(base_folder, variant_dir)

    results: list[dict[str, Any]] = []
    grouped: dict[str, list[TokenShiftPatch]] = {}
    for patch in patches:
        grouped.setdefault(patch.part, []).append(patch)

    for part, part_patches in sorted(grouped.items(), key=lambda item: item[0].casefold()):
        sym_path = variant_dir / f"{part}.sym"
        if not sym_path.exists():
            raise FileNotFoundError(f"Part symbol not found in variant folder: {sym_path}")
        text = sym_path.read_text(encoding="utf-8", errors="replace")
        for patch in sorted(part_patches, key=lambda item: (item.row_index, item.slot)):
            text, result = _replace_geometry_token(text, patch)
            results.append(result)
        sym_path.write_text(text, encoding="utf-8")

    manifest = {
        "variant": name,
        "base_folder": str(base_folder),
        "variant_dir": str(variant_dir),
        "patch_count": len(results),
        "parts": sorted(grouped, key=str.casefold),
        "patches": results,
    }
    (variant_dir / "token_spelling_variant_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return manifest


def parse_patch_spec(value: str) -> tuple[str, TokenShiftPatch]:
    fields = value.split(":")
    if len(fields) < 5:
        raise ValueError("Patch specs must be VARIANT:PART:ROW:SLOT:SHIFT[:APPEND_ZEROS[:NOTE]].")
    variant, part, row_text, slot_text, shift_text = fields[:5]
    append_zeros = int(fields[5]) if len(fields) >= 6 and fields[5] else 0
    note = fields[6] if len(fields) >= 7 else "custom token shift"
    return (
        variant,
        TokenShiftPatch(
            part=part.strip(),
            row_index=int(row_text),
            slot=int(slot_text),
            shift=int(shift_text),
            append_zeros=append_zeros,
            note=note,
        ),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build lab-only compact token spelling variants without oracle row copy.")
    parser.add_argument("--base-folder", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument(
        "--variant",
        action="append",
        default=[],
        help="Built-in variant name. Defaults to all B37 built-ins.",
    )
    parser.add_argument(
        "--patch",
        action="append",
        default=[],
        help="Custom patch spec VARIANT:PART:ROW:SLOT:SHIFT[:APPEND_ZEROS[:NOTE]].",
    )
    args = parser.parse_args()

    selected: dict[str, list[TokenShiftPatch]] = {}
    variants = args.variant or sorted(B37_VARIANTS)
    for name in variants:
        if name not in BUILTIN_VARIANTS:
            raise ValueError(f"Unknown built-in variant {name!r}. Known: {', '.join(sorted(BUILTIN_VARIANTS))}")
        selected[name] = list(BUILTIN_VARIANTS[name])

    for value in args.patch:
        name, patch = parse_patch_spec(value)
        selected.setdefault(name, []).append(patch)

    out_dir = args.out_dir.expanduser().resolve()
    assert_lab_output_path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    manifests = [
        build_variant(args.base_folder, out_dir, name, patches)
        for name, patches in sorted(selected.items(), key=lambda item: item[0])
    ]
    summary = {
        "base_folder": str(args.base_folder.expanduser().resolve()),
        "out_dir": str(out_dir),
        "variant_count": len(manifests),
        "variants": [
            {
                "variant": manifest["variant"],
                "variant_dir": manifest["variant_dir"],
                "patch_count": manifest["patch_count"],
                "parts": manifest["parts"],
            }
            for manifest in manifests
        ],
    }
    (out_dir / "token_spelling_variants_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
