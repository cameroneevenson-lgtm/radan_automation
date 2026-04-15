from __future__ import annotations

import argparse
import json
from pathlib import Path

from radan_com import open_application


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a headless RADAN output probe.")
    parser.add_argument("--backend", default=None, help="Optional RADAN backend override.")
    args = parser.parse_args()

    base_dir = Path(__file__).resolve().parent
    base_path = base_dir / "_tmp_headless_output_probe.rpd"
    actual_path = Path(str(base_path) + ".drg")
    thumbnail_path = base_dir / "_tmp_headless_output_probe.png"

    result: dict[str, object] = {
        "base_path": str(base_path),
        "actual_path": str(actual_path),
        "thumbnail_path": str(thumbnail_path),
    }

    with open_application(backend=args.backend, force_new_instance=True) as app:
        info = app.info()
        result["backend"] = app.backend_name
        result["created_new_instance"] = app.created_new_instance
        result["process_id"] = info.process_id
        result["license_info"] = app.mac.license_info().__dict__
        result["report_type_png"] = app.mac.report_type("PNG")

        app.visible = False
        app.new_drawing(False)
        app.visible = False
        app.interactive = False
        result["document_before_save"] = app.active_document_info().__dict__

        app.save_active_document_as(str(base_path))
        result["saved_path_exists"] = actual_path.exists()
        result["thumbnail_ok"] = app.mac.flat_thumbnail(str(thumbnail_path), 640, 480)
        result["thumbnail_exists"] = thumbnail_path.exists()
        result["document_after_output"] = app.active_document_info().__dict__

        app.close_active_document(True)
        result["quit_result"] = app.quit()

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
