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

### 2026-04-29 Copied-Project Synthetic Gate

Ran the first copied-project gate using the RADAN-saved synthetic corpus, not the raw pre-save writer output.

Lab project setup:

- run folder:
  `C:\Tools\radan_automation\_sym_lab\copied_project_gate_20260429_153330`
- copied source RPD:
  `L:\BATTLESHIELD\F-LARGE FLEET\F54410\PAINT PACK\F54410 PAINT PACK\F54410 PAINT PACK.rpd`
- copied lab RPD:
  `C:\Tools\radan_automation\_sym_lab\copied_project_gate_20260429_153330\F54410 PAINT PACK.synthetic_gate.rpd`
- copied synthetic symbols:
  `C:\Tools\radan_automation\_sym_lab\copied_project_gate_20260429_153330\symbols_after_radan_save`
- symbol paths rewritten in the copied RPD: `98 / 98`
- production files were read-only inputs; no W: writes and no production RPD/SYM writes.

Doctor result:

- `ok=True`
- `fail_count=0`
- `warn_count=1`
- expected warning: all `98` lab symbols already existed in the copied RPD, so repeat import skipped row creation

Headless copied-project import/refresh result:

- checked `98 / 98` reused symbols for feature-pen remap; no pen-7 line/arc records needed remapping
- skipped `98 / 98` existing copied-project part rows
- opened copied RPD through a fresh hidden RADAN automation instance
- ran the same `UpdateSheetsList` handler used by the Nest Editor button
- RADAN `Quit()` result: `true`
- post-write validation passed:
  - expected symbols: `98`
  - project part rows: `98`
  - sheet rows: `8`
  - `NextID`: `1294`
- timing: conversion `0.0s`, project `1.1s`, total `2.0s`

Canary visual thumbnail comparison:

- rendered RADAN flat thumbnails for these lab synthetic symbols and matching L-side known-good symbols:
  - `B-14`
  - `B-17`
  - `B-27`
  - `B-30`
  - `F54410-B-49`
  - `F54410-B-12`
  - `F54410-B-27`
- all `7 / 7` synthetic thumbnails rendered successfully
- all `7 / 7` known-good thumbnails rendered successfully
- all `7 / 7` pairs were pixel-identical at `900x700`
- diff summary:
  `C:\Tools\radan_automation\_sym_lab\copied_project_gate_20260429_153330\canary_thumbnail_diff_summary.json`

Interpretation:

- the current RADAN-saved synthetic corpus passes file-level validation, RADAN save validation, copied-project membership validation, sheet-refresh validation, and automated canary thumbnail parity
- this is materially stronger than the previous raw synthetic attempts, where several canaries visibly failed or were destructively repaired
- it is still not promoted: the remaining gate is an actual copied-project nest/report validation and user visual review inside RADAN
- at this checkpoint, no proven headless nester path was wired yet; the follow-up nester gate below resolves that for `Mac.lay_run_nest(0)` but not for the managed `Application.RunNester()` surface

### 2026-04-29 Headless Copied-Project Nester Gate

Ran lab-only copied-project nester probes under:

`C:\Tools\radan_automation\_sym_lab\nester_probe_20260429_154029`

This used the RADAN-saved synthetic symbol corpus from:

`C:\Tools\radan_automation\_sym_lab\radan_save_validate_line_repair_zero_arc_start_full98_20260429_151926\after_radan_save`

Production files were read-only inputs. No W: writes and no production RPD/SYM writes.

Important API findings:

- `Application.RunNester()` appears in the interop dump, but was not exposed on the current automation COM object; a direct call raised `AttributeError: Radraft.Application.RunNester`.
- `Mac.nst_add_part(...)` / `Mac.nst_add_sheet(...)` returned success-like values, but did not populate the top-level nest project rows needed by `lay_run_nest(0)`.
- the working headless path is the nest project API:
  - open a copied `.rpd`
  - add rows with `Mac.prj_clear_part_data`, `PRJ_PART_*`, and `Mac.prj_add_part()`
  - refresh sheet rows with `Mac.prg_notify('rpr_sheets_controls', 'UpdateSheetsList')`
  - run `Mac.lay_run_nest(0)`
  - save and quit the automation-owned RADAN instance

Small proof:

- first `10` parts added by `prj_add_part`
- before sheet refresh: `10` parts, `0` sheets
- after `UpdateSheetsList`: `10` parts, `5` sheets
- `lay_run_nest(0)` returned `0` in `3.248s`
- generated `4` `.drg` nest drawings

Full-corpus blocker isolation:

- full `98` with all known sheet definitions added manually returned `11006` with `0` nest drawings
- ten-part batch isolation found the failing range was rows `61-70`
- single-part isolation identified three blockers:
  - `F54410-B-09`
  - `F54410-B-11`
  - `F54410-B-17`
- each of those three also failed as a single part with the L-side known-good RADAN symbol, returning `11039`
- therefore those failures are not synthetic-symbol failures
- all three are `Aluminum 5052`, `0.18 in`, quantity `1`; sheet refresh covered all BOM material/thickness groups

Full copied-project synthetic nester proof with blockers excluded:

- excluded `F54410-B-09`, `F54410-B-11`, and `F54410-B-17`
- added `95` parts through `prj_add_part`
- called `UpdateSheetsList`
- sheet rows after refresh: `8`
- `lay_run_nest(0)` returned `0` in `56.024s`
- generated `28` `.drg` nest drawings
- after nest:
  - part rows: `95`
  - sheet rows: `8`
  - nest rows: `42`
  - made nonzero count: `431`
  - `NextNestNum`: `43`
- no visible RADAN accept/confirm dialog was detected during the run
- `Application.Quit()` returned `true`; no RADAN/Radraft process remained afterward

Interpretation:

- the RADAN-saved synthetic corpus is now proven nestable headlessly in a copied project for `95 / 98` F54410 parts
- the remaining three blockers reproduce with known-good RADAN-created symbols, so they should be investigated as nester/setup/geometry-fit cases rather than native SYM encoding failures
- the likely production-shaped headless nester path is `prj_add_part` + `UpdateSheetsList` + `lay_run_nest(0)`, with explicit process ownership checks and copied-project validation gates
- promotion is still not automatic: we need user visual review and a report/packet validation pass before using this beyond lab/copied-project contexts

### 2026-04-29 Overnight Raw Synthetic Nester Gate

Fresh overnight run folder:

`C:\Tools\radan_automation\_sym_lab\overnight_crack_and_nest_validate_20260429_174834`

New reusable harness:

- `copied_project_nester_gate.py`
- tests: `tests/test_copied_project_nester_gate.py`
- validation: `C:\Tools\.venv\Scripts\python.exe -m unittest discover -v`
- result: `162` tests / `OK`

Harness behavior:

- copies a source `.rpd` into `_sym_lab`
- clears copied project part and sheet rows but preserves existing nest numbering/history
- adds selected rows through `Mac.prj_clear_part_data`, `PRJ_PART_*`, and `Mac.prj_add_part()`
- refreshes sheets with `prg_notify('rpr_sheets_controls', 'UpdateSheetsList')`
- runs `Mac.lay_run_nest(0)`
- saves, closes, quits the automation-owned RADAN process, then logs final process cleanup
- refuses lab outputs outside `_sym_lab`

RADAN-saved synthetic validation ladder:

| Rung | Parts | Sheets | Nests | Made nonzero | DRGs | Result |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `B-10` | `1` | `1` | `15` | `4` | `1` | pass |
| `F54410-B-49` | `1` | `2` | `15` | `4` | `1` | pass |
| `B-14`, `B-17`, `F54410-B-49` | `3` | `5` | `16` | `12` | `2` | pass |
| seven hard canaries | `7` | `5` | `16` | `28` | `2` | pass |
| arc/circle stress set | `6` | `6` | `17` | `24` | `3` | pass |
| first 10 | `10` | `5` | `18` | `43` | `4` | pass |
| first 25 | `25` | `8` | `23` | `115` | `9` | pass |
| first 49 | `49` | `8` | `27` | `232` | `13` | pass |
| 95-part subset excluding oversized blockers | `95` | `8` | `42` | `431` | `28` | pass |

Raw pre-save synthetic validation ladder:

