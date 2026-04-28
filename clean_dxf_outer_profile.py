from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import ezdxf
from ezdxf import edgeminer, edgesmith

from path_safety import assert_w_drive_write_allowed


DEFAULT_LAYERS = ("IV_INTERIOR_PROFILES",)
DEFAULT_GAP_TOLERANCE = 1e-6
DEFAULT_SIMPLIFY_TOLERANCE = 0.003
DEFAULT_PREPROCESSED_DXF_DIR = "_preprocessed_dxfs"


@dataclass(frozen=True)
class Point2:
    x: float
    y: float

    def as_tuple(self) -> tuple[float, float]:
        return (self.x, self.y)


def _point2(value: Any) -> Point2:
    return Point2(float(value[0]), float(value[1]))


def _distance(left: Point2, right: Point2) -> float:
    return math.hypot(left.x - right.x, left.y - right.y)


@dataclass(frozen=True)
class LoopItem:
    entity: Any
    entity_type: str
    start: Point2
    end: Point2


def _signed_area(vertices: list[Point2]) -> float:
    if len(vertices) < 3:
        return 0.0
    total = 0.0
    for index, point in enumerate(vertices):
        next_point = vertices[(index + 1) % len(vertices)]
        total += point.x * next_point.y - next_point.x * point.y
    return total / 2.0


def _point_to_segment_distance(point: Point2, start: Point2, end: Point2) -> float:
    dx = end.x - start.x
    dy = end.y - start.y
    length_squared = dx * dx + dy * dy
    if length_squared == 0.0:
        return _distance(point, start)
    t = ((point.x - start.x) * dx + (point.y - start.y) * dy) / length_squared
    t = max(0.0, min(1.0, t))
    projection = Point2(start.x + t * dx, start.y + t * dy)
    return _distance(point, projection)


def _remove_duplicate_closure(vertices: Iterable[Point2], *, tolerance: float) -> list[Point2]:
    cleaned: list[Point2] = []
    for point in vertices:
        if cleaned and _distance(cleaned[-1], point) <= tolerance:
            continue
        cleaned.append(point)
    if len(cleaned) > 1 and _distance(cleaned[0], cleaned[-1]) <= tolerance:
        cleaned.pop()
    return cleaned


def _remove_duplicate_open(vertices: Iterable[Point2], *, tolerance: float) -> list[Point2]:
    cleaned: list[Point2] = []
    for point in vertices:
        if cleaned and _distance(cleaned[-1], point) <= tolerance:
            continue
        cleaned.append(point)
    return cleaned


def _point_to_polyline_distance(point: Point2, vertices: list[Point2]) -> float:
    if not vertices:
        return 0.0
    if len(vertices) == 1:
        return _distance(point, vertices[0])
    return min(
        _point_to_segment_distance(point, vertices[index], vertices[index + 1])
        for index in range(len(vertices) - 1)
    )


def simplify_closed_vertices(
    vertices: Iterable[Point2],
    *,
    tolerance: float,
    duplicate_tolerance: float = DEFAULT_GAP_TOLERANCE,
    min_vertices: int = 3,
) -> tuple[list[Point2], dict[str, Any]]:
    """Simplify a closed polygon by removing locally low-deviation vertices.

    This intentionally favors a bounded local interpolation over a global
    best-fit simplifier. It is meant for tiny flat-pattern artifacts such as
    bend-distortion stair steps, not for aggressive aesthetic smoothing.
    """

    original = _remove_duplicate_closure(vertices, tolerance=duplicate_tolerance)
    simplified = list(original)
    removed: list[dict[str, Any]] = []

    while len(simplified) > min_vertices:
        best_index: int | None = None
        best_distance = 0.0
        best_area = 0.0
        for index, point in enumerate(simplified):
            previous_point = simplified[index - 1]
            next_point = simplified[(index + 1) % len(simplified)]
            chord_length = _distance(previous_point, next_point)
            if chord_length <= duplicate_tolerance:
                distance = 0.0
            else:
                distance = _point_to_segment_distance(point, previous_point, next_point)
            if distance > tolerance:
                continue
            area = abs(
                (previous_point.x * (point.y - next_point.y))
                + (point.x * (next_point.y - previous_point.y))
                + (next_point.x * (previous_point.y - point.y))
            ) / 2.0
            if best_index is None or (area, distance) < (best_area, best_distance):
                best_index = index
                best_distance = distance
                best_area = area

        if best_index is None:
            break

        point = simplified.pop(best_index)
        removed.append(
            {
                "x": point.x,
                "y": point.y,
                "local_deviation": best_distance,
                "triangle_area": best_area,
            }
        )

    max_final_deviation = 0.0
    if simplified:
        for point in original:
            max_final_deviation = max(
                max_final_deviation,
                min(
                    _point_to_segment_distance(point, simplified[index], simplified[(index + 1) % len(simplified)])
                    for index in range(len(simplified))
                ),
            )

    before_area = _signed_area(original)
    after_area = _signed_area(simplified)
    stats = {
        "input_vertices": len(original),
        "output_vertices": len(simplified),
        "removed_vertices": len(removed),
        "tolerance": tolerance,
        "duplicate_tolerance": duplicate_tolerance,
        "max_removed_local_deviation": max((row["local_deviation"] for row in removed), default=0.0),
        "max_final_vertex_deviation": max_final_deviation,
        "area_before_abs": abs(before_area),
        "area_after_abs": abs(after_area),
        "area_delta": after_area - before_area,
        "area_delta_abs": abs(abs(after_area) - abs(before_area)),
        "removed": removed,
    }
    return simplified, stats


