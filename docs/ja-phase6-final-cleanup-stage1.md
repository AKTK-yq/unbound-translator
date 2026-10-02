# Phase 6C-1: Final Cleanup Stage 1 (kana-only)

This stage re-audits the 1,129 held Phase 6 entries. It does **not** approve new Japanese terminology, create new translations, or claim mGBA runtime validation. The source ROM is MD5 `9cad8e771940e7f7094d13911552cef0`; the Batch 06 ROM is SHA-256 `99e3a0fe0a2c84dee07a3ae6be68292e34344ff1378659b0b824a6e422f5182b`. Both were read without modification.

## Accounting and resolution

The 2,500 selected IDs split exactly into 1,371 Phase 6 applied and 1,129 unique held IDs. None of the held IDs overlaps the 2,048 current Japanese-applied IDs. Batch attribution, primary/secondary holds, and priority were validated. The normalized source of truth is `out/phase6/ja_phase6_final_cleanup_inventory_v2.json`.

| Resolution class | Entries | Result |
| --- | ---: | --- |
| DETERMINISTIC_SAFE | 117 | Existing candidate unchanged; applied |
| DETERMINISTIC_FIX_REQUIRED | 53 | Original FE segment structure preserved with no-wrap controlfix; applied |
| CLAUDE_TRANSLATION | 246 | Wording or proved static fit/semantic conflict needs review |
| CLAUDE_GLOSSARY | 258 | Exact term/entity/scope decision needed |
| CLAUDE_CONTEXT | 196 | Writer/value or speaker context needed before wording |
| CODEX_INVESTIGATION | 222 | Pointer, buffer, UI, or control mechanics remain unproved |
| RUNTIME_REVIEW | 32 | Battle renderer with theoretical dynamic worst-case overflow |
| KEEP_ENGLISH | 5 | Unchanged Latin labels `HP`, `1F`, `2F`, `3F`, `4F` |
| **Total** | **1,129** | **170 added; 2,218 Japanese entries total** |

Primary-hold outcomes (rows count once, so secondary holds remain separately recorded):

| Previous primary | Total | Applied | Remaining decision |
| --- | ---: | ---: | --- |
| WIDTH_LAYOUT | 191 | 117 | 32 runtime, 27 technical, 15 translation |
| CONTROL_BOUNDARY | 88 | 53 | 26 translation, 9 technical |
| UNKNOWN_BUFFER | 280 | 0 | 173 context, 107 technical |
| OFFICIAL_NAME_UNRESOLVED | 215 | 0 | 189 glossary, 26 translation |
| INCOMPLETE_TRANSLATION | 179 | 0 | 179 translation |
| GLOSSARY_APPROVAL | 69 | 0 | 69 glossary |
| FA_LAYOUT | 30 | 0 | 30 technical |
| CONTEXT_REQUIRED | 23 | 0 | 23 context |
| POINTER_OWNER | 19 | 0 | 19 technical |
| STRUCTURED_UI | 17 | 0 | 17 technical |
| OTHER | 18 | 0 | 13 technical, 5 keep English |

## Focused technical findings

