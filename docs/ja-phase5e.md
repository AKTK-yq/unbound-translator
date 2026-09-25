# Japanese Phase 5E: reviewed glossary and runtime QA build

## Starting state and inputs

- Branch: `japanese-support`; starting HEAD: `22a425f6850308383ae1bee746a3c4ebdb47cf0d`.
- Baseline: 253 tests and 16 subtests passed. Source ROM MD5: `9cad8e771940e7f7094d13911552cef0`.
- The three pre-existing untracked Phase 5D review files were preserved unchanged.
- Phase 5D review validated: 122 terms, 114 `project_standard`, 8 unresolved; the 114-row patch exactly covers approved terms, with no duplicate source, kanji, or PCS encode error. One affected ID was stale: clipped `tbl_menu_game_settings_00000_1F4E274` maps to complete `...1F4E26F` at ROM `0x01F4E26F`, GBA `0x09F4E26F`, pointer owner `0x01EBD7FC`.
- Phase 5D recheck: 96 entries = 52 ready + 44 held (36 technical + 8 visual/context).

## Glossary and translations

- `glossaries/ja.json`: 25 existing + 114 approved = 139 terms. The 8 unresolved terms (`Gruff`, `Exp. Gain`, `Capped Share`, `Djinn`, `High King`, `Unique Horn`, `Dancing`, `Sphere`) were **not** adopted. Review has 37 context-sensitive terms; 29 approved terms are non-global, plus 2 existing Option(s) terms now scoped to `settings_ui` = 31 non-global terms in the merged glossary.
- Context restrictions use `context_scope`, `global_replace`, category and exact `entry_ids`. `Difficult` applies only to the known battle-difficulty choice; Safari `Hard` is not globally replaced. `Black [player]` and `New Game \\+` retain controls. `Route [N]` substitutes digits only in `map_names`. `Log`, `The Shadows`, and `Cube` cannot match unrelated ordinary prose through their restricted categories or IDs.
- The `Option`/`Options` terms match settings UI labels as `せってい`, not ordinary prose or battle choices. Existing Phase 4/5 reviewed wording was not bulk rewritten. The audit reports zero conflicts in translated entries, but visual coherence of every setting remains human QA.
- `Oddish Leaves` item-name row `tbl_item_names_00363_EB92C0`, ROM `0x00EB92C0`, GBA `0x08EB92C0`, 14-byte fixed slot: `[japanese]ナゾノクサのはっぱ[latin]` encodes to exactly 14 bytes, in-place. The two reviewed prose occurrences `scr_746471` and `scr_75318A` retain their existing spacing; the glossary term is `item_names`-only.
- Reproducible build: `scripts/build_ja_phase5e_glossary.py` validates/promotes the patch; `scripts/build_ja_phase5e.py` rebuilds Phase 5C applied input, adds 52 ready labels and the item-name correction. Phase 5C input is untouched. Final 674 Japanese entries = 621 + 52 + 1; 24,370 extracted entries remain English.
- Ready 52: name labels 25, places 9, mission titles 14, trainer classes 4. All 52 have approved spellings, PCS byte/slot/pixel-width and pointer-owner records in `out/ja-phase5e-merge-audit.json`. Expected fit: 24 in-place, 28 relocation. Mission titles have no inserted word spaces. These Unbound names are `project_standard`, not claimed official.
- Literal packed `bufferstring` references (`85 00 <pointer>`) added 22 pointer owners across 13 entries, after ROM-byte verification. Extraction still has 25,044 entries and unchanged category counts. The extra aligned Blizzard City pointer at `0x00721150` was not accepted without consumer proof; this label is in-place, so no pointer update depends on it.
- Approved glossary application: 89 of 114 terms occur in 125 translated entries, with zero detected conflicts. The other approved terms remain available for later translations; `out/ja-phase5e-glossary-audit.json` records per-term scope, affected IDs, actually applied IDs, and conflict status.

## Remaining 44 entries

The complete evidence and next action for every entry are in `out/ja-phase5e-remaining-context.json`. Classification is triage, **not** translation approval:

| Class | Count | Finding |
|---|---:|---|
| A | 4 | Three credit blocks are real staff names and intentionally stay Latin; one clipped difficulty warning is superseded by the translated complete entry. |
| B | 16 | Gender fragments, battle grammar fragments, and five script-buffer texts need exact buffer producer and insertion-sentence tracing. No buffer was fully resolved. |
| C | 10 | Five short weekday labels and five legacy trainer names are fixed-table records with no literal pointer owners. The table consumer/index and runtime reachability remain unproven; none were injected. |
| D | 2 | `scr_7A95BA` begins with raw `D1`; `scr_750C28` begins with raw `C1`. Both have exact pointer metadata, so clipping or false extraction cannot yet be asserted. |
| E | 3 | `Exp. Gain` help, critical-hit color scope, and Mission Log A–Z sort need UI/renderer or comparator evidence. |
| F | 8 | Trim colour, VICTORIES, Gruff, and five Pokédex form names need visual/wording review. |
| H | 1 | `scr_1080302` remains suspected non-text; no injection. |

The technical 36 are A4+B16+C10+D2+E3+H1. Four are disposition-resolved without new translation (three credits retained, one duplicate excluded); the other 32 still need technical investigation. Nine entries need Claude wording review, nine need human visual review. These counts overlap because the eight visual/context entries and the options help both need review. No entry from the held 44 was translated.

### Priority evidence

