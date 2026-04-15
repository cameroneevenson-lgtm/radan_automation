# Keystroke Reference Extract

First-pass extract of keystroke-oriented help topics from the installed RADAN CHM help.

Primary sources:

- `C:\Program Files\Mazak\Mazak\help\manuals\radraft.chm`
- `C:\Program Files\Mazak\Mazak\help\manuals\radanapi.chm`

Extraction note:

- `pychm` did not build successfully in the current Python `3.12` environment because it required Microsoft C++ Build Tools.
- `pylibmspack` worked and could read both CHM archives directly.

This file is not yet a normalized full keystroke table. It is a curated extract of:

- the CHM entry points for keystroke help
- representative topic pages
- concrete command tokens found in those topics
- topic paths worth mining further

## Core Entry Points

### API Help

From `radanapi.chm`:

- `/htm/Objects/MacObject/macobjectkeystrokes.htm`
- `/htm/Objects/MacObject/macobjectkeystrokesvba.htm`
- `/htm/Objects/MacObject/macobjectkeystrokescsharp.htm`

These cover:

- `mac2()`
- `fmac2()`
- `rfmac()`
- command-string syntax
- argument escaping
- pattern command examples

### User Help

From `radraft.chm`:

- `/htm/Introduction/usingkeystrokecommands.htm`
- `/htm/Drafting aids/on.screenhelpforkeystrokes.htm`
- `/htm/Finding features/usingkeystrokestofindfeatures.htm`

These cover:

- how keystrokes are entered in the UI
- the on-screen `?` help mechanism
- grouped feature-finding topics

## High-Value Topic Pages

### Drawing

- `/htm/Drafting/Drawing lines/keystrokes.drawinglines.htm`
- `/htm/Drafting/Drawing arcs/keystrokes.drawingarcs.htm`
- `/htm/Drafting/Putting centre-line crosses in the drawing/keystrokes.addingacentre.linecross.htm`
- `/htm/Adding text/Introduction to adding text/keystrokes.addingtext.htm`
- `/htm/Drafting/Adding hatching to the drawing/keystrokes.addinghatching.htm`

### Editing

- `/htm/Editing features/Editing lines and arcs/keystrokes.editinglinesandarcs.htm`
- `/htm/Editing features/Editing lines and arcs/keystrokes.editingprofilesoflinesandarcs.htm`
- `/htm/Editing features/Editing features/keystrokes.editingfeatures.htm`
- `/htm/Editing features/Editing text/keystrokes.editingtextproperties.htm`
- `/htm/Editing features/Editing dimensions/keystrokes.editingdimensionproperties.htm`

### Finding And Selection

- `/htm/Finding features/Using keystrokes to find features/keystrokes.findinganyfeature.htm`
- `/htm/Finding features/Using keystrokes to find features/keystrokes.findinglines.htm`
- `/htm/Finding features/Using keystrokes to find features/keystrokes.findingarcs.htm`
- `/htm/Finding features/Using keystrokes to find features/keystrokes.findinglinesandarcs.htm`
- `/htm/Finding features/Using keystrokes to find features/keystrokes.findingtext.htm`
- `/htm/Finding features/Using keystrokes to find features/keystrokes.findingdimensions.htm`
- `/htm/Finding features/Using keystrokes to find features/keystrokes.findinghatching.htm`
- `/htm/Finding features/Using keystrokes to find features/keystrokes.findingsymbols.htm`
- `/htm/Finding features/Using keystrokes to find features/keystrokes.selectingfeaturesusingawindow.htm`
- `/htm/Finding features/Using keystrokes to find features/keystrokes.tailoringfeatureselectionwithfilters.htm`

### Patterns And Symbols

- `/htm/Patterns/Working with patterns/keystrokes.patternmode.htm`
- `/htm/Patterns/Pattern manipulation/keystrokes.manipulatingpatterns.htm`
- `/htm/Patterns/Displaying patterns in a drawing/keystrokes.displayingpatternsinthedrawing.htm`
- `/htm/Symbols and the Part Editor/Recalling symbols/keystrokes.recallingasymbol.htm`
- `/htm/Symbols and the Part Editor/Fixing and realising symbols/keystrokes.fixingandrealisingsymbols.htm`
- `/htm/Symbols and the Part Editor/Adding step & repeats of symbols/keystrokes.addingstep.repeatsalongalineorarc.htm`

### View / Prompt / Cursor

