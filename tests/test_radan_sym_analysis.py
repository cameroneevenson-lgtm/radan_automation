from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from radan_sym_analysis import build_sym_index, diff_sym_sections, summarize_sym


def _write_sym(
    path: Path,
    *,
    name: str,
    created: str = "2026-04-29T10:00:00-04:00",
    file_size: str = "1234",
    material: str = "Aluminum 5052",
    ddc_geometry: str = "G,,1,A,,1,,,1,1,o?0..0@0.,",
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"""<?xml version="1.0" encoding="UTF-8"?>
<RadanCompoundDocument xmlns="http://www.radan.com/ns/rcd">
  <RadanAttributes>
    <Group class="system" name="File">
      <Attr num="101" name="Created" type="t" value="{created}"/>
      <Attr num="103" name="File size" type="i" value="{file_size}"/>
      <Attr num="110" name="File name" type="s" value="{name}"/>
    </Group>
    <Group class="custom" name="Manufacturing">
      <Attr num="119" name="Material" type="s" value="{material}"/>
    </Group>
  </RadanAttributes>
  <RadanFile extension="ddc">
    <![CDATA[A,1,
B,G,N,?,@,E1,R1,J,V,W,I,l1,O,P,Q,R,V1,W1,A2,B2,C2,D2,E2,F2,G2,H2,O2,P2,Q2,R2,W2,[2,\\2,
{ddc_geometry}
]]>
  </RadanFile>
  <History>
    <![CDATA[history payload]]>
  </History>
</RadanCompoundDocument>
""",
        encoding="utf-8",
    )


class RadanSymAnalysisTests(unittest.TestCase):
    def test_summarize_sym_classifies_l_side_as_safe_oracle(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            sym_path = root / "part.sym"
            _write_sym(sym_path, name="B-10")

            summary = summarize_sym(sym_path)

        self.assertEqual(summary["classification"], "unknown")
        self.assertFalse(summary["safe_oracle"])
        self.assertEqual(summary["ddc_record_count"], 1)
        self.assertEqual(summary["ddc_type_counts"], {"G": 1})
        self.assertEqual(summary["attr_110_file_name"], "B-10")

    def test_build_index_excludes_donor_and_synthetic_from_safe_oracles(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            good = root / "L" / "B-10.sym"
            donor = root / "donor.sym"
            synthetic = root / "_sym_lab" / "synthetic_source_round6_full_20260427" / "B-10.sym"
            _write_sym(good, name="B-10")
            _write_sym(donor, name="donor")
            _write_sym(synthetic, name="B-10")

            payload = build_sym_index([root])

        self.assertEqual(payload["symbol_count"], 3)
        by_name = {Path(row["path"]).name + ":" + row["classification"]: row for row in payload["symbols"]}
        self.assertFalse(by_name["donor.sym:donor"]["safe_oracle"])
        self.assertFalse(by_name["B-10.sym:synthetic"]["safe_oracle"])

    def test_diff_sym_sections_localizes_ddc_geometry_difference(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            good = root / "good.sym"
            compare = root / "compare.sym"
            _write_sym(good, name="B-10", created="2026-04-29T10:00:00-04:00", file_size="1000")
            _write_sym(
                compare,
                name="B-10",
                created="2026-04-29T10:01:00-04:00",
                file_size="1001",
                ddc_geometry="G,,1,A,,1,,,1,1,o?0..0@4.,",
            )

            payload = diff_sym_sections(good, compare)

        self.assertEqual(payload["difference_localization"], "ddc_geometry_difference")
        self.assertFalse(payload["section_equalities"]["ddc_geometry_lines"])
        self.assertTrue(payload["section_equalities"]["normalized_wrapper_without_ddc_or_history"])
        self.assertEqual(payload["ddc_comparison"]["paired_record_count"], 1)
        self.assertEqual(payload["ddc_comparison"]["exact_geometry_data_matches"], 0)


if __name__ == "__main__":
    unittest.main()
