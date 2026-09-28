# Phase 6B-4 — Batch 04 technical integration

**Static gate: 198 safe entries applied; 210 stay in English.**

- Runtime display and event reachability are **not human-tested**.
- Batch 05/06 were not translated.
- No commit or push was made.

**Start state:**

| Item | Value |
|---|---|
| Branch | `japanese-support` |
| HEAD | `cd885719ca36802b069ff9579c1260013274e24f` |
| Worktree | 5 untracked Claude Batch 04 review files; no tracked modifications. None were reset or deleted |
| Baseline pytest | 331 passed, 16 subtests |
| Source ROM MD5 | `9cad8e771940e7f7094d13911552cef0` |
| Batch 03 ROM | MD5 `91422451ecc21213a590bcea8df07670`, SHA-256 `535509572cf3f61951a58b6c700eea8ca669776bb9c596f890938405c1afdae3` |
| Safely applied Japanese at start | 1,351 |

## 1–2. Review validation and review source

- `ja_phase6_batch04_review_validation.json` confirms exactly 408 unique IDs, in the same order as the segmented source and the selection.
- Extra, duplicate, original/category, protected-token, control, kanji, and Japanese PCS charmap errors are all 0.
- **Review source:** `claude_cli` 408.
- **Statuses:** confirmed 362, existing_glossary 17, needs_context 28, needs_technical_fit 1 (existing_official 0).
- **Structure:** non-FA 358; FA 50 (88 FA controls, 505 segments, 22 entries with more than one FA).
- **Token order:** held `candidate_japanese` values may reorder tokens and are compared as a multiset. Reviewed text must keep the exact order.

## 3–6. Official names (`ja_phase6_batch04_official_name_audit.json`)

**Counts:** 54 unique English terms, 112 occurrences, 81 entries.

- These match the Claude report exactly: 83 occurrences are PokeAPI entity types (pokemon/move/item/ability), and 29 are not.
- Lookup used the existing exact-English PokeAPI `ja-hrkt` pipeline (`audit_ja_phase6_batch02_names.lookup`), with a PCS-safety check.

| Result | Occurrences | Unique terms | Detail |
|---|---:|---:|---|
| verified_exact | 74 | 37 | Every provisional value equals the PokeAPI value |
| verified_difference | 0 | 0 | |
| not_found | 8 | 7 | Plurals are not singularized: Poké Balls, Pretty Wings, Rawst/Belue/Watmel Berries, Moomoo Milks, Incense |
| ambiguous | 1 | 1 | Qualot Berry: line-wrapped in the source, so the term is not contiguous |
| not_applicable | 29 | 9 | Non-PokeAPI terms: Hoenn, Battle Frontier, Safari Zone, Mega Evolution, National Pokédex, Hidden Grotto, Hiker, Seagallop Hi-Speed, Pokémon Wireless Club |
| unsupported | 0 | 0 | |

- **Unresolved official names:** 38 occurrences (not_found + ambiguous + not_applicable).
- **Handling of unresolved names:** every entry that needs one of these names is held, and its provisional Japanese was not adopted.
- **Apply impact per occurrence:** applied 35; entry held for an unverified name 38; name verified but entry held for another reason 39.

## 7. existing_glossary (17)

`ja_phase6_batch04_existing_glossary_audit.json` covers:
- 3 deterministic locations (Seaport City, Tarmigan Town, Thundercap Mt.), each equal to its exact approved glossary match.
- 14 `Route [N]` rows. Each keeps its number and reads `[N]ばんどうろ`.
- The template was misapplied to "route" prose in 0 cases.

All 17 are scoped correctly, but none are applied:
- Seaport City (`scr_1F69284`) has extra whole-ROM pointer hits, so ownership is incomplete.
- The other 16 are single-line labels whose Japanese width (about 64–65px) exceeds the observed English envelope (about 47px). The label renderer width is unproved.

## 8–13. FA (`ja_phase6_batch04_fa_audit.json`)

**Classification of all 50 FA rows (disjoint):**
- semantic_confirmed_review: 48
- segment_conflict: 1
- context_hold_only: 1

**Rebuild method:** Codex rebuilt every semantic row from the ROM-derived `control_segments` plus Claude's per-segment text. Claude chose no FA position.

