from __future__ import annotations

import unittest

from ddc_number_codec import decode_ddc_number, encode_ddc_number


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

    def test_encode_carries_near_power_of_two_rounding(self) -> None:
        token = encode_ddc_number(3.9999999999999964)

        self.assertEqual(token, "1@0")
        self.assertNotIn("@@", token)
        self.assertAlmostEqual(decode_ddc_number(token), 4.0, places=9)


if __name__ == "__main__":
    unittest.main()
