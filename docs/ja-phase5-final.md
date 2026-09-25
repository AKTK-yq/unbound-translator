# Pokémon Unbound Japanese Phase 5F final integration

## Start and scope

Branch `japanese-support`; HEAD `22a425f6850308383ae1bee746a3c4ebdb47cf0d`.
Starting worktree contained Phase 5E/5F work plus the newly supplied Claude
fixture; preserved without reset or deletion. Starting pytest:
**270 passed, 16 subtests passed**. English source ROM MD5
`9cad8e771940e7f7094d13911552cef0`; Phase 5E ROM MD5
`c067bf8c8e60b8e8ca3bc0df42e8820a`, SHA-256
`4cccd4887f9056cc14d35839b30d922bd56cada621a36492314c29bf6fbce3fc`.
No commit, push, font, renderer, ASM, graphics, global glossary or release change.

## Claude review and exact scope

`tests/fixtures/ja_phase5f_claude_review.json` contains exactly one row:
`scr_1F1A99A`, status `needs_technical_fit`. Approved body:

> なにかの でんきゅうの ようだ。 [green][buffer1][black]に しますか？

It has no kanji, PCS-encodes, and preserves the original `[green]`,
`[buffer1]`, `[black]` once each in that order. The source string is ROM
`0x01F1A99A`, GBA `0x09F1A99A`, 44-byte slot, ten script `0F 00` pointer
owners. Controlfix gives 41 bytes, so the body is **in-place**. The controlfixed
line break is between `ようだ。` and `[green]`; source and Phase 5E ROM are
unchanged until building the new output.

The only additionally translated IDs are `scr_1F1A9C6` (`on` to `オン`) and
`scr_1F1A9C9` (`off` to `オフ`). Scope is these bulb-event buffer literals
only, equivalent to `bulb_toggle_buffer`. No generic `on`/`off` glossary term
or global replacement was added. Reviewed input contains 674 Phase 5E entries
unchanged plus one dialogue and two buffer-value entries: **677 applied**.

## Source, owners and buffer path

| Value | Source ROM / GBA | Original bytes and slot | Japanese PCS | Destination ROM / GBA |
|---|---|---|---|---|
| `on` / `オン` | `0x01F1A9C6` / `0x09F1A9C6` | `E3 E2 FF`, 3 bytes | `FC 15 55 7E FC 16 FF`, 7 bytes | `0x00BA02A4` / `0x08BA02A4` |
| `off` / `オフ` | `0x01F1A9C9` / `0x09F1A9C9` | `E3 DA DA FF`, 4 bytes | `FC 15 55 6C FC 16 FF`, 7 bytes | `0x00BD0ABC` / `0x08BD0ABC` |

`on` exact pointer owners: ROM `0x01E74C91`, `0x01E74CEE`, `0x01E74D4B`,
`0x01E74DA8`, `0x01E74E05`.

`off` exact pointer owners: ROM `0x01E74CBB`, `0x01E74D18`, `0x01E74D75`,
`0x01E74DD2`, `0x01E74E2F`.

A whole-32-MB exact-pointer scan matches precisely these five owners per
value; all interior offsets within both old strings have **zero** pointer
hits. Each owner is preceded by `85 00` (`bufferstring 0`) and followed by
`0F 00` and a pointer to the same dialogue at ROM `0x01F1A99A`. This proves
five local script branches per value: literal copied to buffer1, then dialogue
loaded. No separate structured-table/direct owner was found for either
literal. A computed reference without a stored GBA word cannot be ruled out
mathematically, so event play remains required.

The five event script starts are ROM `0x01E74C86`, `0x01E74CE3`,
`0x01E74D40`, `0x01E74D9D`, `0x01E74DFA`. Map-event arrays at ROM
`0x00B7079C` and `0x00B9CACC` point to them; corresponding map headers at
ROM `0x0034FB28` and `0x003513A8` use section byte `0x62` at ROM
`0x0034FB3C` and `0x003513BC`. Index `0x62` in the map-name pointer table
at ROM `0x003F1CAC` selects the PCS text `Antisis Port`. This is a location clue,
**not** a human-confirmed exact room or route. Coordinates and QA steps are in
`tests/fixtures/ja_phase5f_final_runtime_qa.json`.

