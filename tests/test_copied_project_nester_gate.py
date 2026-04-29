from __future__ import annotations

import os
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import copied_project_nester_gate as gate


def _write_project(path: Path) -> None:
    path.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<RadanProject xmlns="http://www.radan.com/ns/project">\n'
        '  <JobName>F54410 PAINT PACK</JobName>\n'
        '  <Parts>\n'
        '    <NextID>22</NextID>\n'
        '    <Part><ID>21</ID><Symbol>old.sym</Symbol><Made>1</Made></Part>\n'
        '  </Parts>\n'
        '  <Sheets>\n'
        '    <NextID>6</NextID>\n'
        '    <Sheet><ID>5</ID><Made>0</Made></Sheet>\n'
        '  </Sheets>\n'
        '  <Nests>\n'
        '    <NextNestNum>15</NextNestNum>\n'
        '    <Nest><Made>0</Made></Nest>\n'
        '  </Nests>\n'
        '</RadanProject>\n',
        encoding="utf-8",
    )


class CopiedProjectNesterGateTests(unittest.TestCase):
    def test_assert_lab_output_path_rejects_paths_outside_lab_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            lab_root = Path(tmpdir) / "_sym_lab"
            outside = Path(tmpdir) / "elsewhere" / "result.json"

            with self.assertRaisesRegex(RuntimeError, "outside lab root"):
                gate.assert_lab_output_path(outside, lab_root=lab_root)

    def test_prepare_copied_project_clears_parts_and_sheets_but_preserves_nests(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "source.rpd"
            copied = Path(tmpdir) / "_sym_lab" / "run" / "copied.rpd"
            _write_project(source)

            with mock.patch.object(gate, "DEFAULT_LAB_ROOT", Path(tmpdir) / "_sym_lab"):
                snapshot = gate.prepare_copied_project(source, copied, label="LAB")

            self.assertEqual(snapshot["part_count"], 0)
            self.assertEqual(snapshot["sheet_count"], 0)
            self.assertEqual(snapshot["nest_count"], 1)
            root = ET.parse(copied).getroot()
            self.assertIn("LAB", root.find(f".//{{{gate.RADAN_PROJECT_NS}}}JobName").text)
            self.assertEqual(root.find(f".//{{{gate.RADAN_PROJECT_NS}}}Parts/{{{gate.RADAN_PROJECT_NS}}}NextID").text, "1")

    def test_select_parts_applies_include_exclude_and_limit(self) -> None:
        parts = [
            SimpleNamespace(part_name="B-10"),
            SimpleNamespace(part_name="B-14"),
            SimpleNamespace(part_name="F54410-B-49"),
            SimpleNamespace(part_name="F54410-B-17"),
        ]

        selected, missing = gate.select_parts(
            parts,
            include_parts=["B-10", "B-14", "F54410-B-17", "Missing"],
            exclude_parts=["F54410-B-17"],
            max_parts=1,
        )

        self.assertEqual([part.part_name for part in selected], ["B-10"])
        self.assertEqual(missing, ["f54410-b-17", "missing"])

    def test_project_snapshot_counts_made_and_next_nest_num(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir) / "job.rpd"
            _write_project(project)

            snapshot = gate.project_snapshot(project)

        self.assertEqual(snapshot["part_count"], 1)
        self.assertEqual(snapshot["sheet_count"], 1)
        self.assertEqual(snapshot["nest_count"], 1)
        self.assertEqual(snapshot["made_nonzero_count"], 1)
        self.assertEqual(snapshot["next_nest_num"], ["15"])

    def test_run_gate_writes_error_result_when_requested_part_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            lab_root = root / "_sym_lab"
            source = root / "source.rpd"
            csv_path = root / "parts_Radan.csv"
            symbol_folder = root / "symbols"
            out_dir = lab_root / "run"
            dxf_path = root / "B-10.dxf"
            _write_project(source)
            dxf_path.write_text("dxf", encoding="utf-8")
            symbol_folder.mkdir()
            (symbol_folder / "B-10.sym").write_text("sym", encoding="utf-8")
            csv_path.write_text(f"{dxf_path},1,Aluminum 5052,0.18,in,AIR\n", encoding="utf-8")

            with mock.patch.object(gate, "DEFAULT_LAB_ROOT", lab_root):
                with self.assertRaisesRegex(RuntimeError, "Requested part"):
                    gate.run_gate(
                        source_rpd=source,
                        csv_path=csv_path,
                        symbol_folder=symbol_folder,
                        out_dir=out_dir,
                        label="missing",
                        include_parts=["Nope"],
                    )


if __name__ == "__main__":
    unittest.main()
