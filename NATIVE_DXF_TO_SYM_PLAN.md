# Native DXF to SYM Plan

Last updated: 2026-04-28

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
5. Do not run conversion against the production paint-pack folder during research. Copy input to `C:\Tools\radan_automation\_sym_lab\...`.
6. Do not write generated prototype `.sym` files into production project folders.
7. Do not wire native `.sym` writing into Truck Nest Explorer until the validation harness can reject bad output automatically.
8. Treat `W:` as read-only source truth. Do not create, overwrite, move, or delete files on `W:` from RADAN automation.
9. The only allowed `W:` mutation is the Inventor-to-RADAN handoff output we own: generated `*_Radan.csv` and `*_report.txt` files that are immediately moved/cut-copied to the matching `L:` project folder.

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
- generate `B-28-native.sym` under `C:\Tools\radan_automation\_sym_lab\out`

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
  --out "C:\Tools\radan_automation\_sym_lab\f54410_ddc_corpus.json"
```

Expected result:

- no RADAN launch
- no license use
- corpus JSON containing all 4,085 paired DXF/DDC records

## Progress 2026-04-27

Completed Phase 1 deliverable:

- `ddc_corpus.py`
- tests: `tests/test_ddc_corpus.py`
- corpus output: `C:\Tools\radan_automation\_sym_lab\f54410_ddc_corpus.json`

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
- token analysis output: `C:\Tools\radan_automation\_sym_lab\f54410_ddc_token_analysis.json`

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
- keep generated files under `C:\Tools\radan_automation\_sym_lab`

## Progress 2026-04-27 Overnight

Added exact numeric and comparison tooling:

- `ddc_number_codec.encode_ddc_number_fraction(...)`
- `write_native_sym_prototype.py --canonicalize-endpoints`
- `write_native_sym_prototype.py --topology-snap-endpoints`
- `compare_ddc_geometry.py`
- tests:
  - `tests/test_ddc_number_codec.py`
  - `tests/test_write_native_sym_prototype.py`
  - `tests/test_compare_ddc_geometry.py`

Key discovery:

- `B-14` failed even though it is line-only.
- The decoded floats looked correct, but shared endpoints were not always the same exact decoded DDC fraction.
- A line endpoint reached as `start + delta` can differ from the neighboring line's absolute start by around `1e-17` if all slots are encoded independently.
- The synthetic writer now has a lab-only canonical mode that encodes endpoint fractions first, then encodes deltas from those exact fractions.

Best current lab generator settings:

```powershell
C:\Tools\.venv\Scripts\python.exe .\write_native_sym_prototype.py `
  --dxf "<source.dxf>" `
  --template "<radian-direct-template.sym>" `
  --out "C:\Tools\radan_automation\_sym_lab\<part>.sym" `
  --source-coordinate-digits 6 `
  --topology-snap-endpoints `
  --canonicalize-endpoints
