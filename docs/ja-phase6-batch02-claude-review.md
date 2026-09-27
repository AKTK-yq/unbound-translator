# Phase 6B Batch 02 review

Batch 02 only. Source: `out/phase6/ja_phase6_batch02_for_claude.json` (408 entries). No Batch 03 translation, Python/glossary edit, controlfix, injection, ROM build, commit, or push.

## Outcome and provenance

| Status | Count |
| --- | ---: |
| reviewed | 408 |
| confirmed | 195 |
| existing_official | 0 |
| existing_glossary | 7 |
| needs_context | 156 |
| needs_technical_fit | 50 |

Claude CLI reviewed 200 rows (chunks 01–04 and 06). Claude refused chunk 08's narrative translation, then hit its session limit while handling chunks 05, 07, 09 and 10. On the user's explicit approval, Codex reviewed the remaining 208 rows (chunks 05 and 07–11). `review_provenance` marks every row in `tests/fixtures/ja_phase6_batch02_claude_review.json`; the filename follows the requested handoff contract, **not a claim that all 408 rows were authored by Claude**. Temporary chunk inputs and drafts remain ignored under `out/phase6/batch02_chunks/`.

The final fixture has 252 nonempty kana reviews, including the 50 `needs_technical_fit` drafts. The 156 `needs_context` rows have empty `reviewed_japanese`; the English original is authoritative until the missing name, buffer, or scene evidence is supplied. Of 200 Claude-sourced rows, final status counts are 77 confirmed, 4 existing_glossary, 23 needs_technical_fit, 96 needs_context. Of 208 Codex-sourced rows: 118, 3, 27, 60 respectively.

## Scope and content risk

Extractor categories are **404 `scripts` and 4 `plain_scripts`**. These are event/script rows, not `battle_messages`, `mission_log`, or menu-table categories. Many scripts are NPC/trainer lines, reward prompts, lore, signs or minigame UI, but exact runtime renderer and speaker are not proven by this batch input. Therefore story/NPC, battle, mission and UI *semantic* counts are not asserted as independently verified category counts. Batch 02 includes trainer-battle style lines, mission-like requests and Game Corner UI prompts; they remain in their source script categories.

Warnings in the final review: 120 rows need official-name verification, 49 have unknown dynamic buffer/suffix concerns, 27 have speaker uncertainty, 21 have other context uncertainty, 52 have fixed/width concerns (including two later context holds), 4 flag possible glossary collision. **30 Claude rows lacked original `\\l` page-scroll controls in their drafts**. Those controls were restored provisionally at the draft end, with `control_placement_review_required`, and the rows were downgraded to `needs_technical_fit`. Their layout is **not approved for injection**; a later human/controlfix review must position them naturally. Two further drafts were held because `Prof Log` did not exactly match approved `Prof. Log`, and `Cube` did not match the permitted script scope. Source `\\07`, `\\08`, `\\0C` cases remain `needs_context` rather than guessed suffixes.

`tests/fixtures/ja_phase6_batch02_official_name_review.json` lists **153 entry–term checks across 120 entries**, including English source, term type, null Japanese candidate unless verified, PokeAPI applicability, and reason. No memory-only Pokémon/Move/Item/Ability/Type/Nature name was accepted as official. This phase did not call PokeAPI. Exact English-name and ja-hrkt verification belongs to the next technical pass. Unbound-only place/organization names with provisional kana are kept separate from official franchise terms.

`tests/fixtures/ja_phase6_batch02_glossary_candidates.json` has **18 unapproved proposals**: 12 first raised in Batch 02, 6 carried over from the Batch 01 style handoff. Each has source, proposed kana, type, confidence, reason and affected IDs. Nothing was added to `glossaries/ja.json`. `Ace` was not applied inside `Aerial Ace`; scoped terms such as `Cube`, `Hard`, `Difficult`, `Option`, and `Log` were not globally substituted.

## Validation

- Exactly 408 unique input IDs, in order; duplicate/extra/missing IDs **0**. `original`, `category`, conversation/scene metadata copied from the input. All three output JSON files parse.
- Among 252 nonempty reviewed translations: protected/semantic token mismatches **0**; existing backslash-control count mismatches, including `\\l`, FE/FA/FB/FC/FD-related escapes, button/color/quote tokens **0**; Han characters **0**; unsupported Japanese PCS characters **0**. All nonempty `glossary_terms_used` claims match the current scoped matcher; outside-scope matches **0**. Empty `needs_context` rows are not counted as translations and preserve their source original separately.
- Claude's wrapper ASCII quotes were removed from the affected Game Corner drafts. One accidental Han character (`買`) became kana (`か`) in `scr_1F0DA30`. These are mechanical review-format corrections, not approval of name or layout.
- No controlfix, injector dry-run, ROM generation, runtime check or PokeAPI verification was performed in this phase. `needs_technical_fit` means meaning has a draft, not that byte/slot/pixel layout passed.

## Style for Batch 03 handoff (guidance only)

Keep kana-only, moderate wakachigaki and the existing P7 pacing baseline. Do not infer speaker identity or carry one NPC's voice into another. Preserve source controls, especially page scrolls, at review time; do not rely on a later controlfix pass to reconstruct intent. Treat unknown `[bufferN]` producers and `\\07`/`\\08`/`\\0C` as unresolved. Use only exact, scope-valid approved glossary terms; carry proposal-only locations/features separately. Never fill Pokémon, Move, Item, Ability, Type or Nature names from memory; list exact English terms for later PokeAPI ja-hrkt review. Keep `$` and context-appropriate counters (`ひき`, `こ`, `かい`, `とおり`). Batch 03 itself was not processed.