| Rung | Parts | Sheets | Nests | Made nonzero | DRGs | Result |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `B-10` | `1` | `1` | `15` | `4` | `1` | pass |
| `F54410-B-49` | `1` | `2` | `15` | `4` | `1` | pass |
| seven hard canaries | `7` | `5` | `16` | `28` | `2` | pass |
| first 25 | `25` | `8` | `23` | `115` | `9` | pass |
| first 49 | `49` | `8` | `27` | `232` | `13` | pass |
| 95-part subset excluding oversized blockers | `95` | `8` | `42` | `431` | `28` | pass |

Interpretation:

- Raw pre-save synthetic symbols are practically nestable in the copied F54410 project for the same `95 / 98` subset as the RADAN-saved synthetic symbols.
- This does not crack exact DDC token spelling, but it materially changes the risk model: token-exact mismatch and prior RADAN-save canonicalization deltas are not automatically nester blockers.
- The next format-cracking target should compare raw-vs-saved-vs-known-good at the DRG/nest-output level, not only at the SYM token level, to identify which token/cache deltas are operationally irrelevant.
- Report generation through `prj_output_report` / `stp_output_report` remained blocked in this headless Nest Project context with `Wrong mode for DevExpress reports`.

Raw-vs-RADAN-saved nest artifact comparison:

- analyzer: `compare_nest_artifacts.py`
- report: `_sym_lab\overnight_crack_and_nest_validate_20260429_174834\RAW_VS_RADAN_SAVED_NEST_ARTIFACTS.md`
- RPD used-nest semantics matched exactly between raw pre-save synthetic and RADAN-saved synthetic outputs
- DRG count matched: `28 / 28`
- contained symbol summaries matched: `28 / 28`
- full DRG hash matches: `0 / 28`
- normalized DRG hash matches after path/job-label/timestamp normalization: `0 / 28`
- DDC line comparison across paired DRGs:
  - same lines: `3980`
  - changed lines: `292`
  - `F -> F`: `55`
  - `I -> I`: `125`
  - `N -> N`: `112`
- DDC change classification:
  - `F layout entity token payload`: `55`
  - `I layout annotation token payload`: `69`
  - `I report date text`: `28`
  - `I report drawing-name text`: `28`
  - `N numeric cache/timestamp`: `112`

Interpretation:

- RADAN's nesting plan and part counts are insensitive to the raw-vs-saved token spelling deltas for this `95 / 98` corpus.
- The raw-vs-saved deltas still propagate into generated DRG DDC payloads, mainly as same-prefix `F`, `I`, and `N` token changes rather than row insertion/deletion or changed nest membership.
- The upgraded delta classifier localizes all `N` differences as numeric cache/timestamp rows and all report-name/date differences as report text rows; the remaining crack-relevant nest DRG payloads are the `F` layout entity and `I` layout annotation token classes.
- This supports treating exact token spelling as a display/report/canonicalization research target, while copied-project nesting is already accepting the raw writer's current token spelling.

Known-good L-side full95 nester oracle:

- gate folder: `_sym_lab\overnight_crack_and_nest_validate_20260429_174834\nester_full95_known_good`
- symbol folder: `L:\BATTLESHIELD\F-LARGE FLEET\F54410\PAINT PACK`
- subset: `95 / 98`, excluding oversized `F54410-B-09`, `F54410-B-11`, `F54410-B-17`
- `lay_run_nest(0)` returned `0` in `60.933 s`
- project rows after nest:
  - parts: `95`
  - sheets: `8`
  - nests: `42`
  - made/nonzero count: `431`
  - `NextNestNum`: `43`
  - DRG files: `28`
- RADAN process cleanup proof: final RADAN-family process list was empty
- report attempt stayed blocked with `Wrong mode for DevExpress reports`

Raw-vs-known-good nest artifact comparison:

- analyzer: `compare_nest_artifacts.py`
- report: `_sym_lab\overnight_crack_and_nest_validate_20260429_174834\RAW_VS_KNOWN_GOOD_NEST_ARTIFACTS.md`
- RPD used-nest semantics matched exactly between raw pre-save synthetic and L-side known-good outputs
- DRG count matched: `28 / 28`
- contained symbol summaries matched: `28 / 28`
- full DRG hash matches: `0 / 28`
- normalized DRG hash matches after path/job-label/timestamp normalization: `0 / 28`
- DDC line comparison across paired DRGs:
  - same lines: `3965`
  - changed lines: `307`
  - `F -> F`: `61`
  - `I -> I`: `134`
  - `N -> N`: `112`
- DDC change classification:
  - `F layout entity token payload`: `61`
  - `I layout annotation token payload`: `78`
  - `I report date text`: `28`
  - `I report drawing-name text`: `28`
  - `N numeric cache/timestamp`: `112`

Interpretation:

- Raw pre-save synthetic symbols now reproduce the same copied-project nesting membership, part counts, sheet counts, nest counts, made counts, and contained-symbol layout semantics as the L-side known-good symbols for the accepted `95 / 98` corpus.
- The remaining DRG differences are same-prefix compact-token/cache/report-text payload differences, not evidence of missing parts, changed DRG counts, changed used-nest semantics, or nester rejection.
- Against the L-side known-good output, `168 / 307` DRG DDC deltas are volatile/report classes (`N` cache/timestamp plus report date/name text), leaving `139` same-prefix layout token payload deltas to keep mining.
- This upgrades raw native generation from "decoded-close but visually risky" to "RADAN-open, thumbnail-identical on canaries, and nester-accepted against known-good operational state" for this copied-project corpus.

Nest layout token delta analysis:

- analyzer: `analyze_nest_layout_token_deltas.py`
- raw vs RADAN-saved report: `_sym_lab\overnight_crack_and_nest_validate_20260429_174834\RAW_VS_RADAN_SAVED_LAYOUT_TOKEN_DELTAS.md`
- raw vs known-good report: `_sym_lab\overnight_crack_and_nest_validate_20260429_174834\RAW_VS_KNOWN_GOOD_LAYOUT_TOKEN_DELTAS.md`

| Comparison | Layout changed rows | Layout token mismatches | Decoded bucket | Same-prefix except last char |
| --- | ---: | ---: | --- | ---: |
| raw pre-save synthetic vs RADAN-saved synthetic | `124` | `489` | `489 close_1e-12` | `486` |
| raw pre-save synthetic vs L-side known-good | `139` | `543` | `543 close_1e-12` | `537` |

Interpretation:

- The remaining crack-relevant DRG layout payload differences are not far decoded coordinate/layout differences.
- For the L-side known-good comparison, every `F` layout entity token mismatch (`73 / 73`) and every `I` layout annotation token mismatch (`470 / 470`) decodes close within `1e-12`.
- Most remaining mismatches are the familiar final-continuation-character spelling deltas, typically mantissa delta units of `+/-1` or `+/-2`.
- This strongly supports the current raw writer's practical acceptance while narrowing exact-token cracking to deterministic final continuation/canonical spelling rules rather than geometry semantics.

Accepted-subset token residual benchmark:

- analyzer: `analyze_token_residuals.py`
- summary tool: `summarize_token_residual_runs.py`
- summary report: `_sym_lab\overnight_crack_and_nest_validate_20260429_174834\TOKEN_RESIDUAL_ACCEPTED95_SUMMARY.md`
- subset: `95 / 98`, excluding oversized `F54410-B-09`, `F54410-B-11`, `F54410-B-17`
- total compared compact-token slots per run: `69451`

| Comparison | Exact token slots | Exact token rate | Mismatches | Close mismatches | Far mismatches | Same-prefix last-char-ish |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| raw pre-save synthetic vs known-good | `62761` | `0.903673` | `6690` | `6690` | `0` | `3421` |
| RADAN-saved synthetic vs known-good | `67931` | `0.978114` | `1520` | `1520` | `0` | `630` |
| raw pre-save synthetic vs RADAN-saved synthetic | `62963` | `0.906582` | `6488` | `6488` | `0` | `3473` |

Interpretation:

- RADAN save canonicalization strongly improves exact token spelling versus the known-good L-side symbols.
- The raw writer's current residuals are all decoded-close within the analyzer tolerance for the accepted `95 / 98` subset; none are far decoded.
- Raw-vs-saved residuals are also all decoded-close, reinforcing that RADAN save mostly changes compact spelling/canonicalization, not the decoded geometry RADAN's nester uses for this corpus.
- The largest residual groups remain line `start_x`, `start_y`, `delta_x`, and `delta_y`, so any next token-spelling rule should be judged against practical acceptance, not decoded geometry alone.

