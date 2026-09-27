# Phase 6B-1: Batch 01 technical gate

Scope: Claude-reviewed Batch 01 only. No Batch 02 translation, glossary-candidate approval, ASM/font/graphics patch, release, commit, or push. All ROMs and generated JSON below are local `out/` artifacts, not release inputs.

## Baseline and decision

- Branch `japanese-support`; start HEAD `34c2866b1ffe380ea8abd63c5752f109926bdccc`. The worktree already contained uncommitted Phase 6A work and the Claude review fixtures; none was reset or deleted.
- Source `rom/unbound.gba` MD5 `9cad8e771940e7f7094d13911552cef0`, unchanged after build. Phase 5F `out/unbound-ja-phase5f-final.gba` MD5 `ea68145f777763504a3f897a08dd4c8e`, unchanged.
- Claude review: **407 unique, exact Batch 01 IDs**, 401 `confirmed` and 6 `needs_context`; duplicate/extra/missing IDs 0. Identity, original, status, protected/control tokens, kana/PCS encoding: **0 validation issues** after the one documented technical punctuation normalization below. Per-entry evidence: `out/phase6/ja_phase6_batch01_review_validation.json`.
- The 401 confirmed candidates became **385 safely applied**, **12 provisional official-name holds**, **4 incomplete-pointer-owner holds**. Six `needs_context` remain English. Thus 22 Batch 01 entries are not injected. `out/phase6/ja_phase6_batch01_reviewed.json` records all 407 with status; `...safe_input.json` contains only 385. The Claude fixture was not edited.
- `scr_1F010E6` had one ASCII parenthetical that cannot encode in the Japanese page. The reproducible builder alone changes `(オープニングと おなじ ないようです)` to `オープニングと おなじ ないようです。`; no semantic/control token was removed. Other reviewed wording remains as supplied.

## Names, glossary, context

- The **56 memory-based name entries** contain 77 term occurrences, individually listed with English source, Claude kana, type/context, PokeAPI entity and ja-hrkt result in `out/phase6/ja_phase6_batch01_unverified_names.json`. The existing PokeAPI localizer was used; only exact English entity-name matches and encodable ja-hrkt count as verified. Results: **64 `verified_exact`**, **0 `verified_but_difference`**, **0 `not_found`**, **12 `ambiguous`**, **1 `not_supported`**. Claude-vs-verified-name differences: **0**. The 12 unresolved entries (one `Bird Keepeer` trainer-class case and eleven plural-item cases) remain English; singular PokeAPI names were not passed off as exact plural-source verification.
- `scr_75C267` exposed a semantic compound collision: word-boundary matching alone treated the person-name glossary term `Ace` as the last word of `Aerial Ace`. The `Ace` entry is now scoped to its evidenced exact character-name entry `scr_1F0EF1F`, with `global_replace: false`. Existing boundary/longest-specific match behavior remains unchanged; `Aerial Ace` and `Ace Trainer` no longer inherit the person name. Tests also cover `Log`, `Hard`, `Difficult`, `Option`, `Cube`, and a longer `Aerial Ace` term outranking `Ace`.
- Static glossary re-evaluation over **all 2,500 Phase 6 selection entries** finds exactly **4 changed matches**, all removed erroneous `Ace` matches in `Aerial Ace` (IDs and before/after spans in `out/phase6/ja_phase6_glossary_match_audit.json`). Another **52 capitalized-compound-proximity matches** are *suspicions for manual review*, not proven bugs or automatic changes. No Batch 02 translation was generated.
- All **24** Claude glossary proposals remain proposals: 17 locations, 4 items, 1 feature, 1 NPC label, 1 other. `out/phase6/ja_phase6_batch01_glossary_candidates_audit.json` includes proposed kana, affected IDs, existing-glossary conflicts (none), PokeAPI applicability, project-standard candidacy, and context sensitivity. Four proposed item terms were not found as PokeAPI item entities. Nothing from this proposal list was added to `glossaries/ja.json`.
- Six context holds: `scr_1F01267`, `scr_1F012BD`, `scr_1F016AD` (`[buffer2]` relationship), `scr_1F02458` (`[buffer3]` address), `scr_1F01914` (`\\07`/`\\08` after “world”), `scr_1F0618A` (`\\0C` evolution sentence). `out/phase6/ja_phase6_batch01_buffer_evidence.json` records each ROM text offset/GBA address, source bytes, owning script operand, nearby bytes and bounded search for `bufferstring` candidates. The producer, source table, complete possible values and Japanese grammatical behavior are **not proven**. The codec labels FD 07/08/0C only as raw placeholders; their rendering as expansion/control is not enough to assert a safe Japanese suffix or sentence. No token was deleted and no ASM change was made.
- Full-ROM exact-pointer scan found four entries with pointer sources absent from extraction metadata: `scr_74B441`→ROM `0x74B363`, `scr_1F02008`→`0xB14DC3`, `scr_1F06A77`→`0x1D77C2F`, `scr_1F07376`→`0x1E6B092`. All four remain English; `out/phase6/ja_phase6_batch01_owner_audit.json` gives recorded and missing owners. These candidates need independent script/table ownership proof before extraction metadata is expanded. In particular the extra `scr_1F07376` reference is preceded by a `bufferstring 0`-shaped operand; treating it as unrelated would risk a stale pointer.

