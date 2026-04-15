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
  - executed successfully against an attached visible RADAN UI session
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
| `Mac.scan(...)` / `next()` / `rewind()` | PDF, interop | headless/live | keystroke find workflows | `API` | `doc-only` | Prefer for deterministic feature iteration instead of cursor-driven find commands. |
| `Mac.elf_bounds(...)` | PDF, interop | live/headless | pattern-based size queries via keystrokes | `API` | `tested-live` | Used indirectly to compute active part bounds for live rectangle placement. |
| `Mac.fed_edit_feature(...)` | PDF, interop | headless/live | edit-mode keystrokes | `API` | `doc-only` | Strong candidate for structured feature edits instead of edit-mode keys. |
| `IPartEditor.DrawRectangle(...)` | interop reflection | live | keystroke `"` rectangle | `API` | `tested-live` | Successfully attached to live Part Editor and drew geometry. |
| `run_verifier()` / `run_verifier_silently()` | PDF, interop | verifier | keystroke-driven verifier workflow | `API` | `doc-only` | Better as typed calls if we automate verifier mode later. |
| `ord_run_blockmaker_silently()` | PDF, interop | order mode | order-mode keystrokes | `API` | `doc-only` | Prefer typed path if order/blockmaker automation becomes important. |

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
