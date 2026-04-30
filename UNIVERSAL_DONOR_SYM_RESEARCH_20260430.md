# Universal Donor SYM Research 2026-04-30

Lab root:
`C:\Tools\radan_automation\_sym_lab\universal_donor_sym_research_20260430_084148`

Template seed:
`C:\Tools\radan_automation\donor.sym`

## Current Evidence

The donor is a blank-style seed: `Attr 110=donor`, one `D` record, one `E` record, three `U` records, and zero `G/H` geometry records.

The new harness generates symbols from only this donor and records `template_source=universal_donor` for every part.

Offline parser/decoded-geometry results passed for:

| Rung | Result |
| --- | --- |
| B-10 | pass, 4 DXF entities to 4 `G` records |
| B-14 | pass, 16 DXF entities to 16 `G` records |
| F54410-B-49 | pass, 28 DXF entities to 28 `G` records |
| B-14/B-17/F54410-B-49 | pass |
| hard7 canaries | pass |

Copied-project nester results:

| Candidate | Symbol source | Result |
| --- | --- | --- |
| B-10 | raw donor-only generated | pass, `lay_run_nest(0)=0`, 1 DRG |
| B-14 | raw donor-only generated | fail, `lay_run_nest(0)=11063`, 0 DRGs |
| B-17 | raw donor-only generated | fail, `lay_run_nest(0)=11063`, 0 DRGs |
| F54410-B-49 | raw donor-only generated | fail, `lay_run_nest(0)=11063`, 0 DRGs |
| B-14 | RADAN open/saved donor-only generated | fail, `lay_run_nest(0)=11063`, 0 DRGs |
| B-14 | donor-only with BOM attrs and connected line order | fail, `lay_run_nest(0)=11063`, 0 DRGs |
| B-14 | connected line order plus RADAN open/save | fail, `lay_run_nest(0)=11063`, 0 DRGs |
| B-14 | connected line order rotated to lowest-Y/rightmost start | fail, `lay_run_nest(0)=11063`, 0 DRGs |
| B-14 | donor-only source-6 line order, no topology snap, no endpoint canonicalization | fail, `lay_run_nest(0)=11063`, 0 DRGs |
| B-14 | donor-only raw-float line order, no topology snap, no endpoint canonicalization | fail, `lay_run_nest(0)=11063`, 0 DRGs |
| B-14 | donor-only raw-float original DXF order, no topology snap, no endpoint canonicalization | fail, `lay_run_nest(0)=11063`, 0 DRGs |
| B-14 | donor-only raw-float connected line order rotated to lowest-Y/rightmost start | fail, `lay_run_nest(0)=11063`, 0 DRGs |
| B-14 | donor-only visible fractions with existing continuation tokens padded to length 11 | fail, `lay_run_nest(0)=11063`, 0 DRGs |
| B-14 | donor wrapper plus oracle decoded fractions re-encoded by our encoder, with trailing zero continuation trimmed | fail, `lay_run_nest(0)=11063`, 0 DRGs |
| B-14 | oracle decoded fractions, exact trailing-zero spelling restored only for start slots | fail, `lay_run_nest(0)=11063`, 0 DRGs |
| B-14 | oracle decoded fractions, exact trailing-zero spelling restored only for delta slots | fail, `lay_run_nest(0)=11063`, 0 DRGs |
| B-14 | oracle decoded fractions, exact trailing-zero spelling restored only for x slots | fail, `lay_run_nest(0)=11063`, 0 DRGs |
| B-14 | oracle decoded fractions, exact trailing-zero spelling restored only for y slots | fail, `lay_run_nest(0)=11063`, 0 DRGs |
| B-14 | donor wrapper plus oracle DDC geometry lines | pass, `lay_run_nest(0)=0`, 1 DRG |
| B-17 | donor wrapper plus oracle DDC geometry lines | pass, `lay_run_nest(0)=0`, 1 DRG |
| F54410-B-49 | donor wrapper plus oracle full DDC block | pass, `lay_run_nest(0)=0`, 1 DRG |
| B-10 | donor-only with BOM attrs and connected line order | pass, `lay_run_nest(0)=0`, 1 DRG |
| B-14 | prior RADAN-saved synthetic baseline | pass, `lay_run_nest(0)=0`, 1 DRG |

The inspectable passing copied-project RPD for raw donor-only B-10 is:
`C:\Tools\radan_automation\_sym_lab\universal_donor_sym_research_20260430_084148\b10_nester\nester_universal_donor_b10\F54410 PAINT PACK.universal_donor_b10.rpd`

The inspectable passing copied-project RPD for the B-14 saved-synthetic baseline is:
`C:\Tools\radan_automation\_sym_lab\universal_donor_sym_research_20260430_084148\b14_saved_synthetic_baseline_nester\F54410 PAINT PACK.b14_saved_synthetic_baseline.rpd`

Additional B-14 diagnostic artifacts:

| Diagnostic | Path |
| --- | --- |
| token fraction analysis | `C:\Tools\radan_automation\_sym_lab\universal_donor_sym_research_20260430_084148\b14_token_fraction_analysis.json` |
| raw-float no-order donor nester RPD | `C:\Tools\radan_automation\_sym_lab\universal_donor_sym_research_20260430_084148\b14_variant_float_no_order\nester_b14_float_no_order\F54410 PAINT PACK.b14_float_no_order.rpd` |
| raw-float rotated short-path donor nester RPD | `C:\Tools\radan_automation\_sym_lab\b14fr\nester_b14fr\F54410 PAINT PACK.b14fr.rpd` |
| oracle-fraction re-encoded diagnostic RPD | `C:\Tools\radan_automation\_sym_lab\universal_donor_sym_research_20260430_084148\b14_oracle_fraction_reencoded_diagnostic\nester\F54410 PAINT PACK.b14_oracle_fraction_reencoded.rpd` |
| partial restore start/delta/x/y RPDs | `C:\Tools\radan_automation\_sym_lab\nst_rs`, `C:\Tools\radan_automation\_sym_lab\nst_rd`, `C:\Tools\radan_automation\_sym_lab\nst_rx`, `C:\Tools\radan_automation\_sym_lab\nst_ry` |

