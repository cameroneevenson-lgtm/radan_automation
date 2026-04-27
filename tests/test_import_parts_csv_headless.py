from __future__ import annotations

import os
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from types import SimpleNamespace
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import import_parts_csv_headless


def _write_project(path: import_parts_csv_headless.Path) -> None:
    path.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<RadanProject xmlns="http://www.radan.com/ns/project">\n'
        '  <RadanSchedule>\n'
        '    <Parts />\n'
        '  </RadanSchedule>\n'
        '  <Parts>\n'
        '    <NextID>10</NextID>\n'
        '  </Parts>\n'
        '</RadanProject>\n',
        encoding="utf-8",
    )


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

    def test_resolve_automation_instance_rejects_preexisting_visible_session(self) -> None:
        class _FakeApp:
            created_new_instance = True

            def info(self):
                return SimpleNamespace(process_id=1234)

        logger = import_parts_csv_headless._Logger()
        with self.assertRaisesRegex(RuntimeError, "already-open visible RADAN session"):
            import_parts_csv_headless._resolve_automation_instance(_FakeApp(), {1234}, logger)

    def test_resolve_automation_instance_allows_nonvisible_new_pid(self) -> None:
        class _FakeApp:
            created_new_instance = True

            def info(self):
                return SimpleNamespace(process_id=5678)

        logger = import_parts_csv_headless._Logger()
        info, should_quit = import_parts_csv_headless._resolve_automation_instance(_FakeApp(), {1234}, logger)

        self.assertEqual(info.process_id, 5678)
        self.assertTrue(should_quit)

    def test_run_headless_import_refuses_visible_radan_by_default_when_conversion_is_needed(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = import_parts_csv_headless.Path(tmpdir)
            dxf_path = root / "Part A.dxf"
            csv_path = root / "parts_Radan.csv"
            output_folder = root / "out"
            project_path = root / "job.rpd"
            dxf_path.write_text("dxf", encoding="utf-8")
            csv_path.write_text(f"{dxf_path},1,Aluminum 5052,0.125,in,AIR\n", encoding="utf-8")
            output_folder.mkdir()
            _write_project(project_path)

            with mock.patch.object(import_parts_csv_headless, "_visible_radan_process_ids", return_value={1234}):
                with self.assertRaisesRegex(RuntimeError, "still needs to convert"):
                    import_parts_csv_headless.run_headless_import(
                        csv_path=csv_path,
                        output_folder=output_folder,
                        project_path=project_path,
                        logger=import_parts_csv_headless._Logger(),
                    )

            self.assertFalse(any(root.glob("*_before_headless_import_*.rpd")))

    def test_run_headless_import_allows_visible_radan_when_symbols_already_exist(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = import_parts_csv_headless.Path(tmpdir)
            dxf_path = root / "Part A.dxf"
            csv_path = root / "parts_Radan.csv"
            output_folder = root / "out"
            project_path = root / "job.rpd"
            dxf_path.write_text("dxf", encoding="utf-8")
            csv_path.write_text(f"{dxf_path},1,Aluminum 5052,0.125,in,AIR\n", encoding="utf-8")
            output_folder.mkdir()
            (output_folder / "Part A.sym").write_text("existing sym", encoding="utf-8")
            _write_project(project_path)

            with mock.patch.object(import_parts_csv_headless, "_visible_radan_process_ids", return_value={1234}):
                with mock.patch.object(import_parts_csv_headless, "open_application") as open_application_mock:
                    result = import_parts_csv_headless.run_headless_import(
                        csv_path=csv_path,
                        output_folder=output_folder,
                        project_path=project_path,
                        logger=import_parts_csv_headless._Logger(),
                    )

            self.assertEqual(result["converted"], [])
            self.assertEqual(len(result["skipped_conversion"]), 1)
            open_application_mock.assert_not_called()
            self.assertEqual(result["added"][0]["part"], "Part A")
            self.assertEqual(result["added"][0]["project_part_id"], 10)
            self.assertIn("<Symbol>", project_path.read_text(encoding="utf-8"))

    def test_run_headless_import_allows_visible_radan_with_explicit_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = import_parts_csv_headless.Path(tmpdir)
            dxf_path = root / "Part A.dxf"
            csv_path = root / "parts_Radan.csv"
            output_folder = root / "out"
            project_path = root / "job.rpd"
            dxf_path.write_text("dxf", encoding="utf-8")
            csv_path.write_text(f"{dxf_path},1,Aluminum 5052,0.125,in,AIR\n", encoding="utf-8")
            output_folder.mkdir()
            _write_project(project_path)

            class _FakeMac:
                def ped_set_attrs2(self, *args):
                    return True

            class _FakeApp:
                created_new_instance = True

                def __init__(self):
                    self.visible = True
                    self.interactive = True
                    self.quit_called = False
                    self.closed = False

                def info(self):
                    return SimpleNamespace(process_id=5678)

                def open_symbol(self, path, read_only=False):
                    return None

                def save_active_document_as(self, path):
                    import_parts_csv_headless.Path(path).write_text("sym", encoding="utf-8")

                def close_active_document(self, discard_changes=True):
                    return None

                def quit(self):
                    self.quit_called = True
                    return True

                def close(self):
                    self.closed = True

            fake_mac = _FakeMac()
            fake_app = _FakeApp()
            with mock.patch.object(import_parts_csv_headless, "_visible_radan_process_ids", return_value={1234}):
                with mock.patch.object(import_parts_csv_headless, "open_application", return_value=fake_app):
                    with mock.patch.object(import_parts_csv_headless, "_mac_object", return_value=fake_mac):
                        result = import_parts_csv_headless.run_headless_import(
                            csv_path=csv_path,
                            output_folder=output_folder,
                            project_path=project_path,
                            logger=import_parts_csv_headless._Logger(),
                            allow_visible_radan=True,
                        )

            self.assertEqual(result["part_count"], 1)
            self.assertTrue(fake_app.quit_called)
            self.assertTrue((output_folder / "Part A.sym").exists())
            self.assertTrue(any(root.glob("*_before_headless_import_*.rpd")))

    def test_run_headless_import_rejects_visible_radan_when_same_pid_is_resolved_with_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = import_parts_csv_headless.Path(tmpdir)
            dxf_path = root / "Part A.dxf"
            csv_path = root / "parts_Radan.csv"
            output_folder = root / "out"
            project_path = root / "job.rpd"
            dxf_path.write_text("dxf", encoding="utf-8")
            csv_path.write_text(f"{dxf_path},1,Aluminum 5052,0.125,in,AIR\n", encoding="utf-8")
            output_folder.mkdir()
            _write_project(project_path)

            class _FakeApp:
                created_new_instance = True

                def info(self):
                    return SimpleNamespace(process_id=1234)

                def close(self):
                    return None

            with mock.patch.object(import_parts_csv_headless, "_visible_radan_process_ids", return_value={1234}):
                with mock.patch.object(import_parts_csv_headless, "open_application", return_value=_FakeApp()):
                    with self.assertRaisesRegex(RuntimeError, "already-open visible RADAN session"):
                        import_parts_csv_headless.run_headless_import(
                            csv_path=csv_path,
                            output_folder=output_folder,
                            project_path=project_path,
                            logger=import_parts_csv_headless._Logger(),
                            allow_visible_radan=True,
                        )

            self.assertFalse(any(root.glob("*_before_headless_import_*.rpd")))

    def test_import_lock_rejects_second_import_for_same_project(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = import_parts_csv_headless.Path(tmpdir) / "job.rpd"
            _write_project(project_path)
            logger = import_parts_csv_headless._Logger()

            with import_parts_csv_headless._ImportLock(project_path, logger):
                with self.assertRaisesRegex(RuntimeError, "Another RADAN CSV import"):
                    with import_parts_csv_headless._ImportLock(project_path, logger):
                        pass

    def test_import_lock_removes_stale_dead_pid_lock(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = import_parts_csv_headless.Path(tmpdir) / "job.rpd"
            _write_project(project_path)
            logger = import_parts_csv_headless._Logger()
            import_lock = import_parts_csv_headless._ImportLock(project_path, logger)
            import_lock.path.write_text("999999", encoding="ascii")

            with mock.patch.object(import_parts_csv_headless, "_process_exists", return_value=False):
                with import_parts_csv_headless._ImportLock(project_path, logger):
                    pass

            self.assertFalse(import_lock.path.exists())

    def test_missing_symbol_verification_lists_absent_symbols(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = import_parts_csv_headless.Path(tmpdir)
            dxf_path = root / "Part A.dxf"
            output_folder = root / "out"
            dxf_path.write_text("dxf", encoding="utf-8")
            output_folder.mkdir()
            part = import_parts_csv_headless.ImportPart(
                dxf_path=dxf_path,
                quantity=1,
                material="Aluminum",
                thickness=0.125,
                unit="in",
                strategy="AIR",
            )

            missing = import_parts_csv_headless._missing_symbol_paths([part], output_folder)

            self.assertEqual(missing, [output_folder / "Part A.sym"])

    def test_project_part_colors_are_deterministic_and_varied(self) -> None:
        colors = [
            import_parts_csv_headless._project_part_color(part_id)
            for part_id in range(10, 108)
        ]

        self.assertEqual(colors, [import_parts_csv_headless._project_part_color(part_id) for part_id in range(10, 108)])
        self.assertEqual(len(set(colors)), len(import_parts_csv_headless.PROJECT_PART_COLOR_PALETTE))
        for color in colors:
            channels = [int(value.strip()) for value in color.split(",")]
            self.assertEqual(len(channels), 3)
            self.assertTrue(all(31 <= channel <= 223 for channel in channels))

    def test_direct_project_update_assigns_varied_part_colors(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = import_parts_csv_headless.Path(tmpdir)
            output_folder = root / "out"
            project_path = root / "job.rpd"
            output_folder.mkdir()
            _write_project(project_path)
            parts = []
            for name in ("Part A", "Part B", "Part C", "Part D"):
                dxf_path = root / f"{name}.dxf"
                dxf_path.write_text("dxf", encoding="utf-8")
                (output_folder / f"{name}.sym").write_text("sym", encoding="utf-8")
                parts.append(
                    import_parts_csv_headless.ImportPart(
                        dxf_path=dxf_path,
                        quantity=1,
                        material="Aluminum",
                        thickness=0.125,
                        unit="in",
                        strategy="AIR",
                    )
                )

            added = import_parts_csv_headless._update_project_file_direct(project_path, parts, output_folder)

            root_xml = ET.parse(project_path).getroot()
            ns = f"{{{import_parts_csv_headless.RADAN_PROJECT_NS}}}"
            colors = [
                node.findtext(f"{ns}ColourWhenPartSaved")
                for node in root_xml.findall(f".//{ns}Part")
            ]
            self.assertEqual(colors, [row["colour_when_part_saved"] for row in added])
            self.assertEqual(len(colors), 4)
            self.assertEqual(len(set(colors)), 4)


if __name__ == "__main__":
    unittest.main()