| Layout class (48 semantic-confirmed) | Count | Reason |
|---|---:|---|
| LAYOUT_PASS | **13** | Same ROM boundaries; every Japanese line is ≤208px and within the source maximum |
| LAYOUT_WRAP_SAFE | 0 | An FA segment is one rendered line; no automatic wrap is modelled |
| LAYOUT_OVERFLOW | **5** | A line is wider than the 240px GBA screen |
| LAYOUT_AMBIGUOUS | **30** | 22 contain `[player]`/`[rival]`, whose dynamic width and page state are unproved; 8 exceed the 208px diagnostic or the source envelope |
| TECHNICAL_OWNER_HOLD | 0 | |

- **Applied FA:** the 13 LAYOUT_PASS rows, all of which pass the FA invariant.
- **Invariant on encoded bytes after controlfix** (`ja_phase6_batch04_fa_invariant.json`):
  - Source FA count, order, and segment count equal the output.
  - FA added, removed, or moved: 0; segment merges or splits: 0; tokens crossing a segment: 0.
- **Width model:** static, using the ROM's normal Latin and Japanese glyph widths. The 208px two-line model is diagnostic only, not a pixel-perfect proof of Unbound's renderer.

## 14. Long FA segments (60 in 39 entries, over 18 kana)

All 60 were measured in ROM glyph pixels. Accounting is exact.

| Class | Count | Meaning |
|---|---:|---|
| FIT | 17 | ≤208px and no dynamic buffer; 5 of these are in applied rows, all 188–199px |
| WRAP_SAFE | 0 | No automatic wrap within an FA segment |
| LAYOUT_AMBIGUOUS | 18 | 209–240px |
| WIDTH_OVERFLOW | 8 | Over 240px |
| RENDERER_UNKNOWN | 17 | ≤208px, but the row has a dynamic buffer |

## 15–16. The two FA holds

- **scr_1F48ED0:** held as a segment conflict. `ja_phase6_batch04_fa_retranslation.json` gives Claude segments 2–4 in English, the source FE/FA order (the FA sits after segment 3), and Claude's candidate. Codex authored no wording.
- **scr_1F4C2ED:** its `[buffer1]` ("my [buffer1]") is reached from a `loadpointer 0` operand at `0x01E6D700`. No `bufferstring` writer was found within the bounded ±0x100 search, so the value is unproved and the row stays held. No guess was made.

## 17–18. needs_context (28) and battle buffers

`ja_phase6_batch04_context_audit.json` classifies the 28 as:

| Class | Count | Notes |
|---|---:|---|
| field_buffer | 12 | Unproved `[bufferN]` |
| battle_buffer | 12 | 11 battle rows plus the `\\0C` handover list; resolution `runtime_dynamic` |
| standalone_name | 3 | Polder Town, Ruins of Void, Maxima. Returned to glossary review, not added |
| gendered_fragment | 1 | "daughter": its owners are `bufferstring 2` (`0x01E70A14`) and `bufferstring 1` (`0x01E92DEF`), so it is a dynamic gender-pair fragment |

Technically resolved: 0; all 28 stay held.

**Battle buffer verification.** Codes were checked against pret `pokefirered/include/battle_message.h`, and the source strings' FD bytes were decoded from the ROM.

- **Engine-defined type, safe:** `0F` ATK_NAME_WITH_PREFIX, `10` DEF_NAME_WITH_PREFIX, `11` EFF_NAME_WITH_PREFIX, `13` SCR_ACTIVE_NAME_WITH_PREFIX, `14` CURRENT_MOVE, `1A` SCR_ACTIVE_ABILITY.
- **Held:**
  - `00`/`01` BUFF1/2: the value type depends on the battle script.
  - `2A` ATK_PREFIX2: an English side prefix, so the Batch 04 style note was correct to hold it.
  - `36`/`38`: CFRU codes above vanilla `0x30`, unproved.
- **Field placeholders:** `[player]` (FD 01) and `[rival]` (FD 06), per FireRed `StringExpandPlaceholders`, are allowed in non-FA dialogue.

**Width for battle text.** The type rule alone never approved battle text:
- The 35 type-safe battle messages are all held on width: 32 layout_ambiguous and 3 width_overflow.
- Vanilla FireRed `B_WIN_MSG` is 28 tiles, but the Unbound/CFRU battle window and the width of the prefix plus nickname in a `NAME_WITH_PREFIX` expansion are unproved.

## 19. Glossary candidates (55)

`ja_phase6_batch04_glossary_audit.json`:
- **Types:** mission_title 32, location 13, person 3, other 4, feature 2, npc_label 1.
- **Status:** all `proposal_only_not_approved`. Each row records existing-glossary conflicts and overlaps, context scope, and PokeAPI applicability (none).
- **Matcher:** scope collisions 0; 46 entries had approved-term substrings correctly filtered by the boundary-safe matcher.
- **Mission titles:** all 32 standalone `mission_names` rows are held as `mission_title_glossary_proposal_not_approved`. Prose containing provisional names follows the Batch 01–03 practice and is flagged in review.

