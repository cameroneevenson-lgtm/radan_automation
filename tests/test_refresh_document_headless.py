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

import refresh_document_headless


class _FakeDocumentInfo:
    def __init__(self, document_type: int = 2, dirty: bool = False) -> None:
        self.document_type = document_type
        self.dirty = dirty


class _FakeMac:
    def __init__(self, thumbnail_writes: list[tuple[str, int, int]]) -> None:
        self.thumbnail_writes = thumbnail_writes

    def license_info(self):
        class _LicenseInfo:
            holder = "Battleshield Industries"
            servercode = "8341-8159-8477-6673-9885-7909"

            @property
            def __dict__(self):
                return {"holder": self.holder, "servercode": self.servercode}

        return _LicenseInfo()

    def flat_thumbnail(self, path: str, width: int, height: int) -> bool:
        self.thumbnail_writes.append((path, width, height))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(b"png")
        return True


class _FakeApp:
    backend_name = "fake"
    created_new_instance = True

    def __init__(self) -> None:
        self.visible = True
        self.interactive = True
        self.open_calls: list[tuple[str, bool]] = []
        self.saved = 0
        self.closed = 0
        self.thumbnail_writes: list[tuple[str, int, int]] = []
        self.mac = _FakeMac(self.thumbnail_writes)

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
        self.saved += 1

    def close_active_document(self, discard_changes: bool = True) -> None:
        self.closed += 1

    def quit(self) -> bool:
        return True


class RefreshDocumentHeadlessTests(unittest.TestCase):
    def test_main_saves_document_and_exports_thumbnail(self) -> None:
        fake_app = _FakeApp()
        tmpdir = os.path.join(TEST_TMP_ROOT, f"refresh_{uuid.uuid4().hex}")
        os.makedirs(tmpdir, exist_ok=False)
        try:
            input_path = os.path.join(tmpdir, "Demo.sym")
            thumbnail_path = os.path.join(tmpdir, "thumb.png")
            with mock.patch("refresh_document_headless.open_application", return_value=fake_app):
                with mock.patch.object(
                    sys,
                    "argv",
                    [
                        "refresh_document_headless.py",
                        input_path,
                        "--thumbnail-path",
                        thumbnail_path,
                    ],
                ):
                    stdout = io.StringIO()
                    with redirect_stdout(stdout):
                        result = refresh_document_headless.main()
        finally:
            import shutil

            shutil.rmtree(tmpdir, ignore_errors=True)

        self.assertEqual(result, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["backend"], "fake")
        self.assertTrue(payload["save_requested"])
        self.assertTrue(payload["save_ok"])
        self.assertTrue(payload["thumbnail_ok"])
        self.assertTrue(payload["thumbnail_exists"])
        self.assertEqual(fake_app.saved, 1)
        self.assertEqual(fake_app.closed, 1)
        self.assertEqual(len(fake_app.thumbnail_writes), 1)

    def test_main_skips_save_in_read_only_mode(self) -> None:
        fake_app = _FakeApp()
        tmpdir = os.path.join(TEST_TMP_ROOT, f"refresh_{uuid.uuid4().hex}")
        os.makedirs(tmpdir, exist_ok=False)
        try:
            input_path = os.path.join(tmpdir, "Demo.sym")
            with mock.patch("refresh_document_headless.open_application", return_value=fake_app):
                with mock.patch.object(
                    sys,
                    "argv",
                    [
                        "refresh_document_headless.py",
                        input_path,
                        "--read-only",
                    ],
                ):
                    stdout = io.StringIO()
                    with redirect_stdout(stdout):
                        result = refresh_document_headless.main()
        finally:
            import shutil

            shutil.rmtree(tmpdir, ignore_errors=True)

        self.assertEqual(result, 0)
        payload = json.loads(stdout.getvalue())
        self.assertFalse(payload["save_requested"])
        self.assertIsNone(payload["save_ok"])
        self.assertEqual(fake_app.saved, 0)


if __name__ == "__main__":
    unittest.main()
