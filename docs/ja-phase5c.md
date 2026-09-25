# Phase 5C: reviewed kana integration and difficulty runtime QA

Status: ROM build and strict byte audit **PASS**; human mGBA visual QA **pending**. No commit, push, BPS release, font/ASM/runtime/graphics patch, kanji, or glossary approval was performed.

## Starting point and review gate

- Branch `japanese-support`; starting HEAD `490279c8dfe06b7da5a3f5eac0369cb24acf12d4`. The worktree already had unrelated uncommitted and untracked Phase 4/5 work. It was preserved.
- Source `rom/unbound.gba` MD5 `9cad8e771940e7f7094d13911552cef0` before and after; never written.
- Baseline: 247 pytest tests passed before Phase 5C work. Final: 253 passed.
- [Claude context review](../tests/fixtures/ja_phase5c_claude_review.json): exactly 116 handoff IDs, no duplicate/extra ID or original/category mismatch; 20 `confirmed`, 96 `needs_context`, zero kanji, all confirmed Japanese PCS-encodable, semantic/control tokens preserved. Candidate text in the 96 holds was not injected. `scr_74AE91` (Zeph, unknown buffer) remains English.
- [Difficulty review](../tests/fixtures/ja_phase5c_difficulty_review.json): 19 confirmed difficulty rows; 14 overlap those 20, five are focused additions. Eight already confirmed Phase 5B rows remain, one clipped warning is out of scope, one is not found, one is not to translate. No global `Difficult`/`Hard` glossary mapping was added.
- The reproducible gate in [build_ja_phase5c.py](../scripts/build_ja_phase5c.py) validates status counts, IDs, metadata, source text, tokens, kana, and codec; it assembles 596 Phase 5B rows + 20 newly confirmed + five focused additions = **621**. Its [merge audit](../out/ja-phase5c-merge-audit.json) records IDs. The prior Phase 5B input/ROM was not modified.

## Difficulty path and fit

The Options Battle Difficulty record at ROM `0x01FB3948` / GBA `0x09FB3948` points to label, four-choice list, and help. The choice pointer list is ROM `0x01FB3A18` / GBA `0x09FB3A18`. The parallel Puzzle record is ROM `0x01FB37B8` / GBA `0x09FB37B8`; its first two choices begin ROM `0x01FB3A4C`. The result-buffer source uses selector variable `0x50DF` and name table ROM `0x01FB54CC`; see [difficulty evidence](../out/ja-phase5c-difficulty-audit.json). These are code/data-reference anchors, not an assertion that every screen has passed mGBA visual QA.

| Entry / role | ROM offset / GBA address | Slot / encoded | Max line pixels | Placement | Owners |
| --- | --- | ---: | ---: | --- | ---: |
| `scr_1F10630` Vanilla → バニラ | `0x01F10630` / `0x09F10630` | 8 / 8 | 30 | in-place | 5 |
| `scr_1F10621` Difficult → ハード | `0x01F10621` / `0x09F10621` | 10 / 8 | 30 | in-place | 5 |
| `scr_1F1063D` Expert → エキスパート | `0x01F1063D` / `0x09F1063D` | 7 / 11 | 60 | relocated to `0x00BA3A7F` | 4 |
| `scr_1F10644` Insane → インセイン | `0x01F10644` / `0x09F10644` | 7 / 10 | 50 | relocated to `0x00BB005E` | 5 |
| `tbl_setting_names_00013_1F4DB23` Battle title → バトルのむずかしさ | `0x01F4DB23` / `0x09F4DB23` | 18 / 14 | 90 | in-place | 1 |
| `tbl_setting_names_00014_1F4DC09` Puzzle title → なぞときのむずかしさ | `0x01F4DC09` / `0x09F4DC09` | 18 / 15 | 100 | in-place | 1 |
| `tbl_menu_game_settings_00035_1F4E037` Battle help | `0x01F4E037` / `0x09F4E037` | 39 / 27 | see focused audit | in-place | 1 |
| `tbl_menu_game_settings_00018_1F4DE12` Puzzle help | `0x01F4DE12` / `0x09F4DE12` | 37 / 27 | see focused audit | in-place | 1 |
| `tbl_menu_game_settings_00000_1F4E26F` complete warning | `0x01F4E26F` / `0x09F4E26F` | 185 / 91 | 150 | in-place | 1 |

The four battle labels are pointer-owned scripts, not no-relocation structured fixed slots. The strict ROM audit checks each relocated payload, all recorded owners, absence of the old pointer anywhere in the output ROM, and the vetted FF allocation. The complete warning owner is ROM `0x01EBD7FC` / GBA `0x09EBD7FC`. Its Claude wording retains the “cannot raise above Hard until cleared” meaning, separate from `...1F4E328`'s “cannot raise again” warning. [Controlfix](../004_controlfix_translations.py) wraps only these two Japanese warnings to 16 visible characters/line, preserving `[red]`, `[black]`, FE newline, FA scroll, and FB page clear. The clipped `tbl_menu_game_settings_00000_1F4E274` is absent from extraction and injection. Its former full-script duplicate is now a single complete menu row.

