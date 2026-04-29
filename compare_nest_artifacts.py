from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


RADAN_PROJECT_NS = "http://www.radan.com/ns/project"
NEST_ID_RE = re.compile(r"\bP(?P<id>\d+)\b", re.IGNORECASE)
TIMESTAMP_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:[-+]\d{2}:\d{2})?")
SYM_PATH_RE = re.compile(r"[A-Za-z]:[\\/][^,\r\n<>$]*[\\/](?P<name>[^\\/,\r\n<>$]+\.sym)", re.IGNORECASE)
SLASH_PATH_RE = re.compile(r"[A-Za-z]:/[^\r\n<>$]*?/(?P<name>[^/\r\n<>$]+\.sym)", re.IGNORECASE)
LAB_JOB_RE = re.compile(r"F54410 PAINT PACK\.[A-Za-z0-9_.-]+")
NEST_DIR_RE = re.compile(r"[A-Za-z]:[/\\][^,\r\n<>$]*[/\\]nests", re.IGNORECASE)
DDC_RECORD_RE = re.compile(r"^(?P<prefix>[A-Z\]])(?:,|$)")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_text(text: str) -> str:
    return _sha256_bytes(text.encode("utf-8", errors="replace"))


def _local_name(node: ET.Element) -> str:
    if "}" in node.tag:
        return node.tag.rsplit("}", 1)[1]
    return node.tag


def _children(parent: ET.Element | None, name: str) -> list[ET.Element]:
    if parent is None:
        return []
    return [child for child in list(parent) if _local_name(child) == name]


def _child(parent: ET.Element | None, name: str) -> ET.Element | None:
    matches = _children(parent, name)
    return matches[0] if matches else None


def _text(parent: ET.Element | None, name: str, default: str = "") -> str:
    child = _child(parent, name)
    if child is None or child.text is None:
        return default
    return child.text.strip()


def _int_text(parent: ET.Element | None, name: str, default: int = 0) -> int:
    try:
        return int(_text(parent, name, str(default)))
    except ValueError:
        return default


def _basename(path_text: str) -> str:
    return re.split(r"[\\/]", path_text.strip())[-1]


def _part_name_from_path(path_text: str) -> str:
    name = _basename(path_text)
    if name.lower().endswith(".sym"):
        return name[:-4]
    return name


def _nest_id_from_name(value: str) -> int | None:
    match = NEST_ID_RE.search(value)
    if not match:
        return None
    return int(match.group("id"))


def _find_rpd(gate_dir: Path, result: dict[str, Any]) -> Path:
    project_value = str(result.get("project_path", "")).strip()
    project_path = Path(project_value) if project_value else None
    if project_path is not None and project_path.exists() and project_path.is_file():
        return project_path
    matches = sorted(gate_dir.rglob("*.rpd"))
    if not matches:
        raise FileNotFoundError(f"No .rpd found under {gate_dir}")
    return matches[0]


def _find_drg_files(gate_dir: Path, result: dict[str, Any]) -> list[Path]:
    paths = [Path(value) for value in result.get("drg_files", []) if Path(str(value)).exists()]
    if paths:
        return sorted(paths)
    return sorted(gate_dir.rglob("*.drg"))


def load_gate_result(gate_dir: Path) -> dict[str, Any]:
    result_path = gate_dir / "result.json"
    if not result_path.exists():
        return {}
    return json.loads(result_path.read_text(encoding="utf-8"))


def parse_rpd_nests(project_path: Path) -> list[dict[str, Any]]:
    root = ET.parse(project_path).getroot()
    nests_node = _child(root, "Nests")
    nests: list[dict[str, Any]] = []
    for nest in _children(nests_node, "Nest"):
        filename = _text(nest, "FileName")
        sheet_used = _child(nest, "SheetUsed")
        parts_made = _child(nest, "PartsMade")
        parts = []
        for part_node in _children(parts_made, "PartMade"):
            file_text = _text(part_node, "File")
            parts.append(
                {
                    "part": _part_name_from_path(file_text),
                    "file_basename": _basename(file_text),
                    "made": _int_text(part_node, "Made"),
                }
            )
        parts.sort(key=lambda row: (row["part"].casefold(), row["made"]))
        nest_id = _int_text(nest, "ID", -1)
        if nest_id < 0:
            nest_id = _nest_id_from_name(filename) or -1
        nests.append(
            {
                "id": nest_id,
                "filename": filename,
                "filename_id": _nest_id_from_name(filename),
                "used": _int_text(sheet_used, "Used"),
                "material": _text(sheet_used, "Material"),
                "thickness": _text(sheet_used, "Thickness"),
                "sheet_x": _text(sheet_used, "SheetX"),
                "sheet_y": _text(sheet_used, "SheetY"),
                "parts": parts,
            }
        )
    return nests


