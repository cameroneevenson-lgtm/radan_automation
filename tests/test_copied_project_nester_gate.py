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


def _write_compare_rpd(path: Path, label: str, sym_folder: str, *, second_part: str = "B-184") -> None:
    path.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<RadanProject xmlns="http://www.radan.com/ns/project">\n'
        '  <Nests>\n'
        f'    <Nest><FileName>P15 F54410 PAINT PACK.{label}.drg</FileName><ID>15</ID>\n'
        '      <SheetUsed><Used>1</Used><Material>Aluminum 5052</Material><Thickness>0.25</Thickness>'
        '<SheetX>120</SheetX><SheetY>60</SheetY></SheetUsed>\n'
        '      <PartsMade>\n'
        f'        <PartMade><File>C:\\lab\\{sym_folder}\\B-10.sym</File><Made>2</Made></PartMade>\n'
        f'        <PartMade><File>C:\\lab\\{sym_folder}\\{second_part}.sym</File><Made>4</Made></PartMade>\n'
        '      </PartsMade>\n'
        '    </Nest>\n'
        '  </Nests>\n'
        '</RadanProject>\n',
        encoding="utf-8",
    )


def _write_compare_drg(path: Path, label: str, sym_folder: str, *, second_part: str = "B-184") -> None:
    path.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<RadanCompoundDocument>\n'
        f'  <Attr name="Drawing" value="P15 F54410 PAINT PACK.{label}"/>\n'
        '  <RadanFile extension="ddc"><![CDATA[\n'
        f'U,,$C:\\lab\\{sym_folder}\\B-10.sym\n'
        f'U,,$C:\\lab\\{sym_folder}\\{second_part}.sym\n'
        '  ]]></RadanFile>\n'
        f'  <Info num="4" name="Contained Symbols"><Symbol name="B-10" count="2"/><Symbol name="{second_part}" count="4"/></Info>\n'
        '</RadanCompoundDocument>\n',
        encoding="utf-8",
    )


class CopiedProjectNesterGateTests(unittest.TestCase):
    def test_assert_lab_output_path_rejects_paths_outside_lab_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            lab_root = Path(tmpdir) / "_sym_lab"
            outside = Path(tmpdir) / "elsewhere" / "result.json"

            with self.assertRaisesRegex(RuntimeError, "outside lab root"):
                gate.assert_lab_output_path(outside, lab_root=lab_root)

    def test_path_length_summary_flags_near_radan_limit_paths(self) -> None:
        project = Path(
            "C:/Tools/radan_automation/_sym_lab/run/"
            "F54410 PAINT PACK.full95_B194_circle_pair_context_only_repeat1.rpd"
        )
        out_dir = project.parent

        summary = gate.path_length_summary(project, out_dir, warning_chars=len(str(project)))

        self.assertEqual(summary["project_path_length"], len(str(project)))
        self.assertEqual(summary["out_dir_length"], len(str(out_dir)))
        self.assertTrue(summary["project_path_warning"])

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

    def test_terminate_processes_preserves_excluded_ids(self) -> None:
        processes = [
            {"id": "101", "process_name": "RADRAFT"},
            {"id": "202", "process_name": "RADRAFT"},
        ]
        with mock.patch.object(gate.os, "name", "nt"):
            with mock.patch.object(gate, "list_radan_processes", return_value=[]):
                with mock.patch.object(gate.subprocess, "run") as run_mock:
                    result = gate.terminate_processes(processes, exclude_ids=[202])

        self.assertEqual(result["requested_ids"], [101])
        self.assertEqual(result["preserved_ids"], [202])
        self.assertEqual(result["stopped"], [101])
        self.assertIn("-Id 101", run_mock.call_args.args[0][-1])
        self.assertNotIn("202", run_mock.call_args.args[0][-1])

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

    def test_finish_nesting_for_reports_calls_headless_refresh_api(self) -> None:
        class FakeMac:
            def __init__(self) -> None:
                self.calls: list[tuple[bool, bool, float]] = []

            def pfl_finish_nesting(self, update_annotation: bool, update_schedule: bool, reserved: float) -> bool:
                self.calls.append((update_annotation, update_schedule, reserved))
                return True

        class FakeLogger:
            def __init__(self) -> None:
                self.messages: list[str] = []

            def write(self, message: str) -> None:
                self.messages.append(message)

        mac = FakeMac()
        logger = FakeLogger()

        result = gate._finish_nesting_for_reports(mac, logger)

        self.assertTrue(result["ok"])
        self.assertEqual(mac.calls, [(True, False, 0.0)])
        self.assertIn("pfl_finish_nesting", logger.messages[0])

    def test_write_gate_comparison_accepts_tie_aware_alternate_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            lab_root = root / "_sym_lab"
            left = lab_root / "left"
            primary = lab_root / "primary"
            alternate = lab_root / "alternate"
            for folder in (left, primary, alternate):
                folder.mkdir(parents=True)
            _write_compare_rpd(left / "left.rpd", "candidate", "candidate")
            _write_compare_drg(left / "P15 F54410 PAINT PACK.candidate.drg", "candidate", "candidate")
            _write_compare_rpd(primary / "primary.rpd", "raw_original", "raw_original", second_part="B-185")
            _write_compare_drg(
                primary / "P15 F54410 PAINT PACK.raw_original.drg",
                "raw_original",
                "raw_original",
                second_part="B-185",
            )
            _write_compare_rpd(alternate / "alternate.rpd", "raw_repeat", "raw_repeat")
            _write_compare_drg(alternate / "P15 F54410 PAINT PACK.raw_repeat.drg", "raw_repeat", "raw_repeat")

            with mock.patch.object(gate, "DEFAULT_LAB_ROOT", lab_root):
                summary = gate.write_gate_comparison(
                    left_dir=left,
                    left_name="candidate",
                    right_dir=primary,
                    right_name="raw_original",
                    alternate_right_dirs=[alternate],
                    alternate_right_names=["raw_repeat"],
                )
                self.assertTrue(Path(summary["out_json"]).exists())
                self.assertTrue(Path(summary["out_md"]).exists())

        self.assertFalse(summary["rpd_used_nests_match"])
        self.assertTrue(summary["tie_aware"]["acceptance_match"])
        self.assertEqual(summary["tie_aware"]["matched_baseline"], "raw_repeat")


if __name__ == "__main__":
    unittest.main()
