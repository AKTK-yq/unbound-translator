# Phase 6B-4.6 — renderer width focused investigation

**Decision: Batch 05 translation HOLD.** This is a static ROM/code audit, not a new translation or a claim of mGBA completion. Name-entry length and local Latin-keyboard bounds are now ROM-backed, and a few menu templates are mapped. However 208/408 Batch 05 entries still have unknown renderers and another 11 have incomplete column/cursor geometry. That fails the requested “majority of major menus proven or safely bounded” GO condition. All 408 remain held for final pixel-fit approval. No ROM, font, ASM, graphics, or translation entry was changed.

## 1. Start state and evidence policy

| Item | Result |
| --- | --- |
| Branch / HEAD | `japanese-support` / `cd885719ca36802b069ff9579c1260013274e24f` |
| Starting worktree | 16 pre-existing untracked Phase 6B-4.5/Batch 04 files; no tracked edits. Preserved. |
| Baseline tests | 352 passed, 16 subtests passed |
| Source ROM MD5 | `9cad8e771940e7f7094d13911552cef0` |
| Batch 04 ROM MD5 / SHA256 | `d67c0d56d2bc1662ca19c31aaf36a542` / `3cc314c7ceb3cd6057d8c6fb71194af0e4691f54a06b0174d9b06c41900dae0e` |
| Current Japanese applied | 1,549; Batch 04 applied 198 of 408 selected, 210 held |

Machine-readable findings are in ignored local `out/phase6/ja_phase6_renderer_width_final_audit.json`, `ja_phase6_batch04_battle35_width_final.json`, and `ja_phase6_batch04_fa_width_final.json`. The reproducible read-only-ROM audit is `scripts/audit_ja_phase6_renderer_widths_final.py`. Offsets below are ROM offsets; GBA address is `0x08000000 + ROM offset`. `0x00A…` ROM offsets therefore become `0x08A…` addresses, not `0x09A…`.