def simplify_open_vertices(
    vertices: Iterable[Point2],
    *,
    tolerance: float,
    duplicate_tolerance: float = DEFAULT_GAP_TOLERANCE,
    min_vertices: int = 2,
) -> tuple[list[Point2], dict[str, Any]]:
    """Simplify an open line chain while preserving both chain endpoints."""

    original = _remove_duplicate_open(vertices, tolerance=duplicate_tolerance)
    simplified = list(original)
    removed: list[dict[str, Any]] = []

    while len(simplified) > max(2, min_vertices):
        best_index: int | None = None
        best_distance = 0.0
        best_area = 0.0
        for index in range(1, len(simplified) - 1):
            previous_point = simplified[index - 1]
            point = simplified[index]
            next_point = simplified[index + 1]
            chord_length = _distance(previous_point, next_point)
            if chord_length <= duplicate_tolerance:
                distance = 0.0
            else:
                distance = _point_to_segment_distance(point, previous_point, next_point)
            if distance > tolerance:
                continue
            area = abs(
                (previous_point.x * (point.y - next_point.y))
                + (point.x * (next_point.y - previous_point.y))
                + (next_point.x * (previous_point.y - point.y))
            ) / 2.0
            if best_index is None or (area, distance) < (best_area, best_distance):
                best_index = index
                best_distance = distance
                best_area = area

        if best_index is None:
            break

        point = simplified.pop(best_index)
        removed.append(
            {
                "x": point.x,
                "y": point.y,
                "local_deviation": best_distance,
                "triangle_area": best_area,
            }
        )

    max_final_deviation = 0.0
    if simplified:
        for point in original:
            max_final_deviation = max(max_final_deviation, _point_to_polyline_distance(point, simplified))

    stats = {
        "input_vertices": len(original),
        "output_vertices": len(simplified),
        "removed_vertices": len(removed),
        "tolerance": tolerance,
        "duplicate_tolerance": duplicate_tolerance,
        "max_removed_local_deviation": max((row["local_deviation"] for row in removed), default=0.0),
        "max_final_vertex_deviation": max_final_deviation,
        "removed": removed,
    }
    return simplified, stats


def _profile_entities(doc: Any, layers: set[str]) -> list[Any]:
    return [entity for entity in doc.modelspace() if str(entity.dxf.layer) in layers]


def _outside_loop(profile_entities: list[Any], *, gap_tolerance: float) -> tuple[list[Any], list[Any]]:
    edge_entities = list(edgesmith.filter_open_edges(profile_entities))
    edges = list(edgesmith.edges_from_entities_2d(edge_entities, gap_tol=gap_tolerance))
    deposit = edgeminer.Deposit(edges, gap_tol=gap_tolerance)
    loops = list(edgeminer.find_all_loops(deposit))
    if not loops:
        raise RuntimeError("No closed outside/profile loop found.")
    outside = max(loops, key=lambda loop: abs(edgesmith.loop_area(loop, gap_tol=gap_tolerance)))
    return loops, list(outside)


def _loop_vertices(loop: list[Any], *, gap_tolerance: float) -> list[Point2]:
    vertices = [_point2(vertex) for vertex in edgesmith.chain_vertices(loop, gap_tol=gap_tolerance)]
    return _remove_duplicate_closure(vertices, tolerance=gap_tolerance)


def _loop_items(loop: list[Any]) -> list[LoopItem]:
    return [
        LoopItem(
            entity=edge.payload,
            entity_type=str(edge.payload.dxftype()),
            start=_point2(edge.start),
            end=_point2(edge.end),
        )
        for edge in loop
        if edge.payload is not None
    ]


