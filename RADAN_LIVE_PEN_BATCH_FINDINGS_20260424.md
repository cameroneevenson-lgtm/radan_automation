# RADAN Live Pen Batch Findings 2026-04-24

This note captures the live Nest-driven pen-remap batch we proved on `2026-04-24`.

## Proven Batch Path

The working live path for a batch from Nest is:

1. start in `Nest Editor`
2. select the target row in the parts list
3. open the selected part with `rpr_parts_list_open_part_button`
4. wait for the real Part Editor title to settle on the requested part
5. run [remap_feature_pens_live.py](/c:/Tools/radan_automation/remap_feature_pens_live.py)
   - default mapping: pen `7 -> 5`
   - partial arcs on scan filter `a -> 9`
6. return through `rtl_nest_button`
7. if `Mazak Smart System Notice` appears, click `Yes`
8. confirm RADAN is back in `Nest Editor`

The reusable batch helper for this path is now:

- [batch_fix_parts_from_nest_live.py](/c:/Tools/radan_automation/batch_fix_parts_from_nest_live.py)

## Two Critical Live Fixes

### 1. Part Editor title fallback

In live testing, `Get-Process MainWindowTitle` could come back blank while RADAN was visibly in Part Editor.

That broke attach-time mode detection and caused `describe_live_session(..., require_part_editor=True)` to misread the editor mode as `unknown`.

The durable repo fix is now in [radan_com.py](/c:/Tools/radan_automation/radan_com.py):

- if `Get-Process` returns no title, fall back to visible top-level `myframe` titles for that PID
- `list_visible_radan_sessions()` also falls back to the same raw window enumeration path

### 2. Parts-list selection verification

After the first save-return cycle, `accSelect(...)` stopped advancing the visible parts-list highlight on this machine.

Observed failure mode:

- `F56139-B-20` opened and remapped correctly
- later iterations appeared to target `30`, `35`, `41`, and `8`
- but RADAN kept reopening `F56139-B-20`

The durable repo fix is now in [batch_fix_parts_from_nest_live.py](/c:/Tools/radan_automation/batch_fix_parts_from_nest_live.py):

- verify the selected row state after `accSelect(...)`
- if the target row is not visibly selected, click the row directly
- fail fast if the requested row still does not become selected

## Live Evidence

Artifacts captured during the run:

- [docs/live_pen_batch_20260424_run.json](/c:/Tools/radan_automation/docs/live_pen_batch_20260424_run.json)
- [docs/live_pen_batch_20260424_remaining.json](/c:/Tools/radan_automation/docs/live_pen_batch_20260424_remaining.json)

These checked-in artifacts are now summarized: they keep timings and before/after pen counts, but omit raw subprocess stdout and per-feature success rows.

The first JSON artifact records the initial batch attempt:

- `F56139-B-20` was genuinely fixed
- the later rows exposed the selection bug and no-op reopened `F56139-B-20`

The second JSON artifact records the corrected follow-up batch:

- `F56139-B-30`
- `F56139-B-35`
- `F56139-B-41`
- `F56139-B-8`

## Final Per-Part Results

Requested mapping:

- lines on pen `7 -> 5`
- partial arcs on pen `7 -> 9`

Observed successful remap counts:

| Part | Changed features | Save prompt | Elapsed |
| --- | ---: | --- | ---: |
| `F56139-B-20` | `155` | `Yes` | `40.500s` |
| `F56139-B-30` | `159` | `Yes` | `34.828s` |
| `F56139-B-35` | `136` | `Yes` | `35.031s` |
| `F56139-B-41` | `181` | `Yes` | `43.204s` |
| `F56139-B-8` | `110` | `Yes` | `26.781s` |

Post-remap pen summaries:

| Part | Lines after | Arcs after |
| --- | --- | --- |
| `F56139-B-20` | `1:18, 5:143` | `1:21, 9:12` |
| `F56139-B-30` | `1:6, 5:147` | `1:9, 9:12` |
| `F56139-B-35` | `1:18, 5:124` | `1:21, 9:12` |
| `F56139-B-41` | `1:18, 5:169` | `1:21, 9:12` |
| `F56139-B-8` | `1:6, 5:98` | `1:9, 9:12` |

## Timing

Successful per-part elapsed time total:

- `180.344s`

Recorded batch wall times:

- first attempt: `230.391s`
  - only `F56139-B-20` was truly processed before the selection bug was identified
- corrected remaining batch: `139.844s`

Wall-clock from first batch start to corrected batch finish:

- `07:54:15` to `08:01:31` America/Toronto
- about `436s` total

## Practical Rule

For live Nest-driven part batches on this machine:

- do not trust `accSelect(...)` alone after a save-return cycle
- verify the actual highlighted row before opening
- do not trust `Get-Process MainWindowTitle` as the sole title source for live Part Editor detection
- keep the save path on standard dialog buttons only
