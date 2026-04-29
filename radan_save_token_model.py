from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from ddc_corpus import read_ddc_records, read_dxf_entities
from ddc_number_codec import decode_ddc_number_fraction
from evaluate_exported_coordinate_token_model import slot_role, value_key

MODEL_SOURCES = (
    "type_role_value_before_token",
    "type_role_before_token",
    "role_before_token",
    "before_token",
)


def _token_at(row: dict[str, Any], slot: int) -> str:
    tokens = list(row.get("tokens") or [])
    return str(tokens[slot]) if slot < len(tokens) else ""


def _decoded_close(left: str, right: str, *, tolerance: float) -> bool:
    try:
        return abs(float(decode_ddc_number_fraction(left) - decode_ddc_number_fraction(right))) <= tolerance
    except Exception:
        return False


def _slot_visible_values(dxf_row: dict[str, Any], *, value_digits: int) -> dict[int, str]:
    entity_type = str(dxf_row["type"])
    if entity_type == "LINE":
        start = [float(value) for value in dxf_row["normalized_start"]]
        end = [float(value) for value in dxf_row["normalized_end"]]
        return {
            0: value_key(start[0], digits=value_digits),
            1: value_key(start[1], digits=value_digits),
            2: value_key(end[0] - start[0], digits=value_digits),
            3: value_key(end[1] - start[1], digits=value_digits),
        }
    if entity_type == "ARC":
        start = [float(value) for value in dxf_row["normalized_start_point"]]
        end = [float(value) for value in dxf_row["normalized_end_point"]]
        center = [float(value) for value in dxf_row["normalized_center"]]
        return {
            0: value_key(start[0], digits=value_digits),
            1: value_key(start[1], digits=value_digits),
            2: value_key(end[0] - start[0], digits=value_digits),
            3: value_key(end[1] - start[1], digits=value_digits),
            4: value_key(center[0] - start[0], digits=value_digits),
            5: value_key(center[1] - start[1], digits=value_digits),
            6: value_key(1.0, digits=value_digits),
            9: value_key(1.0, digits=value_digits),
        }
    if entity_type == "CIRCLE":
        center = [float(value) for value in dxf_row["normalized_center"]]
        radius = float(dxf_row["radius"])
        return {
            0: value_key(center[0] + radius, digits=value_digits),
            1: value_key(center[1], digits=value_digits),
            4: value_key(-radius, digits=value_digits),
            5: value_key(0.0, digits=value_digits),
            6: value_key(1.0, digits=value_digits),
            9: value_key(1.0, digits=value_digits),
        }
    return {}


def _lookup_key(row: dict[str, Any], source: str) -> tuple[Any, ...]:
    if source == "type_role_value_before_token":
        return (row["dxf_type"], row["role"], row["visible_value_key"], row["before_token"])
    if source == "type_role_before_token":
        return (row["dxf_type"], row["role"], row["before_token"])
    if source == "role_before_token":
        return (row["role"], row["before_token"])
    if source == "before_token":
        return (row["before_token"],)
    raise ValueError(f"Unsupported RADAN save token model source: {source}")


def _record_sequence(rows: list[dict[str, Any]]) -> list[str]:
    return [str(row.get("record", "")) for row in rows]


def _after_matches_oracle(
    after_rows: list[dict[str, Any]],
    oracle_rows: list[dict[str, Any]],
    *,
    decoded_tolerance: float,
) -> bool:
    for after_row, oracle_row in zip(after_rows, oracle_rows):
        slot_count = max(len(after_row.get("tokens") or []), len(oracle_row.get("tokens") or []))
        for slot in range(slot_count):
            if not _decoded_close(
                _token_at(after_row, slot),
                _token_at(oracle_row, slot),
                tolerance=decoded_tolerance,
            ):
                return False
    return True


