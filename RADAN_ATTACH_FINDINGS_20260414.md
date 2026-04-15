# RADAN Attach Findings - 2026-04-14

This note captures what we confirmed on `PC-6886` while trying to attach automation to an already-open RADAN UI session.

## Bottom Line

No supported attach path to the hand-opened RADAN UI session has been confirmed yet.

What *is* confirmed:

- `Radraft.Application` is a valid COM server.
- Its registered server is `"C:\Program Files\Mazak\Mazak\bin\Radraft.exe" /Automation`.
- Hand-opened RADAN windows do **not** register themselves as the active `Radraft.Application` object.
- The managed interop layer also does **not** treat the hand-opened UI windows as an attachable "existing instance".
- The managed interop layer uses the same ROT-based attach idea under the hood, with one extra filter: it rejects an existing COM app unless `Visible=True`.

## What We Tested

### 1. Classic COM attach

- `GetActiveObject("Radraft.Application")`
- `GetActiveObject("Radraft.Application.1")`

Result:

- No active COM object was available when only the visible UI windows were open.
- Creating `Radraft.Application` launched a separate hidden automation process instead.

### 2. Managed interop attach hint

Assembly:

- `C:\Program Files\Mazak\Mazak\bin\Radan.Shared.Radraft.Interop.dll`

Interesting types:

- `Radan.Shared.Radraft.Interop.IRadraftApplicationFactory`
- `Radan.Shared.Radraft.Interop.RadraftApplicationFactory`
- `Radan.Shared.Radraft.Interop.IRadraftApplication`
- `Radan.Shared.Radraft.Interop.RadraftApplication`

Important signatures:

- `RadraftApplicationFactory.Create(useExistingInstance:Boolean) -> IRadraftApplication`
- `RadraftApplication(useExistingInstance:Boolean)`

Observed result with visible UI windows already open:

- `useExistingInstance=True` returns an object with:
  - `IsConnected=False`
  - empty `ProcessId`
  - `Visible=False`
- It does **not** attach to the visible UI PIDs.

### 2a. Managed interop IL inspection

Script:

- [inspect_dotnet_method_il.ps1](/c:/Tools/radan_automation/inspect_dotnet_method_il.ps1)

Important IL findings from `Radan.Shared.Radraft.Interop.RadraftApplication`:

- `TryConnectingToExisting()` does:
  - `GetActiveObject("Radraft.Application")`
  - cast to `Radraft.Interop.IApplication`
  - reject it if `Visible=False`
  - if accepted, call `ProcessID`, get the process main window handle, and call `RestoreWindow(...)`
- `TryNewConnection()` does:
  - `Type.GetTypeFromCLSID(Guid("0E753ADB-1A75-4B45-A453-DBED5F652005"))`
  - `Activator.CreateInstance(...)`
  - cast to `Radraft.Interop.Application`
- The constructor `RadraftApplication(..., useExistingInstance:Boolean)` is **attach-only** when `useExistingInstance=True`.
  - It calls `TryConnectingToExisting()`.
  - If that fails, it leaves `mComApplication = null`.
  - It does **not** fall back to `TryNewConnection()`.

Interpretation:

- The managed wrapper is not using some secret attach channel.
- It is still looking for the same ROT-registered `Radraft.Application` object.
- It additionally ignores hidden automation instances, even if they are registered, unless they are visible.

### 3. Window-object attach probe

Script:

- [probe_radan_window_automation.py](/c:/Tools/radan_automation/probe_radan_window_automation.py)

Observed window classes:

- `myframe`
- `mysecond`

Observed result:

- `AccessibleObjectFromWindow(...)` returns standard `IAccessible` objects.
- `OBJID_NATIVEOM` fails for the tested top-level RADAN windows.

Interpretation:

- RADAN exposes accessibility information for the UI.
- It does **not** appear to expose a native object model off the window handle in the same way Office apps often do.

## Practical Meaning

Right now there are two distinct worlds:

1. Normal UI launches:
   - `RADRAFT.exe`
   - visible Nest Editor windows
   - not attachable through the tested COM/managed attach paths

2. Automation launches:
   - `Radraft.exe /Automation`
   - hidden or automation-owned process
   - attachable through `Radraft.Application` once that automation server exists

## Reusable Probes

- [probe_radan_attach.py](/c:/Tools/radan_automation/probe_radan_attach.py)
  - Tests classic COM attach without spawning a new automation server.

- [probe_radan_managed_attach.ps1](/c:/Tools/radan_automation/probe_radan_managed_attach.ps1)
  - Tests the managed `useExistingInstance=True` paths.

- [inspect_dotnet_method_il.ps1](/c:/Tools/radan_automation/inspect_dotnet_method_il.ps1)
  - Dumps IL instructions for managed RADAN interop methods so we can verify attach/spawn behavior directly.

- [probe_radan_window_automation.py](/c:/Tools/radan_automation/probe_radan_window_automation.py)
  - Probes the live RADAN window handles for `IAccessible` / `OBJID_NATIVEOM` exposure.

## Current Best Conclusion

We are closer in certainty than before:

- The visible RADAN UI session is almost certainly **not** the same thing as the COM automation server.
- No evidence has been found yet for a hidden "attach-to-current-UI" API.
- The managed interop layer now appears fully explained:
  - attach means `GetActiveObject("Radraft.Application")`
  - the target must be `Visible=True`
  - otherwise the wrapper stays disconnected
- If an attach path exists, it is probably outside the common COM patterns already tested, or hidden behind an internal subsystem we have not found yet.
