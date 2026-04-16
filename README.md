# RADAN Automation

Reusable RADAN automation wrapper, probes, and reverse-engineering notes extracted from `radan_kitter`.

## What Lives Here

- `radan_com.py`
  - Stable public wrapper surface for `Radraft.Application`
- `radan_models.py`, `radan_backends.py`, `radan_utils.py`, `radan_mac.py`
  - Internal support modules split out from the original monolithic wrapper
- `radan_com_bridge.ps1`
  - PowerShell bridge backend for COM access
- `inspect_radan_api_xml.py`
  - Search the shipped RADAN XML docs
- `inspect_dotnet_method_il.ps1`
  - Inspect IL for the managed RADAN interop assembly
- `probe_radan_*` and `try_radan_*`
  - Attach, headless, and output probes
- `RADAN_*.md`
  - Findings and quick-reference notes
- `COMMAND_CATALOG.md`
  - First-pass catalog of documented COM methods, MAC entry points, and keystroke syntax
- `API_VS_KEYSTROKE_MATRIX.md`
  - Decision guide for when to prefer direct COM/API calls vs MAC keystroke command strings
- `KEYSTROKE_REFERENCE_EXTRACT.md`
  - First-pass extract of concrete keystroke topics and command tokens from the installed CHM help
- `INTEROP_SURFACE_DUMP.md`
  - Generated dump of exported RADAN interop interfaces, methods, properties, and parameter lists
- `COMMAND_TEST_MATRIX.md`
  - Working matrix of direct API calls and keystroke commands, with recommended path and tested status
- `tests/test_radan_com.py`
  - Unit coverage for the wrapper surface
- `docs/Radan API Programming Help.pdf`
  - Local PDF reference copy

## Local References

- PDF: [docs/Radan API Programming Help.pdf](</c:/Tools/radan_automation/docs/Radan API Programming Help.pdf>)
- Installed CHM help:
  - `C:\Program Files\Mazak\Mazak\help\manuals\radanapi.chm`
  - `C:\Program Files\Mazak\Mazak\help\manuals\radraft.chm`

## Setup

Install the automation-only Python dependencies:

```powershell
python -m pip install -r requirements.txt
```

Run the wrapper tests:

```powershell
python -m unittest tests.test_radan_com
```

## Verified Probes

- `try_radan_headless.py`
- `try_radan_headless_save.py`
- `try_radan_headless_outputs.py`
- `headless_export_document_artifacts.py`
- `probe_radan_attach.py`
- `probe_radan_managed_attach.ps1`
- `probe_live_session.py`

## Live Session API

The reusable live-session entry points are still exposed from `radan_com.py`:

- `describe_live_session()`
  - Read-only attach to the active visible RADAN session and report PID, title, editor mode, and bounds when available.
- `list_visible_radan_sessions()`
  - Enumerate visible RADAN UI windows so multi-session targeting can start from real PIDs and titles.
- `attach_live_application()`
  - Returns a guarded live-session object for follow-up geometry calls like `draw_rectangle_centered()`.

Read-only live probe:

```powershell
python .\probe_live_session.py --require-part-editor
```

Visible RADAN windows:

```powershell
python .\probe_live_session.py --list-visible-sessions
```

Python example:

```python
from radan_com import attach_live_application

live = attach_live_application(expected_process_id=22188, require_part_editor=True)
print(live.session)
```

Live write caution:

- `attach_live_application()` targets the currently registered active RADAN UI session.
- Geometry helpers write directly into the attached editor.
- Prefer a read-only `describe_live_session()` or `probe_live_session.py` pass first when multiple RADAN windows are open.
- The current RADAN `IPartEditor` interop surface exposes `DrawRectangle`, but not `DrawCircle`.

## Headless Workflow

Useful batch work can stay isolated from the live UI session:

```powershell
python .\headless_export_document_artifacts.py C:\path\to\part.drg --save-copy-path C:\path\to\part_copy.drg
```

That workflow:

- opens the document headlessly
- exports a flat PNG thumbnail
- optionally saves a copy
- closes the document and quits the automation instance
- forces a fresh automation instance instead of reusing a live attached UI session
