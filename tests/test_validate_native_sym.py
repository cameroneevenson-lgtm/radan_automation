from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import ezdxf

from validate_native_sym import validate_native_sym


def _write_dxf(path: Path) -> None:
    doc = ezdxf.new("R2010")
    doc.modelspace().add_line((0, 0, 0), (2, 0, 0), dxfattribs={"layer": "IV_INTERIOR_PROFILES"})
    doc.saveas(path)


def _write_sym(path: Path) -> None:
    path.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<RadanCompoundDocument>
  <RadanFile extension="ddc">
    <![CDATA[A,1,
G,,1,A,,1,,,1,,..0@0..............,.,,,
]]>
  </RadanFile>
</RadanCompoundDocument>
""",
        encoding="utf-8",
    )


class ValidateNativeSymTests(unittest.TestCase):
    def test_validate_native_sym_passes_decoded_geometry(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            dxf = root / "Part.dxf"
            sym = root / "Part.sym"
            _write_dxf(dxf)
            _write_sym(sym)

            payload = validate_native_sym(dxf_path=dxf, sym_path=sym)

        self.assertTrue(payload["passed"])
        self.assertEqual(payload["tiers"][0]["name"], "record_count")
        self.assertTrue(payload["tiers"][-1]["passed"])


if __name__ == "__main__":
    unittest.main()
