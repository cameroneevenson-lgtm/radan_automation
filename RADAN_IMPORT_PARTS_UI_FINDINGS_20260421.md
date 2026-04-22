# RADAN Import Parts UI Findings - 2026-04-21

This note captures what was proven while inspecting and driving the `Import Parts` flow inside a live RADAN Nest session on this machine.

Repo: `c:\Tools\radan_automation`

## Bottom Line

The `Import Parts` flow is automatable, but it is not a single dialog.

What actually happens in the live UI here:

- the custom Nest-side launcher button opens the import workflow
- the import workflow immediately surfaces a standard Windows file-open dialog on top
- the larger WinForms `Import Parts` container sits behind that file picker and is disabled while the picker is active

That means automation should treat this as a two-layer flow rather than a single window.

## Proven Launcher Control

The live launcher inside the Nest window was exposed through Windows UI Automation as:

- `rpr_parts_list_import_parts_button`
- paired bitmap: `project_import_parts.bmp`

Observed characteristics:

- class: `myexclusive` / `myexbutton`
- no useful UIA `InvokePattern`
- click success depended on the control being on the visible desktop

Important practical note:

- when the RADAN window was moved partly off-screen, the control still existed in UIA, but the live click path did not work reliably
- after moving the main RADAN window back to `0,0`, the same control became clickable again and the import flow opened successfully

So the reliable path is:

- first ensure the main RADAN window is actually on-screen
- then locate the launcher by UIA name
- then click the live screen rectangle center

## Proven Parent Import Dialog

The larger parent dialog behind the file picker is a WinForms window:

- title: `Import Parts`
- class: `WindowsForms10.Window.8.app.0.9585cb_r6_ad1`

This dialog is much more automation-friendly than the top-row Nest mode strip.

Important controls observed on the parent dialog:

- `DataGridView`
- `Add...`
- `Delete`
- `Apply`
- `View Results File...`
- `Settings...`
- `Save As Default`
- `Import All`
- `Options...`
- `Browse...`
- `Change Material...`
- `DXF/DWG template:`

Behavior observed in the empty state:

- `Add...` was enabled
- many controls were disabled until parts were added or selected
- the grid exposed table patterns
- the template selector exposed combo-box style patterns

## Proven Child File Picker

After the launcher click, the active top dialog was a standard Windows common dialog:

- title: `Import Parts`
- class: `#32770`

Observed child controls included:

- `Look in:`
- folder view / `FolderView`
- `File name:`
- `Files of type: DXF Files (*.dxf)`
- `Open`
- `Cancel`
- `Options...`
- `Template:`

This is good news for automation because this layer is much more standard than the RADAN custom controls.

## Proven Flow Behavior

The flow observed in local testing was:

1. start in live Nest `modify` mode
2. click `rpr_parts_list_import_parts_button`
3. RADAN opens the import workflow
4. the standard `#32770` file picker appears immediately on top
5. the WinForms `Import Parts` parent dialog remains behind it and is disabled

Additional operator note confirmed during testing:

- every UI launch of `Import Parts` opens the `Add...` file picker automatically

That matches the live inspection results exactly.

## Import Variants

There are two practical import workflows for operators here:

- select DXF files directly in the standard file-open dialog
- import through a CSV file

Current workflow priority from the operator side:

- CSV is the common / preferred path for internal work
- direct DXF selection is still important as a fallback for smaller or odd jobs that may not have a CSV

Current evidence level:

- direct DXF selection is automation-aligned with the active `#32770` file picker we already observed live
- the CSV path is operator-confirmed and uses the same standard `#32770` file picker
- the branch point is the `Files of type` control in that picker

Important distinction:

- the active file picker currently presented itself with `Files of type: DXF Files (*.dxf)`
- that does **not** mean CSV import is unavailable
- instead, it means the picker opened on the DXF filter during this session and the CSV path should be reached by changing `Files of type`

So for automation planning, `Import Parts` should now be treated as having at least two branches:

