# RADAN SYM/DXF Reverse Engineering Notes 2026-04-27

## Scope

This pass compared the source DXFs in:

`L:\BATTLESHIELD\F-LARGE FLEET\F54410\PAINT PACK\F54410 PAINT PACK\F54410-PAINT PACK-BOM_Radan.csv`

against the RADAN-generated symbols in:

`L:\BATTLESHIELD\F-LARGE FLEET\F54410\PAINT PACK`

The goal was to determine whether a no-RADAN-installed DXF-to-SYM generator is plausible, similar to the direct `.sym` pen remapper.

## File Structure

The generated `.sym` files are XML compound documents:

- root: `RadanCompoundDocument`
- metadata: `RadanAttributes`
- preview/cache sections: thumbnail/history/cache CDATA blocks
- geometry: `<RadanFile extension="ddc">` CDATA block

The useful production geometry lives in the `ddc` block.

## Geometry Record Mapping

Across all 98 F54410 paint-pack CSV rows:

- total source DXF entities checked: 4,085
- total generated DDC geometry records: 4,085
- count mismatches: 0
- type mismatches: 0

Mapping:

| DXF entity | DDC record |
| --- | --- |
| `LINE` | `G` |
| `ARC` | `H` |
| `CIRCLE` | `H` |

Record order matched source DXF modelspace order for every checked part.

## Layer/Pen Mapping

The generated DDC pen field is field index `8`, matching the direct pen-remap utility's prior finding.

Observed mapping:

| Count | DXF type | DXF layer | DDC record | DDC pen |
| ---: | --- | --- | --- | --- |
| 1730 | `LINE` | `IV_MARK_SURFACE` | `G` | `7` |
| 1442 | `LINE` | `IV_INTERIOR_PROFILES` | `G` | `1` |
| 522 | `ARC` | `IV_INTERIOR_PROFILES` | `H` | `1` |
| 367 | `CIRCLE` | `IV_INTERIOR_PROFILES` | `H` | `1` |
| 24 | `ARC` | `IV_MARK_SURFACE` | `H` | `7` |

So a first-pass native converter can infer:

- `IV_INTERIOR_PROFILES` -> pen `1`
- `IV_MARK_SURFACE` -> pen `7`

## Coordinate Normalization

RADAN appears to normalize source geometry into a positive local symbol coordinate space.

Example `B-28`:

- DXF extents:
  - X: `0` to `2`
  - Y: `-1.523913` to `1.322835`
- SYM attributes:
  - Bounding box X: `2`
  - Bounding box Y: `2.846748`

That matches shifting Y by `+1.523913` while preserving dimensions.

## Numeric Encoding Status

The main unsolved piece is RADAN's compact numeric encoding in DDC field data.

Examples from `B-28`:

- a DXF line from `(1.75, 1.322835)` to `(0.25, 1.322835)` becomes a `G` record with compact geometry data:
  - `o?<.0@6aR?@_j2@.o?X..............`
- after Y normalization, the likely numeric sequence is:
  - `1.75`, `2.846748`, `0.25`, with repeated/zero values omitted or represented by empty dot-separated slots

Known token/value hints from `B-28`:

| Likely value | Token |
| ---: | --- |
| `0` | empty token |
| `0.125` | `l?P` |
| `0.25` | `o?X` |
| `0.375` | `m?8` |
| `1.0` | `o?2` |
| `1.75` | `o?<` |
| `2.0` | `0@0` |
| `2.846748` | `0@6aR?@_j2@` |

This looks like a proprietary printable real-number encoding, not raw DXF text.

### B-28 Record-Level Observations

`B-28` remains the best small specimen because it has 13 source entities and 13 generated DDC records.

Source:

- DXF: `W:\LASER\For Battleshield Fabrication\F54410\PAINT PACK\B-28.dxf`
- generated symbol: `L:\BATTLESHIELD\F-LARGE FLEET\F54410\PAINT PACK\B-28.sym`
- copied successful symbol: `C:\Tools\_sym_probe_copy\out\B-28-copy.sym`