Raw pre-save thumbnail parity:

- harness: `run_thumbnail_parity_gate.py`
- report: `_sym_lab\overnight_crack_and_nest_validate_20260429_174834\thumbnail_parity_raw_canaries\thumbnail_parity_result.json`
- candidate folder: `_sym_lab\radan_save_validate_line_repair_zero_arc_start_full98_20260429_151926\before`
- oracle folder: `L:\BATTLESHIELD\F-LARGE FLEET\F54410\PAINT PACK`
- mode: read-only symbol opens, no symbol saves
- parts:
  - `B-14`
  - `B-17`
  - `B-27`
  - `B-30`
  - `F54410-B-49`
  - `F54410-B-12`
  - `F54410-B-27`
- result: `7 / 7` exact pixel matches at `900 x 700`
- all per-render RADAN `process_final` lists were empty

Interpretation:

- The current raw pre-save synthetic symbols now pass the same hard-canary thumbnail parity that previously required RADAN-saved synthetic symbols.
- Together with the `95 / 98` nester pass, this is the strongest current evidence that normal RADAN conversion/save may not be required for practical F54410 copied-project acceptance, even though exact token spelling is still not cracked.

Known-good blocker fit check:

| Part | DXF size | Biggest matching sheet | Fit result |
| --- | --- | --- | --- |
| `F54410-B-09` | `215.000 x 47.000 in` | `120.0 x 60.0 in` | oversized |
| `F54410-B-11` | `60.813 x 101.754 in` | `120.0 x 60.0 in` | oversized |
| `F54410-B-17` | `65.754 x 60.813 in` | `120.0 x 60.0 in` | oversized |

Those three should remain excluded from synthetic-SYM pass/fail classification unless a larger matching sheet setup is intentionally added to the copied project.

### 2026-04-29 Overnight Token-Majority Canonicalization Probe

Token-spelling experiment outputs:

- context unanimous:
  `_sym_lab\overnight_crack_and_nest_validate_20260429_174834\writer_radan_save_context_unanimous`
- token majority:
  `_sym_lab\overnight_crack_and_nest_validate_20260429_174834\writer_radan_save_token_majority`
- shorter majority:
  `_sym_lab\overnight_crack_and_nest_validate_20260429_174834\writer_radan_save_shorter_majority`

Accepted95 residual results versus L-side known-good symbols:

| Candidate | Exact token slots | Exact token rate | Mismatches | Far mismatches |
| --- | ---: | ---: | ---: | ---: |
| raw pre-save baseline | `62761 / 69451` | `0.903673` | `6690` | `0` |
| context unanimous | `63235 / 69451` | `0.910498` | `6216` | `0` |
| token majority | `63560 / 69451` | `0.915178` | `5891` | `0` |
| shorter majority | `62763 / 69451` | `0.903702` | `6688` | `0` |
| RADAN-saved synthetic | `67931 / 69451` | `0.978114` | `1520` | `0` |

Token-majority validation:

- single `B-10` nester gate passed
- single `F54410-B-49` nester gate passed
- seven hard-canary nester gate passed
- seven hard-canary thumbnail parity passed with `7 / 7` exact pixel matches at `900 x 700`
- full95 copied-project nester gate passed:
  - part rows: `95`
  - sheet rows: `8`
  - nest rows: `42`
  - made/nonzero count: `431`
  - `NextNestNum`: `43`
  - DRG files: `28`
  - `lay_run_nest(0)`: `0`
  - elapsed: `56.454 s`
  - final RADAN-family process list: empty
- report generation stayed blocked with `Wrong mode for DevExpress reports`

Operational regression:

- token-majority full95 did not preserve raw/known-good used-nest membership
- `compare_nest_artifacts.py` now reports exact RPD used-nest membership deltas, not just the boolean mismatch
- the mismatch is localized to two nests with identical sheet signatures:
  - nest `27`: token-majority has `B-3 R1 x1`; raw/known-good has `B-5 R1 x1`
  - nest `28`: token-majority has `B-5 R1 x1`; raw/known-good has `B-3 R1 x1`
- the directly swapped symbol files `B-3 R1.sym` and `B-5 R1.sym` were byte-identical between the raw and token-majority symbol folders, so the layout change is likely caused by other nearby token changes or nester tie-breaking sensitivity, not mutation of those two symbol files

Repeat check:

- a second full95 token-majority nester run was created at:
  `_sym_lab\overnight_crack_and_nest_validate_20260429_174834\nester_full95_token_majority_repeat1`
- repeat metrics matched the first token-majority count envelope:
  - part rows: `95`
  - sheet rows: `8`
  - nest rows: `42`
  - made/nonzero count: `431`
  - DRG files: `28`
  - `lay_run_nest(0)`: `0`
  - elapsed: `56.549 s`
  - final RADAN-family process list: empty
- repeat versus original token-majority:
  - `rpd_used_nests_match=True`
  - contained-symbol summaries matched `28 / 28`
- repeat versus raw:
  - `rpd_used_nests_match=False`
  - contained-symbol summaries matched `26 / 28`
  - the same `B-3 R1` / `B-5 R1` swap occurred in nests `27` and `28`
- this makes random nester tie-breaking a weaker explanation than a stable layout perturbation caused by the token-majority symbol corpus

Interpretation:

- token-majority is RADAN-acceptable: it displays correctly on hard canaries and nests the full accepted corpus
- token-majority is not currently a better operational candidate than raw pre-save output because it perturbs the copied-project nest plan even while improving offline exact token rate
- raw pre-save remains the best operational benchmark tonight because it matches L-side known-good used-nest semantics for the accepted `95 / 98` subset
- future token-spelling rules should be gated by both exact token improvement and preservation of raw/known-good nester semantics

### 2026-04-29 Context-Unanimous Token Probe

Context-unanimous was the less aggressive RADAN-save token model:

- accepted95 exact token rate: `0.910498`
- exact token slots: `63235 / 69451`
- mismatches: `6216`
- far mismatches: `0`

Validation ladder:

| Rung | Parts | Sheets | Made/nonzero | DRGs | Result |
| --- | ---: | ---: | ---: | ---: | --- |
| `B-10` | `1` | `1` | `4` | `1` | pass |
| `F54410-B-49` | `1` | `2` | `4` | `1` | pass |
| seven hard canaries | `7` | `5` | `28` | `2` | pass |
| first25 | `25` | `8` | `115` | `9` | pass |
| full95 excluding oversized blockers | `95` | `8` | `431` | `28` | pass |

Full95 metrics:

- `lay_run_nest(0)`: `0`
- elapsed: `56.625 s`
- nest rows: `42`
- `NextNestNum`: `43`
- final RADAN-family process list: empty
- report generation stayed blocked with `Wrong mode for DevExpress reports`

Operational regression:

- context-unanimous still did not preserve raw/known-good used-nest membership
- context-unanimous versus raw:
  - `rpd_used_nests_match=False`
  - contained-symbol summaries matched `26 / 28`
  - the same `B-3 R1` / `B-5 R1` swap appeared in nests `27` and `28`
- context-unanimous versus known-good showed the same two-nest swap

B-194 isolation:

- among the symbols referenced by the affected nests, context-unanimous differs from raw only in `B-194.sym`
- `B-194` context-unanimous versus raw has only `3` token differences, all decoded-close:
  - row `10`, `LINE:delta_y`: context `2@7iVIVIVIP`, raw `2@7iVIVIVIT`
  - row `23`, `CIRCLE:center_delta_x`: context ``j?W2Se`Xm00``, raw ``j?W2Se`XmL:``
  - row `24`, `CIRCLE:center_delta_x`: context ``j?W2Se`Xm00``, raw ``j?W2Se`XmL:``
- raw `B-194.sym` alone nests successfully
- a lab hybrid using context-unanimous symbols except raw `B-194.sym` fails aggregate gates:
  - first20: `lay_run_nest(0)=11088`, `0` DRGs
  - first21: `lay_run_nest(0)=11088`, `0` DRGs
  - first25: `lay_run_nest(0)=11088`, `0` DRGs
  - first49: `lay_run_nest(0)=11088`, `0` DRGs
  - full95: `lay_run_nest(0)=11088`, `0` DRGs
- unmodified context-unanimous first20, first21, first25, and full95 all pass

Interpretation:

