from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

import ezdxf

import ddc_corpus


def _write_sample_dxf(path: Path) -> None:
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    msp.add_line((0, -1, 0), (2, -1, 0), dxfattribs={"layer": "IV_INTERIOR_PROFILES"})
    msp.add_circle((1, 0, 0), 0.5, dxfattribs={"layer": "IV_MARK_SURFACE"})
    doc.saveas(path)


def _write_sample_sym(path: Path) -> None:
    path.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<RadanCompoundDocument>
  <RadanFile extension="ddc">
    <![CDATA[A,2,
G,,1,A,,1,,,1,,line-token-a.line-token-b,.,,,
H,,1,B,,1,,,7,1,circle-token-a..circle-token-c,
]]>
  </RadanFile>
</RadanCompoundDocument>
""",
        encoding="utf-8",
    )


class DdcCorpusTests(unittest.TestCase):
    def test_read_ddc_records_extracts_geometry_tokens(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            sym_path = Path(tmpdir) / "Sample.sym"
            _write_sample_sym(sym_path)

            rows = ddc_corpus.read_ddc_records(sym_path)

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["record"], "G")
        self.assertEqual(rows[0]["identifier"], "A")
        self.assertEqual(rows[0]["pen"], "1")
        self.assertEqual(rows[0]["tokens"], ["line-token-a", "line-token-b"])
        self.assertEqual(rows[1]["tokens"], ["circle-token-a", "", "circle-token-c"])

    def test_build_part_corpus_pairs_dxf_and_ddc_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            dxf_path = root / "Sample.dxf"
            sym_path = root / "Sample.sym"
            _write_sample_dxf(dxf_path)
            _write_sample_sym(sym_path)

            payload = ddc_corpus.build_part_corpus(dxf_path, sym_path)

        self.assertEqual(payload["part"], "Sample")
        self.assertEqual(payload["dxf_count"], 2)
        self.assertEqual(payload["ddc_count"], 2)
        self.assertTrue(payload["count_match"])
        self.assertEqual(payload["type_mismatch_count"], 0)
        self.assertEqual(payload["known_pen_mismatch_count"], 0)
        self.assertEqual(payload["bounds"]["min_y"], -1.0)
        self.assertEqual(payload["bounds"]["height"], 1.5)
        self.assertEqual(payload["pairs"][0]["dxf"]["normalized_start"], [0.0, 0.0])
        self.assertEqual(payload["pairs"][0]["dxf"]["normalized_end"], [2.0, 0.0])
        self.assertEqual(payload["pairs"][1]["dxf"]["normalized_center"], [1.0, 1.0])

    def test_build_corpus_summarizes_csv(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            dxf_path = root / "Sample.dxf"
            sym_folder = root / "symbols"
            sym_path = sym_folder / "Sample.sym"
            csv_path = root / "parts.csv"
            sym_folder.mkdir()
            _write_sample_dxf(dxf_path)
            _write_sample_sym(sym_path)
            with csv_path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow([str(dxf_path), "1", "Aluminum 5052", "0.125", "in", "AIR"])

            payload = ddc_corpus.build_corpus(csv_path, sym_folder)

        self.assertEqual(payload["part_count"], 1)
        self.assertEqual(payload["total_dxf_entities"], 2)
        self.assertEqual(payload["total_ddc_records"], 2)
        self.assertEqual(payload["count_mismatches"], [])
        self.assertEqual(payload["type_mismatches"], [])
        self.assertEqual(payload["known_pen_mismatches"], [])
        self.assertEqual(
            payload["layer_record_pen_counts"],
            [
                {
                    "count": 1,
                    "dxf_layer": "IV_INTERIOR_PROFILES",
                    "dxf_type": "LINE",
                    "ddc_pen": "1",
                    "ddc_record": "G",
                },
                {
                    "count": 1,
                    "dxf_layer": "IV_MARK_SURFACE",
                    "dxf_type": "CIRCLE",
                    "ddc_pen": "7",
                    "ddc_record": "H",
                },
            ],
        )


if __name__ == "__main__":
    unittest.main()