The B-14 token fraction analysis showed that the oracle and donor-rotated symbols both match transformed DXF geometry to floating tolerance (`~1e-14` / `~1e-15`), but `0/16` rows had identical first-four `G` tokens. This keeps the blocker in DDC token spelling / hidden fraction representation rather than visible geometry, row connectivity, or donor wrapper structure.

The oracle-fraction re-encoding diagnostic used the donor-generated wrapper and oracle decoded fractions, but did not copy oracle token text. Our encoder reproduced `244/272` slots exactly (`89.7%`) and stripped trailing zero continuation digits from 28 non-empty tokens, for example `n?=5R[T\1R0 -> n?=5R[T\1R`. RADAN still returned `11063`. The earlier donor-wrapper plus exact oracle DDC text passed. This is strong evidence that RADAN nesting is sensitive to exact compact-number token spelling, including otherwise decoded-equivalent trailing continuation zeroes.

## Hard Singleton Isolation 2026-04-30

Lab root:
`C:\Tools\radan_automation\_sym_lab\universal_donor_hard_singleton_row_isolation_20260430_1044`

The copied-project nester gate now preserves pre-existing RADAN/RADRAFT PIDs during cleanup unless `--kill-existing-radan` is explicitly used. The hard-singleton run preserved visible preflight PID `17512` (`P3 F55985 SPEEDLAY ... Nest Editor`) and cleaned up only automation-owned hidden instances.

The three donor-only hard singletons are now localized to small exact-token sets:

| Part | Required setup | Required exact oracle-token slots | Minimal nester result |
| --- | --- | --- | --- |
| B-14 | universal donor, connected line order, lowest-Y/rightmost rotation | `B-14:3:2`, `B-14:7:2`, `B-14:11:2`, `B-14:12:2`, `B-14:14:2`, `B-14:15:2` | pass, `lay_run_nest(0)=0`, 1 DRG |
| B-17 | universal donor hard7 writer output | `B-17:1:2`, `B-17:1:3`, `B-17:1:4`, `B-17:2:2`, `B-17:3:2`, `B-17:4:2`, `B-17:6:3`, `B-17:6:5` | pass, `lay_run_nest(0)=0`, 1 DRG |
| F54410-B-49 | universal donor from cleaned DXF, tolerance `0.002`, 28 input line vertices simplified to 20 | `F54410-B-49:7:2`, `F54410-B-49:10:3`, `F54410-B-49:13:2`, `F54410-B-49:14:2`, `F54410-B-49:16:2`, `F54410-B-49:17:2` | pass, `lay_run_nest(0)=0`, 1 DRG |

The B-49 cleaned-DXF report is:
`C:\Tools\radan_automation\_sym_lab\universal_donor_hard_singleton_row_isolation_20260430_1044\b49_cleaned_source\clean_report.json`

Its simplification removed 8 micro-jog vertices with `max_removed_local_deviation=0.0017680232690313101`, producing 20 line entities. A cleaned donor-only B-49 with decoded geometry passing still failed nesting until the six exact token slots above were restored.

Inspectable minimal singleton RPDs:

| Candidate | RPD |
| --- | --- |
| B-14 minimal token patch | `C:\Tools\radan_automation\_sym_lab\universal_donor_hard_singleton_row_isolation_20260430_1044\nester_b14_min_required_tokens\F54410 PAINT PACK.b14_min_tok.rpd` |
| B-17 minimal token patch | `C:\Tools\radan_automation\_sym_lab\universal_donor_hard_singleton_row_isolation_20260430_1044\nester_b17_min_required_tokens\F54410 PAINT PACK.b17_min_tok.rpd` |
| F54410-B-49 cleaned minimal token patch | `C:\Tools\radan_automation\_sym_lab\universal_donor_hard_singleton_row_isolation_20260430_1044\nester_b49_cleaned_min_required_tokens\F54410 PAINT PACK.b49_min_tok.rpd` |
| combined hard-three proof | `C:\Tools\radan_automation\_sym_lab\universal_donor_hard_singleton_row_isolation_20260430_1044\nester_hard3_min_required_tokens\F54410 PAINT PACK.hard3_min_tok.rpd` |

The combined hard-three proof used:
`C:\Tools\radan_automation\_sym_lab\universal_donor_hard_singleton_row_isolation_20260430_1044\hard3_min_required_tokens_symbols`

Combined proof metrics:

| Metric | Value |
| --- | --- |
| part rows | `3` |
| sheet rows after refresh | `5` |
| `lay_run_nest(0)` | `0` |
| DRG count | `2` |
| nest rows | `16` |
| made/nonzero count | `12` |
| `NextNestNum` | `17` |

Interpretation: these are still diagnostic token-patch variants, because the exact accepted token strings were copied from per-part RADAN oracle symbols during isolation. The crack has narrowed from whole-symbol uncertainty to a small set of compact-number spelling choices. The next real writer step is to derive those final-token/continuation choices from DXF-visible values and corpus rules without same-part oracle tokens.

## Hard7 Follow-Up 2026-04-30

Lab root:
`C:\Tools\radan_automation\_sym_lab\universal_donor_predictability_20260430_1128`

A fresh 95-part universal-donor corpus was generated offline under:
`C:\Tools\radan_automation\_sym_lab\universal_donor_predictability_20260430_1128\proven95_generate`

Generation result:

| Metric | Value |
| --- | --- |
| generated symbols | `95` |
| excluded oversized known-good nester blockers | `F54410-B-09`, `F54410-B-11`, `F54410-B-17` |
| template source | `universal_donor` |
| RADAN conversion used | no |

A simple leave-one-part-out before-token predictability check was run against the required hard-singleton token slots. Slot-aware before-token evidence predicted only `3/20` required repairs; most required repairs had no matching training token outside the target part. This argues for a numeric/token-continuation rule rather than a sparse lookup table.

