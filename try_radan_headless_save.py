from __future__ import annotations

import argparse
import json
from pathlib import Path

from radan_com import open_application


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a headless RADAN save/reopen probe.")
    parser.add_argument("--backend", default=None, help="Optional RADAN backend override.")
    args = parser.parse_args()

    base_dir = Path(__file__).resolve().parent
    base_path = base_dir / "_tmp_headless_probe_2.rpd"
    actual_path = Path(str(base_path) + ".drg")
    result: dict[str, object] = {
        "base_path": str(base_path),
        "actual_path": str(actual_path),
    }

    with open_application(backend=args.backend) as app:
        info = app.info()
        result["backend"] = app.backend_name
        result["created_new_instance"] = app.created_new_instance
        result["process_id"] = info.process_id

        app.visible = False
        app.interactive = False
        app.new_drawing(False)
        app.save_active_document_as(str(base_path))

        result["base_exists"] = base_path.exists()
        result["actual_exists"] = actual_path.exists()

        app.close_active_document(True)
        app.open_drawing(str(actual_path), read_only=True)

        reopened = app.active_document_info()
        result["reopened_document_type"] = reopened.document_type if reopened else None
        result["reopened_document_dirty"] = reopened.dirty if reopened else None

        app.close_active_document(True)
        result["quit_result"] = app.quit()

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