def _cyclic_line_runs(items: list[LoopItem]) -> list[list[int]]:
    if not items:
        return []
    if all(item.entity_type == "LINE" for item in items):
        return [list(range(len(items)))]

    runs: list[list[int]] = []
    count = len(items)
    for index, item in enumerate(items):
        if item.entity_type != "LINE" or items[index - 1].entity_type == "LINE":
            continue
        run: list[int] = []
        cursor = index
        while items[cursor].entity_type == "LINE":
            run.append(cursor)
            cursor = (cursor + 1) % count
            if cursor == index:
                break
        runs.append(run)
    return runs


def _line_dxfattribs(entity: Any) -> dict[str, Any]:
    return {"layer": str(entity.dxf.layer)}


def _rewrite_line_run(
    *,
    modelspace: Any,
    items: list[LoopItem],
    run: list[int],
    tolerance: float,
    gap_tolerance: float,
) -> dict[str, Any]:
    vertices = [items[run[0]].start]
    vertices.extend(items[index].end for index in run)
    simplified, stats = simplify_open_vertices(
        vertices,
        tolerance=tolerance,
        duplicate_tolerance=gap_tolerance,
        min_vertices=2,
    )
    stats["line_count_before"] = len(run)
    stats["line_count_after"] = max(0, len(simplified) - 1)
    stats["rewritten"] = False
    if int(stats["removed_vertices"]) <= 0:
        return stats

    attributes = _line_dxfattribs(items[run[0]].entity)
    for index in run:
        modelspace.delete_entity(items[index].entity)
    for index, start in enumerate(simplified[:-1]):
        end = simplified[index + 1]
        if _distance(start, end) <= gap_tolerance:
            continue
        modelspace.add_line(
            (start.x, start.y, 0.0),
            (end.x, end.y, 0.0),
            dxfattribs=attributes,
        )
    stats["rewritten"] = True
    return stats


def _simplify_mixed_line_runs(
    *,
    doc: Any,
    outside: list[Any],
    tolerance: float,
    gap_tolerance: float,
) -> dict[str, Any]:
    items = _loop_items(outside)
    line_runs = [run for run in _cyclic_line_runs(items) if run and len(run) > 1]
    modelspace = doc.modelspace()
    run_stats = [
        _rewrite_line_run(
            modelspace=modelspace,
            items=items,
            run=run,
            tolerance=tolerance,
            gap_tolerance=gap_tolerance,
        )
        for run in line_runs
    ]
    removed_vertices = sum(int(stats.get("removed_vertices", 0) or 0) for stats in run_stats)
    input_vertices = sum(int(stats.get("input_vertices", 0) or 0) for stats in run_stats)
    output_vertices = sum(int(stats.get("output_vertices", 0) or 0) for stats in run_stats)
    line_count_before = sum(1 for item in items if item.entity_type == "LINE")
    line_count_delta = sum(
        int(stats.get("line_count_before", 0) or 0) - int(stats.get("line_count_after", 0) or 0)
        for stats in run_stats
        if bool(stats.get("rewritten"))
    )
    return {
        "mode": "arc_preserving_mixed_line_cleanup",
        "input_vertices": input_vertices,
        "output_vertices": output_vertices,
        "removed_vertices": removed_vertices,
        "line_run_count": len(line_runs),
        "rewritten_line_run_count": sum(1 for stats in run_stats if bool(stats.get("rewritten"))),
        "arc_count": sum(1 for item in items if item.entity_type == "ARC"),
        "line_count_before": line_count_before,
        "line_count_after": line_count_before - line_count_delta,
        "max_removed_local_deviation": max(
            (float(stats.get("max_removed_local_deviation", 0.0) or 0.0) for stats in run_stats),
            default=0.0,
        ),
        "max_final_vertex_deviation": max(
            (float(stats.get("max_final_vertex_deviation", 0.0) or 0.0) for stats in run_stats),
            default=0.0,
        ),
        "runs": run_stats,
    }


def _tolerance_tag(tolerance: float) -> str:
    text = f"{float(tolerance):.6f}".rstrip("0").rstrip(".")
    if text.startswith("0."):
        text = text[2:]
    return "tol" + (text.replace(".", "p") or "0")


def preprocessed_output_paths(
    *,
    dxf_path: Path,
    project_folder: Path,
    tolerance: float,
) -> tuple[Path, Path]:
    stem = Path(dxf_path).stem
    tag = _tolerance_tag(tolerance)
    root = Path(project_folder) / DEFAULT_PREPROCESSED_DXF_DIR
    cleaned_dxf = root / f"{stem}_outer_cleaned_{tag}.dxf"
    report = root / f"{stem}_outer_cleaned_{tag}.report.json"
    return cleaned_dxf, report


