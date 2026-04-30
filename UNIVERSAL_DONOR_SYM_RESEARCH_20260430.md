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
| B-10 | donor-only with BOM attrs and connected line order | pass, `lay_run_nest(0)=0`, 1 DRG |
| B-14 | prior RADAN-saved synthetic baseline | pass, `lay_run_nest(0)=0`, 1 DRG |

The inspectable passing copied-project RPD for raw donor-only B-10 is:
`C:\Tools\radan_automation\_sym_lab\universal_donor_sym_research_20260430_084148\b10_nester\nester_universal_donor_b10\F54410 PAINT PACK.universal_donor_b10.rpd`

The inspectable passing copied-project RPD for the B-14 saved-synthetic baseline is:
`C:\Tools\radan_automation\_sym_lab\universal_donor_sym_research_20260430_084148\b14_saved_synthetic_baseline_nester\F54410 PAINT PACK.b14_saved_synthetic_baseline.rpd`

## Disproven Hypotheses

`RADAN open/save will canonicalize the donor-only B-14 enough to nest.`

Result: false. RADAN saved the lab copy, changed the file hash, and the copied-project nester still returned `11063`.

`Missing BOM manufacturing attrs are the whole B-14 nester blocker.`

Result: false. Refreshing `Attr 119/120/121/146` from the CSV made the donor symbol metadata more correct, but B-14 still returned `11063`.

`Line-only DXF row order is the whole B-14 nester blocker.`

Result: false. The line-ordering pass produced one connected B-14 chain and unordered line geometry matched the source DXF, but raw and RADAN-saved ordered B-14 still returned `11063`.

## Next Research Direction

The remaining donor-only blocker appears to be in token spelling, row/cache semantics, wrapper metadata beyond the simple BOM attrs, or non-DDC sections. The strongest next comparison is failed donor-only B-14 versus the nesting-good RADAN-saved synthetic B-14, using the existing section/token analyzers and then targeted variants whose rules can be computed from donor + DXF/BOM rather than copied from per-part symbols.