- DXF-selection branch
- CSV-import branch

Recommended automation priority at this stage:

- map and stabilize the CSV branch first
- keep the direct DXF branch as a secondary fallback path

Current best model of the branch logic:

- launch `Import Parts`
- RADAN opens the same standard Windows file picker every time
- choose the import variant through `Files of type`
  - DXF filter for direct file selection
  - CSV filter for the preferred internal import flow

## Interaction Guidance

Current best approach for this flow:

- use UIA to find the custom Nest launcher button
- use a real foregrounded click for the launcher
- once launched, treat the standard `#32770` file picker as the active window
- only interact with the WinForms parent dialog after closing or completing the file picker

For the parent dialog itself:

- button clicks are still likely the simplest path
- row/grid interaction should go through the `DataGridView`
- combo-box style settings can likely be driven through the standard WinForms controls once enabled

## Output Folder Behavior

The imported grid includes a per-row `Output folder` column.

What was proven live:

- the `Output folder` header is present in the `DataGridView`
- row cells such as `Output folder Row 0, Not sorted.` exposed `ValuePattern`
- the first sampled rows currently reported:
  - `Row 0 -> L:\BATTLESHIELD`
  - `Row 1 -> L:\BATTLESHIELD`
  - `Row 2 -> L:\BATTLESHIELD`
- the separate `Browse...` button becomes enabled after the CSV import completes

Operator workflow note:

- the output path is fundamentally per row
- users can select all rows, which provides the practical bulk-edit path
- after adding parts from CSV or DXFs, all rows are selected by default

Async import behavior note:

- after the CSV picker closes, the parent `Import Parts` dialog can remain in a partial-load state for a significant amount of time while RADAN imports and expands the source rows
- on larger CSV jobs, this load can take roughly a second or more per part on this machine
- visible rows in the `DataGridView` do **not** mean the import is ready; the grid may already be partially populated while RADAN is still processing additional rows
- during that load window, `Import All` may already be enabled while `Browse...` is still disabled
- that disabled `Browse...` state should be interpreted as "rows are still loading / not ready yet", not as "no rows are selected"
- one earlier live attempt used `Ctrl+A` around the same time `Browse...` became enabled, but that should no longer be treated as evidence that manual reselection was required

Current best interpretation:

- `Output folder` is not just a single global import setting
- it is a row-level field that RADAN applies through the selected rows plus `Browse...`
- in the normal import flow here, the imported rows are already selected by default, so the important gating factor for `Browse...` is the async CSV load finishing rather than any extra manual selection step
- `Browse...` is therefore the immediate bulk-output-folder action once that async load has actually settled
- in practice, the important automation problem is likely folder resolution from the current nest-pack context, not manual browsing itself

Operator constraint confirmed during testing:

- in the normal RADAN UI workflow, output paths are only edited through the `Browse...` dialog
- even if the cells expose editable-looking automation patterns, they should not be treated as the intended operator path
- the `Browse For Folder` dialog is cumbersome manually because it is the older tree-only shell picker rather than a modern path-entry dialog

Automation implication:

- if the current nest pack determines the intended output folder, automation should derive that target path first
- then use the supported `Browse...` / `Browse For Folder` flow to apply it, instead of relying on manual-style folder hunting

## Proven End-To-End CSV Import

The full CSV import workflow is now proven live on this machine for:

- CSV source:
  - `L:\BATTLESHIELD\F-LARGE FLEET\F56139\PAINT PACK\F56139 PAINT PACK\F56139-PAINT PACK-BOM_Radan.csv`
- output folder:
  - `L:\BATTLESHIELD\F-LARGE FLEET\F56139\PAINT PACK\F56139 PAINT PACK`

The successful live flow was:

1. launch `Import Parts` from the Nest parts-list button
2. enter the CSV path in the standard `#32770` file picker and click `Open`
3. wait for the async CSV row import to finish until `Browse...` becomes enabled
4. click `Browse...`
5. use the old shell `Browse For Folder` tree to select the target output folder
6. confirm the folder with `OK`
7. click `Import All`
8. wait for the completion modal and confirm it with `OK`

