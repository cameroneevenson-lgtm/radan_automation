from __future__ import annotations

import unittest

from analyze_exported_dxf_token_corpus import (
    evaluate_lookup_strategy,
    observations_for_part,
    slot_values_for_dxf_row,
    value_key,
)
from ddc_number_codec import encode_ddc_number


class AnalyzeExportedDxfTokenCorpusTests(unittest.TestCase):
    def test_value_key_normalizes_negative_zero(self) -> None:
        self.assertEqual(value_key(-0.0), "0.000000")
        self.assertEqual(value_key(-0.0000001), "0.000000")
        self.assertEqual(value_key(1.2345678), "1.234568")

    def test_slot_values_for_line(self) -> None:
        values = slot_values_for_dxf_row(
            {
                "type": "LINE",
                "normalized_start": [1.0, 2.0],
                "normalized_end": [4.5, 1.25],
            }
        )

        self.assertEqual(values[0], 1.0)
        self.assertEqual(values[1], 2.0)
        self.assertEqual(values[2], 3.5)
        self.assertEqual(values[3], -0.75)

    def test_slot_values_for_arc(self) -> None:
        values = slot_values_for_dxf_row(
            {
                "type": "ARC",
                "normalized_start_point": [10.0, 2.0],
                "normalized_end_point": [9.5, 2.5],
                "normalized_center": [9.5, 2.0],
            }
        )

        self.assertEqual(values[0], 10.0)
        self.assertEqual(values[2], -0.5)
        self.assertEqual(values[4], -0.5)
        self.assertEqual(values[5], 0.0)
        self.assertEqual(values[6], 1.0)

    def test_observations_include_current_encoder_and_context(self) -> None:
        observations = observations_for_part(
            part_name="P1",
            dxf_rows=[
                {
                    "type": "LINE",
                    "layer": "0",
                    "normalized_start": [0.25, 0.0],
                    "normalized_end": [1.25, 0.0],
                }
            ],
            ddc_rows=[
                {
                    "record": "G",
                    "pen": "1",
                    "tokens": [encode_ddc_number(0.25), "", encode_ddc_number(1.0), ""],
                }
            ],
        )

        nonzero = [row for row in observations if row["nonzero_slot"]]
        self.assertEqual(len(nonzero), 2)
        self.assertTrue(all(row["token_match"] for row in nonzero))
        self.assertEqual(nonzero[0]["role"], "start_x")
        self.assertEqual(nonzero[0]["previous_type"], "")
        self.assertEqual(nonzero[0]["next_type"], "")

    def test_lookup_strategy_is_leave_one_part_out(self) -> None:
        rows = [
            {
                "part": "P1",
                "ddc_record": "G",
                "dxf_type": "LINE",
                "slot": 0,
                "role": "start_x",
                "previous_type": "",
                "next_type": "",
                "value_key": "1.000000",
                "good_token": "token_a",
                "nonzero_slot": True,
                "row_index": 1,
            },
            {
                "part": "P2",
                "ddc_record": "G",
                "dxf_type": "LINE",
                "slot": 0,
                "role": "start_x",
                "previous_type": "",
                "next_type": "",
                "value_key": "1.000000",
                "good_token": "token_a",
                "nonzero_slot": True,
                "row_index": 1,
            },
            {
                "part": "P3",
                "ddc_record": "G",
                "dxf_type": "LINE",
                "slot": 0,
                "role": "start_x",
                "previous_type": "",
                "next_type": "",
                "value_key": "2.000000",
                "good_token": "token_only_in_p3",
                "nonzero_slot": True,
                "row_index": 1,
            },
        ]

        result = evaluate_lookup_strategy(rows, strategy="type_role_value")

        self.assertEqual(result["evaluated_slot_count"], 3)
        self.assertEqual(result["covered_slot_count"], 2)
        self.assertEqual(result["exact_match_count"], 2)


if __name__ == "__main__":
    unittest.main()
