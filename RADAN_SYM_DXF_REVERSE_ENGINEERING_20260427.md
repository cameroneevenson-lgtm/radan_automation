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
