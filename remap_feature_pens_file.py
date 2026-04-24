from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from collections import Counter
from pathlib import Path
import re
import shutil
from typing import Any


DDC_BLOCK_RE = re.compile(
    r'(<RadanFile\s+extension="ddc"\s*>\s*<!\[CDATA\[)(.*?)(\]\]>\s*</RadanFile>)',
    re.DOTALL,
)


def _split_newline(line: str) -> tuple[str, str]:
    if line.endswith("\r\n"):
        return line[:-2], "\r\n"
    if line.endswith("\n") or line.endswith("\r"):
        return line[:-1], line[-1]
    return line, ""


def _count_records(ddc_text: str, line_record: str, arc_record: str) -> dict[str, dict[str, Any]]:
    counters: dict[str, Counter[str]] = {
        "l": Counter(),
        "a": Counter(),
    }
    for raw_line in ddc_text.splitlines():
        parts = raw_line.split(",")
        if len(parts) <= 8:
            continue
        if parts[0] == line_record:
            counters["l"][parts[8]] += 1
        elif parts[0] == arc_record:
            counters["a"][parts[8]] += 1
    return {
        key: {
            "count": sum(counter.values()),
            "pens": {pen: count for pen, count in sorted(counter.items(), key=lambda item: item[0])},
        }
        for key, counter in counters.items()
    }


def _rewrite_ddc(
    ddc_text: str,
    *,
    source_pen: int,
    target_pen: int,
    arc_target_pen: int,
    line_record: str,
    arc_record: str,
) -> tuple[str, dict[str, int]]:
    source = str(int(source_pen))
    line_target = str(int(target_pen))
    arc_target = str(int(arc_target_pen))
    changed = {"l": 0, "a": 0}

    rewritten_lines: list[str] = []
    for line in ddc_text.splitlines(keepends=True):
        body, newline = _split_newline(line)
        parts = body.split(",")
        if len(parts) > 8 and parts[8] == source:
            if parts[0] == line_record:
                parts[8] = line_target
                changed["l"] += 1
            elif parts[0] == arc_record:
                parts[8] = arc_target
                changed["a"] += 1
        rewritten_lines.append(",".join(parts) + newline)
    return "".join(rewritten_lines), changed


def remap_file(
    path: Path,
    *,
    source_pen: int = 7,
    target_pen: int = 5,
    arc_target_pen: int = 9,
    line_record: str = "G",
    arc_record: str = "H",
    dry_run: bool = False,
    backup_suffix: str | None = None,
) -> dict[str, Any]:
    path = path.expanduser().resolve()
    with path.open("r", encoding="utf-8", newline="") as handle:
        text = handle.read()
    match = DDC_BLOCK_RE.search(text)
    if match is None:
        raise RuntimeError(f"No DDC RadanFile CDATA block found in {path}.")

    ddc_text = match.group(2)
    before = _count_records(ddc_text, line_record, arc_record)
    rewritten_ddc, changed = _rewrite_ddc(
        ddc_text,
        source_pen=source_pen,
        target_pen=target_pen,
        arc_target_pen=arc_target_pen,
        line_record=line_record,
        arc_record=arc_record,
    )
    after = _count_records(rewritten_ddc, line_record, arc_record)
    changed_total = sum(changed.values())

    result: dict[str, Any] = {
        "path": str(path),
        "dry_run": bool(dry_run),
        "source_pen": int(source_pen),
        "target_pen": int(target_pen),
        "arc_target_pen": int(arc_target_pen),
        "before": before,
        "after": after,
        "changed": changed,
        "changed_total": changed_total,
        "backup_path": None,
        "write_ok": False,
        "requires_radan_resave": changed_total > 0,
        "refresh_note": (
            "Direct DDC edits do not refresh RADAN-derived Nest warnings, cached thumbnails, or file metadata. "
            "Open and save the symbol in RADAN after a write when those derived views need to update; "
            "do not spoof Workflow status by direct XML edit."
            if changed_total > 0
            else None
        ),
    }

    if dry_run:
        return result

    if changed_total == 0:
        result["write_ok"] = True
        return result

    if backup_suffix is not None:
        backup_path = path.with_name(f"{path.name}{backup_suffix}")
        shutil.copy2(path, backup_path)
        result["backup_path"] = str(backup_path)

    new_text = text[: match.start(2)] + rewritten_ddc + text[match.end(2) :]
    temp_path = path.with_name(f"{path.name}.tmp-{os.getpid()}")
    with temp_path.open("w", encoding="utf-8", newline="") as handle:
        handle.write(new_text)
    os.replace(temp_path, path)
    result["write_ok"] = True
    return result


def _default_backup_suffix() -> str:
    stamp = dt.datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    return f".bak-{stamp}"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Remap line and arc pen numbers directly inside RADAN .sym DDC XML without opening RADAN.",
    )
    parser.add_argument("path", nargs="+", help="RADAN .sym file path(s) to update.")
    parser.add_argument("--source-pen", type=int, default=7)
    parser.add_argument("--target-pen", type=int, default=5)
    parser.add_argument("--arc-target-pen", type=int, default=9)
    parser.add_argument("--line-record", default="G", help="DDC record token used for lines. Defaults to G.")
    parser.add_argument("--arc-record", default="H", help="DDC record token used for arcs. Defaults to H.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-backup", action="store_true")
    args = parser.parse_args()

    backup_suffix = None if args.dry_run or args.no_backup else _default_backup_suffix()
    results = [
        remap_file(
            Path(raw_path),
            source_pen=args.source_pen,
            target_pen=args.target_pen,
            arc_target_pen=args.arc_target_pen,
            line_record=args.line_record,
            arc_record=args.arc_record,
            dry_run=args.dry_run,
            backup_suffix=backup_suffix,
        )
        for raw_path in args.path
    ]
    print(json.dumps({"results": results}, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
