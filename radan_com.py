from __future__ import annotations

import json
import os
import subprocess
import time
import uuid
from typing import Any

try:
    from .radan_backends import _Backend, _make_backend, available_radan_backends
    from .radan_mac import RadanMac
    from .radan_models import (
        DEFAULT_RADRAFT_PROG_ID,
        DEFAULT_RASTER_TO_VECTOR_PROG_ID,
        RadanApplicationInfo,
        RadanBounds,
        RadanComError,
        RadanComProtocolError,
        RadanComUnavailableError,
        RadanDocumentInfo,
        RadanLicenseInfo,
        RadanLiveSessionInfo,
        RadanRectangleResult,
        RadanReportResult,
        RadanTargetMismatchError,
        RadanVisibleSessionInfo,
        _RASTER_IMAGE_EXTENSIONS,
        _SYMBOL_EXTENSIONS,
    )
    from .radan_utils import (
        _coerce_bool,
        _coerce_float,
        _coerce_int,
        _coerce_str,
        _contains_case_insensitive,
        _infer_document_kind_from_path,
        _infer_editor_mode,
        _parse_report_result,
    )
except ImportError:
    from radan_backends import _Backend, _make_backend, available_radan_backends
    from radan_mac import RadanMac
    from radan_models import (
        DEFAULT_RADRAFT_PROG_ID,
        DEFAULT_RASTER_TO_VECTOR_PROG_ID,
        RadanApplicationInfo,
        RadanBounds,
        RadanComError,
        RadanComProtocolError,
        RadanComUnavailableError,
        RadanDocumentInfo,
        RadanLicenseInfo,
        RadanLiveSessionInfo,
        RadanRectangleResult,
        RadanReportResult,
        RadanTargetMismatchError,
        RadanVisibleSessionInfo,
        _RASTER_IMAGE_EXTENSIONS,
        _SYMBOL_EXTENSIONS,
    )
    from radan_utils import (
        _coerce_bool,
        _coerce_float,
        _coerce_int,
        _coerce_str,
        _contains_case_insensitive,
        _infer_document_kind_from_path,
        _infer_editor_mode,
        _parse_report_result,
    )

__all__ = [
    "DEFAULT_RADRAFT_PROG_ID",
    "DEFAULT_RASTER_TO_VECTOR_PROG_ID",
    "RadanApplication",
    "RadanApplicationInfo",
    "RadanBounds",
    "RadanComError",
    "RadanComProtocolError",
    "RadanComUnavailableError",
    "RadanDocumentInfo",
    "RadanLicenseInfo",
    "RadanLiveApplication",
    "RadanLiveSessionInfo",
    "RadanMac",
    "RadanRectangleResult",
    "RadanReportResult",
    "RadanTargetMismatchError",
    "RadanVisibleSessionInfo",
    "_Backend",
    "_RASTER_IMAGE_EXTENSIONS",
    "_SYMBOL_EXTENSIONS",
    "_coerce_bool",
    "_coerce_float",
    "_coerce_int",
    "_coerce_str",
    "_contains_case_insensitive",
    "_infer_document_kind_from_path",
    "_infer_editor_mode",
    "_make_backend",
    "_parse_report_result",
    "attach_application",
    "attach_live_application",
    "available_radan_backends",
    "describe_live_session",
    "list_visible_radan_sessions",
    "open_application",
    "probe_application",
]


def _get_process_window_title(process_id: int | None) -> str | None:
    if process_id is None or os.name != "nt":
        return None

    command = [
        "powershell",
        "-NoProfile",
        "-Command",
        (
            f"$p = Get-Process -Id {int(process_id)} -ErrorAction SilentlyContinue; "
            "if ($null -ne $p) { $p.MainWindowTitle }"
        ),
    ]
    try:
        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except Exception:
        return None

    title = result.stdout.strip()
    return title or None


