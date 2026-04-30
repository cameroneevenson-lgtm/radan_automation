from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import analyze_ddc_identifier_fields as analyzer


def _sym(rows: list[str]) -> str:
    return (
        '<RadanCompoundDocument><RadanFile extension="ddc"><![CDATA[\n'
        + "\n".join(rows)
        + "\n]]></RadanFile></RadanCompoundDocument>\n"
    )


class AnalyzeDdcIdentifierFieldsTests(unittest.TestCase):
    def test_small_identifier_codec_matches_geometry_row_sequence(self) -> None:
        self.assertEqual(analyzer.encode_ddc_small_identifier(15), "?")
        self.assertEqual(analyzer.decode_ddc_small_identifier("?"), 15)
        self.assertEqual(analyzer.expected_geometry_identifier(13), "?")
        self.assertIsNone(analyzer.decode_ddc_small_identifier("\t"))

    def test_analyze_folders_reports_reference_identifier_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            ref = root / "ref"
            candidate = root / "candidate"
            ref.mkdir()
            candidate.mkdir()
            (ref / "P1.sym").write_text(
                _sym(["G,,1,3,,,,,,,a.b.c", "H,,1,4,,,,,,,d.e.f"]),
                encoding="utf-8",
            )
            (candidate / "P1.sym").write_text(
                _sym(["G,,1,3,,,,,,,a.b.c", "H,,1,Z,,,,,,,d.e.f"]),
                encoding="utf-8",
            )

            payload = analyzer.analyze_folders(
                [("ref", ref), ("candidate", candidate)],
                reference_label="ref",
            )

        self.assertEqual(payload["folders"][0]["nonsequential_count"], 0)
        self.assertEqual(payload["folders"][1]["nonsequential_count"], 1)
        comparison = payload["comparisons"][0]
        self.assertEqual(comparison["identifier_or_record_mismatch_count"], 1)
        self.assertEqual(comparison["mismatch_examples"][0]["identifier"], "Z")

    def test_output_guard_rejects_non_lab_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaises(RuntimeError):
                analyzer._assert_sym_lab_output(Path(tmpdir) / "out.json")


if __name__ == "__main__":
    unittest.main()
