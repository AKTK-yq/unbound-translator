# Japanese Phase 6A: production translation selection

## 1. Baseline and boundary

Starting branch `japanese-support`, HEAD/Phase 5 final commit
`34c2866b1ffe380ea8abd63c5752f109926bdccc` (`a`); starting worktree
clean. The commit includes the Phase 5 final report and glossary. English
`rom/unbound.gba` MD5 is `9cad8e771940e7f7094d13911552cef0`.
Baseline `.venv/Scripts/python.exe -m pytest -q`: **277 passed, 16 subtests
passed**. Phase 5F controlfixed input has **677** applied IDs. Its strict map
reports 478 in-place, 199 relocated, 2,009 pointer writes, 2,654 unique vetted
FF bytes consumed, **613,179** remaining, and zero encode, pointer, truncation,
runtime-patch, or graphics-patch errors. Phase 5 human runtime checks are
recorded in earlier reports; Phase 6A has no new gameplay observations.

This phase creates selection and review data only. No new prose translation,
controlfix, injection, ROM, BPS, font/ASM/renderer/graphics/pacing change,
commit, or push. Kana-only and the Phase 5F dynamic-buffer page-switch contract
remain unchanged.

## 2. Selection and exclusions

`scripts/build_ja_phase6a.py` reads the Phase 5E prepared extraction, Phase 5F
applied IDs and held audit, original ROM, glossary, PokeAPI cache, and Phase 5F
map. It checks ROM MD5 and uses the PCS decoder to measure source encoded
lengths. `tests/fixtures/ja_phase6_selection.json` contains **2,500 new
targets**; no Phase 5 applied ID is reselected. The 44 original Phase 5 held
rows contain one subsequently applied bulb dialogue. The remaining **43** are
listed separately under `excluded_phase5_unresolved` with
`phase5_unresolved: true` and excluded from every batch. This is deliberately
more conservative than excluding only the 39 substantive unresolved cases.

All 2,500 are **B** (owned script operand or extractor-defined table); A 0,
C 0, D 0. Phase 5 already covers the known A-class NEW GAME text. B does
**not** prove each row is reached in the current game. Suspected legacy/old
tables, generic `pointer_texts`, unowned script text, and raw ROM hits are not
included. Text-table B evidence is table structure, not a played screen.
Selection favors the owner-proven NPC text bank, then high-bank script
operands; exact map, branch, chronology, and speaker are not inferred from
ROM locality. Some script rows could still be unused; Phase 6B must trace them.

Category counts (all manifest entries are new translation targets):

| Category | Count | Category | Count |
| --- | ---: | --- | ---: |
| scripts | 1478 | plain_scripts | 7 |
| battle_messages | 235 | mission_names | 32 |
| mission_descriptions | 36 | mission_objectives | 25 |
| mission_log | 7 | menu_battle | 24 |
| menu_common | 19 | menu_cube_system | 14 |
| menu_game_settings | 35 | menu_item_storage | 9 |
| menu_link_controls | 15 | menu_list_labels | 38 |
| menu_options | 5 | menu_pause | 1 |
| menu_pc | 30 | menu_pokemon | 7 |
| menu_pokemon_summary | 12 | menu_save | 1 |
| menu_shop | 1 | menu_trainer_card | 14 |
| setting_names | 8 | start_menu_labels | 3 |
| pokemon_names | 58 | move_names | 58 |
| item_names | 58 | ability_names | 32 |
| type_names | 6 | nature_names | 6 |
| trainer_names | 23 | trainer_classes | 12 |
| map_names | 22 | pokedex_species | 16 |
| pokedex_descriptions | 25 | move_descriptions | 46 |
| item_descriptions | 46 | ability_descriptions | 28 |
| habitat_names | 3 | move_learning | 3 |
| trade_messages | 2 |  |  |

Story/NPC (`scripts` plus `plain_scripts`) totals **1,485**. Nearby script
pointer operands and text offsets form **624** *operand-neighborhood* groups;
these are batch-contiguity aids, **not proven conversations**. `scene_id` is
null for scripts, `speaker` and `speaker_confidence` are `unknown` for all
2,500, and `sequence_index` is operand order rather than proven dialogue
order. No speaker name was guessed. Claude context is limited to up to three
nearby script operands on either side within strict owner/text distance;
confidence is `medium` for structural adjacency, never high. Context is
absent where this test fails. A neighboring Phase 5 applied row carries both
English and its Japanese text, marked `already_translated`; selected rows
themselves remain `already_translated: false`.

## 3. Renderer, controls, and risk

All selected display-family labels occur among Phase 5 applied categories:
**new renderer groups 0**. This describes classification coverage, not proof
that every table uses one concrete renderer routine. There are **8**
`unknown` renderer rows (e.g. move-learning/trade/habitat categories); these
need Phase 6B tracing. Exact counts for each of the 29 classified groups are
in `out/phase6/ja_phase6a_coverage.json`; event dialogue 1,485 and battle
text printer 235 dominate.

Control coverage counts entries containing a feature, not raw byte frequency:

| FE | FA | FB | FC | FD | Dynamic buffer | Prepared placeholder | 2+ FB | Existing page switch |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1,512 | 352 | 789 | 476 | 514 | 514 | 1,060 | 397 | 0 |

`FC` is present in English source but no source row already uses `FC 15/16`.
Phase 6B will add Japanese/Latin switches through existing controlfix and
must recheck buffers after expansion. Common combinations: none 802; FE 453;
FE+FB 225; FE+FD 201; FE+FA+FB 118. Full histogram and examples are in the
coverage JSON. `protected_tokens`, prepared placeholder mappings, and exact
ROM control-byte classification travel with each Claude row. No text-control
repair was run here.

