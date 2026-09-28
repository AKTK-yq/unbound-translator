# Phase 6B-4.5 — Unbound renderer width audit (Batch 05 preflight)

Status: **HOLD** for width-based automatic approval. This is a ROM/code audit, not a new translation or runtime test. The source and Batch 04 ROMs were read only. No new ROM was generated. The existing 1,549 applied Japanese entries remain unchanged.

## 1. Baseline and evidence rules

| Item | Recorded value |
| --- | --- |
| Branch / HEAD | `japanese-support` / `cd885719ca36802b069ff9579c1260013274e24f` |
| Start status | Eleven pre-existing untracked Batch 04 files; no tracked changes. See final status below. |
| Baseline tests | `343 passed in 35.46s` |
| `rom/unbound.gba` MD5 | `9cad8e771940e7f7094d13911552cef0` |
| `out/unbound-ja-phase6-batch04.gba` MD5 | `d67c0d56d2bc1662ca19c31aaf36a542` |
| Batch 04 ROM SHA256 | `3cc314c7ceb3cd6057d8c6fb71194af0e4691f54a06b0174d9b06c41900dae0e` |
| Batch 04 | 408 selected, 198 applied, 210 held; 1,549 total Japanese entries; FA applied 13. |

The source ROM bytes are primary evidence. [FireRed battle-window](https://github.com/pret/pokefirered/blob/master/src/battle_bg.c), [battle printer and buffer expansion](https://github.com/pret/pokefirered/blob/master/src/battle_message.c), [text renderer](https://github.com/pret/pokefirered/blob/master/src/text.c), and [name lengths](https://github.com/pret/pokefirered/blob/master/include/constants/global.h) are structural references, **not** proof that Unbound's CFRU-modified behavior is identical. Source records, pointer hits, and source-ROM name-table maxima do not alone prove the active runtime consumer. Audit implementation: `lib/renderer_profiles.py:46`, `scripts/audit_ja_phase6_renderer_widths.py:293`; machine-readable results: `out/phase6/ja_phase6_renderer_width_audit.json`.

## 2. Battle renderer path and usable area

The Unbound window initialization routine begins at ROM `0x0000F324` / GBA `0x0800F324`. At ROM `0x0000F348` / GBA `0x0800F348`, its literal points to ROM `0x00248330` / GBA `0x08248330`. It calls the window initialization function at GBA `0x08003B24` from ROM `0x0000F338` / GBA `0x0800F338`. The first three eight-byte window records are:

| ID | Record ROM / GBA | Bytes | Interpretation |
| --- | --- | --- | --- |
| 0, B_WIN_MSG | `0x00248330` / `0x08248330` | `00 01 0F 1C 04 00 90 00` | BG0, x=1 tile, y=15 tiles, **28×4 tiles**. |
| 1, prompt | `0x00248338` / `0x08248338` | `00 01 23 0E 04 00 C0 01` | 14×4 tiles. |
| 2, action menu | `0x00248340` / `0x08248340` | `00 11 23 0C 04 05 90 01` | 12×4 tiles. |

Battle text-printer routine ROM `0x000D87BC` / GBA `0x080D87BC` indexes a 12-byte-per-window settings table via the literal at ROM `0x000D8814` / GBA `0x080D8814`, whose target is ROM `0x003FEB64` / GBA `0x083FEB64`. Window 0 record `FF 02 02 02 00 02 01 01 0F 06 00 00` means normal font ID 2, x=2px, y=2px, letter spacing 0px, line spacing 2px. The physical right-edge budget from the printer origin is **28×8−2 = 222px**. This is a *maximum drawable span*, not a demonstrated anti-clipping margin: no separately reserved right padding, cursor, or icon subtraction has been proven. The absolute window starts at screen x=8px; text origin is x=10px. A 222px advance reaches the window's x=232px right boundary; actual last glyph pixel and clipping must be checked in mGBA. Prefixes are expanded into the text and consume part of this span, not a constant reserved column.

The normal `RenderText` entry is ROM `0x00005790` / GBA `0x08005790`; glyph selection/copy path includes ROM `0x00005B6C` / GBA `0x08005B6C`, and current-X advance at ROM `0x00005BEE` / GBA `0x08005BEE`. This observed path does not compare X to a window width and does not automatically wrap at 222px. FE makes a new line; FA waits and scrolls; FB waits and clears. Long text without an explicit control can overrun/clip. The 4-tile-height message area is conventionally two visible lines; exact glyph height/scroll edge under CFRU remains a runtime visual check, so no previously held FA or battle entry is approved on this alone. No Unbound-specific width-changing hook was established. The printer table is definitely Unbound's, rather than an assumed FireRed constant.

Other battle records have different geometry/font: prompt 14 tiles with font 2 and x=2 (physical span 110px); action menu 12 tiles with font 1 and x=0 (96px); move-name area 16 tiles with small font 0 and x=0 (128px). Their cell origins, two-column action layout, selection cursor, right-side PP/type values, and font-0/1 glyph metrics are **not** proved as a generic 96px/128px text-fit rule. Crucially, extractor category `menu_battle` includes Safari-like menus and is not automatically the action-menu window. The batch metadata therefore leaves those 12 entries' usable width null.

## 3. Glyph and dynamic-buffer width model

`lib/gen3_font.py:9` is the normal Latin advance table; `:30` is the Unbound/Japanese normal advance table. `:45` computes widths while switching pages. The new `lib/renderer_profiles.py:137` extends this normal-font model to FD placeholder bounds and FE/FA/FB line segments. The battle message printer's font ID 2 and zero letter spacing match this metric. Japanese page and Latin page use different width tables; a dynamic Latin name inside Japanese text cannot be assigned a Japanese fixed width without proving the engine's substitution-page semantics. Space width, glyph advance, and start x are accounted for by the table and record; no unsupported right padding is invented. Small font 0 and menu-copy font 1 are **not** measured using normal-font widths.

Every fixed source-ROM name record in the extracted tables was measured in normal Latin-font pixels. These are finite *current English ROM* candidate maxima, not bounds for future Japanese translations or user nicknames:

| Source candidate set | Records | Maximum | Record ID |
| --- | ---: | ---: | --- |
| Pokémon species names | 1,294 | 59px | `tbl_pokemon_names_01290_166E0FA` |
| Move names | 923 | 71px | `tbl_move_names_00496_A42340` |
| Ability names | 293 | 86px | `tbl_ability_names_00268_A37564` |
| Trainer names | 743 | 67px | `tbl_trainer_names_00019_23EDC4` |
| Trainer classes | 107 | 117px | `tbl_trainer_classes_00026_1FA1EF5` |

The source-ROM battle prefix literals are `Wild ` at ROM `0x003FD555` / GBA `0x083FD555` (27px) and `Foe ` at ROM `0x003FD55B` / GBA `0x083FD55B` (24px). Their adjacent bytes are verified, but the exact Unbound nickname-expansion branch consuming them was not traced. For `\0F`/`\10`/`\11`/`\13` (Pokémon name with state-dependent prefix), a *conditional* reference bound is 10 FireRed name characters × 12px maximum Latin advance + 27px prefix = 147px. It is **not** an Unbound-proven maximum. Ordinary Pokémon species table maximum 59px is insufficient because a user nickname can be longer/wider. `\14` has the current Move-table maximum 71px, but all contextual move fallbacks are not enumerated. `\1A` has current Ability-table maximum 86px, requiring recomputation after translating that table. `\00`/`\01` are writer-dependent; `\2A` is side/prefix-dependent; CFRU extensions `\36`/`\38` remain unknown. Metadata classifies these as `FINITE_SET_MAX_WIDTH`, `PLAYER_VARIABLE_MAX_WIDTH`, `CONTEXT_DEPENDENT`, or `UNKNOWN`, with `bound_proven_for_unbound` flags. There is no safely provable typical player-generated name width; no guessed typical value is recorded.

For player/rival names, FireRed's reference is 7 characters. A charset-agnostic upper bound using the current normal tables is 7×12 = 84px Latin or 7×10 = 70px Japanese. Nickname reference is 10×12 = 120px Latin or 10×10 = 100px Japanese. This worst-glyph-times-length method is safer than using only a naming keyboard's known characters, but **even the length, accepted characters, stored page, and `[player]`/`[rival]` expansion page are not independently proved for Unbound**. The more precise keyboard-charset maximum needs tracing of Unbound's naming screen, save layout, and renderer. Accordingly `approved_for_automatic_fit=false`; FA widths remain diagnostic only. For `\0F` prefixes, 147px is merely conditional. See `lib/renderer_profiles.py:116`.

## 4. Batch 04 holds rechecked, without changing translations

The 35 battle messages held *only* for unknown width were measured line-by-line against the physical 222px span with their reviewed Japanese text and dynamic-code metadata. Result: **35 `DYNAMIC_WIDTH_AMBIGUOUS`, 0 FIT/WRAP_SAFE, 0 newly safe**. They all use nickname-bearing `\0F`, `\10`, `\11`, or `\13`; 4 also use ability `\1A`. Under the unproven FireRed-length reference, 34/35 still exceed 222px in at least one line; one conditionally fits. This is not a reason to rewrite their Japanese or approve the one: actual nickname max/page and right-edge margin are not proved. Per-entry ID, Japanese text, static/dynamic/total widths, controls, and result are in `out/phase6/ja_phase6_batch04_battle35_width_recheck.json`. Example `tbl_battle_messages_00003_3FB534`: 85px static + conditional 147px name/prefix = 232px, over physical 222px. The 35 remain English in the existing ROM.

The segmented FA audit remeasured **30 `LAYOUT_AMBIGUOUS`** and **5 `LAYOUT_OVERFLOW`** entries without editing any segment. The normal dialogue window/caller width, dynamic player/rival cap/page, and two-line scroll viewport are not proved from this battle investigation, so **0 newly safe**. All five prior overflow entries have at least one *static Japanese segment* over the full 240px screen even before placeholders (max widths 249–305px); no evidence for a horizontal scroller, smaller font, or automatic wrap was found for their actual callers. Two of the 30 ambiguous also have a static segment over 240px (`scr_1F41F58` 259px, `scr_1F48C27` 250px), and still need caller identification. Exact per-segment widths are in `out/phase6/ja_phase6_batch04_fa_width_recheck.json`. The prior 208px dialogue-box assumption and 54px buffer estimate are **not** promoted to ROM facts.

## 5. Menu, label, and route renderer classification

| Renderer group | Example / current evidence | Caller → printer → window / width status |
| --- | --- | --- |
| Normal dialogue | FA source `scr_1F3E84E` | Script operand exists; actual widget caller/template not traced here. `UNKNOWN_RENDERER`. |
| Battle message | `tbl_battle_messages_00062_3FBAB2` | Battle message routine ROM `0x000D87BC` → printer table `0x003FEB64` → B_WIN_MSG `0x00248330`; physical 222px normal font. Dynamic expansion still gated. |
| Battle action/prompt | Fight/Pokémon/Bag/Run screen | Window records `0x00248338`/`0x00248340`; printer records `0x003FEB70`/`0x003FEB7C`; 110/96px physical spans, but per-item cell/cursor geometry unproved. |
| Battle `menu_battle` extraction group | `tbl_menu_battle_00001_3FE747`, Safari choice | Category does not prove B_WIN_ACTION_MENU consumer; width `UNKNOWN_RENDERER`. |
| Pause/Options/Game Settings | `tbl_menu_options_00011_419E28`, `tbl_menu_game_settings_00016_75CE9A` | Table owners are extracted, but actual Unbound caller, window template, text origin, selector cells, right-side values, and font not mapped. `UNKNOWN_RENDERER`. |
| Bag / PC / item storage | `tbl_menu_pc_00008_4182A7`, `tbl_menu_item_storage_00001_417706` | Category/tables known; active widget, cursor/icon area, columns, and printer width unknown. `UNKNOWN_RENDERER`. |
| Generic list / short selector | `tbl_menu_list_labels_00000_4178D0`, `tbl_setting_names_00005_1F4DAAE` | List/right value/cursor geometry unknown; fixed-slot capacity is not display width. `UNKNOWN_RENDERER`. |
| Pokémon/Trainer fixed labels | `menu_pokemon_summary`, `menu_trainer_card` | Multiple likely widgets; no category-wide width. `UNKNOWN_RENDERER`. |
| Signpost / town-city sign / route label | `scr_1F69284` “Seaport City”; `scr_1F783B8` “Tarmigan Town”; `scr_1F7E03C` “Thundercap Mt.”; `scr_1F5B578` “Route 10” | Literal pointers exist, but sign/map-label runtime paths and text-box widths not demonstrated. **Still held**, not merely because Japanese is wider than English. |
| Mission UI | mission-name/objective sources in existing extraction | Dedicated UI and width not traced here. `UNKNOWN_RENDERER`. |

For the city/route examples, no real label-box pixel width is claimed. Width cannot be inferred from the source's fixed slot or from English byte length. Exact screen screenshots and runtime caller tracing are required before changing their holds.

### Seaport City pointer ownership

Target `scr_1F69284` is ROM `0x01F69284` / GBA `0x09F69284`, source slot 13 bytes. The pointer value `84 92 F6 09` occurs **six** times in the 32MB ROM, at ROM `0x01E60934`, `0x01E7E0A3`, `0x01E7FBF8`, `0x01E7FC2E`, `0x01EAF564`, and `0x01EAFD84` (add `0x08000000` for each GBA address). Five are recorded owners in the extracted metadata; `0x01E7E0A3` is a real omitted owner: the two preceding bytes at ROM `0x01E7E0A1` are `85 00`, the `bufferstring 0` script opcode/argument, followed by this direct four-byte operand. Two aligned fields at `0x01EAF564` and `0x01EAFD84` have untraced consumers. No interior pointer or computed reference was established by the exact-byte scan; those possibilities are **not** excluded. Since the full runtime owner set is still not proved, the entry remains held and the extractor/selection ownership is not silently modified. See `out/phase6/ja_phase6_seaport_owner_audit.json`.

## 6. Reusable profiles, Batch 05 preflight, and handoff

`lib/renderer_profiles.py` parses the anchored battle window/printer records, rejects changed xrefs/bytes, measures current fixed table names, computes conservative reference bounds, and returns `UNKNOWN_RENDERER` (width null) where the caller is unproved. `scripts/audit_ja_phase6_renderer_widths.py` reproduces the audit and updates ignored Batch 05 planning JSON, adding fields only; it does not translate or inject. Existing schema keys and 408 entries are retained.

Batch 05 selection: **408 total**, **189 battle messages**, **219 menu/setting/label entries**, **0 normal dialogue**, **4 with FA**. Of the 219 non-battle entries, 11 are short/fixed label categories, 12 are `menu_battle` (unmapped structured UI), and 196 other menu/UI entries have unknown renderer. Width-risk status: `WIDTH_NEEDS_TRANSLATION` 189; `UNKNOWN_RENDERER` 196; `STRUCTURED_UI` 23. All 408 have `final_fit_gate=HOLD_UNTIL_TRANSLATED_AND_PROVED`. Per-category distribution:

| Category | Count | Category | Count |
| --- | ---: | --- | ---: |
| battle_messages | 189 | menu_list_labels | 38 |
| menu_game_settings | 35 | menu_pc | 30 |
| menu_common | 19 | menu_link_controls | 15 |
| menu_cube_system | 14 | menu_battle | 12 |
| menu_pokemon_summary | 12 | menu_item_storage | 9 |
| menu_trainer_card | 9 | setting_names | 8 |
| menu_pokemon | 7 | menu_options | 5 |
| start_menu_labels | 3 | menu_shop/menu_save/menu_pause | 1 each |

`out/phase6/ja_phase6_batch05_fa_segmented_input.json` now adds each entry's `renderer_width_profile`, `width_status`, `usable_width_pixels` (null when unproved), `placeholder_width_classes`, `width_evidence`, and final gate. `out/phase6/ja_phase6_batch05_style_handoff.json` adds the ROM battle geometry, dynamic-width placeholder classes, menu/label unknown-width rule, and explicit instruction that Claude should **not** unnaturally abbreviate for a guessed pixel width; Codex makes the final fit decision after review. Existing `battle_buffer_rule` remains: semantics-safe control types are not automatically layout-safe.

## 7. Human visual QA and next proof targets

`tests/fixtures/ja_phase6_renderer_visual_qa.json` contains **14 untested cases**, each with renderer/screen, reachability instructions, measured coordinates needed, expected original/reviewed text, and resolution condition. These are requests for human evidence, not claims that the held Japanese appears in the current ROM.

In mGBA, use the current Batch 04 ROM at native **240×160** capture resolution (avoid counting scaled UI pixels). For each case: enter the specified screen; save a screenshot with entry ID; note outer window x-left/x-right, first glyph x, last visible glyph pixel, cursor/right-value columns, font size, and whether the end clips. For battle, compare wild and trainer prefixes and a maximum-length nickname. For dialogue, record FE/newline, FA/scroll, and FB/clear on separate frames and repeat with longest accepted player/rival names. A screenshot alone does not prove the pointer owner: tie displayed text to the entry with a controlled debug ROM or runtime trace before changing translation eligibility.

Priority code follow-ups: prove Unbound nickname/player/rival limits and naming charset/page in the save/naming routines; prove all `\0F`/`\10`/`\11`/`\13` prefix branches and any right-edge padding; map Options/Bag/PC widget callers to their window and list printers; trace the Seaport six-pointer owner set and route-label consumers; verify FA viewport and page behavior. Only then can held translations be reclassified or a focused ROM built.

## 8. Checks, GO/HOLD, and worktree

Added regressions cover ROM profile parse/xref failure, 222px physical bound, explicit FE/FA/FB segmentation, source Pokémon/Move/Ability maxima, conditional player bound, route/sign unknown hold, all 35 battle holds, FA 30+5, Batch 05 metadata, visual QA, and the Seaport script operand. Baseline was 343 passed; final checks/results are recorded after the audit run below. No new ROM and therefore no new binary diff audit; the prior Batch 04 strict map and binary audit remain unchanged. Batch 05 **HOLD** because dynamic name caps and major menu/label renderers remain unproved. Width metadata is ready for future reviewed translations, but it is not a fit approval.

Changed/created files for this audit: `lib/renderer_profiles.py`, `scripts/audit_ja_phase6_renderer_widths.py`, `tests/test_ja_phase6_renderer_widths.py`, `tests/fixtures/ja_phase6_renderer_visual_qa.json`, this report, and ignored `out/phase6/ja_phase6_renderer_width_audit.json`, `ja_phase6_batch04_battle35_width_recheck.json`, `ja_phase6_batch04_fa_width_recheck.json`, `ja_phase6_seaport_owner_audit.json`, plus metadata-only updates to ignored Batch 05 segmented input and style handoff. Existing Batch 04 worktree files were preserved. `git diff --stat` does not display untracked files; use `git status --short` for their list. No commit or push.

Final verification: `.venv/Scripts/python.exe -m pytest` **352 passed in 34.56s** (343 baseline + 9 new); `py_compile` **PASS** for the three new Python files; `git diff --check` **PASS**. The audit script's final rerun returned battle 35/35 dynamic-ambiguous, Batch 05 width risks 189/196/23, visual cases 14, gate HOLD. `git diff --stat` is empty because all tracked files remain unchanged; the five new audit files above are untracked. Final `git status --short` contains those five plus the same eleven pre-existing Batch 04 untracked files, and no tracked modifications. `rom/unbound.gba` and the Batch 04 ROM retained the verified source/baseline hashes during the audit. No commit or push.
