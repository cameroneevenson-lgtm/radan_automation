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
