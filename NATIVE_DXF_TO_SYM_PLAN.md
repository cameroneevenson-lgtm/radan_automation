# Native DXF to SYM Plan

Last updated: 2026-04-29

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

## Progress 2026-04-29

New lab-only writer/evaluator:

- `write_coordinate_model_sym_prototype.py`
- tests: `tests/test_write_coordinate_model_sym_prototype.py`
- run folder: `C:\Tools\radan_automation\_sym_lab\radan_import_emulator_20260429_123634`

Important correction:

- The exported-DXF hidden-coordinate model now supports `CIRCLE` records. Earlier canary output under the same run folder without the `_v2` suffix is obsolete because circle rows were left blank.

Current full-corpus results using RADAN-exported DXFs and L-side known-good SYMs:

| Mode | Exact parts | Exact records | Exact token slots | Meaning |
| --- | ---: | ---: | ---: | --- |
| strict leave-one-part-out | `20/98` | `1009/4053` | `65396/72553` (`90.135%`) | Best non-oracle predictive result so far. |
| same-part hidden-coordinate fallback | `38/98` | `2181/4053` | `69652/72553` (`96.002%`) | Shows hidden coordinates are the main missing state. |
| same-part coordinate + token spelling fallback | `48/98` | `3420/4053` | `71601/72553` (`98.688%`) | Upper bound still not perfect because repeated visible coordinates can map to different hidden RADAN coordinates. |

Canary results from `strict_v2`:

- `B-17`: `1/8` exact records, `137/152` exact slots; decoded geometry close in all slots.
- `F54410-B-49`: `0/20` exact records, `285/340` exact slots; decoded geometry close in all slots.
- `B-14`: `0/16` exact records, `226/272` exact slots; decoded geometry close in all slots.
- `B-27`: `31/181` exact records, `2649/3173` exact slots; circle handling is now fixed.
- `B-28`, `B-30`, and `F54410-B-41` still have non-close arc slots tied to repeated six-decimal visible coordinates.

New key insight:

- RADAN's DDC geometry cannot be predicted from exported six-decimal coordinates alone.
- `B-17`, `F54410-B-49`, and `B-14` have no same-part hidden-coordinate ambiguity, and the model reaches decoded-close parity for them.
- `B-28`, `B-30`, and `F54410-B-41` have repeated visible coordinate keys that map to multiple hidden RADAN fractions. Example artifact: `same_part_coordinate_ambiguity.json`.
- Therefore the next crack target is not basic DXF entity mapping. It is recovering RADAN's row/topology-specific hidden coordinate identity before token spelling.

Next useful research:

1. Build a topology-aware hidden-coordinate resolver that keys coordinates by entity index, previous/next entity, endpoint role, arc center/radius, and loop traversal, not just `(axis, six-decimal value)`.
2. Retest the same writer with that resolver against the 98-part exported-DXF corpus.
3. Only after strict exact slots improve materially should any visual RADAN check be run.

## Progress 2026-04-29, Topology Resolver Follow-Up

New run folder:

`C:\Tools\radan_automation\_sym_lab\topology_coordinate_resolver_20260429_125627`

Report:

`TOPOLOGY_COORDINATE_RESOLVER_REPORT.md`

Changes:

- Added `--coordinate-resolver context` to `write_coordinate_model_sym_prototype.py`.
- The context resolver uses entity type, point role, visible point pair, previous/next entity type, arc/circle radius, and exact row/point identity in explicit oracle mode.
- Preserved arc point precision in `ddc_corpus.py` to 15 decimals. The prior 9-decimal rounding created artificial non-close geometry on non-cardinal arcs such as `B-28`, `B-30`, and `F54410-B-41`.
- Added tests for context row-coordinate fallback and high-precision arc point preservation.

Best current results:

| Mode | Exact parts | Exact records | Exact token slots | Decoded-close slots |
| --- | ---: | ---: | ---: | ---: |
| context strict | `21/98` | `1024/4053` | `65405/72553` (`90.148%`) | `72533/72553` (`99.972%`) |
| context coordinate oracle | `51/98` | `2740/4053` | `70521/72553` (`97.199%`) | `72553/72553` |
| context coordinate + token oracle | `98/98` | `4053/4053` | `72553/72553` (`100%`) | `72553/72553` |