def list_visible_radan_sessions() -> list[RadanVisibleSessionInfo]:
    if os.name != "nt":
        return []

    command = [
        "powershell",
        "-NoProfile",
        "-Command",
        (
            "$items = Get-Process RADRAFT -ErrorAction SilentlyContinue | "
            "Where-Object { $_.MainWindowHandle -ne 0 -and -not [string]::IsNullOrWhiteSpace($_.MainWindowTitle) } | "
            "Sort-Object Id | "
            "Select-Object @{Name='ProcessId';Expression={$_.Id}}, @{Name='WindowTitle';Expression={$_.MainWindowTitle}}; "
            "if ($items) { $items | ConvertTo-Json -Depth 3 }"
        ),
    ]

    try:
        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except Exception:
        return []

    output = result.stdout.strip()
    if not output:
        return []

    try:
        payload = json.loads(output)
    except json.JSONDecodeError:
        return []

    items: list[dict[str, Any]]
    if isinstance(payload, dict):
        items = [payload]
    elif isinstance(payload, list):
        items = [item for item in payload if isinstance(item, dict)]
    else:
        return []

    sessions: list[RadanVisibleSessionInfo] = []
    for item in items:
        process_id = _coerce_int(item.get("ProcessId"))
        window_title = _coerce_str(item.get("WindowTitle"))
        if process_id is None or not window_title:
            continue
        sessions.append(
            RadanVisibleSessionInfo(
                process_id=process_id,
                window_title=window_title,
                editor_mode=_infer_editor_mode(window_title),
            )
        )

    return sessions


def _select_visible_radan_session(
    *,
    expected_process_id: int | None = None,
    window_title_contains: str | None = None,
    require_part_editor: bool = False,
) -> RadanVisibleSessionInfo:
    sessions = list_visible_radan_sessions()
    if not sessions:
        raise RadanComUnavailableError("No visible RADAN UI session was found.")

    matches = sessions
    if expected_process_id is not None:
        matches = [session for session in matches if session.process_id == expected_process_id]
        if not matches:
            raise RadanTargetMismatchError(
                f"No visible RADAN UI session matched expected PID {expected_process_id}."
            )

    if window_title_contains:
        titled_matches = [
            session
            for session in matches
            if _contains_case_insensitive(session.window_title, window_title_contains)
        ]
        if not titled_matches:
            if len(matches) == 1:
                raise RadanTargetMismatchError(
                    f"Attached RADAN window {matches[0].window_title!r} does not contain {window_title_contains!r}."
                )
            raise RadanTargetMismatchError(
                f"No visible RADAN window title contains {window_title_contains!r}."
            )
        matches = titled_matches

    if require_part_editor:
        part_matches = [session for session in matches if session.editor_mode == "part"]
        if not part_matches:
            if len(matches) == 1:
                raise RadanTargetMismatchError(
                    f"Attached RADAN window is in {matches[0].editor_mode or 'unknown'} mode, not Part Editor."
                )
            raise RadanTargetMismatchError("No visible RADAN session is in Part Editor mode.")
        matches = part_matches

    if len(matches) > 1:
        raise RadanTargetMismatchError(
            "Multiple visible RADAN UI sessions matched the current filters. "
            "Pass expected_process_id or window_title_contains to disambiguate."
        )

    return matches[0]


def _make_visible_window_application_info(session: RadanVisibleSessionInfo) -> RadanApplicationInfo:
    return RadanApplicationInfo(
        prog_id=DEFAULT_RADRAFT_PROG_ID,
        backend="visible-window",
        name="Mazak Smart System",
        full_name=None,
        path=None,
        software_version=None,
        process_id=session.process_id,
        visible=True,
        interactive=True,
        gui_state=None,
        gui_sub_state=None,
    )


def _make_host_bridge_application_info(
    payload: dict[str, Any],
    visible_session: RadanVisibleSessionInfo,
) -> RadanApplicationInfo:
    return RadanApplicationInfo(
        prog_id=DEFAULT_RADRAFT_PROG_ID,
        backend="host-bridge",
        name="Mazak Smart System",
        full_name=None,
        path=None,
        software_version=None,
        process_id=_coerce_int(payload.get("ProcessId")) or visible_session.process_id,
        visible=_coerce_bool(payload.get("Visible")),
        interactive=True,
        gui_state=None,
        gui_sub_state=None,
    )


def _default_live_bridge_dir() -> str:
    return os.path.join(os.path.dirname(__file__), "_runtime", "live_bridge")


def _live_bridge_dir() -> str:
    configured = os.environ.get("RADAN_LIVE_BRIDGE_DIR", "").strip()
    if configured:
        return os.path.abspath(os.path.expanduser(configured))
    return _default_live_bridge_dir()