- context-unanimous is RADAN-accepted, but it is not layout-neutral
- the three `B-194` token choices are likely coupled to aggregate nester behavior under the context-unanimous corpus
- mixing token-spelling regimes can be worse than either consistent regime: raw full95 passes, context-unanimous full95 passes, but context-unanimous with raw `B-194` fails
- next token rules should avoid per-part transplant assumptions and should validate consistency at the corpus/subset level, not just per-symbol display or decoded-close geometry

### 2026-04-29 Minimal B-194 Token Restore Probe

Built three lab variants from the failing context-unanimous plus raw-`B-194` hybrid:

- row10 context only:
  `_sym_lab\overnight_crack_and_nest_validate_20260429_174834\writer_context_unanimous_B194_row10_context_only`
- circle-pair context only:
  `_sym_lab\overnight_crack_and_nest_validate_20260429_174834\writer_context_unanimous_B194_circle_pair_context_only`
- all three context tokens restored:
  `_sym_lab\overnight_crack_and_nest_validate_20260429_174834\writer_context_unanimous_B194_all3_context_restored`

First25 result:

- raw `B-194` hybrid: `lay_run_nest(0)=11088`, `0` DRGs
- row10 context only: pass, `9` DRGs, made/nonzero `115`
- circle-pair context only: pass, `9` DRGs, made/nonzero `115`
- all three restored: pass, `9` DRGs, made/nonzero `115`

Full95 result:

| Candidate | Exact token rate | Mismatches | Full95 nester | Used-nest match vs raw | Contained symbols vs raw | Thumbnail canaries |
| --- | ---: | ---: | --- | --- | --- | --- |
| raw pre-save baseline | `0.903673` | `6690` | pass | yes | `28 / 28` | `7 / 7` |
| context-unanimous | `0.910498` | `6216` | pass | no, swaps nests `27`/`28` | `26 / 28` | not rerun |
| B-194 row10 context only | `0.910469` | `6218` | pass | yes | `28 / 28` | not rerun |
| B-194 circle-pair context only | `0.910484` | `6217` | pass | yes | `28 / 28` | `7 / 7`, plus `B-194` exact |

Circle-pair DRG layout deltas:

- versus raw pre-save:
  - layout changed rows: `17`
  - layout token mismatches: `79`
  - decoded buckets: `79 close_1e-12`
- versus L-side known-good:
  - layout changed rows: `142`
  - layout token mismatches: `541`
  - decoded buckets: `541 close_1e-12`

Repeat stability check:

- long-label repeat:
  `_sym_lab\overnight_crack_and_nest_validate_20260429_174834\nester_full95_B194_circle_pair_context_only_repeat1`
  - project path length: `203`
  - `lay_run_nest(0)=11088`
  - `0` DRGs
  - after sheet refresh/nest attempt: `95` parts, `8` sheets, `14` nest rows, `0` made/nonzero
  - no lingering RADAN-family processes
- short-label repeat:
  `_sym_lab\overnight_crack_and_nest_validate_20260429_174834\nester_cp_b194_repeat2`
  - project path length: `145`
  - `lay_run_nest(0)=0`
  - `28` DRGs, `42` nest rows, `431` made/nonzero
  - `rpd_used_nests_match=True` versus both raw synthetic and the first circle-pair full95 run
  - no lingering RADAN-family processes
- interpretation:
  - the failed repeat is a path/label-length sensitivity suspect, not current evidence that the circle-pair token candidate is semantically unstable
  - use short labels/output paths for future copied-project nester gates and treat long-path failures near this envelope as harness evidence to isolate before token conclusions
- harness follow-up:
  - `copied_project_nester_gate.py` now records copied-project path lengths in `result.json`
  - it logs a warning when the copied project path reaches `200` characters, so long-path nester failures are not misclassified as token evidence

Raw-corpus B-194 all-three isolation:

- variant:
  `_sym_lab\overnight_crack_and_nest_validate_20260429_174834\writer_raw_B194_all3_context_only`
- construction:
  - copied the raw pre-save corpus from `_sym_lab\radan_save_validate_line_repair_zero_arc_start_full98_20260429_151926\before`
  - replaced only `B-194.sym` with the all-three context-token B-194 variant
  - verified `98` `.sym` files and exactly one hash difference versus raw: `B-194.sym`
- full95 nester:
  `_sym_lab\overnight_crack_and_nest_validate_20260429_174834\nester_raw_b194_all3`
  - `lay_run_nest(0)=0`
  - `95` parts, `8` sheets, `42` nest rows, `431` made/nonzero
  - `28` DRGs
  - `path_lengths.project_path_length=141`, `project_path_warning=False`
  - report attempts still blocked with `Wrong mode for DevExpress reports`
  - no lingering RADAN-family processes
- comparison:
  - versus raw synthetic: `rpd_used_nests_match=True`, `0` RPD used-nest differences
  - versus context-unanimous: `rpd_used_nests_match=False`, same nest `27`/`28` `B-3 R1` / `B-5 R1` swap
- token residuals versus L-side known-good:
  - exact tokens: `62764 / 69451`
  - exact rate: `0.903716`
  - mismatches: `6687`
  - far mismatches: `0`
- interpretation:
  - the three B-194 context tokens are not sufficient by themselves to perturb raw nester semantics
  - the context-unanimous swap needs broader corpus spelling context plus the all-three B-194 spelling state
  - this points away from a simple per-symbol token rule and toward corpus-level or neighboring-part layout sensitivity in the nester oracle

Interpretation:

- restoring either the row10 `LINE:delta_y` context token or the two row23/24 `CIRCLE:center_delta_x` context tokens is enough to recover first25/full95 nester acceptance from the raw-`B-194` hybrid
- both minimal variants preserve the raw full95 used-nest semantics, unlike full context-unanimous
- the circle-pair variant is the best current improved-token lab candidate:
  - exact token rate improves over raw by about `0.006811`
  - all accepted95 mismatches remain decoded-close
  - full95 copied-project nester semantics match raw and L-side known-good
  - hard-canary thumbnails are pixel-identical to L-side known-good
- this still is not a production promotion candidate; it is evidence that final token spelling rules can improve while preserving practical RADAN behavior, but they need corpus-level nester guards

### 2026-04-29 B-194 Partner Split Probe

To isolate the broader context needed for the context-unanimous `B-3 R1` / `B-5 R1`
nest swap, built raw-corpus variants with `B-194.sym` carrying all three
context-unanimous tokens plus progressively smaller sets of other
context-unanimous symbols.

All runs used the full `95`-part copied-project nester gate with
`F54410-B-09`, `F54410-B-11`, and `F54410-B-17` excluded as oversized known-good
blockers.

| Variant | Context symbols beyond raw | `lay_run_nest(0)` | DRGs | Used-nest match vs raw | Difference |
| --- | --- | ---: | ---: | --- | --- |
| A | `B-194` + `B-14`, `B-185`, `B-186`, `B-193`, `B-25 R2`, `B-31`, `F54410-B-01`, `F54410-B-02`, `F54410-B-05`, `F54410-B-07`, `F54410-B-08`, `F54410-B-10`, `F54410-B-12`, `F54410-B-13` | `0` | `28` | no | nests `27`/`28` swap `B-3 R1` and `B-5 R1` |
| A1 | `B-194` + `B-14`, `B-185`, `B-186`, `B-193`, `B-25 R2`, `B-31`, `F54410-B-01` | `0` | `28` | no | same nests `27`/`28` swap |
| A1a | `B-194` + `B-14`, `B-185`, `B-186` | `0` | `28` | no | same nests `27`/`28` swap |
| single B-14 | `B-194` + `B-14` | `0` | `28` | no | same nests `27`/`28` swap |
| single B-185 | `B-194` + `B-185` | `0` | `28` | no | same nests `27`/`28` swap |
| single B-186 | `B-194` + `B-186` | `0` | `28` | no | same nests `27`/`28` swap |

Every listed variant preserved the envelope:

- `95` project parts
- `8` sheet rows
- `42` nest rows
- `431` made/nonzero count
- `28` generated DRGs
- final RADAN-family process list empty
- report attempts still blocked with `Wrong mode for DevExpress reports`

Raw-to-context token deltas for the three single trigger partners are small and
decoded-close:

- `B-14`: four `LINE:delta_y` spellings, all about `6.66e-16` decoded delta
- `B-185`: nine arc token spellings on rows `11` and `13`, all about
  `1.1e-14` or smaller decoded delta