Interpretation:

- The native writer can reproduce all 98 known-good geometry blocks exactly when it is given row-specific hidden coordinates and same-part token spelling.
- Strict mode is now geometrically close for nearly all slots, and all seven hard canaries are decoded-close in every slot.
- Exact token spelling remains the main blocker.

Dead end:

- `--fallback-continuation type-role` and `--fallback-continuation role` both reduced exact token matches, so role-level continuation length frequency is not a safe predictor.

Next useful research:

1. Build a residual analyzer for close-but-not-exact tokens.
2. Group mismatches by mantissa-unit delta, final-character delta, role, and whether decoded values are exactly equal or merely close.
3. Test whether RADAN's final mantissa digits follow a deterministic decimal/floating parse rule rather than a role-level continuation rule.

## Progress 2026-04-29, Token Residuals

New analyzer:

- `analyze_token_residuals.py`
- tests: `tests/test_analyze_token_residuals.py`

Run artifacts:

- `C:\Tools\radan_automation\_sym_lab\topology_coordinate_resolver_20260429_125627\TOKEN_RESIDUALS_REPORT.md`
- `context_rawarc_strict_token_residuals.json`
- `context_rawarc_strict_token_residuals.csv`

Strict context/raw-arc residual summary:

- total token slots: `72553`
- exact token slots: `65405` (`90.148%`)
- mismatches: `7148`
- decoded-close within `1e-12`: `72533` (`99.972%`)

Mismatch buckets:

| Bucket | Count |
| --- | ---: |
| decoded equal but spelling differs | `50` |
| close within `1e-15` | `358` |
| close within `1e-12` | `6720` |
| far | `20` |

Key conclusions:

- `7128/7148` mismatches are decoded-close.
- `3527/7148` mismatches share the full token prefix and differ only in the final character.
- Most common mantissa-unit deltas are small: `+1`, `+2`, `-1`, `+3`, `-2`.
- The `20` far residuals are mostly radius-derived X slots in `F54410-B-01`, `F54410-B-02`, `F54410-B-19`, and `F54410-B-35`.
- `F54410-B-02` shows exported circle radius `0.101562`, while known-good DDC uses `0.1015625`, suggesting a targeted dyadic-radius snapping hypothesis.

Next useful research:

1. Test a targeted `CIRCLE` radius snap from six-decimal exported radii to nearby dyadic fractions.
2. For non-cardinal `ARC` endpoints, prefer raw center/radius/angle-derived points over corpus values keyed only by six-decimal visible coordinates.
3. Rerun residual analysis and check whether far residuals drop to zero without hurting exact-token count.

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

## 2026-04-29 RADAN Exported-DXF Oracle Pass

New controlled RADAN oracle runs used the user's RADAN-exported DXFs from:

- `L:\BATTLESHIELD\F-LARGE FLEET\F54410\PAINT PACK\Exported DXFs`

The machine was checked for RADAN/Radraft processes before and after each COM run; the lab runs ended with no RADAN processes alive.

Artifacts:

- raw exported-DXF reimport oracle:
  `C:\Tools\radan_automation\_sym_lab\far_radius_radan_oracle_20260429_132022`
- circle-radius snap RADAN oracle:
  `C:\Tools\radan_automation\_sym_lab\circle_radius_textpatch_oracle_20260429_132339`
- full exported-vs-good geometry scan:
  `C:\Tools\radan_automation\_sym_lab\exported_vs_good_geometry_scan_20260429_1328\geometry_scan.json`
- full radius-snapped exported DXF corpus:
  `C:\Tools\radan_automation\_sym_lab\exported_dxfs_circle_radius_snap_128_20260429_132615`
- best current strict synthetic run:
  `C:\Tools\radan_automation\_sym_lab\radius_snap_literal_context_writer_20260429_1330\strict`

Findings:

