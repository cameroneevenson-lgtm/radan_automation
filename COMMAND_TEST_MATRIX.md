# Command Test Matrix

Working matrix for deciding which RADAN command path to use and what still needs verification.

This file is intended to bridge:

- [COMMAND_CATALOG.md](</c:/Tools/radan_automation/COMMAND_CATALOG.md>)
- [API_VS_KEYSTROKE_MATRIX.md](</c:/Tools/radan_automation/API_VS_KEYSTROKE_MATRIX.md>)
- [KEYSTROKE_REFERENCE_EXTRACT.md](</c:/Tools/radan_automation/KEYSTROKE_REFERENCE_EXTRACT.md>)
- [INTEROP_SURFACE_DUMP.md](</c:/Tools/radan_automation/INTEROP_SURFACE_DUMP.md>)

## Status Legend

- `tested-headless`
  - executed successfully in an isolated automation instance
- `tested-live`
  - executed successfully against an attached, automation-backed visible RADAN session
- `wrapper-tested`
  - covered by unit tests or wrapper contract checks, but not yet proven against a live RADAN workflow here
- `doc-only`
  - documented in PDF/CHM and/or reflected from interop, but not yet exercised by us
- `not-tested`
  - identified candidate, but no execution proof yet

## Direct API / COM Paths

These are the highest-value typed calls to prefer when possible.

| Command or Surface | Source | Mode | Direct API Alternative | Recommended Path | Tested Status | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| `Application.NewDrawing(...)` | PDF, interop, wrapper | headless/live | n/a | `API` | `tested-headless` | Works when startup mode is established before forcing fully non-interactive state. |
| `Application.OpenDrawing(...)` | PDF, interop, wrapper | headless/live | n/a | `API` | `tested-headless` | Verified by opening saved drawing in headless export flow. |
| `Application.OpenSymbol(...)` | PDF, interop, wrapper | headless/live | n/a | `API` | `wrapper-tested` | Routed by `open_document()`, but no live symbol workflow proof yet. |
| `Application.OpenSymbolFromRasterImage(...)` | PDF, interop, wrapper | headless/live | n/a | `API` | `wrapper-tested` | Exposed and routed; still needs real raster import test. |
| `Application.Quit()` | PDF, interop, wrapper | headless/live | n/a | `API` | `tested-headless` | Used throughout probes and isolated export scripts. |
| `Document.Close(...)` | PDF, interop, wrapper | headless/live | n/a | `API` | `tested-headless` | Used in headless save/export flows. |
| `Document.SaveAs(...)` | PDF, interop, wrapper | headless/live | n/a | `API` | `tested-headless` | Verified in temp drawing save probe. |
| `Document.SaveCopyAs(...)` | PDF, interop, wrapper | headless/live | n/a | `API` | `tested-headless` | Verified in `headless_export_document_artifacts.py`. |
| `Mac.lic_get_holder()` / `lic_get_servercode()` | PDF, interop, wrapper | headless/live | n/a | `API` | `tested-headless` | Confirmed live license info through wrapper. |
| `Mac.fla_thumbnail(...)` | wrapper, interop | headless | n/a | `API` | `tested-headless` | Verified to produce PNG output in isolated automation instance. |
| `Mac.prj_output_report(...)` / `stp_output_report(...)` | wrapper, interop | headless/live | n/a | `API` | `wrapper-tested` | Interface present; setup report path unit-covered, real workflow still pending. |
| `Mac.scan(...)` / `next()` / `rewind()` | PDF, interop | headless/live | keystroke find workflows | `API` | `tested-live` | Proven on an attached Part Editor session for deterministic feature counting and candidate collection ahead of pen remap work. Important live nuance: `scan(...)` armed the iterator, but `next()` had to be called before reading `FI0` / `FP0` to avoid a stale prior feature. |
| `Mac.find_xy_identifier(...)` | PDF, interop | live/headless | keystroke find workflows | `API` | `tested-live` | Proven as the missing re-mark step needed before edit-mode pen changes in a live attached Part Editor session. |
| `Mac.elf_bounds(...)` | PDF, interop | live/headless | pattern-based size queries via keystrokes | `API` | `tested-live` | Used indirectly to compute active part bounds for live rectangle placement in an attachable live session. |
| `Mac.fed_edit_feature(...)` | PDF, interop | headless/live | edit-mode keystrokes | `API` | `doc-only` | Strong candidate for structured feature edits instead of edit-mode keys. |
| `IPartEditor.DrawRectangle(...)` | interop reflection | live | keystroke `"` rectangle | `API` | `tested-live` | Successfully attached to a live Part Editor and drew geometry once the session was attachable through the managed/COM path. |
| `run_verifier()` / `run_verifier_silently()` | PDF, interop | verifier | keystroke-driven verifier workflow | `API` | `doc-only` | Better as typed calls if we automate verifier mode later. |
| `ord_run_blockmaker_silently()` | PDF, interop | order mode | order-mode keystrokes | `API` | `doc-only` | Prefer typed path if order/blockmaker automation becomes important. |