- `B-186`: four arc token spellings on rows `22` and `24`, all about
  `7.1e-15` or smaller decoded delta

Interpretation:

- the all-three `B-194` context-token state is harmless by itself in the raw
  corpus, but it becomes layout-perturbing when paired with at least one of
  several other small decoded-close token spelling changes
- the trigger is not unique to `B-14`; `B-185` and `B-186` also produce the same
  stable used-nest swap
- exact-token improvement rules need a nester semantic guard, because small
  decoded-close token changes in unrelated symbols can alter aggregate layout
  ordering without changing parser, thumbnail, part-count, sheet-count, made, or
  DRG-count gates

Single-symbol and one-token follow-up:

| Variant | Context tokens beyond raw | Used-nest match vs raw | Difference |
| --- | --- | --- | --- |
| `B-14` only | four `LINE:delta_y` tokens | yes | none |
| `B-185` only | nine arc tokens | no | nests `27`/`28` swap `B-3 R1` and `B-5 R1` |
| `B-186` only | four arc tokens | no | same nests `27`/`28` swap |
| `B-186` slot2 pair | row `22` and row `24` `ARC:delta_x` tokens only | no | same nests `27`/`28` swap |
| `B-186` non-slot2 pair | row `24` `ARC:delta_y` and `center_delta_x` tokens only | yes | none |
| `B-186` row22 slot2 | one row `22` `ARC:delta_x` token only | no | same nests `27`/`28` swap |
| `B-186` row24 slot2 | one row `24` `ARC:delta_x` token only | no | same nests `27`/`28` swap |

The one-token trigger is:

- part: `B-186`
- role: `ARC:delta_x`
- raw token: `4@7Tollog\K`
- context token: `4@7Tollog\L`
- decoded delta: about `7.1e-15`

Interpretation update:

- `B-14` is neutral alone but becomes layout-perturbing when paired with
  `B-194` all-three context tokens
- `B-185` and `B-186` do not require `B-194`; each can perturb the full95 nest
  assignment from decoded-close arc token spelling alone
- in `B-186`, either of two individual `ARC:delta_x` final-character choices is
  sufficient, while the neighboring decoded-close `ARC:delta_y` /
  `center_delta_x` pair is neutral
- this is strong evidence that RADAN-acceptable token spelling is not merely
  about decoded geometry or per-symbol thumbnail parity; aggregate nester
  behavior can be sensitive to exact compact-token spellings below practical
  geometry tolerance

B-185 common-token follow-up:

| Variant | Context tokens beyond raw | Used-nest match vs raw | Difference |
| --- | --- | --- | --- |
| `B-185` row11 slot2 | one row `11` `ARC:delta_x` token only | no | nests `27`/`28` swap `B-3 R1` and `B-5 R1` |
| `B-185` row13 slot2 | one row `13` `ARC:delta_x` token only | yes | none |

Both selected B-185 rows use the same raw/context token text
(`4@7Tollog\K` -> `4@7Tollog\L`), but only row `11` perturbs the full95 nest.
That rules out a purely global token-string effect. Entity row context, local
geometry, or downstream cached placement state also matters.

### 2026-04-29 B-185/B-186 Known-Good Geometry Interaction

The B-185/B-186 follow-up separated token spelling from wrapper/cache metadata:

- `B-185` known-good alone in the raw corpus passed the full95 count envelope
  but reproduced the nests `27`/`28` `B-3 R1` / `B-5 R1` swap.
- `B-186` known-good alone did the same.
- `B-185` + `B-186` known-good together restored raw used-nest semantics.
- `B-185` + `B-186` context-only still swapped.
- mixed pairs (`B-185` known-good + `B-186` context, and `B-185` context +
  `B-186` known-good) both still swapped.

`sym_section_diff.py` localized the B-185/B-186 differences to G/H geometry
token spelling only. Wrapper, history, attributes, and non-geometry DDC lines
matched between raw/context/known-good symbols. The cancellation is therefore a
geometry-token interaction, not hidden metadata/cache repair.

B-186 residual split with `B-185` known-good:

| B-186 state | Used-nest match vs raw | Notes |
| --- | --- | --- |
| context-only | no | same nests `27`/`28` swap |
| context + 18 known-good `start_y` residuals | no | count envelope passed |
| context + `start_y` + 3 known-good `delta_y` residuals | no | count envelope passed |
| context + only row 24 `center_delta_y` residual | no | center token is not sufficient alone |
| full known-good residual set with DDC raw text preserved | yes | B-186 byte-identical to known-good; raw used-nest semantics restored |

B-185 residual split with `B-186` known-good:

| B-185 state | Used-nest match vs raw | Notes |
| --- | --- | --- |
| context-only | no | same nests `27`/`28` swap |
| context + row 1 circle pair | yes | row 1 pair restores raw membership |
| context + rows 5/6 `start_x` | no | rows 5/6 are not sufficient |
| context + row 1 `start_x` | no | long start token is not sufficient |
| context + row 1 `center_delta_x` | yes | single token `k?P` -> `k?P000000P0` restores raw membership |

Tooling note:

- `build_sym_token_patch_variant.py` now builds lab-only token-patched corpus
  variants and records an exact patch manifest.
- The patcher preserves the final newline inside the DDC CDATA block. An initial
  pre-fix patch stripped that newline and produced a confounded nester result,
  so exact DDC text preservation is now part of the token-transplant harness.

Interpretation:

- local exact-token improvement remains unsafe without corpus-level nester
  validation
- some token effects are additive/interacting across independent parts
- raw synthetic remains the simpler operational benchmark, while targeted
  exact-token variants need a semantic guard before they are considered better

### 2026-04-29 B-185 Circle Center-Delta Context Mining

`analyze_symbol_token_context.py` now records generated-vs-oracle token spelling
with local DXF row context. The first use focused on the B-185 row `1`
`CIRCLE:center_delta_x` cancellation token:

- generated/raw token: `k?P`
- known-good token: `k?P000000P0`
- decoded absolute delta: about `2.842e-14`
- role/value cohort: `138` `CIRCLE:center_delta_x` rows with visible value
  `-0.062500000000000`
- oracle spelling split in that cohort: `137` keep `k?P`; only B-185 row `1`
  uses `k?P000000P0`
- four other first-geometry circle rows in the same visible-value cohort keep
  `k?P`

This disproves a simple radius, dyadic value, or first-geometry-row rule for
that long continuation spelling. The spelling choice may depend on more subtle
source float provenance, local geometry ordering, original RADAN conversion
state, or downstream nester/cache behavior. Do not teach the writer to emit
`k?P000000P0` for all `-1/16` circle center-delta-X slots from this evidence
alone.

Follow-up one-token nester isolation:

| Variant | Token change beyond raw | Used-nest match vs raw | Difference |
| --- | --- | --- | --- |
| `B-185` row1 `CIRCLE:center_delta_x` | `k?P` -> `k?P000000P0` | no | nests `27`/`28` swap `B-3 R1` and `B-5 R1` |

The same token that cancels the `B-186` known-good perturbation also perturbs
raw on its own. The full95 gate still passed the count envelope (`95` parts,
`8` sheets, `42` nest rows, `431` made/nonzero, `28` DRGs), but the semantic
comparison failed exactly like the other one-token triggers. This reinforces
that exact-token deltas can interact and cancel; a token spelling that is
locally closer to known-good is not automatically a better corpus state.

### 2026-04-29 ARC Delta-X Trigger Cohort

The context analyzer was extended to include line/arc/circle geometry context:
normalized start/end/center, visible deltas, center deltas, radius, and arc
angles. Raw-vs-context-unanimous mining for `ARC:delta_x` found six identical
`4@7Tollog\K` -> `4@7Tollog\L` rows at visible delta
`47.156226753946804`.

One-token full95 nester outcomes for that exact token/value cohort:

| Part row | Geometry | Used-nest match vs raw | Difference |
| --- | --- | --- | --- |
| `B-185` row `11` | `180.0` -> `323.198444`, `delta_y=-15.6874999464` | no | nests `27`/`28` swap |
| `B-185` row `13` | `216.801556` -> `0.0`, `delta_y=+15.6874999464` | yes | none |
| `B-186` row `22` | `180.0` -> `323.198444`, `delta_y=-15.6874999464` | no | nests `27`/`28` swap |
| `B-186` row `24` | `216.801556` -> `0.0`, `delta_y=+15.6874999464` | no | nests `27`/`28` swap |
| `F54410-B-21` row `12` | `180.0` -> `323.198444`, `delta_y=-15.6874999464` | no | nests `27`/`28` swap |
| `F54410-B-21` row `14` | `216.801556` -> `0.0`, `delta_y=+15.6874999464` | no | nests `27`/`28` swap |