- RADAN reimport of unmodified exported DXFs did not exactly recreate all trusted symbols.
- `F54410-B-35` proved the export can be lossy: exported DXF circle radius `0.085938` needed to be restored to `0.0859375` (`11/128`) to recreate the trusted DDC exactly.
- `F54410-B-02` had four exported circle radii `0.101562` that needed to be restored to `0.1015625` (`13/128`). That removed the real decoded geometry error, although many tiny line token deltas remain.
- Across all 98 exported DXFs, only `F54410-B-02` and `F54410-B-35` had trusted-SYM decoded geometry differences above `1e-12`, and all were circle-radius/start-X consequences of six-decimal export.
- A literal-geometry-priority resolver fixed the remaining synthetic far misses by:
  - keeping dyadic LINE values literal,
  - keeping cardinal-arc dyadic values literal,
  - using raw computed points for non-cardinal arcs instead of borrowing rounded-key coordinates from other parts.

Best current strict synthetic result, using radius-snapped exported DXFs plus `--prefer-literal-geometry`:

- generated parts: `98 / 98`
- decoded-close slots within `1e-12`: `72553 / 72553` (`100%`)
- far decoded mismatches: `0`
- exact token slots: `65417 / 72553` (`90.164%`)
- exact geometry records: `1042 / 4053` (`25.709%`)

Oracle-mode sanity check, with same-part coordinate and token spelling allowed, still reaches:

- exact token slots: `72553 / 72553`
- exact geometry records: `4053 / 4053`
- exact parts: `98 / 98`

Current conclusion:

- We now have a no-RADAN synthetic writer that is decoded-geometry faithful across the F54410 exported-DXF corpus when the small radius-snap and literal-geometry rules are applied.
- This is a real improvement over the earlier visible-failure stage, but it still does not crack RADAN's exact token spelling/cache behavior: about `9.8%` of token slots differ while decoding to the same or near-identical geometry.
- Promotion recommendation remains `do not promote`; the next useful validation is opening/nesting a copied lab project with these strict outputs to see whether decoded-geometry fidelity is enough operationally.

## 2026-04-29 Symbol Origin / D-Record Cache Pass

User-observed RADAN behavior:

- every symbol has an inherent origin point
- deleting it in RADAN and saving causes RADAN to recreate it
- the practical origin appears to be the lower-left corner of the symbol bounding box

Corpus inspection:

- all 98 RADAN-exported F54410 DXFs have modelspace geometry normalized to `min_x = 0`, `min_y = 0`
- all DDC G/H geometry records already match that lower-left-origin model: coordinates are stored relative to DXF bounding-box min X/Y
- the non-geometry `E` record payload is constant across the 98-part corpus:
  `o?0...o?0.........o?0.o?0.$/`
- the non-geometry `D` record contains a symbol view/cache rectangle plus unit scale, not cut geometry
- the `25.4` token in D is the inch-to-mm scale marker

Observed D-record decoded shape:

```text
D,-1,6,.<view_x>..<view_y>..<view_x>..<view_y>.<25.4>.<1>.<1>.$<part>
```

The decoded `view_x/view_y` rule across the 98 fresh RADAN symbols is:

```text
base_x = 99.318474
base_y = 70.228767
scale = max(1, 3 * bbox_x / base_x, 3 * bbox_y / base_y)
view_x = base_x * scale
view_y = base_y * scale
```

This is a padded landscape view rectangle with roughly A-series / sqrt(2) aspect ratio. It is separate from attrs `165` and `166`, which remain the actual part bounding-box X/Y in inches.

Code update:

- `write_native_sym_prototype.py` now rebuilds the D-record view/cache field from DXF bounds when writing lab native prototypes
- it also refreshes XML attrs:
  - `110` File name
  - `165` Bounding box X
  - `166` Bounding box Y
- tests now cover the observed D-record padding rule and metadata refresh behavior

Implication:

- stale donor metadata was a real lab risk: a donor-created symbol could carry another part's D-record view extents and filename/bounding-box attrs even when G/H decoded geometry validated
- this does not solve exact RADAN geometry token spelling, but it removes one derived-cache/source-of-truth mismatch from lab prototypes
- production recommendation remains `do not promote synthetic SYM generation`

## 2026-04-29 RADAN Save Canonicalization Probe

Purpose:

- use RADAN proper as a microscope, not as a production repair flow
- open/save decoded-correct strict synthetic symbols and compare RADAN's saved result to the fresh RADAN oracle

Artifact:

`C:\Tools\radan_automation\_sym_lab\radan_save_canonicalization_20260429_1400\RADAN_SAVE_CANONICALIZATION_REPORT.md`

Run:

