from __future__ import annotations

from types import SimpleNamespace
import unittest

from radan_com import RadanApplicationInfo, RadanLiveSessionInfo, RadanTargetMismatchError
from remap_feature_pens_live import _assert_attached_app_matches_session


def _session(process_id: int) -> RadanLiveSessionInfo:
    return RadanLiveSessionInfo(
        application=RadanApplicationInfo(
            prog_id="Radraft.Application",
            backend="fake",
            name="Mazak Smart System",
            full_name=None,
            path=None,
            software_version=None,
            process_id=process_id,
            visible=True,
            interactive=True,
            gui_state=4,
            gui_sub_state=14,
        ),
        window_title="Demo Part - Mazak Smart System Part Editor",
        editor_mode="part",
        pattern="/symbol editor",
        bounds=None,
    )


class _FakeApp:
    def __init__(self, process_id: int | None) -> None:
        self._process_id = process_id

    def info(self):
        return SimpleNamespace(process_id=self._process_id)


class RemapFeaturePensLiveTests(unittest.TestCase):
    def test_write_attach_must_match_validated_session_pid(self) -> None:
        with self.assertRaises(RadanTargetMismatchError):
            _assert_attached_app_matches_session(_FakeApp(999), _session(123))

    def test_write_attach_accepts_matching_expected_pid(self) -> None:
        _assert_attached_app_matches_session(
            _FakeApp(123),
            _session(123),
            expected_process_id=123,
        )


if __name__ == "__main__":
    unittest.main()
