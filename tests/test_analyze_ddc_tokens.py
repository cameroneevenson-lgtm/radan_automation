from __future__ import annotations

import unittest

import analyze_ddc_tokens


SAMPLE_CORPUS = {
    "csv_path": "parts.csv",
    "sym_folder": "symbols",
    "part_count": 1,
    "total_dxf_entities": 2,
    "total_ddc_records": 2,
    "parts": [
        {
            "part": "Sample",
            "pairs": [
                {
                    "dxf": {
                        "type": "LINE",
                        "layer": "IV_INTERIOR_PROFILES",
                        "normalized_start": [0.0, 0.0],
                        "normalized_end": [2.0, 0.0],
                    },
                    "ddc": {
                        "record": "G",
                        "pen": "1",
                        "tokens": ["", "", "0@0", ""],
                    },
                },
                {
                    "dxf": {
                        "type": "CIRCLE",
                        "layer": "IV_MARK_SURFACE",
                        "normalized_center": [1.0, 1.0],
                        "radius": 0.5,
                    },
                    "ddc": {
                        "record": "H",
                        "pen": "7",
                        "tokens": ["o?8", "o?0", "", "", "n?P", "", "o?0", "", "", "o?0"],
                    },
                },
            ],
        }
    ],
}


class AnalyzeDdcTokensTests(unittest.TestCase):
    def test_analyze_corpus_reports_pair_and_layer_counts(self) -> None:
        payload = analyze_ddc_tokens.analyze_corpus(SAMPLE_CORPUS)

        self.assertEqual(
            payload["pair_counts"],
            [
                {"ddc_record": "G", "dxf_type": "LINE", "count": 1},
                {"ddc_record": "H", "dxf_type": "CIRCLE", "count": 1},
            ],
        )
        self.assertEqual(payload["source_corpus"]["part_count"], 1)
        self.assertEqual(payload["line_slot_hypothesis"][2]["assumed_field"], "end_x")
        self.assertEqual(payload["line_delta_slot_hypothesis"][2]["assumed_field"], "delta_x")
        self.assertEqual(payload["line_slot_hypothesis"][2]["empty_token_nonzero_count"], 0)
        self.assertEqual(payload["line_delta_slot_hypothesis"][2]["empty_token_nonzero_count"], 0)
        self.assertEqual(payload["circle_slot_hypothesis"][2]["assumed_field"], "center_delta_x")
        self.assertEqual(payload["circle_slot_hypothesis"][2]["distinct_non_empty_tokens"], 1)

    def test_record_shapes_capture_non_empty_slots(self) -> None:
        payload = analyze_ddc_tokens.analyze_corpus(SAMPLE_CORPUS)

        shapes = {
            (row["ddc_record"], row["dxf_type"]): row["shapes"]
            for row in payload["record_shapes"]
        }
        self.assertEqual(shapes[("G", "LINE")][0]["non_empty_slots"], "2")
        self.assertEqual(shapes[("H", "CIRCLE")][0]["non_empty_slots"], "0,1,4,6,9")


if __name__ == "__main__":
    unittest.main()