- input strict synthetic folder:
  `C:\Tools\radan_automation\_sym_lab\radius_snap_literal_context_writer_20260429_1330\strict`
- copied lab save folder:
  `C:\Tools\radan_automation\_sym_lab\radan_save_canonicalization_20260429_1400\syms`
- opened/saved all `98` copied symbols through one hidden RADAN instance
- RADAN PID `21268`
- elapsed `22.786s`
- errors `0`
- final RADAN process check clean

Aggregate result vs fresh RADAN oracle:

| Metric | Before save | After save |
| --- | ---: | ---: |
| token match ratio | `0.902030` | `0.909471` |
| exact geometry record ratio | `0.260054` | `0.511675` |
| exact token slots | `65445 / 72553` | `64336 / 70739` |

Interpretation:

- RADAN save performs a real canonicalization pass and often moves synthetic DDC closer to RADAN's own spelling.
- It is not safe as a repair shortcut: 20 parts had after-save decoded row-pair differences greater than `1.0` inch against the fresh RADAN oracle.
- Some of that may be row deletion/reordering or RADAN geometry repair, but operationally it confirms decoded geometry validation alone is not sufficient.

Notable improvements:

- `B-14`: `0.830882 -> 0.977941` token ratio
- `F54410-B-49`: `0.838235 -> 0.952941`
- `B-17`: `0.894737 -> 0.986842`

Notable failures/worsening:

- `B-27`: after-save max decoded row-pair diff `54.409952`
- `F54410-B-12`: `58.1875`
- `F54410-B-27`: `63.5`
- `F54410-B-10`: `68.994306`
- `F54410-B-01`: `70.160859`

Conclusion:

- use RADAN save canonicalization as a reverse-engineering oracle only
- do not promote it or synthetic SYM generation into production
- next research target is to compare before/after-save token deltas for the improved symbols (`B-14`, `B-17`, `F54410-B-49`) against the symbols that RADAN repaired destructively (`B-27`, `F54410-B-12`)

## 2026-04-29 L-Side Save Canonicalization Analysis

Added:

- `analyze_radan_save_canonicalization.py`
- tests: `tests/test_analyze_radan_save_canonicalization.py`

Purpose:

- compare the RADAN-saved synthetic symbols against the real L-side F54410 known-good symbols, not only the fresh LAB oracle
- classify whether RADAN save acted as harmless token canonicalization or as destructive geometry repair
- separate pen/material noise from actual DDC geometry changes

Artifacts:

- report:
  `C:\Tools\radan_automation\_sym_lab\radan_save_canonicalization_20260429_1400\l_side_good_analysis\RADAN_SAVE_CANONICALIZATION_ANALYSIS.md`
- JSON:
  `C:\Tools\radan_automation\_sym_lab\radan_save_canonicalization_20260429_1400\l_side_good_analysis\radan_save_canonicalization_analysis.json`
- CSV:
  `C:\Tools\radan_automation\_sym_lab\radan_save_canonicalization_20260429_1400\l_side_good_analysis\radan_save_canonicalization_analysis.csv`
- token residuals before save:
  `C:\Tools\radan_automation\_sym_lab\radan_save_canonicalization_20260429_1400\l_side_good_analysis\before_save_token_residuals.json`
- token residuals after save, excluding row-count-changed parts:
  `C:\Tools\radan_automation\_sym_lab\radan_save_canonicalization_20260429_1400\l_side_good_analysis\after_save_token_residuals_count_matched.json`

Classification result against L-side known-good symbols:

| Classification | Count |
| --- | ---: |
| `exact_after_save` | `46` |
| `canonicalized_closer` | `29` |
| `decoded_close_no_token_change` | `2` |
| `decoded_close_but_token_worse` | `1` |
| `destructive_radan_repair_row_count_changed` | `20` |

Aggregate:

| Metric | Before RADAN save | After RADAN save |
| --- | ---: | ---: |
| exact token ratio | `0.901644` | `0.906559` |
| exact geometry-data ratio | `0.257094` | `0.470051` |
| exact token slots | `65417 / 72553` | `64130 / 70740` |

Token residuals:

- before save, all `98` parts were decoded-close, with `7136` token mismatches and `0` far decoded mismatches
- after save, among the `78` count-matched parts:
  - exact token rate: `0.981687`
  - mismatches: `599`
  - far decoded mismatches: `0`
  - top remaining mismatch roles: `LINE:start_x`, `LINE:delta_x`, `ARC:start_x`, `LINE:start_y`

Good canaries:

- `B-14`: token ratio `0.830882 -> 0.977941`, exact records `0 -> 12`
- `B-17`: `0.894737 -> 0.986842`, exact records `1 -> 7`
- `F54410-B-49`: `0.838235 -> 0.952941`, exact records `0 -> 9`

Destructive row-count-changing canaries:

- `B-27`: records `181 -> 170`, token ratio `0.834857 -> 0.781271`
- `F54410-B-12`: records `194 -> 184`, token ratio `0.833631 -> 0.788798`
- `F54410-B-27`: records `61 -> 56`, token ratio `0.968559 -> 0.806066`

Aggregate destructive row churn:

- missing from known-good after save: `751` G records and `79` H records
- extra after save: `659` G records and `58` H records

Conclusion:

- RADAN save is a very strong token-canonicalization oracle for the `78` count-matched parts
- RADAN save is still disqualified as a production repair step because `20` symbols are rebuilt into different row counts
- next useful cracking work is to mine the `599` remaining after-save token residuals and infer the final RADAN token spelling rule for the non-destructive group

## 2026-04-29 Lab RADAN-Save Token Model Pass

Added:

- `radan_save_token_model.py`
- tests: `tests/test_radan_save_token_model.py`
- lab-only writer flags in `write_coordinate_model_sym_prototype.py`:
  - `--radan-save-token-model-mode off`
  - `--radan-save-token-model-mode fallback-context-unanimous`
  - `--radan-save-token-model-mode fallback-token-majority`
  - `--radan-save-token-model-mode fallback-shorter-majority`

Purpose:

- turn the `before synthetic -> after RADAN save -> L-side good` evidence into an explicit offline token-spelling model
- keep the model lab-only and opt-in
- exclude same-part observations during prediction so the run measures generalization instead of memorizing the answer
- only train from the `78` non-destructive/count-matched after-save symbols
- keep the `20` row-count-changing symbols quarantined as RADAN repair/destructive cases

Artifact:

`C:\Tools\radan_automation\_sym_lab\radan_save_token_model_writer_20260429_141849`

Input folders:

- DXF input:
  `C:\Tools\radan_automation\_sym_lab\exported_dxfs_circle_radius_snap_128_20260429_132615\dxfs`
- before-save synthetic symbols:
  `C:\Tools\radan_automation\_sym_lab\radius_snap_literal_context_writer_20260429_1330\strict`
- after-save RADAN symbols:
  `C:\Tools\radan_automation\_sym_lab\radan_save_canonicalization_20260429_1400\syms`
- L-side known-good oracle:
  `L:\BATTLESHIELD\F-LARGE FLEET\F54410\PAINT PACK`

Model summary:

- eligible count-matched training parts: `78`
- quarantined/skipped row-count-changing parts: `20`
- learned before/save/oracle correction observations: `1284`

Full-corpus writer results against L-side known-good symbols:

| Mode | Exact token slots | Exact token ratio | Exact geometry records | Canonicalized slots | Far decoded mismatches |
| --- | ---: | ---: | ---: | ---: | ---: |
| baseline strict | `65417 / 72553` | `0.901644` | `1042 / 4053` | `0` | `0` |
| `fallback-shorter-majority` | `65440 / 72553` | `0.901961` | `1042 / 4053` | `23` | `0` |
| `fallback-context-unanimous` | `65471 / 72553` | `0.902389` | `1037 / 4053` | `120` | `0` |
| `fallback-token-majority` | `65484 / 72553` | `0.902568` | `1047 / 4053` | `282` | `0` |

Cross-validation read:

- `fallback-token-majority` gives the largest net token gain but also applies wrong canonicalizations:
  `130` helps, `63` hurts, and `89` changed-but-still-wrong coordinate-slot substitutions in the inspected coordinate slots
- `fallback-context-unanimous` is less noisy but still not safe:
  `73` helps, `19` hurts, and `28` changed-but-still-wrong coordinate-slot substitutions
- `fallback-shorter-majority` is intentionally conservative:
  `23` observed coordinate-slot helps with no observed hurt/wrong substitutions in this corpus

