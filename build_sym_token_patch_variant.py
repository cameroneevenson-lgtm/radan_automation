from __future__ import annotations

import argparse
import csv
import json
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

from ddc_corpus import read_ddc_records
from path_safety import assert_w_drive_write_allowed
from write_native_sym_prototype import DDC_BLOCK_RE


DEFAULT_LAB_ROOT = Path(__file__).resolve().parent / "_sym_lab"


def assert_lab_output_path(path: Path, *, lab_root: Path | None = None) -> None:
    assert_w_drive_write_allowed(path, operation="write SYM token patch variant")
    resolved = path.expanduser().resolve()
    root = (lab_root or DEFAULT_LAB_ROOT).expanduser().resolve()
    if resolved == root or root in resolved.parents:
        return
    raise RuntimeError(f"Refusing to write SYM token patch variant outside lab root {root}: {path}")


def parse_patch_spec(value: str) -> dict[str, Any]:
    fields = str(value).split(":")
    if len(fields) != 3:
        raise ValueError(f"Patch specs must be PART:ROW:SLOT, got: {value!r}")
    part, row_text, slot_text = fields
    if not part.strip():
        raise ValueError(f"Patch spec has an empty part name: {value!r}")
    row_index = int(row_text)
    slot = int(slot_text)
    if row_index <= 0:
        raise ValueError(f"Patch row index must be 1-based and positive: {value!r}")
    if slot < 0:
        raise ValueError(f"Patch slot must be zero-based and non-negative: {value!r}")
    return {"part": part.strip(), "row_index": row_index, "slot": slot, "source": "spec"}


def _truthy(value: str) -> bool:
    return str(value).strip().casefold() in {"1", "true", "yes", "y"}


def load_patch_csv(
    path: Path,
    *,
    roles: Iterable[str] = (),
    parts: Iterable[str] = (),
    only_mismatches: bool = True,
) -> list[dict[str, Any]]:
    role_filter = {str(value).strip().casefold() for value in roles if str(value).strip()}
    part_filter = {str(value).strip().casefold() for value in parts if str(value).strip()}
    patches: list[dict[str, Any]] = []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            part = str(row.get("part", "")).strip()
            role = str(row.get("role", "")).strip()
            if not part:
                continue
            if part_filter and part.casefold() not in part_filter:
                continue
            if role_filter and role.casefold() not in role_filter:
                continue
            if only_mismatches and "token_match" in row and _truthy(str(row.get("token_match", ""))):
                continue
            patches.append(
                {
                    "part": part,
                    "row_index": int(str(row["row_index"]).strip()),
                    "slot": int(str(row["slot"]).strip()),
                    "role": role,
                    "source": str(path),
                }
            )
    return patches


def _source_token(source_folder: Path, patch: dict[str, Any]) -> tuple[str, str]:
    rows = read_ddc_records(source_folder / f"{patch['part']}.sym")
    row_index = int(patch["row_index"])
    slot = int(patch["slot"])
    if row_index > len(rows):
        raise RuntimeError(f"Source {patch['part']} has no geometry row {row_index}.")
    row = rows[row_index - 1]
    tokens = list(row.get("tokens") or [])
    if slot >= len(tokens):
        raise RuntimeError(f"Source {patch['part']} row {row_index} has no token slot {slot}.")
    return str(tokens[slot]), str(row.get("record", ""))


