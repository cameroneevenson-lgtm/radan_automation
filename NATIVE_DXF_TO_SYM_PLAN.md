# Native DXF to SYM Plan

Last updated: 2026-04-27

## Goal

Create RADAN `.sym` files directly from Inventor-exported DXF files without using RADAN conversion during the normal import path.

Target operating result:

- no extra RADAN license seat
- no visible RADAN UI disturbance
- no requirement to close existing RADAN windows
- no production `.rpd` or `.sym` write until file-level validation passes
- all Python entry points run through `C:\Tools\.venv\Scripts\python.exe`

## Current State

Already proven:

- source DXF entity order matches generated DDC geometry record order for all 98 F54410 paint-pack parts
- DXF `LINE` maps to DDC `G`
- DXF `ARC` and `CIRCLE` map to DDC `H`
- DDC field index `8` is the pen field
- DDC field index `10` contains compact geometry data
- `IV_INTERIOR_PROFILES` maps to pen `1`
- `IV_MARK_SURFACE` maps to pen `7`
- `.rpd` project rows can already be updated directly without RADAN

Still blocked:

- DDC compact numeric geometry encoding
- exact `G` line field semantics
- exact `H` arc/circle field semantics
- production-confidence metadata regeneration

## Safety Rules

1. File parsing, corpus analysis, and prototype writing are always allowed because they do not touch RADAN.
2. Any COM probe must attach only to a known hidden automation-owned RADAN process, or stop and report the blocker.
3. Do not attach to a visible user RADAN session for this work.
4. Do not create a new RADAN process unless explicitly approved for a one-off experiment.
5. Do not run conversion against the production paint-pack folder during research. Copy input to `C:\Tools\_sym_lab\...`.
6. Do not write generated prototype `.sym` files into production project folders.
7. Do not wire native `.sym` writing into Truck Nest Explorer until the validation harness can reject bad output automatically.

## Phase 1: DDC Corpus Extractor

Deliverable:

- `ddc_corpus.py`

Inputs:

- BOM/RADAN CSV path
- generated symbol folder
- optional output JSON/CSV path

Responsibilities:

- parse each source DXF with `ezdxf`
- parse each generated `.sym` XML
- extract DDC `G` and `H` records
- split geometry data into dot-separated slots
- normalize DXF coordinates into local positive symbol space
- pair DXF entities with DDC records by order
- emit a durable corpus file under a scratch/output path

Pass gate:

- all 98 F54410 rows produce paired DXF/DDC records
- total entity count remains `4085`
- count mismatch is zero
- type mismatch is zero
- output is deterministic across two runs

Why this is first:

- it requires no RADAN
- it creates the truth table needed for the encoding work
- it lets us test hypotheses quickly without disturbing open sessions

## Phase 2: Slot and Token Analyzer

Deliverable:

- `analyze_ddc_tokens.py`

Responsibilities:

- group tokens by record type, slot index, DXF entity type, layer, pen, and normalized numeric value
- report token reuse and value reuse
- find slots that behave like absolute coordinates
- find slots that behave like deltas or omitted/default values
- isolate simple records such as horizontal/vertical lines and full circles
- emit candidate field maps for `G` and `H`

Pass gate:

- produce a ranked hypothesis for `G` line slots
- produce a ranked hypothesis for circle-style `H` slots
- identify at least one subset of records where token/value behavior is consistent enough to attempt reproduction

Expected first target:

- line-only reproduction for simple horizontal and vertical records
- circle records second
- true arcs last

## Phase 3: Hidden COM Oracle Probe

Deliverable:

- `probe_hidden_sym_scan.py`

Purpose:

- use RADAN only as a decoder/oracle, not as the production converter

Responsibilities:

- attach to a known hidden automation-owned RADAN process
- open a copied `.sym`
- dump `COP`, `CUP`, `PART_PATTERN`, `PRS`, and active-document state
- scan with filters `l`, `a`, and blank filter
- capture `FI0`, `FP0`, `FT0`, `LT0`, `S0X`, `S0Y`, `TS0X`, `TS0Y`, `TE0X`, `TE0Y`
- write results to scratch JSON

Pass gate:

- hidden scan returns at least one feature row from copied `B-28-copy.sym`
- scan identifiers can be correlated to DDC record identifiers

Fallback if hidden scan cannot work:

- skip COM oracle for now
- continue with file corpus only
- use visible RADAN validation only as a deliberate manual final check, not as part of normal research automation

## Phase 4: Native Writer Prototype

Deliverable:

- `write_native_sym_prototype.py`

First target:

- clone the XML wrapper from a known-good symbol
- replace only the minimum DDC geometry block and bounding attributes
- generate `B-28-native.sym` under `C:\Tools\_sym_lab\out`

Responsibilities:

- preserve XML namespace and compound document shape
- preserve safe metadata from a known-good template
- write deterministic DDC records
- never write to production folders

Pass gate:

- generated XML is well-formed
- generated DDC record count matches source DXF entity count
- generated `G`/`H` record type sequence matches source DXF sequence
- generated symbol can be parsed by our file tools

## Phase 5: Validation Harness

Deliverable:

- `validate_native_sym.py`

Validation tiers:

1. XML parses cleanly.
2. DDC block parses cleanly.
3. DXF-to-DDC record count and type sequence match.
4. bounds match source DXF normalized extents within tolerance.
5. direct `.rpd` add works in a copied project.
6. optional manual RADAN open/nest check only after file validation passes.

Pass gate:

- `B-28-native.sym` passes tiers 1 through 5 without RADAN
- any manual RADAN check is explicitly started by a human, not hidden in the normal run