Conclusion:

- this is a useful offline harness, not a breakthrough
- the learned save-token model proves RADAN has transferable spelling preferences, but the current keys are still too coarse for production
- the safest learned rule is currently "only adopt a RADAN-save spelling when it shortens a fallback-generated token"; it improves exact token count only slightly
- promotion recommendation remains `do not promote synthetic SYM generation`
- next useful work is a stronger local context model around row neighborhoods and exact source fractions, especially for the count-matched canaries `B-14`, `B-17`, and `F54410-B-49`

## 2026-04-29 RADAN Save Start-State / Transplant Probes

Purpose:

- use RADAN proper in copied lab folders only
- test whether RADAN open/save output is deterministic from decoded geometry/metadata, or whether the starting DDC token spelling changes the saved result
- isolate why some decoded-close synthetic symbols are destructively repaired on save while L-side known-good copies are not

Artifacts:

- run folder:
  `C:\Tools\radan_automation\_sym_lab\radan_save_start_state_probe_20260429_142457`
- start-state report:
  `RADAN_SAVE_START_STATE_PROBE.md`
- chunk transplant report:
  `RADAN_TOKEN_TRANSPLANT_PROBE.md`
- fine window report:
  `RADAN_TRANSPLANT_WINDOW_PROBE.md`
- single-token report:
  `RADAN_SINGLE_TOKEN_TRANSPLANT_PROBE.md`
- trigger row details:
  `trigger_row_token_details.json`

RADAN/process notes:

- all experiment inputs and outputs were copied lab files under `_sym_lab`
- no `W:` writes
- production L-side `.sym` files were read-only oracles
- RADAN was launched headlessly for copied symbols and cleaned up after each probe
- a process-filter false positive was observed: Microsoft Edge can match a naive `RADAN` window-title scan when the browser title contains `radan_automation`; future process cleanup should prefer actual process names (`RADRAFT`, `Radnest`, `Radpunch`, etc.) or exclude browser titles

Start-state result:

- copied L-side known-good controls save back exact against L-side good for the tested canaries
- synthetic starts do not all converge to one saved output; the initial DDC spelling can affect the saved result
- for `B-14`, `B-17`, and `F54410-B-49`, baseline/shorter/context synthetic starts saved to the same DDC geometry, while known-good saved exact and `token_majority` could preserve worse residuals
- for destructive canaries, L-side good copies remained exact, but synthetic starts were rebuilt:
  - `B-27`: `181 -> 170` geometry records
  - `F54410-B-12`: `194 -> 184` geometry records before the dyadic-delta fix below

Chunk transplant result:

- starting from the L-side good symbol, replacing selected DDC geometry rows with baseline synthetic geometry rows can trigger RADAN repair
- this points at geometry token spelling/value representation, not broad XML metadata, as a repair trigger

`B-27`:

- synthetic ARC rows alone were safe: `181 / 181`
- synthetic LINE rows alone triggered repair: `181 -> 170`
- individual synthetic rows that trigger repair by themselves:
  - row `22`
  - row `24`
  - row `29`
  - row `45`
  - row `82`
  - row `134`
- single-token transplant proved the exact trigger slots:
  - rows `22`, `24`, `29`, `45`, `82`: slot `0` / `LINE:start_x`
  - row `134`: slot `2` / `LINE:delta_x`
- the common row `22/24/29/45/82` shape is a fallback token that decodes equal but is shorter than RADAN's good token, e.g. good `...0` vs synthetic trimmed `...`

`F54410-B-12`:

- synthetic ARC rows alone triggered repair: `194 -> 192`
- synthetic LINE rows alone triggered repair: `194 -> 186`
- individual `H` row `18` triggered repair by itself
- single-token transplant proved row `18` slot `3` / `ARC:delta_y` was sufficient:
  - good token: `m?P`
  - synthetic token: `l?_ooooool`
  - both decode near `-0.25`, but RADAN treats the synthetic approximate spelling as a repair trigger
- line-window repair still exists in ranges:
  - rows `16-20`
  - `21-25`
  - `56-60`
  - `71-75`
  - `81-85`
  - `146-150`
  - `151-155`
  - `166-170`

Code update:

- `write_coordinate_model_sym_prototype.py`
  - when `--prefer-literal-geometry` is active, cardinal-endpoint ARC deltas that are visibly dyadic are now kept as exact dyadic fractions
  - this is intentionally restricted to cardinal ARC endpoints; applying it to non-cardinal arcs caused decoded misses in `B-185`, `B-186`, `F54410-B-01`, `F54410-B-05`, `F54410-B-10`, `F54410-B-14`, and `F54410-B-21`
- `tests/test_write_coordinate_model_sym_prototype.py`
  - added coverage for preserving exact dyadic cardinal-arc deltas

Full-corpus result after the cardinal-arc dyadic-delta fix:

- output folder:
  `C:\Tools\radan_automation\_sym_lab\dyadic_cardinal_delta_writer_20260429_1500\strict`
- generated parts: `98 / 98`
- decoded-close slots within `1e-12`: `72553 / 72553`
- far decoded mismatches: `0`
- exact token slots: `65515 / 72553` (`90.300%`)
- exact geometry records: `1054 / 4053` (`26.005%`)
- improvement over previous strict baseline:
  - `+98` exact token slots
  - `+12` exact geometry records

Patched RADAN save check:

- `B-27` still repairs destructively: `181 -> 170`
- `F54410-B-12` improves but still repairs destructively: `194 -> 186`
- this confirms the row `18` arc fix removes one concrete repair trigger, but B-12 still has additional cumulative line-window triggers and B-27 still needs a fallback-token spelling rule

Current cracking hypothesis:

- RADAN's repair gate is sensitive to exact compact-number spelling, not only decoded geometry
- some one-token differences that decode equal or within `1e-14` can mark a profile as repairable/destructive
- cardinal-arc dyadic deltas must be represented as compact exact dyadics when possible
- LINE fallback tokens may need a non-trimmed continuation rule in specific contexts, but broad continuation padding (`role` / `type-role`) is too noisy and reduced exact-token performance

Next useful experiment:

- build a targeted fallback continuation model for `LINE:start_x` and `LINE:delta_x` that predicts when RADAN wants a trailing `0`/longer continuation without broadly padding every fallback token
- validate it first on the known single-token B-27 repair triggers, then on full-corpus exact-token ratio and RADAN save repair count

### 2026-04-29 Targeted LINE Fallback Zero Experiment

Added lab-only writer mode:

```powershell
C:\Tools\.venv\Scripts\python.exe .\write_coordinate_model_sym_prototype.py `
  --dxf-folder "C:\Tools\radan_automation\_sym_lab\exported_dxfs_circle_radius_snap_128_20260429_132615\dxfs" `
  --sym-folder "L:\BATTLESHIELD\F-LARGE FLEET\F54410\PAINT PACK" `
  --out-dir "C:\Tools\radan_automation\_sym_lab\line_repair_zero_low_digit_writer_20260429_145710\strict" `
  --coordinate-resolver context `
  --prefer-literal-geometry `
  --fallback-continuation line-repair-zero
```

Rule:

- only applies to fallback-generated `LINE:start_x` and `LINE:delta_x` tokens
- only when the generated token length is `10`, does not already end in `0`, and appending `0` decodes within `1e-12` of the original token
- special `LINE:delta_x` sub-rule: if the final base-64 continuation digit is `1..9`, try replacing that final digit with `00` first; this is the shape needed by B-27 row `134`
- source tag: `encoded_fraction_fallback:line-repair-zero:0->line_repair_zero_append0`
- low-digit source tag: `encoded_fraction_fallback:line-repair-zero:0->line_repair_zero_low_digit_last00`

Full-corpus result:

- generated parts: `98 / 98`
- decoded-close slots within `1e-12`: `72553 / 72553`
- far decoded mismatches: `0`
- exact token slots: `65546 / 72553` (`90.342%`)
- exact geometry records: `1057 / 4053` (`26.079%`)
- improvement over dyadic-cardinal baseline: `+31` exact token slots, `+3` exact geometry records

Targeted canary movement:

- `B-27` exact token slots improved `2649 -> 2655`
- all six known B-27 single-token repair trigger slots now match the L-side oracle exactly:
  - rows `22`, `24`, `29`, `45`, and `82`, slot `0` / `LINE:start_x`
  - row `134`, slot `2` / `LINE:delta_x`, now emits `k?^3\M38100`