def used_nest_signature(project_path: Path) -> list[dict[str, Any]]:
    signature = []
    for nest in parse_rpd_nests(project_path):
        if int(nest.get("used", 0)) == 0:
            continue
        signature.append(
            {
                "id": nest["id"],
                "material": nest["material"],
                "thickness": nest["thickness"],
                "sheet_x": nest["sheet_x"],
                "sheet_y": nest["sheet_y"],
                "parts": nest["parts"],
            }
        )
    signature.sort(key=lambda row: int(row["id"]))
    return signature


def normalize_drg_text(text: str) -> str:
    text = TIMESTAMP_RE.sub("<TIMESTAMP>", text)
    text = LAB_JOB_RE.sub("F54410 PAINT PACK.<LABEL>", text)
    text = NEST_DIR_RE.sub("<NEST_DIR>", text)
    text = SYM_PATH_RE.sub(r"<SYM>/\g<name>", text)
    text = SLASH_PATH_RE.sub(r"<SYM>/\g<name>", text)
    return text


def extract_ddc_text(path: Path) -> str:
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError:
        return ""
    for node in root.iter():
        if _local_name(node) == "RadanFile" and node.attrib.get("extension", "").casefold() == "ddc":
            return node.text or ""
    return ""


def _ddc_record_prefix(line: str) -> str:
    match = DDC_RECORD_RE.match(line.strip())
    if not match:
        return ""
    return match.group("prefix")


def ddc_lines(path: Path) -> list[str]:
    text = extract_ddc_text(path)
    return [line.rstrip() for line in text.splitlines() if line.strip()]


