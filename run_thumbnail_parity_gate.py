from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageStat

from copied_project_nester_gate import assert_lab_output_path, list_radan_processes, terminate_processes
from radan_com import open_application
from radan_utils import _summarize_license_info


DEFAULT_CANARIES = (
    "B-14",
    "B-17",
    "B-27",
    "B-30",
    "F54410-B-49",
    "F54410-B-12",
    "F54410-B-27",
)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    assert_lab_output_path(path, operation="write thumbnail gate JSON")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def compare_images(candidate_png: Path, oracle_png: Path) -> dict[str, Any]:
    with Image.open(candidate_png) as candidate_image:
        candidate = candidate_image.convert("RGBA")
    with Image.open(oracle_png) as oracle_image:
        oracle = oracle_image.convert("RGBA")
    same_size = candidate.size == oracle.size
    result: dict[str, Any] = {
        "candidate_png": str(candidate_png),
        "oracle_png": str(oracle_png),
        "size": list(candidate.size),
        "oracle_size": list(oracle.size),
        "same_size": same_size,
        "ok": False,
        "exact_pixel_match": False,
        "diff_bbox": None,
        "diff_pixels": None,
        "diff_pixel_pct": None,
        "mean_abs_rgba": None,
        "max_channel_diff": None,
    }
    if not same_size:
        return result
    diff = ImageChops.difference(candidate, oracle)
    bbox = diff.getbbox()
    stat = ImageStat.Stat(diff)
    pixel_data = diff.get_flattened_data() if hasattr(diff, "get_flattened_data") else diff.getdata()
    diff_pixels = sum(1 for pixel in pixel_data if pixel != (0, 0, 0, 0))
    total_pixels = candidate.size[0] * candidate.size[1]
    result.update(
        {
            "ok": bbox is None,
            "exact_pixel_match": bbox is None,
            "diff_bbox": None if bbox is None else list(bbox),
            "diff_pixels": diff_pixels,
            "diff_pixel_pct": diff_pixels / total_pixels if total_pixels else 0.0,
            "mean_abs_rgba": [float(value) for value in stat.mean],
            "max_channel_diff": [int(channel_max) for _channel_min, channel_max in stat.extrema],
        }
    )
    return result


