from __future__ import annotations

import io
import json
import os
import sys
import unittest
import uuid
from contextlib import redirect_stdout
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

TEST_TMP_ROOT = os.path.join(HERE, "_tmp")
os.makedirs(TEST_TMP_ROOT, exist_ok=True)

import apply_geometry_util_headless


class _FakeDocumentInfo:
    def __init__(self, document_type: int = 1, dirty: bool = True) -> None:
        self.document_type = document_type
        self.dirty = dirty


class _FakeMac:
    def __init__(self) -> None:
        self.part_pattern = "/part editor"
        self.current_pattern_path = "/current pattern"
        self.open_pattern_path = "/open pattern"
        self.prompt_string = "Ready"
        self.healing_calls: list[tuple[object, ...]] = []
        self.extraction_calls: list[tuple[object, ...]] = []

    def profile_healing(
        self,
        pattern: str,
        *,
        include_sub_patterns: bool = False,
        tolerance: float = 0.005,
        realise_ellipses: bool = False,
        remove_small_features: bool = False,
        close_small_gaps: bool = False,
        merge_overlaps: bool = False,
        simplify_data: bool = False,
    ) -> bool:
        self.healing_calls.append(
            (
                pattern,
                include_sub_patterns,
                tolerance,
                realise_ellipses,
                remove_small_features,
                close_small_gaps,
                merge_overlaps,
                simplify_data,
            )
        )
        self.prompt_string = "Geometry Utilities complete"
        return True

    def profile_healing_with_timeout(
        self,
        pattern: str,
        *,
        include_sub_patterns: bool = False,
        tolerance: float = 0.005,
        realise_ellipses: bool = False,
        remove_small_features: bool = False,
        close_small_gaps: bool = False,
        merge_overlaps: bool = False,
        simplify_data: bool = False,
        time_limit: float = 0.0,
    ) -> int:
        self.healing_calls.append(
            (
                pattern,
                include_sub_patterns,
                tolerance,
                realise_ellipses,
                remove_small_features,
                close_small_gaps,
                merge_overlaps,
                simplify_data,
                time_limit,
            )
        )
        self.prompt_string = "Geometry Utilities complete"
        return 1

    def profile_extraction(
        self,
        pattern: str,
        *,
        include_sub_patterns: bool = False,
        delete_by_pen: bool = False,
        pen_mask: int = 0,
        lines_arcs_only: bool = False,
        full_linetype_only: bool = False,
    ) -> bool:
        self.extraction_calls.append(
            (
                pattern,
                include_sub_patterns,
                delete_by_pen,
                pen_mask,
                lines_arcs_only,
                full_linetype_only,
            )
        )
        self.prompt_string = "Profile extraction complete"
        return True


class _FakeApp:
    backend_name = "fake"
    created_new_instance = True

    def __init__(self) -> None:
        self.visible = True
        self.interactive = True
        self.open_calls: list[tuple[str, bool]] = []
        self.save_calls: list[str] = []
        self.closed = 0
        self.mac = _FakeMac()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return None

    def info(self):
        class _Info:
            process_id = 18516
            software_version = "2025.1.2523.1252"

        return _Info()

    def open_document(self, path: str, read_only: bool = False, password: str = "") -> None:
        self.open_calls.append((path, bool(read_only)))

    def active_document_info(self):
        return _FakeDocumentInfo()

    def save_active_document(self) -> None:
        self.save_calls.append("save")

    def save_copy_of_active_document_as(self, path: str, options_file_path: str = "") -> None:
        self.save_calls.append(path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(b"copy")

    def close_active_document(self, discard_changes: bool = True) -> None:
        self.closed += 1

    def quit(self) -> bool:
        return True


class ApplyGeometryUtilHeadlessTests(unittest.TestCase):
    def test_main_runs_profile_healing_and_saves_copy(self) -> None:
        fake_app = _FakeApp()
        tmpdir = os.path.join(TEST_TMP_ROOT, f"geometry_util_{uuid.uuid4().hex}")
        os.makedirs(tmpdir, exist_ok=False)
        try:
            input_path = os.path.join(tmpdir, "Demo.drg")
            save_copy_path = os.path.join(tmpdir, "Demo-healed.drg")
            with open(input_path, "wb") as f:
                f.write(b"drg")
            with mock.patch("apply_geometry_util_headless.open_application", return_value=fake_app):
                with mock.patch.object(
                    sys,
                    "argv",
                    [
                        "apply_geometry_util_headless.py",
                        input_path,
                        "--smooth-data",
                        "--tolerance",
                        "0.005",
                        "--save-copy-path",
                        save_copy_path,
                    ],
                ):
                    stdout = io.StringIO()
                    with redirect_stdout(stdout):
                        result = apply_geometry_util_headless.main()
        finally:
            import shutil

            shutil.rmtree(tmpdir, ignore_errors=True)

        self.assertEqual(result, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["pattern"], "/current pattern")
        self.assertEqual(payload["pattern_source"], "current_pattern")
        self.assertEqual(payload["healing_result"]["mode"], "profile_healing")
        self.assertTrue(payload["healing_result"]["ok"])
        self.assertTrue(payload["save_copy_exists"])
        self.assertFalse(payload["run_extraction"])
        self.assertEqual(
            fake_app.mac.healing_calls,
            [("/current pattern", False, 0.005, False, False, False, False, True)],
        )
        self.assertEqual(fake_app.closed, 1)

    def test_main_can_run_extraction_only(self) -> None:
        fake_app = _FakeApp()
        tmpdir = os.path.join(TEST_TMP_ROOT, f"geometry_extract_{uuid.uuid4().hex}")
        os.makedirs(tmpdir, exist_ok=False)
        try:
            input_path = os.path.join(tmpdir, "Demo.drg")
            with open(input_path, "wb") as f:
                f.write(b"drg")
            with mock.patch("apply_geometry_util_headless.open_application", return_value=fake_app):
                with mock.patch.object(
                    sys,
                    "argv",
                    [
                        "apply_geometry_util_headless.py",
                        input_path,
                        "--skip-healing",
                        "--delete-by-pen",
                        "--pen-mask",
                        "0x12",
                        "--lines-arcs-only",
                    ],
                ):
                    stdout = io.StringIO()
                    with redirect_stdout(stdout):
                        result = apply_geometry_util_headless.main()
        finally:
            import shutil

            shutil.rmtree(tmpdir, ignore_errors=True)

        self.assertEqual(result, 0)
        payload = json.loads(stdout.getvalue())
        self.assertFalse(payload["run_healing"])
        self.assertTrue(payload["run_extraction"])
        self.assertTrue(payload["extraction_result"]["ok"])
        self.assertEqual(fake_app.mac.healing_calls, [])
        self.assertEqual(fake_app.mac.extraction_calls, [("/current pattern", False, True, 18, True, False)])


if __name__ == "__main__":
    unittest.main()
