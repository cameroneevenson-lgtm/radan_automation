# RADAN Live Nest Findings - 2026-04-21

This note captures what was proven while driving an attachable visible RADAN Nest session on this machine.

Repo: `c:\Tools\radan_automation`

## Bottom Line

The live Nest Editor now has a practical automation story here:

- the visible Nest session can be attachable through the managed/PowerShell bridge
- Nest layout bounds can be read through `PCC_PATTERN_LAYOUT` plus `ElfBounds(...)`
- Nest mode changes are most reliably detected through `GUISubState`
- top-row Nest mode buttons can be found and clicked through Windows UI Automation plus a foregrounded RADAN window

## Proven Nest Mode Signal

In local live testing, the attached Nest session stayed at:

- `GUIState = 4`

while `GUISubState` changed as follows:

- `14` = modify
- `7` = profiling
- `11` = order

Important note:

- `Mac.PRS` was **not** a reliable discriminator for these Nest modes in local testing
- the prompt text often stayed the same while `GUISubState` changed

## Proven Nest Pattern / Bounds Signal

For the attachable visible Nest session, the bridge and wrapper reported:

- `PCC_PATTERN_LAYOUT = "/layout"`
- `CUP = "/layout"`
- `COP = "/layout"`

and `ElfBounds("/layout", ...)` returned stable layout bounds.

That is why `live_session_bridge.ps1` now treats Nest Editor sessions differently from Part Editor sessions:

- Part Editor -> `PART_PATTERN`
- Nest Editor -> `PCC_PATTERN_LAYOUT`

## Proven UI Controls

Windows UI Automation inspection of the live RADAN window exposed the top-row Nest mode strip as custom Win32 controls.

The important control names found were:

- `rtl_nest_modify_button`
- `rtl_nest_profile_button`
- `rtl_nest_order_button`

paired with bitmap controls:

- `big_button_nest_modify.bmp`
- `big_button_profile.bmp`
- `big_button_order.bmp`

These controls are custom panes/buttons rather than standard invokable controls, so simple UIA `InvokePattern` calls were not available.

## Proven Live Mode Changes

The following mode changes were proven by automation:

- `order -> profiling`
  - succeeded by foregrounding the RADAN window and clicking `rtl_nest_profile_button`
- `profiling -> modify`
  - succeeded by foregrounding the RADAN window and clicking `rtl_nest_modify_button`

The corresponding live confirmation came from:

- `GUISubState`
- main window title

Observed title behavior:

- `Order Mode` appeared explicitly in the window title while `GUISubState = 11`
- the title returned to `Nest Editor` when the session moved back to `profiling` / `modify`

## Failed / Weak Paths

One low-risk command path was tested and should **not** be treated as a working mode switch:

- `mac2('\!')`

Observed behavior in `order` mode:

- RADAN accepted the command and returned success
- the prompt string was cleared
- `GUISubState` stayed at `11`

Interpretation:

- the escape command may dismiss an order-mode prompt layer
- it did **not** exit `order` mode on this machine

So the current preferred mode-switch path is:

- UI control click on the proven top-row Nest mode buttons

not:

- guessed keystrokes

## Useful Repo Tools

- [watch_live_session.py](/c:/Tools/radan_automation/watch_live_session.py)
  - Transition-only watcher for `GUIState`, `GUISubState`, prompt text, pattern paths, and selected MAC fields.
- [probe_live_session.py](/c:/Tools/radan_automation/probe_live_session.py)
  - Read-only probe for PID, title, mode, backend, pattern, and bounds.
- [live_session_bridge.ps1](/c:/Tools/radan_automation/live_session_bridge.ps1)
  - Managed bridge that now supports Nest layout pattern/bounds reporting.

Example watcher usage:

```powershell
python .\watch_live_session.py --seconds 30 --interval 0.2
```

## Current Best Conclusion

For live Nest automation on this workstation:

- use `GUISubState` as the main machine-readable mode signal
- use `PCC_PATTERN_LAYOUT` and `ElfBounds(...)` for Nest layout probing
- use top-row Nest mode button clicks for mode changes that are not exposed as stable typed APIs
- do not assume a successful MAC escape command means the session actually left `order` mode

## Sandbox Level Note

The successful automation paths split cleanly by how much desktop access they require:

- attach / probe level
  - `describe_live_session()`
  - `probe_live_session.py`
  - `watch_live_session.py`
  - These depend on a usable attachable RADAN session and COM/managed bridge access, but they do not inherently require mouse-driven UI interaction.
- desktop interaction level
  - clicking `rtl_nest_profile_button`
  - clicking `rtl_nest_modify_button`
  - These required access to the real interactive Windows desktop session so the automation could foreground the RADAN window and drive custom Win32 controls.

Practical implication:

- a tighter sandbox that still allows filesystem/process work may be enough for read-only attach and state inspection
- a sandbox that blocks focus changes, mouse movement, or direct desktop interaction should be expected to fail for the proven live mode-switch path