The B-185 row `13` neutral result is now the exception, not the rule. B-185
row `13` and F54410-B-21 row `14` have matching visible arc geometry, but only
F54410-B-21 row `14` perturbs the full95 nest. That rules out token text,
visible delta, local LINE/ARC/LINE context, and visible arc geometry as complete
explanations. The remaining signal is likely deeper row/corpus context, source
float provenance, hidden per-symbol conversion state, or aggregate nester
ordering sensitivity.

### 2026-04-29 DDC Field-3 Identifier Is Nester-Visible

`build_sym_token_patch_variant.py` now also supports lab-only DDC field patches
via `--field-patch PART:ROW:FIELD:VALUE`, preserving DDC CDATA framing. This
was added to test whether the geometry-row identifier field participates in the
same nester sensitivity.

Identifier-control experiments:

| Variant | DDC field change | Geometry-token change | Used-nest match vs raw | Difference |
| --- | --- | --- | --- | --- |
| `B-185` row13 slot2 + row13/14 ID swap | row13 `?` -> `@`, row14 `@` -> `?` | row13 `4@7Tollog\K` -> `4@7Tollog\L` | no | nests `27`/`28` swap |
| `F54410-B-21` row14 slot2 + row13/14 ID swap | row13 `?` -> `@`, row14 `@` -> `?` | row14 `4@7Tollog\K` -> `4@7Tollog\L` | no | nests `27`/`28` swap |
| `B-185` row13/14 ID swap only | row13 `?` -> `@`, row14 `@` -> `?` | none | no | nests `27`/`28` swap |
| `F54410-B-21` row13/14 ID swap only | row13 `?` -> `@`, row14 `@` -> `?` | none | no | nests `27`/`28` swap |

All four passed the full95 count envelope (`lay_run_nest(0)=0`, `28` DRGs,
`95` parts, `8` sheets, `42` nest rows, `431` made/nonzero) and cleaned up
RADAN processes. The identifier-only controls are the important result: DDC
field index `3` is nester-visible even when decoded geometry and geometry
tokens are unchanged.

Treat field `3` as part of the native crack target. It may be a feature/row ID,
topology ordering key, cache correlation key, or tie-break input. It is not safe
to regenerate or reorder it casually, and future hybrid/token experiments must
preserve it unless the hypothesis explicitly targets field `3`.

Follow-up corpus analyzer result: `analyze_ddc_identifier_fields.py` confirms
that the current known-good, raw synthetic, RADAN-saved synthetic, and
context-unanimous corpora all have `4053/4053` sequential identifiers and `0`
field-3/record mismatches versus known-good. The normal identifier sequence is
the geometry row index plus `2` (`row13` -> `?`, `row14` -> `@`). Therefore the
field-3 nester failures above are deliberate perturbation evidence, not an
accidental field-3 drift in the current writer candidates.

### 2026-04-29 DXF Source Text Does Not Explain ARC Delta-X Split

`analyze_dxf_entity_provenance.py` compares raw DXF group-code rows alongside
the normalized geometry view. For the most informative neutral/trigger split,
`B-185` row `13` and `F54410-B-21` row `14`, the raw ARC entity group sequence
is byte-identical:

- layer `0`
- center `10=84.500000`, `20=31.688690`
- radius `40=26.187500`
- angles `50=216.801556`, `51=0.000000`

The matching trigger pair `B-185` row `11` and `F54410-B-21` row `12` is also
byte-identical at the raw ARC entity level. Therefore the `B-185` row `13`
neutral exception is not explained by source DXF decimal spelling, source DXF
numeric values, local ARC group-code text, visible geometry, token text, or
local LINE/ARC/LINE shape. The remaining likely causes are global row/topology
context, row identity/cache participation, interaction with other token
spellings, or downstream nester ordering sensitivity.

`analyze_symbol_token_context.py` now records broader topology context including
entity count, row-from-end, same-type ordinal, prefix LINE/ARC/CIRCLE counts,
two-row neighbor signatures, full type signatures, and bounds. In the
`4@7Tollog\K` -> `4@7Tollog\L` cohort, `B-185` row `13` and
`F54410-B-21` row `14` share the same local ARC text and row-from-end (`7`),
but differ in prefix circle count (`9` vs `10`) and type signature
(`CCCCCCCCCLALALLLLLL` vs `CCCCCCCCCCLALALLLLLL`).

Follow-up pair interactions:

| Variant | Single-row priors | Used-nest match vs raw | Difference |
| --- | --- | --- | --- |
| `B-185` rows `11`+`13` slot `2` | row `11` triggers, row `13` neutral | no | nests `27`/`28` swap |
| `B-186` rows `22`+`24` slot `2` | both rows trigger | no | nests `27`/`28` swap |
| `F54410-B-21` rows `12`+`14` slot `2` | both rows trigger | yes | no crack-relevant DRG layout deltas |

The `F54410-B-21` pair is especially useful: each constituent token triggers
alone, but together they cancel back to raw used-nest semantics. This disproves
a simple additive one-token trigger model and reinforces that token spelling
choices participate in part/global ordering state.

Combination follow-up: raw plus the individually neutral `B-194` circle-pair
tokens and the individually neutral `F54410-B-21` row `12`+`14` pair did not
compose. The combined candidate still passed the full95 count envelope, but
reproduced the nests `27`/`28` swap. Exact token rate versus known-good improved
only slightly over raw (`0.9039598638236875`, far mismatches `0`) and is not an
operational improvement.

Adding the nine highest-count broader context parts to that combined candidate
still swapped. Adding the lower-count complement parts still swapped. The
previous broader `B194_circle_pair_context_only` candidate, which includes the
full context set, still matches raw used-nest semantics. Therefore cancellation
requires cross-group token interactions; neither high-count nor low-count
context groups are sufficient alone.

Further split narrowed a smaller passing candidate. With the raw+B194/F21 base,
`top9 + lowB` restores raw semantics, while `top9 + lowA` does not. Splitting
`lowB` showed `top9 + lowB2` restores raw semantics and `top9 + lowB1` does
not. Pair probes inside `lowB2` all failed, but leave-one-out showed:

| Variant | Used-nest match vs raw |
| --- | --- |
| top9 + `F54410-B-32` + `F54410-B-19` + `F54410-B-18` (no `F54410-B-15`) | no |
| top9 + `F54410-B-15` + `F54410-B-19` + `F54410-B-18` (no `F54410-B-32`) | no |
| top9 + `F54410-B-15` + `F54410-B-32` + `F54410-B-18` (no `F54410-B-19`) | yes |
| top9 + `F54410-B-15` + `F54410-B-32` + `F54410-B-19` (no `F54410-B-18`) | yes |

The current smaller passing candidate is raw + `B-194` circle-pair +
`F54410-B-21` pair + top9 + `F54410-B-15` + `F54410-B-32` +
`F54410-B-18`. It passed full95 copied-project nesting with raw used-nest
semantics, `28` DRGs, `431` made/nonzero, no final RADAN processes, and hard
canary thumbnails `7/7` exact. Token exact rate versus known-good is
`0.9099830468760768` (`66022/72553`, far mismatches `0`). The top9 side remains
unminimized.

Top9 minimization found a smaller sufficient subset. With the `F54410-B-15` +
`F54410-B-32` + `F54410-B-18` support set, topA failed and topB passed. TopB
halves failed individually. Leave-one-out on topB showed `F54410-B-13` is
optional, while `F54410-B-16`, `F54410-B-02`, and `F54410-B-12` are
load-bearing. Replacing `F54410-B-18` with `F54410-B-19` after this reduction
failed, so the current smallest passing candidate is raw + `B-194` circle-pair
+ `F54410-B-21` pair + `F54410-B-15` + `F54410-B-32` + `F54410-B-18` +
`F54410-B-16` + `F54410-B-02` + `F54410-B-12`. It preserves raw full95
used-nest semantics, passes hard-canary thumbnails `7/7`, and has known-good
token exact rate `0.9055173459402093` (`65698/72553`, far mismatches `0`).

