from __future__ import annotations

import unittest

from radan_com import (
    RadanApplication,
    RadanApplicationInfo,
    RadanLicenseInfo,
    RadanReportResult,
    available_radan_backends,
)


class _FakeBackend:
    backend_name = "fake"

    def __init__(self, created_new_instance: bool = False) -> None:
        self.document_calls: list[tuple[str, tuple[object, ...]]] = []
        self.mac_calls: list[tuple[str, tuple[object, ...]]] = []
        self.document = self._FakeDocument(self.document_calls)
        self.mac = self._FakeMac(self.mac_calls)
        self.properties = {
            "Name": "Mazak Smart System",
            "FullName": r"C:\Program Files\Mazak\Mazak\bin\radraft",
            "Path": r"C:\Program Files\Mazak\Mazak\bin",
            "SoftwareVersion": "2025.1.2523.1252",
            "ProcessID": "18516",
            "Visible": "false",
            "Interactive": True,
            "GUIState": "1",
            "GUISubState": 0,
        }
        self.path_properties = {
            ("ActiveDocument",): self.document,
            ("Mac",): self.mac,
        }
        self.calls: list[tuple[str, tuple[object, ...]]] = []
        self.closed = False
        self.created_new_instance = created_new_instance

    class _FakeDocument:
        def __init__(self, calls: list[tuple[str, tuple[object, ...]]]) -> None:
            self.Type = "1"
            self.Dirty = "false"
            self._calls = calls

        def Close(self, discard_changes: bool) -> None:
            self._calls.append(("Close", (discard_changes,)))

        def Save(self) -> None:
            self._calls.append(("Save", ()))

        def SaveAs(self, path: str) -> None:
            self._calls.append(("SaveAs", (path,)))

        def SaveCopyAs(self, path: str, options_file_path: str) -> None:
            self._calls.append(("SaveCopyAs", (path, options_file_path)))

    class _FakeMac:
        REPORT_TYPE_PDF = "4"
        REPORT_TYPE_CSV = 0

        def __init__(self, calls: list[tuple[str, tuple[object, ...]]]) -> None:
            self._calls = calls

        def lic_get_holder(self) -> str:
            self._calls.append(("lic_get_holder", ()))
            return "Battleshield Industries"

        def lic_get_servercode(self) -> str:
            self._calls.append(("lic_get_servercode", ()))
            return "8341-8159-8477-6673-9885-7909"

        def lic_available(self, name: str) -> str:
            self._calls.append(("lic_available", (name,)))
            return "true" if name == "CORE" else "false"

        def lic_confirm(self, name: str) -> bool:
            self._calls.append(("lic_confirm", (name,)))
            return name == "CORE"

        def lic_request(self, name: str) -> int:
            self._calls.append(("lic_request", (name,)))
            return 1 if name == "CORE" else 0

        def rfmac(self, command: str) -> str:
            self._calls.append(("rfmac", (command,)))
            return "1"

        def fla_thumbnail(self, path: str, width: int, height: int) -> bool:
            self._calls.append(("fla_thumbnail", (path, width, height)))
            return True

        def mfl_thumbnail(self, path: str, width: int) -> str:
            self._calls.append(("mfl_thumbnail", (path, width)))
            return "false"

        def prj_output_report(self, report_name: str, file_path: str, file_type: int, options: str):
            self._calls.append(("prj_output_report", (report_name, file_path, file_type, options)))
            return (False, "Wrong mode for DevExpress reports")

        def stp_output_report(self, report_name: str, file_path: str, file_type: int, options: str):
            self._calls.append(("stp_output_report", (report_name, file_path, file_type, options)))
            return (True, "")

    def get_property(self, name: str):
        return self.properties[name]

    def set_property(self, name: str, value: object) -> None:
        self.properties[name] = value

    def call_method(self, name: str, *args: object):
        self.calls.append((name, args))
        if name == "Quit":
            return True
        return None

    def close(self) -> None:
        self.closed = True

    def get_path_property(self, path: tuple[str, ...], name: str):
        return getattr(self.path_properties[path], name)

    def call_path_method(self, path: tuple[str, ...], name: str, *args: object):
        return getattr(self.path_properties[path], name)(*args)