def _replace_geometry_token(text: str, patch: dict[str, Any], token: str) -> tuple[str, dict[str, Any]]:
    match = DDC_BLOCK_RE.search(text)
    if match is None:
        raise RuntimeError(f"No DDC block found while patching {patch['part']}.")

    ddc_body = match.group(2)
    lines = ddc_body.splitlines()
    trailing_newline = ""
    if ddc_body.endswith("\r\n"):
        trailing_newline = "\r\n"
    elif ddc_body.endswith("\n"):
        trailing_newline = "\n"
    geometry_index = 0
    row_index = int(patch["row_index"])
    slot = int(patch["slot"])
    previous_token = ""
    target_record = ""
    replaced = False

    for line_index, line in enumerate(lines):
        if not line.strip():
            continue
        fields = line.split(",")
        record_type = fields[0] if fields else ""
        if record_type not in {"G", "H"}:
            continue
        geometry_index += 1
        if geometry_index != row_index:
            continue
        target_record = record_type
        while len(fields) <= 10:
            fields.append("")
        tokens = fields[10].split(".") if fields[10] else []
        while len(tokens) <= slot:
            tokens.append("")
        previous_token = tokens[slot]
        tokens[slot] = token
        fields[10] = ".".join(tokens)
        lines[line_index] = ",".join(fields)
        replaced = True
        break

    if not replaced:
        raise RuntimeError(f"Target {patch['part']} has no geometry row {row_index}.")

    newline = "\r\n" if "\r\n" in ddc_body else "\n"
    patched_body = newline.join(lines) + trailing_newline
    patched_text = DDC_BLOCK_RE.sub(
        lambda current: f"{current.group(1)}{patched_body}{current.group(3)}",
        text,
        count=1,
    )
    return patched_text, {
        "part": patch["part"],
        "row_index": row_index,
        "slot": slot,
        "role": patch.get("role", ""),
        "target_record": target_record,
        "previous_token": previous_token,
        "source_token": token,
        "changed": previous_token != token,
    }


def build_token_patch_variant(
    *,
    base_folder: Path,
    source_folder: Path,
    out_dir: Path,
    patches: list[dict[str, Any]],
    lab_root: Path | None = None,
) -> dict[str, Any]:
    assert_lab_output_path(out_dir, lab_root=lab_root)
    if out_dir.exists():
        raise RuntimeError(f"Refusing to overwrite existing token patch variant: {out_dir}")
    out_dir.mkdir(parents=True)

    copied = 0
    for path in sorted(base_folder.glob("*.sym"), key=lambda item: item.name.casefold()):
        shutil.copy2(path, out_dir / path.name)
        copied += 1

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for patch in patches:
        grouped[str(patch["part"])].append(patch)

    patch_results: list[dict[str, Any]] = []
    for part, part_patches in sorted(grouped.items(), key=lambda item: item[0].casefold()):
        target_path = out_dir / f"{part}.sym"
        if not target_path.exists():
            raise RuntimeError(f"Target symbol not found in base copy: {target_path}")
        text = target_path.read_text(encoding="utf-8", errors="replace")
        for patch in sorted(part_patches, key=lambda row: (int(row["row_index"]), int(row["slot"]))):
            token, source_record = _source_token(source_folder, patch)
            text, result = _replace_geometry_token(text, patch, token)
            result["source_record"] = source_record
            result["patch_source"] = patch.get("source", "")
            patch_results.append(result)
        target_path.write_text(text, encoding="utf-8")

    manifest = {
        "schema_version": 1,
        "base_folder": str(base_folder),
        "source_folder": str(source_folder),
        "out_dir": str(out_dir),
        "copied_symbol_count": copied,
        "patch_count": len(patch_results),
        "changed_patch_count": sum(1 for row in patch_results if row["changed"]),
        "patched_parts": sorted(grouped, key=str.casefold),
        "patches": patch_results,
    }
    manifest_path = out_dir / "token_patch_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=True, sort_keys=True), encoding="utf-8")
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a lab-only SYM corpus by copying selected DDC tokens.")
    parser.add_argument("--base-folder", type=Path, required=True)
    parser.add_argument("--source-folder", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--patch", action="append", default=[], help="Patch spec PART:ROW:SLOT.")
    parser.add_argument("--patch-csv", action="append", type=Path, default=[])
    parser.add_argument("--role", action="append", default=[], help="When reading CSVs, include only this role.")
    parser.add_argument("--part", action="append", default=[], help="When reading CSVs, include only this part.")
    parser.add_argument("--include-matches", action="store_true", help="Do not skip token_match=True CSV rows.")
    args = parser.parse_args(argv)

    patches = [parse_patch_spec(value) for value in args.patch]
    for csv_path in args.patch_csv:
        patches.extend(
            load_patch_csv(
                csv_path,
                roles=args.role,
                parts=args.part,
                only_mismatches=not args.include_matches,
            )
        )
    if not patches:
        raise RuntimeError("No token patches requested.")

    manifest = build_token_patch_variant(
        base_folder=args.base_folder,
        source_folder=args.source_folder,
        out_dir=args.out_dir,
        patches=patches,
    )
    print(json.dumps(manifest, indent=2, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