The record identifiers in the DDC block are:

`3, 4, 5, 6, 7, 8, 9, :, ;, <, =, >, ?`

The B-28 DXF-to-DDC order is exactly modelspace order:

| # | DXF type | Layer | DDC | Pen | Normalized values observed | Geometry tokens |
| ---: | --- | --- | --- | ---: | --- | --- |
| 1 | `ARC` | `IV_INTERIOR_PROFILES` | `H 3` | 1 | center/radius/angles approx `1.75, 2.596748, 0.25, 0, 90` | `0@0.0@4aR?@_j2@.m?P.m?0.m?P..o?0...o?0...........` |
| 2 | `CIRCLE` | `IV_INTERIOR_PROFILES` | `H 4` | 1 | center/radius approx `1.0, 0.375, 0.125` | `o?2.m?8...l?P..o?0...o?0...........` |
| 3 | `LINE` | `IV_INTERIOR_PROFILES` | `G 5` | 1 | start/end approx `1.75, 2.846748, 0.25, 2.846748` | `o?<.0@6aR?@_j2@.o?X..............` |
| 4 | `ARC` | `IV_INTERIOR_PROFILES` | `H 6` | 1 | center/radius/angles approx `0.25, 2.596748, 0.25, 90, 180` | `m?0.0@6aR?@_j2@.m?P.m?P..m?P.o?0...o?0...........` |
| 5 | `LINE` | `IV_INTERIOR_PROFILES` | `G 7` | 1 | start/end approx `0, 1.523913, 0, 2.596748` | `.o?8HO:I3c0P..o?1:UD8L140.............` |
| 6 | `LINE` | `IV_INTERIOR_PROFILES` | `G 8` | 1 | start/end approx `0.155475, 1.072835, 0, 1.523913` | `l?3iY[D;3d0.o?1:UD8L140.l?SiY[D;3d0.m?<gWI2O7b0.............` |
| 7 | `LINE` | `IV_INTERIOR_PROFILES` | `G 9` | 1 | start/end approx `0.486084, 0.164495, 0.155475, 1.072835` | `m??700@a_N0.l?53R\`B[H80.m?U:;:V\=T0.n?=4Al<=<60.............` |
| 8 | `ARC` | `IV_INTERIOR_PROFILES` | `H :` | 1 | center/radius/angles approx `0.721007, 0.25, 0.25, 200, 270` | `m??6omZ8^:0.l?53R_5^_X0.l?>4OI2DRd0.l?U3R_5^_X0.l?>4OI2DRd0.k?5hjQdRP\`0.o?0...o?0...........` |
| 9 | `LINE` | `IV_INTERIOR_PROFILES` | `G ;` | 1 | start/end approx `1.278993, 0, 0.721007, 0` | `o?4M\5M;@70..n?Qf\`Ed]0L0..............` |
| 10 | `ARC` | `IV_INTERIOR_PROFILES` | `H <` | 1 | center/radius/angles approx `1.278993, 0.25, 0.25, 270, 340` | `o?4M\5M;@70..l?>4OI2DRd0.l?53R_5^_X0..m?0.o?0...o?0...........` |
| 11 | `LINE` | `IV_INTERIOR_PROFILES` | `G =` | 1 | start/end approx `1.844525, 1.072835, 1.513916, 0.164495` | `o?=PbbUNWQP.o?1:UD8L140.m?U:;:V\=T0.n?]4Al<=<60.............` |
| 12 | `LINE` | `IV_INTERIOR_PROFILES` | `G >` | 1 | start/end approx `1.844525, 1.072835, 2.0, 1.523913` | `o?=PbbUNWQP.o?1:UD8L140.l?3iY[D;3d0.m?<gWI2O7b0.............` |
| 13 | `LINE` | `IV_INTERIOR_PROFILES` | `G ?` | 1 | start/end approx `2.0, 1.523913, 2.0, 2.596748` | `0@0.o?8HO:I3c0P..o?1:UD8L140.............` |