def _live_bridge_ready_path(bridge_dir: str | None = None) -> str:
    root = bridge_dir or _live_bridge_dir()
    return os.path.join(root, "ready.json")


def _host_live_bridge_is_ready(bridge_dir: str | None = None) -> bool:
    return os.path.exists(_live_bridge_ready_path(bridge_dir))


def _live_bridge_timeout_seconds() -> float:
    raw = os.environ.get("RADAN_LIVE_BRIDGE_TIMEOUT_SEC", "").strip()
    if raw:
        try:
            value = float(raw)
            if value > 0:
                return value
        except ValueError:
            pass
    return 15.0


def _write_json_atomic(path: str, payload: dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temp_path = f"{path}.tmp-{os.getpid()}-{uuid.uuid4().hex}"
    with open(temp_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle)
    os.replace(temp_path, path)


def _run_local_live_session_bridge(
    action: str,
    *,
    expected_process_id: int | None = None,
    window_title_contains: str | None = None,
    require_part_editor: bool = False,
    width: float | None = None,
    height: float | None = None,
    gap: float | None = None,
    x: float | None = None,
    y: float | None = None,
    center_on_bounds: bool = False,
    use_explicit_position: bool = False,
) -> dict[str, Any]:
    if os.name != "nt":
        raise RadanComUnavailableError("Live session bridge is only available on Windows.")

    bridge_path = os.path.join(os.path.dirname(__file__), "live_session_bridge.ps1")
    command: list[str] = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        bridge_path,
        "-Action",
        action,
    ]

    if expected_process_id is not None:
        command.extend(["-ExpectedProcessId", str(int(expected_process_id))])
    if window_title_contains:
        command.extend(["-WindowTitleContains", window_title_contains])
    if require_part_editor:
        command.append("-RequirePartEditor")
    if width is not None:
        command.extend(["-Width", str(float(width))])
    if height is not None:
        command.extend(["-Height", str(float(height))])
    if gap is not None:
        command.extend(["-Gap", str(float(gap))])
    if x is not None:
        command.extend(["-X", str(float(x))])
    if y is not None:
        command.extend(["-Y", str(float(y))])
    if center_on_bounds:
        command.append("-CenterOnBounds")
    if use_explicit_position:
        command.append("-UseExplicitPosition")

    try:
        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except subprocess.CalledProcessError as exc:
        message = (exc.stderr or exc.stdout or str(exc)).strip()
        raise RadanComError(f"Live session bridge failed: {message}") from exc
    except Exception as exc:
        raise RadanComError("Failed to start the live session bridge.") from exc

    output = result.stdout.strip()
    if not output:
        raise RadanComProtocolError("Live session bridge returned no JSON output.")

    try:
        payload = json.loads(output)
    except json.JSONDecodeError as exc:
        raise RadanComProtocolError(f"Live session bridge returned invalid JSON: {output!r}") from exc

    if not isinstance(payload, dict):
        raise RadanComProtocolError(f"Live session bridge returned unexpected payload: {payload!r}")
    return payload


