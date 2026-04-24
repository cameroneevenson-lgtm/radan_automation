from __future__ import annotations

import unittest
from unittest import mock

import radan_com
from radan_com import (
    RadanApplication,
    RadanApplicationInfo,
    RadanBounds,
    RadanComUnavailableError,
    RadanLicenseInfo,
    RadanLiveApplication,
    RadanLiveSessionInfo,
    RadanReportResult,
    RadanTargetMismatchError,
    RadanVisibleSessionInfo,
    attach_live_application,
    available_radan_backends,
    describe_live_session,
    list_visible_radan_sessions,
    open_application,
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
        PRS = "Ready"
        PART_PATTERN = "/part editor"
        CUP = "/current pattern"
        COP = "/open pattern"
        FI0 = "/symbol editor/_19"
        FT0 = ""
        FP0 = "7"
        LT0 = "1"
        S0X = "89.64375"
        S0Y = "64.64827"

        def __init__(self, calls: list[tuple[str, tuple[object, ...]]]) -> None:
            self._calls = calls

        def lic_get_holder(self) -> str:
            self._calls.append(("lic_get_holder", ()))
            return "Example Fabrication"

        def lic_get_servercode(self) -> str:
            self._calls.append(("lic_get_servercode", ()))
            return "0000-0000-0000-0000"

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

        def scan(self, path: str, feature_filter: str, number: int) -> bool:
            self._calls.append(("scan", (path, feature_filter, number)))
            return True

        def next(self) -> bool:
            self._calls.append(("next", ()))
            return False

        def rewind(self) -> bool:
            self._calls.append(("rewind", ()))
            return True

        def end_scan(self) -> bool:
            self._calls.append(("end_scan", ()))
            return True

        def find_xy_identifier(self, identifier: str, x: float, y: float) -> bool:
            self._calls.append(("find_xy_identifier", (identifier, x, y)))
            return True

        def profile_healing(
            self,
            pattern: str,
            include_sub_patterns: bool,
            tolerance: float,
            realise_ellipses: bool,
            remove_small_features: bool,
            close_small_gaps: bool,
            merge_overlaps: bool,
            simplify_data: bool,
        ) -> bool:
            self._calls.append(
                (
                    "profile_healing",
                    (
                        pattern,
                        include_sub_patterns,
                        tolerance,
                        realise_ellipses,
                        remove_small_features,
                        close_small_gaps,
                        merge_overlaps,
                        simplify_data,
                    ),
                )
            )
            return True

        def profile_healing_with_timeout(
            self,
            pattern: str,
            include_sub_patterns: bool,
            tolerance: float,
            realise_ellipses: bool,
            remove_small_features: bool,
            close_small_gaps: bool,
            merge_overlaps: bool,
            simplify_data: bool,
            time_limit: float,
        ) -> int:
            self._calls.append(
                (
                    "profile_healing_with_timeout",
                    (
                        pattern,
                        include_sub_patterns,
                        tolerance,
                        realise_ellipses,
                        remove_small_features,
                        close_small_gaps,
                        merge_overlaps,
                        simplify_data,
                        time_limit,
                    ),
                )
            )
            return 1

        def profile_extraction(
            self,
            pattern: str,
            include_sub_patterns: bool,
            delete_by_pen: bool,
            pen_mask: int,
            lines_arcs_only: bool,
            full_linetype_only: bool,
        ) -> bool:
            self._calls.append(
                (
                    "profile_extraction",
                    (
                        pattern,
                        include_sub_patterns,
                        delete_by_pen,
                        pen_mask,
                        lines_arcs_only,
                        full_linetype_only,
                    ),
                )
            )
            return True

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

    def test_open_application_can_force_fresh_instance(self) -> None:
        with mock.patch("radan_com.RadanApplication", return_value="sentinel") as application_factory:
            result = open_application(force_new_instance=True)

        self.assertEqual(result, "sentinel")
        application_factory.assert_called_once_with(
            backend=None,
            create_if_missing=True,
            force_new_instance=True,
        )

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

    def test_open_document_dispatches_by_extension(self) -> None:
        app = RadanApplication.__new__(RadanApplication)
        app.prog_id = "Radraft.Application"
        app._backend = _FakeBackend()

        app.open_document(r"C:\Jobs\Demo.sym")
        app.open_document(r"C:\Jobs\Raster.png", read_only=True, password="secret")
        app.open_document(r"C:\Jobs\Demo.drg", read_only=True, password="pw")

        self.assertEqual(
            app._backend.calls,
            [
                ("OpenSymbol", (r"C:\Jobs\Demo.sym", False, "")),
                ("OpenSymbolFromRasterImage", (r"C:\Jobs\Raster.png", True, "secret")),
                ("OpenDrawing", (r"C:\Jobs\Demo.drg", True, "pw")),
            ],
        )

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
        prompt_string = app.mac.prompt_string
        part_pattern = app.mac.part_pattern
        current_pattern = app.mac.current_pattern_path
        open_pattern = app.mac.open_pattern_path
        current_feature_identifier = app.mac.current_feature_identifier
        current_feature_type = app.mac.current_feature_type
        current_feature_pen = app.mac.current_feature_pen
        current_feature_line_type = app.mac.current_feature_line_type
        current_feature_x = app.mac.current_feature_x
        current_feature_y = app.mac.current_feature_y
        scan_result = app.mac.scan("/symbol editor", "l")
        next_result = app.mac.next()
        rewind_result = app.mac.rewind()
        end_scan_result = app.mac.end_scan()
        find_result = app.mac.find_xy_identifier("/symbol editor/_19", 89.64375, 64.64827)
        healing_result = app.mac.profile_healing(
            "/part editor",
            include_sub_patterns=True,
            tolerance=0.01,
            realise_ellipses=True,
            remove_small_features=True,
            close_small_gaps=True,
            merge_overlaps=True,
            simplify_data=True,
        )
        healing_timeout_result = app.mac.profile_healing_with_timeout(
            "/part editor",
            include_sub_patterns=False,
            tolerance=0.005,
            simplify_data=True,
            time_limit=12.5,
        )
        extraction_result = app.mac.profile_extraction(
            "/part editor",
            include_sub_patterns=True,
            delete_by_pen=True,
            pen_mask=0x12,
            lines_arcs_only=True,
            full_linetype_only=False,
        )
        flat_thumbnail = app.mac.flat_thumbnail(r"C:\Jobs\thumb.png", 400, 300)
        model_thumbnail = app.mac.model_thumbnail(r"C:\Jobs\model.png", 512)
        project_report = app.mac.output_project_report("Project Report", r"C:\Jobs\project.pdf", 4)
        setup_report = app.mac.output_setup_report("Setup Sheet", r"C:\Jobs\setup.pdf", 4)

        self.assertIsInstance(license_info, RadanLicenseInfo)
        self.assertEqual(license_info.holder, "Example Fabrication")
        self.assertEqual(license_info.servercode, "0000-0000-0000-0000")
        self.assertTrue(available)
        self.assertTrue(confirmed)
        self.assertFalse(requested)
        self.assertEqual(report_type_pdf, 4)
        self.assertEqual(report_type_csv, 0)
        self.assertEqual(keystroke_result, 1)
        self.assertEqual(prompt_string, "Ready")
        self.assertEqual(part_pattern, "/part editor")
        self.assertEqual(current_pattern, "/current pattern")
        self.assertEqual(open_pattern, "/open pattern")
        self.assertEqual(current_feature_identifier, "/symbol editor/_19")
        self.assertEqual(current_feature_type, "")
        self.assertEqual(current_feature_pen, 7)
        self.assertEqual(current_feature_line_type, 1)
        self.assertEqual(current_feature_x, 89.64375)
        self.assertEqual(current_feature_y, 64.64827)
        self.assertTrue(scan_result)
        self.assertFalse(next_result)
        self.assertTrue(rewind_result)
        self.assertTrue(end_scan_result)
        self.assertTrue(find_result)
        self.assertTrue(healing_result)
        self.assertEqual(healing_timeout_result, 1)
        self.assertTrue(extraction_result)
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
                ("scan", ("/symbol editor", "l", 0)),
                ("next", ()),
                ("rewind", ()),
                ("end_scan", ()),
                ("find_xy_identifier", ("/symbol editor/_19", 89.64375, 64.64827)),
                (
                    "profile_healing",
                    ("/part editor", True, 0.01, True, True, True, True, True),
                ),
                (
                    "profile_healing_with_timeout",
                    ("/part editor", False, 0.005, False, False, False, False, True, 12.5),
                ),
                (
                    "profile_extraction",
                    ("/part editor", True, True, 18, True, False),
                ),
                ("fla_thumbnail", (r"C:\Jobs\thumb.png", 400, 300)),
                ("mfl_thumbnail", (r"C:\Jobs\model.png", 512)),
                ("prj_output_report", ("Project Report", r"C:\Jobs\project.pdf", 4, "")),
                ("stp_output_report", ("Setup Sheet", r"C:\Jobs\setup.pdf", 4, "")),
            ],
        )

    def test_describe_live_session_uses_attached_pid_title_and_bounds(self) -> None:
        info = RadanApplicationInfo(
            prog_id="Radraft.Application",
            backend="fake",
            name="Mazak Smart System",
            full_name=r"C:\Program Files\Mazak\Mazak\bin\radraft",
            path=r"C:\Program Files\Mazak\Mazak\bin",
            software_version="2025.1.2523.1252",
            process_id=22188,
            visible=True,
            interactive=True,
            gui_state=4,
            gui_sub_state=14,
        )

        class _FakeAttachedApp:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return None

            def info(self):
                return info

        with mock.patch("radan_com.attach_application", return_value=_FakeAttachedApp()):
            with mock.patch(
                "radan_com._get_process_window_title",
                return_value="Demo Part - Mazak Smart System Part Editor",
            ):
                with mock.patch(
                    "radan_com._run_live_session_bridge",
                    return_value={
                        "ProcessId": 22188,
                        "WindowTitle": "Demo Part - Mazak Smart System Part Editor",
                        "Pattern": "/symbol editor",
                        "BoundsAvailable": True,
                        "Left": 10.0,
                        "Bottom": 20.0,
                        "Right": 30.0,
                        "Top": 50.0,
                    },
                ):
                    session = describe_live_session(require_part_editor=True, window_title_contains="Demo Part")

        self.assertIsInstance(session, RadanLiveSessionInfo)
        self.assertEqual(session.process_id, 22188)
        self.assertEqual(session.window_title, "Demo Part - Mazak Smart System Part Editor")
        self.assertEqual(session.editor_mode, "part")
        self.assertEqual(session.pattern, "/symbol editor")
        self.assertIsInstance(session.bounds, RadanBounds)
        assert session.bounds is not None
        self.assertEqual(session.bounds.width, 20.0)
        self.assertEqual(session.bounds.height, 30.0)
        self.assertEqual(session.bounds.center_x, 20.0)
        self.assertEqual(session.bounds.center_y, 35.0)

    def test_get_process_window_title_falls_back_to_visible_myframe_title(self) -> None:
        with mock.patch(
            "radan_com.subprocess.run",
            return_value=mock.Mock(stdout=""),
        ):
            with mock.patch(
                "radan_com._list_visible_window_titles_for_pid",
                return_value=["Demo Part - Mazak Smart System Part Editor"],
            ) as fallback:
                title = radan_com._get_process_window_title(22188)

        self.assertEqual(title, "Demo Part - Mazak Smart System Part Editor")
        fallback.assert_called_once_with(22188)

    def test_list_visible_radan_sessions_parses_visible_windows(self) -> None:
        payload = """
[
  {
    "ProcessId": 22188,
    "WindowTitle": "Demo Part - Mazak Smart System Part Editor"
  },
  {
    "ProcessId": 22189,
    "WindowTitle": "Demo Nest - Mazak Smart System Nest Editor"
  }
]
"""

        with mock.patch(
            "radan_com.subprocess.run",
            return_value=mock.Mock(stdout=payload),
        ):
            sessions = list_visible_radan_sessions()

        self.assertEqual(len(sessions), 2)
        self.assertEqual(sessions[0].process_id, 22188)
        self.assertEqual(sessions[0].editor_mode, "part")
        self.assertEqual(sessions[1].process_id, 22189)
        self.assertEqual(sessions[1].editor_mode, "nest")

    def test_list_visible_radan_sessions_falls_back_to_raw_windows_when_powershell_is_blank(self) -> None:
        fallback_sessions = [
            RadanVisibleSessionInfo(
                process_id=22188,
                window_title="Demo Part - Mazak Smart System Part Editor",
                editor_mode="part",
            )
        ]

        with mock.patch(
            "radan_com.subprocess.run",
            return_value=mock.Mock(stdout=""),
        ):
            with mock.patch(
                "radan_com._list_visible_radan_sessions_from_windows",
                return_value=fallback_sessions,
            ) as fallback:
                sessions = list_visible_radan_sessions()

        self.assertEqual(sessions, fallback_sessions)
        fallback.assert_called_once_with()

    def test_attach_live_application_rejects_wrong_mode(self) -> None:
        info = RadanApplicationInfo(
            prog_id="Radraft.Application",
            backend="fake",
            name="Mazak Smart System",
            full_name=r"C:\Program Files\Mazak\Mazak\bin\radraft",
            path=r"C:\Program Files\Mazak\Mazak\bin",
            software_version="2025.1.2523.1252",
            process_id=22188,
            visible=True,
            interactive=True,
            gui_state=4,
            gui_sub_state=14,
        )

        class _FakeAttachedApp:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return None

            def info(self):
                return info

        with mock.patch("radan_com.attach_application", return_value=_FakeAttachedApp()):
            with mock.patch(
                "radan_com._get_process_window_title",
                return_value="Demo Nest - Mazak Smart System Nest Editor",
            ):
                with self.assertRaises(RadanTargetMismatchError):
                    attach_live_application(require_part_editor=True)

    def test_describe_live_session_falls_back_to_visible_window_when_com_attach_is_unavailable(self) -> None:
        visible_session = RadanVisibleSessionInfo(
            process_id=2324,
            window_title="Demo Nest - Mazak Smart System Nest Editor",
            editor_mode="nest",
        )

        with mock.patch(
            "radan_com.attach_application",
            side_effect=RadanComUnavailableError("No active COM object is registered."),
        ):
            with mock.patch("radan_com.list_visible_radan_sessions", return_value=[visible_session]):
                session = describe_live_session()

        self.assertEqual(session.process_id, 2324)
        self.assertEqual(session.window_title, visible_session.window_title)
        self.assertEqual(session.editor_mode, "nest")
        self.assertEqual(session.application.backend, "visible-window")
        self.assertIsNone(session.pattern)
        self.assertIsNone(session.bounds)

    def test_describe_live_session_visible_window_fallback_requires_disambiguation(self) -> None:
        visible_sessions = [
            RadanVisibleSessionInfo(
                process_id=2324,
                window_title="Demo Part - Mazak Smart System Part Editor",
                editor_mode="part",
            ),
            RadanVisibleSessionInfo(
                process_id=2456,
                window_title="Demo Nest - Mazak Smart System Nest Editor",
                editor_mode="nest",
            ),
        ]

        with mock.patch(
            "radan_com.attach_application",
            side_effect=RadanComUnavailableError("No active COM object is registered."),
        ):
            with mock.patch("radan_com.list_visible_radan_sessions", return_value=visible_sessions):
                with self.assertRaises(RadanTargetMismatchError):
                    describe_live_session()

    def test_run_live_session_bridge_uses_host_bridge_after_local_failure(self) -> None:
        with mock.patch(
            "radan_com._run_local_live_session_bridge",
            side_effect=RadanComUnavailableError("No active COM object is registered."),
        ):
            with mock.patch("radan_com._host_live_bridge_is_ready", return_value=True):
                with mock.patch(
                    "radan_com._run_host_live_session_bridge",
                    return_value={"ProcessId": 2324, "WindowTitle": "Demo Part"},
                ) as host_bridge:
                    payload = radan_com._run_live_session_bridge(
                        "describe",
                        expected_process_id=2324,
                        window_title_contains="Demo Part",
                        require_part_editor=True,
                    )

        self.assertEqual(payload["ProcessId"], 2324)
        host_bridge.assert_called_once_with(
            "describe",
            expected_process_id=2324,
            window_title_contains="Demo Part",
            require_part_editor=True,
            width=None,
            height=None,
            gap=None,
            x=None,
            y=None,
            center_on_bounds=False,
            use_explicit_position=False,
        )

    def test_describe_live_session_uses_host_bridge_when_local_attach_is_unavailable(self) -> None:
        visible_session = RadanVisibleSessionInfo(
            process_id=2324,
            window_title="Demo Part - Mazak Smart System Part Editor",
            editor_mode="part",
        )
        payload = {
            "ProcessId": 2324,
            "WindowTitle": visible_session.window_title,
            "Visible": True,
            "Pattern": "/part editor",
            "BoundsAvailable": True,
            "Left": 10.0,
            "Bottom": 20.0,
            "Right": 40.0,
            "Top": 60.0,
        }

        with mock.patch(
            "radan_com.attach_application",
            side_effect=RadanComUnavailableError("No active COM object is registered."),
        ):
            with mock.patch(
                "radan_com._select_visible_radan_session",
                return_value=visible_session,
            ):
                with mock.patch("radan_com._host_live_bridge_is_ready", return_value=True):
                    with mock.patch("radan_com._run_live_session_bridge", return_value=payload) as bridge:
                        session = describe_live_session(require_part_editor=True)

        self.assertEqual(session.application.backend, "host-bridge")
        self.assertEqual(session.process_id, 2324)
        self.assertEqual(session.window_title, visible_session.window_title)
        self.assertEqual(session.pattern, "/part editor")
        self.assertEqual(session.bounds, RadanBounds(left=10.0, bottom=20.0, right=40.0, top=60.0))
        bridge.assert_called_once_with(
            "describe",
            expected_process_id=2324,
            window_title_contains=None,
            require_part_editor=True,
        )

    def test_attach_live_application_rejects_visible_window_fallback(self) -> None:
        visible_only = RadanLiveSessionInfo(
            application=RadanApplicationInfo(
                prog_id="Radraft.Application",
                backend="visible-window",
                name="Mazak Smart System",
                full_name=None,
                path=None,
                software_version=None,
                process_id=2324,
                visible=True,
                interactive=True,
                gui_state=None,
                gui_sub_state=None,
            ),
            window_title="Demo Part - Mazak Smart System Part Editor",
            editor_mode="part",
            pattern=None,
            bounds=None,
        )

        with mock.patch("radan_com.describe_live_session", return_value=visible_only):
            with self.assertRaises(RadanComUnavailableError):
                attach_live_application(require_part_editor=True)

    def test_live_application_draw_rectangle_centered_uses_pid_guard(self) -> None:
        session = RadanLiveSessionInfo(
            application=RadanApplicationInfo(
                prog_id="Radraft.Application",
                backend="fake",
                name="Mazak Smart System",
                full_name=r"C:\Program Files\Mazak\Mazak\bin\radraft",
                path=r"C:\Program Files\Mazak\Mazak\bin",
                software_version="2025.1.2523.1252",
                process_id=22188,
                visible=True,
                interactive=True,
                gui_state=4,
                gui_sub_state=14,
            ),
            window_title="Demo Part - Mazak Smart System Part Editor",
            editor_mode="part",
            pattern="/symbol editor",
            bounds=RadanBounds(left=10.0, bottom=20.0, right=30.0, top=50.0),
        )
        live = RadanLiveApplication(
            session,
            backend="fake",
            title_guard_contains="Demo Part",
            require_part_editor=True,
        )
        refreshed = RadanLiveSessionInfo(
            application=session.application,
            window_title=session.window_title,
            editor_mode="part",
            pattern="/symbol editor",
            bounds=RadanBounds(left=10.0, bottom=20.0, right=31.0, top=52.0),
        )

        with mock.patch(
            "radan_com._run_live_session_bridge",
            return_value={
                "RectangleX": 19.5,
                "RectangleY": 34.0,
                "RectangleWidth": 1.0,
                "RectangleHeight": 2.0,
            },
        ) as bridge:
            with mock.patch("radan_com.describe_live_session", return_value=refreshed):
                result = live.draw_rectangle_centered(width=1.0, height=2.0)

        self.assertEqual(result.x, 19.5)
        self.assertEqual(result.y, 34.0)
        self.assertEqual(result.width, 1.0)
        self.assertEqual(result.height, 2.0)
        self.assertEqual(result.session.bounds, refreshed.bounds)
        self.assertEqual(live.session.bounds, refreshed.bounds)
        bridge.assert_called_once_with(
            "draw_rectangle",
            expected_process_id=22188,
            window_title_contains="Demo Part",
            require_part_editor=True,
            width=1.0,
            height=2.0,
            gap=None,
            x=None,
            y=None,
            center_on_bounds=True,
            use_explicit_position=False,
        )

    def test_live_application_draw_rectangle_at_center_converts_center_to_corner(self) -> None:
        session = RadanLiveSessionInfo(
            application=RadanApplicationInfo(
                prog_id="Radraft.Application",
                backend="fake",
                name="Mazak Smart System",
                full_name=r"C:\Program Files\Mazak\Mazak\bin\radraft",
                path=r"C:\Program Files\Mazak\Mazak\bin",
                software_version="2025.1.2523.1252",
                process_id=22188,
                visible=True,
                interactive=True,
                gui_state=4,
                gui_sub_state=14,
            ),
            window_title="Demo Part - Mazak Smart System Part Editor",
            editor_mode="part",
            pattern="/symbol editor",
            bounds=RadanBounds(left=10.0, bottom=20.0, right=30.0, top=50.0),
        )
        live = RadanLiveApplication(
            session,
            backend="fake",
            expected_process_id=22188,
            title_guard_contains="Demo Part",
            require_part_editor=True,
        )

        with mock.patch(
            "radan_com._run_live_session_bridge",
            return_value={
                "RectangleX": 48.0,
                "RectangleY": 99.0,
                "RectangleWidth": 4.0,
                "RectangleHeight": 2.0,
            },
        ) as bridge:
            with mock.patch("radan_com.describe_live_session", return_value=session):
                result = live.draw_rectangle_at_center(center_x=50.0, center_y=100.0, width=4.0, height=2.0)

        self.assertEqual(result.x, 48.0)
        self.assertEqual(result.y, 99.0)
        self.assertEqual(result.width, 4.0)
        self.assertEqual(result.height, 2.0)
        bridge.assert_called_once_with(
            "draw_rectangle",
            expected_process_id=22188,
            window_title_contains="Demo Part",
            require_part_editor=True,
            width=4.0,
            height=2.0,
            gap=None,
            x=48.0,
            y=99.0,
            center_on_bounds=False,
            use_explicit_position=True,
        )

    def test_live_application_close_is_noop_and_context_manager_returns_self(self) -> None:
        session = RadanLiveSessionInfo(
            application=RadanApplicationInfo(
                prog_id="Radraft.Application",
                backend="fake",
                name="Mazak Smart System",
                full_name=r"C:\Program Files\Mazak\Mazak\bin\radraft",
                path=r"C:\Program Files\Mazak\Mazak\bin",
                software_version="2025.1.2523.1252",
                process_id=22188,
                visible=True,
                interactive=True,
                gui_state=4,
                gui_sub_state=14,
            ),
            window_title="Demo Part - Mazak Smart System Part Editor",
            editor_mode="part",
            pattern="/symbol editor",
            bounds=RadanBounds(left=10.0, bottom=20.0, right=30.0, top=50.0),
        )
        live = RadanLiveApplication(
            session,
            backend="fake",
            expected_process_id=22188,
            title_guard_contains="Demo Part",
            require_part_editor=True,
        )

        with live as attached:
            self.assertIs(attached, live)
            self.assertEqual(attached.process_id, 22188)

        self.assertEqual(live.window_title, "Demo Part - Mazak Smart System Part Editor")
        live.close()
        self.assertEqual(live.process_id, 22188)

if __name__ == "__main__":
    unittest.main()