Important nuance: repeated tokens are not a simple global `number -> token` mapping. Some equivalent-looking coordinates use different tokens depending on record type, slot, omitted/default values, orientation, or local feature state. For example, `0.25` appears as `o?X`, `m?0`, `m?P`, and `l?>4OI2DRd0` in different contexts. That makes a naive dictionary encoder risky.

The data still looks deterministic, because equivalent generated symbols from the same source preserve the same DDC block structure.

## Synthetic DXF Experiments

Minimal `ezdxf.new()` DXFs were not accepted by RADAN conversion. RADAN rejected them before producing a symbol.

These variants were tested:

- brand-new minimal DXF with known lines/arcs
- `ezdxf` load of real `B-28.dxf`, delete modelspace entities, add synthetic entities, save
- text rewrite of real `B-28.dxf` with no coordinate changes
- text transform of real `B-28.dxf` with coordinate edits
- fixed-decimal text transform to avoid scientific notation such as `-5e-16`

Results:

- real `B-28.dxf` copied to `C:\Tools\_sym_probe_copy\B-28-copy.dxf` converted successfully
- no-change text rewrite converted successfully
- synthetic entity replacement failed
- coordinate-transformed versions failed, even when scientific notation was removed

Likely implications:

- RADAN's DXF importer is more sensitive than a normal CAD parser
- Inventor DXF headers, tables, extents, handles, object ownership, or profile consistency may matter
- synthetic corpus generation should start from controlled real Inventor-exported DXFs, not from bare `ezdxf` documents
- failed transformed files are not proof that native `.sym` writing is impossible; they are only a warning that RADAN is a poor black-box converter for arbitrary synthetic DXF fixtures

## Public Research

No public DDC/SYM geometry encoding specification was found.

Searches for `RADAN DDC file format`, `.sym RadanFile extension ddc`, and known token fragments such as `o?X` did not reveal a technical spec. Public Hexagon material confirms that Radimport can batch import DXF/DWG and create RADAN parts, but it does not document the `.sym` internal DDC record encoding.

Useful public context:

- Hexagon RADAN Radimport: https://hexagon.com/products/radan-radimport
- Hexagon RADAN Radraft: https://hexagon.com/products/radan-radraft

Conclusion: treat DDC as proprietary and reverse engineer from local generated files and RADAN's COM/macro API.

## COM Oracle Experiments

The hidden RADAN process `PID 2496` was confirmed by the user to belong to this automation work. It had:

- process name: `RADRAFT`
- no visible main window
- RADAN info from COM:
  - `process_id=2496`
  - `visible=False`
  - `interactive=False`
  - `gui_state=3`
  - `gui_sub_state=6`
  - version `2025.1.2523.1252`

This process is useful as a safer oracle than attaching to visible user sessions, provided we do not make it visible or steal focus.

### Macro Number API Attempt

The interop dump lists methods that look useful:

- `GetNumberInMacCode(String name)`
- `GetStringInMacCode(String name)`
- `SetNumberInMacCode(String name, Double value)`
- `SetStringInMacCode(String name, String value)`

Attempting to call these through the current dynamic `win32com` wrapper failed both on:

- root `Radraft.Application`
- `Radraft.Application.Mac`

Observed errors:

- `AttributeError('Radraft.Application.SetNumberInMacCode')`
- `AttributeError('<unknown>.SetNumberInMacCode')`

This does not prove the methods are unusable. It likely means the current late-bound dispatch object is not exposing the typed interface that the interop XML lists. Possible next attempts:

- try `comtypes` with generated type information
- inspect the actual `Mac` dispatch object with `dir()` and type info
- invoke `ExecuteMacCode`/`LoadMacro` to set macro variables, then read them through exposed getters if available
- check whether these methods live on a different typed object than the object currently returned by `Application.Mac`

### Hidden OpenSymbol + Scan Attempt

The hidden process was asked to open:

`C:\Tools\_sym_probe_copy\out\B-28-copy.sym`

Then scan was attempted:

