# RADAN Command Catalog

First-pass catalog of the RADAN callable surface gathered from:

- [docs/Radan API Programming Help.pdf](</c:/Tools/radan_automation/docs/Radan API Programming Help.pdf>)
- the installed `Radan.Shared.Radraft.Interop.dll`
- the current wrapper in [radan_com.py](</c:/Tools/radan_automation/radan_com.py>)

This is not yet a complete "every keystroke in RADAN" dump. It is a practical map of:

- the top-level COM calls we can make now
- the documented MAC command entry points
- the keystroke syntax rules documented in the PDF
- the command families worth testing next

## Scope

There are three different command layers in RADAN:

- `Application` / `Document` COM methods
  - Open, create, save, close, quit, and object access.
- `Mac` methods
  - Licensing, UI text, scans, feature editing, ELF geometry analysis, verifier helpers, and keystroke execution.
- Keystroke command strings
  - Strings passed to `mac2()`, `fmac2()`, or `rfmac()`.

The PDF documents the first two well and documents the syntax for the third, but it does not include a single compact "all keystrokes" table in the extracted pages I reviewed. It points to `Keystroke Reference` and `Order mode keystroke reference` for the fuller command lists.

## Application COM Surface

Documented in the PDF on pages `3-5`.

### Methods

- `Help() -> Boolean`
- `NewDrawing(DiscardChanges As Boolean)`
- `NewSymbol(DiscardChanges As Boolean)`
- `OpenDrawing(FilePath, DiscardChanges, OptionsFilePath)`
  - Drawing path may also be `DXF`, `DWG`, or `IGES`.
- `OpenSheetRemnantDrawingFromRasterImage(FilePath, DiscardChanges, OptionsFilePath, SheetX)`
- `OpenSymbol(FilePath, DiscardChanges, OptionsFilePath)`
  - Symbol path may also be `DXF` or `DWG`.
- `OpenSymbolFromRasterImage(FilePath, DiscardChanges, OptionsFilePath)`
- `Quit() -> Boolean`

### Properties

- `ActiveDocument`
- `DatPath`
- `FullName`
- `GUIState`
- `GUISubState`
- `Interactive`
- `Language`
- `Mac`
- `MacFiles`
- `Name`
- `Path`
- `PluginManager`
- `ProcessID`
- `SoftwareVersion`
- `SystemDataFiles`
- `Visible`

### Notes

- The PDF states that an externally created `Radraft.Application` instance starts hidden by default but stays interactive unless you change it.
- COM availability is not guaranteed in every GUI state. The PDF says calls may be rejected in modal dialogs, verifier mode, polygon window mode, long calculations, clamp/picker/chute moves, or while waiting for user input from a keystroke command or MAC macro. See page `2`.

## Document Surface

Documented in the PDF on pages `6-7`.

### Methods

- `Close(DiscardChanges As Boolean)`
- `Save()`
- `SaveAs(FilePath)`
- `SaveCopyAs(FilePath, OptionsFilePath)`

### Properties

- `Dirty`
- `Type`
- `Application`

### Practical Notes

- `SaveCopyAs()` is the safer batch export primitive because it preserves the currently open document identity.
- In our current repo, these calls are wrapped by:
  - `active_document_info()`
  - `close_active_document()`
  - `save_active_document()`
  - `save_active_document_as()`
  - `save_copy_of_active_document_as()`

## Mac Entry Points

The PDF introduces the `Mac` object on page `7` and then breaks it into topic sections.

### Licensing

Documented on pages `9-10`.

- `lic_available(name)`
- `lic_confirm(name)`
- `lic_get_holder()`
- `lic_get_servercode()`
- `lic_request(name)`

These are already wrapped in [radan_com.py](</c:/Tools/radan_automation/radan_com.py>) as:

- `license_info()`
- `license_available()`
- `license_confirm()`
- `license_request()`

### UI Helpers

Documented on page `10`.

- `uim_error(message)`
- `uim_info(message)`
- `uim_prompt(message)`

The same section also describes file browser helpers, but those are more UI-bound and less useful for isolated batch automation.

### Keystroke Execution

Documented on pages `13-19`.

- `fmac2(command)`
  - Ends any current feature scan, then runs the command string.
  - Does not update current state values afterward.
- `mac2(command)`
  - Ends any current feature scan, runs the command string, then updates current state values.
- `rfmac(command)`
  - Runs the command string without ending the current scan and without refreshing state values.

### Drafting / Tooling Mode Helpers

Documented on page `14`.

- `silent_exit_nc_mode()`
- `silent_nc_mode()`
- `d_fix()`
- `d_dump()`

### Scan and Feature Iteration

Documented on pages `28-29`.

- `scan(path, filter, number)`
- `next()`
- `end_scan()`
- `rewind()`
- `scan_level(level)`

The PDF's documented scan filter tokens include:

- feature classes: `a l c h H s d t p S C R g`
- modifiers: `x i D N O`

### Feature Editing

Documented on pages `41-42`.

- `fed_edit_feature(featureId)`
- `fed_edit_profile_features(featureId)`
- `fed_batch_begin()`
- `fed_batch_end()`
- `fed_clear_properties()`

