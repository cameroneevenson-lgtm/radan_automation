# RADAN Live Pen Remap Findings 2026-04-23

This note captures the pen-remap workflow we proved live against an attached RADAN Part Editor session.

## What Worked

The successful path was mixed `API` + keystroke, not keystrokes-only:

1. use `Mac.scan(...)` to walk candidate features
   - in live testing, `scan(...)` only armed the iterator
   - call `next()` before reading `FI0` / `FP0` / `S0X` / `S0Y`
2. read the current feature identity and pick point from:
   - `FI0`
   - `FP0`
   - `S0X`
   - `S0Y`
3. call `Mac.find_xy_identifier(identifier, x, y)` to re-mark that exact feature
4. call `Mac.rfmac('e\\?P,<pen>?')` through the wrapper as `mac.keystroke(...)`

## What Did Not Work

Calling `rfmac('e\\?P,<pen>?')` directly from raw scan state did not stick.

Observed live prompt:

- `First find a feature`

That means scan state alone is not enough to satisfy the edit-mode pen command. The explicit `find_xy_identifier(...)` re-mark step is required.

There was also a second trap:

- reading `FI0` immediately after `scan(...)` pulled a stale prior feature in live testing
- the reliable iterator shape was `scan(...)`, then `while next(): ...`

## Practical Rule

For live pen changes in Part Editor:

- use `scan(...)` for deterministic iteration and candidate collection
- do not mutate the part while the scan is being used as the only selection state
- re-mark each target feature with `find_xy_identifier(...)`
- then run `rfmac('e\\?P,<pen>?')`

## Proven Example

One live feature changed successfully with:

- identifier: `/symbol editor/_19`
- source pen: `7`
- point: `89.64375, 64.64827`
- command: `e\\?P,5?`

The follow-up rescan confirmed the feature pen changed from `7` to `5`.

## Generic Utility

The reusable repo utility for this workflow is now:

- [remap_feature_pens_live.py](/c:/Tools/radan_automation/remap_feature_pens_live.py)

Example shape:

```powershell
C:\Tools\.venv\Scripts\python.exe .\remap_feature_pens_live.py --expected-process-id 22704 --source-pen 7 --target-pen 5 --filter-target a=9
```

That example means:

- remap pen `7` to pen `5` by default
- but remap scanned arc features on filter `a` to pen `9`

## Caution

Close modal dialogs such as `Edit Common Properties` before running the live remap utility.

The RADAN PDF already warns that COM/MAC calls may be rejected while modal dialogs are open, and that matches the live behavior risk here.