Observed final result:

- completion modal text:
  - `Number of parts added to the parts list: 108`
- the target output folder populated incrementally with `.sym` files during the import
- the final observed changed `.sym` count for that run reached `108`

Shell-tree targeting note:

- cropped folder labels in the old `Browse For Folder` tree can make text-bound click coordinates misleading
- a label-driven click can land outside the truly actionable row area even when the item name is correct
- the safer path was:
  - force focus into the tree control itself
  - use MSAA selection plus keyboard expansion
  - reserve ordinary clicks for the dialog buttons rather than the truncated folder labels

## Measured Timings

Two separate timing windows were measured live for the same `108`-row CSV.

CSV ingest timing:

- start:
  - `Open` click in the standard file picker
- stop:
  - `Browse...` becomes enabled in the WinForms parent dialog
- measured result:
  - `70.618s` total
  - about `0.6539s/part`

Important timing interpretation:

- this is not the `Import All` time
- it is the CSV-to-parent-dialog expansion time until the import rows are actually ready for output-folder assignment

Import action timing:

- start:
  - real live click on `Import All`
- stop:
  - the completion modal appears with the parts-added message
- measured result:
  - `56.886s` total
  - about `0.5267s/part`

Observed import progress signal:

- the output folder began receiving updated or created `.sym` files almost immediately
- the first observed changed output was `B-1.sym` at about `1.2s`
- later observed progress samples continued up through:
  - `changed_sym_count = 108`
  - latest observed file near completion: `F56139-B-99.sym`

## Completion Modal Signature

The import-complete dialog is easy to confuse with the parent dialog because both use the title `Import Parts`.

Reliable distinction:

- completion modal:
  - title: `Import Parts`
  - class: `#32770`
  - contains:
    - enabled `OK` button
    - static text `Number of parts added to the parts list: 108`
- parent dialog:
  - title: `Import Parts`
  - class: `WindowsForms10.Window.8.app.0.9585cb_r6_ad1`

Automation rule:

- do **not** key off the title text alone
- treat the `#32770` class plus the completion text and enabled `OK` button as the real end-of-import signal

## Click Semantics Matter For Long RADAN Actions

One important automation bug was proven during the timed `Import All` work.

What failed:

- triggering `Import All` with synchronous `SendMessage(BM_CLICK, ...)`

Observed effect:

- the automation call blocked inside RADAN's button handler while the import was running
- that prevented the timing script from polling for:
  - the completion modal
  - incremental `.sym` output in the target folder
- this made it look like the completion modal had been missed, even though the import itself had finished correctly

What worked:

- a real foregrounded desktop click on the `Import All` button

Practical rule:

- for long-running RADAN actions where the script needs to keep observing UI or filesystem progress, prefer a real live click over synchronous `SendMessage(BM_CLICK, ...)`

## Unsafe Shortcut Found

One attempted shortcut should now be treated as unsafe for this RADAN workflow:

- sending shell-level folder-browser selection messages directly into the open `Browse For Folder` dialog
  - specifically the standard `BFFM_SETSELECTIONW` / related message-based selection route

Observed result on this machine:

- RADAN terminated during the folder-browser workflow
- Windows event logs recorded `RADRAFT.exe` crashes while inside WinForms folder-browser handling

Relevant crash signal captured locally:

- faulting application: `RADRAFT.exe`
- version: `2025.1.2523.1252`
- faulting module: `shcore.dll`
- .NET stack included:
  - `System.Windows.Forms.FolderBrowserDialog.RunDialog(...)`
  - `Radan.ImportUtility.ObjectSettingsControl.btnBrowseOutFolder_Click(...)`

Practical rule:

- do **not** use shell-message injection as the folder-selection strategy for this dialog
- prefer plain supported UI interaction through the folder tree and normal `OK` confirmation

