from __future__ import annotations

import unittest

from write_native_sym_prototype import encode_geometry_data


class WriteNativeSymPrototypeTests(unittest.TestCase):
    def test_encodes_line_as_start_and_delta_slots(self) -> None:
        row = {
            "type": "LINE",
            "normalized_start": [1.0, 2.0],
            "normalized_end": [1.25, 1.5],
        }

        self.assertEqual(encode_geometry_data(row, token_count=6), "o?0.0@0.m?0.n?P..")

    def test_encodes_circle_as_arc_style_start_and_center_delta(self) -> None:
        row = {
            "type": "CIRCLE",
            "normalized_center": [1.0, 2.0],
            "radius": 0.25,
        }

        self.assertEqual(encode_geometry_data(row, token_count=10), "o?4.0@0...m?P..o?0...o?0")

    def test_encodes_arc_as_start_end_delta_and_center_delta(self) -> None:
        row = {
            "type": "ARC",
            "normalized_start_point": [2.0, 1.0],
            "normalized_end_point": [1.75, 1.25],
            "normalized_center": [1.75, 1.0],
        }

        self.assertEqual(encode_geometry_data(row, token_count=10), "0@0.o?0.m?P.m?0.m?P..o?0...o?0")


if __name__ == "__main__":
    unittest.main()
