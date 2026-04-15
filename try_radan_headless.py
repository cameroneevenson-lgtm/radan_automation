from __future__ import annotations

import argparse
import json

from radan_com import open_application


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a minimal headless RADAN probe.")
    parser.add_argument("--backend", default=None, help="Optional RADAN backend override.")
    args = parser.parse_args()

    result: dict[str, object] = {}

    with open_application(backend=args.backend) as app:
        info = app.info()
        result["backend"] = app.backend_name
        result["created_new_instance"] = app.created_new_instance
        result["process_id"] = info.process_id
        result["visible_before"] = info.visible
        result["interactive_before"] = info.interactive

        app.visible = False
        app.interactive = False
        app.new_drawing(False)

        doc_info = app.active_document_info()
        result["document_type"] = doc_info.document_type if doc_info else None
        result["document_dirty"] = doc_info.dirty if doc_info else None

        app.close_active_document(True)
        result["closed_discarded"] = True
        result["quit_result"] = app.quit()

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