def count_ddc_records(lines: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for line in lines:
        prefix = _ddc_record_prefix(line)
        if not prefix:
            continue
        counts[prefix] = counts.get(prefix, 0) + 1
    return dict(sorted(counts.items()))


def compare_ddc_lines(left_path: Path, right_path: Path) -> dict[str, Any]:
    left_lines = [normalize_drg_text(line) for line in ddc_lines(left_path)]
    right_lines = [normalize_drg_text(line) for line in ddc_lines(right_path)]
    changed_by_prefix: dict[str, int] = {}
    same = 0
    changed = 0
    max_len = max(len(left_lines), len(right_lines))
    first_changes: list[dict[str, Any]] = []
    for index in range(max_len):
        left = left_lines[index] if index < len(left_lines) else None
        right = right_lines[index] if index < len(right_lines) else None
        if left == right:
            same += 1
            continue
        changed += 1
        left_prefix = "" if left is None else _ddc_record_prefix(left)
        right_prefix = "" if right is None else _ddc_record_prefix(right)
        key = f"{left_prefix or '<none>'}->{right_prefix or '<none>'}"
        changed_by_prefix[key] = changed_by_prefix.get(key, 0) + 1
        if len(first_changes) < 8:
            first_changes.append(
                {
                    "index": index,
                    "left_prefix": left_prefix,
                    "right_prefix": right_prefix,
                    "left": left,
                    "right": right,
                }
            )
    return {
        "left_line_count": len(left_lines),
        "right_line_count": len(right_lines),
        "line_count_match": len(left_lines) == len(right_lines),
        "same_lines": same,
        "changed_lines": changed,
        "changed_by_prefix": dict(sorted(changed_by_prefix.items())),
        "first_changes": first_changes,
    }


def summarize_drg(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    text = data.decode("utf-8", errors="replace")
    normalized = normalize_drg_text(text)
    records = ddc_lines(path)
    contained = sorted(
        (
            {"name": name, "count": int(count)}
            for name, count in re.findall(r'<Symbol\s+name="([^"]+)"\s+count="(\d+)"', text)
        ),
        key=lambda row: (row["name"].casefold(), row["count"]),
    )
    sym_refs = sorted(set(_basename(match.group("name")) for match in SYM_PATH_RE.finditer(text)))
    return {
        "path": str(path),
        "filename": path.name,
        "nest_id": _nest_id_from_name(path.name),
        "size": len(data),
        "sha256": _sha256_bytes(data),
        "normalized_sha256": _sha256_text(normalized),
        "line_count": text.count("\n") + 1,
        "ddc_line_count": len(records),
        "ddc_record_counts": count_ddc_records(records),
        "contained_symbols": contained,
        "sym_refs": sym_refs,
    }


def summarize_gate_dir(gate_dir: Path, name: str) -> dict[str, Any]:
    result = load_gate_result(gate_dir)
    project_path = _find_rpd(gate_dir, result)
    drg_files = _find_drg_files(gate_dir, result)
    drgs = [summarize_drg(path) for path in drg_files]
    return {
        "name": name,
        "gate_dir": str(gate_dir),
        "ok": result.get("ok"),
        "lay_run_nest_return": result.get("lay_run_nest_return"),
        "part_count": result.get("part_count"),
        "after": result.get("after", {}),
        "project_path": str(project_path),
        "rpd_used_nests": used_nest_signature(project_path),
        "drg_count": len(drgs),
        "drgs": drgs,
    }


def _by_nest_id(drgs: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    return {int(row["nest_id"]): row for row in drgs if row.get("nest_id") is not None}


def _first_normalized_diff(left_path: Path, right_path: Path, *, max_lines: int = 80) -> list[str]:
    left = normalize_drg_text(left_path.read_text(encoding="utf-8", errors="replace")).splitlines()
    right = normalize_drg_text(right_path.read_text(encoding="utf-8", errors="replace")).splitlines()
    return list(difflib.unified_diff(left, right, fromfile=str(left_path), tofile=str(right_path), lineterm=""))[
        :max_lines
    ]


def compare_gate_dirs(left_dir: Path, right_dir: Path, *, left_name: str = "left", right_name: str = "right") -> dict[str, Any]:
    left = summarize_gate_dir(left_dir, left_name)
    right = summarize_gate_dir(right_dir, right_name)
    left_drgs = _by_nest_id(left["drgs"])
    right_drgs = _by_nest_id(right["drgs"])
    ids = sorted(set(left_drgs) | set(right_drgs))
    drg_rows = []
    first_diff: dict[str, Any] | None = None
    for nest_id in ids:
        left_row = left_drgs.get(nest_id)
        right_row = right_drgs.get(nest_id)
        row = {
            "nest_id": nest_id,
            "left_exists": left_row is not None,
            "right_exists": right_row is not None,
            "full_hash_match": bool(left_row and right_row and left_row["sha256"] == right_row["sha256"]),
            "normalized_hash_match": bool(
                left_row and right_row and left_row["normalized_sha256"] == right_row["normalized_sha256"]
            ),
            "contained_symbols_match": bool(
                left_row and right_row and left_row["contained_symbols"] == right_row["contained_symbols"]
            ),
            "ddc": None,
            "left_size": None if left_row is None else left_row["size"],
            "right_size": None if right_row is None else right_row["size"],
        }
        if left_row and right_row:
            row["ddc"] = compare_ddc_lines(Path(left_row["path"]), Path(right_row["path"]))
        if (
            first_diff is None
            and left_row
            and right_row
            and not row["normalized_hash_match"]
        ):
            first_diff = {
                "nest_id": nest_id,
                "diff": _first_normalized_diff(Path(left_row["path"]), Path(right_row["path"])),
            }
        drg_rows.append(row)

    ddc_changed_by_prefix: dict[str, int] = {}
    for row in drg_rows:
        ddc = row.get("ddc") or {}
        for key, value in ddc.get("changed_by_prefix", {}).items():
            ddc_changed_by_prefix[key] = ddc_changed_by_prefix.get(key, 0) + int(value)

    comparison = {
        "schema_version": 1,
        "left": left,
        "right": right,
        "rpd_used_nests_match": left["rpd_used_nests"] == right["rpd_used_nests"],
        "drg_count_match": left["drg_count"] == right["drg_count"],
        "drg_comparison": drg_rows,
        "drg_full_hash_matches": sum(1 for row in drg_rows if row["full_hash_match"]),
        "drg_normalized_hash_matches": sum(1 for row in drg_rows if row["normalized_hash_match"]),
        "drg_contained_symbols_matches": sum(1 for row in drg_rows if row["contained_symbols_match"]),
        "ddc_changed_by_prefix": dict(sorted(ddc_changed_by_prefix.items())),
        "ddc_changed_lines": sum(int((row.get("ddc") or {}).get("changed_lines", 0)) for row in drg_rows),
        "ddc_same_lines": sum(int((row.get("ddc") or {}).get("same_lines", 0)) for row in drg_rows),
        "first_normalized_diff": first_diff,
    }
    return comparison


def write_markdown_report(comparison: dict[str, Any], path: Path) -> None:
    left = comparison["left"]
    right = comparison["right"]
    rows = comparison["drg_comparison"]
    lines = [
        "# Nest Artifact Comparison",
        "",
        f"- Left: `{left['name']}`",
        f"- Right: `{right['name']}`",
        f"- Left dir: `{left['gate_dir']}`",
        f"- Right dir: `{right['gate_dir']}`",
        f"- RPD used-nest semantics match: `{comparison['rpd_used_nests_match']}`",
        f"- DRG count match: `{comparison['drg_count_match']}` (`{left['drg_count']}` vs `{right['drg_count']}`)",
        f"- Full DRG hash matches: `{comparison['drg_full_hash_matches']} / {len(rows)}`",
        f"- Normalized DRG hash matches: `{comparison['drg_normalized_hash_matches']} / {len(rows)}`",
        f"- Contained-symbol summaries match: `{comparison['drg_contained_symbols_matches']} / {len(rows)}`",
        f"- DDC changed lines: `{comparison['ddc_changed_lines']}`",
        f"- DDC same lines: `{comparison['ddc_same_lines']}`",
        "",
        "## DRG Rows",
        "",
        "| Nest | Full hash | Normalized hash | Contained symbols | DDC changed | Sizes |",
        "| ---: | --- | --- | --- | ---: | --- |",
    ]
    for row in rows:
        lines.append(
            "| `{nest_id}` | `{full}` | `{norm}` | `{symbols}` | `{changed}` | `{left_size}` / `{right_size}` |".format(
                nest_id=row["nest_id"],
                full=row["full_hash_match"],
                norm=row["normalized_hash_match"],
                symbols=row["contained_symbols_match"],
                changed=(row.get("ddc") or {}).get("changed_lines"),
                left_size=row["left_size"],
                right_size=row["right_size"],
            )
        )
    if comparison.get("ddc_changed_by_prefix"):
        lines.extend(["", "## DDC Changed By Prefix", ""])
        for key, count in comparison["ddc_changed_by_prefix"].items():
            lines.append(f"- `{key}`: `{count}`")
    first_diff = comparison.get("first_normalized_diff")
    if first_diff:
        lines.extend(
            [
                "",
                "## First Normalized Diff",
                "",
                f"Nest `{first_diff['nest_id']}`:",
                "",
                "```diff",
                *first_diff["diff"],
                "```",
            ]
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare two copied-project nester gate artifact folders.")
    parser.add_argument("--left-dir", type=Path, required=True)
    parser.add_argument("--right-dir", type=Path, required=True)
    parser.add_argument("--left-name", default="left")
    parser.add_argument("--right-name", default="right")
    parser.add_argument("--out-json", type=Path)
    parser.add_argument("--out-md", type=Path)
    args = parser.parse_args()

    comparison = compare_gate_dirs(
        args.left_dir.expanduser().resolve(),
        args.right_dir.expanduser().resolve(),
        left_name=args.left_name,
        right_name=args.right_name,
    )
    if args.out_json:
        args.out_json.parent.mkdir(parents=True, exist_ok=True)
        args.out_json.write_text(json.dumps(comparison, indent=2, sort_keys=True), encoding="utf-8")
    if args.out_md:
        args.out_md.parent.mkdir(parents=True, exist_ok=True)
        write_markdown_report(comparison, args.out_md)
    print(json.dumps(comparison, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
