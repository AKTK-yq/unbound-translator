# Phase 6B-2: Batch 02 technical gate

Scope: Batch 02 only. No Batch 03 translation, glossary approval, ASM/font/renderer/graphics patch, release, commit or push. ROM and generated JSON remain local under ignored `out/`. This is a conservative static/injection gate, **not** a claim that the 30 QA entries were played in mGBA.

## 1–6. Starting state, review and official names

- Start branch `japanese-support`, HEAD `34c2866b1ffe380ea8abd63c5752f109926bdccc`. The worktree already had uncommitted Phase 6A/Batch 01/Batch 02 review files. None was reset or removed. Baseline `.venv` pytest: **299 passed, 16 subtests passed**. The global `python` points to a Python without pytest, so checks used `.venv/Scripts/python.exe` on this Windows host.
- Source `rom/unbound.gba` MD5 `9cad8e771940e7f7094d13911552cef0`; Batch 01 validation ROM `out/unbound-ja-phase6-batch01.gba` SHA-256 `52cd6c85aa7d2954159bbbe7a077a09ace895fab858778e5790a2965607fefe6`. Both hashes were unchanged after the build. Prior applied total: **1,062**.
- Review: **408 IDs in input order**, duplicate/extra/missing 0; `original`, `category`, conversation/scene metadata match. Source/protected token mismatch 0, nonempty reviewed token/control-count mismatch 0, Han 0, Japanese PCS encode errors 0. Provenance retained per entry: **Claude CLI 200**, **user-approved Codex completion 208**. Review statuses: 195 `confirmed`, 7 `existing_glossary`, 156 `needs_context`, 50 `needs_technical_fit`, 0 `existing_official`. The 156 context rows have no Japanese text.
- `out/phase6/ja_phase6_batch02_official_name_audit.json` records all **153 term observations across 120 entries**. Existing `PokeAPILocalizer("ja")` and its `ja-hrkt` names were used; only exact full-English entity identity and PCS-encodable Japanese qualify. Results: **89 `verified_exact`, 0 `verified_difference`, 3 `ambiguous`, 21 `not_found`, 40 `unsupported`**. Unresolved total **64** observations; no memory-only official value adopted. The 4 proposed Japanese terms in the list are unsupported facility-title/Pokédex-category cases, so no correction was applied. Example ambiguous source: `Play\lRough` is not the exact `Play Rough` term; `Fighting`/`Hoopa` are absent as exact contiguous names in their source entries. One otherwise `confirmed` row, `scr_1F12F39`, was held for its unverified `Cactus Pokémon` category term. A verified term does **not** override an entry's separate context hold.

## 7–9. `\l` semantics and placement

