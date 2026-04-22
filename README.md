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
- `draw_live_rectangle.py`, `draw_attached_rectangle.ps1`
  - Live Part Editor rectangle writers for an attachable session
- `serve_live_session_bridge.py`, `start_live_session_host_bridge.ps1`
  - Optional host-side request/response bridge for live-session attach and draw calls
- `watch_live_session.py`
  - Transition-only watcher for live RADAN session state, prompts, and MAC fields
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
- `refresh_document_headless.py`
- `draw_live_rectangle.py`
- `watch_live_session.py`

## Live Session API

The reusable live-session entry points are still exposed from `radan_com.py`:

- `describe_live_session()`
  - Read-only live-session probe. When a real attachable automation session is available it reports PID, title, editor mode, pattern, and bounds. When attach is unavailable it falls back to visible-window detection and reports only what can be inferred from the window/process.
- `list_visible_radan_sessions()`
  - Enumerate visible RADAN UI windows so multi-session targeting can start from real PIDs and titles.
- `attach_live_application()`
  - Returns a guarded write-capable live-session object for follow-up geometry calls like `draw_rectangle_centered()`.
  - This requires a real attachable automation session. A merely visible RADAN window is not enough.

## Session Model

There are three different runtime states that the repo has to keep separate:

- visible RADAN UI window
  - A normal hand-opened `RADRAFT.exe` window that we can identify by PID and title.
  - This is enough for `list_visible_radan_sessions()` and the visible-window fallback in `describe_live_session()`.
- attachable live automation session
  - A visible RADAN session that the managed/COM attach paths can actually bind to.
  - This is required for `attach_live_application()`, `ElfBounds(...)`, and `PartEditor.DrawRectangle(...)`.
- hidden automation-owned worker
  - A separate `Radraft.Application` automation instance used for headless open/save/export work.
  - This is the safest path for unattended batch workflows.

Two bridge models also exist in the repo:

- `radan_com_bridge.ps1`
  - Long-lived stdin/stdout bridge for classic COM access to `Radraft.Application`.
- `live_session_bridge.ps1`
  - One-shot managed interop probe/write helper for attachable live sessions.
- `serve_live_session_bridge.py`
  - Optional request/response host bridge for cases where a local attach probe fails but a host-side live session is already available.

Read-only live probe:

```powershell
python .\probe_live_session.py --require-part-editor
```

Visible RADAN windows:

```powershell
python .\probe_live_session.py --list-visible-sessions
```

Transition-only live watcher:

```powershell
python .\watch_live_session.py --seconds 30 --interval 0.2
```

Optional host bridge:

```powershell
powershell .\start_live_session_host_bridge.ps1 -Background
```

Python example:

```python
from radan_com import attach_live_application

live = attach_live_application(expected_process_id=22188, require_part_editor=True)
print(live.session)
```

Live write caution:

- `attach_live_application()` only succeeds when RADAN exposes a real attachable live automation session.
- Geometry helpers write directly into the attached editor.
- If `describe_live_session()` reports a `visible-window` backend, that is read-only detection, not proof that live geometry calls will work.
- Prefer a read-only `describe_live_session()` or `probe_live_session.py` pass first when multiple RADAN windows are open.
- The current RADAN `IPartEditor` interop surface exposes `DrawRectangle`, but not `DrawCircle`.

## Live Nest Findings

The strongest current live-session findings for Nest mode are:

- when an attachable visible Nest session is available, `live_session_bridge.ps1` now reports the active layout pattern through `PCC_PATTERN_LAYOUT` and can resolve layout bounds with `ElfBounds(...)`
- the attached Nest mode signal on this machine is primarily `GUISubState`, not prompt text
  - `14` = modify
  - `7` = profiling
  - `11` = order
- `GUIState` stayed at `4` across those live Nest mode transitions
- `Mac.PRS` was **not** a reliable discriminator for Nest modes in local testing; it often stayed the same across `modify`, `profiling`, and `order`
- the live UI exposes top-row custom mode buttons that can be targeted directly once the RADAN window is foregrounded:
  - `rtl_nest_modify_button`
  - `rtl_nest_profile_button`
  - `rtl_nest_order_button`
- the `Profiling` and `Modify` buttons have been proven live by automation on this machine
  - `order -> profiling`
  - `profiling -> modify`
- the `Order` button has also now been proven live by automation on this machine
  - `modify -> order`
- the parts-list import launcher has been identified and exercised live:
  - `rpr_parts_list_import_parts_button`
  - paired bitmap `project_import_parts.bmp`
  - launching it immediately surfaces a standard Windows `Import Parts` file picker on top of the WinForms parent dialog
- the full CSV import path has now also been proven live end-to-end:
  - CSV `Open` -> `Browse...` enabled:
    - `70.618s` for `108` rows
    - about `0.6539s/part`
  - `Import All` -> completion modal:
    - `56.886s` for `108` parts
    - about `0.5267s/part`
  - completion was confirmed by a separate `Import Parts` modal with class `#32770` and text:
    - `Number of parts added to the parts list: 108`
  - output `.sym` files were observed appearing incrementally in the selected output folder during the import
- a direct MAC escape command (`mac2('\!')`) was accepted in `order` mode, but it did **not** exit `order` mode here

Sandbox / desktop-access note:

- read-only probing (`describe_live_session()`, `probe_live_session.py`, `watch_live_session.py`) can work from a normal automation shell as long as RADAN is attachable
- live mode switching through the top-row Nest buttons is a lower-level UI action
  - it required access to the real interactive Windows desktop session so the automation could foreground the RADAN window and click custom controls
  - a more restrictive sandbox that blocks focus changes, mouse movement, or desktop interaction should be expected to fail for this path even if COM attach still works
- the same desktop caveat applies to the custom `Import Parts` launcher button in the live Nest window
  - once the standard Windows file picker is open, the interaction surface becomes much more conventional than the custom launcher itself
- the same caveat also applies to long-running live buttons such as `Import All`
  - a real desktop click allowed the script to keep observing progress and the completion modal
  - synchronous `SendMessage(BM_CLICK, ...)` blocked inside RADAN for this path and is therefore a poor fit when we need concurrent observation

For the detailed evidence trail, see [RADAN_LIVE_NEST_FINDINGS_20260421.md](/c:/Tools/radan_automation/RADAN_LIVE_NEST_FINDINGS_20260421.md) and [RADAN_IMPORT_PARTS_UI_FINDINGS_20260421.md](/c:/Tools/radan_automation/RADAN_IMPORT_PARTS_UI_FINDINGS_20260421.md).

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

For a simpler "open, save, optionally thumbnail, and quit" path, use:

```powershell
python .\refresh_document_headless.py C:\path\to\part.drg --thumbnail-path C:\path\to\part.png
```
