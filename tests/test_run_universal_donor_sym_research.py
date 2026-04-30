from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import ezdxf

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import run_universal_donor_sym_research as research


def _write_line_dxf(path: Path) -> None:
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    msp.add_line((0, 0, 0), (2, 0, 0), dxfattribs={"layer": "IV_INTERIOR_PROFILES"})
    doc.saveas(path)


def _write_two_fragment_line_dxf(path: Path) -> None:
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    msp.add_line((0, 0, 0), (1, 0, 0), dxfattribs={"layer": "IV_INTERIOR_PROFILES"})
    msp.add_line((1, 0, 0), (2, 0, 0), dxfattribs={"layer": "IV_INTERIOR_PROFILES"})
    doc.saveas(path)


def _write_blank_donor(path: Path) -> None:
    path.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<RadanCompoundDocument>
  <Attr num="110" name="File name" type="s" value="donor">
  </Attr>
  <Attr num="165" name="Bounding box X" type="r" value="0">
  </Attr>
  <Attr num="166" name="Bounding box Y" type="r" value="0">
  </Attr>
  <Attr num="119" name="Material" type="s" value="-">
  </Attr>
  <Attr num="120" name="Thickness" type="r" value="0.1">
  </Attr>
  <Attr num="121" name="Thickness units" type="s" value="mm">
  </Attr>
  <Attr num="146" name="Strategy" type="s" value="">
  </Attr>
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