The measured glyph widths do **not** prove that the live Options selector has sufficient horizontal room. In particular Expert is 60 px, the Battle title 90 px, and the Puzzle title 100 px; no verified renderer-width bound was found. Do not shorten these reviewed names without a new review. mGBA must decide visual fit.

## Extraction and buffer safety

The fixed extractor merges the old complete script duplicate into the menu entry. Re-extraction produced **25,044**, versus `out/unbound-texts.json`'s 25,045; the sole category delta is scripts −1. Vanilla and Difficult's packed `bufferstring 0` owners are recorded. The first strict audit exposed additional Easy pointers at ROM `0x01E6FC43`, `0x01E6FDED` and Challenging at `0x01E6FC32`, all prefixed `85 00` and containing the exact source GBA address. They are now explicit [extractor owners](../001_extract_unbound_text.py); no other category count changed.

The five resolved buffer cases are `scr_1F10323` (selected mode name via `[buffer1]`), `tbl_mission_log_00017_1F560DA` (location name via `[buffer1]`), and `scr_1F9FBCD`, `scr_1F9EAF1`, `scr_1F9F08F` (player name in ブラック[player]). The [controlfixed JSON](../out/ja-phase5c-controlfix.json) switches Japanese→Latin before placeholders and back afterward. Codec-level tests expand a Japanese mode-name buffer containing its own `FC 15`/`FC 16` controls and an English player name, then decode the result correctly. This does **not** prove the game's runtime buffer-copy semantics or visual width; those remain on the mGBA checklist.

## Pipeline and byte audit

Reproduction from the repository root:

```text
python 001_extract_unbound_text.py rom/unbound.gba -o out/ja-phase5c-extracted.json
python 002_prepare_translation_text.py out/ja-phase5c-extracted.json -o out/ja-phase5c-prepared.json
python scripts/build_ja_phase5c.py
python 004_controlfix_translations.py out/ja-phase5c-reviewed-input.json -o out/ja-phase5c-controlfix.json --source out/ja-phase5c-prepared.json --report out/ja-phase5c-controlfix-report.json --target-lang ja
python 005_hybrid_injector.py rom/unbound.gba out/ja-phase5c-controlfix.json -o out/unbound-ja-phase5c.gba --target-lang ja --map-output out/ja-phase5c-dry-run-map.json --dry-run --fail-on-no-space
python 005_hybrid_injector.py rom/unbound.gba out/ja-phase5c-controlfix.json -o out/unbound-ja-phase5c.gba --target-lang ja --map-output out/ja-phase5c-map.json --fail-on-no-space
python scripts/audit_ja_phase5b.py rom/unbound.gba out/unbound-ja-phase5c.gba out/ja-phase5c-controlfix.json out/ja-phase5c-map.json --report out/ja-phase5c-binary-audit.json
python scripts/audit_ja_phase5c_difficulty.py
```

- Controlfix: 621 translated, 26 changed, 11 wrapped, zero remaining control mismatches. Second pass: zero changes and byte-for-byte identical output. `[japanese]`/`[latin]`, FE, FA, FB, FC, FD, color, buffer, and placeholder regression tests pass.
- Strict dry-run and build maps match: 621 input; **452 in-place**, **169 relocated**, **876 pointer writes**; **2,383** unique vetted FF bytes consumed, 613,450 vetted FF bytes remaining. 15 relocations share payloads. Encode errors, pointer mismatches, implausible pointers, no-space, missing relocation, truncation, runtime patches, and graphics patches: all zero.
- [Full binary audit](../out/ja-phase5c-binary-audit.json): **PASS**. Actual changed bytes: 31,063 in-place text; 2,229 relocated payload; 3,059 pointer bytes. These are changed-byte counts, not entry or pointer counts. Unrelated bytes: zero; old pointers for relocated entries: zero. No ASM/font/graphics/runtime writes. Audit code: [audit_ja_phase5b.py](../scripts/audit_ja_phase5b.py).
- [Focused difficulty audit](../out/ja-phase5c-difficulty-binary-audit.json): **PASS**, 26 related entries with original, Japanese, source/target address, slot, encoded size, pixel width, owners, and placement. It maps the pre-fix `scr_1F4E26F` evidence ID to the canonical complete menu ID; it does not use the clipped entry.
- Source MD5 `9cad8e771940e7f7094d13911552cef0`; output MD5 `bfb180b9855a679a27a5bef2f8eafc0e`; output SHA-256 `6e5898dd28f1c623ca725c800fc730506fec4e9a929c7d1dd6a10b5cb9edb590`.
- Applied Japanese entries: **621**. Remaining extracted entries without Japanese application: **24,423** (not a claim that every one is live English runtime text).

## Holds and next human QA

The four prior pointer-owner holds were rechecked by scanning the fresh source ROM for every exact pointer and every interior target within each text slot:

