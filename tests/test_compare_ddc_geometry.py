from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import ezdxf

from compare_ddc_geometry import compare_part


def _write_line_dxf(path: Path) -> None:
    doc = ezdxf.new("R2010")
    doc.modelspace().add_line((0, 0, 0), (2, 0, 0), dxfattribs={"layer": "IV_INTERIOR_PROFILES"})
    doc.saveas(path)


def _write_sym(path: Path, geometry_data: str) -> None:
    path.write_text(
        f"""<?xml version="1.0" encoding="UTF-8"?>
<RadanCompoundDocument>
  <RadanFile extension="ddc"><![CDATA[
G,,1,3,,1,,,1,1,{geometry_data}
]]></RadanFile>
</RadanCompoundDocument>
""",
        encoding="utf-8",
    )


class CompareDdcGeometryTests(unittest.TestCase):
    def test_compare_part_reports_decoded_slot_differences(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            dxf_path = root / "Sample.dxf"
            oracle_sym = root / "Sample-oracle.sym"
            compare_sym = root / "Sample-compare.sym"
            _write_line_dxf(dxf_path)
            _write_sym(oracle_sym, "..0@0")
            _write_sym(compare_sym, "..0@0P")

            payload = compare_part(dxf_path, oracle_sym, compare_sym)

        self.assertEqual(payload["changed_geometry_records"], 1)
        self.assertEqual(payload["decoded_nonzero_diff_slots"], 1)
        line_delta_x = [
            row
            for row in payload["groups"]
            if row["record"] == "G" and row["dxf_type"] == "LINE" and row["slot"] == 2
        ][0]
        self.assertAlmostEqual(line_delta_x["max_abs_diff"], 0.0625)


if __name__ == "__main__":
    unittest.main()
