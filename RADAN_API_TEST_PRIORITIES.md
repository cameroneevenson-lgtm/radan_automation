# RADAN API Test Priorities

Source reviewed: `docs/Radan API Programming Help.pdf` (116 pages, 2026-02-18).

This is a ranked backlog of RADAN API functions worth testing next. The ranking favors:

- eliminating path guesses and live-session ambiguity
- clearing or explaining stale Nest warnings, thumbnails, and workflow status
- replacing fragile keystroke/UI automation with typed calls
- building safe headless or automation-owned workflows before touching user-owned sessions

## Coverage Notes From The Full Pass

- Pages 3-7: `Application` and `Document` lifecycle: open, save, close, process id, visibility, interactivity.
- Pages 8-28: `Mac` setup, licensing, UI/prompt state, direct MAC command execution, current drawing/pattern/session properties.
- Pages 29-39: scan/find/latch APIs plus feature properties such as `FI0`, `FP0`, `PRF_CLOSED0`, and `SD0`.
- Pages 40-42: feature-editor APIs: `fed_*` can edit typed properties in batches.
- Pages 42-51: `elf_*` geometry analysis/manipulation plus `profile_extraction` and `profile_healing`.
- Pages 52-58: attributes, Part Editor attrs, and `fla_thumbnail`.
- Pages 59-72: 3D import/export/unfold/object info, automatic tooling, embedded part removal, and single-part nesting.
- Pages 73-87: multi-part nesting schedule, Nest Project APIs, finish nesting, extents, setup/project reports, remnants/offcuts/scrap.
- Pages 88-100: order/blockmaker/verifier, machine configuration, strategy, tool library, station library, sheet stock, and support ZIP generation.
- Pages 101-114: MAC language access, `MacFiles`/`MacCommands`, menus, and system-data file access.

## Ranked Test Backlog