The requested literal “no language-page switches around the Japanese buffer”
is **not** what the unmodified normal controlfix produces. It safely wraps
the dynamic token as `[latin][buffer1][japanese]`; each relocated Japanese
value is self-contained `[japanese]オン/オフ[latin]`. Simulating the exact
`FD 02` expansion into the controlfixed PCS stream decodes `オン` or `オフ`,
then restores Japanese for `[black]に しますか？`. The page-switch sequence is
therefore explicit and balanced, with no renderer patch or special-case
controlfix rule. The [FireRed reference implementation of placeholder
expansion](https://github.com/pret/pokefirered/blob/master/src/string_util.c)
copies extended control bytes from substituted strings; Unbound's actual
runtime path still requires mGBA confirmation. Claiming switch-free rendering
would be inaccurate.

## Pipeline, placement, safety

`scripts/build_ja_phase5f_final.py` validates the single Claude row, source
identity, protected token count/order, kana encoding, all literal pointer
owners, interior pointer absence and `bufferstring`/dialogue adjacency. It
merges the three entries into the Phase 5E **pre-controlfix** reviewed input,
using fresh Phase 5F extraction metadata for the two complete owner lists.
Outputs: `out/ja-phase5f-final-reviewed-input.json` and
`out/ja-phase5f-final-fit-audit.json`. No LLM translation was run.

Normal Japanese controlfix:
`out/ja-phase5f-final-controlfix.json`; second pass
`out/ja-phase5f-final-controlfix-second.json` is **byte-for-byte identical**.
Remaining control mismatches **0**. Existing Phase 5E controlfixed 674 rows
are byte/JSON-identical to the prefix of the final 677 rows.

Strict dry-run map: `out/ja-phase5f-final-dry-run-map.json`.
Input 677; encode errors 0; pointer mismatches 0; implausible pointers 0;
no-space/missing relocation 0; fixed/no-relocation truncation 0; control
mismatches 0; runtime and graphics patches 0. Predicted 478 in-place,
199 relocated, 2,009 pointer writes. Full build with the same flags produced
`out/unbound-ja-phase5f-final.gba` and
`out/ja-phase5f-final-map.json`; dry-run/build stats match exactly.

The two new value relocations use `vetted_ff`, **not** script-slot reclaim.
Both are deduplicated to identical 7-byte Japanese payloads already in the
Phase 5E translation set. Thus the full build still consumes 2,654 unique
vetted FF bytes, 613,179 remain, and this focused addition allocates **zero
new** bytes beyond the Phase 5E ROM. Their ten owners are updated; old slots
remain unchanged. The dialogue is in-place and its ten pointer owners remain
unchanged. No old exact GBA pointer remains in the output.

The strict whole-ROM audit via `scripts/audit_ja_phase5b.py` reports
**PASS** in `out/ja-phase5f-final-binary-audit.json`: source differences
classified solely as 31,483 changed in-place text bytes, 2,472 relocated
text bytes and 7,588 pointer-write bytes, across all 677 entries. Unexpected,
ASM, runtime, font and graphics differences: **0**. Relative to the Phase
5E ROM specifically, there are **81** changed bytes: 41 inside the bulb
dialogue's 44-byte slot, 40 at the ten new value-pointer words, and zero
elsewhere. No relocated payload byte changed relative to Phase 5E because
both values reuse existing vetted destinations.

## Tests, hashes, runtime handoff

Final `python -m pytest`: **277 passed**. `python -m py_compile` and
`git diff --check`: PASS. Focused tests cover Claude one-row parsing,
protected/control tokens, kana encode bytes, complete `on`/`off` owner sets,
interior-pointer absence, scoped rather than global wording, page-state
expansion, two-pass controlfix idempotency, vetted relocation, source/Phase
5E binary delta and the human QA fixture.

English source ROM MD5 remains `9cad8e771940e7f7094d13911552cef0`.
Phase 5F final ROM MD5 `ea68145f777763504a3f897a08dd4c8e`;
SHA-256 `4f188556ff5706be2b0a912c944d8cd31cf4a333660c2333fd0bdfe61c3b0b9d`.
Phase 5E ROM MD5 remains `c067bf8c8e60b8e8ca3bc0df42e8820a`.
ROMs stay local/ignored; this is **not** a BPS release.

Human mGBA check remains pending. Use a progressed save near the bulb-switch
puzzle in the `Antisis Port` map section clue; exact room is unverified.
Interact with a bulb in both states and confirm `でんきゅう`, colored `オン` or
`オフ`, Japanese `に しますか？`, ordinary page/confirmation behavior, all five
bulbs and save/load. Line wrap follows controlfix, not the short examples in
the QA fixture. Report screenshots/video and exact map room if found.

After this one held dialogue is applied, **24,367 of 25,044** extracted
entries still have no Japanese applied (including intentionally English
credits and suspected non-text). Of the original held 44, one dialogue was
newly translated, 43 were not; 4 of those 43 have an English/superseded
disposition, leaving 39 substantive technical/visual translation questions.
These include other dynamic-buffer grammars, weekday/trainer-name computed
ownership and width, leading/interior strings, structured UI sort/color
semantics, trim/VICTORIES/Gruff/form-name context and suspected non-text.
The subjective Options text-pacing cause also remains unproven; see
`docs/ja-phase5f-text-pacing.md`. No other Phase 5 translation was expanded.

## Files and Git status

This final integration adds `scripts/build_ja_phase5f_final.py`,
`tests/test_ja_phase5f_final.py`,
`tests/fixtures/ja_phase5f_final_runtime_qa.json` and this report.
The supplied `tests/fixtures/ja_phase5f_claude_review.json` was read, not
modified. Output ROM and maps are ignored in `out/`.

Tracked `git diff --stat` still includes earlier Phase 5E/5F edits:
**9 files changed, 1,458 insertions, 43 deletions**; untracked additions do
not appear in that stat. `git status`: branch `japanese-support`, no staged
changes. Tracked modifications: `.agents/skills/unbound-translation-run/SKILL.md`,
`001_extract_unbound_text.py`, `003_llm_translate.py`, `README.md`,
`glossaries/ja.json`, `lib/translation_glossary.py`,
`tests/test_extraction.py`, `tests/test_ja_phase5_dataset.py`,
`tests/test_translation_glossary.py`. Untracked files: existing Phase 5D/E
reports/build scripts/tests, Phase 5F audit reports/scripts/tests/visual QA,
the supplied Claude fixture, and the four final-integration files above.
No commit or push.