def clean_outer_profile(
    *,
    dxf_path: Path,
    out_path: Path | None = None,
    report_path: Path | None = None,
    project_folder: Path | None = None,
    layers: Iterable[str] = DEFAULT_LAYERS,
    simplify_tolerance: float = DEFAULT_SIMPLIFY_TOLERANCE,
    gap_tolerance: float = DEFAULT_GAP_TOLERANCE,
    min_vertices: int = 3,
) -> dict[str, Any]:
    if project_folder is not None and out_path is None:
        out_path, default_report_path = preprocessed_output_paths(
            dxf_path=dxf_path,
            project_folder=project_folder,
            tolerance=simplify_tolerance,
        )
        if report_path is None:
            report_path = default_report_path
    assert_w_drive_write_allowed(out_path, operation="write cleaned DXF")
    assert_w_drive_write_allowed(report_path, operation="write DXF cleaning report")

    doc = ezdxf.readfile(dxf_path)
    layer_set = {str(layer) for layer in layers}
    profile_entities = _profile_entities(doc, layer_set)
    loops, outside = _outside_loop(profile_entities, gap_tolerance=gap_tolerance)
    outside_payloads = [edge.payload for edge in outside if edge.payload is not None]
    outside_types = sorted({str(entity.dxftype()) for entity in outside_payloads})
    vertices = _loop_vertices(outside, gap_tolerance=gap_tolerance)

    payload = {
        "dxf_path": str(dxf_path),
        "out_path": None if out_path is None else str(out_path),
        "project_folder": None if project_folder is None else str(project_folder),
        "preprocessed_folder": None if out_path is None else str(out_path.parent),
        "layers": sorted(layer_set),
        "profile_entity_count": len(profile_entities),
        "loop_count": len(loops),
        "selected_outside_entity_count": len(outside),
        "selected_outside_entity_types": outside_types,
        "wrote_output": False,
        "skipped_write_reason": None,
    }

    if outside_types == ["LINE"]:
        simplified, stats = simplify_closed_vertices(
            vertices,
            tolerance=float(simplify_tolerance),
            duplicate_tolerance=float(gap_tolerance),
            min_vertices=int(min_vertices),
        )
        payload["simplification"] = stats
        if out_path is not None:
            modelspace = doc.modelspace()
            layer = str(outside_payloads[0].dxf.layer) if outside_payloads else next(iter(layer_set))
            for entity in outside_payloads:
                modelspace.delete_entity(entity)

            for index, start in enumerate(simplified):
                end = simplified[(index + 1) % len(simplified)]
                modelspace.add_line(
                    (start.x, start.y, 0.0),
                    (end.x, end.y, 0.0),
                    dxfattribs={"layer": layer},
                )
            out_path.parent.mkdir(parents=True, exist_ok=True)
            doc.saveas(out_path)
            payload["wrote_output"] = True
    elif set(outside_types).issubset({"ARC", "LINE"}):
        payload["simplification"] = _simplify_mixed_line_runs(
            doc=doc,
            outside=outside,
            tolerance=float(simplify_tolerance),
            gap_tolerance=float(gap_tolerance),
        )
        if out_path is not None:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            doc.saveas(out_path)
            payload["wrote_output"] = True
    else:
        payload["skipped_write_reason"] = (
            "The selected outside loop contains unsupported entity types for arc-preserving line cleanup."
        )
        payload["simplification"] = {
            "input_vertices": len(vertices),
            "output_vertices": len(vertices),
            "removed_vertices": 0,
        }

    if report_path is not None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Lab-only cleaner for the outside DXF profile loop.")
    parser.add_argument("--dxf", type=Path, required=True, help="Input DXF path.")
    parser.add_argument("--out", type=Path, help="Optional cleaned DXF output path. Omit for report-only dry run.")
    parser.add_argument("--report", type=Path, help="Optional JSON report path.")
    parser.add_argument(
        "--project-folder",
        type=Path,
        help=f"L-side project folder. Writes under its {DEFAULT_PREPROCESSED_DXF_DIR} subfolder.",
    )
    parser.add_argument("--layer", action="append", help="Profile layer to consider. Defaults to IV_INTERIOR_PROFILES.")
    parser.add_argument("--tolerance", type=float, default=DEFAULT_SIMPLIFY_TOLERANCE, help="Max local deviation in drawing units.")
    parser.add_argument("--gap-tolerance", type=float, default=DEFAULT_GAP_TOLERANCE, help="Endpoint connection tolerance.")
    parser.add_argument("--min-vertices", type=int, default=3, help="Minimum vertices to keep in the outside loop.")
    args = parser.parse_args()
    if args.out is not None and args.project_folder is not None:
        parser.error("Use either --out or --project-folder, not both.")

    payload = clean_outer_profile(
        dxf_path=args.dxf,
        out_path=args.out,
        report_path=args.report,
        project_folder=args.project_folder,
        layers=args.layer or DEFAULT_LAYERS,
        simplify_tolerance=args.tolerance,
        gap_tolerance=args.gap_tolerance,
        min_vertices=args.min_vertices,
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
