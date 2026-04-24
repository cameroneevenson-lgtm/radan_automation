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

## Safety Note

Do not use `Radraft.Application.Quit()` as cleanup while a user-owned RADAN session is open. On this machine, requesting a new COM automation instance can still bind back to the visible `RADRAFT.exe` process.