def _run_host_live_session_bridge(
    action: str,
    *,
    expected_process_id: int | None = None,
    window_title_contains: str | None = None,
    require_part_editor: bool = False,
    width: float | None = None,
    height: float | None = None,
    gap: float | None = None,
    x: float | None = None,
    y: float | None = None,
    center_on_bounds: bool = False,
    use_explicit_position: bool = False,
) -> dict[str, Any]:
    bridge_dir = _live_bridge_dir()
    if not _host_live_bridge_is_ready(bridge_dir):
        raise RadanComUnavailableError("Host live bridge is not ready.")

    requests_dir = os.path.join(bridge_dir, "requests")
    responses_dir = os.path.join(bridge_dir, "responses")
    request_id = uuid.uuid4().hex
    request_path = os.path.join(requests_dir, f"{request_id}.json")
    response_path = os.path.join(responses_dir, f"{request_id}.json")

    request_payload: dict[str, Any] = {
        "request_id": request_id,
        "action": action,
    }
    if expected_process_id is not None:
        request_payload["expected_process_id"] = int(expected_process_id)
    if window_title_contains:
        request_payload["window_title_contains"] = window_title_contains
    if require_part_editor:
        request_payload["require_part_editor"] = True
    if width is not None:
        request_payload["width"] = float(width)
    if height is not None:
        request_payload["height"] = float(height)
    if gap is not None:
        request_payload["gap"] = float(gap)
    if x is not None:
        request_payload["x"] = float(x)
    if y is not None:
        request_payload["y"] = float(y)
    if center_on_bounds:
        request_payload["center_on_bounds"] = True
    if use_explicit_position:
        request_payload["use_explicit_position"] = True

    _write_json_atomic(request_path, request_payload)

    deadline = time.monotonic() + _live_bridge_timeout_seconds()
    try:
        while time.monotonic() < deadline:
            if os.path.exists(response_path):
                try:
                    with open(response_path, "r", encoding="utf-8") as handle:
                        response = json.load(handle)
                finally:
                    try:
                        os.remove(response_path)
                    except OSError:
                        pass

                if not isinstance(response, dict):
                    raise RadanComProtocolError(
                        f"Host live bridge returned an unexpected payload: {response!r}"
                    )
                if not response.get("ok"):
                    error = str(response.get("error") or "Unknown host live bridge error.")
                    raise RadanComError(f"Host live bridge call failed: {error}")

                payload = response.get("payload")
                if not isinstance(payload, dict):
                    raise RadanComProtocolError(
                        f"Host live bridge returned an invalid payload: {payload!r}"
                    )
                return payload

            time.sleep(0.1)
    finally:
        try:
            if os.path.exists(request_path):
                os.remove(request_path)
        except OSError:
            pass

    raise RadanComUnavailableError(
        f"Timed out waiting for a host live bridge response in {bridge_dir!r}."
    )


def _run_live_session_bridge(
    action: str,
    *,
    expected_process_id: int | None = None,
    window_title_contains: str | None = None,
    require_part_editor: bool = False,
    width: float | None = None,
    height: float | None = None,
    gap: float | None = None,
    x: float | None = None,
    y: float | None = None,
    center_on_bounds: bool = False,
    use_explicit_position: bool = False,
) -> dict[str, Any]:
    local_error: RadanComError | None = None
    try:
        return _run_local_live_session_bridge(
            action,
            expected_process_id=expected_process_id,
            window_title_contains=window_title_contains,
            require_part_editor=require_part_editor,
            width=width,
            height=height,
            gap=gap,
            x=x,
            y=y,
            center_on_bounds=center_on_bounds,
            use_explicit_position=use_explicit_position,
        )
    except RadanComError as exc:
        local_error = exc

    if _host_live_bridge_is_ready():
        try:
            return _run_host_live_session_bridge(
                action,
                expected_process_id=expected_process_id,
                window_title_contains=window_title_contains,
                require_part_editor=require_part_editor,
                width=width,
                height=height,
                gap=gap,
                x=x,
                y=y,
                center_on_bounds=center_on_bounds,
                use_explicit_position=use_explicit_position,
            )
        except RadanComError as bridge_exc:
            if local_error is not None:
                raise RadanComError(
                    f"{local_error} Host live bridge also failed: {bridge_exc}"
                ) from bridge_exc
            raise

    if local_error is not None:
        raise local_error
    raise RadanComError("Live session bridge failed for an unknown reason.")


def _parse_bounds(payload: dict[str, Any]) -> RadanBounds | None:
    if not _coerce_bool(payload.get("BoundsAvailable")):
        return None

    left = _coerce_float(payload.get("Left"))
    bottom = _coerce_float(payload.get("Bottom"))
    right = _coerce_float(payload.get("Right"))
    top = _coerce_float(payload.get("Top"))
    if None in {left, bottom, right, top}:
        return None

    return RadanBounds(left=left, bottom=bottom, right=right, top=top)


def _make_live_session_info(
    application: RadanApplicationInfo,
    payload: dict[str, Any],
    *,
    window_title: str | None = None,
) -> RadanLiveSessionInfo:
    title = window_title if window_title is not None else _coerce_str(payload.get("WindowTitle"))
    return RadanLiveSessionInfo(
        application=application,
        window_title=title,
        editor_mode=_infer_editor_mode(title),
        pattern=_coerce_str(payload.get("Pattern")),
        bounds=_parse_bounds(payload),
    )