```

Important source-rounding correction:

- round source points and source min bounds to 6 decimals
- do not round radii

Best current full-corpus lab output:

`C:\Tools\radan_automation\_sym_lab\synthetic_topology_canonical_source6_preserve_radius_full_20260427`

Comparison artifacts:

- exact closure:
  `C:\Tools\radan_automation\_sym_lab\f54410_topology_canonical_source6_preserve_radius_exact_compare.json`
- decoded slot comparison:
  `C:\Tools\radan_automation\_sym_lab\f54410_topology_canonical_source6_preserve_radius_decoded_compare.json`

Current pass/fail:

- generated part count: `98`
- generated DDC records: `4085`
- count mismatches: `0`
- type mismatches: `0`
- generated exact endpoint odd parts: `0`
- `G` / `LINE` decoded max absolute diff from RADAN-direct: `5.69e-14`
- `H` / `CIRCLE` decoded max absolute diff from RADAN-direct: `5.69e-14`
- `H` / `ARC` decoded max absolute diff from RADAN-direct: `5.88e-7`

Manual RADAN/user-visible audit note, 2026-04-28:

- During the 1/8 material audit from the latest synthetic run, these symbols were confirmed bad:
  - `B-17`
  - `B-27`
  - `B-30`
  - `F54410-B-49`
- During the 1/4 material audit, these symbols were confirmed bad:
  - `B-28`
  - `F54410-B-41`
- There are likely additional failures; this list is only the confirmed audited subset so far.
- Treat these as promotion-blocking manual failures even if file-level validation and decoded comparison pass.

Inspection result:

- `B-28`, `B-30`, and `F54410-B-41` expose real `H`/`ARC` value loss from rounded/non-cardinal arc endpoint math.
- `B-17`, `B-27`, and `F54410-B-49` decode essentially identical to their templates, so their failures point at exact DDC token representation or derived/cache metadata sensitivity.
- Fresh RADAN conversion of `F54410-B-49` matched the 10:27 backup DDC exactly, and hybrid tests proved the failure follows only the DDC block.
- For existing per-part templates, preserving the known-good DDC block exactly is the only safe partial synthetic behavior found so far.
- For true no-template synthetic generation, the next blocker is a token-faithful encoder, not cache invalidation.

Rejected variant:

- `synthetic_canonical_line_source6_h_raw_full_20260427`
- reason: leaving H endpoints raw improves some arc deltas but breaks exact cross-entity closure against rounded lines

Comparison note:

- `synthetic_canonical_source6_preserve_radius_full_20260427` is the simpler non-topology variant.
- It also exact-closes all generated profile endpoints, but its worst H/ARC decoded difference is `6.68e-7`.
- topology snapping reduces the current worst H/ARC decoded difference to `5.88e-7` and fixes the `B-25 R2`/`F54410-B-46` `0.666666668` span outliers.

Next executable step:

1. Keep the production Truck Nest Explorer synthetic button disabled.
2. Use the best lab folder only in a copied project for the first RADAN open/nest validation.
3. If RADAN accepts B-14 and a small mixed line/arc set, test the full copied F54410 project.
4. If RADAN still rejects arc-heavy parts, focus on H/ARC outliers from `compare_ddc_geometry.py`.

## Progress 2026-04-28 Token-Choice Pass

Added lab analyzer:

- `analyze_radan_token_choices.py`
- output:
  `C:\Tools\radan_automation\_sym_lab\f54410_full_token_choice_analysis_20260428b.json`

Inputs:

- DXF truth:
  `W:\LASER\For Battleshield Fabrication\F54410\PAINT PACK`
- RADAN-direct oracle symbols:
  `L:\BATTLESHIELD\F-LARGE FLEET\F54410\PAINT PACK\_headless_import_backups`
- fresh RADAN oracle for the line-only canary:
  `C:\Tools\radan_automation\_sym_lab\f54410_b49_radan_known_good_20260428_105025\F54410-B-49.sym`

Full 98-part corpus result:

| Candidate | Exact records | Token slots | Token ratio |
| --- | ---: | ---: | ---: |
| `source_round6_float_full8_non_dyadic` | `754 / 4085` | `66014 / 73097` | `0.903101` |
| `source_round6_current` | `728 / 4085` | `65498 / 73097` | `0.896042` |
| `raw_current` | `602 / 4085` | `64717 / 73097` | `0.885358` |
| `source_round6_float_fixed8` | `214 / 4085` | `64124 / 73097` | `0.877245` |
| `topology_round6_float_fixed8` | `214 / 4085` | `64092 / 73097` | `0.876808` |

What improved:

- Some RADAN tokens preserve a full 8 continuation-digit shape even when the last continuation digit is `0`.
- `ddc_number_codec.encode_ddc_number_fraction(...)` now has `min_continuation_digits` so lab code can preserve this observed token shape when needed.
- This improves the full corpus from `0.896042` to `0.903101` token-slot match ratio.

What did not improve:

- `F54410-B-49` remains `0 / 28` exact geometry records and `407 / 476` token slots for the best current generative candidate.
- Its mismatches remain `49` last-character deltas plus `20` other token differences.
- Therefore the B-49 canary is not blocked by trailing-zero token length alone.

Current conclusion:

- The DDC number token shape is close to an IEEE-style binary mantissa stream, but RADAN's importer is not simply encoding Python/.NET-style `round(source, 6) - round(min, 6)` doubles.
- The same 6-decimal displayed value can map to multiple RADAN token byte strings in the oracle corpus.
- For example, the rounded value `0.025` appears with several different accepted tokens, and even dyadic-looking values such as `0.0625` can appear as both short exact tokens and long near-value tokens depending on the geometry source.
- A no-RADAN, no-template writer is therefore still blocked on reproducing RADAN's internal coordinate/value selection, not only on the compact token encoder.

Practical recommendation:

1. Do not promote synthetic SYM generation to production.
2. If a RADAN-direct `.sym` already exists for the same part, the only safe synthetic behavior found so far is to preserve its DDC geometry block exactly.
3. For new parts with no existing known-good `.sym`, continue using RADAN conversion and require visible user RADAN sessions to be closed before conversion.
4. The next research step, if this remains worth pursuing, is a tiny controlled DXF oracle corpus generated through RADAN in a closed session. That corpus should vary one coordinate at a time around values like `0.025`, `0.05`, `0.510833`, `0.512607`, `6.299218`, and `10.098437` to isolate RADAN's value-selection rule.

## Lab DXF Outside-Profile Cleaner

Added:

- `clean_dxf_outer_profile.py`
- `tests/test_clean_dxf_outer_profile.py`

Purpose:

- try a bounded pre-cleaning pass before RADAN/SYM conversion
- operate only on the selected outside profile loop
- reduce bend/flat-pattern micro-jog geometry and entity count
- write a report that quantifies exactly what changed

Safety behavior:

- input DXFs are never modified in place
- output/report paths on `W:` are refused by `path_safety.assert_w_drive_write_allowed(...)`
- output is written only when `--out` is supplied
- alternatively, pass `--project-folder <L project folder>` to write the cleaned DXF and report under `<L project folder>\_preprocessed_dxfs`
- the selected outside loop is chosen from configured profile layers by largest loop area
- v1 rewrites only LINE-only outside loops
- loops containing arcs/splines are reported and skipped until a curve-aware cleaner is implemented

B-49 lab result:

```powershell
C:\Tools\.venv\Scripts\python.exe .\clean_dxf_outer_profile.py `
  --dxf "W:\LASER\For Battleshield Fabrication\F54410\PAINT PACK\F54410-B-49.dxf" `
  --project-folder "L:\BATTLESHIELD\F-LARGE FLEET\F54410\PAINT PACK\F54410 PAINT PACK" `
  --tolerance 0.002
```

