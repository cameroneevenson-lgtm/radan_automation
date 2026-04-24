from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from remap_feature_pens_file import remap_file


SAMPLE = """<?xml version="1.0" encoding="UTF-8"?>
<RadanCompoundDocument>
  <RadanFile extension="ddc">
    <![CDATA[A,5,
G,,1,A,,1,,,7,,line-data,.,,,
G,,1,B,,1,,,1,,line-data,.,,,
H,,1,C,,1,,,7,1,arc-data,
H,,1,D,,1,,,1,1,arc-data,
N,,-1,I2,,_,$2026-04-24.15-18-30 GMT
]]>
  </RadanFile>
</RadanCompoundDocument>
"""


class RemapFeaturePensFileTests(unittest.TestCase):
    def test_remaps_line_and_arc_records_in_ddc_block(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "part.sym"
            path.write_text(SAMPLE, encoding="utf-8")

            result = remap_file(path, backup_suffix=".bak")

            self.assertTrue(result["write_ok"])
            self.assertEqual(result["changed"], {"l": 1, "a": 1})
            self.assertTrue(result["requires_radan_resave"])
            self.assertIn("cached thumbnails", result["refresh_note"])
            self.assertIn("do not spoof Workflow status", result["refresh_note"])
            self.assertEqual(result["after"]["l"]["pens"], {"1": 1, "5": 1})
            self.assertEqual(result["after"]["a"]["pens"], {"1": 1, "9": 1})
            self.assertTrue((Path(str(path) + ".bak")).exists())
            text = path.read_text(encoding="utf-8")
            self.assertIn("G,,1,A,,1,,,5,,line-data", text)
            self.assertIn("H,,1,C,,1,,,9,1,arc-data", text)

    def test_dry_run_does_not_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "part.sym"
            path.write_text(SAMPLE, encoding="utf-8")

            result = remap_file(path, dry_run=True, backup_suffix=".bak")

            self.assertFalse(result["write_ok"])
            self.assertEqual(result["changed_total"], 2)
            self.assertTrue(result["requires_radan_resave"])
            self.assertEqual(path.read_text(encoding="utf-8"), SAMPLE)
            self.assertFalse((Path(str(path) + ".bak")).exists())

    def test_preserves_existing_crlf_line_endings(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "part.sym"
            crlf_sample = SAMPLE.replace("\n", "\r\n")
            with path.open("w", encoding="utf-8", newline="") as handle:
                handle.write(crlf_sample)

            remap_file(path)

            raw = path.read_bytes()
            self.assertIn(b"\r\n", raw)
            self.assertEqual(raw.count(b"\r\n"), crlf_sample.count("\r\n"))
            self.assertEqual(raw.count(b"\n"), raw.count(b"\r\n"))


if __name__ == "__main__":
    unittest.main()