class RadanLiveApplication:
    def __init__(
        self,
        session: RadanLiveSessionInfo,
        *,
        backend: str | None = None,
        expected_process_id: int | None = None,
        title_guard_contains: str | None = None,
        require_part_editor: bool = False,
    ) -> None:
        self._session = session
        self._backend = backend
        self._expected_process_id = expected_process_id if expected_process_id is not None else session.process_id
        self._title_guard_contains = title_guard_contains
        self._require_part_editor = require_part_editor

    @property
    def session(self) -> RadanLiveSessionInfo:
        return self._session

    @property
    def process_id(self) -> int | None:
        return self._session.process_id

    @property
    def window_title(self) -> str | None:
        return self._session.window_title

    @property
    def bounds(self) -> RadanBounds | None:
        return self._session.bounds

    @property
    def editor_mode(self) -> str | None:
        return self._session.editor_mode

    def refresh(self) -> RadanLiveSessionInfo:
        self._session = describe_live_session(
            backend=self._backend,
            expected_process_id=self._expected_process_id,
            window_title_contains=self._title_guard_contains,
            require_part_editor=self._require_part_editor,
        )
        return self._session

    def assert_target_matches(
        self,
        *,
        expected_process_id: int | None = None,
        window_title_contains: str | None = None,
        require_part_editor: bool | None = None,
    ) -> RadanLiveSessionInfo:
        session = self.refresh()

        if expected_process_id is not None and session.process_id != expected_process_id:
            raise RadanTargetMismatchError(
                f"Attached RADAN PID {session.process_id} does not match expected PID {expected_process_id}."
            )
        if not _contains_case_insensitive(session.window_title, window_title_contains):
            raise RadanTargetMismatchError(
                f"Attached RADAN window {session.window_title!r} does not contain {window_title_contains!r}."
            )
        if require_part_editor and session.editor_mode != "part":
            raise RadanTargetMismatchError(
                f"Attached RADAN window is in {session.editor_mode or 'unknown'} mode, not Part Editor."
            )
        return session

    def _draw_rectangle(
        self,
        *,
        width: float,
        height: float,
        gap: float | None = None,
        x: float | None = None,
        y: float | None = None,
        center_on_bounds: bool = False,
        use_explicit_position: bool = False,
    ) -> RadanRectangleResult:
        process_id = self._expected_process_id if self._expected_process_id is not None else self.process_id
        if process_id is None:
            raise RadanTargetMismatchError("No live RADAN process is associated with this session.")

        payload = _run_live_session_bridge(
            "draw_rectangle",
            expected_process_id=process_id,
            window_title_contains=self._title_guard_contains,
            require_part_editor=True,
            width=width,
            height=height,
            gap=gap,
            x=x,
            y=y,
            center_on_bounds=center_on_bounds,
            use_explicit_position=use_explicit_position,
        )
        session = self.refresh()

        rect_x = _coerce_float(payload.get("RectangleX"))
        rect_y = _coerce_float(payload.get("RectangleY"))
        rect_width = _coerce_float(payload.get("RectangleWidth"))
        rect_height = _coerce_float(payload.get("RectangleHeight"))
        if None in {rect_x, rect_y, rect_width, rect_height}:
            raise RadanComProtocolError(f"Rectangle bridge payload was incomplete: {payload!r}")

        return RadanRectangleResult(
            session=session,
            x=rect_x,
            y=rect_y,
            width=rect_width,
            height=rect_height,
        )

    def draw_rectangle_centered(self, *, width: float, height: float) -> RadanRectangleResult:
        return self._draw_rectangle(width=width, height=height, center_on_bounds=True)

    def draw_rectangle_at(self, *, x: float, y: float, width: float, height: float) -> RadanRectangleResult:
        return self._draw_rectangle(
            x=x,
            y=y,
            width=width,
            height=height,
            use_explicit_position=True,
        )

    def draw_rectangle_at_center(
        self,
        *,
        center_x: float,
        center_y: float,
        width: float,
        height: float,
    ) -> RadanRectangleResult:
        return self.draw_rectangle_at(
            x=float(center_x) - (float(width) / 2.0),
            y=float(center_y) - (float(height) / 2.0),
            width=width,
            height=height,
        )

    def draw_rectangle_right_of_bounds(
        self,
        *,
        width: float,
        height: float,
        gap: float = 10.0,
    ) -> RadanRectangleResult:
        return self._draw_rectangle(width=width, height=height, gap=gap)

    def close(self) -> None:
        # Live attach objects do not own the target RADAN UI process.
        # This method exists so callers can use a uniform cleanup pattern.
        return None

    def __enter__(self) -> "RadanLiveApplication":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.close()


