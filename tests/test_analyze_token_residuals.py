from __future__ import annotations

import unittest

from analyze_token_residuals import summarize_residual_rows, token_residual_row


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


if __name__ == "__main__":
    unittest.main()