| Rank | Function(s) | PDF Page(s) | Why Test Next | First Test Shape |
| ---: | --- | --- | --- | --- |
| 1 | `Mac.prj_get_file_path()` | 80 | Prevents the exact failure mode where we inferred the wrong `.rpd` path. It should be the canonical active Nest Project locator. | Late-bound live read-only probe against an open Nest project; verify empty string when no project is open. Note: documented in the PDF but not currently present in `INTEROP_SURFACE_DUMP.md`, so first prove callable through the bridge. |
| 2 | `Mac.prj_is_open()`, `Mac.prj_is_edited()` | 80 | Gives a safe guard before reading or saving project state. Useful before any refresh or `.rpd` inspection. | Read-only probe in no-project, open-clean-project, and edited-project states. |
| 3 | `Application.OpenSymbol(...)`, `Application.SaveActiveDocument()`, `Document.Save()`, `Document.Close(...)` | 4, 6 | Most likely route for the stale-warning/stale-thumbnail issue after direct `.sym` edits. Manual open/save already cleared `Workflow status` on one file. | Automation-owned refresh harness on copied `.sym` fixtures; compare internal `Modified`, `Workflow status`, file size metadata, and thumbnail block before/after. |
| 4 | `Application.ProcessID`, `Application.Visible`, `Application.Interactive`, `Application.Quit()` | 5 | Needed to stop automation from closing a user-owned RADAN session again. `Quit()` must only run on a positively owned PID. | Headless process-ownership test that proves PID capture before and after create/open/quit, plus a negative live-session guard. |
| 5 | `Mac.elf_closed(pattern, graphicsMode)` | 44 | Direct candidate for "is this part geometry closed?" without spoofing `Workflow status`. Could explain the RADAN warning before a save. | On known good/open profile copied symbols; test with `PART_PATTERN`, `ELF_CACHE_ID`, and options. |
| 6 | `Mac.elf_set_option("all_pens" / "all_linetypes", value)` | 48 | `elf_closed` ignores configured nesting pens and non-full linetypes by default. Our pen remap work depends on understanding that filter behavior. | Toggle options around `elf_closed` on controlled symbols with ignored pens and dashed linetypes; restore prior values. |
| 7 | `Mac.run_verifier_silently()`, `Mac.run_verifier()` | 89 | Possible typed validation route, but requires Verifier mode. It may be the proper way to compute status rather than editing XML. | Mode-gated probe only after we can enter/own Verifier mode; record return codes and whether symbol metadata changes. |
| 8 | `Mac.profile_healing_with_timeout(...)`, `Mac.profile_healing(...)` | 51 | Best documented cleanup candidate before save/validate; already wrapper-covered but needs real RADAN behavior on copied parts. | Headless copy test with tiny gaps/overlaps; assert geometry and metadata changes are expected. |
| 9 | `Mac.profile_extraction(...)` | 50 | Useful to isolate closed profiles and possibly normalize direct-edited parts before validation. | Run on copied symbols and compare feature counts/bounds before and after. |
| 10 | `Mac.scan(...)`, `next()`, `rewind()`, `end_scan()`, feature properties `FI0`, `FP0`, `FT0`, `PRF_CLOSED0`, `SD0` | 29, 35-39 | Core inspection layer for every geometry and pen-change workflow. Live scan is proven, but we should harden the contract and capture closure/profile properties. | Headless and live-read-only scan fixtures; prove iterator semantics and property freshness after `next()`. |
| 11 | `Mac.find_identifier(...)`, `Mac.find_xy_identifier(...)`, `Mac.find()` | 30 | Selection/remarking was the missing piece for live pen remap. More deterministic selection lets us reduce keystroke state risk. | Unit wrapper plus copied-symbol live probe for feature id, point, and coordinate selection. |
| 12 | `Mac.fed_batch_begin()`, `fed_clear_properties()`, `fed_edit_feature(...)`, `fed_edit_profile_features(...)`, `fed_batch_end()` | 40-42 | High-value replacement for `rfmac('e\\?P,...')` if `FED_*` properties expose the needed feature edits. | Determine whether pen/line/tooling properties are writable through `FED_*`; if not, document the limit and keep keystroke fallback. |
| 13 | `Mac.pattern_bounds2(...)`, `Mac.elf_bounds(...)`, `Mac.elf_properties(...)` | 35, 43, 47 | Gives deterministic before/after geometry checks for remap, healing, nesting, and thumbnail framing. | Compare against known rectangles/arcs and against direct `.sym` DDC bounds. |
| 14 | `Mac.fla_thumbnail(...)` | 58 | Already exports external images, but we need to know whether it can refresh or reproduce stale Nest thumbnails. | Compare external thumbnail output before/after open/save; verify it does not claim to update embedded symbol thumbnail state. |
| 15 | `Mac.ped_get_attrs2(...)`, `Mac.ped_set_attrs2(...)`, `Mac.ped_attrs_handle()` | 57-58 | Part Editor metadata matters for nesting: material, strategy, thickness, units, orientation. | Read-only attr probe on current copied symbols; then write/revert on temp copies. |
| 16 | `Mac.prj_open(file)`, `Mac.prj_save()`, `Mac.prj_close()` | 80-81 | Needed for real project lifecycle automation once path discovery is proven. May refresh project-level state, but probably not symbol-derived status by itself. | Open a copied `.rpd` in an automation-owned session, save, close, and diff project XML. |
| 17 | `Mac.prj_add_part()`, `prj_remove_all_parts()`, `prj_clear_part_data()`, `prj_set_numeric_property(...)` | 78-83 | Potential replacement for UI-driven parts import. Lets us build controlled test projects from symbol paths. | Create a throwaway project, add one copied symbol with explicit quantity/material/thickness/orientation, save, inspect `.rpd`. |
| 18 | `Mac.prj_add_sheet()`, `prj_remove_all_sheets()`, `prj_clear_sheet_data()` | 78-84 | Needed with `prj_add_part` to make complete reproducible nesting fixtures. | Add one sheet to a throwaway project and assert saved sheet properties. |
| 19 | `Mac.prj_new_project()` and `PRJ_PROJECT_*` properties | 80, 82 | Headless project creation would remove a large amount of UI setup. | Temp-folder project creation using only copies; verify created folders and `.rpd` path. |
| 20 | `Mac.nst_start_adding_parts()`, `nst_add_part()`, `nst_add_sheet()`, `nst_finish_adding_parts()`, `nst_set_path(...)` | 76-77 | Schedule-level alternative to Nest Project APIs; may be better for open Nest Editor workflows. | Add copied part/sheet to an empty schedule and compare UI list plus saved schedule/project contents. |
| 21 | `Mac.lay_run_nest(...)`, `lay_clear_properties()`, `lay_calculate_utilisations(...)`, `lay_get_utilisation(...)` | 72-76 | Core nesting automation path. Important after project/schedule setup is deterministic. | Single small part and sheet fixture; assert nonzero placement/utilisation result. |
| 22 | `Mac.nst_calculate_extents(...)` and `NEST_*` properties | 85 | Lets automation reason about actual sheet/nest bounds instead of window or screenshot guesses. | Run after known nest; compare `NEST_*` values to `elf_bounds(PCC_PATTERN_LAYOUT)`. |
| 23 | `Mac.pfl_finish_nesting(...)` | 84 | Could be the typed "refresh/save annotation and parts list" route for stale Nest views. | Test on copied Nest project after symbol refresh; verify annotation, schedule, project state, and thumbnails. |
| 24 | `Mac.prj_output_report(...)`, `Mac.stp_output_report(...)`, `report_type(...)` | 81, 85-86 | Reports are a good black-box verification artifact for projects and nests. Wrapper exists, real workflow pending. | Generate PDF/CSV reports from throwaway projects; assert output and error message behavior. |
| 25 | `Mac.pfl_get_default_mdb_strategy(...)`, `pcc_get_current_mc_id()`, `get_num_machines()`, `machine_type(...)`, `bki_*` | 89-90 | Strategy and machine discovery are needed to populate part/project attrs correctly. | Read-only machine/strategy probe; compare to current RADAN UI/system data. |
| 26 | `Mac.ssm_num_mat()`, `ssm_get_mat(...)`, `ssm_num_thick(...)`, `ssm_get_thick(...)`, `ssm_num_size(...)`, `ssm_get_size(...)` | 97-100 | Sheet-stock discovery could prevent bad project fixtures and material mismatches. | Read-only stock inventory probe for the current machine; no writes. |
| 27 | `Mac.prj_output_report(...)` plus `fla_create_zip_embed_silent(...)` | 81, 100 | Support artifacts and project reports are useful diagnostics when RADAN state diverges from file edits. | Generate into temp folder only; confirm no project mutation. |
| 28 | `Mac.att_current_dwg()`, `att_load(...)`, `att_get_value(...)`, `att_set_value(...)`, `att_update_file(...)` | 52-57 | Attribute files may expose more metadata than direct XML inspection. Lower than `ped_*` because writes are broader. | Read-only attr dump first; write tests only against temp copies. |
| 29 | `Mac.elf_copy_geometry(...)`, `elf_intersection(...)`, `elf_union(...)`, `elf_subtraction(...)`, `elf_partition(...)` | 45-50 | Useful for deeper geometry QA, but not required to solve the current refresh/status issue. | Controlled synthetic shapes in a new drawing, with image/bounds verification. |
| 30 | `Mac.mfl_read_model_default(...)`, `mfl_auto_unfold(...)`, `mfl_object_info(...)`, `mfl_set_material(...)`, `mfl_set_thickness(...)`, `mfl_write_*` | 59-70 | Valuable if 3D model import/unfold becomes part of automation. Not on the current 2D Nest refresh path. | Separate 3D fixture track with known CAD samples. |
| 31 | `Mac.apr_auto_add_part_rems(...)`, `pfl_auto_tool(...)`, `pfl_get_run_time(...)` | 71-72 | Manufacturing automation value, but requires stable material/machine/part setup first. | Run only after strategy and fixture project tests are stable. |
| 32 | `Mac.ord_run_blockmaker_silently()`, `ord_run_blockmaker()` | 88-89 | Important for order mode, but outside the immediate symbol/project refresh problem. | Order-mode gated fixture with copied nest output. |
| 33 | `Mac.mtm_*`, `stm_*` tool and station library functions | 91-97 | Read-only tool inventory may be useful later; write methods like `mtm_save()` carry system-data risk. | Read-only probes only; no tool-library writes until explicitly needed. |
| 34 | `Mac.Execute(...)`, `GetNumber(...)`, `GetString(...)`, `SetNumber(...)`, `SetString(...)`, `MacFiles.Load(...)`, `MacCommands.Execute` | 101-107 | Useful fallback for undocumented MAC procedures, but the PDF warns direct methods/properties are more robust. | Test only for a tiny no-op macro and variable round-trip. |
| 35 | `SystemDataFiles.Open(...)`, `OpenCurrentMdb(...)`, `MdbFolder(...)`, `PsysFile(...)`, `SystemDataFile.Save/SaveAs` | 109-114 | Powerful system-data access, but write risk is high. | Read-only path discovery first; writes only to temp/copied data files. |