class RadanApplication:
    """Small Python wrapper around the `Radraft.Application` COM object."""

    def __init__(
        self,
        prog_id: str = DEFAULT_RADRAFT_PROG_ID,
        backend: str | None = None,
        create_if_missing: bool = True,
        force_new_instance: bool = False,
    ) -> None:
        self.prog_id = prog_id
        self._backend = _make_backend(
            prog_id,
            backend=backend,
            create_if_missing=create_if_missing,
            force_new_instance=force_new_instance,
        )

    @property
    def backend_name(self) -> str:
        return self._backend.backend_name

    @property
    def created_new_instance(self) -> bool:
        return bool(getattr(self._backend, "created_new_instance", False))

    def close(self) -> None:
        self._backend.close()

    def __enter__(self) -> "RadanApplication":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.close()

    def _safe_get(self, property_name: str) -> Any:
        try:
            return self._backend.get_property(property_name)
        except RadanComError:
            return None

    @property
    def mac(self) -> RadanMac:
        return RadanMac(self._backend)

    def info(self) -> RadanApplicationInfo:
        return RadanApplicationInfo(
            prog_id=self.prog_id,
            backend=self.backend_name,
            name=self._safe_get("Name"),
            full_name=self._safe_get("FullName"),
            path=self._safe_get("Path"),
            software_version=self._safe_get("SoftwareVersion"),
            process_id=_coerce_int(self._safe_get("ProcessID")),
            visible=_coerce_bool(self._safe_get("Visible")),
            interactive=_coerce_bool(self._safe_get("Interactive")),
            gui_state=_coerce_int(self._safe_get("GUIState")),
            gui_sub_state=_coerce_int(self._safe_get("GUISubState")),
        )

    @property
    def visible(self) -> bool | None:
        return _coerce_bool(self._backend.get_property("Visible"))

    @visible.setter
    def visible(self, value: bool) -> None:
        self._backend.set_property("Visible", bool(value))

    @property
    def interactive(self) -> bool | None:
        return _coerce_bool(self._backend.get_property("Interactive"))

    @interactive.setter
    def interactive(self, value: bool) -> None:
        self._backend.set_property("Interactive", bool(value))

    def new_drawing(self, use_default_settings: bool = False) -> None:
        self._backend.call_method("NewDrawing", bool(use_default_settings))

    def new_symbol(self, use_default_settings: bool = False) -> None:
        self._backend.call_method("NewSymbol", bool(use_default_settings))

    def active_document_info(self) -> RadanDocumentInfo | None:
        try:
            document_type = self._backend.get_path_property(("ActiveDocument",), "Type")
            dirty = self._backend.get_path_property(("ActiveDocument",), "Dirty")
        except RadanComError:
            return None

        return RadanDocumentInfo(
            document_type=_coerce_int(document_type),
            dirty=_coerce_bool(dirty),
        )

    def close_active_document(self, discard_changes: bool = True) -> None:
        self._backend.call_path_method(("ActiveDocument",), "Close", bool(discard_changes))

    def save_active_document(self) -> None:
        self._backend.call_path_method(("ActiveDocument",), "Save")

    def save_active_document_as(self, path: str) -> None:
        self._backend.call_path_method(("ActiveDocument",), "SaveAs", path)

    def save_copy_of_active_document_as(self, path: str, options_file_path: str = "") -> None:
        self._backend.call_path_method(("ActiveDocument",), "SaveCopyAs", path, options_file_path)

    def open_drawing(self, path: str, read_only: bool = False, password: str = "") -> None:
        self._backend.call_method("OpenDrawing", path, bool(read_only), password)

    def open_symbol(self, path: str, read_only: bool = False, password: str = "") -> None:
        self._backend.call_method("OpenSymbol", path, bool(read_only), password)

    def open_symbol_from_raster_image(self, path: str, read_only: bool = False, password: str = "") -> None:
        self._backend.call_method("OpenSymbolFromRasterImage", path, bool(read_only), password)

    def open_document(self, path: str, read_only: bool = False, password: str = "") -> None:
        kind = _infer_document_kind_from_path(path)
        if kind == "symbol":
            self.open_symbol(path, read_only=read_only, password=password)
            return
        if kind == "symbol_from_raster":
            self.open_symbol_from_raster_image(path, read_only=read_only, password=password)
            return
        self.open_drawing(path, read_only=read_only, password=password)

    def quit(self) -> bool | None:
        return _coerce_bool(self._backend.call_method("Quit"))


