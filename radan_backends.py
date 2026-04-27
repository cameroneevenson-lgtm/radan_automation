from __future__ import annotations

import json
import os
import subprocess
from typing import Any

try:
    import win32com.client as win32_client  # type: ignore[import-not-found]
except ImportError:
    win32_client = None

try:
    import comtypes.client as comtypes_client  # type: ignore[import-not-found]
except ImportError:
    comtypes_client = None

try:
    from .radan_models import RadanComError, RadanComProtocolError, RadanComUnavailableError
except ImportError:
    from radan_models import RadanComError, RadanComProtocolError, RadanComUnavailableError


class _Backend:
    backend_name = "unknown"
    created_new_instance = False

    def get_property(self, name: str) -> Any:
        raise NotImplementedError

    def set_property(self, name: str, value: Any) -> None:
        raise NotImplementedError

    def call_method(self, name: str, *args: Any) -> Any:
        raise NotImplementedError

    def close(self) -> None:
        return None

    def get_path_property(self, path: tuple[str, ...], name: str) -> Any:
        raise NotImplementedError

    def call_path_method(self, path: tuple[str, ...], name: str, *args: Any) -> Any:
        raise NotImplementedError


class _Win32ComBackend(_Backend):
    backend_name = "win32com"

    def __init__(self, prog_id: str, create_if_missing: bool = True, force_new_instance: bool = False) -> None:
        if win32_client is None:
            raise RadanComUnavailableError("win32com is not installed.")
        if force_new_instance:
            try:
                dispatch_ex = getattr(win32_client, "DispatchEx", None)
                if dispatch_ex is None:
                    raise RadanComUnavailableError("win32com DispatchEx is not available.")
                self._dispatch = dispatch_ex(prog_id)
                self.created_new_instance = True
                return
            except Exception as exc:
                raise RadanComError(f"Failed to create a fresh {prog_id!r} via win32com.") from exc
        try:
            self._dispatch = win32_client.GetActiveObject(prog_id)
            self.created_new_instance = False
        except Exception:
            if not create_if_missing:
                raise RadanComUnavailableError(f"No active COM object is registered for {prog_id!r}.")
            try:
                self._dispatch = win32_client.Dispatch(prog_id)
                self.created_new_instance = True
            except Exception as exc:
                raise RadanComError(f"Failed to activate {prog_id!r} via win32com.") from exc

    def get_property(self, name: str) -> Any:
        return getattr(self._dispatch, name)

    def set_property(self, name: str, value: Any) -> None:
        setattr(self._dispatch, name, value)

    def call_method(self, name: str, *args: Any) -> Any:
        return getattr(self._dispatch, name)(*args)

    def _resolve_path(self, path: tuple[str, ...]) -> Any:
        target = self._dispatch
        for segment in path:
            target = getattr(target, segment)
        return target

    def get_path_property(self, path: tuple[str, ...], name: str) -> Any:
        return getattr(self._resolve_path(path), name)

    def call_path_method(self, path: tuple[str, ...], name: str, *args: Any) -> Any:
        return getattr(self._resolve_path(path), name)(*args)

    def close(self) -> None:
        self._dispatch = None


class _ComtypesBackend(_Backend):
    backend_name = "comtypes"

    def __init__(self, prog_id: str, create_if_missing: bool = True, force_new_instance: bool = False) -> None:
        if comtypes_client is None:
            raise RadanComUnavailableError("comtypes is not installed.")
        if force_new_instance:
            try:
                self._dispatch = comtypes_client.CreateObject(prog_id, dynamic=True)
                self.created_new_instance = True
                return
            except Exception as exc:
                raise RadanComError(f"Failed to create a fresh {prog_id!r} via comtypes.") from exc
        try:
            self._dispatch = comtypes_client.GetActiveObject(prog_id, dynamic=True)
            self.created_new_instance = False
        except Exception:
            if not create_if_missing:
                raise RadanComUnavailableError(f"No active COM object is registered for {prog_id!r}.")
            try:
                self._dispatch = comtypes_client.CreateObject(prog_id, dynamic=True)
                self.created_new_instance = True
            except Exception as exc:
                raise RadanComError(f"Failed to activate {prog_id!r} via comtypes.") from exc

    def get_property(self, name: str) -> Any:
        return getattr(self._dispatch, name)

    def set_property(self, name: str, value: Any) -> None:
        setattr(self._dispatch, name, value)

    def call_method(self, name: str, *args: Any) -> Any:
        return getattr(self._dispatch, name)(*args)

    def _resolve_path(self, path: tuple[str, ...]) -> Any:
        target = self._dispatch
        for segment in path:
            target = getattr(target, segment)
        return target

    def get_path_property(self, path: tuple[str, ...], name: str) -> Any:
        return getattr(self._resolve_path(path), name)

    def call_path_method(self, path: tuple[str, ...], name: str, *args: Any) -> Any:
        return getattr(self._resolve_path(path), name)(*args)

    def close(self) -> None:
        self._dispatch = None