The PDF also documents many `FED_*` properties used as edit parameters, such as bend angle, bend radius, allowance type, and undercut flags.

### ELF Geometry Analysis

Documented beginning on page `42` and continuing through the late `40s`.

Examples mentioned in the PDF:

- `elf_bounds(...)`
- `elf_closed(...)`
- `elf_set_option(...)`
- `elf_shape_in_shape(...)`
- `elf_short_path_in_shape(...)`

The PDF is explicit that in the Part Editor the normal source pattern is `PART_PATTERN`.

### Verification and Machine Helpers

Documented on page `89`.

- `run_verifier()`
- `run_verifier_silently()`
- `ord_run_blockmaker_silently()`
- `get_num_machines()`
- `machine_type(machineId)`

## Keystroke Command Syntax

Documented on pages `18-27`.

### Basic Form

- Single command:
  - `mac.mac2("f")`
- Multiple commands in one string:
  - `mac.mac2("fx")`

### Commands With Arguments

The PDF shows the command-argument wrapper as `\? ... ?`.

Examples from the documented syntax:

- numeric argument pattern:
  - fillet example using command `5`
- text argument pattern:
  - text command example using `T`
- prompt/input pattern:
  - documented prompt forms using escaped quoting and variable references

### Pattern-Related Command Examples

The PDF includes concrete pattern examples on pages `27-28`, including:

- open pattern:
  - `\?\P,stringVal?o`
- delete pattern:
  - `\?\P,stringVal?x`
- create pattern:
  - `\?\P,stringVal,"def"?`
- set pattern visibility:
  - `\?\P,stringVal?\?v,numVal?`

These are especially useful because they are complete documented command strings rather than isolated token mentions.

## `rfmac()` Safe Command Notes

The PDF gives a very important constraint on page `14`:

- `rfmac()` must not be used if the called keystroke command performs its own scan.

The PDF explicitly lists these as currently safe with `rfmac()`:

- `s`
- `c`
- `~`
- `d`
- `e`
- `x`
  - except hatching or window delete cases
- `m`
  - except symbol or window move cases
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

This is the best concrete "known safe keystroke set" we currently have from the PDF.

## Macro Procedure Execution

Documented on pages `103-105`.

This is the other big execution path besides raw keystroke strings.

### Objects

- `MacCommands`
- `MacCommand`
- `MacArguments`
- `MacFiles`
- `MacFile`

### Important Methods

- `MacCommand.Execute()`
- `MacFiles.Load(file)`
- `MacFile.Unload()`
- `MacFile.EnquireGlobalValue(name)`

### Practical Meaning

If we want structured automation without hand-building fragile keystroke strings, loading a MAC file and executing named procedures is likely the cleaner path.

## Interop-Confirmed Surface On This Machine

From `Radan.Shared.Radraft.Interop.dll` on this workstation:

### Exported Interface Names

- `Radan.Shared.Radraft.Interop.IRadraftApplication`
- `Radraft.Interop.IDocument`
- `Radraft.Interop.IMac`
- `Radan.Shared.Radraft.Interop.IPartEditor`

### Confirmed `IPartEditor` Method

The installed interop exposes:

- `DrawRectangle(Double x, Double y, Double width, Double height)`

It does not currently expose `DrawCircle` on `IPartEditor`, which is why the live geometry helpers in this repo are rectangle-based only.

### Confirmed Command-Relevant `IMac` Methods

Reflection confirmed these names on the installed `IMac` surface:

- `d_fix`
- `elf_bounds`
- `elf_closed`
- `elf_set_option`
- `end_scan`
- `fmac2`
- `mac2`
- `next`
- `rewind`
- `rfmac`
- `scan`
- `silent_exit_nc_mode`
- `silent_nc_mode`

This lines up well with the PDF sections already mined.

## What We Can Call Reliably Today

With the current repo state, the most reliable command paths are:

- `Application` / `Document` COM calls for open, save, close, and quit
- `Mac` licensing calls
- `Mac.flat_thumbnail(...)`
- `Mac.output_*_report(...)`
- guarded live attach and `PartEditor.DrawRectangle(...)`
- isolated headless document open/export/copy workflows

See:

- [radan_com.py](</c:/Tools/radan_automation/radan_com.py>)
- [probe_live_session.py](</c:/Tools/radan_automation/probe_live_session.py>)
- [headless_export_document_artifacts.py](</c:/Tools/radan_automation/headless_export_document_artifacts.py>)

## Gaps

This catalog is still missing a full alphabetical keystroke table.

Most likely next sources:

- the installed CHM pages referenced by the PDF:
  - `C:\Program Files\Mazak\Mazak\help\manuals\radanapi.chm`
  - `C:\Program Files\Mazak\Mazak\help\manuals\radraft.chm`
- any XML help or decompiled CHM pages containing `Keystroke Reference`
- controlled live testing of documented keystroke strings through `mac2()` and `rfmac()`

## Recommended Next Step

Build a second file, `KEYSTROKE_REFERENCE_EXTRACT.md`, from the installed help with:

- the documented keystroke token
- the mode it belongs to
- whether it appears safe for `rfmac()`
- a short meaning
- whether we have tested it successfully
