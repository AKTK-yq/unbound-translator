# Phase 6B-6 — Batch 06 technical integration

**Static GO for Phase 6 Final Cleanup preparation.** This is not runtime/release approval. Batch 06 reviewed 461, applied 331, held 130. No past hold was changed. No commit or push.

## 1. Baseline and review

| Item | Result |
| --- | --- |
| Branch / HEAD | `japanese-support` / `cd885719ca36802b069ff9579c1260013274e24f` |
| Opening worktree | 36 pre-existing untracked files, tracked edits 0; none reset/deleted |
| Opening pytest | 373 passed, 16 subtests passed |
| Source ROM MD5 | `9cad8e771940e7f7094d13911552cef0` |
| Batch 05 ROM MD5 | `6dfe3258db3276a7ea217528c80167db` |
| Batch 05 ROM SHA-256 | `dcb2b8813cc1257001f38586b5a214bccae24e29a3812f47c4a897fbfef9ec73` |
| Existing Japanese entries | 1,717 |

All 461 IDs are unique and equal to Batch 06 selection, in the same order as the Claude input. Extra/missing IDs 0. Original, category, source control metadata, protected-token metadata, scene/conversation metadata, `review_source=claude_cli`, ROM-derived text/control segments, kanji and PCS encoding: mismatch 0. Source FE 254; FA 0. Status: confirmed 214, existing_official 212, existing_glossary 29, needs_context 6, needs_technical_fit 0. Adopted review text 455; six empty review values stay held.

## 2. Names and glossary

The 212 `existing_official` entries all have input `pokeapi-ja-hrkt` origin and `official_terms`. Reviewed wording equals deterministic text after whitespace normalization; three Pokédex descriptions differ only in FE/spacing placement. Memory-only official classification 0. Of these, 204 survive control/fit checks; eight are held.

The 39 pending-name audit uses exact English entity identity, `ja-hrkt` and Japanese PCS. Result: **verified_exact 1, verified_difference 0, ambiguous 12, not_found 6, not_applicable 19, unsupported 1**. The sole exact term is `Catching Charm`, but its reviewed translation remains empty and the PokeAPI value conflicts with the approved glossary; it is **not applied**. Thus 38 lack an official verification, and none of these 39 flagged entries is automatically promoted. The 12 Pokédex genus rows disagree with PokeAPI when using the repository's `table_index_plus_one` mapping; apparent shifted matches were not assumed to prove a species identity. `Black Augurite` lacks a `ja-hrkt` name in the returned entity. Unsupported PokeAPI types remain `not_applicable`, not memory-verified.

All 29 existing-glossary entries have an approved matcher hit in the correct category/entry scope, including numeric `Route [N]` expansion; target-presence check 29/29. All 29 applied. The 25 new candidates remain entry-scoped proposals only, without editing `glossaries/ja.json`; all 25 affected entries are held pending approval or another reason. The six `needs_context` entries have empty final translation and `final_apply=false`.

## 3. Control, renderer, slot and owner gates

The raw Claude review preserves all 254 FE boundaries. Candidate controlfix reported zero general control mismatches, but byte-sequence comparison against ROM source found **72** translated entries where FE/control structure changed. All 72 were excluded. The applied subset contains **81 source FE and 81 output FE**, in the same order, with no inserted/deleted/moved structural control. Protected-token, encoding, kanji and page-switch checks pass. No Batch 06 FA entry.

Menu/UI 17: twelve applied, five held for unresolved name/glossary/context. Each row's table, source controls, label/value uncertainty, slot/fixed flags and pointer owners are recorded in `ja_phase6_batch06_menu_audit.json`. For these custom battle submenu/trainer-card rows, exact usable renderer width is **not proved**. The warning `width_runtime_unverified` alone held zero rows. No known 240px physical-screen overflow was applied; this does **not** prove runtime fit or field/cursor geometry. mGBA validation remains required.

Exact whole-ROM owner scan found 102 selected entries with additional/stale pointer evidence. Only relocations require the relocation owner gate; five candidates were held for incomplete ownership. A separate whole-ROM interior-pointer scan found 28 selected entries with conservative interior hits, but none of the applied relocations used an unproved interior reference. Six type-name candidates exceed their 7-byte fixed/unrelocatable slots and remain English. No wording was shortened or truncated to fit.

The final safe set has 331 entries: 297 in-place and 34 vetted-FF relocations, 45 pointer-owner writes. Original status of safe entries: 204 existing_official, 29 existing_glossary, 98 confirmed. The remaining 130 are held. Reason counts overlap: control boundary 72, official name 38, glossary proposal 25, empty/context 6, pointer 5, fixed-slot overflow 6.

