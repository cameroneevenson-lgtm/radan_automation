from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


DEFAULT_XML_PATH = Path(r"C:\Program Files\Mazak\Mazak\bin\radraft.interop.xml")


def normalize_space(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value).strip()


def parse_member_name(raw_name: str) -> tuple[str, str, str]:
    kind, rest = raw_name.split(":", 1)
    rest = rest.strip()
    if "(" in rest:
        head, tail = rest.split("(", 1)
        namespace_part, _, member_name = head.rpartition(".")
        member_part = f"{member_name}({tail}"
    else:
        namespace_part, _, member_part = rest.rpartition(".")
    interface_name = namespace_part.split(".")[-1] if namespace_part else ""
    return kind, interface_name, member_part


def collect_members(xml_path: Path) -> list[dict[str, object]]:
    tree = ET.parse(xml_path)
    root = tree.getroot()
    result: list[dict[str, object]] = []

    for member in root.findall("./members/member"):
        raw_name = member.attrib.get("name")
        if not raw_name:
            continue

        kind, interface_name, member_part = parse_member_name(raw_name)
        params = []
        for param in member.findall("param"):
            params.append(
                {
                    "name": param.attrib.get("name", ""),
                    "text": normalize_space("".join(param.itertext())),
                }
            )

        result.append(
            {
                "raw_name": raw_name,
                "kind": kind,
                "interface": interface_name,
                "member": member_part,
                "summary": normalize_space("".join((member.findtext("summary") or ""))),
                "returns": normalize_space("".join((member.findtext("returns") or ""))),
                "remarks": normalize_space("".join((member.findtext("remarks") or ""))),
                "params": params,
            }
        )

    return result


def filter_members(
    members: list[dict[str, object]],
    interfaces: list[str],
    keywords: list[str],
    kinds: list[str],
) -> list[dict[str, object]]:
    interface_set = {item.lower() for item in interfaces}
    keyword_set = [item.lower() for item in keywords]
    kind_set = {item.upper() for item in kinds}

    filtered: list[dict[str, object]] = []
    for member in members:
        interface_name = str(member["interface"])
        if interface_set and interface_name.lower() not in interface_set:
            continue

        kind = str(member["kind"]).upper()
        if kind_set and kind not in kind_set:
            continue

        haystack_parts = [
            str(member["raw_name"]),
            str(member["member"]),
            str(member["summary"]),
            str(member["returns"]),
            str(member["remarks"]),
        ]
        for param in member["params"]:  # type: ignore[index]
            haystack_parts.append(str(param["name"]))
            haystack_parts.append(str(param["text"]))
        haystack = " ".join(haystack_parts).lower()
        if keyword_set and not all(keyword in haystack for keyword in keyword_set):
            continue

        filtered.append(member)

    return filtered


def format_markdown(members: list[dict[str, object]]) -> str:
    lines: list[str] = []
    for member in members:
        lines.append(f"- `{member['raw_name']}`")
        summary = str(member["summary"])
        if summary:
            lines.append(f"  summary: {summary}")
        returns = str(member["returns"])
        if returns:
            lines.append(f"  returns: {returns}")
        params = member["params"]  # type: ignore[assignment]
        for param in params:
            if param["text"]:
                lines.append(f"  param `{param['name']}`: {param['text']}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Search RADAN XML API docs.")
    parser.add_argument("--xml", type=Path, default=DEFAULT_XML_PATH, help="Path to the XML doc file.")
    parser.add_argument("--interface", action="append", default=[], help="Interface/type name filter, e.g. IMac.")
    parser.add_argument("--keyword", action="append", default=[], help="Case-insensitive keyword filter.")
    parser.add_argument("--kind", action="append", default=[], help="Member kind filter: T, M, P.")
    parser.add_argument("--limit", type=int, default=0, help="Optional maximum number of results.")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of markdown bullets.")
    args = parser.parse_args()

    members = collect_members(args.xml)
    filtered = filter_members(members, args.interface, args.keyword, args.kind)
    filtered.sort(key=lambda item: str(item["raw_name"]))

    if args.limit > 0:
        filtered = filtered[: args.limit]

    if args.json:
        print(json.dumps(filtered, indent=2))
    else:
        print(format_markdown(filtered))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