Technical risk: **high 1,766, medium 510, low 224**. A high flag includes
multi-page/special controls or multiple owners, not necessarily a known
failure. **236 fixed/non-relocatable** rows, including **2 explicit
`no_relocation`**; lists, original slots, deterministic encoded sizes, and
pointer owners are in `out/phase6/ja_phase6a_fixed_audit.json`. Six official
type names already exceed their seven-byte fixed slots with page switches;
they remain approved *terms* but require fit/renderer review before injection.
No `translated_fixed` or truncation was fabricated.

## 4. Glossary, official terms, and Claude batches

`glossaries/ja.json` is authoritative. The builder calls its scoped matcher
with the actual category and entry ID. `Difficult`, `Hard`, `Log`, `Cube`,
`The Shadows`, `Route [N]`, `Black [player]`, and `New Game \\+` are not
globally substituted. `glossary_term_details` retains scope/type; exact
whole-string matches only may become deterministic translations.

PokeAPI localization uses the repository's English-match/row-ID validator,
`ja-hrkt`, kana-only PCS encoder, and cache under ignored `.cache/pokeapi`.
The first build used `--live-pokeapi` to populate missing records; normal
rebuilds work offline from cache. **213** selected rows have validated
PokeAPI values, **33** have exact approved glossary values: **246
deterministic/lexically resolved**, **2,254 still need Claude wording**.
Another 132 PokeAPI-eligible selected rows remain unverified; neither a
kanji fallback nor an invented translation was accepted. Deterministic does
not imply ROM fit: six fixed type names require special review.

Six ignored local handoff files exist under `out/phase6/`, 400–500 rows each:

| Batch | Rows | Main material |
| --- | ---: | --- |
| `ja_phase6_batch01_for_claude.json` | 407 | NPC/event scripts, three plain scripts |
| `ja_phase6_batch02_for_claude.json` | 408 | NPC/event scripts, four plain scripts |
| `ja_phase6_batch03_for_claude.json` | 408 | NPC/event scripts |
| `ja_phase6_batch04_for_claude.json` | 408 | scripts, missions, first battle messages |
| `ja_phase6_batch05_for_claude.json` | 408 | battle messages, menus/settings |
| `ja_phase6_batch06_for_claude.json` | 461 | names, descriptions, remaining UI |

These are review/handoff data, **not 2,500 completed translations**. IDs are
unique within/across files; union equals manifest; operand-neighborhood
groups are not split. Each row has requested context, owner-group,
unknown-speaker marker, runtime note, protected tokens, controls, buffers,
official and scoped glossary terms, slot and risk metadata. Chapter/game
progression cannot be read reliably from pointer order, so batch 1–3 labels
do not assert early/mid-game chronology.

## 5. Capacity forecast, not injection

Selected source slots total **181,717 bytes**; actual source PCS through
terminators totals **180,893 bytes**. Phase 5F map has **613,179 vetted FF
bytes remaining**. For the 677 Phase 5 translations, translated PCS/source
slot ratios have 25th percentile 0.667, median 0.846, and 90th percentile
1.600. For unresolved wording, these factors estimate encoded length; the
246 deterministic values use actual Japanese PCS size. Results:

| Scenario | Estimated Japanese PCS bytes | In-place | Relocations | Destination bytes / upper-bound FF consumption | Fixed overflow | FF lower-bound remainder |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 25th | 121,497 | 2,471 | 23 | 256 | 6 | 612,923 |
| Median | 153,444 | 2,471 | 23 | 256 | 6 | 612,923 |
| 90th | 287,775 | 240 | 2,226 | 284,499 | 34 | 328,680 |

The broad range is intentional: line wrapping, natural Japanese wording,
page switches, category mix, deduplication, allocator fragmentation, and
fixed UI widths are not known until translation/controlfix/inject. The
forecast is **not a dry-run, reservation, or capacity guarantee**. It is
computed from the Phase 5 map; font/code storage is not being allocated.

## 6. Human QA candidates and next phase

`tests/fixtures/ja_phase6_runtime_candidates.json` has **120** selected IDs:
1 conditional NEW GAME settings row, 32 script/NPC event rows (exact maps
unproven), 26 battle, 15 mission, 46 menu/data lookups. All currently
verified NEW GAME intro dialogue was applied in Phase 5, so there is no new
A-class intro dialogue in this selection. Candidate inclusion is not a claim
of play-tested reachability. Prioritize the conditional NEW GAME setting,
then menus, battle and Mission Log; locate NPC maps before demanding a human
confirmation. Fixed, buffer, page and risk examples are included.

Phase 6B: have Claude translate only 2,254 unresolved rows in the provided
batches; preserve kana-only protected tokens and scoped terms; review six
fixed type-name fits and all 236 fixed rows; map NPC scene/speaker and eight
unknown display families; run normal controlfix twice, strict injector
dry-run, relocation/pointer/free-space audit, ROM binary audit, then human
mGBA checks. Keep existing `[japanese][latin][buffer][japanese]` dynamic
buffer policy and P7 pacing baseline. Do not silently truncate or treat a
pointer-neighbor group as confirmed dialogue.

## 7. Rebuild and checks

From repository root (on Windows use `.venv/Scripts/python.exe` instead of
`python` when the system Python lacks pytest):

```text
python scripts/build_ja_phase6a.py --live-pokeapi
python scripts/build_ja_phase6a.py
python -m py_compile scripts/build_ja_phase6a.py tests/test_ja_phase6a.py
python -m pytest
git diff --check
```

`--live-pokeapi` only populates ignored cache and is optional after the
first build. Batch and audit JSON under `out/phase6/` are ignored local
artifacts; the tracked selection and QA fixtures plus builder reproduce
them. No private ROM is tracked or distributed.