Reduced-set minimization pushed that smaller again. Direct leave-one-out showed
`F54410-B-02` is optional in the six-part reduced candidate; the no-`F54410-B-02`
variant preserved raw used-nest semantics, had token exact rate
`0.9049798078645955` (`65659/72553`, far `0`), had `0` crack-relevant DRG
layout-token deltas versus raw, and passed hard-canary thumbnails `7/7`.

Leave-one-out on the five-part state showed `F54410-B-15` and `F54410-B-16`
are required, while `F54410-B-32`, `F54410-B-18`, and `F54410-B-12` are each
optional one-at-a-time. Three-part addback probes found two passing stabilizers:
raw + `B-194` circle-pair + `F54410-B-21` pair + `F54410-B-15` +
`F54410-B-16` + `F54410-B-32`, and the same base plus `F54410-B-12` instead of
`F54410-B-32`. The `F54410-B-12` version is the current smallest passing
reduced candidate: full95 copied-project nesting matches raw used-nest
semantics, `28` DRGs, `431` made/nonzero, `0` crack-relevant layout-token deltas
versus raw, token exact rate `0.9049660248370157` (`65658/72553`, far `0`), and
hard-canary thumbnail parity `7/7`. The `F54410-B-32` sibling also matches raw
semantics but has a slightly lower exact rate (`65624/72553`,
`0.9044974018993012`). The two-part `F54410-B-15`+`F54410-B-16` variant and
the `F54410-B-18` addback both reproduce the nests `27`/`28` `B-3 R1` /
`B-5 R1` swap.

This is not yet a writer rule. It is strong lab evidence that small, nonlocal
token-spelling sets can cancel nester-visible ordering perturbations without
changing decoded geometry or final DRG layout payloads.

F12 role splitting narrowed the current reduced branch further. Relative to
the raw+B194/F21 base, the three-part stabilizer has `137` decoded-close token
differences: one `F54410-B-15` `delta_x`, `70` `F54410-B-16` `delta_x/delta_y`
tokens, and `66` `F54410-B-12` `delta_x/delta_y` tokens. On top of the failing
`F54410-B-15`+`F54410-B-16` base, F12 `delta_x`-only still swaps B-3/B-5, but
F12 `delta_y`-only restores raw full95 used-nest semantics with `28` DRGs,
`431` made/nonzero, `0` crack-relevant layout-token deltas, token exact rate
`0.9047592794233181` (`65643/72553`, far `0`).

The `29` F12 `delta_y` rows were split into early (`43`, `58`, `59`, `73`,
`76`, `77`, `79`, `80`, `83`, `84`), middle (`109`, `110`, `118`, `119`,
`122`, `123`, `124`, `126`, `127`, `129`, `130`, `131`, `132`, `133`, `138`,
`139`, `140`), and late (`156`, `165`) row clusters. Each cluster alone failed,
and each leave-one-cluster-out variant failed. Removing the middle cluster was
most severe (`27` DRGs versus raw `28`, contained-symbol summaries `11/28`),
so the F12 `delta_y` stabilizer appears distributed across all three coarse
clusters, with the middle rows especially load-bearing.

Finer F12 row-cluster splitting found that late row `156` is sufficient with
early+middle present, while late row `165` is not. The current smallest passing
role/row subset is therefore F12 early all + middle all + row `156`, for `28`
F12 `delta_y` patches instead of `29`. It preserves raw full95 used-nest
semantics, has `0` crack-relevant DRG layout-token deltas versus raw, and has
token exact rate `0.9047454963957383` (`65642/72553`, far `0`). Splitting early
and middle into halves still failed: earlyA+middle+156, earlyB+middle+156,
early+midA+156, and early+midB+156 all failed, with earlyB+middle+156 producing
the severe `27`-DRG / `11/28` contained-symbol match shape. Early and middle
remain distributed across the tested halves.

Early leave-one-row-out against the current early+middle+156 candidate found
that rows `73` and `84` are individually optional, while rows `43`, `58`, `59`,
`76`, `77`, `79`, `80`, and `83` are load-bearing one at a time. Rows `73` and
`84` are not jointly optional: omitting both brings back the standard nests
`27`/`28` B-3/B-5 swap. The current early requirement is therefore eight
required rows plus either row `73` or row `84`.

Middle leave-one-row-out in the row-`73`-omitted context found only middle row
`127` is individually optional. Omitting any of rows `109`, `110`, `118`,
`119`, `122`, `123`, `124`, `126`, `129`, `130`, `131`, `132`, `133`, `138`,
`139`, or `140` brings back the B-3/B-5 swap. The current smallest passing F12
subset is early except `73`, middle except `127`, plus row `156`: `26`
F54410-B-12 `delta_y` patches. It preserves raw full95 used-nest semantics,
has `0` crack-relevant DRG layout-token deltas, and has token exact rate
`0.9047317133681585` (`65641/72553`, far `0`).

The alternate early choice also works: early except `84`, middle except `127`,
plus row `156` passes full95 and matches raw used-nest semantics with the same
exact-token count (`65641/72553`) and `0` crack-relevant layout-token deltas.
Rows `73` and `84` remain a coupled either/or pair, not jointly optional:
omitting `73`, `84`, and `127` still nests with the broad count envelope but
reproduces the standard nests `27`/`28` B-3/B-5 swap.

A full middle leave-one sweep in the early-except-`84` context found a broader
optional-middle set than the row-`73` branch. Rows `118`, `127`, `130`, `138`,
and `139` can each be omitted one at a time while preserving raw full95
used-nest semantics and `0` crack-relevant DRG layout-token deltas. Rows `109`,
`110`, `119`, `122`, `123`, `124`, `126`, `129`, `131`, `132`, `133`, and
`140` still fail with the standard B-3/B-5 swap. Among the passing no-`84`
variants, rows `118`, `127`, and `138` tie at `65641/72553` exact tokens; rows
`130` and `139` pass with `65640/72553`.

Pair/triple/quad reduction of that no-`84` branch found additional non-additive
stabilizers. Passing two-middle omissions were `127+130`, `127+139`, and
`138+139`, all with `65640/72553` exact tokens and `0` layout-token deltas.
Passing three-middle omissions were `118+127+139` and `127+138+139`. Passing
four-middle omissions were `118+127+138+139` and `118+130+138+139`; the better
current reduced F12 candidate omits early row `84`, middle rows `118`, `127`,
`138`, and `139`, keeps row `156`, and omits row `165`. This is a `23`-patch
F54410-B-12 `delta_y` subset that preserves raw full95 used-nest semantics,
has `0` crack-relevant DRG layout-token deltas, and has `65640/72553` exact
tokens. Omitting all five optional middle rows (`118`, `127`, `130`, `138`,
`139`) failed hard with `lay_run_nest(0)=11088` and `0` DRGs.

The `23`-patch F12 candidate also passed the hard-canary RADAN thumbnail gate:
`7/7` candidate/known-good pairs were exact pixel matches at `900x700`,
including `F54410-B-12`, and RADAN-family process cleanup was empty afterward.

Rechecking the surrounding stabilizer after F12 reduction showed `F54410-B-16`
is no longer required. Starting again from raw+B194/F21, `F54410-B-16` +
F12(23) fails with the standard B-3/B-5 swap, F12(23) alone also fails, but
`F54410-B-15` + F12(23) preserves raw full95 used-nest semantics. This reduces
the current passing candidate to `24` total token patches: one `F54410-B-15`
`delta_x` token plus the `23` F12 `delta_y` tokens. It has `0` crack-relevant
layout-token deltas, `65602/72553` exact tokens (`0.9041941752925448`), far
`0`, and `7/7` hard-canary thumbnail parity at `900x700`.

Leave-one reduction of the F12(23) subset in the F15-only context found five
individually optional F12 rows: `58`, `59`, `80`, `119`, and `129`. Omitting any
of rows `43`, `73`, `76`, `77`, `79`, `83`, `109`, `110`, `122`, `123`, `124`,
`126`, `130`, `131`, `132`, `133`, `140`, or `156` brings back the standard
B-3/B-5 swap while still producing the broad 28-DRG count envelope. This makes
the F15-only F12 stabilizer smaller and differently shaped than the prior
F15+F16 context.