## Live Session State / UI Control Paths

These are not typed geometry APIs, but they are now proven useful for real live-session targeting in the Nest Editor.

| Command or Surface | Source | Mode | Direct API Alternative | Recommended Path | Tested Status | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| `Application.GUIState` / `Application.GUISubState` | wrapper, live probe | live nest | prompt text | `API` | `tested-live` | On this machine the attached Nest session stayed at `GUIState=4` while `GUISubState` mapped `14=modify`, `7=profiling`, `11=order`. |
| `PCC_PATTERN_LAYOUT` + `ElfBounds(...)` in Nest Editor | managed bridge, interop, live probe | live nest | prompt text | `API` | `tested-live` | The attachable Nest session reported `PCC_PATTERN_LAYOUT=/layout`, and `ElfBounds('/layout', ...)` returned stable layout bounds. |
| `rtl_nest_profile_button` / `big_button_profile.bmp` | UI Automation inspection + live click | live nest | guessed keystrokes | `UI control` | `tested-live` | Foreground the RADAN window, then click the top-row Profile button. Proven `order -> profiling` on this machine. |
| `rtl_nest_modify_button` / `big_button_nest_modify.bmp` | UI Automation inspection + live click | live nest | guessed keystrokes | `UI control` | `tested-live` | Foreground the RADAN window, then click the top-row Modify button. Proven `profiling -> modify` on this machine. |
| `rtl_nest_order_button` / `big_button_order.bmp` | UI Automation inspection + live click | live nest | guessed keystrokes | `UI control` | `tested-live` | Foreground the RADAN window, then click the top-row Order button. Proven `modify -> order` on this machine. |
| `rpr_parts_list_import_parts_button` / `project_import_parts.bmp` | UI Automation inspection + live click | live nest / modify | guessed keystrokes | `UI control` | `tested-live` | Custom launcher for the parts import flow. Proven live once the RADAN window was moved fully on-screen; off-screen placement made the click path unreliable. |
| `Import Parts` `#32770` child dialog | live UI inspection after launcher click | live nest / modify | direct COM import call not yet identified | `standard dialog` | `tested-live` | Launching `Import Parts` immediately surfaced a standard Windows file picker with `File name`, `Open`, `Cancel`, and `Files of type` controls. |
| `Browse...` -> `Browse For Folder` tree path | live WinForms import dialog, shell tree, MSAA, real focus | live nest / modify / import workflow | direct path-set API not identified | `standard dialog + desktop interaction` | `tested-live` | Output folder assignment was proven through the old shell tree dialog. The reliable path was real dialog focus plus MSAA/tree navigation; direct shell-selection messages and later low-level cross-process tree introspection were both unsafe. |
| `Import All` via real live click | WinForms import dialog, filesystem output watch, completion modal | live nest / modify / import workflow | direct COM import call not yet identified | `desktop interaction` | `tested-live` | Full CSV import completed with a separate `#32770` completion modal reporting `Number of parts added to the parts list: 108`. A real click allowed concurrent observation of `.sym` output and modal appearance. |
| `Import All` via synchronous `SendMessage(BM_CLICK, ...)` | Win32 message send against WinForms button | live nest / modify / import workflow | none | `do not use for observed long actions` | `tested-live` | The call blocked inside RADAN while the import ran, preventing the observer from seeing the completion modal or progress. Use a real live click instead when timing or watching the run. |
| `rpr_parts_list_import_parts_button` in populated project state | live handle inspection, real click, MSAA, `WM_COMMAND`, keyboard menu attempt | live nest / modify / populated parts list | direct COM import call still not identified | `UI control` | `tested-live` | In the `F55334 PUMP COVERINGS` Nest session with an existing populated parts list, the launcher remained visible and enabled but did not surface `Import Parts` through those routes. Standalone `LoadMacro('rtlcall')` also raised a `Mac Error` about `RPV_ON_EXIT_NEW`, so that macro-load shortcut is not safe to treat as a generic project-UI entry path. |

