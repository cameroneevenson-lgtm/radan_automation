# RADAN Headless Findings - 2026-04-15

This note captures what we confirmed about using RADAN in a hidden automation process, independent of any visible Nest Editor window.

## Bottom Line

Yes, a hidden RADAN automation instance can do real work.

Confirmed on this machine:

- Start a hidden `Radraft.Application` automation instance.
- Create a new drawing.
- Save the drawing to disk.
- Export a flat PNG thumbnail from the current drawing.
- Re-open that saved drawing in the same hidden instance.
- Close the document.
- Quit the automation process cleanly.

## Verified Headless Flow

Script:

- [try_radan_headless_save.py](/c:/Tools/radan_automation/try_radan_headless_save.py)

Observed behavior:

- A hidden automation instance was launched with `Visible=False`.
- `NewDrawing(False)` succeeded.
- `SaveAs("..._tmp_headless_probe_2.rpd")` did **not** create a file with the exact base path.
- RADAN created the actual file as:
  - `c:\Tools\radan_automation\_tmp_headless_probe_2.rpd.drg`
- Re-opening that actual saved path with `OpenDrawing(..., read_only=True)` succeeded.
- The reopened document reported:
  - `document_type=1`
  - `dirty=False`
- `Quit()` closed the hidden automation instance cleanly.

## Verified Output Flow

Script:

- [try_radan_headless_outputs.py](/c:/Tools/radan_automation/try_radan_headless_outputs.py)

Observed behavior:

- A hidden automation instance was launched with `Visible=False`.
- `Mac.license_info()` returned a valid holder and server code.
- `Mac.report_type("PNG")` returned `13`.
- `NewDrawing(False)` succeeded.
- `SaveAs("..._tmp_headless_output_probe.rpd")` created:
  - `c:\Tools\radan_automation\_tmp_headless_output_probe.rpd.drg`
- `Mac.flat_thumbnail("..._tmp_headless_output_probe.png", 640, 480)` returned `True`.
- The PNG thumbnail file was created successfully.
- The active document still reported:
  - `document_type=1`
  - `dirty=False`
- `Quit()` closed the hidden automation instance cleanly.

## Practical Meaning

For batch or service-style automation, we probably do **not** need to attach to the already-open RADAN UI.

The useful model is:

1. Launch a hidden automation-owned RADAN process.
2. Perform drawing/project operations there.
3. Save outputs to disk.
4. Quit the hidden process when finished.

## Current Wrapper Support

The Python wrapper in [radan_com.py](/c:/Tools/radan_automation/radan_com.py) now supports:

- `active_document_info()`
- `close_active_document(discard_changes=True)`
- `save_active_document()`
- `save_active_document_as(path)`
- `save_copy_of_active_document_as(path, options_file_path="")`
- `mac.license_info()`
- `mac.license_available(name)`
- `mac.license_confirm(name)`
- `mac.license_request(name)`
- `mac.report_type(file_type_name)`
- `mac.keystroke(command)`
- `mac.flat_thumbnail(path, width, height)`
- `mac.model_thumbnail(path, width)`
- `mac.output_project_report(report_name, file_path, file_type)`
- `mac.output_setup_report(report_name, file_path, file_type)`

## Useful Probes

- [try_radan_headless.py](/c:/Tools/radan_automation/try_radan_headless.py)
  - Minimal hidden-instance create/close probe.

- [try_radan_headless_save.py](/c:/Tools/radan_automation/try_radan_headless_save.py)
  - Hidden-instance create/save/re-open/close probe.

- [try_radan_headless_outputs.py](/c:/Tools/radan_automation/try_radan_headless_outputs.py)
  - Hidden-instance create/save/export-thumbnail/close probe.

- [inspect_radan_api_xml.py](/c:/Tools/radan_automation/inspect_radan_api_xml.py)
  - Search the shipped XML docs for `IMac` and other documented interfaces.

## Current Best Conclusion

The unresolved problem is still "attach to the already-open visible RADAN UI session".

But the more important practical question now has a good answer:

- Hidden RADAN automation is viable.
- It can create and persist drawings.
- It can reopen and inspect saved outputs.
- It can be treated as a separate batch-processing worker.
