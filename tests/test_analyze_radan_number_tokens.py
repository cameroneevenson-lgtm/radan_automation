from __future__ import annotations

import unittest

from analyze_radan_number_tokens import analyze_decimal_sweep, is_dyadic_decimal, token_delta_row


class AnalyzeRadanNumberTokensTests(unittest.TestCase):
    def test_is_dyadic_decimal_detects_binary_exact_values(self) -> None:
        self.assertTrue(is_dyadic_decimal(0.25))
        self.assertTrue(is_dyadic_decimal("1.25"))
        self.assertFalse(is_dyadic_decimal(0.1))
        self.assertFalse(is_dyadic_decimal("1.333333"))

    def test_token_delta_row_reports_mantissa_delta(self) -> None:
        row = token_delta_row(
            {
                "stem": "N03",
                "width": 0.1,
                "radan_width_token": "k?9VIVIVIX0",
                "current_width_token": "k?9VIVIVIVJ",
            }
        )

        self.assertFalse(row["match"])
        self.assertEqual(row["mantissa_delta_units"], 102)
        self.assertGreater(row["radan_minus_target"], 0)
        self.assertEqual(row["mantissa_digit_deltas"], [0, 0, 0, 0, 0, 0, 0, 2, -26])

    def test_analyze_decimal_sweep_summarizes_dyadic_and_non_dyadic_rows(self) -> None:
        payload = analyze_decimal_sweep(
            [
                {
                    "stem": "N03",
                    "width": 0.1,
                    "radan_width_token": "k?9VIVIVIX0",
                    "current_width_token": "k?9VIVIVIVJ",
                },
                {
                    "stem": "N05",
                    "width": 0.25,
                    "radan_width_token": "m?0",
                    "current_width_token": "m?0",
                },
            ]
        )

        self.assertEqual(payload["row_count"], 2)
        self.assertEqual(payload["match_count"], 1)
        self.assertEqual(payload["mismatch_count"], 1)
        self.assertEqual(payload["dyadic_match_count"], 1)
        self.assertEqual(payload["non_dyadic_mismatch_count"], 1)
        self.assertEqual(payload["mantissa_delta_unit_counts"], {"0": 1, "102": 1})


if __name__ == "__main__":
    unittest.main()