class RadanComTests(unittest.TestCase):
    def test_available_backends_includes_powershell_on_windows(self) -> None:
        backends = available_radan_backends()
        self.assertIn("powershell", backends)

    def test_application_info_coerces_common_property_types(self) -> None:
        app = RadanApplication.__new__(RadanApplication)
        app.prog_id = "Radraft.Application"
        app._backend = _FakeBackend()

        info = app.info()

        self.assertIsInstance(info, RadanApplicationInfo)
        self.assertEqual(info.backend, "fake")
        self.assertEqual(info.process_id, 18516)
        self.assertEqual(info.gui_state, 1)
        self.assertEqual(info.gui_sub_state, 0)
        self.assertFalse(info.visible)
        self.assertTrue(info.interactive)

    def test_application_methods_delegate_to_backend(self) -> None:
        app = RadanApplication.__new__(RadanApplication)
        app.prog_id = "Radraft.Application"
        app._backend = _FakeBackend()

        app.visible = True
        app.interactive = False
        app.open_drawing(r"C:\Jobs\Demo.rpd", read_only=True, password="secret")
        app.open_symbol(r"C:\Jobs\Demo.sym")
        result = app.quit()
        app.close()

        self.assertTrue(app._backend.properties["Visible"])
        self.assertFalse(app._backend.properties["Interactive"])
        self.assertEqual(
            app._backend.calls,
            [
                ("OpenDrawing", (r"C:\Jobs\Demo.rpd", True, "secret")),
                ("OpenSymbol", (r"C:\Jobs\Demo.sym", False, "")),
                ("Quit", ()),
            ],
        )
        self.assertTrue(result)
        self.assertTrue(app._backend.closed)

    def test_active_document_helpers_delegate_to_document(self) -> None:
        app = RadanApplication.__new__(RadanApplication)
        app.prog_id = "Radraft.Application"
        app._backend = _FakeBackend()

        info = app.active_document_info()
        app.close_active_document(True)
        app.save_active_document()
        app.save_active_document_as(r"C:\Jobs\Demo.rpd")
        app.save_copy_of_active_document_as(r"C:\Jobs\Demo-copy.rpd", r"C:\Jobs\opts.opt")

        self.assertIsNotNone(info)
        assert info is not None
        self.assertEqual(info.document_type, 1)
        self.assertFalse(info.dirty)
        self.assertEqual(
            app._backend.document_calls,
            [
                ("Close", (True,)),
                ("Save", ()),
                ("SaveAs", (r"C:\Jobs\Demo.rpd",)),
                ("SaveCopyAs", (r"C:\Jobs\Demo-copy.rpd", r"C:\Jobs\opts.opt")),
            ],
        )

    def test_created_new_instance_reflects_backend(self) -> None:
        app = RadanApplication.__new__(RadanApplication)
        app.prog_id = "Radraft.Application"
        app._backend = _FakeBackend(created_new_instance=True)

        self.assertTrue(app.created_new_instance)

    def test_mac_helpers_delegate_to_nested_mac_object(self) -> None:
        app = RadanApplication.__new__(RadanApplication)
        app.prog_id = "Radraft.Application"
        app._backend = _FakeBackend()

        license_info = app.mac.license_info()
        available = app.mac.license_available("CORE")
        confirmed = app.mac.license_confirm("CORE")
        requested = app.mac.license_request("NEST")
        report_type_pdf = app.mac.report_type("pdf")
        report_type_csv = app.mac.report_type("CSV")
        keystroke_result = app.mac.keystroke("TEST-COMMAND")
        flat_thumbnail = app.mac.flat_thumbnail(r"C:\Jobs\thumb.png", 400, 300)
        model_thumbnail = app.mac.model_thumbnail(r"C:\Jobs\model.png", 512)
        project_report = app.mac.output_project_report("Project Report", r"C:\Jobs\project.pdf", 4)
        setup_report = app.mac.output_setup_report("Setup Sheet", r"C:\Jobs\setup.pdf", 4)

        self.assertIsInstance(license_info, RadanLicenseInfo)
        self.assertEqual(license_info.holder, "Battleshield Industries")
        self.assertEqual(license_info.servercode, "8341-8159-8477-6673-9885-7909")
        self.assertTrue(available)
        self.assertTrue(confirmed)
        self.assertFalse(requested)
        self.assertEqual(report_type_pdf, 4)
        self.assertEqual(report_type_csv, 0)
        self.assertEqual(keystroke_result, 1)
        self.assertTrue(flat_thumbnail)
        self.assertFalse(model_thumbnail)
        self.assertIsInstance(project_report, RadanReportResult)
        self.assertFalse(project_report.ok)
        self.assertEqual(project_report.error_message, "Wrong mode for DevExpress reports")
        self.assertIsInstance(setup_report, RadanReportResult)
        self.assertTrue(setup_report.ok)
        self.assertEqual(setup_report.error_message, "")
        self.assertEqual(
            app._backend.mac_calls,
            [
                ("lic_get_holder", ()),
                ("lic_get_servercode", ()),
                ("lic_available", ("CORE",)),
                ("lic_confirm", ("CORE",)),
                ("lic_request", ("NEST",)),
                ("rfmac", ("TEST-COMMAND",)),
                ("fla_thumbnail", (r"C:\Jobs\thumb.png", 400, 300)),
                ("mfl_thumbnail", (r"C:\Jobs\model.png", 512)),
                ("prj_output_report", ("Project Report", r"C:\Jobs\project.pdf", 4, "")),
                ("stp_output_report", ("Setup Sheet", r"C:\Jobs\setup.pdf", 4, "")),
            ],
        )

if __name__ == "__main__":
    unittest.main()
