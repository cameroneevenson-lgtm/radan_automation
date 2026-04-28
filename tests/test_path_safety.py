from __future__ import annotations

import unittest
from pathlib import Path

from path_safety import assert_w_drive_write_allowed, is_owned_inventor_output, is_w_drive_path


class PathSafetyTests(unittest.TestCase):
    def test_detects_w_drive_paths(self) -> None:
        self.assertTrue(is_w_drive_path(r"W:\LASER\part.dxf"))
        self.assertTrue(is_w_drive_path(r"\\?\W:\LASER\part.dxf"))
        self.assertFalse(is_w_drive_path(r"L:\BATTLESHIELD\part.sym"))
        self.assertFalse(is_w_drive_path(Path(r"C:\Tools\radan_automation\_sym_lab\part.dxf")))

    def test_blocks_w_drive_write_by_default(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "Refusing to write cleaned DXF on W:"):
            assert_w_drive_write_allowed(r"W:\LASER\part-cleaned.dxf", operation="write cleaned DXF")

    def test_allows_owned_inventor_handoff_files_when_explicit(self) -> None:
        spreadsheet = r"W:\LASER\TruckBom.xlsx"
        self.assertTrue(is_owned_inventor_output(r"W:\LASER\TruckBom_Radan.csv", spreadsheet_path=spreadsheet))
        self.assertTrue(is_owned_inventor_output(r"W:\LASER\TruckBom_report.txt", spreadsheet_path=spreadsheet))

        assert_w_drive_write_allowed(
            r"W:\LASER\TruckBom_Radan.csv",
            operation="move Inventor output",
            allow_owned_inventor_output=True,
            spreadsheet_path=spreadsheet,
        )

    def test_rejects_non_matching_inventor_exception(self) -> None:
        with self.assertRaises(RuntimeError):
            assert_w_drive_write_allowed(
                r"W:\LASER\Different_Radan.csv",
                operation="move Inventor output",
                allow_owned_inventor_output=True,
                spreadsheet_path=r"W:\LASER\TruckBom.xlsx",
            )


if __name__ == "__main__":
    unittest.main()
