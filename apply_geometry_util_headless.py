from __future__ import annotations

import argparse
import json
from pathlib import Path

from radan_com import open_application


def _parse_pen_mask(value: str) -> int:
    return int(value, 0)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Open a RADAN document headlessly and run the Geometry Utilities profile-healing/extraction APIs.",
    )
    parser.add_argument("input_path", help="Path to the RADAN drawing or symbol to process.")
    parser.add_argument("--backend", default=None, help="Optional RADAN backend override.")
    parser.add_argument(
        "--pattern",
        help="Optional explicit pattern path. When omitted, the script uses Mac.PART_PATTERN after opening the file.",
    )
    parser.add_argument(
        "--include-sub-patterns",
        action="store_true",
        help="Apply profile healing/extraction to nested patterns too.",
    )
    parser.add_argument(
        "--skip-healing",
        action="store_true",
        help="Skip the profile-healing pass and only run extraction options.",
    )
    parser.add_argument(
        "--tolerance",
        type=float,
        default=0.005,
        help="Healing tolerance in drawing units.",
    )
    parser.add_argument("--smooth-data", action="store_true", help="Enable the dialog's Smooth data option.")
    parser.add_argument("--realise-ellipses", action="store_true", help="Enable ellipse realization during healing.")
    parser.add_argument(
        "--remove-small-features",
        action="store_true",
        help="Remove small isolated features during healing.",
    )
    parser.add_argument("--close-small-gaps", action="store_true", help="Close small gaps during healing.")
    parser.add_argument("--merge-overlaps", action="store_true", help="Merge overlapping features during healing.")
    parser.add_argument(
        "--time-limit",
        type=float,
        help="Optional profile-healing timeout in seconds. When omitted, the normal healing call is used.",
    )
    parser.add_argument(
        "--delete-by-pen",
        action="store_true",
        help="Enable Geometry Utilities profile extraction by pen.",
    )
    parser.add_argument(
        "--pen-mask",
        type=_parse_pen_mask,
        default=0,
        help="Bitmask of pens to keep for profile extraction. Accepts decimal or 0x-prefixed values.",
    )
    parser.add_argument(
        "--lines-arcs-only",
        action="store_true",
        help="Keep only lines and arcs during profile extraction.",
    )
    parser.add_argument(
        "--full-linetype-only",
        action="store_true",
        help="Keep only full linetype lines and arcs during profile extraction.",
    )
    parser.add_argument(
        "--save-in-place",
        action="store_true",
        help="Save the modified document back to the original file.",
    )
    parser.add_argument(
        "--save-copy-path",
        help="Optional path to save a modified copy instead of overwriting the source file.",
    )
    args = parser.parse_args()

    if args.save_in_place and args.save_copy_path:
        parser.error("--save-in-place and --save-copy-path are mutually exclusive.")

    input_path = Path(args.input_path).expanduser().resolve()
    save_copy_path = Path(args.save_copy_path).expanduser().resolve() if args.save_copy_path else None

    run_healing = not bool(args.skip_healing)
    run_extraction = bool(args.delete_by_pen or args.pen_mask or args.lines_arcs_only or args.full_linetype_only)
    if not run_healing and not run_extraction:
        parser.error("Nothing to do. Enable healing or pass one of the extraction flags.")

    result: dict[str, object] = {
        "input_path": str(input_path),
        "input_exists": input_path.exists(),
        "save_in_place": bool(args.save_in_place),
        "save_copy_path": str(save_copy_path) if save_copy_path is not None else None,
        "include_sub_patterns": bool(args.include_sub_patterns),
        "run_healing": bool(run_healing),
        "run_extraction": bool(run_extraction),
        "healing_options": {
            "tolerance": float(args.tolerance),
            "smooth_data": bool(args.smooth_data),
            "realise_ellipses": bool(args.realise_ellipses),
            "remove_small_features": bool(args.remove_small_features),
            "close_small_gaps": bool(args.close_small_gaps),
            "merge_overlaps": bool(args.merge_overlaps),
            "time_limit": float(args.time_limit) if args.time_limit is not None else None,
        },
        "extraction_options": {
            "delete_by_pen": bool(args.delete_by_pen),
            "pen_mask": int(args.pen_mask),
            "lines_arcs_only": bool(args.lines_arcs_only),
            "full_linetype_only": bool(args.full_linetype_only),
        },
    }

    if save_copy_path is not None:
        save_copy_path.parent.mkdir(parents=True, exist_ok=True)

    exit_code = 0
    with open_application(backend=args.backend, force_new_instance=True) as app:
        info = app.info()
        result["backend"] = app.backend_name
        result["created_new_instance"] = app.created_new_instance
        result["process_id"] = info.process_id
        result["software_version"] = info.software_version

        app.visible = False
        app.open_document(str(input_path), read_only=False)
        app.visible = False
        app.interactive = False

        try:
            document_info = app.active_document_info()
            result["document_after_open"] = None if document_info is None else document_info.__dict__

            pattern_candidates: list[tuple[str, str | None]] = [
                ("explicit", args.pattern),
                ("current_pattern", app.mac.current_pattern_path),
                ("open_pattern", app.mac.open_pattern_path),
                ("part_pattern", app.mac.part_pattern),
            ]
            result["pattern_candidates"] = [
                {"source": source, "value": value}
                for source, value in pattern_candidates
                if value
            ]
            pattern_source = next((source for source, value in pattern_candidates if value), None)
            pattern = next((value for _, value in pattern_candidates if value), None)
            result["pattern"] = pattern
            result["pattern_source"] = pattern_source
            if not pattern:
                raise RuntimeError("Could not determine an active pattern path for the opened document.")

            result["prompt_before"] = app.mac.prompt_string

            if run_healing:
                if args.time_limit is None:
                    healing_ok = app.mac.profile_healing(
                        pattern,
                        include_sub_patterns=args.include_sub_patterns,
                        tolerance=args.tolerance,
                        realise_ellipses=args.realise_ellipses,
                        remove_small_features=args.remove_small_features,
                        close_small_gaps=args.close_small_gaps,
                        merge_overlaps=args.merge_overlaps,
                        simplify_data=args.smooth_data,
                    )
                    result["healing_result"] = {"ok": healing_ok, "mode": "profile_healing"}
                    if not healing_ok:
                        exit_code = 1
                else:
                    healing_code = app.mac.profile_healing_with_timeout(
                        pattern,
                        include_sub_patterns=args.include_sub_patterns,
                        tolerance=args.tolerance,
                        realise_ellipses=args.realise_ellipses,
                        remove_small_features=args.remove_small_features,
                        close_small_gaps=args.close_small_gaps,
                        merge_overlaps=args.merge_overlaps,
                        simplify_data=args.smooth_data,
                        time_limit=args.time_limit,
                    )
                    result["healing_result"] = {
                        "ok": healing_code == 1,
                        "mode": "profile_healing_with_timeout",
                        "return_code": healing_code,
                    }
                    if healing_code != 1:
                        exit_code = 1

            if run_extraction:
                extraction_ok = app.mac.profile_extraction(
                    pattern,
                    include_sub_patterns=args.include_sub_patterns,
                    delete_by_pen=args.delete_by_pen,
                    pen_mask=args.pen_mask,
                    lines_arcs_only=args.lines_arcs_only,
                    full_linetype_only=args.full_linetype_only,
                )
                result["extraction_result"] = {"ok": extraction_ok}
                if not extraction_ok:
                    exit_code = 1

            result["prompt_after"] = app.mac.prompt_string

            if save_copy_path is not None:
                app.save_copy_of_active_document_as(str(save_copy_path))
                result["save_copy_exists"] = save_copy_path.exists()
            elif args.save_in_place:
                app.save_active_document()
                result["save_ok"] = True
            else:
                result["save_ok"] = None

            document_after = app.active_document_info()
            result["document_after_output"] = None if document_after is None else document_after.__dict__
        finally:
            app.close_active_document(True)
            result["quit_result"] = app.quit()

    print(json.dumps(result, indent=2, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