## 20–23. Fit

`ja_phase6_batch04_fit.json`: 380 rows (379 approved plus the one technical-fit row).

- Non-FA widths were measured on controlfixed payloads, the real wrapped lines.
- Dialogue and battle text: line ≤208px and within the source envelope. Mission UI: within the source envelope.

| Result | Count | Note |
|---|---:|---|
| in_place | 252 | |
| relocatable | 1 | |
| layout_ambiguous | 92 | event 39, battle 32, mission UI 15, mission log 6 |
| width_overflow | 3 | |
| not_measurable | 31 | Held for an unverified name before measurement |
| not_measured_held | 1 | |

- **Fixed overflow:** 0 (Batch 04 has no fixed or no_relocation slots).
- **Width overflow:** 3 non-FA and 5 FA overflow layouts.
- **Owner incomplete:** 4 whole-ROM extra-pointer cases: `scr_1F4F180`, `scr_1F5DFC7`, `scr_1F62908`, `scr_1F69284`. Addresses are in `ja_phase6_batch04_owner_audit.json`.

## 24–30. Application

| Item | Value |
|---|---|
| Safe | **198** (185 non-FA + 13 FA): scripts 149, mission_descriptions 26, mission_objectives 22, mission_log 1 |
| Held | **210** |

Hold reasons overlap, so they do not sum to 210:

| Hold reason | Count |
|---|---:|
| width_unproved | 95 |
| fa_layout | 35 |
| unverified_official_name | 37 |
| mission_title_proposal | 32 |
| review_status | 29 |
| dynamic_buffer | 24 |
| incomplete_pointer_ownership | 4 |

**Placement:**
- Batch 04 in-place: 197 new entries; the full map has 1,324.
- Batch 04 relocation: 1 new entry (`scr_1F47A45`) into vetted FF space; the full map has 225. Allocation order moved 67 existing baseline relocation destinations without changing their text.
- Pointer writes: 1 new owner; the full map has 2,037.

**Totals:**
- **Japanese applied total:** 1,549 (1,351 + 198).
- **FA applied:** 13 in Batch 04, 29 counting the earlier 16.

## 31–35. Dry-run, controlfix, ROM, audit

- **Strict dry-run** (`--dry-run --fail-on-no-space`): 1,549 inputs.
  - Zero of each of these: encode errors, pointer mismatches, implausible pointers, missing relocations, no-space skips, fixed or no_relocation truncations, runtime patches, graphics patches.
  - Vetted FF used: 3,200 bytes; remaining: 612,633.
- **Build map:** the real build's map equals the dry-run's.
- **Controlfix:**
  - 1,549 translated, 185 changed, 169 wrapped, remaining control mismatches 0, `FA_PLACEMENT_REVIEW_REQUIRED` 0, 29 segmented rebuilds.
  - The second pass is byte-for-byte identical.
  - The 1,351 baseline entries are preserved exactly (built from the Batch 03 controlfixed baseline, not raw input).
- **FA invariant:** PASS, 13 rows, 0 errors.
- **ROM:** `out/unbound-ja-phase6-batch04.gba`, 32 MiB.
  - MD5 `d67c0d56d2bc1662ca19c31aaf36a542`, SHA-256 `3cc314c7ceb3cd6057d8c6fb71194af0e4691f54a06b0174d9b06c41900dae0e`.
  - The source and Batch 01–03 ROMs were not overwritten.
- **Binary audit, source → Batch 04:** 112,583 changed bytes (101,906 in-place text, 2,993 relocated text, 7,684 pointer bytes); unexpected 0.
- **Binary audit, Batch 03 → 04:** 20,536 changed bytes (16,620 new in-place text, 779 relocation-destination changes, 3,137 pointer-destination changes); unexpected 0.
- ASM, runtime, font, and graphics changes: 0. Text pacing, wakachigaki, and renderer are unchanged.

## 36. Runtime QA

`tests/fixtures/ja_phase6_batch04_runtime_qa.json` has 36 entries, all `not_human_tested` with unverified routes.

| Focus | Count |
|---|---:|
| FA_multi_scroll | 4 |
| FA_long_segment | 2 |
| FA_button_scroll_and_page_state | 4 |
| relocated_text_and_pointer | 1 |
| pokeapi_verified_name | 4 |
| player_or_rival_buffer | 4 |
| mission_objective_ui | 3 |
| mission_description_ui | 3 |
| short_slot_width | 1 |
| held_english_regression_battle_status | 2 |
| held_english_regression_route_template_sign | 2 |
| general dialogue | 6 |