## Deliberately Low Priority Or Avoid By Default

| Function(s) | Reason |
| --- | --- |
| `uim_error(...)`, `uim_info(...)`, `uim_prompt(...)` | UI messaging is not useful for headless automation and may interrupt the operator. |
| `fla_browse_for_file_to_open(...)`, `fla_browse_for_file_to_save(...)` | Dialog-driven file browsing is the opposite of deterministic automation. |
| `gin(...)`, latch/cursor APIs such as `get_latched(...)`, `latch_*`, `pnt(...)` | Useful for interactive macros, but less stable than direct feature ids, scans, and pattern APIs. |
| `reg_most_recent_list_*` | Interesting for diagnostics only; should not be used as project truth. `prj_get_file_path()` is the correct active-project route. |
| `AddMenu(...)`, `AddMenuItem(...)` | Plugin UI customization, not relevant to the current automation path. |

## Recommended Test Order

1. Project truth and ownership guard: ranks 1-4.
2. Symbol refresh and validation path: ranks 3, 5-9, 14, 23.
3. Direct feature-edit replacement for keystrokes: ranks 10-13.
4. Headless project/nest creation: ranks 16-22.
5. Reporting and diagnostics: ranks 24-28.
6. 3D, tooling, order, and system-data work: ranks 29-35.

## Immediate Experiments

1. Add thin wrappers and unit tests for `prj_get_file_path`, `prj_is_open`, and `prj_is_edited`.
2. Run a read-only live probe that calls those three functions while RADAN has `PLAYGROUND.rpd` open.
3. Build an automation-owned refresh fixture: copy one changed `.sym`, call `OpenSymbol -> SaveActiveDocument/Document.Save -> Close`, and diff RADAN XML metadata.
4. Test `elf_closed(PART_PATTERN, graphicsMode)` before and after that refresh to see whether it predicts `Workflow status`.
5. Only after those pass, test `prj_save()` or `pfl_finish_nesting()` on copied `.rpd` projects to see what actually refreshes Nest state.