def render_thumbnail(
    *,
    input_path: Path,
    thumbnail_path: Path,
    backend: str | None,
    width: int,
    height: int,
    kill_existing_radan: bool,
) -> dict[str, Any]:
    assert_lab_output_path(thumbnail_path, operation="write RADAN thumbnail")
    thumbnail_path.parent.mkdir(parents=True, exist_ok=True)
    preflight_processes = list_radan_processes()
    cleanup_before = terminate_processes(preflight_processes) if kill_existing_radan else None
    payload: dict[str, Any] = {
        "input_path": str(input_path),
        "thumbnail_path": str(thumbnail_path),
        "width": width,
        "height": height,
        "process_preflight": preflight_processes,
        "process_cleanup_before": cleanup_before,
    }
    app = None
    quit_attempted = False
    try:
        app = open_application(backend=backend, force_new_instance=True)
        info = app.info()
        payload["backend"] = app.backend_name
        payload["created_new_instance"] = app.created_new_instance
        payload["process_id"] = info.process_id
        payload["software_version"] = info.software_version
        payload["license_info"] = _summarize_license_info(app.mac.license_info())
        app.visible = False
        try:
            app.interactive = False
        except Exception:
            pass
        app.open_document(str(input_path), read_only=True)
        app.visible = False
        payload["document_after_open"] = None if app.active_document_info() is None else app.active_document_info().__dict__
        payload["thumbnail_ok"] = app.mac.flat_thumbnail(str(thumbnail_path), width, height)
        payload["thumbnail_exists"] = thumbnail_path.exists()
        payload["thumbnail_size"] = thumbnail_path.stat().st_size if thumbnail_path.exists() else 0
        app.close_active_document(True)
        payload["quit_result"] = app.quit()
        quit_attempted = True
        payload["ok"] = bool(payload["thumbnail_ok"]) and thumbnail_path.exists()
    except Exception as exc:
        payload["ok"] = False
        payload["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        if app is not None and not quit_attempted:
            try:
                app.quit()
            except Exception:
                pass
            try:
                app.close()
            except Exception:
                pass
        payload["process_cleanup_after_quit"] = terminate_processes(list_radan_processes())
        payload["process_final"] = list_radan_processes()
    return payload


def run_gate(
    *,
    candidate_symbol_folder: Path,
    oracle_symbol_folder: Path,
    out_dir: Path,
    parts: list[str],
    backend: str | None = None,
    width: int = 900,
    height: int = 700,
    kill_existing_radan: bool = False,
) -> dict[str, Any]:
    assert_lab_output_path(out_dir, operation="write thumbnail parity gate")
    out_dir.mkdir(parents=True, exist_ok=True)
    candidate_dir = out_dir / "candidate_thumbnails"
    oracle_dir = out_dir / "oracle_thumbnails"
    comparisons: list[dict[str, Any]] = []
    renders: list[dict[str, Any]] = []
    for part in parts:
        candidate_sym = candidate_symbol_folder / f"{part}.sym"
        oracle_sym = oracle_symbol_folder / f"{part}.sym"
        if not candidate_sym.exists():
            comparisons.append({"part": part, "ok": False, "error": f"Missing candidate symbol: {candidate_sym}"})
            continue
        if not oracle_sym.exists():
            comparisons.append({"part": part, "ok": False, "error": f"Missing oracle symbol: {oracle_sym}"})
            continue
        candidate_png = candidate_dir / f"{part}.png"
        oracle_png = oracle_dir / f"{part}.png"
        candidate_render = render_thumbnail(
            input_path=candidate_sym,
            thumbnail_path=candidate_png,
            backend=backend,
            width=width,
            height=height,
            kill_existing_radan=kill_existing_radan,
        )
        oracle_render = render_thumbnail(
            input_path=oracle_sym,
            thumbnail_path=oracle_png,
            backend=backend,
            width=width,
            height=height,
            kill_existing_radan=kill_existing_radan,
        )
        renders.extend(
            [
                {"part": part, "kind": "candidate", **candidate_render},
                {"part": part, "kind": "oracle", **oracle_render},
            ]
        )
        if candidate_render.get("ok") and oracle_render.get("ok"):
            comparison = {"part": part, **compare_images(candidate_png, oracle_png)}
        else:
            comparison = {
                "part": part,
                "ok": False,
                "candidate_render_ok": candidate_render.get("ok"),
                "oracle_render_ok": oracle_render.get("ok"),
            }
        comparisons.append(comparison)

    payload = {
        "schema_version": 1,
        "candidate_symbol_folder": str(candidate_symbol_folder),
        "oracle_symbol_folder": str(oracle_symbol_folder),
        "out_dir": str(out_dir),
        "parts": list(parts),
        "width": width,
        "height": height,
        "renders": renders,
        "comparisons": comparisons,
        "ok": bool(comparisons) and all(bool(row.get("ok")) for row in comparisons),
        "exact_pixel_match_count": sum(1 for row in comparisons if row.get("exact_pixel_match")),
        "part_count": len(comparisons),
    }
    _write_json(out_dir / "thumbnail_parity_result.json", payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Render and pixel-compare lab-only RADAN symbol thumbnails.")
    parser.add_argument("--candidate-symbol-folder", type=Path, required=True)
    parser.add_argument("--oracle-symbol-folder", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--part", action="append", default=[])
    parser.add_argument("--backend", default=None)
    parser.add_argument("--width", type=int, default=900)
    parser.add_argument("--height", type=int, default=700)
    parser.add_argument("--kill-existing-radan", action="store_true")
    args = parser.parse_args()

    parts = args.part or list(DEFAULT_CANARIES)
    payload = run_gate(
        candidate_symbol_folder=args.candidate_symbol_folder.expanduser().resolve(),
        oracle_symbol_folder=args.oracle_symbol_folder.expanduser().resolve(),
        out_dir=args.out_dir.expanduser().resolve(),
        parts=parts,
        backend=args.backend,
        width=int(args.width),
        height=int(args.height),
        kill_existing_radan=bool(args.kill_existing_radan),
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
