# Phase 6B-5 — Batch 05 technical integration

**Static GO for Batch 06 preparation; Batch 06 translation has not started.** Batch 05 reviewed 408 entries; 168 safely applied, 240 held. The ROM is a private local QA artifact, not a release. Runtime layout remains **not human-tested**. No commit or push.

## 1. Baseline and review validation

| Item | Result |
| --- | --- |
| Branch / HEAD | `japanese-support` / `cd885719ca36802b069ff9579c1260013274e24f` |
| Opening worktree | 24 pre-existing untracked files, no tracked edits; none reset or deleted |
| Opening pytest | 361 passed |
| Source `rom/unbound.gba` MD5 | `9cad8e771940e7f7094d13911552cef0` |
| Batch 04 ROM SHA-256 | `3cc314c7ceb3cd6057d8c6fb71194af0e4691f54a06b0174d9b06c41900dae0e` |
| Existing Japanese entries | 1,549 |

`ja_phase6_batch05_review_validation.json` proves exactly 408 unique IDs in the same order as the segmented source; extra, duplicate, original/category, review-source, source control/protected-token metadata, conversation/scene metadata, reviewed semantic token, kanji, and reviewed PCS errors: **0**. `review_source=claude_cli` for all 408; nonempty reviewed text 331. Original statuses: confirmed 317, existing_glossary 1, needs_context 71, needs_technical_fit 19. Categories: Battle 189, Menu/UI 219. The six failed *candidate* glyph drafts were **not** treated as reviewed translations.

## 2. Official names, buffers, glossary, FA

`ja_phase6_batch05_official_name_audit.json` covers 67 distinct entries/observations. Exact English PokeAPI entity and PCS-safe `ja-hrkt` are required. Results: **verified_exact 32, verified_difference 0, ambiguous 33, not_found 2, not_applicable 0, unsupported 0**. Ten verified entries are applied; 57 flagged entries are held for an unresolved name or another gate. A PokeAPI name missing from inflected battle prose is *not* silently inserted: the term span/use cannot be proved, so it is ambiguous, not a verified difference. The 17 flags without an exact English table entity remain ambiguous. No memory-only official wording was adopted.

All **68** `unknown_buffer` warnings stay held. All **71** `needs_context` rows stay held: technical evidence does not establish every caller/value/grammatical interpretation. The six incomplete translations are `TRANSLATION_INCOMPLETE`, with source/context/slot/owners and an explicit no-Codex-translation flag in `tests/fixtures/ja_phase6_batch05_retranslation.json`; the failed provisional text and exact unsupported codepoint were not preserved in the review fixture, so neither is invented here.

The 19 `needs_technical_fit` rows are disjointly classified: `TRANSLATION_INCOMPLETE` 6; `FA_SEMANTIC_CONFLICT` 1 (`tbl_battle_messages_00122_3FC048`); `STRUCTURED_CONSTRAINT` 12 (battle columns, PC Item Storage, Options shared row, short/fixed labels). Detailed IDs and intersecting reasons are in `ja_phase6_batch05_reviewed.json`. No `WIDTH_OVERFLOW`, `POINTER_OWNER_INCOMPLETE`, `ENCODING_FAILURE`, `CONTROL_FAILURE`, or `RELOCATION_REQUIRED` is a *primary* class among these 19; separate fit gates still evaluate every safe candidate. Four Batch 05 FA rows are all held (one conflict, three context). Source FA controls **4**, source segments **12**; count, order and ROM-derived segment boundaries are recorded in `ja_phase6_batch05_fa_audit.json`. FA added/moved/applied: **0**.

The one existing-glossary row, `tbl_setting_names_00004_1F4DB88` (`Battle Options`), is applied as `バトルせってい`. The approved `Options` match is scoped to the actual setting-name entry; no substring-only expansion into unrelated prose. Four new proposals—SPA, Cube V3, Semi-Shift, Capped Exp. Share—remain `proposal_only_not_approved`; `glossaries/ja.json` is unchanged. Their source, candidate, affected IDs, type, scoped-proposal status, approved-term overlaps and PokeAPI applicability are in `ja_phase6_batch05_glossary_audit.json`.

## 3. Width and technical fit

`width_runtime_unverified` occurs in all **408** review rows. It is **not** an independent hold reason; 168 of these rows are applied. Battle geometry remains ROM-proved: 28-tile window, x=2px, 222px physical span. Batch 05 Battle result: **21 applied, 168 held**. Dynamic battle substitutions are held on unproved expansion/page and imported-name width, not on the warning alone. The local Unbound naming keyboard gives safe local input maxima: nickname 10 characters/60px, player 7/42px, rival 7/42px. These do not prove foreign/traded/modified names or a buffer expansion's page behavior.

Menu/UI result: **147 applied, 72 held**. Its profile evidence is 11 PARTIAL and 208 UNKNOWN menu rows, with no blanket UNKNOWN hold. Known horizontal columns, Options shared label/value row, fixed/no-relocation constraints, missing pointer owners and screen overflow remain gated. Four entries have whole-ROM exact-pointer ownership gaps and are held. Raw source controls are compared against each encoded candidate after controlfix, ignoring only new `[japanese]`/`[latin]` switches. This additional check found **16** structural-sequence mismatches (FE/FB and other boundaries): all are held; 14 had passed preliminary review and were removed before the final build. This catches cases the controlfix summary's `remaining_control_mismatches=0` did not expose. Every one of the 168 applied entries now matches the ROM source FE/FA/FB/FC/FD control sequence exactly apart from the two page switches.

