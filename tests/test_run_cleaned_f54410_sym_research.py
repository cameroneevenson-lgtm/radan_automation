from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from run_cleaned_f54410_sym_research import (
    CsvPartRow,
    _killable,
    build_oracle_index,
    ensure_cleaned_dxf,
    write_cleaned_import_csv,
    write_json_file,
)


class CleanedF54410SymResearchTests(unittest.TestCase):
    def test_cleaned_csv_rewrites_first_column_and_preserves_remaining_columns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_path = Path(tmp) / "cleaned.csv"
            parts = [
                CsvPartRow(
                    part_name="B-1",
                    raw_dxf_path=Path(r"W:\source\B-1.dxf"),
                    columns=[r"W:\source\B-1.dxf", "2", "MS", "0.125", "IN", "strategy"],
                )
            ]
            manifest_by_part = {
                "B-1": {
                    "cleaned_dxf_path": str(Path(tmp) / "_preprocessed_dxfs" / "B-1_outer_cleaned_tol002.dxf")
                }
            }

            write_cleaned_import_csv(parts, manifest_by_part, out_path)

            with out_path.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.reader(handle))
            self.assertEqual(rows[0][0], manifest_by_part["B-1"]["cleaned_dxf_path"])
            self.assertEqual(rows[0][1:], ["2", "MS", "0.125", "IN", "strategy"])

    def test_fallback_copies_raw_dxf_when_cleaner_does_not_write_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw = root / "raw" / "B-2.dxf"
            cleaned = root / "project" / "_preprocessed_dxfs" / "B-2_outer_cleaned_tol002.dxf"
            report = cleaned.with_suffix(".report.json")
            raw.parent.mkdir(parents=True)
            raw.write_text("raw dxf body", encoding="utf-8")
            part = CsvPartRow(part_name="B-2", raw_dxf_path=raw, columns=[str(raw), "1"])

            def fake_entities(path: Path):
                return ([{"type": "LINE", "layer": "IV_OUTER_PROFILE"}], None)

            with patch(
                "run_cleaned_f54410_sym_research.preprocessed_output_paths",
                return_value=(cleaned, report),
            ), patch(
                "run_cleaned_f54410_sym_research.clean_outer_profile",
                return_value={
                    "dxf_path": str(raw),
                    "out_path": str(cleaned),
                    "wrote_output": False,
                    "skipped_write_reason": "unsupported geometry",
                },
            ), patch("run_cleaned_f54410_sym_research.read_dxf_entities", side_effect=fake_entities):
                manifest = ensure_cleaned_dxf(part, project_folder=root / "project", tolerance=0.002)

            self.assertTrue(cleaned.exists())
            self.assertEqual(cleaned.read_text(encoding="utf-8"), "raw dxf body")
            self.assertTrue(manifest["fallback_copied_original"])
            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertTrue(payload["fallback_copied_original"])
            self.assertEqual(payload["fallback_reason"], "unsupported geometry")

    def test_write_json_refuses_w_drive(self) -> None:
        with self.assertRaises(RuntimeError):
            write_json_file(Path(r"W:\LASER\forbidden.json"), {"blocked": True})

    def test_title_only_radan_browser_match_is_not_killable(self) -> None:
        processes = [
            {
                "Id": 100,
                "ProcessName": "msedge",
                "Path": r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                "MainWindowTitle": "Reverse Engineering Radan Files - Microsoft Edge",
            },
            {
                "Id": 101,
                "ProcessName": "RADRAFT",
                "Path": r"C:\Program Files\Mazak\Mazak\bin\RADRAFT.exe",
                "MainWindowTitle": "",
            },
        ]

        self.assertEqual([process["Id"] for process in _killable(processes)], [101])

    def test_oracle_index_excludes_synthetic_and_donor_sources(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            l_side = root / "L-side"
            lab_root = root / "_sym_lab"
            out_dir = root / "run"
            l_side.mkdir()
            (l_side / "PartA.sym").write_text("top level", encoding="utf-8")
            synthetic = lab_root / "radan_known_good_synthetic"
            synthetic.mkdir(parents=True)
            (synthetic / "PartB.sym").write_text("synthetic", encoding="utf-8")
            known_good = lab_root / "f54410_radan_known_good_20260428"
            known_good.mkdir(parents=True)
            (known_good / "PartA.sym").write_text("known good", encoding="utf-8")
            (known_good / "donor.sym").write_text("donor", encoding="utf-8")

            manifest_rows = [
                {"part_name": "PartA", "cleaned_dxf_path": str(root / "PartA_cleaned.dxf")},
                {"part_name": "PartB", "cleaned_dxf_path": str(root / "PartB_cleaned.dxf")},
                {"part_name": "donor", "cleaned_dxf_path": str(root / "donor_cleaned.dxf")},
            ]

            index, copied_folder = build_oracle_index(
                manifest_rows,
                l_side_symbol_folder=l_side,
                lab_root=lab_root,
                out_dir=out_dir,
            )

            self.assertTrue(index["PartA"]["has_oracle"])
            self.assertEqual(Path(index["PartA"]["oracle_sym_path"]), known_good / "PartA.sym")
            self.assertEqual((copied_folder / "PartA_cleaned.sym").read_text(encoding="utf-8"), "known good")
            self.assertFalse(index["PartB"]["has_oracle"])
            self.assertFalse(index["donor"]["has_oracle"])


if __name__ == "__main__":
    unittest.main()