The 95-symbol folder with the three minimal hard-singleton fixes swapped in is:
`C:\Tools\radan_automation\_sym_lab\universal_donor_predictability_20260430_1128\symbols_95_plus_hard3_min`

Hard7 copied-project nester result with that folder:

| Candidate | Result |
| --- | --- |
| B-14 minimal token fix | single-part pass |
| B-17 minimal token fix | single-part pass |
| F54410-B-49 cleaned minimal token fix | single-part pass |
| F54410-B-27 raw donor | single-part pass |
| B-27 raw donor | single-part fail, `11063` |
| B-30 raw donor | single-part fail, `11063` |
| F54410-B-12 raw donor | single-part fail, `11063` |
| hard7 together with only hard3 fixed | fail, `11063`, 0 DRGs |

For `B-27`, `B-30`, and `F54410-B-12`, donor and oracle row counts and type sequences match exactly:

| Part | Rows | Finding |
| --- | --- | --- |
| B-27 | `181` | donor wrapper + all oracle geometry rows passes |
| B-30 | `80` | donor wrapper + all oracle geometry rows passes |
| F54410-B-12 | `194` | donor wrapper + all oracle geometry rows passes |

Chunk-exclusion isolation with 16-row chunks still failed for every chunk on all three parts. Unlike B-14/B-17/B-49, these large canaries do not reduce to a tiny poison-row set; they appear to need broad exact compact-number spelling across many rows.

The hard7 diagnostic folder with `B-27`, `B-30`, and `F54410-B-12` replaced by full oracle-row variants is:
`C:\Tools\radan_automation\_sym_lab\universal_donor_predictability_20260430_1128\symbols_95_plus_hard7_oracle_rows`

Its copied-project nester proof passed:

| Metric | Value |
| --- | --- |
| RPD | `C:\Tools\radan_automation\_sym_lab\universal_donor_predictability_20260430_1128\nester_hard7_oracle_rows\F54410 PAINT PACK.hard7_oracle_rows.rpd` |
| part rows | `7` |
| sheet rows after refresh | `5` |
| `lay_run_nest(0)` | `0` |
| DRG count | `2` |
| nest rows | `16` |
| made/nonzero count | `28` |
| `NextNestNum` | `17` |

## Hard7 Slot-Family Isolation 2026-04-30

Lab root:
`C:\Tools\radan_automation\_sym_lab\universal_donor_predictability_20260430_1128\hard7_slot_family_isolation`

The hard7 follow-up moved beyond full-row replacement by reverting oracle rows one compact-token family at a time. The test starts from passing donor-wrapper/oracle-row diagnostics and asks which slot families can be reverted to donor spelling before `lay_run_nest(0)` fails.

Mismatch profile before isolation:

| Part | Rows | Field diffs | Token mismatch groups |
| --- | ---: | --- | --- |
| B-27 | `181` | `8: 12`, `10: 149` | `G0 109`, `G1 123`, `G2 145`, `G3 144`, `H0 4` |
| B-30 | `80` | `10: 80` | `G0 65`, `G1 67`, `G2 51`, `G3 50`, `H0 8`, `H1 9`, `H2 6`, `H3 4`, `H4 3`, `H5 3` |
| F54410-B-12 | `194` | `8: 154`, `10: 190` | `G0 141`, `G1 150`, `G2 113`, `G3 131`, `H0 2`, `H1 13`, `H2 2`, `H3 2`, `H4 2`, `H5 2` |

Required exact-token families found by copied-project nester gates:

| Part | Required oracle-token families | Field 8 pen exactness | Single-part result |
| --- | --- | --- | --- |
| B-27 | `G0/G2/G3` | not required | pass, `lay_run_nest(0)=0`, 1 DRG |
| B-30 | `G1/G2/G3/H2/H4/H5` | not applicable | pass, `lay_run_nest(0)=0`, 1 DRG |
| F54410-B-12 | `G0/G1/G2/G3/H2/H4/H5` | not required | pass, `lay_run_nest(0)=0`, 1 DRG |

The combined hard7 required-family folder is:
`C:\Tools\radan_automation\_sym_lab\universal_donor_predictability_20260430_1128\symbols_95_plus_hard7_required_families`

Its copied-project nester proof passed:

| Metric | Value |
| --- | --- |
| RPD | `C:\Tools\radan_automation\_sym_lab\universal_donor_predictability_20260430_1128\nester_hard7_required_families\F54410 PAINT PACK.hard7_reqfam.rpd` |
| symbol folder | `C:\Tools\radan_automation\_sym_lab\universal_donor_predictability_20260430_1128\symbols_95_plus_hard7_required_families` |
| part rows | `7` |
| sheet rows after refresh | `5` |
| `lay_run_nest(0)` | `0` |
| elapsed | `3.118s` |
| DRG count | `2` |
| nest rows | `16` |
| made/nonzero count | `28` |
| `NextNestNum` | `17` |
| RADAN process cleanup | preflight empty, final empty |

Interpretation: the universal donor wrapper and generated row structure are still acceptable, but larger canaries need broad exact compact-number spelling by slot family. These variants are diagnostic because the accepted token text is still copied from same-part RADAN oracle rows. The next crack target is a numeric continuation/spelling rule for these families, not a per-part token lookup.

## Arc/Circle Stress Slot-Family Isolation 2026-04-30

Lab root:
`C:\Tools\radan_automation\_sym_lab\universal_donor_predictability_20260430_1128\arc_stress_slot_family_isolation`

The arc/circle stress rung was run with:
`B-27`, `B-28`, `B-30`, `F54410-B-41`, `F54410-B-02`, `F54410-B-35`.

The first attempt using only the hard7 required-family folder failed with `11063`. Single-part isolation showed four new donor-family blockers:

| Part | Raw/hard7-family donor result |
| --- | --- |
| B-28 | fail, `11063` |
| F54410-B-41 | fail, `11063` |
| F54410-B-02 | fail, `11063` |
| F54410-B-35 | fail, `11063` |

