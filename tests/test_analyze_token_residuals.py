from __future__ import annotations

import unittest
from pathlib import Path
from unittest import mock

from analyze_token_residuals import analyze_token_residuals, summarize_residual_rows, token_residual_row


class AnalyzeTokenResidualsTests(unittest.TestCase):
    def test_token_residual_row_reports_last_char_and_mantissa_delta(self) -> None:
        row = token_residual_row(
            part="P1",
            row_index=1,
            dxf_type="ARC",
            slot=2,
            oracle_token="k?9VIVIVIX0",
            generated_token="k?9VIVIVIVJ",
            visible_value_key="0.100000",
        )

        self.assertFalse(row["token_match"])
        self.assertEqual(row["role"], "delta_x")
        self.assertEqual(row["mantissa_delta_units"], 102)
        self.assertEqual(row["last_char_delta"], None)
        self.assertEqual(row["decoded_bucket"], "close_1e-12")

    def test_token_residual_row_detects_same_prefix_except_last_char(self) -> None:
        row = token_residual_row(
            part="P1",
            row_index=1,
            dxf_type="LINE",
            slot=0,
            oracle_token="0@=PVoW6:Q`",
            generated_token="0@=PVoW6:Q]",
        )

        self.assertTrue(row["same_prefix_except_last_char"])
        self.assertEqual(row["last_char_delta"], 3)

    def test_summarize_residual_rows_groups_mismatch_shapes(self) -> None:
        rows = [
            token_residual_row(
                part="P1",
                row_index=1,
                dxf_type="LINE",
                slot=0,
                oracle_token="m?0",
                generated_token="m?0",
            ),
            token_residual_row(
                part="P1",
                row_index=2,
                dxf_type="LINE",
                slot=0,
                oracle_token="0@=PVoW6:Q`",
                generated_token="0@=PVoW6:Q]",
            ),
        ]

        summary = summarize_residual_rows(rows)

        self.assertEqual(summary["slot_count"], 2)
        self.assertEqual(summary["exact_token_count"], 1)
        self.assertEqual(summary["mismatch_count"], 1)
        self.assertEqual(summary["same_prefix_except_last_char_count"], 1)
        self.assertIn("LINE:start_x", summary["by_role"])

    def test_analyze_token_residuals_excludes_requested_parts(self) -> None:
        dxf_rows = {
            "keep": [{"type": "LINE", "normalized_start": (0.0, 0.0), "normalized_end": (1.0, 0.0)}],
            "skip": [{"type": "LINE", "normalized_start": (0.0, 0.0), "normalized_end": (1.0, 0.0)}],
        }
        ddc_rows = {
            "keep": [{"tokens": ["", "", "0@0", ""], "record": "G"}],
            "skip": [{"tokens": ["", "", "0@0", ""], "record": "G"}],
        }

        def fake_read_dxf(path: Path):
            return dxf_rows[path.stem], {}

        def fake_read_ddc(path: Path):
            return ddc_rows[path.stem]

        with mock.patch("analyze_token_residuals.Path.glob") as glob_mock:
            glob_mock.side_effect = [
                [Path("keep.dxf"), Path("skip.dxf")],
                [Path("keep.sym"), Path("skip.sym")],
                [Path("keep.sym"), Path("skip.sym")],
            ]
            with mock.patch("analyze_token_residuals.read_dxf_entities", side_effect=fake_read_dxf):
                with mock.patch("analyze_token_residuals.read_ddc_records", side_effect=fake_read_ddc):
                    payload = analyze_token_residuals(
                        dxf_folder=Path("dxf"),
                        oracle_sym_folder=Path("oracle"),
                        generated_sym_folder=Path("generated"),
                        exclude_parts=["skip"],
                    )

        self.assertEqual(payload["exclude_parts"], ["skip"])
        self.assertEqual(payload["part_count"], 1)
        self.assertEqual(payload["parts"][0]["part"], "keep")


if __name__ == "__main__":
    unittest.main()
