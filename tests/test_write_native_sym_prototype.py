from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import ezdxf
from ddc_corpus import Bounds
from ddc_number_codec import decode_ddc_number_fraction
from write_native_sym_prototype import (
    _refresh_symbol_metadata_attrs,
    _rows_with_connected_line_profiles,
    _rows_with_low_y_rightmost_line_profile_start,
    _rows_with_rounded_source_coordinates,
    _rows_with_topology_snapped_endpoints,
    _symbol_view_extents,
    _symbol_view_record_field,
    encode_geometry_data,
    normalize_collinear_boundary_chains,
    normalize_collinear_line_chains,
    write_native_prototype,
)


class WriteNativeSymPrototypeTests(unittest.TestCase):
    def test_encodes_line_as_start_and_delta_slots(self) -> None:
        row = {
            "type": "LINE",
            "normalized_start": [1.0, 2.0],
            "normalized_end": [1.25, 1.5],
        }

        self.assertEqual(encode_geometry_data(row, token_count=6), "o?0.0@0.m?0.n?P..")

    def test_line_delta_repair_zero_appends_decoded_close_zero_to_length10_deltas(self) -> None:
        start_y = float(decode_ddc_number_fraction("4@1j5RcmS`a"))
        row = {
            "type": "LINE",
            "normalized_start": [35.0625, start_y],
            "normalized_end": [35.0625, 36.25],
        }

        original = encode_geometry_data(row, token_count=17).split(".")
        repaired = encode_geometry_data(row, token_count=17, line_delta_repair_zero=True).split(".")

        self.assertEqual(original[3], "m?;djH4hNN")
        self.assertEqual(repaired[3], "m?;djH4hNN0")
        self.assertEqual(float(decode_ddc_number_fraction(original[3])), float(decode_ddc_number_fraction(repaired[3])))

    def test_h_delta_repair_zero_pads_arc_delta_slots(self) -> None:
        row = {
            "type": "ARC",
            "normalized_start_point": [33.5, 53.38],
            "normalized_end_point": [33.5, 53.451],
            "normalized_center": [33.475, 53.38],
        }

        original = encode_geometry_data(row, token_count=21, canonicalize_endpoints=True).split(".")
        repaired = encode_geometry_data(
            row,
            token_count=21,
            canonicalize_endpoints=True,
            h_delta_repair_zero=True,
        ).split(".")

        self.assertEqual(original[4], "i?YVIVIVJ")
        self.assertEqual(repaired[4], "i?YVIVIVJ00")
        self.assertEqual(float(decode_ddc_number_fraction(original[4])), float(decode_ddc_number_fraction(repaired[4])))

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

    def test_rounds_source_coordinates_before_normalizing_for_radan_import_parity(self) -> None:
        rows = [
            {
                "type": "LINE",
                "start": [25.382135827, -3.286611652],
                "end": [25.382135827, 0.512607024],
                "normalized_start": [25.892968677, 6.299218677],
                "normalized_end": [25.892968677, 10.098437353],
            }
        ]
        bounds = Bounds(min_x=-0.51083285, min_y=-9.585830329, max_x=30.650104503, max_y=0.512607024)

        rounded = _rows_with_rounded_source_coordinates(rows, bounds, digits=6)

        self.assertEqual(rounded[0]["normalized_start"], [25.892969, 6.299218])
        self.assertEqual(rounded[0]["normalized_end"], [25.892969, 10.098437])

    def test_source_coordinate_rounding_does_not_round_circle_radius(self) -> None:
        rows = [
            {
                "type": "CIRCLE",
                "center": [42.67778, -1.25],
                "normalized_center": [42.67778, 0.0],
                "radius": 0.1015625,
            }
        ]
        bounds = Bounds(min_x=0.0, min_y=-1.25, max_x=42.7793425, max_y=-1.1484375)

        rounded = _rows_with_rounded_source_coordinates(rows, bounds, digits=6)

        self.assertEqual(rounded[0]["normalized_center"], [42.67778, 0.0])
        self.assertEqual(rounded[0]["radius"], 0.1015625)

    def test_topology_snap_uses_rounded_line_point_for_shared_arc_endpoint(self) -> None:
        rows = [
            {
                "type": "LINE",
                "layer": "IV_INTERIOR_PROFILES",
                "start": [0.0, 0.0],
                "end": [1.00000049, 0.0],
                "normalized_start": [0.0, 0.0],
                "normalized_end": [1.00000049, 0.0],
            },
            {
                "type": "ARC",
                "layer": "IV_INTERIOR_PROFILES",
                "center": [1.0, 0.5],
                "normalized_center": [1.0, 0.5],
                "radius": 0.5,
                "normalized_start_point": [1.0000003, 0.0],
                "normalized_end_point": [1.5, 0.5],
            },
        ]
        bounds = Bounds(min_x=0.0, min_y=0.0, max_x=1.5, max_y=0.5)

        snapped = _rows_with_topology_snapped_endpoints(rows, bounds, digits=6)

        self.assertEqual(snapped[0]["normalized_end"], [1.0, 0.0])
        self.assertEqual(snapped[1]["normalized_start_point"], [1.0, 0.0])

    def test_connected_line_profile_order_reverses_and_chains_segments(self) -> None:
        rows = [
            {
                "type": "LINE",
                "start": [0.0, 1.0],
                "end": [1.0, 1.0],
                "normalized_start": [0.0, 1.0],
                "normalized_end": [1.0, 1.0],
            },
            {
                "type": "LINE",
                "start": [0.0, 0.0],
                "end": [1.0, 0.0],
                "normalized_start": [0.0, 0.0],
                "normalized_end": [1.0, 0.0],
            },
            {
                "type": "LINE",
                "start": [1.0, 0.0],
                "end": [1.0, 1.0],
                "normalized_start": [1.0, 0.0],
                "normalized_end": [1.0, 1.0],
            },
            {
                "type": "LINE",
                "start": [0.0, 0.0],
                "end": [0.0, 1.0],
                "normalized_start": [0.0, 0.0],
                "normalized_end": [0.0, 1.0],
            },
        ]

        ordered, stats = _rows_with_connected_line_profiles(rows)

        self.assertTrue(stats["eligible"])
        self.assertTrue(stats["changed"])
        self.assertEqual(stats["chain_count"], 1)
        self.assertEqual(
            [(row["normalized_start"], row["normalized_end"]) for row in ordered],
            [
                ([0.0, 1.0], [1.0, 1.0]),
                ([1.0, 1.0], [1.0, 0.0]),
                ([1.0, 0.0], [0.0, 0.0]),
                ([0.0, 0.0], [0.0, 1.0]),
            ],
        )

    def test_collinear_normalization_merges_contiguous_same_pen_lines(self) -> None:
        rows = [
            {
                "type": "LINE",
                "layer": "IV_INTERIOR_PROFILES",
                "normalized_start": [0.0, 0.0],
                "normalized_end": [1.0, 0.0],
            },
            {
                "type": "LINE",
                "layer": "IV_INTERIOR_PROFILES",
                "normalized_start": [1.0, 0.0],
                "normalized_end": [3.0, 0.0],
            },
            {
                "type": "LINE",
                "layer": "IV_MARK_SURFACE",
                "normalized_start": [3.0, 0.0],
                "normalized_end": [4.0, 0.0],
            },
        ]

        normalized, stats = normalize_collinear_line_chains(rows, part_name="Part A")

        self.assertEqual(len(normalized), 2)
        self.assertEqual(normalized[0]["normalized_start"], [0.0, 0.0])
        self.assertEqual(normalized[0]["normalized_end"], [3.0, 0.0])
        self.assertEqual(stats["accepted_merge_count"], 1)
        self.assertEqual(stats["accepted_merges"][0]["part"], "Part A")
        self.assertEqual(stats["accepted_merges"][0]["original_entity_indexes"], [1, 2])
        self.assertEqual(stats["accepted_merges"][0]["new_endpoint"], [3.0, 0.0])
        self.assertEqual(stats["accepted_merges"][0]["layer"], "IV_INTERIOR_PROFILES")
        self.assertEqual(stats["accepted_merges"][0]["pen"], "1")
        self.assertEqual(stats["accepted_merges"][0]["reason"], "contiguous_same_pen_collinear_line_chain")
        self.assertAlmostEqual(stats["accepted_merges"][0]["total_length"], 3.0)
        self.assertAlmostEqual(stats["accepted_merges"][0]["max_deviation"], 0.0)

    def test_collinear_normalization_rejects_boundaries_and_bad_fragments(self) -> None:
        base = {
            "type": "LINE",
            "layer": "IV_INTERIOR_PROFILES",
            "normalized_start": [0.0, 0.0],
            "normalized_end": [1.0, 0.0],
        }
        cases = [
            (
                "layer_boundary",
                [
                    base,
                    {
                        "type": "LINE",
                        "layer": "IV_MARK_SURFACE",
                        "normalized_start": [1.0, 0.0],
                        "normalized_end": [2.0, 0.0],
                    },
                ],
            ),
            (
                "gap",
                [
                    base,
                    {
                        "type": "LINE",
                        "layer": "IV_INTERIOR_PROFILES",
                        "normalized_start": [1.01, 0.0],
                        "normalized_end": [2.0, 0.0],
                    },
                ],
            ),
            (
                "non_collinear",
                [
                    base,
                    {
                        "type": "LINE",
                        "layer": "IV_INTERIOR_PROFILES",
                        "normalized_start": [1.0, 0.0],
                        "normalized_end": [2.0, 0.1],
                    },
                ],
            ),
            (
                "backtracking_or_reversed",
                [
                    base,
                    {
                        "type": "LINE",
                        "layer": "IV_INTERIOR_PROFILES",
                        "normalized_start": [1.0, 0.0],
                        "normalized_end": [0.0, 0.0],
                    },
                ],
            ),
            (
                "zero_length",
                [
                    base,
                    {
                        "type": "LINE",
                        "layer": "IV_INTERIOR_PROFILES",
                        "normalized_start": [1.0, 0.0],
                        "normalized_end": [1.0, 0.0],
                    },
                ],
            ),
            (
                "entity_type_boundary",
                [
                    base,
                    {
                        "type": "ARC",
                        "layer": "IV_INTERIOR_PROFILES",
                        "normalized_start_point": [1.0, 0.0],
                        "normalized_end_point": [2.0, 0.0],
                    },
                ],
            ),
        ]

        for expected_reason, rows in cases:
            with self.subTest(expected_reason=expected_reason):
                normalized, stats = normalize_collinear_line_chains(rows)

                self.assertEqual(len(normalized), len(rows))
                self.assertEqual(stats["accepted_merge_count"], 0)
                if expected_reason == "entity_type_boundary":
                    self.assertEqual(stats["rejected_near_miss_count"], 0)
                elif expected_reason != "gap":
                    self.assertGreaterEqual(stats["rejected_near_miss_count"], 1)
                    self.assertEqual(stats["rejected_near_misses"][0]["reason"], expected_reason)

    def test_boundary_chain_normalization_merges_nonadjacent_axis_groups(self) -> None:
        rows = [
            {
                "type": "LINE",
                "layer": "IV_INTERIOR_PROFILES",
                "normalized_start": [0.0, 2.0],
                "normalized_end": [0.0, 3.0],
            },
            {
                "type": "LINE",
                "layer": "IV_MARK_SURFACE",
                "normalized_start": [1.0, 0.0],
                "normalized_end": [2.0, 0.0],
            },
            {
                "type": "LINE",
                "layer": "IV_INTERIOR_PROFILES",
                "normalized_start": [0.0, 0.0],
                "normalized_end": [0.0, 1.0],
            },
            {
                "type": "LINE",
                "layer": "IV_INTERIOR_PROFILES",
                "normalized_start": [0.0, 1.0],
                "normalized_end": [0.0, 2.0],
            },
        ]

        normalized, stats = normalize_collinear_boundary_chains(rows, min_source_count=3, part_name="Part A")

        self.assertEqual(len(normalized), 2)
        self.assertEqual(normalized[0]["normalized_start"], [0.0, 0.0])
        self.assertEqual(normalized[0]["normalized_end"], [0.0, 3.0])
        self.assertEqual(stats["accepted_merge_count"], 1)
        self.assertEqual(stats["accepted_merges"][0]["source_line_indices"], [1, 3, 4])
        self.assertEqual(stats["accepted_merges"][0]["replacement_line_index"], 1)
        self.assertEqual(stats["accepted_merges"][0]["orientation"], "V")
        self.assertEqual(stats["accepted_merges"][0]["reason"], "same_axis_boundary_collinear_line_chain")

    def test_low_y_rightmost_rotation_moves_closed_profile_start(self) -> None:
        rows = [
            {"type": "LINE", "normalized_start": [0.0, 1.0], "normalized_end": [1.0, 1.0]},
            {"type": "LINE", "normalized_start": [1.0, 1.0], "normalized_end": [1.0, 0.0]},
            {"type": "LINE", "normalized_start": [1.0, 0.0], "normalized_end": [0.0, 0.0]},
            {"type": "LINE", "normalized_start": [0.0, 0.0], "normalized_end": [0.0, 1.0]},
        ]

        rotated, stats = _rows_with_low_y_rightmost_line_profile_start(rows)

        self.assertTrue(stats["rotation_eligible"])
        self.assertTrue(stats["rotation_changed"])
        self.assertEqual(stats["rotation_start"], [1.0, 0.0])
        self.assertEqual(
            [(row["normalized_start"], row["normalized_end"]) for row in rotated],
            [
                ([1.0, 0.0], [0.0, 0.0]),
                ([0.0, 0.0], [0.0, 1.0]),
                ([0.0, 1.0], [1.0, 1.0]),
                ([1.0, 1.0], [1.0, 0.0]),
            ],
        )

    def test_canonicalized_line_delta_closes_on_encoded_endpoint_fraction(self) -> None:
        row = {
            "type": "LINE",
            "normalized_start": [0.158957, 4.218422],
            "normalized_end": [0.5, 4.218422],
        }

        tokens = encode_geometry_data(row, token_count=6, canonicalize_endpoints=True).split(".")
        start_x = decode_ddc_number_fraction(tokens[0])
        delta_x = decode_ddc_number_fraction(tokens[2])
        end_x = decode_ddc_number_fraction(
            encode_geometry_data(
                {"type": "LINE", "normalized_start": [0.5, 4.218422], "normalized_end": [0.5, 4.218422]},
                token_count=6,
                canonicalize_endpoints=True,
            ).split(".")[0]
        )

        self.assertEqual(start_x + delta_x, end_x)

    def test_symbol_view_extents_match_observed_radan_padding_rule(self) -> None:
        small = Bounds(min_x=0.0, min_y=0.0, max_x=24.0, max_y=3.68869)
        large = Bounds(min_x=0.0, min_y=0.0, max_x=114.0, max_y=35.68869)

        small_x, small_y = _symbol_view_extents(small)
        large_x, large_y = _symbol_view_extents(large)

        self.assertAlmostEqual(float(small_x), 99.318474, places=6)
        self.assertAlmostEqual(float(small_y), 70.228767, places=6)
        self.assertAlmostEqual(float(large_x), 342.0, places=6)
        self.assertAlmostEqual(float(large_y), 241.830521, places=5)

    def test_symbol_view_record_field_keeps_lower_left_origin_and_unit_scale(self) -> None:
        field = _symbol_view_record_field(
            Bounds(min_x=0.0, min_y=0.0, max_x=114.0, max_y=35.68869),
            part_name="B-185",
        )
        numeric_field, part_name = field.split("$", 1)
        tokens = numeric_field.split(".")

        self.assertEqual(part_name, "B-185")
        self.assertEqual(tokens[0], "")
        self.assertEqual(tokens[2], "")
        self.assertEqual(tokens[4], "")
        self.assertEqual(tokens[6], "")
        self.assertAlmostEqual(float(decode_ddc_number_fraction(tokens[1])), 342.0, places=6)
        self.assertAlmostEqual(float(decode_ddc_number_fraction(tokens[3])), 241.830521, places=5)
        self.assertAlmostEqual(float(decode_ddc_number_fraction(tokens[8])), 25.4, places=6)
        self.assertAlmostEqual(float(decode_ddc_number_fraction(tokens[9])), 1.0, places=6)
        self.assertAlmostEqual(float(decode_ddc_number_fraction(tokens[10])), 1.0, places=6)

    def test_symbol_view_record_field_uses_radan_float6_spelling(self) -> None:
        field = _symbol_view_record_field(
            Bounds(
                min_x=0.0,
                min_y=-16.42421867667253,
                max_x=80.68749999999999,
                max_y=32.72343735334496,
            ),
            part_name="B-37",
        )
        tokens = field.split("$", 1)[0].split(".")

        self.assertEqual(tokens[1], "6@>@P")
        self.assertEqual(tokens[3], "6@5ICo:QLZ`")
        self.assertEqual(tokens[5], "6@>@P")
        self.assertEqual(tokens[7], "6@5ICo:QLZ`")

    def test_refresh_symbol_metadata_attrs_updates_filename_and_bounding_box(self) -> None:
        text = """<RadanCompoundDocument>
<Attr num="110" name="File name" type="s" value="donor">
</Attr>
<Attr num="165" name="Bounding box X" type="r" value="1">
</Attr>
<Attr num="166" name="Bounding box Y" type="r" value="2">
</Attr>
</RadanCompoundDocument>"""

        refreshed = _refresh_symbol_metadata_attrs(
            text,
            bounds=Bounds(min_x=0.0, min_y=0.0, max_x=31.160938, max_y=10.098437),
            part_name="F54410-B-49",
        )

        self.assertIn('num="110" name="File name" type="s" value="F54410-B-49"', refreshed)
        self.assertIn('num="165" name="Bounding box X" type="r" value="31.160938"', refreshed)
        self.assertIn('num="166" name="Bounding box Y" type="r" value="10.098437"', refreshed)

    def test_blank_donor_template_gets_geometry_definitions_and_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            dxf_path = root / "Part A.dxf"
            template_path = root / "donor.sym"
            out_path = root / "Part A.sym"
            doc = ezdxf.new("R2010")
            msp = doc.modelspace()
            msp.add_line((0, 0, 0), (2, 0, 0), dxfattribs={"layer": "IV_INTERIOR_PROFILES"})
            doc.saveas(dxf_path)
            template_path.write_text(
                """<?xml version="1.0" encoding="UTF-8"?>
<RadanCompoundDocument>
  <RadanFile extension="ddc">
    <![CDATA[A,2,
B,D,>,,1,2,
B,E,],?,@,
D,-1,6,.5@8e67PaJPE..5@1SZ@NEmWL..5@8e67PaJPE..5@1SZ@NEmWL.3@9IVIVIVIV.o?0.o?0.$donor
E,,-1,1,,,,,,,1,1,1,,,1,1,o?0...o?0.........o?0.o?0.$/
C,$
U,,$
U,$
U,,,,2,,,,,,,
]]>
  </RadanFile>
</RadanCompoundDocument>
""",
                encoding="utf-8",
            )

            payload = write_native_prototype(
                dxf_path=dxf_path,
                template_sym=template_path,
                out_path=out_path,
                allow_outside_lab=True,
            )
            text = out_path.read_text(encoding="utf-8")

        self.assertEqual(payload["entity_count"], 1)
        self.assertEqual(payload["replaced_records"], 1)
        self.assertIn("A,3,", text)
        self.assertIn("B,G,", text)
        self.assertIn("D,-1,6,", text)
        self.assertIn("$Part A", text)
        self.assertIn("E,,-1,3,", text)
        self.assertIn("G,,1,3,,1,,,1,,", text)


if __name__ == "__main__":
    unittest.main()
