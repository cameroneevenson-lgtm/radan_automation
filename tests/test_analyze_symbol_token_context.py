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

import analyze_symbol_token_context as analyzer


class AnalyzeSymbolTokenContextTests(unittest.TestCase):
    def test_circle_visible_values_include_center_delta_x_as_negative_radius(self) -> None:
        row = {
            "type": "CIRCLE",
            "normalized_center": [0.64, 5.688689345562988],
            "radius": 0.062500000000001,
        }

        self.assertAlmostEqual(analyzer.slot_visible_value(row, 0), 0.702500000000001)
        self.assertAlmostEqual(analyzer.slot_visible_value(row, 1), 5.688689345562988)
        self.assertAlmostEqual(analyzer.slot_visible_value(row, 4), -0.062500000000001)
        self.assertEqual(analyzer.slot_visible_value(row, 5), 0.0)

    def test_geometry_context_records_arc_deltas_and_center_deltas(self) -> None:
        row = {
            "type": "ARC",
            "normalized_start_point": [1.0, 2.0],
            "normalized_end_point": [4.5, 6.0],
            "normalized_center": [3.0, 3.5],
            "radius": 2.5,
            "start_angle": 10.0,
            "end_angle": 90.0,
        }

        context = analyzer._geometry_context(row)

        self.assertEqual(context["radius"], 2.5)
        self.assertEqual(context["dxf_delta_x"], 3.5)
        self.assertEqual(context["dxf_delta_y"], 4.0)
        self.assertEqual(context["dxf_center_delta_x"], 2.0)
        self.assertEqual(context["dxf_center_delta_y"], 1.5)
        self.assertEqual(context["arc_start_angle"], 10.0)
        self.assertEqual(context["arc_end_angle"], 90.0)

    def test_topology_context_records_prefix_counts_and_ordinals(self) -> None:
        rows = [
            {"type": "CIRCLE"},
            {"type": "LINE"},
            {"type": "ARC"},
            {"type": "LINE"},
            {"type": "ARC"},
        ]

        context = analyzer._topology_context(rows, 5)

        self.assertEqual(context["entity_count"], 5)
        self.assertEqual(context["row_position_from_end"], 1)
        self.assertEqual(context["same_type_ordinal"], 2)
        self.assertEqual(context["same_type_remaining"], 0)
        self.assertEqual(context["prefix_circle_count"], 1)
        self.assertEqual(context["prefix_line_count"], 2)
        self.assertEqual(context["prefix_arc_count"], 1)
        self.assertEqual(context["previous_two_dxf_types"], "ARC/LINE")
        self.assertEqual(context["type_sequence_signature"], "CLALA")

    def test_focus_summary_groups_same_visible_value_and_role(self) -> None:
        rows = [
            {
                "part": "B-185",
                "row_index": 1,
                "dxf_type": "CIRCLE",
                "role": "center_delta_x",
                "role_key": "CIRCLE:center_delta_x",
                "slot": 4,
                "visible_value_key": "-0.062500000000001",
                "generated_token": "k?P",
                "oracle_token": "k?P000000P0",
                "token_match": False,
                "decoded_bucket": "close_1e-12",
                "decoded_abs_diff": 2.842e-14,
                "previous_dxf_type": "",
                "next_dxf_type": "LINE",
                "is_first_geometry": True,
                "radius": 0.062500000000001,
                "normalized_center_x": 0.64,
                "normalized_center_y": 5.68,
            },
            {
                "part": "B-200",
                "row_index": 7,
                "dxf_type": "CIRCLE",
                "role": "center_delta_x",
                "role_key": "CIRCLE:center_delta_x",
                "slot": 4,
                "visible_value_key": "-0.062500000000001",
                "generated_token": "k?P",
                "oracle_token": "k?P",
                "token_match": True,
                "decoded_bucket": "equal",
                "decoded_abs_diff": 0.0,
                "previous_dxf_type": "LINE",
                "next_dxf_type": "LINE",
                "is_first_geometry": False,
                "radius": 0.062500000000001,
                "normalized_center_x": 1.0,
                "normalized_center_y": 1.0,
            },
        ]

        summary = analyzer.summarize_context_rows(
            rows,
            focus_part="B-185",
            focus_row=1,
            focus_slot=4,
        )

        self.assertEqual(summary["slot_count"], 2)
        self.assertEqual(summary["mismatch_count"], 1)
        self.assertEqual(summary["focus"]["same_value_count"], 2)
        self.assertEqual(summary["focus"]["same_value_mismatch_count"], 1)
        self.assertEqual(
            summary["focus"]["same_value_generated_to_oracle_counts"][0],
            {"key": "k?P -> k?P000000P0", "count": 1},
        )

    def test_code_uses_longer_fence_for_backtick_tokens(self) -> None:
        self.assertEqual(analyzer._code("j?W2Se`Xm00"), "`` j?W2Se`Xm00 ``")

    def test_assert_sym_lab_output_rejects_non_lab_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaises(RuntimeError):
                analyzer._assert_sym_lab_output(Path(tmpdir) / "out.json")


if __name__ == "__main__":
    unittest.main()
