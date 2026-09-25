# Japanese Phase 5A: untranslated runtime-validation dataset

Phase 5A selects **750** entries from the English Unbound ROM for later kana-only review. It does not translate new NPC/story prose, inject text, or build a ROM/BPS. The private ROM remains `rom/unbound.gba` (MD5 `9cad8e771940e7f7094d13911552cef0`). Phase 4 was already committed at start: branch `japanese-support`, HEAD `490279c8dfe06b7da5a3f5eac0369cb24acf12d4`; baseline suite **219 passed**. Existing untracked Phase 4 scripts/fixture and `.sav` files were left intact.

## Build inputs and outputs

From repository root, with development dependencies installed:

```text
python 001_extract_unbound_text.py rom/unbound.gba -o out/ja-phase5a-extracted.json
python 002_prepare_translation_text.py out/ja-phase5a-extracted.json -o out/ja-phase5a-prepared.json
python scripts/build_ja_phase4_selection.py out/ja-phase5a-prepared.json tests/fixtures/ja_phase4_selection.json -o out/unbound-ja-phase4-reviewed-translated.json
python 004_controlfix_translations.py out/unbound-ja-phase4-reviewed-translated.json -o out/unbound-ja-phase4-reviewed-controlfix.json --source out/ja-phase5a-prepared.json --report out/unbound-ja-phase4-reviewed-controlfix-report.json --target-lang ja
python scripts/build_ja_phase5_dataset.py out/ja-phase5a-prepared.json out/ja-phase5a-extracted.json rom/unbound.gba --pokeapi-workers 6
python -m pytest
```

