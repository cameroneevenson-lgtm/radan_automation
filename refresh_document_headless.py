from __future__ import annotations

import argparse
import json
from pathlib import Path

from radan_com import open_application


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Open a RADAN document headlessly, save it, and optionally export a thumbnail.",
    )
    parser.add_argument("input_path", help="Path to the RADAN drawing, symbol, or raster source file.")
    parser.add_argument("--backend", default=None, help="Optional RADAN backend override.")
    parser.add_argument(
        "--read-only",
        action="store_true",
        help="Open the source document read-only. Save is skipped when this flag is set.",
    )
    parser.add_argument(
        "--skip-save",
        action="store_true",
        help="Open the document but do not save it back out.",
    )
    parser.add_argument(
        "--thumbnail-path",
        help="Optional PNG output path. When omitted, no thumbnail is exported.",
    )
    parser.add_argument("--thumbnail-width", type=int, default=640, help="Optional thumbnail width in pixels.")
    parser.add_argument("--thumbnail-height", type=int, default=480, help="Optional thumbnail height in pixels.")
    args = parser.parse_args()

    input_path = Path(args.input_path).expanduser().resolve()
    thumbnail_path = Path(args.thumbnail_path).expanduser().resolve() if args.thumbnail_path else None
    should_save = (not bool(args.skip_save)) and (not bool(args.read_only))

    result: dict[str, object] = {
        "input_path": str(input_path),
        "input_exists": input_path.exists(),
        "thumbnail_path": str(thumbnail_path) if thumbnail_path is not None else None,
        "read_only": bool(args.read_only),
        "skip_save": bool(args.skip_save),
        "save_requested": bool(should_save),
    }

    with open_application(backend=args.backend, force_new_instance=True) as app:
        info = app.info()
        result["backend"] = app.backend_name
        result["created_new_instance"] = app.created_new_instance
        result["process_id"] = info.process_id
        result["software_version"] = info.software_version
        result["license_info"] = app.mac.license_info().__dict__

        app.visible = False
        app.open_document(str(input_path), read_only=args.read_only)
        app.visible = False
        app.interactive = False

        document_info = app.active_document_info()
        result["document_after_open"] = None if document_info is None else document_info.__dict__

        if should_save:
            app.save_active_document()
            result["save_ok"] = True
        else:
            result["save_ok"] = None

        if thumbnail_path is not None:
            result["thumbnail_ok"] = app.mac.flat_thumbnail(
                str(thumbnail_path),
                int(args.thumbnail_width),
                int(args.thumbnail_height),
            )
            result["thumbnail_exists"] = thumbnail_path.exists()

        result["document_after_output"] = (
            None if app.active_document_info() is None else app.active_document_info().__dict__
        )
        app.close_active_document(True)
        result["quit_result"] = app.quit()

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