## Fit, controlfix, injection

`out/phase6/ja_phase6_batch01_fit.json` contains, for each of 407 entries, source PCS byte length, Japanese byte length where applied, slot, fixed/no-relocation flags, owner list, placement, source/Japanese normal-font line-pixel measures, and a renderer-width evidence field. Among new Batch 01 entries: **362 in-place, 23 relocation, 22 held English**; fixed/no-relocation entries **0**, fixed overflow **0**. No applied entry exceeds a rigid slot. **327** applied entries are no wider per line than their source by the measured font advances. **25 compact-label, 4 positional-sign, and 29 dialogue-window** cases have unproven exact renderer bounds; confirmed pixel overflow is **0**, but these **58** are *not certified width-safe*. Byte fit must not be confused with screen fit. Signposts, choice labels and long text require mGBA review.

Normal Japanese controlfix was applied to Phase 5F's 677 plus 385 new safe entries. First pass: 1,062 entries, 467 changed (including 311 wraps, 3 sequence repairs, 2 menu-description repairs, 467 Japanese page-control changes), **0 remaining control mismatches**. Second pass changed **0** and its JSON is **byte-for-byte identical**. FE/FA/FB/FC/FD, buffers, colors, quote/button/arrow/alignment tokens are protected by the existing controlfix and regression tests. P7 text pacing, wakachigaki policy, renderer, waits and pauses were not changed.

Strict injector `--dry-run --fail-on-no-space` on the original English ROM and the 1,062-entry controlfixed JSON: **PASS**. Input 1,062; **840 in-place, 222 relocated, 2,033 pointer writes**; vetted FF consumption **3,142 unique bytes**, remaining **612,691 bytes**; reclaimed space **0**. Encode errors, pointer mismatches, implausible pointers, missing/no-space relocations, fixed/no-relocation truncations, control mismatches, runtime patches, graphics patches: **all 0**. `out/phase6/ja_phase6_batch01_dry_run_map.json` is the dry-run map. Relative to the Phase 5F 677 baseline, Batch 01 adds 385 translations (362 in-place, 23 relocated); 24 of the total pointer writes are newly required.

The strict real build produced `out/unbound-ja-phase6-batch01.gba` (32 MiB, MD5 `37397476f62e0c0e71b4a8d393ce3948`) and `out/phase6/ja_phase6_batch01_map.json`; stats match dry-run. Full bytewise original-ROM audit **PASS**: every changed byte is classified as in-place text (**60,476 changed bytes**), relocated text (**2,938**), or pointer writes (**7,529**). Unexpected differences **0**; runtime/ASM, font and graphics patches **0**. The map reserves only vetted FF for relocated strings. Full ranges and ownership evidence are in `out/phase6/ja_phase6_batch01_binary_audit.json`; its 2,033 pointer-write count is write operations, not the number of byte positions that differ.

## QA, handoff, verification