def open_application(
    backend: str | None = None,
    create_if_missing: bool = True,
    force_new_instance: bool = False,
) -> RadanApplication:
    return RadanApplication(
        backend=backend,
        create_if_missing=create_if_missing,
        force_new_instance=force_new_instance,
    )


def attach_application(backend: str | None = None) -> RadanApplication:
    return RadanApplication(backend=backend, create_if_missing=False)


def describe_live_session(
    backend: str | None = None,
    *,
    expected_process_id: int | None = None,
    window_title_contains: str | None = None,
    require_part_editor: bool = False,
) -> RadanLiveSessionInfo:
    try:
        with attach_application(backend=backend) as app:
            info = app.info()

        if info.process_id is None:
            raise RadanComUnavailableError("Attached RADAN session did not expose a process ID.")
        if expected_process_id is not None and info.process_id != expected_process_id:
            raise RadanTargetMismatchError(
                f"Attached RADAN PID {info.process_id} does not match expected PID {expected_process_id}."
            )

        window_title = _get_process_window_title(info.process_id)
        if not _contains_case_insensitive(window_title, window_title_contains):
            raise RadanTargetMismatchError(
                f"Attached RADAN window {window_title!r} does not contain {window_title_contains!r}."
            )
        editor_mode = _infer_editor_mode(window_title)
        if require_part_editor and editor_mode != "part":
            raise RadanTargetMismatchError(
                f"Attached RADAN window is in {editor_mode or 'unknown'} mode, not Part Editor."
            )

        payload = _run_live_session_bridge(
            "describe",
            expected_process_id=info.process_id,
            window_title_contains=window_title_contains,
            require_part_editor=require_part_editor,
        )
        return _make_live_session_info(info, payload, window_title=window_title)
    except RadanTargetMismatchError:
        raise
    except RadanComError:
        visible_session = _select_visible_radan_session(
            expected_process_id=expected_process_id,
            window_title_contains=window_title_contains,
            require_part_editor=require_part_editor,
        )
        if _host_live_bridge_is_ready():
            try:
                payload = _run_live_session_bridge(
                    "describe",
                    expected_process_id=visible_session.process_id,
                    window_title_contains=window_title_contains,
                    require_part_editor=require_part_editor,
                )
                return _make_live_session_info(
                    _make_host_bridge_application_info(payload, visible_session),
                    payload,
                    window_title=visible_session.window_title,
                )
            except RadanComError:
                pass
        return RadanLiveSessionInfo(
            application=_make_visible_window_application_info(visible_session),
            window_title=visible_session.window_title,
            editor_mode=visible_session.editor_mode,
            pattern=None,
            bounds=None,
        )


def attach_live_application(
    backend: str | None = None,
    *,
    expected_process_id: int | None = None,
    window_title_contains: str | None = None,
    require_part_editor: bool = False,
) -> RadanLiveApplication:
    session = describe_live_session(
        backend=backend,
        expected_process_id=expected_process_id,
        window_title_contains=window_title_contains,
        require_part_editor=require_part_editor,
    )
    if session.application.backend == "visible-window":
        raise RadanComUnavailableError(
            "A visible RADAN window was found, but no attachable live automation session is currently available."
        )
    return RadanLiveApplication(
        session,
        backend=backend,
        expected_process_id=expected_process_id,
        title_guard_contains=window_title_contains,
        require_part_editor=require_part_editor,
    )


def probe_application(backend: str | None = None, force_new_instance: bool = False) -> RadanApplicationInfo:
    with open_application(backend=backend, force_new_instance=force_new_instance) as app:
        info = app.info()
        if app.created_new_instance:
            try:
                app.quit()
            except Exception:
                pass
        return info


if __name__ == "__main__":
    info = probe_application()
    print(json.dumps(info.__dict__, indent=2))
