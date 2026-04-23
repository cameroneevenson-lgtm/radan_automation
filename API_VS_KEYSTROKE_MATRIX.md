# API vs Keystroke Matrix

Decision matrix for RADAN automation work in this repo.

The question this file answers is:

- "Should we call a typed COM/API method directly?"
- "Should we send a keystroke command through `mac2()`, `fmac2()`, or `rfmac()` instead?"
- "Do we still need to investigate?"

Important note:

- keystrokes in this context are still sent through COM, via the `Mac` object
- the distinction is:
  - direct typed API call
  - command string executed through the MAC/keystroke layer

## Rule Of Thumb

- Prefer direct API calls when a stable typed method exists.
- Prefer keystrokes when RADAN only documents the workflow as a command/key sequence.
- Use `rfmac()` only for commands the PDF explicitly says are safe for non-scan execution.
- Use `mac2()` when the workflow depends on refreshed application state or richer command behavior.
- Treat unknown items as research work, not production automation.

## Direct API Exists

These are good candidates for direct typed calls and should generally not be replaced with keystrokes.

### Application And Document Lifecycle

- `Application.Help()`
- `Application.NewDrawing(...)`
- `Application.NewSymbol(...)`
- `Application.OpenDrawing(...)`
- `Application.OpenSheetRemnantDrawingFromRasterImage(...)`
- `Application.OpenSymbol(...)`
- `Application.OpenSymbolFromRasterImage(...)`
- `Application.Quit()`
- `Document.Close(...)`
- `Document.Save()`
- `Document.SaveAs(...)`
- `Document.SaveCopyAs(...)`

### App State And Environment

- `Visible`
- `Interactive`
- `GUIState`
- `GUISubState`
- `ProcessID`
- `SoftwareVersion`
- `Mac`
- `MacFiles`
- `PluginManager`
- `SystemDataFiles`

### Licensing And Output

- `lic_available(...)`
- `lic_confirm(...)`
- `lic_get_holder()`
- `lic_get_servercode()`
- `lic_request(...)`
- `fla_thumbnail(...)`
- `mfl_thumbnail(...)`
- `prj_output_report(...)`
- `stp_output_report(...)`

### Structured Geometry / Analysis / Editing

- `scan(...)`
- `next()`
- `rewind()`
- `end_scan()`
- `scan_level(...)`
- `elf_bounds(...)`
- `elf_closed(...)`
- `elf_set_option(...)`
- `fed_edit_feature(...)`
- `fed_edit_profile_features(...)`
- `fed_batch_begin()`
- `fed_batch_end()`
- `fed_clear_properties()`
- `IPartEditor.DrawRectangle(...)`

### Verifier / Machine / Order Helpers

- `run_verifier()`
- `run_verifier_silently()`
- `ord_run_blockmaker_silently()`
- `get_num_machines()`
- `machine_type(...)`
- `pcc_get_current_mc_id()`
- `pfl_get_default_mdb_strategy(...)`

### Repo Guidance

When one of the typed methods above exists, that is the preferred route for:

- headless batch work
- repeatable export pipelines
- deterministic save/close flows
- anything we want to run unattended

## Keystroke Path Is Better Or Required

These are areas where the current documentation points more strongly to keystroke workflows than to dedicated typed methods.

### Drawing And Construction Commands

Documented in the CHM as keystroke topics:

- drawing lines
  - `d`, `s`, `"` for rectangle, `*` for normal, `7` for tangent, `6` for chamfer
- drawing arcs
  - `c`, `s`, `d`, `o`, `~`, `&`
- adding centre-line crosses
  - back-quote command
- adding text
  - `T`
- adding hatching
  - pattern-mode driven workflow
- adding copies / jump workflows
  - `j`

These are currently better treated as keystroke-driven UI workflows unless we later discover a dedicated typed method.

### Feature Finding And Selection

The CHM documents these as keystroke behaviors:

- `f`
  - find any feature
- `l` / `L`
  - restricted / unrestricted line find
- `a` / `A`
  - restricted / unrestricted arc find
- `t`
  - text find
- `2`
  - dimension find
- `H`
  - hatching find
- `9`
  - symbol find
- `.`
  - centre-line cross find
- `w`
  - window selection workflows
- `Ctrl+f`
  - selection filter control

Even though we also have typed scan APIs, these keystrokes matter for user-style workflows, cursor-relative operations, and some macro behaviors.