Donor wrapper plus full oracle rows for those four parts passed the six-part arc/circle stress rung:

| Metric | Value |
| --- | --- |
| RPD | `C:\Tools\radan_automation\_sym_lab\universal_donor_predictability_20260430_1128\nester_arc_stress_oracle_rows\F54410 PAINT PACK.arc_stress_oracle_rows.rpd` |
| part rows | `6` |
| sheet rows after refresh | `6` |
| `lay_run_nest(0)` | `0` |
| DRG count | `3` |
| nest rows | `17` |
| made/nonzero count | `24` |
| `NextNestNum` | `18` |

Required or sufficient donor-side token-family candidates:

| Part | Sufficient oracle-token families | Notes |
| --- | --- | --- |
| B-28 | `G0/H0` | smallest family candidate tested passed |
| F54410-B-41 | `G2/H2/H3/H4/H5` | smallest family candidate tested passed |
| F54410-B-35 | `G2/G3` | no single family was individually required; this two-family combo passed |
| F54410-B-02 | `G0/G1/G2/G3/H2/H3` | individually necessary `G2/H2/H3` was not sufficient; all G families plus `H2/H3` passed |

Patching field 8 pen values back to oracle spelling was not required for `F54410-B-02` or `F54410-B-35`; in both broad all-token-plus-field8 diagnostics it made RADAN return `11088`. This is another sign that field-level changes can become inconsistent unless the whole row spelling is copied.

The combined arc/circle required-family folder is:
`C:\Tools\radan_automation\_sym_lab\universal_donor_predictability_20260430_1128\symbols_95_plus_arc_stress_required_families`

Its copied-project nester proof passed:

| Metric | Value |
| --- | --- |
| RPD | `C:\Tools\radan_automation\_sym_lab\universal_donor_predictability_20260430_1128\nester_arc_stress_required_families_v2\F54410 PAINT PACK.arc_stress_reqfam_v2.rpd` |
| part rows | `6` |
| sheet rows after refresh | `6` |
| `lay_run_nest(0)` | `0` |
| elapsed | `1.983s` |
| DRG count | `3` |
| nest rows | `17` |
| made/nonzero count | `24` |
| `NextNestNum` | `18` |
| RADAN process cleanup | preflight empty, final empty |

## First-10 Slot-Family Isolation 2026-04-30

The first-10 rung initially failed with the arc/circle required-family folder:

| Metric | Value |
| --- | --- |
| RPD | `C:\Tools\radan_automation\_sym_lab\universal_donor_predictability_20260430_1128\nester_first10_arcstress_reqfam\F54410 PAINT PACK.first10_arcstress_reqfam.rpd` |
| part rows | `10` |
| sheet rows after refresh | `5` |
| `lay_run_nest(0)` | `11063` |
| DRG count | `0` |

Single-part isolation found only two blockers in the first ten CSV rows:

| Part | Single-part donor-family result |
| --- | --- |
| B-15 | fail, `11063` |
| B-16 | fail, `11063` |

Full oracle-row replacement for `B-15` and `B-16` made the first-10 rung pass, then slot-family isolation produced donor-side sufficient candidates:

| Part | Sufficient oracle-token families | Single-part result |
| --- | --- | --- |
| B-15 | `G2/G3/H2/H3/H4/H5` | pass, `lay_run_nest(0)=0`, 1 DRG |
| B-16 | `G0/G1/G2/G3` | pass, `lay_run_nest(0)=0`, 1 DRG |

The combined first-10 required-family folder is:
`C:\Tools\radan_automation\_sym_lab\universal_donor_predictability_20260430_1128\symbols_95_plus_first10_required_families`

Its copied-project nester proof passed:

| Metric | Value |
| --- | --- |
| RPD | `C:\Tools\radan_automation\_sym_lab\universal_donor_predictability_20260430_1128\nester_first10_required_families\F54410 PAINT PACK.first10_reqfam.rpd` |
| part rows | `10` |
| sheet rows after refresh | `5` |
| `lay_run_nest(0)` | `0` |
| elapsed | `3.166s` |
| DRG count | `4` |
| nest rows | `18` |
| made/nonzero count | `43` |
| `NextNestNum` | `19` |
| RADAN process cleanup | preflight empty, final empty |

## First-25 Slot-Family Isolation 2026-04-30

The first-25 rung initially failed with the first-10 required-family folder:

| Metric | Value |
| --- | --- |
| RPD | `C:\Tools\radan_automation\_sym_lab\universal_donor_predictability_20260430_1128\nester_first25_first10_reqfam\F54410 PAINT PACK.first25_first10_reqfam.rpd` |
| part rows | `25` |
| sheet rows after refresh | `8` |
| `lay_run_nest(0)` | `11063` |
| DRG count | `0` |

Single-part isolation over rows 11-25 found these additional blockers:

| Part | Single-part donor-family result |
| --- | --- |
| B-18 | fail, `11063` |
| B-184 | fail, `11063` |
| B-193 | fail, `11063` |
| B-194 | fail, `11063` |
| B-195 | fail, `11063` |
| B-25 R2 | fail, `11063` |

Full oracle-row replacement for those six parts made the first-25 rung pass:

| Metric | Value |
| --- | --- |
| RPD | `C:\Tools\radan_automation\_sym_lab\universal_donor_predictability_20260430_1128\nester_first25_oracle_rows\F54410 PAINT PACK.first25_oracle_rows.rpd` |
| part rows | `25` |
| sheet rows after refresh | `8` |
| `lay_run_nest(0)` | `0` |
| DRG count | `9` |
| made/nonzero count | `115` |

Slot-family isolation produced these donor-side sufficient candidates:

