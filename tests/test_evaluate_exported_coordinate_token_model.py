from __future__ import annotations

import unittest
from fractions import Fraction

from evaluate_exported_coordinate_token_model import (
    coordinate_entries_for_part,
    min_continuation_digits,
    predicted_slot_fractions,
    token_fraction,
    value_key,
)
from ddc_number_codec import encode_ddc_number_fraction


class EvaluateExportedCoordinateTokenModelTests(unittest.TestCase):
    def test_min_continuation_digits_handles_short_and_padded_tokens(self) -> None:
        self.assertEqual(min_continuation_digits(""), 0)
        self.assertEqual(min_continuation_digits("m?0"), 0)
        self.assertEqual(min_continuation_digits("i?9VIVIVIP0"), 8)

    def test_coordinate_entries_reconstruct_line_endpoints_from_ddc(self) -> None:
        start_x = encode_ddc_number_fraction(Fraction(1, 1))
        start_y = encode_ddc_number_fraction(Fraction(2, 1))
        delta_x = encode_ddc_number_fraction(Fraction(3, 1))
        delta_y = encode_ddc_number_fraction(Fraction(-1, 1))

        entries = coordinate_entries_for_part(
            part="P1",
            dxf_rows=[
                {
                    "type": "LINE",
                    "normalized_start": [1.0, 2.0],
                    "normalized_end": [4.0, 1.0],
                }
            ],
            ddc_rows=[
                {
                    "tokens": [start_x, start_y, delta_x, delta_y],
                }
            ],
        )

        by_key = {(entry["axis"], entry["value_key"]): entry["fraction"] for entry in entries}
        self.assertEqual(by_key[("x", "1.000000")], Fraction(1, 1))
        self.assertEqual(by_key[("x", "4.000000")], Fraction(4, 1))
        self.assertEqual(by_key[("y", "1.000000")], Fraction(1, 1))

    def test_coordinate_entries_reconstruct_circle_start_and_center(self) -> None:
        entries = coordinate_entries_for_part(
            part="P1",
            dxf_rows=[
                {
                    "type": "CIRCLE",
                    "normalized_center": [2.0, 3.0],
                    "radius": 0.25,
                }
            ],
            ddc_rows=[
                {
                    "tokens": [
                        encode_ddc_number_fraction(Fraction(9, 4)),
                        encode_ddc_number_fraction(Fraction(3, 1)),
                        "",
                        "",
                        encode_ddc_number_fraction(Fraction(-1, 4)),
                    ],
                }
            ],
        )

        by_key = {(entry["axis"], entry["value_key"]): entry["fraction"] for entry in entries}
        self.assertEqual(by_key[("x", "2.250000")], Fraction(9, 4))
        self.assertEqual(by_key[("x", "2.000000")], Fraction(2, 1))
        self.assertEqual(by_key[("y", "3.000000")], Fraction(3, 1))

    def test_predicted_slot_fractions_use_coordinate_lookup_for_delta(self) -> None:
        coordinate_lookup = {
            ("x", "1.000000"): {"P1": Fraction(1, 1)},
            ("x", "4.000000"): {"P1": Fraction(4, 1)},
            ("y", "2.000000"): {"P1": Fraction(2, 1)},
            ("y", "1.000000"): {"P1": Fraction(1, 1)},
        }

        predictions = predicted_slot_fractions(
            part="P1",
            dxf_row={
                "type": "LINE",
                "normalized_start": [1.0, 2.0],
                "normalized_end": [4.0, 1.0],
            },
            coordinate_lookup=coordinate_lookup,
            coordinate_entries=[],
            value_digits=6,
        )

        self.assertEqual(predictions[0][0], Fraction(1, 1))
        self.assertEqual(predictions[2][0], Fraction(3, 1))
        self.assertEqual(predictions[3][0], Fraction(-1, 1))
        self.assertTrue(predictions[2][2])

    def test_predicted_slot_fractions_support_circle_geometry(self) -> None:
        coordinate_lookup = {
            ("x", "2.250000"): {"P1": Fraction(9, 4)},
            ("x", "2.000000"): {"P1": Fraction(2, 1)},
            ("y", "3.000000"): {"P1": Fraction(3, 1)},
        }

        predictions = predicted_slot_fractions(
            part="P1",
            dxf_row={
                "type": "CIRCLE",
                "normalized_center": [2.0, 3.0],
                "radius": 0.25,
            },
            coordinate_lookup=coordinate_lookup,
            coordinate_entries=[],
            value_digits=6,
        )

        self.assertEqual(predictions[0][0], Fraction(9, 4))
        self.assertEqual(predictions[4][0], Fraction(-1, 4))
        self.assertEqual(predictions[6][0], Fraction(1, 1))

    def test_value_key_and_token_fraction_are_stable(self) -> None:
        self.assertEqual(value_key(-0.0), "0.000000")
        self.assertEqual(token_fraction(""), Fraction(0, 1))


if __name__ == "__main__":
    unittest.main()