FireRed [naming screen](https://github.com/pret/pokefirered/blob/master/src/naming_screen.c), [battle text](https://github.com/pret/pokefirered/blob/master/src/battle_message.c), [text renderer](https://github.com/pret/pokefirered/blob/master/src/text.c), and [characters](https://github.com/pret/pokefirered/blob/master/include/characters.h) informed structure only. The conclusions below are conditional on the **Unbound** bytes and references actually checked. A pointer owner is not automatically a proven live display caller.

## 2. Local naming input: count, charset, page, and width

| Profile | Unbound max chars, **FF excluded** | Naming output, **FF included** | Max keyboard advance | SAFE_UPPER_BOUND, local input | Conditional bound for arbitrary ordinary Latin codes | Conditional Japanese-page bound |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Pokémon nickname | 10 | 11 bytes | 6px | **60px** | 120px | 100px |
| Player name | 7 | 8 bytes | 6px | **42px** | 84px | 70px |
| Rival name | 7 | 8 bytes | 6px | **42px** | 84px | 70px |

ROM evidence: the Unbound naming template pointer table is ROM `0x00A6CE38` / GBA `0x08A6CE38` (five pointers for player, box, caught Pokémon, renamed Pokémon, rival). Naming initialization at ROM `0x0009DA84` / GBA `0x0809DA84` obtains that table via literal ROM `0x0009DB58` / GBA `0x0809DB58`; the templates are ROM `0x003E245C` / GBA `0x083E245C` (player, second byte `07`), `0x003E2468` (box, `08`), `0x003E2474` (Pokémon, `0A`), `0x003E2480` (rival, `07`). The input/full-cell path around ROM `0x0009F668` / GBA `0x0809F668` reads template byte `+1`; the naming output uses the FF terminator. These are actual Unbound records, not imported FireRed constants. The result is an **input-screen** bound, not proof of every save/link/trade value.

The keyboard is the 96-byte ROM array `0x003E22D0–0x003E232F` / GBA `0x083E22D0–0x083E232F`, referenced by the `GetCharAtKeyboardPos` path at ROM `0x0009F634` / GBA `0x0809F634` through literal `0x0009F664` / GBA `0x0809F664`. It has three 4×8 Latin pages: lowercase, uppercase, numbers/symbols, with 75 distinct nonzero glyph codes plus code `00` for space/padding. A few grid cells are blank. No keyboard code is `F7` or above, so it cannot enter `FC 15` (`[japanese]`), `FC 16` (`[latin]`), or FF; **Japanese and mixed-script names cannot be entered locally on this screen**. Upper/lowercase and symbols are included. The ROM normal Latin advance table at `0x001FB100` / GBA `0x081FB100` exactly matches `lib/gen3_font.py`; two references are at ROM `0x00006594` and `0x000065AC`. The greatest keyboard-code normal advance is 6px. Naming text is normal Latin, spacing 0, and terminator has no glyph advance. Thus `10×6=60`, `7×6=42` without average-width shortcuts. An arbitrary Latin code can reach 12px and a Japanese normal glyph 10px, but those latter bounds are **conditional**: imported names, altered saves, storage length, page state after buffer expansion, and foreign-name conversion have not been proved. They cannot grant battle fit approval. No local mixed-script bound is applicable; a conditional per-character mixture would be at most 12px/char if each page switch and length cap were independently proved.

`ACTUAL_DATA_MAX` is different from input upper bound. Scanning all 1,294 extracted source-ROM species records gives **59px** in normal Latin font (`tbl_pokemon_names_01290_166E0FA`); all 743 trainer-name records give **67px** (`tbl_trainer_names_00019_23EDC4`). These are source English table maxima, including potentially unused records, **not** maxima for future translated names or an enumerated set of playable default player/rival names. The template-associated strings at ROM `0x00418E47`, `0x00418E52`, `0x00418E5C`, `0x00418E69` are prompts (“Your Name?”, “Box Name?”, nickname prompt, “Rival’s Name?”), not default-name choices. The actual default player/rival choice set and its maximum are **unproved**; no fabricated `ACTUAL_DATA_MAX` is assigned. The local naming template/keyboard also does not prove the `MON_DATA_NICKNAME` storage field, a dedicated “has custom nickname” flag, or species-name fallback in every Unbound display path. [FireRed’s field IDs](https://github.com/pret/pokefirered/blob/master/include/constants/pokemon.h) are context, not Unbound proof. `lib/renderer_profiles.py` exposes the three reusable profiles with max chars, accepted codes, font, SAFE_UPPER_BOUND and external-name caveat; default species actual max is recorded separately from nickname max.

## 3. Batch 04 battle 35 and FA names

Battle message window and printer remain ROM `0x00248330` / GBA `0x08248330` (28×4 tiles) and ROM `0x003FEB64` / GBA `0x083FEB64` (font 2 Normal, text x=2, letter spacing 0): physical span `28×8−2=222px`. The call path and lack of width-triggered implicit wrap were documented in the [Phase 6B-4.5 audit](ja-phase6-renderer-widths.md). FE/FA/FB delimit lines/pages; a static width result alone cannot prove clipping behavior after dynamic expansion. The current ability-table actual maximum is 86px; recompute after localizing names.

Conditional nickname-buffer models use local keyboard `60px + max observed English prefix 27px = 87px`, all ordinary Latin `120+27=147px`, and potential Japanese `100+27=127px`. Prefix literals `Wild ` at ROM `0x003FD555` / GBA `0x083FD555` (27px) and `Foe ` at ROM `0x003FD55B` / GBA `0x083FD55B` (24px) are present, but their actual Unbound buffer-expansion consumer/branch was **not** proved. The 35-entry result is therefore a diagnostic upper-bound exercise, not release approval:

| Conditional calculation | Entries |
| --- | ---: |
| Fits physical 222px with local-input name model | 29 |
| Of these, exceeds 222px **only** with broader theoretical name model | 28 |
| Can exceed 222px even with local-input model | 6 |
| Broad model also fits (`FIT_ALL_VALUES` conditional only) | 1 |
| Broad model can overflow (`DYNAMIC_OVERFLOW_POSSIBLE`) | 34 |
| **Final approved / newly statically safe** | **0 / 0** |
| **Final `UNKNOWN` hold** | **35** |

The one conditional `FIT_ALL_VALUES` is `tbl_battle_messages_00060_3FBA79`; it is **not** promoted because buffer source, foreign-name/page behavior, and last-glyph margin are unresolved. The 28 theoretical-only entries are not said to fail for a normal locally typed nickname. Every row records its ID, static width per line, buffer codes, local/broad dynamic widths, resulting total widths, explicit line model, conditional classification, and final `UNKNOWN` in `out/phase6/ja_phase6_batch04_battle35_width_final.json`. No reviewed text was shortened or injected.

For the separate FA set, 30 ambiguity holds and five screen-overflow holds remain, **0 newly safe**. Player/rival local bounds are now 42px, but their actual dialogue window and buffer-expansion page remain unproved; five existing overflows exceed even the 240px screen using static Japanese alone. Per-segment local/broad totals and `layout_confidence=UNKNOWN` are in `out/phase6/ja_phase6_batch04_fa_width_final.json`. The old guessed 208px dialogue width is not reinstated.

## 4. Batch 05 inventory and menu renderer geometry

408 entries: 189 battle messages and 219 menu/UI/setting/label entries. Their mutually exclusive renderer groups are:

| Group | Count | Group | Count |
| --- | ---: | --- | ---: |
| Battle message | 189 | Generic list | 38 |
| Settings label/help | 35 | PC box message | 14 |
| PC box action/label | 16 | Bag/Cube sort/popup/tab | 14 |
| Battle submenu | 8 | Battle two-column command | 4 |
| Options label/value | 5 | PC item action | 2 |
| PC item context action/help/message | 7 | Short labels | 11 |
| Menu common | 19 | Menu link controls | 15 |
| Pokémon summary | 12 | Trainer card | 9 |
| Pokémon menu | 7 | Pause/save/shop menu | 3 |

The grouping does **not** equate category, pointer owner, or source slot with a live renderer. Menu-specific findings:

| UI / confidence | Window, printer and controls proved in Unbound | Usable text width |
| --- | --- | --- |
| Battle message — **PROVEN geometry** | Window ROM `0x00248330` / GBA `0x08248330`, printer ROM `0x003FEB64` / GBA `0x083FEB64`, font 2, x=2px, physical 222px, two visible lines; dynamic placeholders separately gated. | Physical 222px; final translated/dynamic fit still held. |
| Battle action/command — **PARTIAL** | Window 2 record ROM `0x00248340` / GBA `0x08248340`, 12×4 tiles, printer ROM `0x003FEB7C` / GBA `0x083FEB7C`, font 1, x=0, spacing 0, physical **96px**. Four extracted strings are anchored to caller literals: Safari `0x000DDCDC`, other Unbound variants `0x0009FB008`, `0x0009FB004`, `0x0009FAFD0` (add base for GBA); the latter hook calls printer `0x080D87BC` via ROM literal `0x0009FAFBC`. All contain `FC 13 38`, placing second column at **56px**. | Physical first/second spans 56/40px. Selector/cursor/right padding and the live variant are unproved, so **neither span is usable width**. Template y=0x23 tiles is off-screen before runtime placement; screenshot coordinates cannot be inferred from template x/y alone. Safari and ordinary battle variants require distinct live confirmation. |
| Battle submenu — **UNKNOWN** | Other 8 `menu_battle` entries have no proven shared window or per-item caller; fight move rows, PP/type and commands cannot be merged. | null |
| Vanilla Options label/value row — **PARTIAL** | `InitWindows` caller ROM `0x0008861C` / GBA `0x0808861C` uses table ROM `0x003CC2B8` / GBA `0x083CC2B8`; row record at `0x003CC2C0` / `0x083CC2C0` is x=2,y=7,26×12 tiles. Label-table pointer at ROM `0x00088DDC` / GBA `0x08088DDC` targets ROM `0x003CC314` / GBA `0x083CC314`; label-print path begins ROM `0x00088D8C` / GBA `0x08088D8C`, window 1, x=8, font 2. Title 26×2 and help 30×2 templates at ROM `0x003CC2B8` and `0x003CC2C8` are distinct. | Row full physical span from label origin =200px, **not** label allowance: value/selector column boundary, text spacing, title/help printers and right padding unproved. All 5 selected Options entries PARTIAL. |
| Custom Game Settings/difficulty — **UNKNOWN** | `tbl_menu_game_settings_00016_75CE9A` “Easy” has script `bufferstring` operand (`85 02`) before pointer source ROM `0x0075CD61` / GBA `0x0875CD61`. It must not inherit the vanilla Options row profile. | null; live buffer/widget mapping needed. |
| PC Item Storage action — **PARTIAL** | `AddWindow` calls around ROM `0x000EB74C–0x000EB77E` / GBA `0x080EB74C–0x080EB77E` reference 13×6 and 13×8 templates ROM `0x00402248`/`0x00402250` (GBA `0x08402248`/`0x08402250`). Text/function pairs at ROM `0x00402208`; “Deposit Item” pointer source ROM `0x00402210` / GBA `0x08402210`. | 13 tiles=104px physical only; text origin, selector and right padding unknown. Only 2 action entries mapped, not all 9 category entries. |
| PC box/list/name/message — **UNKNOWN** | Separate 16 box action/label and 14 messages. Storage box controls, Pokémon-name rows, action menu and message printer not mapped to one template. | null |
| Bag/Cube — **UNKNOWN** | 14 selected sort/popup/tab sources. Item list + quantity, pocket tab, description and context action are distinct potential widgets. No proved shared caller/window, font or icon/right-value region. | null |
| Generic list/script choice — **UNKNOWN** | 38 `menu_list_labels` sources are not all script-choice options. No demonstrated generic choice helper/window sizing/cursor width/max screen span in Unbound for these entries. | null; dynamic/fixed sizing not assumed. |
| Mission/other menu, short label — **UNKNOWN** | Menu common/link/Pokémon/summary/trainer/mission/short-label widget and owner paths are not uniformly mapped; zero Batch 05 entries categorized as mission here. | null |

The `menu_battle` current **Latin** strings can be traced with the normal Latin glyph widths because four separate 256-byte ROM width-table copies at `0x001FB100`, `0x00207300`, `0x00217618`, `0x00227930` are byte-for-byte identical, with code references at ROM `0x00006594`/`0x000065AC`, `0x00006698`/`0x000066F4`, `0x000068CC`/`0x00006928`, `0x00006A38`/`0x00006A94`. Their original line rightmost advances are 73–80px, under the physical 96px window. This **does not** prove Japanese font-1 advances or usable cell widths, nor establish that a translated command fits. [FireRed’s font-1 vs normal glyph functions](https://github.com/pret/pokefirered/blob/master/src/text.c) are only an architectural cross-check.

There is no `\al`/`\ar` alignment command: the PCS aliases are **single-byte left/right arrow glyphs**, while `FC 0D`/`FC 11` shift, `FC 12` sets cursor X, and `FC 13` clears forward to an absolute X. The analyzer traces those horizontal controls per line; right-aligned values and `FC 13`-split columns may not be given a full-window allowance. A font switch, dynamic buffer or unproved glyph page blocks fit approval. The [FireRed control definitions](https://github.com/pret/pokefirered/blob/master/include/characters.h) agree with the local codec; Unbound's copied ROM control bytes provide the entry-level evidence.

## 5. Reusable metadata, QA, and decision

`lib/renderer_profiles.py` now holds **nine ROM-anchored renderer profiles** (four battle, three Options, two PC Item Storage) plus the three name bounds; other IDs resolve to an explicit unknown profile. Each renderer profile records renderer ID, template/printer where known, font, physical/usable width, lines, wrap, dynamic behavior, evidence and confidence (`PROVEN`, `SAFE_BOUND`, `PARTIAL`, `UNKNOWN`; no menu profile qualifies as `SAFE_BOUND` yet). The updated ignored `out/phase6/ja_phase6_batch05_fa_segmented_input.json` retains its prior schema and 408 IDs while adding `renderer_group_final`, `renderer_profile_id`, `renderer_confidence`, `usable_width_pixels`, physical span, wrap/window sizing, dynamic buffer, variable-name profile, layout confidence, risk and final gate. Four FA-segmented rows receive player/rival 42px local-input profiles. None is auto-approved. Counts: **PROVEN 189, SAFE_BOUND 0, PARTIAL 11, UNKNOWN 208**; `fit_approval_count=0`. The 189 `PROVEN` are battle-message **geometry**, not all-value text fits. Existing older width-audit keys remain for schema compatibility.

Ignored `out/phase6/ja_phase6_batch05_style_handoff.json` now says: natural translation first; no width-driven abbreviation; Codex owns final pixel fit after reviewed translation; official names need verification; FA receives segment translation only; unknown renderer stays held. No Claude run or translation occurred.

`tests/fixtures/ja_phase6_renderer_visual_qa.json` was reduced from **14 to 10** targeted, **untested** screen cases: dynamic battle name, FA field dialogue, ordinary battle two-column commands, Safari variant, vanilla Options label/value, custom Game Settings difficulty, PC Item Storage action, PC Box action, Cube sort, and generic script choice. Each records screen, route if known, English baseline, known or null left/text/right screen coordinates, measurement and proof condition. In mGBA open `out/unbound-ja-phase6-batch04.gba`, navigate to a listed screen, leave cursor/value/icons visible, capture the full native **240×160** frame, and record the outer window x-left/x-right, first and last glyph x, cursor/value/icon occupancy. For dynamic names use a locally entered 10-character nickname or 7-character player/rival name, plus both wild/trainer variants where reachable. Photograph FE and FA as separate frames. A screenshot is a measurement, **not** pointer-owner proof: verify the displayed English string/entry or a focused runtime trace before changing a hold. Exact paths to the sleep/ability event, Safari mode and late field script are not known; those cases are explicitly marked.

### Remaining limitations and GO/HOLD

- Local keyboard cap does not bound imported/traded/modified names or prove page restoration after dynamic buffer expansion. Nickname flag/default species fallback and default player/rival finite choice set are unresolved.
- The battle prefix literals' actual expansion branch and last-glyph right-edge margin remain unproved; Battle 35 final hold stays 35.
- Most Bag, PC, custom settings, generic list/choice, mission and other menu renderers have no per-entry live caller/usable-width proof. The 11 partial menus have known physical templates but unresolved cells/padding.
- A source-ROM English font table cannot guarantee future Japanese glyph width in every font ID. `FC 13` column transitions require per-cell measurement.
- No runtime screenshot was taken during this static investigation. Visual QA results must not be inferred from a ROM text hit.

The GO rule allows unknown *exceptions* to be held, but here **208/408 are unknown**, including the majority of the **219 non-battle menu/UI entries**. Thus **HOLD** before Batch 05 translation, despite the proved local-name bounds and Battle-message geometry. The next focused work is per-widget caller/template mapping for Bag, PC, Game Settings and list choices, plus imported-name/placeholder expansion validation. No Batch 05 or 06 translation is initiated.

## 6. Verification and worktree record

New regression tests cover naming character/terminator counts, keyboard codes/page, local safe widths, changed-ROM anchor rejection, Battle 35 re-evaluation and hold, focused menu templates, FC13 versus arrow glyphs, unknown renderer hold, all Batch 05 metadata, four FA metadata rows, and the 10-case visual fixture. Baseline **352 passed**; final `.venv/Scripts/python.exe -m pytest -q` **361 passed, 16 subtests passed in 34.85s**. `py_compile` on the three touched Python files **PASS**; `git diff --check` **PASS**. The audit script checked both input hashes, and final independent checks still found source MD5 `9cad8e771940e7f7094d13911552cef0` and Batch 04 SHA256 `3cc314c7ceb3cd6057d8c6fb71194af0e4691f54a06b0174d9b06c41900dae0e`. No new ROM was produced.

Files touched this task: `lib/renderer_profiles.py` (extended previous untracked profile module), `scripts/audit_ja_phase6_renderer_widths_final.py`, `tests/test_ja_phase6_renderer_widths_final.py`, `tests/fixtures/ja_phase6_renderer_visual_qa.json` (previous untracked fixture updated), this report, and the ignored audit + Batch 05 metadata JSON listed above. Existing unrelated/untracked Batch 04 files remain. `git diff --stat` is **empty** because every visible worktree file is untracked; this does **not** mean no files were created. Final `git status --short --branch`: branch `japanese-support` tracking `origin/japanese-support`, **19 untracked files**, no tracked modifications. The 16 pre-existing untracked files are preserved; the three new files are this report, final audit script and final test. No commit or push.