## Phase 6: Controlled Integration

Deliverable:

- native conversion mode in `import_parts_csv_headless.py`, initially behind a flag

Proposed flag:

- `--native-sym-experimental`

Behavior:

- default remains current known-working behavior
- native mode writes only to a copied/test output folder until promoted
- report clearly labels native output as experimental
- if validation fails, do not update the project

Pass gate:

- native mode successfully generates and validates a small copied project
- no RADAN process is opened
- no visible user RADAN session redraws or changes state

## Stop Conditions

Stop and report instead of continuing if:

- a planned command would touch a production project folder
- a planned command would attach to a visible RADAN session
- a planned command would create a new RADAN process without explicit approval
- generated `.sym` output passes our parser but fails obvious geometric sanity checks
- DDC token behavior proves intentionally encrypted or keyed to file/session metadata

## Decision Points

After Phase 2:

- decide whether enough DDC structure is understood to attempt a writer
- if not, spend one focused pass on the hidden COM oracle

After Phase 4:

- decide whether to keep chasing exact native encoding or pivot to a safer partial approach

After Phase 5:

- decide whether native generation is good enough for a guarded Truck Nest Explorer experiment

## Immediate Next Action

Build `ddc_corpus.py` and run it against:

```powershell
C:\Tools\.venv\Scripts\python.exe .\ddc_corpus.py `
  --csv "L:\BATTLESHIELD\F-LARGE FLEET\F54410\PAINT PACK\F54410 PAINT PACK\F54410-PAINT PACK-BOM_Radan.csv" `
  --sym-folder "L:\BATTLESHIELD\F-LARGE FLEET\F54410\PAINT PACK" `
  --out "C:\Tools\_sym_lab\f54410_ddc_corpus.json"
```

Expected result:

- no RADAN launch
- no license use
- corpus JSON containing all 4,085 paired DXF/DDC records

## Progress 2026-04-27

Completed Phase 1 deliverable:

- `ddc_corpus.py`
- tests: `tests/test_ddc_corpus.py`
- corpus output: `C:\Tools\_sym_lab\f54410_ddc_corpus.json`

Phase 1 pass gate result:

- part count: `98`
- total DXF entities: `4085`
- total DDC records: `4085`
- count mismatches: `0`
- type mismatches: `0`
- known layer/pen mismatches: `0`

Completed Phase 2 deliverable:

- `analyze_ddc_tokens.py`
- tests: `tests/test_analyze_ddc_tokens.py`
- token analysis output: `C:\Tools\_sym_lab\f54410_ddc_token_analysis.json`

Phase 2 findings:

- `G`/`LINE` slots `0` and `1` behave like absolute normalized start `X` and start `Y`.
- `G`/`LINE` slots `2` and `3` fit delta `X` and delta `Y` much better than absolute end `X` and end `Y`.
- empty `G` delta slots mean zero delta.
- at 6-decimal comparison precision, line slot token-to-value mapping is nearly deterministic:
  - start `X`: `0` ambiguous non-empty tokens
  - start `Y`: `0` ambiguous non-empty tokens
  - delta `X`: `2` ambiguous non-empty tokens
  - delta `Y`: `0` ambiguous non-empty tokens
- `H`/`CIRCLE` records have a stable shape: non-empty slots `0,1,4,6,9`.
- `H`/`CIRCLE` slots behave as:
  - slot `0`: start `X`, which is center `X + radius`
  - slot `1`: start `Y`, which is center `Y`
  - slot `4`: center delta `X`, which is `-radius`
  - slots `6` and `9`: constant `1`

Added numeric codec:

- `ddc_number_codec.py`
- tests: `tests/test_ddc_number_codec.py`

Decoded geometry validation:

- `G`/`LINE`: `0` failures over `3172` records, max absolute error below `0.000001`
- `H`/`CIRCLE`: `0` failures over `367` records, max absolute error below `0.000001`
- `H`/`ARC`: `0` failures over `546` records, max absolute error below `0.000001`

Decoded DDC geometry formulas:

| DDC record | DXF entity | Slot | Meaning |
| --- | --- | ---: | --- |
| `G` | `LINE` | 0 | normalized start `X` |
| `G` | `LINE` | 1 | normalized start `Y` |
| `G` | `LINE` | 2 | end `X - start X` |
| `G` | `LINE` | 3 | end `Y - start Y` |
| `H` | `ARC` | 0 | normalized start point `X` |
| `H` | `ARC` | 1 | normalized start point `Y` |
| `H` | `ARC` | 2 | end point `X - start point X` |
| `H` | `ARC` | 3 | end point `Y - start point Y` |
| `H` | `ARC` | 4 | center `X - start point X` |
| `H` | `ARC` | 5 | center `Y - start point Y` |
| `H` | `ARC`/`CIRCLE` | 6 | constant `1` |
| `H` | `ARC`/`CIRCLE` | 9 | constant `1` |

Added Phase 3 deliverable:

- `probe_hidden_sym_scan.py`

Phase 3 run status:

- not run against COM because a visible user RADAN Nest Editor was open at PID `2100`
- the probe refused before attaching, as intended by the safety rules
- hidden automation-owned RADAN PID `2496` was present, but not touched while the visible session was open

Next executable step:

- build a native `.sym` writer prototype for copied `B-28`
- first reproduction target: regenerate the DDC geometry records from DXF using `ddc_number_codec.encode_ddc_number`
- compare decoded generated geometry to source DXF before any RADAN validation
- keep generated files under `C:\Tools\_sym_lab`
