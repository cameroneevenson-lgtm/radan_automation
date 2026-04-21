from __future__ import annotations

import argparse
import atexit
import getpass
import json
import os
from pathlib import Path
import subprocess
import time
import uuid
from typing import Any


def _default_bridge_dir() -> Path:
    return (Path(__file__).resolve().parent / "_runtime" / "live_bridge").resolve()


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.tmp-{os.getpid()}-{uuid.uuid4().hex}")
    with temp_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle)
    os.replace(temp_path, path)


def _claim_request(path: Path) -> Path | None:
    claimed = path.with_name(f"{path.stem}.working-{os.getpid()}.json")
    try:
        os.replace(path, claimed)
    except FileNotFoundError:
        return None
    except OSError:
        return None
    return claimed


def _bridge_command(script_path: Path, request: dict[str, Any]) -> list[str]:
    command: list[str] = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script_path),
        "-Action",
        str(request.get("action") or "describe"),
    ]

    expected_process_id = request.get("expected_process_id")
    if expected_process_id is not None:
        command.extend(["-ExpectedProcessId", str(int(expected_process_id))])

    window_title_contains = str(request.get("window_title_contains") or "").strip()
    if window_title_contains:
        command.extend(["-WindowTitleContains", window_title_contains])

    if bool(request.get("require_part_editor")):
        command.append("-RequirePartEditor")

    for name in ("width", "height", "gap", "x", "y"):
        value = request.get(name)
        if value is not None:
            command.extend([f"-{name.capitalize()}", str(float(value))])

    if bool(request.get("center_on_bounds")):
        command.append("-CenterOnBounds")
    if bool(request.get("use_explicit_position")):
        command.append("-UseExplicitPosition")

    return command


def _run_request(script_path: Path, request: dict[str, Any]) -> dict[str, Any]:
    command = _bridge_command(script_path, request)
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
    except Exception as exc:
        return {"ok": False, "error": f"Failed to start live session bridge: {exc}"}

    stdout = str(completed.stdout or "").strip()
    stderr = str(completed.stderr or "").strip()
    if completed.returncode != 0:
        detail = stderr or stdout or f"exit code {completed.returncode}"
        return {"ok": False, "error": detail}
    if not stdout:
        return {"ok": False, "error": "Live session bridge returned no JSON output."}

    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        return {"ok": False, "error": f"Live session bridge returned invalid JSON: {exc}"}

    if not isinstance(payload, dict):
        return {"ok": False, "error": f"Live session bridge returned an unexpected payload: {payload!r}"}
    return {"ok": True, "payload": payload}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Serve live RADAN attach/draw requests from a shared bridge directory.",
    )
    parser.add_argument("--bridge-dir", default=str(_default_bridge_dir()))
    parser.add_argument("--poll-seconds", type=float, default=0.2)
    args = parser.parse_args()

    bridge_dir = Path(args.bridge_dir).expanduser().resolve()
    requests_dir = bridge_dir / "requests"
    responses_dir = bridge_dir / "responses"
    ready_path = bridge_dir / "ready.json"
    live_session_bridge = Path(__file__).resolve().parent / "live_session_bridge.ps1"

    requests_dir.mkdir(parents=True, exist_ok=True)
    responses_dir.mkdir(parents=True, exist_ok=True)

    ready_payload = {
        "ok": True,
        "pid": os.getpid(),
        "user": getpass.getuser(),
        "bridge_dir": str(bridge_dir),
        "started_at_epoch": time.time(),
        "script": str(Path(__file__).resolve()),
    }
    _write_json_atomic(ready_path, ready_payload)

    def _cleanup_ready_file() -> None:
        try:
            if ready_path.exists():
                ready_path.unlink()
        except OSError:
            pass

    atexit.register(_cleanup_ready_file)

    poll_seconds = max(0.05, float(args.poll_seconds))
    try:
        while True:
            for request_path in sorted(requests_dir.glob("*.json")):
                claimed_path = _claim_request(request_path)
                if claimed_path is None:
                    continue

                try:
                    with claimed_path.open("r", encoding="utf-8") as handle:
                        request = json.load(handle)
                    if not isinstance(request, dict):
                        response = {"ok": False, "error": "Request payload must be a JSON object."}
                        request_id = claimed_path.stem
                    else:
                        request_id = str(request.get("request_id") or claimed_path.stem)
                        response = _run_request(live_session_bridge, request)
                except Exception as exc:
                    request_id = claimed_path.stem
                    response = {"ok": False, "error": str(exc)}
                finally:
                    try:
                        claimed_path.unlink()
                    except OSError:
                        pass

                response_path = responses_dir / f"{request_id}.json"
                _write_json_atomic(response_path, response)

            time.sleep(poll_seconds)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