- `/htm/Drafting aids/Controlling the view of the drawing/keystrokes.zoominginandoutofthedrawing.htm`
- `/htm/Drafting aids/Controlling the view of the drawing/Panning across the drawing/keystrokes.panningacrossthedrawing.htm`
- `/htm/Drafting aids/Controlling the view of the drawing/Redrawing the picture/keystrokes.redrawingthepicture.htm`
- `/htm/Drafting aids/Using locations in drafting/keystrokes.locationcommands.htm`
- `/htm/Drafting aids/Getting information about the drawing/Querying aspects of the drawing/keystrokes.queryingthedrawing.htm`

## Concrete Commands Found In The CHM

### Drawing Lines

From `keystrokes.drawinglines.htm`:

- `d`
  - draw connected line / finish line between two points
- `s`
  - establish start point
- `"`
  - draw rectangle from two corner points
- `*`
  - draw normal
- `7`
  - line tangent
- `6`
  - chamfer

### Drawing Arcs

From `keystrokes.drawingarcs.htm`:

- `c`
  - mark arc centre
- `s`
  - mark start point
- `d`
  - complete circle or arc in center-based flows
- `o`
  - three-point arc completion flow
- `~`
  - set arc direction before final point
- `&`
  - arc tangent command

### Finding Features

From the `Using keystrokes to find features` pages:

- `f`
  - find any feature
- `l`
  - restricted line find
- `L`
  - unrestricted line find
- `a`
  - restricted arc find
- `A`
  - unrestricted arc find
- `t`
  - find text
- `2`
  - find dimension
- `H`
  - find hatching
- `9`
  - find symbol
- `.`
  - find centre-line cross
- `w`
  - rectangular window selection
- `Ctrl+f`
  - selection filter control

### Pattern Operations

From `keystrokes.patternmode.htm` and `keystrokes.manipulatingpatterns.htm`:

- `Ctrl+p`
  - enter pattern mode
- `o`
  - open pattern
- `x`
  - delete pattern
- `s`
  - save and remove pattern from drawing
- `S`
  - save and retain pattern in drawing
- `m`
  - move pattern
- `~`
  - mirror pattern
- `j`
  - jump pattern to cursor
- `|`
  - add pattern documentation

### Editing Lines And Arcs

From `keystrokes.editinglinesandarcs.htm`:

- `e`
  - enter edit mode
- `x`
  - partial delete
- `J`
  - split line or arc
- `d`
  - extend line or arc when in edit flow
- `%`
  - merge1
- `^`
  - merge2
- `i`
  - intersection helper during partial delete flow

### View / Prompt / General Help

From the drafting-aids topics:

- `?`
  - on-screen help for keystrokes
  - double `?` lists commands for the current mode
- `r`
  - full-size redraw
- `z`
  - zoom redraw
- `Ctrl+r`
  - pen redraw
- `Ctrl+z`
  - pen zoom redraw
- `W`
  - panning mode
- `q`
  - query command

### Other Useful Commands

From the symbol and drafting topics:

- back-quote
  - add centre-line cross
- `T`
  - add text
- `j`
  - jump copy/cursor object workflow
- `0`
  - recall symbol
- `Space`
  - fix symbol in drawing
- `)`
  - realise symbol
- `8`
  - add parallel feature / profile

## On-Screen Command Discovery

The CHM confirms a very useful manual discovery trick:

- `?`
  - ask for help with the next command
- `??`
  - list all available commands in the current mode

This is useful alongside automation research because it gives mode-specific command lists directly inside RADAN.

## Relationship To The API

The CHM-backed keystroke topics support the split in [API_VS_KEYSTROKE_MATRIX.md](</c:/Tools/radan_automation/API_VS_KEYSTROKE_MATRIX.md>):

- direct API for deterministic lifecycle, export, scan, ELF, feature-editor, and machine-level calls
- keystrokes for interactive drafting, finding, pattern mode, and edit-mode workflows

## Gaps

This extract is still not a normalized full reference table.

Still missing:

- complete tooling-mode topic extraction
- complete order-mode keystroke extraction
- per-command safety classification for `rfmac()` vs `mac2()`
- tested status for each command token

## Next Good Artifact

The next useful file would be `COMMAND_TEST_MATRIX.md` with columns like:

- command token
- topic path
- mode
- direct API alternative
- recommended path (`API`, `mac2`, `rfmac`, `unknown`)
- tested status
- notes