## Unsafe Tree Introspection Found

Later live testing exposed a second unsafe class of interaction against the same old `Browse For Folder` dialog.

Attempted path:

- low-level cross-process tree introspection against the live `SysTreeView32`
- specifically a remote-memory / `TVM_GETITEMW` style probe intended to read item text without changing the visible UI workflow

Observed result on this machine:

- the entire live RADAN application went down during the folder-selection stage
- the import state was lost
- after restart, RADAN came back only as a fresh Nest Editor session

Important distinction:

- this was **not** the earlier shell-selection-message route
- this was a separate failure mode triggered by direct low-level probing of the shell tree internals

Practical rule:

- do **not** use cross-process tree introspection or remote-memory tree probing against RADAN's live `Browse For Folder` dialog
- for this workflow, treat the shell tree as click/keyboard only
- if automation needs stronger folder targeting, prefer a safer higher-level approach or operator assistance rather than direct tree internals

That part is now confirmed live:

- `Browse...` opens the older shell `Browse For Folder` dialog
- confirming the target folder with `OK` applies it back into the selected import rows

## Sandbox / Desktop Note

This import flow splits into two different automation levels:

- custom launcher click
  - requires real interactive desktop access because the Nest launcher is a custom control without a simple UIA invoke surface
- file picker / WinForms dialog interaction
  - much more standard and should be easier to drive once the workflow is already open

Practical implication:

- a shell that can inspect processes and UIA trees may still fail to launch `Import Parts` if the desktop click cannot land on the live custom control
- once the standard Windows file picker is open, automation options become much better

## Current Launcher Blocker In A Populated Project

Later live testing exposed an important limitation in the already-populated project state.

Observed state:

- live RADAN session: `New Drawing (F55334 PUMP COVERINGS) - Mazak Smart System Nest Editor - [1: Optiplex Champ 3015 3.0kw Fiber TT]`
- parts list summary visible:
  - `Number of parts: 28   Total required: 34   Total extra: 0`
- launcher strip controls still visible and enabled:
  - `rpr_parts_list_add_part_button`
  - `rpr_parts_list_import_parts_button`

What was attempted live in that state:

- real foregrounded desktop click on `rpr_parts_list_import_parts_button`
- real foregrounded desktop click on `rpr_parts_list_add_part_button`
- focus-the-list-then-click retry
- `WM_COMMAND`-style notifications aimed at both the immediate control-area parent and the main RADAN frame
- MSAA `accDoDefaultAction()` against both:
  - `rpr_parts_list_import_parts_button`
  - `project_import_parts.bmp`
- keyboard/context-menu style attempts through the parts list

Observed result:

- none of those paths surfaced the `Import Parts` workflow
- no standard `Import Parts` file picker appeared
- no visible top-level RADAN dialog appeared
- the live session otherwise remained healthy and attachable after the menu state was cleared

So the current conclusion is:

- the parts-list import launcher is not yet reliably automatable from this specific populated-project state on this machine
- this is a stronger claim than the earlier off-screen caveat
- the original empty-state / manually-opened-success path is still real, but it does not automatically generalize to every later live project state

## Macro Route Caveat

One attempted deep route used the installed GUI macro naming convention to try loading `text.rtlcall` through the interop `LoadMacro(...)` surface so `RunMacCommand('prg_notify', ...)` could be tried directly.

Observed result:

- `LoadMacro('rtlcall')` failed with `HRESULT E_FAIL`
- attempting the standalone load path raised a live RADAN modal:
  - title: `Mac Error`
  - message:
    - `MAC: Undefined variable in expression: 'RPV_ON_EXIT_NEW' in definition of rtl_vfy_new_drawing at line 201`

Practical rule from this test:

- do **not** treat `LoadMacro('rtlcall')` as a safe generic way to drive the project UI
- the shipped RTL macro files appear to depend on a broader GUI/macro context than a standalone interop load provides