The builder writes `tests/fixtures/ja_phase5_selection.json`, `out/ja_phase5_for_claude.json`, `tests/fixtures/ja_phase5_runtime_subset.json`, `out/ja_phase5_capacity.json`, and `out/ja_phase5_coverage.json`. `out/` JSON is private local output and ignored by Git; rerun the command to regenerate it. PokeAPI responses use ignored `.cache/pokeapi`. The builder checks source ROM MD5, uses the project PCS codec, and never invokes the LLM or injector. [PokéAPI v2 documentation](https://pokeapi.co/docs/v2) documents localized `names` and resource endpoints; the repository localizer additionally checks the English value against the ROM row before accepting `ja-hrkt`.

The manifest retains lossless `original`, prepared `translation_source`, ROM offset/GBA address, slot length, exact pointer owners, semantic placeholders, controls, expected display family, runtime confidence/reason, and risk. `source_encoded_size` is read from the original ROM up to the PCS terminator, not guessed from visible characters. Context in the Claude handoff is same-category text within 0x200 ROM bytes; **adjacency does not prove a scene, sequence, or speaker**. Speakers remain `unknown`; no person was inferred from writing style. `max_or_expected_width` is `null` where an actual window bound is unproven.

## Selection and runtime evidence

All **55 extractor categories** are represented. Phase 4's 59 reviewed entries seed the selection; remaining rows come from deterministic, category-balanced scoring. Event-script operands and structured table ownership are the basis for B, never a raw ASCII hit. Generic `pointer_texts` remain C. D-class legacy/dead candidates are excluded.

| Confidence | Count | Meaning |
| --- | ---: | --- |
| A | 20 | Prior NEW GAME runtime evidence or its tested script flow; branch-specific text still needs observation. |
| B | 723 | Owned current script/table structure; individual row may depend on conditions or location. |
| C | 7 | Extracted pointer ownership, but caller/renderer runtime use not proven. |
| D | 0 | Suspected legacy/dead text omitted. |

Category counts:

| category | count | category | count | category | count |
|---|---:|---|---:|---|---:|
| ability_descriptions | 7 | ability_names | 17 | battle_messages | 55 |
| credits_text | 3 | day_names | 5 | gendered_dialogue_fragments | 5 |
| habitat_names | 3 | item_descriptions | 7 | item_names | 21 |
| map_names | 11 | menu_battle | 9 | menu_common | 17 |
| menu_cube | 5 | menu_cube_system | 5 | menu_game_settings | 10 |
| menu_item_storage | 9 | menu_link_controls | 5 | menu_list_labels | 10 |
| menu_mining | 1 | menu_multiplayer | 4 | menu_options | 16 |
| menu_pause | 10 | menu_pc | 16 | menu_pcoptions | 3 |
| menu_pokedex | 1 | menu_pokemon | 13 | menu_pokemon_options | 5 |
| menu_pokemon_summary | 9 | menu_save | 9 | menu_save_prompts | 1 |
| menu_saving_messages | 6 | menu_shop | 5 | menu_standalone_labels | 1 |
| menu_trainer_card | 5 | mission_descriptions | 16 | mission_log | 16 |
| mission_names | 17 | mission_objectives | 11 | move_descriptions | 7 |
| move_learning | 5 | move_names | 21 | nature_names | 17 |
| plain_scripts | 7 | pointer_texts | 7 | pokedex_descriptions | 7 |
| pokedex_form_names | 5 | pokedex_species | 7 | pokemon_names | 21 |
| scripts | 230 | setting_names | 9 | start_menu_labels | 7 |
| trade_messages | 5 | trainer_classes | 5 | trainer_names | 5 |
| type_names | 16 |  |  |  |  |

## Renderer and control coverage

The manifest's `renderer` is an **expected display-family classification**, not proof of an ARM/Thumb routine. Data tables such as Pokémon names can feed multiple screens. Of 39 display-family groups, 11 were selected in Phase 4 and 28 are newly represented here. New groups include ability/type/nature names, description and Pokédex UI, PC, shop, save, Bag storage, battle menu, trainer card, cube, multiplayer, and credits. Thirty-three entries have `renderer: unknown`; their IDs and each group's categories/examples are in `out/ja_phase5_coverage.json`. The same file separates `previously_selected` from `new_phase5a`; neither tag claims every row was seen in mGBA.

Control counts are entries containing each feature, not raw token totals:

| Feature | Entries |
| --- | ---: |
| FE / FA / FB | 328 / 75 / 158 |
| FC / FD | 121 / 134 |
| Dynamic buffer/name token | 134 |
| Prepared semantic placeholder | 243 |
| Two or more FB page clears | 73 |

Frequent combinations: no listed control 393; FE only 71; FE+FD 60; FE+FA+FB 35; FE+FB 32; FE+FB+FC 21; FE+FB+FC+FD 21. The full combination histogram is in `out/ja_phase5_coverage.json`. The actual ROM bytes are parsed at PCS command boundaries, so a command argument equal to `FE` is not miscounted as a line break. Japanese text around player/item/number/location buffers is **future QA coverage**, not an assertion that untranslated entries already switch font pages correctly.

## Official terms, glossary, handoff

PokeAPI `ja-hrkt` was verified for **106** selected rows: Pokémon 18, moves 18, items 18, abilities 17, natures 17, types 14, Pokédex species 3, Pokédex description 1. The localizer checks the English name/row and the Japanese result passes the Japanese PCS encoder; 45 eligible rows remain `unverified` and receive no automatic Japanese value. `official_translation`, provenance, and status are saved in both the manifest and Claude handoff. No ordinary `ja` (kanji) fallback is used.

The existing `glossaries/ja.json` matched **43 entries / 56 occurrences**. Its target wording is metadata for Claude, not permission to auto-translate the whole sentence. Approved full-entry values total **166**: 59 Phase 4 reviewed, 106 PokeAPI, 1 exact existing glossary label. The other **584** remain untranslated. `Vanilla` and `Difficult` have no approved Japanese glossary targets.

Twenty-three unapproved `glossary_candidate` labels/titles are listed in `out/ja_phase5_coverage.json`, with `target: null`. Examples: Bellin Town, Crater Town, Dresco Town, Frozen Heights, Tehl Town, Blizzard City, Fallshore City, Tarmigan Town, The Battle of Antisis, and The Endless Nightmare. Some may be ordinary franchise terms rather than Unbound-specific; a human must confirm both scope and Japanese wording before glossary promotion. No candidate was added to `glossaries/ja.json`.

Claude receives **750** rows in `out/ja_phase5_for_claude.json`, including context, protected tokens, controls, approved values, glossary matches, official names, and unknown speaker markers. Existing approved names should not be retranslated. Story/NPC prose remains for Claude's next phase.

## Capacity preflight, not an injection result

The set has **135 fixed slots**, **623 pointer-owned rows**, **615 potentially relocatable rows**, and **8 explicit `no_relocation` rows**. Fixed and `no_relocation` counts overlap by design. Total original slot storage is **37,141 bytes**, mean **49.52 bytes**. Category-level totals, means, owner/fixed/relocatable counts are in `out/ja_phase5_capacity.json`.

The injector's own vetted FF allowlist, exclusions, margins, and full extracted-text protection leave **615,833 shared bytes** across the original ROM. This capacity is shared with future translations/patches, not reserved for Phase 5A. Phase 4's 59 translated/source byte ratios supply rough factors; known Phase 4 and PokeAPI sizes use their actual encodings.

| Scenario | Factor for untranslated rows | Estimated relocations | Destination bytes | Fixed overflows | Shared FF used |
| --- | ---: | ---: | ---: | ---: | ---: |
| Lower quartile | 0.682 | 33 | 379 | 9 | 0.06% |
| Median | 0.833 | 33 | 379 | 9 | 0.06% |
| 90th percentile | 1.600 | 579 | 52,488 | 39 | 8.52% |

Based only on this bounded set, **total FF exhaustion appears unlikely** under these scenarios; fixed-slot fit is the more immediate risk. This is not a promise: Claude wording, controlfix page breaks, other translated entries, and actual allocation order can change both counts. No injector dry-run or ROM build was performed in Phase 5A.

## Runtime QA subset and Phase 5B

`tests/fixtures/ja_phase5_runtime_subset.json` contains **80** selected IDs: 30 NEW GAME text paths plus one further intro text, 9 NPC/event entries, 8 battle messages, 10 mission entries, and 22 menu/data lookups. It includes 48 entries not in Phase 4. Menu/data examples span pause, options, PC, shop, save, Bag/item storage, Pokémon, and six official name categories. NPC map reachability is not independently resolved; the subset labels those routes explicitly. Human testing starts from NEW GAME, then nearby UI, conditional battle, Mission Log, and finally NPC/event text once its map is located.

Phase 5B should: have Claude review only the 584 unapproved entries with their protected-token/context data; verify proposed new proper nouns before glossary promotion; resolve speaker/event and buffer provenance where needed; run controlfix twice, fixed-slot and pixel-width audits, strict injector dry-run, binary diff audit, and mGBA checks against the 80-entry subset. No kanji, font/renderer patch, full 23k-entry translation, release BPS, commit, or push belongs to Phase 5A.

## Unresolved

- Seven C-class `pointer_texts`, 33 unknown display-family entries, and all unlocated NPC events require runtime tracing. Even B-class table rows may be conditional or unused.
- No speaker identity or exact UI window bound is asserted. ROM-neighbor context can cross scenes.
- Forty-five PokeAPI-eligible rows did not yield validated `ja-hrkt`; they remain untranslated, not guessed.
- Eight selected originals produce a different encoded length when re-encoded through the Latin PCS codec (credits/plain scripts); the manifest flags them. Preserve original bytes and investigate before their translation.
- Fixed slots may fail after complete Japanese wording. The 615,833-byte free estimate does not cure a no-relocation or narrow-window failure.