### Pattern Operations

The CHM and API examples both point heavily to keystroke/pattern-mode flows:

- `Ctrl+p`
  - enter pattern mode
- `o`
  - open pattern
- `x`
  - delete pattern
- `s` / `S`
  - save/remove or save/retain variants
- `m`
  - move pattern
- `~`
  - mirror pattern
- `j`
  - jump pattern
- pattern visibility and creation examples via `mac2(...)`

There are ELF and pattern-related APIs, but many interactive pattern-management tasks are still best understood as keystroke workflows.

### Edit-Mode Operations

The CHM documents many edit actions as mode-sensitive command flows:

- partial delete
  - `e`, then `x`
- split line/arc
  - mark point, then `J`
- extend line/arc
  - `e`, then `d`
- merge
  - `%` or `^`
- feature property editing in edit mode
  - pen, line type, orientation, etc.

Live pen remap now has a proven mixed workflow in this repo:

- use `scan(...)` to iterate features and capture `FI0`, `FP0`, `S0X`, and `S0Y`
- use `find_xy_identifier(...)` to re-mark the exact feature you want to edit
- then use `rfmac('e\\?P,<pen>?')` to apply the logical pen change

Important constraint:

- a direct `rfmac('e\\?P,<pen>?')` call from scan state alone failed live with `First find a feature`
- the extra `find_xy_identifier(...)` step was required before the edit-mode keystroke would stick

When the operation is described as "enter edit mode, then press key X", it is usually a keystroke-first workflow.

### View / Prompt / Cursor Workflows

The CHM documents these as keystrokes rather than typed API calls:

- redraw and zoom redraw
  - `r`, `z`, `Ctrl+r`, `Ctrl+z`
- panning
  - `W`
- supplementary windows
- location commands
- prompt help
  - `?`
- query command
  - `q`

These are primarily interactive workflows and are usually poor fits for unattended headless automation.

## Use `rfmac()` Only In Narrow Cases

The PDF explicitly says `rfmac()` must not be used for commands that perform their own scan.

Documented safe-or-safer `rfmac()` commands from the PDF:

- `s`
- `c`
- `~`
- `d`
- `e`
- `x`
  - not for hatching or window delete
- `m`
  - not for symbols or window move
- `P`
- `a`
- `l`
- `.`
- `f`
- `t`
- `1`
- `<`
- `>`
- `,`
- `"`

Practical repo guidance:

- use `rfmac()` only for small, local, non-scan command sequences
- use `mac2()` when state refresh matters or when the workflow is more complex

## Unknown Or Needs Testing

These are the places where we should not assume the answer yet.

### Full Keystroke Universe

We now have topic-level CHM access, but we still do not have a normalized, exhaustive command table.

Unknowns still include:

- complete drafting command inventory
- complete tooling command inventory
- complete order-mode keystroke inventory
- mode restrictions for each command

### Typed API Parity Questions

There may still be dedicated typed methods for some workflows that currently look keystroke-only.

Needs more checking:

- pattern management beyond ELF helpers
- richer geometry creation beyond `DrawRectangle`
- cursor-object manipulation APIs
- dimension-creation APIs
- text creation/edit APIs

### Order Mode

We have typed order-related helpers such as:

- `ord_run_blockmaker_silently()`

But the detailed order-mode command vocabulary still needs extraction from the CHM and then mapping into:

- direct API exists
- keystroke only
- mixed mode

### Safety Classification

Some commands are probably callable, but we should still classify them before using them in production:

- safe in headless automation
- safe only in attached live sessions
- unsafe / focus-sensitive / prompt-blocking

## Current Repo Strategy

For this repo today, the safest practical strategy is:

- use direct API calls for batch/headless automation
- use keystrokes only for editor-style workflows that RADAN documents primarily as command sequences
- use mixed API + keystroke flows when RADAN needs typed selection but only exposes the edit itself through an edit-mode keystroke
- prefer attached live-session automation for keystroke-heavy editing work
- prefer isolated fresh instances for typed export and conversion pipelines

## Suggested Next Additions

The next useful companion docs would be:

- `KEYSTROKE_REFERENCE_EXTRACT.md`
  - topic-by-topic extraction from the CHM
- `COMMAND_TEST_MATRIX.md`
  - command, mode, API/keystroke path, tested status, and risk level