Result:

- outside loop: `28` LINE entities to `20` LINE entities
- L-side cleaned copy:
  `L:\BATTLESHIELD\F-LARGE FLEET\F54410\PAINT PACK\F54410 PAINT PACK\_preprocessed_dxfs\F54410-B-49_outer_cleaned_tol002.dxf`
- L-side report:
  `L:\BATTLESHIELD\F-LARGE FLEET\F54410\PAINT PACK\F54410 PAINT PACK\_preprocessed_dxfs\F54410-B-49_outer_cleaned_tol002.report.json`
- removed vertices: `8`
- minimum remaining line length: `0.510832849900833`
- max final vertex deviation: `0.0017680232690313101 in`
- area delta absolute: `0.0018063177606109093 sq in`
- loop remains closed with `0` odd endpoints rounded to 6 decimals

This is a promising pre-cleaning candidate for `F54410-B-49`, but it should be treated as an intentional geometry change and reviewed before use in production.

## 2026-04-28 Donor SYM Regression

The universal-donor idea failed operational validation.

Observed:

- Truck Nest Explorer temporarily allowed missing `.sym` files to be created from `C:\Tools\radan_automation\donor.sym`.
- F54410 paint-pack synthetic run made the symbols visibly wrong in RADAN.
- `B-27` passed decoded validation but was visibly bad.
- `B-27` donor-created output had the correct `181` record count/type sequence, but only `31 / 181` geometry records exactly matched the older RADAN-created backup.
- `97 / 98` current symbols had `Attr 110 = donor` after the run.

Decision:

- Do not use donor-created symbols from the Truck Nest Explorer button.
- Keep donor mode lab-only behind an explicit CLI flag.
- Synthetic import may only rebuild from existing per-part RADAN-created `.sym` templates.
- Missing symbols must be created by the normal RADAN import path first.

Recovery:

- Restored all `98` F54410 paint-pack symbols from latest `_headless_import_backups`.
- Restore manifest:
  `L:\BATTLESHIELD\F-LARGE FLEET\F54410\PAINT PACK\_headless_import_backups\restore_from_backups_20260428_125053.csv`
- Post-restore donor attribute count: `0`.
