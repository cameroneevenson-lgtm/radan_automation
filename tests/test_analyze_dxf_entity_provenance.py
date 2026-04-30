from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

import ezdxf

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import analyze_dxf_entity_provenance as analyzer


def _write_arc(path: Path, *, center_x: float = 1.25, layer: str = "IV_INTERIOR_PROFILES") -> None:
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    msp.add_arc((center_x, 2.5), 3.0, 10.0, 170.0, dxfattribs={"layer": layer})
    doc.saveas(path)


class AnalyzeDxfEntityProvenanceTests(unittest.TestCase):
    def test_read_raw_dxf_entities_captures_salient_arc_groups(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "P1.dxf"
            _write_arc(path)

            rows = analyzer.read_raw_dxf_entities(path)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["type"], "ARC")
        self.assertEqual(rows[0]["layer"], "IV_INTERIOR_PROFILES")
        salient = {row["code"]: row["value"] for row in rows[0]["salient_groups"]}
        self.assertEqual(float(salient["10"]), 1.25)
        self.assertEqual(float(salient["40"]), 3.0)

    def test_compare_focus_entities_reports_salient_raw_difference(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write_arc(root / "P1.dxf", center_x=1.25)
            _write_arc(root / "P2.dxf", center_x=1.5)

            payload = analyzer.analyze_dxf_entity_provenance(
                dxf_folder=root,
                focuses=[],
                comparisons=[(("P1", 1), ("P2", 1))],
            )

        comparison = payload["comparisons"][0]
        self.assertTrue(comparison["same_type"])
        self.assertFalse(comparison["same_salient_raw_values"])
        self.assertFalse(comparison["same_salient_numeric_values"])
        self.assertTrue(any(diff["left"][0] == "10" for diff in comparison["salient_diffs"]))

    def test_output_guard_rejects_non_lab_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaises(RuntimeError):
                analyzer._assert_sym_lab_output(Path(tmpdir) / "out.json")


if __name__ == "__main__":
    unittest.main()
