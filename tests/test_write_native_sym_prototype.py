from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import ezdxf
from ddc_corpus import Bounds
from ddc_number_codec import decode_ddc_number_fraction
from write_native_sym_prototype import (
    _rows_with_rounded_source_coordinates,
    _rows_with_topology_snapped_endpoints,
    encode_geometry_data,
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