## Keystroke Commands With Strong CHM Evidence

These are directly described in the CHM and are likely the best route when no typed API exists.

| Command Token | Topic Path | Mode | Direct API Alternative | Recommended Path | Tested Status | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| `d` | `keystrokes.drawinglines.htm`, `keystrokes.drawingarcs.htm` | drafting | `NewDrawing(...)` does not replace drawing entities | `mac2` | `not-tested` | Overloaded across line/arc creation flows. |
| `s` | `keystrokes.drawinglines.htm`, `keystrokes.drawingarcs.htm` | drafting | none | `rfmac` for local safe use, otherwise `mac2` | `not-tested` | Also listed by PDF as safe for `rfmac()`. |
| `"` | `keystrokes.drawinglines.htm` | drafting | `IPartEditor.DrawRectangle(...)` | `API` | `not-tested` | Keystroke exists, but direct API is better and already proven. |
| `*` | `keystrokes.drawinglines.htm` | drafting | none | `mac2` | `not-tested` | Normal construction workflow. |
| `7` | `keystrokes.drawinglines.htm` | drafting | none | `mac2` | `not-tested` | Tangent-line construction. |
| `6` | `keystrokes.drawinglines.htm` | drafting | none | `mac2` | `not-tested` | Chamfer construction. |
| `c` | `keystrokes.drawingarcs.htm` | drafting | none | `rfmac` or `mac2` | `not-tested` | PDF marks `c` safe for `rfmac()`. |
| `o` | `keystrokes.drawingarcs.htm` | drafting | none | `mac2` | `not-tested` | Arc completion flow; likely stateful. |
| `~` | `keystrokes.drawingarcs.htm`, pattern topics | drafting/pattern | none | `rfmac` or `mac2` depending context | `not-tested` | PDF marks `~` safe for `rfmac()`, but behavior is mode-sensitive. |
| `&` | `keystrokes.drawingarcs.htm` | drafting | none | `mac2` | `not-tested` | Arc tangent workflow. |
| back-quote | `keystrokes.addingacentre.linecross.htm` | drafting | none | `mac2` | `not-tested` | Centre-line cross creation. |
| `T` | `keystrokes.addingtext.htm` | drafting | no direct text-create API found yet | `mac2` | `not-tested` | Strong candidate for keystroke-only text entry. |
| `j` | copy/pattern topics | drafting/pattern | none | `mac2` | `not-tested` | Used for cursor jump/copy and pattern jump. |
| `f` | `keystrokes.findinganyfeature.htm` | drafting/find | `scan(...)` for structured iteration | `mac2` or `rfmac` | `not-tested` | PDF marks `f` safe for `rfmac()`, but `scan()` is better for headless logic. |
| `e\?P,<pen>?` | `keystrokes.editing features/Keystrokecommands.pen.p.htm` | drafting/edit | `fed_edit_feature(...)` is a future candidate, not yet proven for pen changes | mixed `API` + `rfmac` | `tested-live` | Direct `rfmac('e\\?P,...')` from scan state failed with `First find a feature`. The proven live path is `scan(...)` to collect FI0/S0X/S0Y, then `find_xy_identifier(...)`, then `rfmac('e\\?P,<pen>?')`. |
| `l` / `L` | `keystrokes.findinglines.htm` | drafting/find | `scan(..., 'l', ...)` | `mac2` or `rfmac` | `not-tested` | Strong for cursor-relative user workflows, weaker for unattended automation. |
| `a` / `A` | `keystrokes.findingarcs.htm` | drafting/find | `scan(..., 'a', ...)` | `mac2` or `rfmac` | `not-tested` | Similar tradeoff to line find. |
| `t` | `keystrokes.findingtext.htm` | drafting/find | `scan(..., 't', ...)` | `mac2` or `rfmac` | `not-tested` | PDF marks `t` safe for `rfmac()`. |
| `2` | `keystrokes.findingdimensions.htm` | drafting/find | `scan(..., 'd', ...)` for dimensions | `mac2` | `not-tested` | Dimension find is probably easier by keystroke in attached sessions. |
| `H` | `keystrokes.findinghatching.htm` | drafting/find | `scan(..., 'h', ...)` | `mac2` | `not-tested` | Uppercase hatching find. |
| `9` | `keystrokes.findingsymbols.htm` | drafting/find | `scan(..., 's', ...)` | `mac2` | `not-tested` | Symbol find. |
| `.` | `keystrokes.findingcentre.linecrosses.htm` | drafting/find | `scan(..., 'c', ...)` partly related, not equivalent | `rfmac` or `mac2` | `not-tested` | PDF lists `.` as safe for `rfmac()`. |
| `w` | window selection topics | window/select | typed scans do not replace interactive windows | `mac2` | `not-tested` | Good attached-session candidate, poor headless candidate. |
| `Ctrl+f` | filter topic | drafting/find | typed scan filters | `mac2` | `not-tested` | More UI-stateful than typed scan filters. |
| `Ctrl+p` | `keystrokes.patternmode.htm` | pattern | some ELF operations, not pattern mode itself | `mac2` | `not-tested` | Entry point for many pattern operations. |
| `x` | pattern and edit topics | pattern/edit | `Document.Close`, feature-editor, pattern APIs partial | `rfmac` or `mac2` | `not-tested` | PDF says safe for `rfmac()` in some cases, but not window delete or hatching-related cases. |
| `m` | pattern manipulation | pattern | none | `mac2` | `not-tested` | PDF says `m` is only safe for `rfmac()` outside symbols/window move. |
| `S` | pattern manipulation | pattern | `SaveCopyAs` is not equivalent | `mac2` | `not-tested` | Pattern save-and-retain behavior is keystroke-level. |
| `\!` | MAC language manual escape command | live nest/order | top-row Nest mode buttons | `unknown` | `tested-live` | Accepted by RADAN and returned success in `order` mode, but did not move the session out of `GUISubState=11` here. |
| `?` / `??` | `on.screenhelpforkeystrokes.htm` | all interactive modes | none | manual / `mac2` research only | `not-tested` | Best discovery aid for attached live sessions, not production automation. |
| `r`, `z`, `Ctrl+r`, `Ctrl+z` | redraw/zoom topics | view | none | `mac2` | `not-tested` | Interactive-only, not useful for unattended headless runs. |
| `q` | query topic | drafting/query | some typed geometry APIs overlap | `mac2` | `not-tested` | Better for attached operator workflows than batch automation. |
| `0` | `keystrokes.recallingasymbol.htm` | part/drafting | `OpenSymbol(...)` is related but not equivalent | `mac2` | `not-tested` | Symbol recall is a cursor-driven editor behavior. |
| `Space` | symbol fixing topic | part/drafting | none | `mac2` | `not-tested` | UI/object-placement action, likely live-only. |
| `)` | symbol realising topic | part/drafting | none | `mac2` | `not-tested` | Another strong live-session keystroke candidate. |
| `8` | parallel-copy topic | drafting | none | `mac2` | `not-tested` | Construction command with no typed equivalent found yet. |

## Suggested Test Order

If we want to start proving these safely, the best sequence is:

1. `rfmac()`-safe, non-scan commands in a disposable part or drawing
   - `s`, `c`, `d`, `e`, `f`, `l`, `.`, `t`
2. direct-vs-keystroke comparisons where a typed API exists
   - `"` rectangle vs `IPartEditor.DrawRectangle(...)`
3. low-risk attached-session commands in a scratch document
   - `Ctrl+p`, `o`, `x`, `j`, `m`
4. heavier edit-mode or cursor-stateful commands
   - `%`, `^`, `J`, `q`, symbol fix/realise flows

## Current Recommendation

- Prefer `API` for anything lifecycle, export, scan, ELF, or feature-editor related.
- Prefer `mac2` for most interactive drafting/edit/pattern workflows.
- Reserve `rfmac` for the documented safe commands only.
- Treat the keystroke rows above as a testing backlog until we add live execution proof for each one.