- **Options:** actual extracted label `Exp. Gain` is at ROM `0x01F4DB35`, GBA `0x09F4DB35`, owner `0x01FB3960`. Choices are `Exp. Share` at `0x01F4DC57` (owner `0x01FB3A10`) and `Capped Exp. Share` at `0x01F4DC62` (owner `0x01FB3A14`). The held prose at `scr_1F1057C` says the shorter `Capped Share`; screen wording should be verified before translation. Neither term was put in the glossary.
- **Gruff:** `scr_1FAE999`, ROM `0x01FAE999`, GBA `0x09FAE999`, has 14 script pointer sources and functions as a reused name label. Person name versus nickname/spelling is not proven; held English.
- **Five forms:** structured table at ROM `0x01A35450`, GBA `0x09A35450`, has 8-byte records: 4-byte text pointer + 2-byte value + 2 zero bytes. The value indexes the fixed Pokémon-name table at ROM `0x0166A98C + value*11`. `Djinn` points with value 1210 (`Calyrex`); `High King` is shared by values 1211 (`Calyrex`) and 1213 (`Ponyta`); `Unique Horn` by 1214 (`Rapidash`) and 1220 (`Mr. Mime`); `Dancing` by 1224 (`Slowking`); `Sphere` by 1237 (`Electrode`) and 1238 (`Typhlosion`). This proves table record relationships, **not** direct runtime form-to-species display semantics. Shared strings and apparently surprising pairs require renderer/index tracing and Claude/human review; no names were invented.
- **Buffers:** several `bufferstring` source *pointers* are now proven for the newly relocated name labels. This does not prove the dynamic value or insertion site for the held 16 buffer-dependent texts. They stay English. Battle possessive fragments require a grammar-aware runtime trace, not word-for-word substitution.
- **Leading bytes:** raw prefixes and every currently extracted pointer owner are recorded per entry. The source string is not normalized or skipped to its interior without code-level consumer evidence.

## Build and safety

Pipeline run: fresh extract (`out/ja-phase5e-extracted.json`) → prepare (`out/ja-phase5e-prepared.json`) → reviewed merge (`out/ja-phase5e-reviewed-input.json`) → controlfix (`out/ja-phase5e-controlfix.json`) → injector. This is reviewed-translation integration, not a new LLM batch.

- Controlfix: 674 translated, 79 changed, 11 wrapped, zero remaining control mismatches. Re-running on its own output changed 0 entries and produced a byte-identical JSON. FE/FA/FB/FC/FD and dynamic templates were retained by existing codec/control tests and the new template tests.
- Strict dry-run (`out/ja-phase5e-dry-run-map.json`): 674 input; encode errors 0; pointer mismatches 0; implausible pointers 0; missing relocation 0; no-space 0; fixed/no-relocation truncations 0; control mismatches 0; runtime patches 0; graphics patches 0.
- Full ROM `out/unbound-ja-phase5e.gba`; map `out/ja-phase5e-map.json`. In-place 477, relocated 197 (15 deduplicated relocations), pointer writes 1,999, vetted FF used 2,654 of 615,833 bytes, 613,179 remaining. No reclaimed text or non-vetted allocation.
- Strict whole-ROM binary audit `out/ja-phase5e-binary-audit.json`: PASS. Changed bytes are only in-place text (31,442 bytes), relocated text (2,472 changed bytes), and pointer writes (7,548 changed bytes). Zero unexpected differences; zero font, ASM, runtime or graphics patch. Note changed-byte counts exclude bytes that happen to equal the source, and relocation payload allocation is 2,654 unique bytes.
- Source MD5 after build: `9cad8e771940e7f7094d13911552cef0`; output MD5: `c067bf8c8e60b8e8ca3bc0df42e8820a`; output SHA-256: `4cccd4887f9056cc14d35839b30d922bd56cada621a36492314c29bf6fbce3fc`.
- `tests/fixtures/ja_phase5e_runtime_subset.json` has 25 human mGBA cases. Start with NEW GAME and nearby place labels, then Options, and use progressed saves for named characters, missions, trainer classes, and item. Routes marked unknown are intentionally not asserted runtime-reachable; the ROM audit cannot replace human display QA.

## Validation and handoff

Full pytest: **261 passed, 16 subtests passed**. `py_compile` for every changed Python file: PASS. `git diff --check`: PASS (Git prints only LF-to-CRLF checkout warnings on Windows). Tracked `git diff --stat`: 8 files changed, 1,422 insertions, 43 deletions; this excludes the new scripts, test, fixture and report because they are untracked. Final branch/status: `japanese-support`, no staged changes; tracked edits are `.agents/skills/unbound-translation-run/SKILL.md`, `001_extract_unbound_text.py`, `003_llm_translate.py`, `README.md`, `glossaries/ja.json`, `lib/translation_glossary.py`, `tests/test_ja_phase5_dataset.py`, `tests/test_translation_glossary.py`. Untracked files are this report, the three pre-existing Phase 5D review artifacts, the four new Phase 5E build/audit scripts, `tests/fixtures/ja_phase5e_runtime_subset.json`, and `tests/test_ja_phase5e.py`. No commit or push.

Source and output ROMs remain ignored private local files. Follow-up: trace 16 dynamic-buffer uses, 10 fixed-table consumers, two leading-byte cases, Options renderer/help and Mission Log sort; obtain mGBA screenshots for nine visual/wording cases before any additional Japanese translation. The runtime QA ROM is a validation artifact, not a release candidate.