- Width: 137 entries are A (runtime width unmeasured only), 32 B (battle dynamic worst-case only), 5 C (proved static overflow), and 17 D (structured/unknown). Of A, 117 passed exact control/encoding/ownership/fit gates. Fourteen failed source-control equality, ten had physical-screen overflow (some overlap with the control failures), and two had unproved interior-pointer references. B remains a narrowly scoped runtime queue, not automatic application. C requires wording review; no text was shortened here.
- Official names: normalized states are 26 VERIFIED_EXACT, 41 NOT_FOUND, 55 AMBIGUOUS, 46 NOT_APPLICABLE, and 47 NEEDS_HUMAN_TERM_REVIEW. No held entry could be applied solely from an exact official term: all 26 VERIFIED_EXACT entries lack a complete candidate and also have other holds. Exact English term, entity type, and PokeAPI entity are retained for cross-entry evidence; no substring propagation or memory-only official claim is accepted. Thus official-entry resolution is 0/215. The 47 without usable term-level evidence have explicit term-identification handoff records.
- Buffers: 51 type-proven, 72 caller-dependent, 155 dynamic-unknown, 2 unresolved. No held candidate has a proved finite value set or a value-specific grammatical proof sufficient for automatic application. Buffer resolution is 0/280. The queue records existing scene/conversation, speaker confidence, context neighbors, controls, and buffer tokens; it does not invent a writer or speaker. Among the 23 primary context holds, 14 have scene IDs and 9 only script-neighborhood context; all 23 speakers remain unproved.
- Controls: 72 Batch 06 FE candidates had unique source/translated segment pairing. With no-wrap, 53 kept the source control-byte sequence and passed fit; 19 failed conservative static layout and remain for wording review. Seven battle-text boundaries require semantic/grammar review, and nine other boundaries lack a proven segment mapping. FE, FA (input wait plus one-line scroll), and FB were never treated as interchangeable line breaks. All 30 primary FA holds have an unresolved terminal-FA placement; none is proven layout-only. They remain technical investigation rather than receiving a mechanical FA move.
- Pointers: all 19 primary pointer holds still have a missing/stale exact owner or an interior-reference risk in a full 32 MiB scan. Their recorded owners, extra exact hits, instruction-kind hints, interior hits, table identity, and computed-reference uncertainty are in inventory v2. An exact byte hit is a risk signal, not proof of a live owner. No unsafe relocation was promoted.
- Structured UI: 17 rows are classified by fixed/no-relocation and table/menu metadata. Exact renderer geometry is not established, so no row was automatically promoted. The 179 primary incomplete translations remain untranslated; candidate state and raw reason are included in the handoff.
- Glossary: 208 `(exact English term, entity type)` groups cover 329 held IDs, including secondary glossary/official concerns. Of these, 47 glossary-class IDs need the exact term identified before term-level review. `glossaries/ja.json` was not edited and no proposal was approved. Term groups do not imply a global replacement scope.

## Safe integration and ROM audit

The normal pipeline was used: existing reviewed candidate → controlfix (`--target-lang ja`, with `--no-wrap` only for the 53 FE source-segment reconstructions) → source control/width/owner gate → strict injector dry-run → incremental build. The first 2,048 controlfixed JSON entries are exactly equal to the Batch 06 input. The full-from-English 2,218-entry strict dry-run and the 170-entry incremental strict dry-run both had zero encode errors, pointer mismatches, implausible pointers, no-space entries, truncations, ability compactions, runtime patches, and graphics patches. The full dry-run was **not** used to build because it can move old relocation destinations.

`out/unbound-ja-phase6-cleanup-codex.gba` was built incrementally from the hash-verified Batch 06 ROM: 119 in-place, 51 vetted-FF relocations, 153 pointer-owner writes, 734 vetted-FF bytes used. MD5 `469352b02bebed79e51a8fe2a4197992`; SHA-256 `9123192acb91428a88e72592bacf592e4415ed9bf4d16ef67965ec1986ebba79`. The binary audit classified all 8,053 changed bytes: 6,758 in-place text, 683 relocated text, and 612 pointer bytes. Unexpected bytes: **0**. All existing 2,048 text destinations and pointer operands are protected and unchanged. The ROM is private and ignored; do not commit, upload, or release it.

## Handoff and remaining work

- `out/phase6/ja_phase6_cleanup_for_claude_translation.json`: 442 entry records, including 196 context-class entries; this is a queue only, not translated output.
- `out/phase6/ja_phase6_cleanup_for_claude_glossary.json`: 208 exact term/type groups, plus 47 entry-scope term-identification records; affected IDs can overlap other resolution classes.
- `out/phase6/ja_phase6_cleanup_for_codex_investigation.json`: 222 entries requiring nonlinguistic ROM/script/renderer proof.
- `out/phase6/ja_phase6_cleanup_runtime_review.json`: only 32 dynamic-width battle entries; runtime display is not claimed tested.
- `out/phase6/ja_phase6_cleanup_binary_audit.json`: hash, classified changed ranges, and zero-unexpected proof.

Stage 2, Claude review, glossary approval, and release BPS are outside this stage. Human mGBA checks should focus first on newly relocated FE-heavy descriptions and the 117 width-only dialogue entries; these are newly built but not yet observed at runtime.