class UniversalDonorSymResearchTests(unittest.TestCase):
    def test_default_donor_exists_and_is_blank_style(self) -> None:
        donor = research.ensure_blank_universal_donor(research.DEFAULT_DONOR_SYM)

        self.assertEqual(donor["attr_110"], "donor")
        self.assertEqual(donor["geometry_record_count"], 0)
        self.assertEqual(donor["ddc_record_counts"].get("D"), 1)
        self.assertEqual(donor["ddc_record_counts"].get("E"), 1)
        self.assertEqual(donor["ddc_record_counts"].get("U"), 3)

    def test_missing_donor_fails_clearly(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            missing = Path(tmpdir) / "missing.sym"

            with self.assertRaisesRegex(FileNotFoundError, "Universal donor SYM not found"):
                research.ensure_blank_universal_donor(missing)

    def test_donor_with_geometry_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            donor = Path(tmpdir) / "donor.sym"
            _write_blank_donor(donor)
            text = donor.read_text(encoding="utf-8").replace("C,$", "G,,1,3,,1,,,1,,o?0.o?0.o?0.o?0.............,.,,,\nC,$")
            donor.write_text(text, encoding="utf-8")

            with self.assertRaisesRegex(RuntimeError, "no G/H geometry records"):
                research.ensure_blank_universal_donor(donor)

    def test_lab_path_guard_rejects_non_lab_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            lab_root = Path(tmpdir) / "_sym_lab"
            outside = Path(tmpdir) / "outside" / "run"

            with mock.patch.object(research, "DEFAULT_LAB_ROOT", lab_root):
                with self.assertRaisesRegex(RuntimeError, "outside lab root"):
                    research.generate_symbols_from_universal_donor(
                        csv_path=Path(tmpdir) / "parts.csv",
                        donor_sym=Path(tmpdir) / "donor.sym",
                        out_dir=outside,
                    )

    def test_generates_symbols_from_only_universal_donor_and_records_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            lab_root = root / "_sym_lab"
            out_dir = lab_root / "run"
            donor = root / "donor.sym"
            dxf = root / "Part A.dxf"
            csv_path = root / "parts_Radan.csv"
            symbol_dir = out_dir / "symbols"
            per_part_template = symbol_dir / "Part A.sym"
            _write_blank_donor(donor)
            _write_line_dxf(dxf)
            csv_path.write_text(f"{dxf},1,Aluminum 5052,0.18,in,AIR\n", encoding="utf-8")
            symbol_dir.mkdir(parents=True)
            per_part_template.write_text("not a usable per-part template", encoding="utf-8")

            with mock.patch.object(research, "DEFAULT_LAB_ROOT", lab_root):
                payload = research.generate_symbols_from_universal_donor(
                    csv_path=csv_path,
                    donor_sym=donor,
                    out_dir=out_dir,
                    include_parts=["Part A"],
                    label="unit_test",
                )

            generated_text = per_part_template.read_text(encoding="utf-8")
            manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["generated_count"], 1)
        self.assertEqual(payload["rows"][0]["template_source"], research.TEMPLATE_SOURCE)
        self.assertEqual(manifest["rows"][0]["template_source"], research.TEMPLATE_SOURCE)
        self.assertEqual(payload["writer_options"]["source_coordinate_digits"], 6)
        self.assertTrue(payload["writer_options"]["topology_snap_endpoints"])
        self.assertTrue(payload["writer_options"]["canonicalize_endpoints"])
        self.assertFalse(payload["writer_options"]["h_delta_repair_zero"])
        self.assertTrue(payload["writer_options"]["order_connected_line_profiles"])
        self.assertFalse(payload["writer_options"]["rotate_connected_line_profile_start"])
        self.assertTrue(payload["rows"][0]["bom_metadata"]["all_present"])
        self.assertEqual(payload["rows"][0]["bom_metadata"]["requested"]["119"], "Aluminum 5052")
        self.assertEqual(payload["rows"][0]["bom_metadata"]["requested"]["120"], "0.18")
        self.assertEqual(payload["rows"][0]["bom_metadata"]["requested"]["121"], "in")
        self.assertEqual(payload["rows"][0]["bom_metadata"]["requested"]["146"], "AIR")
        self.assertEqual(payload["rows"][0]["output_attr_110"], "Part A")
        self.assertFalse(payload["rows"][0]["retained_donor_attr_110"])
        self.assertEqual(payload["rows"][0]["entity_count"], 1)
        self.assertEqual(payload["rows"][0]["generated_geometry_records"], 1)
        self.assertTrue(payload["rows"][0]["line_profile_ordering"]["eligible"])
        self.assertTrue(payload["rows"][0]["unordered_line_geometry"]["passed"])
        self.assertIn("B,G,", generated_text)
        self.assertIn("G,,1,3,,1,,,1,,", generated_text)
        self.assertIn('num="119" name="Material" type="s" value="Aluminum 5052"', generated_text)
        self.assertIn('num="120" name="Thickness" type="r" value="0.18"', generated_text)
        self.assertIn('num="121" name="Thickness units" type="s" value="in"', generated_text)
        self.assertIn('num="146" name="Strategy" type="s" value="AIR"', generated_text)
        self.assertNotIn('value="donor"', generated_text)

    def test_writer_options_are_recorded_and_disable_line_ordering(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            lab_root = root / "_sym_lab"
            out_dir = lab_root / "run"
            donor = root / "donor.sym"
            dxf = root / "Part A.dxf"
            csv_path = root / "parts_Radan.csv"
            _write_blank_donor(donor)
            _write_line_dxf(dxf)
            csv_path.write_text(f"{dxf},1,Aluminum 5052,0.18,in,AIR\n", encoding="utf-8")

            with mock.patch.object(research, "DEFAULT_LAB_ROOT", lab_root):
                payload = research.generate_symbols_from_universal_donor(
                    csv_path=csv_path,
                    donor_sym=donor,
                    out_dir=out_dir,
                    include_parts=["Part A"],
                    label="unit_test",
                    writer_options={
                        "source_coordinate_digits": None,
                        "topology_snap_endpoints": False,
                        "canonicalize_endpoints": False,
                        "order_connected_line_profiles": False,
                        "rotate_connected_line_profile_start": False,
                    },
                )

        self.assertTrue(payload["ok"])
        self.assertIsNone(payload["writer_options"]["source_coordinate_digits"])
        self.assertFalse(payload["writer_options"]["topology_snap_endpoints"])
        self.assertFalse(payload["writer_options"]["canonicalize_endpoints"])
        self.assertFalse(payload["writer_options"]["order_connected_line_profiles"])
        self.assertFalse(payload["writer_options"]["rotate_connected_line_profile_start"])
        self.assertFalse(payload["rows"][0]["line_profile_ordering"]["eligible"])
        self.assertTrue(payload["rows"][0]["unordered_line_geometry"]["passed"])

    def test_collinear_normalization_manifest_is_recorded_and_allows_row_count_change(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            lab_root = root / "_sym_lab"
            out_dir = lab_root / "run"
            donor = root / "donor.sym"
            dxf = root / "Part A.dxf"
            csv_path = root / "parts_Radan.csv"
            _write_blank_donor(donor)
            _write_two_fragment_line_dxf(dxf)
            csv_path.write_text(f"{dxf},1,Aluminum 5052,0.18,in,AIR\n", encoding="utf-8")

            with mock.patch.object(research, "DEFAULT_LAB_ROOT", lab_root):
                payload = research.generate_symbols_from_universal_donor(
                    csv_path=csv_path,
                    donor_sym=donor,
                    out_dir=out_dir,
                    include_parts=["Part A"],
                    label="unit_test",
                    writer_options={"normalize_collinear_line_chains": True},
                )

            combined = json.loads((out_dir / "collinear_normalization_manifest.json").read_text(encoding="utf-8"))

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["rows"][0]["source_entity_count"], 2)
        self.assertEqual(payload["rows"][0]["entity_count"], 1)
        self.assertEqual(payload["rows"][0]["generated_geometry_records"], 1)
        self.assertFalse(payload["rows"][0]["validation_passed"])
        self.assertEqual(payload["rows"][0]["collinear_normalization"]["accepted_merge_count"], 1)
        self.assertEqual(combined["parts"][0]["normalization"]["accepted_merge_count"], 1)

    def test_ladder_rung_resolves_proven95_excludes(self) -> None:
        resolved = research.apply_ladder_rung(
            "proven95",
            label="universal_donor",
            include_parts=[],
            exclude_parts=[],
            max_parts=None,
        )

        self.assertEqual(tuple(resolved["exclude_parts"]), research.DEFAULT_OVERSIZED_EXCLUDES)
        self.assertIsNone(resolved["max_parts"])
        self.assertIn("proven95", resolved["label"])


if __name__ == "__main__":
    unittest.main()