| Part | Sufficient oracle-token families | Single-part result |
| --- | --- | --- |
| B-18 | `G3/H2/H3/H4/H5` | pass, `lay_run_nest(0)=0`, 1 DRG |
| B-184 | `G0/G1/G2/G3` | pass, `lay_run_nest(0)=0`, 1 DRG |
| B-193 | `G2/G3/H2/H3/H4/H5` | pass, `lay_run_nest(0)=0`, 1 DRG |
| B-194 | `G2/G3/H2/H3/H4/H5` | pass, `lay_run_nest(0)=0`, 1 DRG |
| B-195 | `G2/G3/H2/H3/H4/H5` | pass, `lay_run_nest(0)=0`, 1 DRG |
| B-25 R2 | `G0/G1/G2/G3/H2/H4/H5` | pass, `lay_run_nest(0)=0`, 1 DRG |

For `B-25 R2`, `H2/H4/H5` were individually necessary but not sufficient; adding all G families made the candidate pass. As with earlier field-8 diagnostics, adding field-8 pen patches to the broad all-token candidate returned `11088`, so field-8 exactness is not being treated as a safe standalone repair.

The combined first-25 required-family folder is:
`C:\Tools\radan_automation\_sym_lab\universal_donor_predictability_20260430_1128\symbols_95_plus_first25_required_families`

Its copied-project nester proof passed:

| Metric | Value |
| --- | --- |
| RPD | `C:\Tools\radan_automation\_sym_lab\universal_donor_predictability_20260430_1128\nester_first25_required_families\F54410 PAINT PACK.first25_reqfam.rpd` |
| part rows | `25` |
| sheet rows after refresh | `8` |
| `lay_run_nest(0)` | `0` |
| elapsed | `12.881s` |
| DRG count | `9` |
| nest rows | `23` |
| made/nonzero count | `115` |
| `NextNestNum` | `24` |
| RADAN process cleanup | preflight empty, final empty |

## First-49 Slot-Family And D-Record Isolation 2026-04-30

The first-49 rung initially failed with the first-25 required-family folder:

| Metric | Value |
| --- | --- |
| RPD | `C:\Tools\radan_automation\_sym_lab\universal_donor_predictability_20260430_1128\nester_first49_first25_reqfam\F54410 PAINT PACK.first49_first25_reqfam.rpd` |
| part rows | `49` |
| sheet rows after refresh | `8` |
| `lay_run_nest(0)` | `11063` |
| DRG count | `0` |

Single-part isolation over rows 26-49 found six new donor blockers:

| Part | First failing code |
| --- | --- |
| B-31 | `11063` |
| B-37 | `11036` |
| B-38 | `11036` |
| B-50 | `11036` |
| B-52-R2 | `11063` |
| B-52 | `11063` |

Known-good RADAN-saved source symbols for `B-37`, `B-38`, and `B-50`
passed singly, proving those were donor-generation failures rather than sheet
or nester setup failures. Donor wrapper plus exact oracle G/H rows still failed
for those three parts with `11036`, but copying only the RADAN-saved D record
into the donor-generated symbol made all three pass singly:

| Part | Minimal passing non-geometry repair | Single-part result |
| --- | --- | --- |
| B-37 | D record only | pass, `lay_run_nest(0)=0`, 1 DRG |
| B-38 | D record only | pass, `lay_run_nest(0)=0`, 1 DRG |
| B-50 | D record only | pass, `lay_run_nest(0)=0`, 1 DRG |

This is the first clear donor-only evidence that a non-geometry DDC/cache row
can be nester-visible independent of the exact G/H geometry rows.

Forward slot-family candidates then passed for the other three blockers:

| Part | Sufficient oracle-token families | Single-part result |
| --- | --- | --- |
| B-31 | `G2` | pass, `lay_run_nest(0)=0`, 1 DRG |
| B-52-R2 | `G2/G3/H2/H3/H4` | pass, `lay_run_nest(0)=0`, 1 DRG |
| B-52 | `G2/G3/H2/H3/H4/H5` | pass, `lay_run_nest(0)=0`, 1 DRG |

The combined first-49 required-family folder is:
`C:\Tools\radan_automation\_sym_lab\universal_donor_predictability_20260430_1128\symbols_95_plus_first49_required_families`

Its copied-project nester proof passed:

| Metric | Value |
| --- | --- |
| RPD | `C:\Tools\radan_automation\_sym_lab\universal_donor_predictability_20260430_1128\nester_first49_required_families\F54410 PAINT PACK.first49_reqfam.rpd` |
| part rows | `49` |
| sheet rows after refresh | `8` |
| `lay_run_nest(0)` | `0` |
| elapsed | `34.184s` |
| DRG count | `13` |
| nest rows | `27` |
| made/nonzero count | `232` |
| `NextNestNum` | `28` |
| RADAN process cleanup | preflight empty, final empty |

## 95-Part Donor Wrapper DDC Upper Bound 2026-04-30

Promoting the first-49 required-family folder directly to the 95-part proven
subset, excluding only oversized `F54410-B-09`, `F54410-B-11`, and
`F54410-B-17`, loaded 95 part rows and 8 sheet rows but failed during nesting
with a COM exception from RADAN:

| Metric | Value |
| --- | --- |
| RPD | `C:\Tools\radan_automation\_sym_lab\universal_donor_predictability_20260430_1128\nester_95_first49_required_families\F54410 PAINT PACK.q95_first49_reqfam.rpd` |
| symbol folder | `C:\Tools\radan_automation\_sym_lab\universal_donor_predictability_20260430_1128\symbols_95_plus_first49_required_families` |
| part rows | `95` |
| sheet rows after refresh | `8` |
| excluded parts | `F54410-B-09`, `F54410-B-11`, `F54410-B-17` |
| result | COM exception during nest, 0 DRGs |
| RADAN process cleanup | preflight empty, automation PID killed, final empty |

Singleton isolation over the post-49 rows found 20 parts that already nested
with the first-49 folder and 26 additional donor blockers:

| Code | Parts |
| --- | --- |
| `11036` | `F54410-B-01`, `F54410-B-10`, `F54410-B-29`, `F54410-B-31` |
| `11063` | `F54410-B-03`, `F54410-B-04`, `F54410-B-05`, `F54410-B-06`, `F54410-B-07`, `F54410-B-08`, `F54410-B-13`, `F54410-B-14`, `F54410-B-15`, `F54410-B-16`, `F54410-B-18`, `F54410-B-19`, `F54410-B-25`, `F54410-B-26`, `F54410-B-32`, `F54410-B-33`, `F54410-B-37`, `F54410-B-38`, `F54410-B-39`, `F54410-B-40`, `F54410-B-46`, `F54410-B-47` |

D-record-only repair was sufficient for two of the four `11036` parts:

| Part | D-record-only result |
| --- | --- |
| F54410-B-01 | changed failure from `11036` to `11063`; D record alone not enough |
| F54410-B-10 | changed failure from `11036` to `11063`; D record alone not enough |
| F54410-B-29 | pass, `lay_run_nest(0)=0`, 1 DRG |
| F54410-B-31 | pass, `lay_run_nest(0)=0`, 1 DRG |

Replacing the full DDC block, but keeping the universal donor wrapper, for the
26 post-49 failing parts produced a 95-part copied-project nester pass. This is
a diagnostic upper bound, not a generated-symbol solution, because it borrows
same-part RADAN DDC text. It proves the universal donor wrapper remains
acceptable at the full proven-subset scale and localizes the remaining failures
to DDC block generation.

| Metric | Value |
| --- | --- |
| RPD | `C:\Tools\radan_automation\_sym_lab\universal_donor_predictability_20260430_1128\nester_95_post49_full_ddc_failures\F54410 PAINT PACK.q95_post49_full_ddc.rpd` |
| symbol folder | `C:\Tools\radan_automation\_sym_lab\universal_donor_predictability_20260430_1128\symbols_95_plus_post49_full_ddc_failures` |
| part rows | `95` |
| sheet rows after refresh | `8` |
| `lay_run_nest(0)` | `0` |
| elapsed | `59.750s` |
| DRG count | `26` |
| nest rows | `40` |
| made/nonzero count | `428` |
| `NextNestNum` | `41` |
| RADAN process cleanup | preflight empty, final empty |

The report follow-up reran the same 95-part upper-bound candidate successfully
and then attempted `Project Report` and `Setup Sheet`. Both report calls failed
with `Wrong mode for DevExpress reports`, no PDFs were created, and the RADAN
process cleanup was clean:

| Metric | Value |
| --- | --- |
| RPD | `C:\Tools\radan_automation\_sym_lab\universal_donor_predictability_20260430_1128\nester_95_post49_full_ddc_reports\F54410 PAINT PACK.q95_full_ddc_report.rpd` |
| `lay_run_nest(0)` | `0` |
| DRG count | `26` |
| report result | blocked: `Wrong mode for DevExpress reports` |
| RADAN process cleanup | preflight empty, final empty |

A reduced DDC upper bound also passed. It kept the donor wrapper, copied exact
G/H geometry rows for 21 post-49 failures, used D-record-only repair for
`F54410-B-29` and `F54410-B-31`, and used full DDC only for the three parts
where RADAN's source DDC has fewer geometry rows than the donor writer
(`F54410-B-37`, `F54410-B-38`, `F54410-B-39`).

| Metric | Value |
| --- | --- |
| RPD | `C:\Tools\radan_automation\_sym_lab\universal_donor_predictability_20260430_1128\nester_95_post49_geometry_exact_upper\F54410 PAINT PACK.q95_post49_geom_upper.rpd` |
| symbol folder | `C:\Tools\radan_automation\_sym_lab\universal_donor_predictability_20260430_1128\symbols_95_plus_post49_geometry_exact_upper` |
| part rows | `95` |
| sheet rows after refresh | `8` |
| `lay_run_nest(0)` | `0` |
| elapsed | `56.626s` |
| DRG count | `27` |
| nest rows | `41` |
| made/nonzero count | `428` |
| `NextNestNum` | `42` |
| RADAN process cleanup | preflight empty, final empty |

This narrows the full-subset donor crack to exact G/H row generation, two
known D-record-only cache repairs, and three row-count/repair cases.

A stricter field-10-only reduction was tested next. It preserved the donor
G/H row prefixes and non-field-10 fields, copied only the source field-10
geometry-token payload for row-count-matching post-49 failures, kept D-only
repair for `F54410-B-29` and `F54410-B-31`, and kept full DDC for the same
three row-count/repair cases. The full 95-part copied-project nester run failed
fast with `11063` and 0 DRGs:

| Metric | Value |
| --- | --- |
| RPD | `C:\Tools\radan_automation\_sym_lab\universal_donor_predictability_20260430_1128\nester_95_post49_field10_exact_upper\F54410 PAINT PACK.q95_post49_f10_upper.rpd` |
| symbol folder | `C:\Tools\radan_automation\_sym_lab\universal_donor_predictability_20260430_1128\symbols_95_plus_post49_field10_exact_upper` |
| part rows | `95` |
| sheet rows after refresh | `8` |
| `lay_run_nest(0)` | `11063` |
| DRG count | `0` |
| RADAN process cleanup | preflight empty, final empty |

Singleton isolation showed the field-10-only reduction was sufficient for 16 of
the 21 row-count-matching post-49 failures, but these five still require more
than exact field-10 payload:

| Part | Field-10-only singleton result |
| --- | --- |
| F54410-B-01 | fail, `11063` |
| F54410-B-05 | fail, `11063` |
| F54410-B-10 | fail, `11063` |
| F54410-B-14 | fail, `11063` |
| F54410-B-40 | fail, `11063` |

That separates most post-49 failures into token-payload exactness and leaves a
smaller set where record type or other G/H fields are also nester-visible.

The five field-10-only singleton failures were reduced further:

| Part | Additional requirement over exact field 10 | Singleton result |
| --- | --- | --- |
| F54410-B-05 | field 8 exactness | pass, `lay_run_nest(0)=0`, 1 DRG |
| F54410-B-10 | field 8 exactness | pass, `lay_run_nest(0)=0`, 1 DRG |
| F54410-B-14 | field 8 exactness | pass, `lay_run_nest(0)=0`, 1 DRG |
| F54410-B-01 | record type, fields 8/9/11, and terminal empty-field count | pass, `lay_run_nest(0)=0`, 1 DRG |
| F54410-B-40 | record type, fields 9/11, and terminal empty-field count | pass, `lay_run_nest(0)=0`, 1 DRG |

For `F54410-B-01` and `F54410-B-40`, matching the visible fields but leaving
the donor-style terminal comma count still failed with `11063`. Adjusting only
the trailing empty-field shape to match RADAN's exact row text made both parts
nest. This proves the raw DDC row arity/trailing-delimiter spelling is
nester-visible.

The current sharpest 95-part reduced upper bound is:
`C:\Tools\radan_automation\_sym_lab\universal_donor_predictability_20260430_1128\symbols_95_plus_post49_required_fields_trailing_upper`

It uses:

- exact field 10 only for the 16 post-49 parts where that was sufficient
- field 8 plus exact field 10 for `F54410-B-05`, `F54410-B-10`, `F54410-B-14`
- record type / field 9 / field 11 / trailing-empty-field-count repairs for `F54410-B-01` and `F54410-B-40`
- D-record-only repair for `F54410-B-29` and `F54410-B-31`
- full DDC only for row-count/repair cases `F54410-B-37`, `F54410-B-38`, `F54410-B-39`

Its copied-project nester proof passed:

| Metric | Value |
| --- | --- |
| RPD | `C:\Tools\radan_automation\_sym_lab\universal_donor_predictability_20260430_1128\nester_95_post49_required_fields_trailing\F54410 PAINT PACK.q95_post49_reqfields.rpd` |
| part rows | `95` |
| sheet rows after refresh | `8` |
| `lay_run_nest(0)` | `0` |
| elapsed | `54.020s` |
| DRG count | `27` |
| nest rows | `41` |
| made/nonzero count | `428` |
| `NextNestNum` | `42` |
| RADAN process cleanup | preflight empty, final empty |

## Row-Count Geometry-Only Reduction 2026-04-30

The remaining full-DDC bucket for `F54410-B-37`, `F54410-B-38`, and
`F54410-B-39` was reduced. Each part's raw universal-donor symbol has exactly
8 more G/H rows than RADAN's saved source symbol:

| Part | raw donor G/H rows | RADAN source G/H rows | delta |
| --- | ---: | ---: | ---: |
| F54410-B-37 | 80 | 72 | 8 |
| F54410-B-38 | 280 | 272 | 8 |
| F54410-B-39 | 26 | 18 | 8 |

The unmatched-row inspection shows RADAN collapses straight collinear boundary
fragments into one longer `G` row per side:

| Part | RADAN merged rows observed |
| --- | --- |
| F54410-B-37 | vertical boundary fragments at `x=0` and `x=42` collapse into long side rows |
| F54410-B-38 | horizontal boundary fragments on the bottom/top edges collapse into long edge rows |
| F54410-B-39 | vertical boundary fragments at `x=0` and `x=70.8125` collapse into long side rows |

Two lab variants were generated from the current 95-part reduced upper bound:

| Variant | Row-count case treatment |
| --- | --- |
| `symbols_95_plus_rowcount_source_geometry_Ecount` | replace only the three parts' G/H rows with RADAN source G/H rows, and regenerate the donor `E` count |
| `symbols_95_plus_rowcount_source_geometry_only_keep_raw_E` | replace only the three parts' G/H rows with RADAN source G/H rows, leaving the raw donor `E` record untouched |

All six singleton checks passed through the copied-project nester oracle:

| Variant | Parts | Result |
| --- | --- | --- |
| regenerated `E` count | `F54410-B-37`, `F54410-B-38`, `F54410-B-39` | all pass, `lay_run_nest(0)=0`, 1 DRG each |
| raw donor `E` count | `F54410-B-37`, `F54410-B-38`, `F54410-B-39` | all pass, `lay_run_nest(0)=0`, 1 DRG each |

The sharper raw-`E` geometry-only variant also passed the full 95-part copied
project gate:

| Metric | Value |
| --- | --- |
| RPD | `C:\Tools\radan_automation\_sym_lab\universal_donor_predictability_20260430_1128\nester_95_rowcount_geometry_only_keep_raw_E\F54410 PAINT PACK.q95_rowcount_geom_only.rpd` |
| symbol folder | `C:\Tools\radan_automation\_sym_lab\universal_donor_predictability_20260430_1128\symbols_95_plus_rowcount_source_geometry_only_keep_raw_E` |
| part rows | `95` |
| sheet rows after refresh | `8` |
| `lay_run_nest(0)` | `0` |
| elapsed | `56.253s` |
| DRG count | `28` |
| nest rows | `42` |
| made/nonzero count | `431` |
| `NextNestNum` | `43` |
| RADAN process cleanup | preflight empty, final empty |

The same symbol folder was rerun with report generation enabled:

| Metric | Value |
| --- | --- |
| RPD | `C:\Tools\radan_automation\_sym_lab\universal_donor_predictability_20260430_1128\nester_95_rowcount_geometry_only_reports\F54410 PAINT PACK.q95_rowcount_geom_reports.rpd` |
| `lay_run_nest(0)` | `0` |
| elapsed | `56.797s` |
| DRG count | `28` |
| nest rows | `42` |
| made/nonzero count | `431` |
| `pfl_finish_nesting(True, False, 0.0)` | `false` |
| project report | failed, `Wrong mode for DevExpress reports`, no PDF |
| setup sheet | failed, `Wrong mode for DevExpress reports`, no PDF |
| RADAN process cleanup | preflight empty, final empty |