Pair/triple testing among those five optional rows found three passing pair
omissions (`58+80`, `59+80`, and `80+129`) and two passing triple omissions
(`58+59+119` and `58+80+119`). No four-row omission among the optional set
preserved raw used-nest semantics. The best current reduced-context candidate is
raw+B194/F21 + the single F15 `delta_x` token + F12 rows excluding `58`, `80`,
and `119`: `22` total token patches. It preserves raw full95 used-nest
semantics, has `0` crack-relevant DRG layout-token deltas, has `65601/72553`
exact tokens (`0.9041803922649649`, far `0`), and passes hard-canary thumbnails
`7/7` at `900x700`.

The current boundary check confirms both sides are still needed: the F12(20)
subset without F15 and the F15-only variant each nest with `28` DRGs but fail
raw used-nest semantics with the same `26/28` contained-symbol match pattern.

Leave-one reduction from the F12(20) bottom found seven additional individually
optional rows: `73`, `77`, `126`, `129`, `131`, `133`, and `140`. Rows `43`,
`59`, `76`, `79`, `83`, `109`, `110`, `122`, `123`, `124`, `130`, `132`, and
`156` remain load-bearing in this context. This opens a new F12(19) reduction
layer on top of the current F15+F12(20) candidate.

Pairwise testing among those seven rows found four passing two-row omissions:
`73+131`, `77+140`, `126+133`, and `129+133`. All preserve raw full95 used-nest
semantics and `0` layout-token deltas. The best exact-token pair candidates are
`77+140` and `129+133`, each with `65600/72553` exact tokens
(`0.9041666092373851`, far `0`) and `19` total token patches.

Third-row additions to those passing pairs found four passing triples:
`73+77+131`, `73+131+133`, `77+129+140`, and `126+129+133`. The best exact-token
triple is `77+129+140`, with `65600/72553` exact tokens, `0` layout-token
deltas, and `18` total token patches. Adding any of `73`, `126`, `131`, or
`133` to that best triple fails with the standard `26/28` contained-symbol
summary shape. The `18`-patch `77+129+140` candidate passed hard-canary
thumbnail parity `7/7` at `900x700`.

Additional fourth/fifth-row testing found a smaller passing branch:
`73+126+131+133` and `73+126+129+133` both pass as `17`-patch candidates, and
`73+126+131+133+140` passes as a `16`-patch candidate. That `16`-patch candidate
preserves raw full95 used-nest semantics, has `0` layout-token deltas,
`65596/72553` exact tokens (`0.9041114771270657`, far `0`), and passes
hard-canary thumbnails `7/7`. Adding `77`, `129`, or both to the `16`-patch
candidate hard-fails with `lay_run_nest(0)=11088` and `0` DRGs.

The full Python baseline after documenting the reduced branch passed:
`C:\Tools\.venv\Scripts\python.exe -m unittest discover -v` ran `196` tests in
`2.733s` with `OK`.

A follow-up boundary sweep showed the `16`-patch candidate was not minimal.
Removing the single F15 token entirely still preserved raw full95 used-nest
semantics, giving a pure F54410-B-12 `15`-token branch with `28/28`
contained-symbol matches, `0` layout-token deltas, `65595/72553` exact tokens,
and hard-canary thumbnail parity `7/7`. Removing one remaining F12 row while
keeping F15 also produced five passing `15`-token branches: no-row `77`, `122`,
`129`, `130`, and `132`; each preserved raw used-nest semantics with `28/28`
contained-symbol matches, `0` layout-token deltas, `65596/72553` exact tokens,
and no far decoded mismatches. The no-row `77` branch also passed hard-canary
thumbnail parity `7/7`.

Reducing the pure F12-only `15`-token branch found three individually removable
rows: `76`, `109`, and `132`. Dropping row `109` is the best current pure-F12
`14`-token branch: it preserves raw full95 used-nest semantics, has `28/28`
contained-symbol matches, `0` layout-token deltas, `65595/72553` exact tokens,
`0` far mismatches, and hard-canary thumbnail parity `7/7`. Dropping row `76`
or `132` also preserves the nester oracle but lands one exact token lower at
`65594/72553`. Pair drops among `76`, `109`, and `132` all fail with the
standard `26/28` contained-symbol swap shape.

Continuing from the pure-F12 branch revealed a much smaller stabilizer. The
best branch reduced through passing drop sets `109+122`, `79+109+122`,
`79+83+109+122`, `77+79+83+109+122`,
`77+79+83+109+122+124`, and finally
`43+59+77+79+83+109+122+124`. This leaves only seven F54410-B-12 `delta_y`
token patches, at rows `76`, `110`, `123`, `129`, `130`, `132`, and `156`.
That `7`-token pure-F12 candidate preserves raw full95 used-nest semantics with
`28/28` contained-symbol matches, `0` layout-token deltas, `65591/72553` exact
tokens (`0.904042561989`, far `0`), and hard-canary thumbnail parity `7/7`.
Trying to remove any one of the seven remaining rows from this branch failed;
six removals produced the standard `26/28` swap and removing row `132` produced
the older `27`-DRG/`428`-made failure shape.

An alternate tied `8`-token branch continued one step further. Dropping
`76+77+79+83+109+122+123+124` gives another `7`-token pass; from that branch,
also dropping row `59` produces the current best pure-F12 stabilizer. It keeps
only six F54410-B-12 `delta_y` token patches, at rows `43`, `110`, `129`,
`130`, `132`, and `156`. This `6`-token candidate preserves raw full95
used-nest semantics with `28/28` contained-symbol matches, `0` layout-token
deltas, `65590/72553` exact tokens (`0.904028778962`, far `0`), and hard-canary
thumbnail parity `7/7`. Removing any one of those six retained rows hard-fails
with `lay_run_nest(0)=11088`, `0` DRGs, and `0` made parts, so this branch has a
strong local floor at six F12 row-3 tokens.

Repeat runs showed the B-3/B-5 used-nest swap is not a simple candidate
regression: the raw synthetic baseline itself repeated into the same alternate
`26/28` tie state under a fresh copied-project label. The six-token candidate's
short-label and long-label repeats matched that raw-repeat tie state exactly
(`28/28` against the repeat baseline), while the original six-token run matched
the original raw baseline. The same reclassification applies to exact-token
row `129`: replacing all six retained F12 tokens from the known-good folder, or
changing only row `129` from the source spelling `g?WE\TjL@00` to the known-good
token `g?WE\TjLD00`, matches the raw-repeat tie state. Removing row `129`
entirely still hard-fails with `lay_run_nest(0)=11088`, so row `129` is
required, but its source-vs-known-good spelling appears to select between valid
raw nester tie states rather than an accept/reject boundary.

The tie-state reclassification also changes the interpretation of the
raw+B-194/F54410-B-21 base branch. `writer_raw_B194_circle_F21_arc_pairs`
previously looked like a nester-semantics failure because it differed from the
original raw run by the same B-3/B-5 swap. Compared against a fresh raw repeat,
however, it matches `28/28` contained-symbol summaries and used-nest semantics.
The six F12 rows by themselves on top of raw synthetic also match that raw-repeat
tie state. Therefore the B-194/F21 pair is RADAN-acceptable under a tie-aware
copied-project nester oracle, while the F12 six-row set is best understood as a
token-exactness/spelling improvement and tie-state selector, not as a strict
acceptance stabilizer.

`compare_nest_artifacts.py` now has a tie-aware comparison mode via
`--alternate-right-dir` / `--alternate-right-name`. It keeps the original
primary comparison intact but adds a `tie_aware` result that accepts a candidate
when it matches either the original baseline or an explicitly supplied alternate
raw baseline by used-nest signature, DRG count, and contained-symbol summaries.
Using the original raw run plus `nester_raw_repeat1` as the alternate baseline
reclassifies the six-token F12 candidate, raw+B-194/F54410-B-21 pair candidate,
and raw-plus-six-F12 candidate as tie-aware accepted, all matching
`raw_repeat`. The comparator update added focused unit coverage and the full
baseline passed afterward: `197` tests, `OK`.

Current tie-aware accepted token benchmarks against the L-side known-good corpus
are: raw+B-194/F54410-B-21 pair at `65585/72553` exact tokens
(`0.903959863824`, far `0`), raw plus the six F12 row-3 tokens at
`65586/72553` (`0.903973646851`, far `0`), and the combined B-194/F21 pair plus
six F12 tokens at `65590/72553` (`0.904028778962`, far `0`). All remain
decoded-close for `72553/72553` token slots.
