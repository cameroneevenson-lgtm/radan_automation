from __future__ import annotations

import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import import_parts_csv_headless


class ImportPartsCsvHeadlessTests(unittest.TestCase):
    def test_read_import_csv_parses_six_column_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            dxf_path = os.path.join(tmpdir, "Part A.dxf")
            csv_path = os.path.join(tmpdir, "parts_Radan.csv")
            with open(dxf_path, "w", encoding="utf-8") as handle:
                handle.write("dxf")
            with open(csv_path, "w", encoding="utf-8") as handle:
                handle.write(f"{dxf_path},2,Aluminum 5052,0.18,in,AIR\n")

            parts = import_parts_csv_headless.read_import_csv(import_parts_csv_headless.Path(csv_path))

        self.assertEqual(len(parts), 1)
        self.assertEqual(parts[0].part_name, "Part A")
        self.assertEqual(parts[0].quantity, 2)
        self.assertEqual(parts[0].material, "Aluminum 5052")
        self.assertEqual(parts[0].thickness, 0.18)
        self.assertEqual(parts[0].unit, "in")
        self.assertEqual(parts[0].strategy, "AIR")

    def test_read_import_csv_rejects_unsupported_units(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            dxf_path = os.path.join(tmpdir, "Part A.dxf")
            csv_path = os.path.join(tmpdir, "parts_Radan.csv")
            with open(dxf_path, "w", encoding="utf-8") as handle:
                handle.write("dxf")
            with open(csv_path, "w", encoding="utf-8") as handle:
                handle.write(f"{dxf_path},2,Aluminum 5052,0.18,cm,AIR\n")

            with self.assertRaisesRegex(ValueError, "unsupported thickness unit"):
                import_parts_csv_headless.read_import_csv(import_parts_csv_headless.Path(csv_path))

    def test_format_elapsed(self) -> None:
        self.assertEqual(import_parts_csv_headless._format_elapsed(4.25), "4.2s")
        self.assertEqual(import_parts_csv_headless._format_elapsed(65.5), "1m 5.5s")


if __name__ == "__main__":
    unittest.main()