The final applied set has **85 in-place, 83 relocations, 108 new pointer-owner writes**. All relocated destinations are injector-classified `vetted_ff`. No fixed/no-relocation truncation and no unresolved relocation candidate. `ja_phase6_batch05_reviewed.json` contains for every entry: original review status, official/buffer/width/fit result, encoded size, source slot, pointer ownership, final Japanese or null, `final_apply`, and hold reasons.

## 4. Controlfix, strict injection and byte audit

The normal controlfix pipeline ran against 168 safe *raw* translations plus the unchanged 1,549-entry Batch 04 controlfixed baseline. Report: 1,717 translated, 168 changed, 12 wrapped, remaining control mismatches **0**, FA placement review **0**. The safe-only rebuild is byte-for-byte equal to `ja_phase6_batch05_combined_controlfix.json`; a second controlfix pass changes **0** and is byte-for-byte identical. The first 1,549 JSON entries are exactly equal to the Batch 04 input.

Full-from-English strict dry-run of 1,717 entries has encode/pointer/space/truncation/runtime/graphics errors **0**, but its allocation order would move **220 earlier relocation destinations**. This violates the stricter Batch 05 demand that earlier bytes/pointers remain unchanged; it was **not used to build** the ROM. Instead, the injector ran the 168-entry safe controlfixed subset on the verified Batch 04 ROM. This incremental strict dry-run and build agree exactly: encode errors 0, pointer mismatches 0, implausible pointers 0, no-space skips 0, missing relocations 0, truncations 0, runtime patches 0, graphics patches 0; vetted FF used **870 bytes**, remaining **611,666 bytes**. Input 168; in-place 85, relocated 83, pointer writes 108. No reclaim-script-slot or lossy-fit option was used.

ROM: `out/unbound-ja-phase6-batch05.gba` (32 MiB), SHA-256 `dcb2b8813cc1257001f38586b5a214bccae24e29a3812f47c4a897fbfef9ec73`, MD5 `6dfe3258db3276a7ea217528c80167db`. The first generated candidate was rejected after the extra control check; it was removed only after hash verification, then replaced by the audited candidate. The source and Batch 04 ROM hashes remain unchanged.

`ja_phase6_batch05_incremental_audit.json` proves Batch 04-to-05 changed bytes **2,858**: in-place text **1,715**, relocated text **796**, pointer bytes **347**, unexpected **0**. All prior 1,549 in-place slots, relocation destination bytes and pointer-source bytes were compared against Batch 04 and are unchanged. `ja_phase6_batch05_rom_audit.json` independently classifies *all* source-English-to-Batch-05 changes: **115,441** bytes = in-place text **103,621** + relocated text **3,789** + pointer bytes **8,031**; unexpected **0**. ASM, font, graphics, runtime patch bytes: **0**. Applied Japanese total: **1,717**.

## 5. Runtime QA and Batch 06 gate

`tests/fixtures/ja_phase6_batch05_runtime_qa.json` contains **36** prioritized cases: battle 8; Game Settings 5; PC/Item Storage 4; Cube 3; list/choice 3; verified official name 3; relocation/pointer 4; short slot 2; held-English dynamic buffer 2; other menu 2. Each records original, expected display, ROM address, owner, placement and unverified route. Every runtime result is `not_human_tested`; no screen claim is inferred from a ROM pointer. Check battle text, menus, dynamic names and relocation in mGBA with a progressed save, record exact screen/entry match, then update the fixture with observed outcomes.

`out/phase6/ja_phase6_batch06_style_handoff.json` consolidates the Batch 01–05 rules and says source-only/no Batch 06 translation. Batch 06 selection has **461 source entries, zero FA**, so no FA-segmented Batch 06 input was created. **Static GO** for Batch 06 translation preparation: safe subset injected, official-name/unproved-buffer/incomplete/FA holds preserved, width warning not blanket-held, controlfix idempotent, byte audit unexpected 0. Runtime signoff remains pending mGBA verification; this GO is not release approval.

## 6. Verification and files

Targeted regression tests: 12 PASS. They cover the 408 review, status counts, 67 names, 68 buffer holds, six incomplete, four FA/12 segments, widths and local name bounds, scoped glossary, control sequence, idempotency, untouched 1,549 baseline, map/ROM audit, auditor rejection of an unrelated byte, QA and Batch 06 source-only handoff. Full pytest and static-check results are recorded in the final task reply. No ready-translation file, glossary, shared injector, font, renderer or graphics source was edited.

Created tracked-visible files for this task: `scripts/audit_ja_phase6_batch05_names.py`, `scripts/build_ja_phase6_batch05.py`, `scripts/build_ja_phase6_batch05_handoff.py`, `tests/test_ja_phase6_batch05.py`, `tests/fixtures/ja_phase6_batch05_runtime_qa.json`, `tests/fixtures/ja_phase6_batch05_retranslation.json`, and this report. Generated private/ignored files: official/name, review, owner, FA, glossary, controlfix, map, binary-audit and Batch 06 style handoff JSON under `out/phase6/`, plus `out/unbound-ja-phase6-batch05.gba`. Pre-existing untracked files were retained.

Final `.venv/Scripts/python.exe -m pytest`: **373 passed in 38.43s** (baseline 361). `py_compile` on all four new Python files: **PASS**. `git diff --check`: **PASS**. `git diff --stat`: **empty**, because every visible worktree file is untracked. Final `git status --short --branch`: `japanese-support` tracking `origin/japanese-support`, **31 untracked files**, no tracked modifications; seven are new from this task and 24 predate it. No commit or push.