This removes the need for a full DDC-block transplant for those three
row-count parts. The blocker is now specifically the geometry row merge/spelling
for those straight boundary fragments; surrounding donor D/E/U records were not
the practical nester blocker in this test. This remains an oracle-reduced upper
bound, because the merged G/H row text was copied from same-part RADAN source
symbols instead of generated directly from DXF.

Follow-up generated-row diagnostics narrowed the row-count crack further:

| Candidate | F54410-B-37 | F54410-B-38 | F54410-B-39 | Conclusion |
| --- | --- | --- | --- | --- |
| generated collinear-chain merge from raw donor rows, generated field 10, generated row count | fail `11063` | fail `11063` | fail `11063` | the merge topology and row count are not sufficient by themselves |
| source G/H rows, but generated field 10 only on the two merged-chain rows | pass | pass | pass | generated compact tokens for the merged rows are acceptable |
| source G/H order/row fields, generated field 10 for every matching generated `G` segment | fail `11063` | fail `11063` | pass | `F54410-B-39` is mostly row order/row-shape sensitive; `F54410-B-37` and `F54410-B-38` still need exact token spelling on additional rows |

The generated collinear-chain rule found exactly the RADAN row-count reduction
for all three parts: two five-fragment straight same-pen chains per part,
removing eight geometry rows. Artifacts:

| Artifact | Path |
| --- | --- |
| generated merge symbols | `C:\Tools\radan_automation\_sym_lab\universal_donor_predictability_20260430_1128\symbols_95_plus_rowcount_generated_collinear_merge_v2` |
| generated merge singleton checks | `C:\Tools\radan_automation\_sym_lab\universal_donor_predictability_20260430_1128\rowcount_generated_collinear_merge_v2_single_checks` |
| generated merged-row field-10 diagnostic | `C:\Tools\radan_automation\_sym_lab\universal_donor_predictability_20260430_1128\symbols_95_plus_rowcount_source_rows_generated_merged_only_field10` |
| source-order generated field-10 diagnostic | `C:\Tools\radan_automation\_sym_lab\universal_donor_predictability_20260430_1128\symbols_95_plus_rowcount_source_order_generated_field10_all` |

This turns the row-count branch into two smaller problems:

- generate RADAN-like row order/row fields for the merged source-order shape
- improve compact token spelling for the remaining non-merged generated rows,
  especially `F54410-B-37` and `F54410-B-38`

## Disproven Hypotheses

`RADAN open/save will canonicalize the donor-only B-14 enough to nest.`

Result: false. RADAN saved the lab copy, changed the file hash, and the copied-project nester still returned `11063`.

`Missing BOM manufacturing attrs are the whole B-14 nester blocker.`

Result: false. Refreshing `Attr 119/120/121/146` from the CSV made the donor symbol metadata more correct, but B-14 still returned `11063`.

`Line-only DXF row order is the whole B-14 nester blocker.`

Result: false. The line-ordering pass produced one connected B-14 chain and unordered line geometry matched the source DXF, but raw and RADAN-saved ordered B-14 still returned `11063`.

`Loop start point is the whole B-14 nester blocker.`

Result: false. A lab-only computed variant rotated the connected B-14 loop to the same lowest-Y/rightmost start point seen in the nesting-good saved synthetic B-14, updated row identifiers, and still returned `11063`.

`Current snapping/canonicalization settings are the whole B-14 nester blocker.`

Result: false. Source-rounded/no-snap/no-canonical, raw-float/no-snap/no-canonical, and raw-float/original-order variants all still returned `11063`.

`Raw float coordinates plus the saved-symbol loop start is enough for B-14.`

Result: false. A repeatable writer option now rotates a closed connected line profile to the lowest-Y/rightmost start point. The B-14 raw-float/no-snap/no-canonical rotated variant started at `[21.5, 0.0]`, had unordered line geometry parity, and still returned `11063` in a short copied-project path with no path-length warning.

`Continuation length alone can fix visible-fraction donor B-14.`

Result: false. Padding existing generated visible-fraction tokens with continuation digits changed 8 tokens but still returned `11063`.

`Decoded oracle fractions are enough even if token text is not exact.`

Result: false. Re-encoding oracle decoded fractions from the donor wrapper stripped only trailing zero continuation digits from 28 non-empty tokens and still returned `11063`.

`Only one broad B-14 slot family needs exact trailing-zero spelling.`

Result: false. Restoring exact oracle token text only for start slots, delta slots, x slots, or y slots all still returned `11063`. Each run used a short copied-project path, produced 0 DRGs, and ended with no RADAN processes. Exact token spelling appears to be a broader all-slot/block property for this canary.

`Generic leave-one-out corpus token spelling is enough for B-14.`

Result: false. A token-only variant preserved the donor geometry fractions and changed 8 token spellings using B-14-excluded corpus observations. Unordered geometry still matched the DXF, but the nester returned `11088`.

`Donor wrapper/cache metadata is the hard blocker.`

Result: false for the tested canaries. Donor-wrapper symbols nested successfully when their DDC geometry/block was replaced with oracle RADAN DDC:

| Part | Diagnostic | Result |
| --- | --- | --- |
| B-14 | donor wrapper + oracle G lines, DDC raw equal to oracle | pass |
| B-17 | donor wrapper + oracle G/H lines | pass |
| F54410-B-49 | donor wrapper + oracle full DDC block, including RADAN row-count repair from 28 to 20 rows | pass |

These are diagnostic upper bounds only, not candidate generated symbols, because they read per-part oracle DDC.

## Next Research Direction

The remaining donor-only blocker is now localized to DDC geometry/block generation. The donor wrapper is acceptable. Next work should focus on deriving RADAN-exact DDC from DXF without per-part symbols:

- exact token spelling/hidden-coordinate fractions for line and arc slots
- continuation-length / trailing-zero rules for compact number tokens
- RADAN row deletion/repair behavior for B-49 style micro-jog geometry
- DDC row start/order/orientation rules only where they change the exact DDC block
- corpus-learned rules that preserve DXF geometry and do not borrow same-part oracle rows