Battle, sign, and route rows are checks that the English text still displays correctly, because those rows are held.

## 37–38. Tests and static checks

- New `tests/test_ja_phase6_batch04.py` has 12 tests. They cover:
  - review counts
  - complete accounting of the 50 FA rows, 88 FA controls, and 505 segments
  - the long-segment pixel classes
  - the two FA holds
  - the 112 name occurrences and the unverified-name fallback
  - the battle-buffer rule
  - the 17 existing_glossary rows and the Route template
  - proposal-only glossary candidates
  - controlfix idempotency and baseline preservation
  - the strict maps and binary audit, with a mutation test
  - runtime QA and the Batch 05 inputs
- `.venv/Scripts/python.exe -m pytest`: **343 passed**, 16 subtests.
- `py_compile` of the new scripts and test: PASS. `git diff --check`: PASS.

## 39–41. Batch 05 handoff and gate

- **Style handoff:** `out/phase6/ja_phase6_batch05_style_handoff.json` carries forward every Batch 01–04 rule. New additions:
  - an FA segment length guide (about 18–20 kana, ≤208px, because a segment is one rendered line)
  - the official-name rule (PokeAPI exact only; plurals, wrapped terms, and non-PokeAPI franchise terms hold the entry)
  - the verified battle safe/hold table with its evidence
  - the rule that unproven battle-window width holds a row
  - the field-buffer rule and the mission-title rule
  - new known-bad patterns
- **Batch 05 FA input:** `out/phase6/ja_phase6_batch05_fa_segmented_input.json` has 408 source-only rows. 4 battle messages carry ROM-derived FA segments: `tbl_battle_messages_00122/00185/00216/00219`. Nothing was translated.
- **Gate: STATIC GO for Batch 05 translation.** Every GO condition passed:
  - the name pipeline
  - 13 FA rows injected safely
  - the FA invariant
  - automatic holds for long or ambiguous segments and unknown buffers
  - idempotent controlfix
  - the binary audit
- **RUNTIME HOLD** remains for claiming display correctness.
- **Caveat:** Batch 05 is mostly battle messages and menus. Until the Unbound battle-window and menu widths are traced or measured in mGBA, most battle text will be held on width, as all 35 type-safe Batch 04 battle messages were.

## 42–44. Files and git

**Created:**
- `scripts/audit_ja_phase6_batch04_names.py`
- `scripts/build_ja_phase6_batch04.py` (stages `candidates` and `finalize`)
- `scripts/build_ja_phase6_batch04_handoff.py`
- `tests/test_ja_phase6_batch04.py`
- `tests/fixtures/ja_phase6_batch04_runtime_qa.json`
- this report

**Generated** (ignored `out/`): candidate, controlfix, map, reviewed, fit, FA, name, owner, glossary, context, audit, and handoff JSON files, plus the Batch 04 ROM.

**Not changed:** shared codec, controlfix, injector, glossary, renderer, and font source.

**Reproduce:**
1. `python scripts/audit_ja_phase6_batch04_names.py`
2. `python scripts/build_ja_phase6_batch04.py candidates`
3. Controlfix `ja_phase6_batch04_candidates_input.json` into `ja_phase6_batch04_candidates_controlfix.json`.
4. `python scripts/build_ja_phase6_batch04.py finalize`
5. Controlfix `ja_phase6_batch04_combined_input.json` twice.
6. Run the injector with `--dry-run --fail-on-no-space`, then the real build.
7. `python scripts/build_ja_phase6_batch04_handoff.py`

**`git diff --stat`:** no tracked changes.

**`git status --short`:**

```
?? docs/ja-phase6-batch04-claude-review.md
?? docs/ja-phase6-batch04-technical.md
?? scripts/audit_ja_phase6_batch04_names.py
?? scripts/build_ja_phase6_batch04.py
?? scripts/build_ja_phase6_batch04_handoff.py
?? tests/fixtures/ja_phase6_batch04_claude_review.json
?? tests/fixtures/ja_phase6_batch04_fa_claude_review.json
?? tests/fixtures/ja_phase6_batch04_glossary_candidates.json
?? tests/fixtures/ja_phase6_batch04_official_name_review.json
?? tests/fixtures/ja_phase6_batch04_runtime_qa.json
?? tests/test_ja_phase6_batch04.py
```