- `tests/fixtures/ja_phase6_batch01_runtime_qa.json` contains **26** applied Batch 01 candidates for human runtime QA, including signs, choices, buffers, multiple pages, relocation, proposed terms and verified names. Batch 01 is 404 `scripts` + 3 `plain_scripts`; it contains **no battle-message or mission-category entries**, so the fixture does not pretend to test those renderers. Route clues are marked **unverified**; exact runtime reachability and speaker attribution are not claimed. Human mGBA verification remains necessary, especially the 58 width-uncertain cases.
- `out/phase6/ja_phase6_batch02_style_handoff.json` is guidance only, with no Batch 02 translation. It retains kana-only/P7/wakachigaki, `$`, conditional counters (`ひき`/`こ`/`かい`/`とおり`), and the wording candidates `ナゾノクサのはっぱ`, `わざマシン`, `レポートを かく` without making them global glossary terms. It forbids memory-only Pokémon/Move/Item names, guessing unresolved buffers, and globalizing the 24 proposals.
- Regression coverage: review parse/identity/tokens, 56 names and no memory-only acceptance, glossary scope/2,500-row audit, six holds, 4 owners, controlfix idempotency, fit/relocation and strict binary-audit helper. Full `python -m pytest -q`: **299 passed, 16 subtests passed**. `py_compile` and `git diff --check`: **PASS**.
- Created for this task: five `scripts/*ja_phase6_batch01*.py` audit/build helpers, `tests/test_ja_phase6_batch01.py`, the 26-entry QA fixture, and this report. Changed: `glossaries/ja.json`, `tests/test_translation_glossary.py`, plus legacy expectation tests `tests/test_ja_phase5e.py` and `tests/test_ja_phase6a.py` to reflect the deliberate `Ace` scope change. Existing uncommitted Phase 6A files and `.gitignore` remain as found.
- `git diff --stat` for tracked files only (untracked files do not appear): `.gitignore | 1 +`, `glossaries/ja.json | 7`, `tests/test_ja_phase5e.py | 3`, `tests/test_translation_glossary.py | 23`; **4 files, 31 insertions, 3 deletions**. `tests/test_ja_phase6a.py` was already untracked, so its adjusted expectation and all newly created files appear only in `git status`. Modified and untracked work remains; no commit or push was made. ROMs and generated JSON under `out/` remain ignored/local.

Final `git status --short` (including the pre-existing Phase 6A/Claude-review files):

```text
 M .gitignore
 M glossaries/ja.json
 M tests/test_ja_phase5e.py
 M tests/test_translation_glossary.py
?? docs/ja-phase6-batch01-claude-review.md
?? docs/ja-phase6-batch01-technical.md
?? docs/ja-phase6a.md
?? scripts/audit_ja_phase6_batch01_buffers.py
?? scripts/audit_ja_phase6_batch01_fit.py
?? scripts/audit_ja_phase6_batch01_names.py
?? scripts/build_ja_phase6_batch01.py
?? scripts/build_ja_phase6_batch01_handoff.py
?? scripts/build_ja_phase6a.py
?? tests/fixtures/ja_phase6_batch01_claude_review.json
?? tests/fixtures/ja_phase6_batch01_glossary_candidates.json
?? tests/fixtures/ja_phase6_batch01_runtime_qa.json
?? tests/fixtures/ja_phase6_runtime_candidates.json
?? tests/fixtures/ja_phase6_selection.json
?? tests/test_ja_phase6_batch01.py
?? tests/test_ja_phase6a.py
```

Reproduce the gate from the current prepared Phase 6A inputs with `python scripts/build_ja_phase6_batch01.py`, `python scripts/audit_ja_phase6_batch01_buffers.py`, normal `004_controlfix_translations.py` twice on the combined input, `python scripts/audit_ja_phase6_batch01_fit.py`, `python 005_hybrid_injector.py ... --target-lang ja --dry-run --fail-on-no-space`, the same injector without `--dry-run` to the Batch 01 ROM, then `python scripts/audit_ja_phase5b.py` for the complete byte-diff audit. Do not make `out/phase6/ja_phase6_batch01_reviewed.json` or the generated ROM a release input without resolving the held entries and performing runtime QA.
