from __future__ import annotations

import unittest
from fractions import Fraction

from ddc_number_codec import decode_ddc_number, decode_ddc_number_fraction, encode_ddc_number, encode_ddc_number_fraction


class DdcNumberCodecTests(unittest.TestCase):
    def test_decode_known_short_tokens(self) -> None:
        cases = {
            "": 0.0,
            "j?0": 0.03125,
            "j?P": -0.03125,
            "m?0": 0.25,
            "m?P": -0.25,
            "o?0": 1.0,
            "o?P": -1.0,
            "0@0": 2.0,
            "0@P": -2.0,
            "0@0P": 2.0625,
        }
        for token, expected in cases.items():
            with self.subTest(token=token):
                self.assertAlmostEqual(decode_ddc_number(token), expected, places=9)

    def test_decode_known_long_tokens(self) -> None:
        self.assertAlmostEqual(decode_ddc_number("4@:l4gdOiU0"), 53.877379, places=6)
        self.assertAlmostEqual(decode_ddc_number("o?9nLU?JLZ0"), 1.623483, places=6)
        self.assertAlmostEqual(decode_ddc_number("2@7@COAoVC`"), 11.627379, places=6)

    def test_encode_round_trips_simple_values(self) -> None:
        values = [0.0, 0.25, -0.25, 1.0, -1.0, 2.0, -2.0, 2.0625, 53.877379]
        for value in values:
            with self.subTest(value=value):
                token = encode_ddc_number(value)
                self.assertAlmostEqual(decode_ddc_number(token), value, places=6)

    def test_encode_matches_observed_dyadic_tokens(self) -> None:
        self.assertEqual(encode_ddc_number(0.25), "m?0")
        self.assertEqual(encode_ddc_number(-0.25), "m?P")
        self.assertEqual(encode_ddc_number(2.0625), "0@0P")

    def test_encode_handles_near_power_of_two_without_invalid_digit(self) -> None:
        token = encode_ddc_number(3.9999999999999964)

        self.assertNotIn("@@", token)
        self.assertAlmostEqual(decode_ddc_number(token), 3.9999999999999964, places=9)

    def test_encode_matches_observed_near_dyadic_tokens(self) -> None:
        token = "3@5Ooooooon"

        self.assertAlmostEqual(decode_ddc_number(token), 21.5, places=9)
        self.assertEqual(encode_ddc_number(decode_ddc_number(token)), token)

    def test_fraction_encoder_preserves_dyadic_values_exactly(self) -> None:
        token = encode_ddc_number_fraction(Fraction(43, 2))

        self.assertEqual(token, "3@5P")
        self.assertEqual(decode_ddc_number_fraction(token), Fraction(43, 2))

    def test_fraction_encoder_preserves_observed_terminal_zero_digit(self) -> None:
        token = "n?0F;ibU_I0"

        value = decode_ddc_number_fraction(token)

        self.assertEqual(encode_ddc_number_fraction(value, min_continuation_digits=8), token)


if __name__ == "__main__":
    unittest.main()
