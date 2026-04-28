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


CREATED_SYMBOL_SAMPLE = """<?xml version="1.0" encoding="UTF-8"?>
<RadanCompoundDocument>
  <RadanFile extension="ddc">
    <![CDATA[A,5,
G,,1,A,,1,,,7,,line-data,.,,,
H,,1,B,,1,,,7,1,arc-data,
]]>
  </RadanFile>
</RadanCompoundDocument>
"""


class ImportPartsCsvHeadlessTests(unittest.TestCase):
    def test_write_native_sym_prototype_uses_topology_canonical_settings(self) -> None:
        calls: dict[str, object] = {}

        def fake_write_native_prototype(**kwargs):
            calls.update(kwargs)
            return {"entity_count": 3, "replaced_records": 3}

        fake_module = SimpleNamespace(write_native_prototype=fake_write_native_prototype)

        with mock.patch.dict(sys.modules, {"write_native_sym_prototype": fake_module}):
            result = import_parts_csv_headless._write_native_sym_prototype(
                dxf_path=import_parts_csv_headless.Path("part.dxf"),
                template_sym=import_parts_csv_headless.Path("template.sym"),
                out_path=import_parts_csv_headless.Path("part.sym"),
            )

        self.assertEqual(result["entity_count"], 3)
        self.assertEqual(calls["source_coordinate_digits"], 6)
        self.assertEqual(calls["topology_snap_endpoints"], True)
        self.assertEqual(calls["canonicalize_endpoints"], True)
        self.assertEqual(calls["allow_outside_lab"], True)

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

    def test_read_import_csv_can_limit_importable_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            first_dxf_path = os.path.join(tmpdir, "Part A.dxf")
            missing_second_dxf_path = os.path.join(tmpdir, "Part B.dxf")
            csv_path = os.path.join(tmpdir, "parts_Radan.csv")
            with open(first_dxf_path, "w", encoding="utf-8") as handle:
                handle.write("dxf")
            with open(csv_path, "w", encoding="utf-8") as handle:
                handle.write("\n")
                handle.write(f"{first_dxf_path},2,Aluminum 5052,0.18,in,AIR\n")
                handle.write(f"{missing_second_dxf_path},1,Aluminum 5052,0.18,in,AIR\n")

            parts = import_parts_csv_headless.read_import_csv(
                import_parts_csv_headless.Path(csv_path),
                max_parts=1,
            )

        self.assertEqual(len(parts), 1)
        self.assertEqual(parts[0].part_name, "Part A")

    def test_read_import_csv_rejects_invalid_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = os.path.join(tmpdir, "parts_Radan.csv")
            with open(csv_path, "w", encoding="utf-8") as handle:
                handle.write("")

            with self.assertRaisesRegex(ValueError, "max_parts"):
                import_parts_csv_headless.read_import_csv(
                    import_parts_csv_headless.Path(csv_path),
                    max_parts=0,
                )

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

    def test_run_headless_import_refuses_w_drive_output_folder(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = import_parts_csv_headless.Path(tmpdir)
            dxf_path = root / "Part A.dxf"
            csv_path = root / "parts_Radan.csv"
            project_path = root / "job.rpd"
            dxf_path.write_text("dxf", encoding="utf-8")
            csv_path.write_text(f"{dxf_path},1,Aluminum 5052,0.125,in,AIR\n", encoding="utf-8")
            _write_project(project_path)

            with self.assertRaisesRegex(RuntimeError, "Refusing to write RADAN symbol output on W:"):
                import_parts_csv_headless.run_headless_import(
                    csv_path=csv_path,
                    output_folder=import_parts_csv_headless.Path(r"W:\LASER\symbols"),
                    project_path=project_path,
                    logger=import_parts_csv_headless._Logger(),
                )

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

            self.assertFalse(any((root / "_bak").glob("*_before_headless_import_*.rpd")))

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
            (output_folder / "Part A.sym").write_text(CREATED_SYMBOL_SAMPLE, encoding="utf-8")
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
                    self.opened_symbols: list[str] = []
                    self.saved = 0
                    self.quit_called = False
                    self.closed = False

                def info(self):
                    return SimpleNamespace(process_id=5678)

                def open_symbol(self, path, read_only=False):
                    self.opened_symbols.append(path)
                    return None

                def save_active_document_as(self, path):
                    import_parts_csv_headless.Path(path).write_text(CREATED_SYMBOL_SAMPLE, encoding="utf-8")

                def save_active_document(self):
                    self.saved += 1

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
            self.assertEqual(fake_app.opened_symbols, [str(dxf_path), str(output_folder / "Part A.sym")])
            self.assertEqual(fake_app.saved, 1)
            symbol_text = (output_folder / "Part A.sym").read_text(encoding="utf-8")
            self.assertIn("G,,1,A,,1,,,5,,line-data", symbol_text)
            self.assertIn("H,,1,B,,1,,,9,1,arc-data", symbol_text)
            self.assertEqual(result["converted"][0]["pen_remap"]["changed"], {"l": 1, "a": 1})
            self.assertTrue(result["converted"][0]["radan_refresh"]["refreshed"])
            self.assertTrue(any((root / "_bak").glob("*_before_headless_import_*.rpd")))

    def test_run_headless_import_native_sym_experimental_uses_existing_template_without_com(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = import_parts_csv_headless.Path(tmpdir)
            dxf_path = root / "Part A.dxf"
            csv_path = root / "parts_Radan.csv"
            output_folder = root / "out"
            project_path = root / "job.rpd"
            dxf_path.write_text("dxf", encoding="utf-8")
            csv_path.write_text(f"{dxf_path},1,Aluminum 5052,0.125,in,AIR\n", encoding="utf-8")
            output_folder.mkdir()
            symbol_path = output_folder / "Part A.sym"
            symbol_path.write_text("template sym", encoding="utf-8")
            _write_project(project_path)

            def fake_write_native_sym(*, dxf_path, template_sym, out_path):
                self.assertTrue(template_sym.exists())
                self.assertIn("_headless_import_backups", str(template_sym))
                self.assertEqual(template_sym.read_text(encoding="utf-8"), "template sym")
                out_path.write_text("native sym", encoding="utf-8")
                return {"entity_count": 3, "replaced_records": 3}

            with mock.patch.object(import_parts_csv_headless, "_visible_radan_process_ids", return_value={1234}):
                with mock.patch.object(import_parts_csv_headless, "open_application") as open_application_mock:
                    with mock.patch.object(import_parts_csv_headless, "_write_native_sym_prototype", side_effect=fake_write_native_sym):
                        with mock.patch.object(
                            import_parts_csv_headless,
                            "_validate_native_symbol",
                            return_value={"passed": True, "tiers": []},
                        ):
                            with mock.patch.object(
                                import_parts_csv_headless,
                                "_apply_created_symbol_pen_remap",
                                return_value={"changed": {"l": 1, "a": 1}, "changed_total": 2},
                            ) as pen_remap_mock:
                                result = import_parts_csv_headless.run_headless_import(
                                    csv_path=csv_path,
                                    output_folder=output_folder,
                                project_path=project_path,
                                logger=import_parts_csv_headless._Logger(),
                                native_sym_experimental=True,
                                allow_synthetic_donor=True,
                            )

            open_application_mock.assert_not_called()
            pen_remap_mock.assert_called_once_with(symbol_path, mock.ANY)
            self.assertEqual(symbol_path.read_text(encoding="utf-8"), "native sym")
            self.assertEqual(result["conversion_method"], "native_sym_experimental")
            self.assertEqual(len(result["converted"]), 1)
            self.assertEqual(result["converted"][0]["template_symbol_path"].endswith("Part A.sym"), True)
            self.assertEqual(result["converted"][0]["pen_remap"]["changed"], {"l": 1, "a": 1})
            self.assertEqual(result["skipped_conversion"], [])
            self.assertEqual(result["added"][0]["part"], "Part A")

    def test_run_headless_import_native_sym_experimental_preprocesses_dxf_before_symbol_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = import_parts_csv_headless.Path(tmpdir)
            dxf_path = root / "Part A.dxf"
            csv_path = root / "parts_Radan.csv"
            output_folder = root / "out"
            project_path = root / "job.rpd"
            dxf_path.write_text("raw dxf", encoding="utf-8")
            csv_path.write_text(f"{dxf_path},1,Aluminum 5052,0.125,in,AIR\n", encoding="utf-8")
            output_folder.mkdir()
            symbol_path = output_folder / "Part A.sym"
            symbol_path.write_text("template sym", encoding="utf-8")
            _write_project(project_path)

            source_dxf_path = dxf_path
            cleaned_path = project_path.parent / "_preprocessed_dxfs" / "Part A_outer_cleaned_tol002.dxf"
            report_path = project_path.parent / "_preprocessed_dxfs" / "Part A_outer_cleaned_tol002.report.json"
            calls: dict[str, object] = {}

            def fake_preprocessed_output_paths(*, dxf_path, project_folder, tolerance):
                self.assertEqual(dxf_path, source_dxf_path)
                self.assertEqual(project_folder, project_path.parent)
                self.assertEqual(tolerance, 0.002)
                return cleaned_path, report_path

            def fake_clean_outer_profile(*, dxf_path, project_folder, simplify_tolerance):
                self.assertEqual(dxf_path, source_dxf_path)
                self.assertEqual(project_folder, project_path.parent)
                self.assertEqual(simplify_tolerance, 0.002)
                cleaned_path.parent.mkdir(parents=True, exist_ok=True)
                cleaned_path.write_text("cleaned dxf", encoding="utf-8")
                report_path.write_text("{}", encoding="utf-8")
                return {
                    "dxf_path": str(dxf_path),
                    "out_path": str(cleaned_path),
                    "project_folder": str(project_folder),
                    "wrote_output": True,
                    "simplification": {"removed_vertices": 2, "max_final_vertex_deviation": 0.001},
                }

            def fake_write_native_sym(*, dxf_path, template_sym, out_path):
                calls["write_dxf_path"] = dxf_path
                out_path.write_text("native sym", encoding="utf-8")
                return {"entity_count": 3, "replaced_records": 3}

            def fake_validate_native_symbol(*, dxf_path, sym_path):
                calls["validate_dxf_path"] = dxf_path
                return {"passed": True, "tiers": []}

            fake_clean_module = SimpleNamespace(
                clean_outer_profile=fake_clean_outer_profile,
                preprocessed_output_paths=fake_preprocessed_output_paths,
            )
            with mock.patch.dict(sys.modules, {"clean_dxf_outer_profile": fake_clean_module}):
                with mock.patch.object(import_parts_csv_headless, "open_application") as open_application_mock:
                    with mock.patch.object(
                        import_parts_csv_headless,
                        "_write_native_sym_prototype",
                        side_effect=fake_write_native_sym,
                    ):
                        with mock.patch.object(
                            import_parts_csv_headless,
                            "_validate_native_symbol",
                            side_effect=fake_validate_native_symbol,
                        ):
                            with mock.patch.object(
                                import_parts_csv_headless,
                                "_apply_created_symbol_pen_remap",
                                return_value={"changed": {"l": 0, "a": 0}, "changed_total": 0},
                            ):
                                result = import_parts_csv_headless.run_headless_import(
                                    csv_path=csv_path,
                                    output_folder=output_folder,
                                    project_path=project_path,
                                    logger=import_parts_csv_headless._Logger(),
                                    native_sym_experimental=True,
                                    preprocess_dxf_outer_profile=True,
                                    preprocess_dxf_tolerance=0.002,
                                )

            open_application_mock.assert_not_called()
            self.assertEqual(calls["write_dxf_path"], cleaned_path)
            self.assertEqual(calls["validate_dxf_path"], cleaned_path)
            self.assertEqual(result["converted"][0]["preprocessed_dxf_path"], str(cleaned_path))
            self.assertEqual(result["converted"][0]["preprocess_report_path"], str(report_path))
            self.assertEqual(result["converted"][0]["source_dxf_path"], str(cleaned_path))

    def test_preprocess_dxf_for_synthetic_sym_falls_back_to_l_copy_when_cleaner_skips(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = import_parts_csv_headless.Path(tmpdir)
            dxf_path = root / "Part A.dxf"
            project_folder = root / "Project"
            project_folder.mkdir()
            dxf_path.write_text("raw dxf", encoding="utf-8")
            part = import_parts_csv_headless.ImportPart(
                dxf_path=dxf_path,
                quantity=1,
                material="Aluminum",
                thickness=0.125,
                unit="in",
                strategy="AIR",
            )
            cleaned_path = project_folder / "_preprocessed_dxfs" / "Part A_outer_cleaned_tol002.dxf"
            report_path = project_folder / "_preprocessed_dxfs" / "Part A_outer_cleaned_tol002.report.json"

            def fake_preprocessed_output_paths(*, dxf_path, project_folder, tolerance):
                return cleaned_path, report_path

            def fake_clean_outer_profile(*, dxf_path, project_folder, simplify_tolerance):
                report_path.parent.mkdir(parents=True, exist_ok=True)
                report_path.write_text("{}", encoding="utf-8")
                return {
                    "dxf_path": str(dxf_path),
                    "out_path": str(cleaned_path),
                    "project_folder": str(project_folder),
                    "wrote_output": False,
                    "skipped_write_reason": "curve-aware cleanup is not implemented yet",
                }

            fake_clean_module = SimpleNamespace(
                clean_outer_profile=fake_clean_outer_profile,
                preprocessed_output_paths=fake_preprocessed_output_paths,
            )
            with mock.patch.dict(sys.modules, {"clean_dxf_outer_profile": fake_clean_module}):
                result = import_parts_csv_headless._preprocess_dxf_for_synthetic_sym(
                    part=part,
                    project_folder=project_folder,
                    logger=import_parts_csv_headless._Logger(),
                    tolerance=0.002,
                )

            self.assertEqual(result["source_dxf_path"], cleaned_path)
            self.assertEqual(cleaned_path.read_text(encoding="utf-8"), "raw dxf")
            self.assertTrue(result["payload"]["fallback_copied_original"])
            self.assertIn("curve-aware", report_path.read_text(encoding="utf-8"))

    def test_run_headless_import_radan_com_can_preprocess_dxf_before_conversion(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = import_parts_csv_headless.Path(tmpdir)
            source_dxf_path = root / "Part A.dxf"
            csv_path = root / "parts_Radan.csv"
            output_folder = root / "out"
            project_path = root / "job.rpd"
            source_dxf_path.write_text("raw dxf", encoding="utf-8")
            csv_path.write_text(f"{source_dxf_path},1,Aluminum 5052,0.125,in,AIR\n", encoding="utf-8")
            output_folder.mkdir()
            _write_project(project_path)
            cleaned_path = project_path.parent / "_preprocessed_dxfs" / "Part A_outer_cleaned_tol002.dxf"
            report_path = project_path.parent / "_preprocessed_dxfs" / "Part A_outer_cleaned_tol002.report.json"

            def fake_preprocessed_output_paths(*, dxf_path, project_folder, tolerance):
                return cleaned_path, report_path

            def fake_clean_outer_profile(*, dxf_path, project_folder, simplify_tolerance):
                cleaned_path.parent.mkdir(parents=True, exist_ok=True)
                cleaned_path.write_text("cleaned dxf", encoding="utf-8")
                report_path.write_text("{}", encoding="utf-8")
                return {
                    "dxf_path": str(dxf_path),
                    "out_path": str(cleaned_path),
                    "project_folder": str(project_folder),
                    "wrote_output": True,
                    "simplification": {"removed_vertices": 2, "max_final_vertex_deviation": 0.001},
                }

            class _FakeMac:
                def ped_set_attrs2(self, *args):
                    return True

            class _FakeApp:
                created_new_instance = True

                def __init__(self):
                    self.opened_symbols: list[str] = []
                    self.saved = 0
                    self.quit_called = False
                    self.closed = False

                def info(self):
                    return SimpleNamespace(process_id=6789)

                def open_symbol(self, path, read_only=False):
                    self.opened_symbols.append(path)
                    return None

                def save_active_document_as(self, path):
                    import_parts_csv_headless.Path(path).write_text(CREATED_SYMBOL_SAMPLE, encoding="utf-8")

                def save_active_document(self):
                    self.saved += 1

                def close_active_document(self, discard_changes=True):
                    return None

                def quit(self):
                    self.quit_called = True
                    return True

                def close(self):
                    self.closed = True

            fake_clean_module = SimpleNamespace(
                clean_outer_profile=fake_clean_outer_profile,
                preprocessed_output_paths=fake_preprocessed_output_paths,
            )
            fake_app = _FakeApp()
            with mock.patch.dict(sys.modules, {"clean_dxf_outer_profile": fake_clean_module}):
                with mock.patch.object(import_parts_csv_headless, "_visible_radan_process_ids", return_value=set()):
                    with mock.patch.object(import_parts_csv_headless, "open_application", return_value=fake_app):
                        with mock.patch.object(import_parts_csv_headless, "_mac_object", return_value=_FakeMac()):
                            result = import_parts_csv_headless.run_headless_import(
                                csv_path=csv_path,
                                output_folder=output_folder,
                                project_path=project_path,
                                logger=import_parts_csv_headless._Logger(),
                                preprocess_dxf_outer_profile=True,
                                preprocess_dxf_tolerance=0.002,
                            )

            self.assertEqual(fake_app.opened_symbols, [str(cleaned_path), str(output_folder / "Part A.sym")])
            self.assertEqual(fake_app.saved, 1)
            self.assertTrue(fake_app.quit_called)
            self.assertEqual(result["conversion_method"], "radan_com")
            self.assertEqual(result["converted"][0]["source_dxf_path"], str(cleaned_path))
            self.assertEqual(result["converted"][0]["preprocessed_dxf_path"], str(cleaned_path))
            self.assertEqual(result["converted"][0]["preprocess_report_path"], str(report_path))
            self.assertTrue(result["converted"][0]["radan_refresh"]["refreshed"])

    def test_run_headless_import_native_sym_experimental_does_not_require_env_guard(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = import_parts_csv_headless.Path(tmpdir)
            dxf_path = root / "Part A.dxf"
            csv_path = root / "parts_Radan.csv"
            output_folder = root / "out"
            project_path = root / "job.rpd"
            dxf_path.write_text("dxf", encoding="utf-8")
            csv_path.write_text(f"{dxf_path},1,Aluminum 5052,0.125,in,AIR\n", encoding="utf-8")
            output_folder.mkdir()
            symbol_path = output_folder / "Part A.sym"
            symbol_path.write_text("template sym", encoding="utf-8")
            _write_project(project_path)

            def fake_write_native_sym(*, dxf_path, template_sym, out_path):
                out_path.write_text("native sym", encoding="utf-8")
                return {"entity_count": 3, "replaced_records": 3}

            with mock.patch.object(import_parts_csv_headless, "open_application") as open_application_mock:
                with mock.patch.dict(os.environ, {}, clear=True):
                    with mock.patch.object(
                        import_parts_csv_headless,
                        "_write_native_sym_prototype",
                        side_effect=fake_write_native_sym,
                    ):
                        with mock.patch.object(
                            import_parts_csv_headless,
                            "_validate_native_symbol",
                            return_value={"passed": True, "tiers": []},
                        ):
                            with mock.patch.object(
                                import_parts_csv_headless,
                                "_apply_created_symbol_pen_remap",
                                return_value={"changed": {"l": 0, "a": 0}, "changed_total": 0},
                            ):
                                result = import_parts_csv_headless.run_headless_import(
                                    csv_path=csv_path,
                                    output_folder=output_folder,
                                    project_path=project_path,
                                    logger=import_parts_csv_headless._Logger(),
                                    native_sym_experimental=True,
                                    allow_synthetic_donor=True,
                                )

            open_application_mock.assert_not_called()
            self.assertEqual(symbol_path.read_text(encoding="utf-8"), "native sym")
            self.assertEqual(result["conversion_method"], "native_sym_experimental")

    def test_run_headless_import_native_sym_experimental_uses_donor_when_symbol_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = import_parts_csv_headless.Path(tmpdir)
            dxf_path = root / "Part A.dxf"
            csv_path = root / "parts_Radan.csv"
            output_folder = root / "out"
            project_path = root / "job.rpd"
            donor_path = root / "donor.sym"
            dxf_path.write_text("dxf", encoding="utf-8")
            csv_path.write_text(f"{dxf_path},1,Aluminum 5052,0.125,in,AIR\n", encoding="utf-8")
            donor_path.write_text("donor sym", encoding="utf-8")
            output_folder.mkdir()
            _write_project(project_path)

            def fake_write_native_sym(*, dxf_path, template_sym, out_path):
                self.assertEqual(template_sym, donor_path)
                out_path.write_text("native sym", encoding="utf-8")
                return {"entity_count": 3, "replaced_records": 3}

            with mock.patch.object(import_parts_csv_headless, "open_application") as open_application_mock:
                with mock.patch.object(import_parts_csv_headless, "DEFAULT_SYNTHETIC_DONOR_SYM", donor_path):
                    with mock.patch.object(
                        import_parts_csv_headless,
                        "_write_native_sym_prototype",
                        side_effect=fake_write_native_sym,
                    ):
                        with mock.patch.object(
                            import_parts_csv_headless,
                            "_validate_native_symbol",
                            return_value={"passed": True, "tiers": []},
                        ):
                            with mock.patch.object(
                                import_parts_csv_headless,
                                "_apply_created_symbol_pen_remap",
                                return_value={"changed": {"l": 0, "a": 0}, "changed_total": 0},
                            ):
                                result = import_parts_csv_headless.run_headless_import(
                                    csv_path=csv_path,
                                    output_folder=output_folder,
                                    project_path=project_path,
                                    logger=import_parts_csv_headless._Logger(),
                                    native_sym_experimental=True,
                                    allow_synthetic_donor=True,
                                )

            open_application_mock.assert_not_called()
            self.assertEqual((output_folder / "Part A.sym").read_text(encoding="utf-8"), "native sym")
            self.assertEqual(result["converted"][0]["template_source"], "universal_donor")
            self.assertEqual(result["converted"][0]["template_symbol_path"], str(donor_path))

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

            self.assertFalse(any((root / "_bak").glob("*_before_headless_import_*.rpd")))

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

    def test_direct_project_update_uses_default_project_color_when_recoloring_is_off(self) -> None:
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

            update_result = import_parts_csv_headless._update_project_file_direct(project_path, parts, output_folder)
            added = update_result["added"]

            root_xml = ET.parse(project_path).getroot()
            ns = f"{{{import_parts_csv_headless.RADAN_PROJECT_NS}}}"
            colors = [
                node.findtext(f"{ns}ColourWhenPartSaved")
                for node in root_xml.findall(f".//{ns}Part")
            ]
            made_values = [
                node.findtext(f"{ns}Made")
                for node in root_xml.findall(f".//{ns}Part")
            ]
            used_in_nests_nodes = [
                node.find(f"{ns}UsedInNests")
                for node in root_xml.findall(f".//{ns}Part")
            ]
            self.assertEqual(colors, [row["colour_when_part_saved"] for row in added])
            self.assertEqual(len(colors), 4)
            self.assertEqual(set(colors), {import_parts_csv_headless.DEFAULT_PROJECT_PART_COLOR})
            self.assertEqual(made_values, ["1", "1", "1", "1"])
            self.assertTrue(all(node is not None for node in used_in_nests_nodes))

    def test_direct_project_update_assigns_varied_part_colors_when_enabled(self) -> None:
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

            update_result = import_parts_csv_headless._update_project_file_direct(
                project_path,
                parts,
                output_folder,
                assign_project_colors=True,
            )
            added = update_result["added"]

            root_xml = ET.parse(project_path).getroot()
            ns = f"{{{import_parts_csv_headless.RADAN_PROJECT_NS}}}"
            colors = [
                node.findtext(f"{ns}ColourWhenPartSaved")
                for node in root_xml.findall(f".//{ns}Part")
            ]
            self.assertEqual(colors, [row["colour_when_part_saved"] for row in added])
            self.assertEqual(len(colors), 4)
            self.assertEqual(len(set(colors)), 4)

    def test_radan_nst_project_update_adds_parts_without_sheet_calls(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = import_parts_csv_headless.Path(tmpdir)
            output_folder = root / "out"
            project_path = root / "job.rpd"
            output_folder.mkdir()
            _write_project(project_path)
            dxf_path = root / "Part A.dxf"
            dxf_path.write_text("dxf", encoding="utf-8")
            (output_folder / "Part A.sym").write_text("sym", encoding="utf-8")
            part = import_parts_csv_headless.ImportPart(
                dxf_path=dxf_path,
                quantity=2,
                material="Aluminum 5052",
                thickness=0.125,
                unit="in",
                strategy="AIR",
            )

            class _FakeMac:
                def __init__(self) -> None:
                    object.__setattr__(self, "calls", [])
                    object.__setattr__(self, "values", {})
                    object.__setattr__(self, "project_path", None)

                def __setattr__(self, name, value):
                    if name in {"calls", "values", "project_path"}:
                        object.__setattr__(self, name, value)
                    else:
                        self.values[name] = value

                def __getattr__(self, name):
                    if name == "PRJ_PART_MULTI":
                        return 0
                    if name == "NSM_ORIENTATION_MODE_FREE":
                        return 0
                    raise AttributeError(name)

                def prj_open(self, file):
                    self.calls.append("prj_open")
                    self.project_path = import_parts_csv_headless.Path(file)
                    return True

                def nst_start_adding_parts(self):
                    self.calls.append("nst_start_adding_parts")
                    return 0

                def nst_add_part(self):
                    self.calls.append("nst_add_part")
                    tree = ET.parse(self.project_path)
                    project_parts = import_parts_csv_headless._find_project_parts(tree.getroot())
                    next_id_node = project_parts.find(f"{{{import_parts_csv_headless.RADAN_PROJECT_NS}}}NextID")
                    next_id = int(next_id_node.text)
                    node = ET.Element(f"{{{import_parts_csv_headless.RADAN_PROJECT_NS}}}Part")
                    for key, value in (
                        ("ID", next_id),
                        ("Symbol", self.values["NST_NAME"]),
                        ("Number", self.values["NST_NUMBER"]),
                        ("Material", self.values["NST_MATERIAL"]),
                        ("Thickness", self.values["NST_THICKNESS"]),
                        ("ThickUnits", self.values["NST_THICK_UNITS"]),
                        ("Strategy", self.values["NST_STRATEGY"]),
                    ):
                        child = ET.SubElement(node, f"{{{import_parts_csv_headless.RADAN_PROJECT_NS}}}{key}")
                        child.text = str(value)
                    project_parts.append(node)
                    next_id_node.text = str(next_id + 1)
                    ET.indent(tree, space="  ")
                    tree.write(self.project_path, encoding="utf-8", xml_declaration=True)
                    return 0

                def nst_finish_adding_parts(self):
                    self.calls.append("nst_finish_adding_parts")
                    return 0

                def prj_save(self):
                    self.calls.append("prj_save")
                    return True

                def prj_close(self):
                    self.calls.append("prj_close")
                    return True

            class _FakeBackend:
                def __init__(self, mac):
                    self.mac = mac

                def _resolve_path(self, path):
                    self.mac.calls.append(f"resolve:{'.'.join(path)}")
                    return self.mac

            fake_mac = _FakeMac()
            fake_app = SimpleNamespace(_backend=_FakeBackend(fake_mac))

            result = import_parts_csv_headless._update_project_file_via_radan_nst(
                fake_app,
                project_path,
                [part],
                output_folder,
                logger=import_parts_csv_headless._Logger(),
            )

            self.assertEqual(result["added"][0]["project_part_id"], 10)
            self.assertFalse(result["sheet_observation"]["sheet_calls_made"])
            self.assertEqual(result["sheet_observation"]["before"]["sheet_count"], 0)
            self.assertEqual(result["sheet_observation"]["after"]["sheet_count"], 0)
            self.assertNotIn("nst_add_sheet", fake_mac.calls)
            self.assertEqual(
                fake_mac.calls,
                [
                    "resolve:Mac",
                    "prj_open",
                    "nst_start_adding_parts",
                    "nst_add_part",
                    "nst_finish_adding_parts",
                    "prj_save",
                    "prj_close",
                ],
            )

    def test_refresh_project_sheets_from_current_parts_uses_fresh_hidden_radan(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = import_parts_csv_headless.Path(tmpdir)
            project_path = root / "job.rpd"
            _write_project(project_path)

            class _FakeMac:
                def __init__(self) -> None:
                    self.calls: list[str] = []
                    self.project_path: import_parts_csv_headless.Path | None = None

                def prj_open(self, file):
                    self.calls.append("prj_open")
                    self.project_path = import_parts_csv_headless.Path(file)
                    return True

                def prj_get_file_path(self):
                    self.calls.append("prj_get_file_path")
                    return str(self.project_path)

                def Execute(self, line):
                    self.calls.append(f"Execute:{line}")
                    self.asserted_line = line
                    assert self.project_path is not None
                    tree = ET.parse(self.project_path)
                    root_node = tree.getroot()
                    sheets = import_parts_csv_headless._find_project_sheets(root_node)
                    if sheets is None:
                        sheets = ET.SubElement(
                            root_node,
                            f"{{{import_parts_csv_headless.RADAN_PROJECT_NS}}}Sheets",
                        )
                        ET.SubElement(
                            sheets,
                            f"{{{import_parts_csv_headless.RADAN_PROJECT_NS}}}NextID",
                        ).text = "2"
                    sheet = ET.SubElement(sheets, f"{{{import_parts_csv_headless.RADAN_PROJECT_NS}}}Sheet")
                    for key, value in (
                        ("ID", "1"),
                        ("Material", "Aluminum 5052"),
                        ("Thickness", "0.125"),
                        ("ThickUnits", "in"),
                        ("SheetX", "120"),
                        ("SheetY", "60"),
                        ("SheetUnits", "in"),
                    ):
                        ET.SubElement(sheet, f"{{{import_parts_csv_headless.RADAN_PROJECT_NS}}}{key}").text = value
                    ET.indent(tree, space="  ")
                    tree.write(self.project_path, encoding="utf-8", xml_declaration=True)
                    return True

                def prj_save(self):
                    self.calls.append("prj_save")
                    return True

                def prj_close(self):
                    self.calls.append("prj_close")
                    return True

            class _FakeBackend:
                def __init__(self, mac):
                    self.mac = mac

                def _resolve_path(self, path):
                    self.mac.calls.append(f"resolve:{'.'.join(path)}")
                    return self.mac

            class _FakeApp:
                created_new_instance = True

                def __init__(self, mac):
                    self._backend = _FakeBackend(mac)
                    self.visible = True
                    self.interactive = True
                    self.quit_called = False
                    self.closed = False

                def info(self):
                    return SimpleNamespace(process_id=9876)

                def quit(self):
                    self.quit_called = True
                    return True

                def close(self):
                    self.closed = True

            fake_mac = _FakeMac()
            fake_app = _FakeApp(fake_mac)
            with mock.patch.object(import_parts_csv_headless, "open_application", return_value=fake_app) as open_mock:
                result = import_parts_csv_headless._refresh_project_sheets_from_current_parts(
                    project_path,
                    logger=import_parts_csv_headless._Logger(),
                    backend="win32com",
                    preexisting_visible_pids={1234},
                )

            open_mock.assert_called_once_with(backend="win32com", force_new_instance=True)
            self.assertEqual(result["before"]["sheet_count"], 0)
            self.assertEqual(result["after"]["sheet_count"], 1)
            self.assertEqual(result["process_id"], 9876)
            self.assertTrue(fake_app.quit_called)
            self.assertTrue(fake_app.closed)
            self.assertEqual(
                fake_mac.calls,
                [
                    "resolve:Mac",
                    "prj_open",
                    "prj_get_file_path",
                    f"Execute:{import_parts_csv_headless.PROJECT_SHEETS_REFRESH_MAC_LINE}",
                    "prj_save",
                    "prj_close",
                ],
            )

    def test_run_headless_import_skips_existing_project_rows_on_repeat(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = import_parts_csv_headless.Path(tmpdir)
            dxf_path = root / "Part A.dxf"
            csv_path = root / "parts_Radan.csv"
            output_folder = root / "out"
            project_path = root / "job.rpd"
            dxf_path.write_text("dxf", encoding="utf-8")
            csv_path.write_text(f"{dxf_path},1,Aluminum 5052,0.125,in,AIR\n", encoding="utf-8")
            output_folder.mkdir()
            (output_folder / "Part A.sym").write_text(CREATED_SYMBOL_SAMPLE, encoding="utf-8")
            _write_project(project_path)

            class _FakeRefreshApp:
                created_new_instance = True

                def __init__(self):
                    self.opened_symbols: list[str] = []
                    self.saved = 0
                    self.quit_called = False
                    self.closed = False
                    self.visible = True
                    self.interactive = True

                def info(self):
                    return SimpleNamespace(process_id=7788)

                def open_symbol(self, path, read_only=False):
                    self.opened_symbols.append(path)

                def save_active_document(self):
                    self.saved += 1

                def close_active_document(self, discard_changes=True):
                    return None

                def quit(self):
                    self.quit_called = True
                    return True

                def close(self):
                    self.closed = True

            fake_app = _FakeRefreshApp()
            with mock.patch.object(import_parts_csv_headless, "_visible_radan_process_ids", return_value=set()):
                with mock.patch.object(import_parts_csv_headless, "open_application", return_value=fake_app):
                    first_result = import_parts_csv_headless.run_headless_import(
                        csv_path=csv_path,
                        output_folder=output_folder,
                        project_path=project_path,
                        logger=import_parts_csv_headless._Logger(),
                    )
                    second_result = import_parts_csv_headless.run_headless_import(
                        csv_path=csv_path,
                        output_folder=output_folder,
                        project_path=project_path,
                        logger=import_parts_csv_headless._Logger(),
                    )

            self.assertEqual(len(first_result["added"]), 1)
            self.assertEqual(first_result["skipped_conversion"][0]["pen_remap"]["changed"], {"l": 1, "a": 1})
            self.assertTrue(first_result["skipped_conversion"][0]["radan_refresh"]["refreshed"])
            self.assertEqual(fake_app.opened_symbols, [str(output_folder / "Part A.sym")])
            self.assertEqual(fake_app.saved, 1)
            self.assertTrue(fake_app.quit_called)
            self.assertTrue(fake_app.closed)
            self.assertEqual(second_result["added"], [])
            self.assertEqual(len(second_result["skipped_existing_project_rows"]), 1)
            self.assertEqual(second_result["skipped_conversion"][0]["pen_remap_changed_total"], 0)
            self.assertTrue(second_result["project_validation"]["passed"])

            root_xml = ET.parse(project_path).getroot()
            ns = f"{{{import_parts_csv_headless.RADAN_PROJECT_NS}}}"
            self.assertEqual(len(root_xml.findall(f".//{ns}Part")), 1)

    def test_validate_project_file_after_write_detects_duplicate_expected_symbol(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = import_parts_csv_headless.Path(tmpdir)
            output_folder = root / "out"
            output_folder.mkdir()
            symbol_path = output_folder / "Part A.sym"
            symbol_path.write_text("sym", encoding="utf-8")
            dxf_path = root / "Part A.dxf"
            dxf_path.write_text("dxf", encoding="utf-8")
            project_path = root / "job.rpd"
            project_path.write_text(
                '<?xml version="1.0" encoding="UTF-8"?>\n'
                '<RadanProject xmlns="http://www.radan.com/ns/project">\n'
                '  <Parts>\n'
                '    <NextID>3</NextID>\n'
                '    <Part><ID>1</ID><Symbol>{0}</Symbol></Part>\n'
                '    <Part><ID>2</ID><Symbol>{0}</Symbol></Part>\n'
                '  </Parts>\n'
                '</RadanProject>\n'.format(symbol_path),
                encoding="utf-8",
            )
            part = import_parts_csv_headless.ImportPart(
                dxf_path=dxf_path,
                quantity=1,
                material="Aluminum",
                thickness=0.125,
                unit="in",
                strategy="AIR",
            )

            result = import_parts_csv_headless._validate_project_file_after_write(
                project_path,
                [part],
                output_folder,
            )

            self.assertFalse(result["passed"])
            self.assertTrue(
                any("appear more than once" in error for error in result["errors"]),
                result["errors"],
            )

    def test_preflight_doctor_blocks_synthetic_missing_symbols_by_default(self) -> None:
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

            with mock.patch.object(import_parts_csv_headless, "_module_available", return_value=(True, "test")):
                with mock.patch.object(import_parts_csv_headless, "_visible_radan_process_ids", return_value=[]):
                    result = import_parts_csv_headless.run_preflight_doctor(
                        csv_path=csv_path,
                        output_folder=output_folder,
                        project_path=project_path,
                        native_sym_experimental=True,
                    )

            checks_by_code = {check["code"]: check for check in result["checks"]}
            self.assertEqual(checks_by_code["synthetic_missing_symbols"]["status"], "fail")
            self.assertIn("donor creation is disabled", checks_by_code["synthetic_missing_symbols"]["message"])


if __name__ == "__main__":
    unittest.main()