class _PowerShellBridgeBackend(_Backend):
    backend_name = "powershell"

    def __init__(self, prog_id: str, create_if_missing: bool = True, force_new_instance: bool = False) -> None:
        if os.name != "nt":
            raise RadanComUnavailableError("PowerShell COM bridge is only available on Windows.")
        if force_new_instance and not create_if_missing:
            raise RadanComUnavailableError("force_new_instance cannot be combined with attach-only mode.")
        bridge_path = os.path.join(os.path.dirname(__file__), "radan_com_bridge.ps1")
        command = [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            bridge_path,
        ]
        if not force_new_instance:
            command.append("-AttachActive")
        if not create_if_missing:
            command.append("-AttachOnly")
        command.extend(["-ProgId", prog_id])
        try:
            self._process = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                bufsize=1,
            )
        except Exception as exc:
            raise RadanComError("Failed to start the PowerShell RADAN COM bridge.") from exc

        ready = self._read_response(expect_ready=True)
        if not ready.get("ok"):
            error = ready.get("error") or "Unknown startup error."
            raise RadanComError(f"PowerShell RADAN COM bridge failed to start: {error}")
        self.created_new_instance = bool(ready.get("created_new"))

    def _read_response(self, *, expect_ready: bool = False) -> dict[str, Any]:
        if self._process.stdout is None:
            raise RadanComProtocolError("PowerShell bridge stdout is unavailable.")

        line = self._process.stdout.readline()
        if not line:
            stderr = ""
            if self._process.stderr is not None:
                stderr = self._process.stderr.read().strip()
            message = "PowerShell bridge terminated unexpectedly."
            if stderr:
                message = f"{message} {stderr}"
            raise RadanComProtocolError(message)

        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise RadanComProtocolError(f"PowerShell bridge returned invalid JSON: {line!r}") from exc

        if expect_ready and payload.get("event") not in {"ready", "startup_error"}:
            raise RadanComProtocolError(f"Unexpected PowerShell bridge handshake: {payload!r}")

        return payload

    def _request(self, action: str, **kwargs: Any) -> Any:
        if self._process.stdin is None:
            raise RadanComProtocolError("PowerShell bridge stdin is unavailable.")

        payload = {"action": action, **kwargs}
        self._process.stdin.write(json.dumps(payload) + "\n")
        self._process.stdin.flush()
        response = self._read_response()
        if not response.get("ok"):
            error = response.get("error") or "Unknown bridge error."
            raise RadanComError(f"PowerShell bridge call failed: {error}")
        return response.get("result")

    def get_property(self, name: str) -> Any:
        return self._request("get_property", name=name)

    def set_property(self, name: str, value: Any) -> None:
        self._request("set_property", name=name, value=value)

    def call_method(self, name: str, *args: Any) -> Any:
        return self._request("call_method", name=name, args=list(args))

    def get_path_property(self, path: tuple[str, ...], name: str) -> Any:
        return self._request("get_path_property", path=list(path), name=name)

    def call_path_method(self, path: tuple[str, ...], name: str, *args: Any) -> Any:
        return self._request("call_path_method", path=list(path), name=name, args=list(args))

    def close(self) -> None:
        process = getattr(self, "_process", None)
        if process is None:
            return

        try:
            self._request("dispose")
        except Exception:
            pass

        try:
            if process.stdin is not None:
                process.stdin.close()
        finally:
            if process.stdout is not None:
                process.stdout.close()
            if process.stderr is not None:
                process.stderr.close()
            process.wait(timeout=5)
        self._process = None


def available_radan_backends() -> list[str]:
    backends: list[str] = []
    if win32_client is not None:
        backends.append("win32com")
    if comtypes_client is not None:
        backends.append("comtypes")
    if os.name == "nt":
        backends.append("powershell")
    return backends


def _make_backend(
    prog_id: str,
    backend: str | None = None,
    create_if_missing: bool = True,
    force_new_instance: bool = False,
) -> _Backend:
    backend_factories = {
        "win32com": _Win32ComBackend,
        "comtypes": _ComtypesBackend,
        "powershell": _PowerShellBridgeBackend,
    }

    if backend is not None:
        if backend not in backend_factories:
            raise RadanComUnavailableError(f"Unknown RADAN backend: {backend}")
        return backend_factories[backend](
            prog_id,
            create_if_missing=create_if_missing,
            force_new_instance=force_new_instance,
        )

    errors: list[str] = []
    for candidate in ("win32com", "comtypes", "powershell"):
        factory = backend_factories[candidate]
        try:
            return factory(
                prog_id,
                create_if_missing=create_if_missing,
                force_new_instance=force_new_instance,
            )
        except RadanComUnavailableError as exc:
            errors.append(str(exc))
        except RadanComError as exc:
            errors.append(str(exc))

    joined = "; ".join(errors) if errors else "No backend candidates were tried."
    raise RadanComUnavailableError(f"Unable to activate {prog_id!r}. {joined}")