```text
mac.scan('/symbol editor', '', 0) -> True
while mac.next(): ... -> no rows
```

The empty scan is inconclusive. It may mean:

- wrong scan path for hidden/non-interactive Symbol Editor context
- wrong feature filter; previous successful live scan work used feature filters such as `l` and `a`
- read-only `OpenSymbol(..., True, '')` did not establish the same editor state as visible Part Editor
- hidden RADAN was not in the expected document/editor mode after opening
- `scan()` requires a visible or interactive editor in this RADAN version

It does not prove the file has no features; direct DDC and DXF counts already prove it does.

Next COM-oracle probe should dump after `OpenSymbol`:

- `COP`, `CUP`, `PART_PATTERN`, `PRS`
- `ActiveDocument.Type`, `ActiveDocument.Dirty`
- scan rows separately for filters `l`, `a`, and possibly blank filter
- fields `FI0`, `FP0`, `FT0`, `LT0`, `S0X`, `S0Y`, `TS0X`, `TS0Y`, `TE0X`, `TE0Y`

If scan works in hidden mode, correlate scan `FI0` identifiers back to DDC record identifiers.

## Operational Constraint

The desired path is:

- no extra RADAN license seat
- no visible RADAN UI disturbance
- no requirement to close existing user RADAN sessions

Separate Windows users/sessions, VMs, or another visible RADAN process may isolate UI state, but they probably consume another RADAN/Mazak license seat. That makes them less attractive for production.

The preferred architecture is therefore:

1. convert Inventor BOM to RADAN CSV inline in Truck Nest Explorer
2. parse DXF and generate `.sym` directly as files
3. update `.rpd` directly as XML
4. never call RADAN COM for the normal import path

The current blocker is only step 2: native generation of valid DDC geometry records.

## Current Encoding Hypotheses

What seems solid:

- DDC geometry record order equals DXF modelspace order for the F54410 paint pack.
- `G` records are lines.
- `H` records are arcs and circles.
- record field index `8` is pen.
- record field index `10` contains compact geometry data.
- empty dot slots often represent zero, unchanged, omitted, or default values.
- RADAN normalizes part geometry into positive local symbol coordinates.

What is not solved:

- whether compact numeric tokens are standalone encoded doubles, slot-dependent values, deltas, or macro-code expressions
- whether line records encode `start x, start y, end x, end y` directly or use mixed absolute/delta/omitted fields
- whether arc records encode center/radius/angles directly or endpoint/bulge/orientation data
- how to regenerate all derived symbol metadata safely enough for production

Most likely approach:

- solve the DDC field format from real generated symbols first
- use COM scan only as an oracle, not as the production converter
- generate a native `.sym` prototype for one small known part
- validate by adding the prototype `.sym` to a copied `.rpd` and opening/nesting in RADAN only after file-level confidence is high

## Reusable Probe

Added:

`probe_sym_dxf_mapping.py`

Example:

```powershell
C:\Tools\.venv\Scripts\python.exe .\probe_sym_dxf_mapping.py `
  --csv "L:\BATTLESHIELD\F-LARGE FLEET\F54410\PAINT PACK\F54410 PAINT PACK\F54410-PAINT PACK-BOM_Radan.csv" `
  --output-folder "L:\BATTLESHIELD\F-LARGE FLEET\F54410\PAINT PACK"
```

## Feasibility

Native DXF-to-SYM generation looks plausible but not done.

Likely easy:

- generate the XML compound document wrapper
- set material/thickness/strategy/orientation attributes
- create `G` and `H` record counts in source DXF order
- map layers to DDC pens
- write `.rpd` project rows directly, which is already implemented

Hard part:

- encode line/arc/circle geometry values into RADAN DDC numeric tokens
- regenerate trustworthy derived attributes such as area, perimeter, bounding boxes, workflow status, thumbnails/history/cache

Practical next step:

Build a small synthetic DXF corpus with known values, convert once through RADAN in a controlled/closed session, and solve the DDC numeric encoder from known token/value pairs.
