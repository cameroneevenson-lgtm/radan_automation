from __future__ import annotations

import argparse
import json
from pathlib import Path

from radan_com import open_application
from radan_utils import _summarize_license_info


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Open a RADAN document headlessly and export useful artifacts.",
    )
    parser.add_argument("input_path", help="Path to the RADAN drawing, symbol, or raster source file.")
    parser.add_argument("--backend", default=None, help="Optional RADAN backend override.")
    parser.add_argument(
        "--thumbnail-path",
        help="Optional PNG output path. Defaults to '<input-stem>_flat.png' next to the input file.",
    )
    parser.add_argument("--thumbnail-width", type=int, default=640, help="Flat thumbnail width in pixels.")
    parser.add_argument("--thumbnail-height", type=int, default=480, help="Flat thumbnail height in pixels.")
    parser.add_argument(
        "--save-copy-path",
        help="Optional path for a SaveCopyAs output so the source file stays untouched.",
    )
    parser.add_argument(
        "--options-file-path",
        default="",
        help="Optional RADAN options file path to pass to SaveCopyAs.",
    )
    parser.add_argument(
        "--read-only",
        action="store_true",
        help="Open the source document read-only before exporting artifacts.",
    )
    args = parser.parse_args()

    input_path = Path(args.input_path).expanduser().resolve()
    thumbnail_path = (
        Path(args.thumbnail_path).expanduser().resolve()
        if args.thumbnail_path
        else input_path.with_name(f"{input_path.stem}_flat.png")
    )
    save_copy_path = Path(args.save_copy_path).expanduser().resolve() if args.save_copy_path else None

    if not input_path.exists():
        parser.error(f"Input path does not exist: {input_path}")

    result: dict[str, object] = {
        "input_path": str(input_path),
        "thumbnail_path": str(thumbnail_path),
        "save_copy_path": str(save_copy_path) if save_copy_path is not None else None,
        "read_only": args.read_only,
    }

    with open_application(backend=args.backend, force_new_instance=True) as app:
        info = app.info()
        result["backend"] = app.backend_name
        result["created_new_instance"] = app.created_new_instance
        result["process_id"] = info.process_id
        result["software_version"] = info.software_version
        result["license_info"] = _summarize_license_info(app.mac.license_info())

        app.visible = False
        app.open_document(str(input_path), read_only=args.read_only)
        app.visible = False
        app.interactive = False
        document_info = app.active_document_info()
        result["document_after_open"] = None if document_info is None else document_info.__dict__

        result["thumbnail_ok"] = app.mac.flat_thumbnail(
            str(thumbnail_path),
            args.thumbnail_width,
            args.thumbnail_height,
        )
        result["thumbnail_exists"] = thumbnail_path.exists()

        if save_copy_path is not None:
            app.save_copy_of_active_document_as(str(save_copy_path), args.options_file_path)
            result["save_copy_exists"] = save_copy_path.exists()

        result["document_after_output"] = (
            None if app.active_document_info() is None else app.active_document_info().__dict__
        )
        app.close_active_document(True)
        result["quit_result"] = app.quit()

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
