# RADAN Live Geometry Repair Findings 2026-04-24

This note captures the live geometry investigation on `F56139-B-95` in the visible Part Editor session on `2026-04-24`.

The immediate goal was to understand and repair the open-geometry warning on that part without losing the proven live pen-remap workflow that had already been completed earlier in the day.

## Starting Point

- part: `F56139-B-95`
- editor: live `Part Editor`
- user hint: one line likely needs to be trimmed
- initial warning path:
  - return toward Nest
  - RADAN raises `Mazak Smart System Notice`
  - message:
    - `The geometry is not closed.`
    - `Do you want to continue to save?`

## What We Proved

### 1. Generic healing was not enough

Two live `profile_healing(...)` attempts were exercised against the open part:

- tolerance `0.0`
  - `close_small_gaps=True`
  - `merge_overlaps=True`
  - `simplify_data=True`
  - returned success
  - did **not** remove the warning
- tolerance `0.03`
  - same options
  - returned success
  - still did **not** remove the warning
  - returning toward Nest still raised the not-closed save notice

Practical conclusion:

- for this part, generic healing success is **not** proof that the actual discontinuity was fixed

### 2. The visible problem markers were around the top shoulders

In the live editor, the most useful visual cues were the tiny highlighted segments at the top shoulders.

Observed screenshots showed:

- a tiny suspect segment on the left top shoulder
- a tiny suspect segment on the right top shoulder
- RADAN presenting these as the `1/2` and `2/2` style unconnected markers

The screenshots captured during this pass live under:

- `C:\Users\athankachan\AppData\Local\Temp\codex-shot-2026-04-24_08-21-52.png`
- `C:\Users\athankachan\AppData\Local\Temp\codex-shot-2026-04-24_08-22-07.png`

### 3. The wrong delete was recoverable with Undo

One incorrect live delete happened early in the pass.

That was recovered cleanly through the normal undo command, and the part returned to the original geometry before the next investigation step.

Practical conclusion:

- if a live geometry probe goes wrong, prefer a normal `Undo` immediately instead of trying to compensate with more edits

### 4. The real line-mode commands can be targeted through menu command IDs

The Part Editor menu was enumerated live from the top-level window.

Useful IDs discovered:

- `Edit -> Restart Command` = `43`
- `Draw -> Lines -> Connected` = `313`
- `Draw -> Lines -> Unconnected` = `314`
- `Modify -> Delete` = `374`

Practical conclusion:

- use real menu command IDs instead of guessing at the left-side drafting strip when the current tool state matters

### 5. `TS0/TE0` endpoint fields are real, but they were not readable in the contaminated draw state

The interop surface does expose true line endpoint properties:

- `TS0X`
- `TS0Y`
- `TE0X`
- `TE0Y`

That is already visible in:

- [INTEROP_SURFACE_DUMP.md](/c:/Tools/radan_automation/INTEROP_SURFACE_DUMP.md)
- [watch_live_session.py](/c:/Tools/radan_automation/watch_live_session.py)

However, during this live pass:

- `scan('l', ...)` returned line identities and `S0X/S0Y`
- but `TS0/TE0` stayed `0.0`
- `find_xy_identifier(...)` and `fed_edit_feature(...)` did not surface richer endpoint data while the editor was still effectively sitting in line-draw state

Practical conclusion:

- the endpoint properties are promising
- but they should be captured from a neutral marked-feature state, **before** entering a live draw workflow

### 6. A stale screen-coordinate approach is not safe

The RADAN window shifted during the session.

That invalidated earlier click assumptions and contributed to misses.

Practical conclusion:

- do not reuse stale screen coordinates
- re-query live control rectangles each time
- the top-right Part Editor `Nest` control was re-found live as:
  - control text: `rtl_nest_button`

## What Failed Or Became Unreliable

### 1. Blind redraw by pixels was the wrong abstraction

A redraw attempt was made from screen observations rather than from exact captured model-space endpoints.

That was the wrong approach for this geometry.

The user correction was right:

- for inserting a single replacement segment, the tool should be `Unconnected`, not `Connected`

### 2. Active draw mode contaminated later automation

Once the session was sitting in line mode:

- prompt reads could drift
- `Pattern mode escaped` was not enough to prove the visible tool state was truly neutral
- even after `Restart Command` / `Esc`, the screenshot could still show:
  - `Connected Lines: Indicate start point`

Practical conclusion:

- do not trust `Mac.PRS` alone once the session has been through an interactive draw command
- always verify the visible tool mode in the actual window

### 3. Feature marking around the shoulder collapsed onto the currently selected feature

When trying to re-mark likely top-shoulder neighbors with `find_xy_identifier(...)`, the active feature state repeatedly collapsed onto:

- `FI0 = /symbol editor/_47`

That made the raw endpoint readout unusable in that state.

### 4. Save-copy probing from the dirty live part was not a safe fallback in this pass

An attempt to save a copy of the active document timed out and later surfaced a save dialog that the user dismissed manually.

Practical conclusion:

- do not assume `SaveCopyAs` is a safe background geometry-inspection fallback once the live part is already in a dirty interactive state

## Useful Geometry Signal Collected Anyway

Even though exact `TS0/TE0` endpoints were not recovered cleanly, the line scan around the top shoulder region still exposed suspicious duplicate line entries.

Notable duplicate or near-duplicate shoulder-region scan rows:

- `/symbol editor/_19` and `/symbol editor/_21`
  - both at `S0X=55.833456`, `S0Y=43.5878215`
- `/symbol editor/_25` and `/symbol editor/_26`
  - both at `S0X=50.833456`, `S0Y=42.4244355`
- `/symbol editor/_44` and `/symbol editor/_45`
  - both at `S0X=56.621842`, `S0Y=42.2019885`

Practical conclusion:

- the warning may not be a simple missing segment
- overlapping or duplicate shoulder geometry is a strong candidate and should be inspected before any redraw

## Safe Rule For Next Time

For live geometry repair on parts like `F56139-B-95`:

1. start from a clean freshly opened part
2. do **not** enter draw mode until the exact neighboring feature IDs and endpoints are captured
3. capture and persist:
   - feature IDs
   - `S0X/S0Y`
   - if available, `TS0/TE0`
4. if a single replacement segment is needed, use `Unconnected`, not `Connected`
5. if an interactive attempt goes sideways, prefer:
   - `Undo`
   - or discard/reopen the part from Nest
6. do not trust stale pixel coordinates after the RADAN window moves

## Current Status At Pause

At the end of this pass:

- the part had been manually undone back to its original visible geometry
- the open-geometry warning still existed
- the working knowledge was:
  - the top shoulders are the right area to inspect
  - generic healing alone is insufficient
  - duplicate shoulder-region lines are plausible root-cause candidates
  - next attempt should begin from a fresh reopen and a neutral non-draw state