def build_radan_save_token_model(
    *,
    dxf_folder: Path,
    before_folder: Path,
    after_folder: Path,
    oracle_folder: Path,
    value_digits: int = 6,
    decoded_tolerance: float = 1e-12,
) -> dict[str, Any]:
    dxf_by_part = {path.stem.casefold(): path for path in Path(dxf_folder).glob("*.dxf")}
    before_by_part = {path.stem.casefold(): path for path in Path(before_folder).glob("*.sym")}
    after_by_part = {path.stem.casefold(): path for path in Path(after_folder).glob("*.sym")}
    oracle_by_part = {path.stem.casefold(): path for path in Path(oracle_folder).glob("*.sym")}
    requested = sorted(set(dxf_by_part) & set(before_by_part) & set(after_by_part) & set(oracle_by_part))

    observations: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    eligible_parts: list[str] = []
    for key in requested:
        dxf_path = dxf_by_part[key]
        before_path = before_by_part[key]
        after_path = after_by_part[key]
        oracle_path = oracle_by_part[key]
        dxf_rows, _bounds = read_dxf_entities(dxf_path)
        before_rows = read_ddc_records(before_path)
        after_rows = read_ddc_records(after_path)
        oracle_rows = read_ddc_records(oracle_path)
        if not (len(dxf_rows) == len(before_rows) == len(after_rows) == len(oracle_rows)):
            skipped.append({"part": dxf_path.stem, "reason": "count_mismatch"})
            continue
        if not (
            _record_sequence(before_rows) == _record_sequence(after_rows) == _record_sequence(oracle_rows)
        ):
            skipped.append({"part": dxf_path.stem, "reason": "record_sequence_mismatch"})
            continue
        if not _after_matches_oracle(after_rows, oracle_rows, decoded_tolerance=decoded_tolerance):
            skipped.append({"part": dxf_path.stem, "reason": "after_not_decoded_close_to_oracle"})
            continue
        eligible_parts.append(dxf_path.stem)

        for row_index, (dxf_row, before_row, after_row, oracle_row) in enumerate(
            zip(dxf_rows, before_rows, after_rows, oracle_rows),
            start=1,
        ):
            entity_type = str(dxf_row["type"])
            visible_values = _slot_visible_values(dxf_row, value_digits=int(value_digits))
            slot_count = max(
                len(before_row.get("tokens") or []),
                len(after_row.get("tokens") or []),
                len(oracle_row.get("tokens") or []),
            )
            for slot in range(slot_count):
                before_token = _token_at(before_row, slot)
                after_token = _token_at(after_row, slot)
                oracle_token = _token_at(oracle_row, slot)
                if before_token == oracle_token or after_token != oracle_token:
                    continue
                observations.append(
                    {
                        "part": dxf_path.stem,
                        "row_index": row_index,
                        "dxf_type": entity_type,
                        "role": slot_role(entity_type, slot),
                        "slot": slot,
                        "visible_value_key": visible_values.get(slot, ""),
                        "before_token": before_token,
                        "target_token": oracle_token,
                    }
                )

    lookup: dict[str, dict[tuple[Any, ...], list[tuple[str, str]]]] = {source: {} for source in MODEL_SOURCES}
    for row in observations:
        for source in MODEL_SOURCES:
            lookup[source].setdefault(_lookup_key(row, source), []).append((str(row["part"]), row["target_token"]))

    return {
        "schema_version": 1,
        "dxf_folder": str(dxf_folder),
        "before_folder": str(before_folder),
        "after_folder": str(after_folder),
        "oracle_folder": str(oracle_folder),
        "value_digits": int(value_digits),
        "decoded_tolerance": float(decoded_tolerance),
        "eligible_parts": eligible_parts,
        "eligible_part_count": len(eligible_parts),
        "skipped": skipped,
        "observations": observations,
        "observation_count": len(observations),
        "lookup": lookup,
    }


def choose_radan_save_canonical_token(
    *,
    model: dict[str, Any] | None,
    mode: str,
    target_part: str,
    dxf_type: str,
    role: str,
    visible_value_key: str,
    before_token: str,
    token_source: str,
) -> tuple[str, str]:
    if model is None or mode == "off":
        return before_token, ""
    if not str(token_source).startswith("encoded_fraction_fallback"):
        return before_token, ""

    min_count = 1
    min_confidence = 1.0
    sources: tuple[str, ...]
    shorten_only = False
    if mode == "fallback-context-unanimous":
        sources = ("type_role_value_before_token", "type_role_before_token")
    elif mode == "fallback-token-majority":
        sources = ("before_token",)
        min_confidence = 0.67
    elif mode == "fallback-shorter-majority":
        sources = ("before_token",)
        min_confidence = 0.67
        shorten_only = True
    else:
        raise ValueError(f"Unsupported RADAN save token canonicalization mode: {mode}")

    row = {
        "dxf_type": dxf_type,
        "role": role,
        "visible_value_key": visible_value_key,
        "before_token": before_token,
    }
    for source in sources:
        entries = model.get("lookup", {}).get(source, {}).get(_lookup_key(row, source), [])
        candidates = [token for part, token in entries if str(part) != target_part]
        if len(candidates) < min_count:
            continue
        token, count = Counter(candidates).most_common(1)[0]
        if count / len(candidates) < min_confidence:
            continue
        if shorten_only and len(token) >= len(before_token):
            continue
        if not _decoded_close(before_token, token, tolerance=float(model.get("decoded_tolerance", 1e-12))):
            continue
        return str(token), f"radan_save_token:{mode}:{source}:{count}/{len(candidates)}"
    return before_token, ""