| Held ID | Recorded / exact refs | Additional exact refs | Interior-pointer findings |
| --- | ---: | --- | --- |
| `scr_1A6211` | 19 / 33 | 14 operands shaped as script message opcode `0x67`; see [technical audit](../out/ja-phase5c-technical-audit.json) | none found |
| `tbl_ability_descriptions_00000_24F3C4` | 2 / 3 | aligned `0x0024FB08` | none found |
| `tbl_battle_messages_00000_800880` | 1 / 3 | `0x00FA6636`, `0x00FA6C32` | target `+8`: `0x000C864B`, `0x000D9B23`, `0x0015C921`, `0x0088E51E`, `0x0088ED1E`; target `+11`: `0x00030509` (raw hits; consumers unproven) |
| `tbl_battle_messages_00002_965C16` | 1 / 2 | `0x0096552F` | none found |

These four remain **English**. `scr_1A6211` has strong evidence for all exact references, but its 14 newly found owners still need extraction regression before use; the ability/battle fields lack consumer proof; the first battle text also has interior-pointer candidates requiring classification. The six Pokédex suffix holds (`tbl_pokedex_species_00000`–`00004` and `00006`, addresses `0x01A35814`–`0x01A358EC` in 0x24 strides) remain English: Japanese FireRed's separate “Pokémon” suffix is known, but matching Unbound draw-path behavior has not been established. The other prior technical holds (20 fixed/no-relocation, seven known width failures) also remain English.

The [15-case mGBA subset](../tests/fixtures/ja_phase5c_runtime_subset.json) orders Options first, then Battle/Puzzle choices, warnings, selected-name buffers, NEW GAME branches, player and location buffers, and relocated/owner-corrected labels. Use a disposable save before lowering Battle Difficulty. Confirm full label width, menu highlight/cursor, all pages and color changes, selector return, Japanese name in `[buffer1]`, save/load, and English text regression. Exact routes for the three Black[player] scenes, mission-location log state, and Cube Space are not yet proven and are marked as such in the fixture. A code/ROM PASS is **not** a human runtime PASS.

## Verification and worktree

`python -m pytest`: **253 passed** (after six Phase 5C integration tests). `python -m py_compile` and `git diff --check`: PASS. The changed Phase 5C files are [001 extractor](../001_extract_unbound_text.py), [004 controlfix](../004_controlfix_translations.py), [merge script](../scripts/build_ja_phase5c.py), [focused audit](../scripts/audit_ja_phase5c_difficulty.py), [handoff tests](../tests/test_ja_phase5c_handoff.py), [integration tests](../tests/test_ja_phase5c_integration.py), this document, and [runtime subset](../tests/fixtures/ja_phase5c_runtime_subset.json). The supplied Claude review fixtures were read, not edited. Existing Phase 4/5 dirty files were preserved.

`git diff --stat` reports tracked changes only; it omits untracked Phase 5C and prior Phase 4/5 assets:

```text
 .agents/skills/unbound-translation-run/SKILL.md |  4 +++-
 .gitignore                                      |  1 +
 001_extract_unbound_text.py                     | 11 ++++++++++-
 004_controlfix_translations.py                  | 23 ++++++++++++++++++++++-
 README.md                                       |  7 +++++--
 tests/test_controlfix_cli.py                    | 21 +++++++++++++++++++++
 6 files changed, 62 insertions(+), 5 deletions(-)
```

`git status --short --branch` at completion (existing dirty files included):

```text
## japanese-support
 M .agents/skills/unbound-translation-run/SKILL.md
 M .gitignore
 M 001_extract_unbound_text.py
 M 004_controlfix_translations.py
 M README.md
 M tests/test_controlfix_cli.py
?? docs/ja-phase5-claude-review.md
?? docs/ja-phase5a.md
?? docs/ja-phase5b.md
?? docs/ja-phase5c-claude-review.md
?? docs/ja-phase5c-handoff.md
?? docs/ja-phase5c.md
?? scripts/audit_ja_phase4.py
?? scripts/audit_ja_phase5b.py
?? scripts/audit_ja_phase5c_difficulty.py
?? scripts/build_ja_phase4_selection.py
?? scripts/build_ja_phase5_dataset.py
?? scripts/build_ja_phase5_reviewed.py
?? scripts/build_ja_phase5c.py
?? scripts/build_ja_phase5c_handoff.py
?? tests/fixtures/ja_phase4_claude_review.json
?? tests/fixtures/ja_phase5_claude_review.json
?? tests/fixtures/ja_phase5_fit_review.json
?? tests/fixtures/ja_phase5_glossary_review.json
?? tests/fixtures/ja_phase5_runtime_subset.json
?? tests/fixtures/ja_phase5_selection.json
?? tests/fixtures/ja_phase5b_runtime_subset.json
?? tests/fixtures/ja_phase5c_claude_review.json
?? tests/fixtures/ja_phase5c_difficulty_review.json
?? tests/fixtures/ja_phase5c_runtime_subset.json
?? tests/test_ja_phase5_dataset.py
?? tests/test_ja_phase5_reviewed.py
?? tests/test_ja_phase5c_handoff.py
?? tests/test_ja_phase5c_integration.py
```

ROMs and generated `out/` JSON are ignored local artifacts; do not stage, commit, upload, or release them.