- PCS `\l` encodes **FA** in `lib/pcs_text.py`. In this ROM, `RenderText` starts at ROM `0x00005790` / GBA `0x08005790`; special-byte dispatch at ROM `0x00005848` subtracts `F8`, and jump-table index 2 at ROM `0x00005868` contains `26 5B 00 08`: FA handler GBA `0x08005B26`. FB index 3 points to GBA `0x08005B22`; FE points to `0x08005880`. Handler bytes at ROM `0x00005B22`: `02 20 00 E0 03 20 30 77`, storing different printer states for clear/scroll. [FireRed's `CHAR_PROMPT_SCROLL` definition](https://github.com/pret/pokefirered/blob/master/include/characters.h) and [text-printer state path](https://github.com/pret/pokefirered/blob/master/src/text.c) corroborate: FA waits for button press, then scrolls one dialogue line; FB waits then clears. This is not a speed, alignment or glyph modifier. Unbound dispatch bytes are direct evidence; exact player-visible timing of each Batch 02 scene was not measured.
- All **30** `control_placement_review_required` entries have raw source bytes, decoded English, source FA byte/text positions, neighboring text/controls, source pointer owners, renderer class and provisional Japanese positions in `out/phase6/ja_phase6_batch02_scroll_audit.json`. Source raw FA counts equal decoded `\l` counts for all 30. **A 0 / B 0 / C 30 / D 0**: their Japanese drafts either append FA at the tail or are empty; the replacement semantic page boundary is unreviewed. All 30 remain English. Three further technical-fit drafts and one `confirmed` draft (`scr_1F0E997`) also put FA at the end despite an internal source FA; they too are held.
- Rule: preserve FA at an editorially reviewed semantic/page boundary. Never restore missing FA by appending it, never let controlfix infer its placement, never delete/move it as punctuation. A count match alone cannot prove page behavior.

## 10–17. Buffers, context, fit and glossary

- The **49** `unknown_buffer` rows have per-owner opcode bytes, direct `bufferstring` evidence where present, nearby *candidate* writers, possible values, raw FD suffixes, source grammar hints and uncertainty level in `out/phase6/ja_phase6_batch02_buffer_audit.json`. Classification: **resolved_value 0, resolved_type_only 0, runtime-dependent 1, unknown 48**. Six rows contain raw `\07`/`\08`/`\0C` suffix tokens. These are not deleted or interpreted as Japanese grammar. `scr_1F0DBDC` has three immediate `bufferstring 0` writers to `item`, `Pokémon`, `TM` at pointer sources ROM `0x01E6EE2E`, `0x01E6EED0`, `0x01E6EF3B`; it is runtime-dependent, not a single known value. Most other nearby `0x85` patterns lack proved branch/caller flow. All 49 remain English; possible Latin/Japanese substitution page behavior remains unproved.
- Speaker warning **27**, other context warning **21** (48 distinct rows). Per-row script operand kind, owner, nearby extracted text and conservative speaker evidence are in `out/phase6/ja_phase6_batch02_context_audit.json`. All 48 still have unknown actor; pointer ownership does not establish NPC identity or map/event root. No new persona or speech style was authored.
- All **50** `needs_technical_fit` rows have Japanese PCS bytes, source slot, flags, owners, normal-font pixel advances, controls and renderer-bound caveat in `out/phase6/ja_phase6_batch02_fit.json`. Raw pre-controlfix classification: **45 in-place byte fit, 2 relocatable, 3 structured/position-sensitive**. Fixed/no-relocation rows 0; fixed overflow **0**; owner-incomplete within these 50 **0**. Exact renderer width limits are unproved, so confirmed pixel overflow **0**, *not* 50 width-safe passes. Forty-six unwrapped Japanese drafts exceed their source's maximum line advance; 3 positional headings need centering evidence. All 50 remain English; no abbreviated wording was invented. A separate compact-slot width guard holds **35** otherwise confirmed entries when Japanese glyph advance exceeds the source in a slot of at most 32 bytes. Five technical-fit rows meet that guard too (40 warning instances total); these are risks, not proven clipping.
- Whole-ROM exact-pointer scan across **408** selected rows found two metadata gaps: `scr_1F0DAD3` has extra raw pointer hit ROM `0x012CF6AA`; `scr_1F0DD3F` has extra `bufferstring 0` owner ROM `0x01E6EECB`. Both held. The latter is structurally suggestive; no extraction metadata was silently changed. See `out/phase6/ja_phase6_batch02_owner_audit.json`.
- All **18** glossary proposals remain unapproved (12 Batch 02 new, 6 Batch 01 carry-over). The candidate audit records source, kana, type, confidence, affected IDs, existing conflict, context sensitivity and PokeAPI applicability. Exact-source conflict **0**. Current scoped matcher claims outside allowed scope **0**; 4 collision warnings remain held. `Ace` is still not matched inside `Aerial Ace`; no candidate entered `glossaries/ja.json`. See `out/phase6/ja_phase6_batch02_glossary_audit.json`.

## 18–28. Safe set, controlfix, strict ROM and QA

- Safe application: **164 Batch 02 entries** (all `scripts`); held English: **244**. Only `confirmed`/`existing_glossary` entries passing name, FA, buffer, owner, glossary and compact-width gates were considered. `out/phase6/ja_phase6_batch02_reviewed.json` records original status, provenance, technical status, name/buffer/FA/fit results, apply flag, final controlfixed Japanese, encoded byte size and hold reasons for every ID. Its `safe_input.json` and `combined_input.json` are generated by `scripts/build_ja_phase6_batch02.py`, then `scripts/build_ja_phase6_batch02_handoff.py` finalizes fit against the real map; no JSON was hand-edited. Combined Phase 5F + Batch 01 + Batch 02: **1,226** applied.
- Japanese controlfix on the 1,226 safe entries: first pass changed 631 (461 wraps, 90 actual-newline repairs, 3 sequence repairs, 2 menu-description repairs), remaining control mismatches **0**. Second pass changed **0**; JSON byte-for-byte identical. FE/FA/FB/FC/FD, colors, quote/button/alignment, buffers and placeholders use the existing controlfix; no text-speed/wait/renderer/wakachigaki policy change.
- Strict injector `--dry-run --fail-on-no-space`: **PASS**. Input 1,226; total in-place **1,004**, relocated **222**, pointer writes **2,033**; Batch 02 contribution **164 in-place, 0 relocated, 0 pointer writes**. Existing Batch 01 baseline still accounts for 222 relocations. Vetted FF used **3,142 bytes** total, 612,691 remain; reclaimed text **0**. Encode errors, pointer mismatches, implausible pointers, missing/no-space relocations, truncations, runtime patches, graphics patches: **all 0**. No ASM/font patch. Map: `out/phase6/ja_phase6_batch02_dry_run_map.json`.
- Real output: `out/unbound-ja-phase6-batch02.gba` (32 MiB), MD5 `8a2929601688451b15ca36020fd48fc6`, SHA-256 `c7f71c87c644871f2e66c28a6258818ba3523441ff1726183b8340d44872f4a7`. It was generated from the original English ROM, not by modifying the Batch 01 ROM. Strict real-build stats equal dry-run. Map: `out/phase6/ja_phase6_batch02_map.json`.
- Full source-versus-output byte audit: **PASS**. Changed byte positions classified only as in-place text **73,348**, relocated text **2,938**, pointer writes **7,529**; unexpected **0**. All relocated destinations are vetted FF; all recorded owners updated; old pointers absent; original relocated slots unchanged. Complete ranges/entry evidence: `out/phase6/ja_phase6_batch02_binary_audit.json`. The 2,033 pointer-write count is operations, not changed byte positions. Separate Batch 01-to-02 incremental audit: **164 source slots, 12,872 changed bytes, 0 unrelated, 0 pointer writes, 0 new relocations**; `out/phase6/ja_phase6_batch02_incremental_audit.json` lists every changed range.
- `tests/fixtures/ja_phase6_batch02_runtime_qa.json` contains **30 applied candidate entries**: 5 reviewed FA scrolls, 5 buffer/token cases, 5 short labels, 3 questions, 3 multi-page/NPC, 9 general. All 30 are in-place; no Batch 02 relocation is currently approved, so relocation QA must rely on the existing Batch 01 set until width/layout evidence clears a Batch 02 candidate. Routes are **unverified** because exact map/event reachability was not traced. The 30 provisional FA and 49 unknown-buffer rows are English and cannot serve as Japanese runtime examples. Batch 02 has 404 `scripts` and 4 `plain_scripts`, not independently verified battle-message/mission table rows. No mGBA play result is claimed.

## 29–35. Tests, handoff, decision and working tree

- Focused Batch 02 tests: **10 passed**. Complete `.venv/Scripts/python.exe -m pytest -q`: **309 passed, 16 subtests passed**. `py_compile` on changed Python and `git diff --check`: **PASS** (Git issued only existing LF/CRLF working-copy warnings). Regression covers 408 review/200+208 provenance, 153-name strict matching, memory-only rejection, ROM FA dispatch and 30 holds, 49 buffer/suffix holds, 50 fit rows, glossary scope, controlfix idempotency, reviewed safe set and binary-audit tamper rejection.
- `out/phase6/ja_phase6_batch03_style_handoff.json` combines Batch 01 style with exact-English PokeAPI rule, neutral speaker, unknown-buffer hold, context-scoped glossary, counters, sign/mission formatting and FA interactive-scroll placement. It is guidance only; Batch 03 text was not translated.
- **Batch 03 gate: HOLD.** FA semantics are identified, PokeAPI path works, scoped glossary has no new proven collision, controlfix and strict ROM audit pass. But 30 missing-FA drafts were provisionally end-appended; their semantic boundaries remain unresolved, and 49 dynamic-buffer rows remain unapproved. The safe ROM can be tested, but proceeding with another translation batch before correcting the FA review workflow risks repeating a systematic page-control failure.
- New tracked-worktree candidates for this task: `scripts/audit_ja_phase6_batch02_names.py`, `scripts/audit_ja_phase6_batch02_controls.py`, `scripts/build_ja_phase6_batch02.py`, `scripts/build_ja_phase6_batch02_handoff.py`, `tests/test_ja_phase6_batch02.py`, `tests/fixtures/ja_phase6_batch02_runtime_qa.json`, this report. Generated audits/controlfixed JSON/map/ROM/handoff remain ignored under `out/`. Earlier unrelated and Phase 6A/Batch 01/Batch 02 review work remains unchanged.
- `git diff --stat` on tracked files still reflects pre-existing edits only: `.gitignore | 1 +`, `glossaries/ja.json | 7`, `tests/test_ja_phase5e.py | 3`, `tests/test_translation_glossary.py | 23`; **4 files, 31 insertions, 3 deletions**. New Batch 02 files are untracked, so they do not appear in that stat. No commit or push.

Final `git status --short` (pre-existing work retained; this task's new files mixed in):

```text
 M .gitignore
 M glossaries/ja.json
 M tests/test_ja_phase5e.py
 M tests/test_translation_glossary.py
?? docs/ja-phase6-batch01-claude-review.md
?? docs/ja-phase6-batch01-technical.md
?? docs/ja-phase6-batch02-claude-review.md
?? docs/ja-phase6-batch02-technical.md
?? docs/ja-phase6a.md
?? scripts/audit_ja_phase6_batch01_buffers.py
?? scripts/audit_ja_phase6_batch01_fit.py
?? scripts/audit_ja_phase6_batch01_names.py
?? scripts/audit_ja_phase6_batch02_controls.py
?? scripts/audit_ja_phase6_batch02_names.py
?? scripts/build_ja_phase6_batch01.py
?? scripts/build_ja_phase6_batch01_handoff.py
?? scripts/build_ja_phase6_batch02.py
?? scripts/build_ja_phase6_batch02_handoff.py
?? scripts/build_ja_phase6a.py
?? tests/fixtures/ja_phase6_batch01_claude_review.json
?? tests/fixtures/ja_phase6_batch01_glossary_candidates.json
?? tests/fixtures/ja_phase6_batch01_runtime_qa.json
?? tests/fixtures/ja_phase6_batch02_claude_review.json
?? tests/fixtures/ja_phase6_batch02_glossary_candidates.json
?? tests/fixtures/ja_phase6_batch02_official_name_review.json
?? tests/fixtures/ja_phase6_batch02_runtime_qa.json
?? tests/fixtures/ja_phase6_runtime_candidates.json
?? tests/fixtures/ja_phase6_selection.json
?? tests/test_ja_phase6_batch01.py
?? tests/test_ja_phase6_batch02.py
?? tests/test_ja_phase6a.py
```

Source ROM and Batch 01 validation ROM hashes above remain unchanged.