## 4. Controlfix, injection, binary audit

Normal controlfix ran on 1,717 unchanged prior entries plus 412 preliminary candidates. After safety gating, it was rerun on only 331 safe raw candidates plus the same prior 1,717. The resulting 2,048-entry file is byte-for-byte equal to the assembled safe controlfixed JSON; a second pass changed **0** entries and is byte-for-byte identical. The first 1,717 JSON entries equal the Batch 05 input exactly. Remaining controlfix mismatches 0.

Full-from-English strict dry-run of all 2,048: encode/pointer/space/fixed-truncation/ability-compaction/runtime/graphics failures **0**. That dry-run would move **303 of 308** prior relocation destinations, so it was not used to build the ROM. Incremental strict dry-run and build against the hash-verified Batch 05 ROM agree exactly: input 331; in-place 297; relocated 34; pointer writes 45; used vetted FF 357 bytes; remaining 611,279 bytes. Missing relocation, pointer mismatch, implausible pointer, no-space, encode error, fixed/no-relocation truncation, runtime patch, graphics patch: **all 0**. No lossy-fit or reclaimed-slot option.

Private ROM: `out/unbound-ja-phase6-batch06.gba`, 32 MiB. MD5 `045c6dfd491a342250e131a9a81c69c2`; SHA-256 `99e3a0fe0a2c84dee07a3ae6be68292e34344ff1378659b0b824a6e422f5182b`. Source ROM and Batch 05 ROM hashes remain unchanged.

Batch 05-to-06 changed **6,879** bytes: in-place text **6,409**, relocated text **325**, pointer bytes **145**, unexpected **0**. All 1,717 prior text destinations and pointer operands were separately protected and unchanged. Source-English-to-Batch-06 audit classifies **122,320** changed bytes: in-place text **110,030**, relocated text **4,114**, pointer bytes **8,176**, unexpected **0**. No ASM/font/graphics/runtime bytes changed. Auditor regression test flips an unrelated ROM byte and verifies rejection.

## 5. Runtime QA and Phase 6 accounting

`tests/fixtures/ja_phase6_batch06_runtime_qa.json` has 36 prioritized cases: Menu/UI 8, official PokeAPI 5, approved glossary 4, FE-heavy 8, long text 3, relocation 4, multiple owners 2, other 2. Exact live routes are not established; all results `not_human_tested`. No mGBA pass is claimed.

| Batch | Selected | Applied | Held |
| --- | ---: | ---: | ---: |
| 01 | 407 | 385 | 22 |
| 02 | 408 | 164 | 244 |
| 03 | 408 | 125 | 283 |
| 04 | 408 | 198 | 210 |
| 05 | 408 | 168 | 240 |
| 06 | 461 | 331 | 130 |
| **Phase 6 total** | **2,500** | **1,371** | **1,129** |

Phase 5以前の677件とは別に、Phase 6で1,371件を新規適用。現在の日本語適用総数 **2,048**。`out/phase6/ja_phase6_final_cleanup_inventory.json` に残る1,129件をID単位で統合し、primary/secondary/raw理由、状態、P1/P2/P3、次の調査を保存。分類と優先順位の集計は `docs/ja-phase6-final-cleanup-inventory.md`。**Inventory作成のみで、Final Cleanupは未着手。**

## 6. Verification and files

Targeted Batch 06 tests: 6 PASS。全pytestと静的確認の最終結果は本作業の完了報告に記録する。再現用スクリプトは `scripts/audit_ja_phase6_batch06_names.py`、`scripts/build_ja_phase6_batch06.py`、`scripts/build_ja_phase6_batch06_handoff.py`。回帰テストは `tests/test_ja_phase6_batch06.py`。追加fixtureは36件のruntime QA。本報告とcleanup台帳報告を追加。private生成物は `out/phase6/ja_phase6_batch06_*.json`、`out/phase6/ja_phase6_final_cleanup_inventory.json`、上記ROM。既存未追跡ファイルを保存し、tracked file、glossary、codec、injector、font、renderer、graphicsは変更していない。commit/pushなし。

**Final Cleanupへの静的GO**: safe subset注入、既存1,717不変、制御境界、公式名gate、ROM差分、2,500件accounting、master inventoryがPASS。**Runtime/releaseはHOLD**: mGBA未確認、保留1,129件未解決。