- `B-28` gained one exact fallback slot
- `B-30` gained six exact fallback slots
- `F54410-B-12` gained one exact fallback slot
- `F54410-B-49` did not improve; it remains `0 / 20` exact geometry records, so this specific rule does not explain the B-49 token/cache issue

Interpretation:

- this is real evidence that some destructive RADAN repair triggers are caused by trimmed fallback compact-number spellings
- it is not a broad solution; unrestricted zero-padding or last-digit-zero transforms hurt exact-token performance heavily
- next validation requires RADAN proper: save the new `line_repair_zero` B-27 and F54410-B-12 prototypes in a copied lab context and compare row counts against the previous `181 -> 170` / `194 -> 186` repair behavior

### 2026-04-29 RADAN-Validated Repair-Token Expansion

RADAN became available and the `line-repair-zero` mode was expanded in two more narrow steps:

- `LINE:start_y`: append one trailing `0` for length-10 fallback tokens when decoded-close
- `LINE:delta_y`: round down final continuation digit to an 8-boundary plus `0`, or carry the final digit into a `00` suffix for the observed high-tail case
- `ARC:start_x`: append one trailing `0` for length-10 fallback tokens when decoded-close

Key exact-name RADAN probes:

- B-12 filename lesson:
  - exact filename `F54410-B-12.sym` repaired `194 -> 190`
  - suffixed filename `F54410-B-12__same_bytes.sym` failed/opened unreliably and could produce false no-repair results
  - future RADAN save probes must put each variant in its own folder while preserving the real `.sym` filename
- B-12 remaining trigger rows after B-27 rules:
  - row `25`, slot `3`, `LINE:delta_y`: `l??Yd\`9\`ll -> l??Yd\`9\`lh0`
  - row `82`, slot `3`, `LINE:delta_y`: `i?ZoZ?OKKU -> i?ZoZ?OKL00`
  - row `154`, slot `1`, `LINE:start_y`: `3@23FP>1U< -> 3@23FP>1U<0`
- Small destructive parts:
  - `B-28` row `10`, slot `0`, `ARC:start_x`: `o?4M\5M;@7 -> o?4M\5M;@70`
  - `F54410-B-40` row `4`, slot `0`, `ARC:start_x`: `5@0e^Un<BX -> 5@0e^Un<BX0`

Best current strict writer run:

```powershell
C:\Tools\.venv\Scripts\python.exe .\write_coordinate_model_sym_prototype.py `
  --dxf-folder "C:\Tools\radan_automation\_sym_lab\exported_dxfs_circle_radius_snap_128_20260429_132615\dxfs" `
  --sym-folder "L:\BATTLESHIELD\F-LARGE FLEET\F54410\PAINT PACK" `
  --out-dir "C:\Tools\radan_automation\_sym_lab\line_repair_zero_arc_start_writer_20260429_151909\strict" `
  --coordinate-resolver context `
  --prefer-literal-geometry `
  --fallback-continuation line-repair-zero
```

Pre-save corpus result:

- exact token slots: `65581 / 72553` (`90.390%`)
- exact geometry records: `1063 / 4053` (`26.227%`)
- decoded-close slots within `1e-12`: `72553 / 72553`
- far decoded mismatches: `0`

Full 98-part RADAN open/save validation:

- run folder:
  `C:\Tools\radan_automation\_sym_lab\radan_save_validate_line_repair_zero_arc_start_full98_20260429_151926`
- COM save failures: `0 / 98`
- RADAN `Quit()` result: `true`
- destructive row-count repairs: `0 / 98`
- geometry-changed-after-save classifications: `0 / 98`
- classifications:
  - `exact_after_save`: `53`
  - `canonicalized_closer`: `42`
  - `decoded_close_no_token_change`: `2` (`B-49`, `B-50`)
  - `decoded_close_but_token_worse`: `1` (`B-193`)
- after-save exact token slots: `70953 / 72553` (`97.795%`)
- after-save exact geometry records: `2919 / 4053` (`72.021%`)

This is the first full F54410 corpus where RADAN save did not destructively repair any synthetic symbol. It is still lab-only: the writer output is not token-exact before save, and promotion still requires visual inspection plus copied-project nesting/report validation.
