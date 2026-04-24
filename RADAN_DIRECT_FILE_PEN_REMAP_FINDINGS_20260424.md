# RADAN Direct File Pen Remap Findings 2026-04-24

This note captures the direct `.sym` DDC edit path used after live COM automation proved unsafe for an already-open Nest session.

## What Worked

- The target `.sym` files are XML compound documents with a `<RadanFile extension="ddc">` CDATA block.
- In the tested symbols, DDC `G` records matched line counts and DDC `H` records matched arc counts from the prior live scan workflow.
- Field index `8` in those records held the logical pen number.
- Direct remap rule:
  - line records: pen `7 -> 5`
  - arc records: pen `7 -> 9`

Reusable utility:

- [remap_feature_pens_file.py](/c:/Tools/radan_automation/remap_feature_pens_file.py)

## Important Caveat

Direct file edits update the geometry records, but they do not make RADAN regenerate derived state.

Observed after a successful direct edit:

- the Nest warning/status can remain stale
- Nest thumbnails can remain stale
- opening the symbol from the parts list and saving it refreshes the derived state

Practical rule:

- use direct file remap for the geometry pen change
- then do a RADAN open/save refresh pass when Nest warnings, status, thumbnails, or other cached views need to update
- do not manually flip `Workflow status` to clear the flag; that is RADAN's validation result and spoofing it could hide a real geometry problem

## Follow-Up Observations

- The seven-part Nest project path for the tested batch was operator-confirmed as:
  - `L:\BATTLESHIELD\F-LARGE FLEET\PLAYGROUND\PLAYGROUND\PLAYGROUND.rpd`
- The earlier Paint Pack project file was an incorrect inference; it only referenced `F56139-B-95` from the visible seven-row list.
- Future live project targeting should use documented `Mac.prj_get_file_path()` before inspecting `.rpd` contents, rather than guessing from symbol folders or recent files.
- The operator-confirmed `PLAYGROUND.rpd` stores the seven symbol paths and nest membership, but no embedded per-symbol thumbnails were found there.
- Touching filesystem `LastWriteTime` on the modified `.sym` files does not update the internal RADAN XML metadata fields such as `Modified`, `Workflow status`, or `File size`.
- A manual RADAN open/save on `F56139-B-1.sym` changed its internal `Workflow status` from `3 - Part geometry is not closed` to `1 - OK` and rewrote its thumbnail block.

## Safety Note

Do not use `Radraft.Application.Quit()` as cleanup while a user-owned RADAN session is open. On this machine, requesting a new COM automation instance can still bind back to the visible `RADRAFT.exe` process.
