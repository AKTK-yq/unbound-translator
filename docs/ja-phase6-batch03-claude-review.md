# Phase 6B Batch 03 kana review

Batch 03 only: 408 `scripts` entries, comprising 286 non-FA and 122 FA entries. The source of truth is `out/phase6/ja_phase6_batch03_fa_segmented_input.json`; the ordinary input and style handoff were consulted. No Batch 04 translation, PokeAPI call, controlfix, injection, ROM build, Python change, glossary approval, commit, or push was performed.

## Status and provenance

| Status | All 408 | FA 122 |
| --- | ---: | ---: |
| `confirmed` | 234 | 40 |
| `existing_official` | 0 | 0 |
| `existing_glossary` | 29 | 11 |
| `needs_context` | 65 | 26 |
| `needs_technical_fit` | 80 | 45 |

FA semantic-confirmed is **51** (`confirmed` plus `existing_glossary`); all 51 still require layout approval. **29** FA entries have `FA_SEGMENT_SEMANTIC_CONFLICT`, and **26** FA entries are context holds. The requested `*_claude_review.json` filename is a handoff contract, not an authorship claim: Claude CLI produced 160 entries; after its session limit, Codex completed 248 entries with the user's approval. Every entry records `review_provenance`.

The 122 FA entries were translated only in ROM-derived segments. Their `reviewed_japanese` full-string field is empty; each segment retains the exact source, index, protected tokens, and following FE/FA/FB boundary. `confirmed` approves semantics only, not FA placement, width, runtime display, or injection. The FA-only fixture records this distinction independently.

## Context and terminology concerns

Speaker metadata is `unknown` for **408/408** entries. ROM proximity or shared conversation IDs were not taken as speaker proof; unknown voice remains neutral. **35** entries contain `[bufferN]` with an unproven producer or value range and are held as `needs_context` where applicable. Raw dynamic suffix cases are also held rather than inferred. Runtime reachability and exact speaker remain unobserved for individual rows.

The official-name file records **108 entry–term checks across 84 entries**. A broader **124 entries** carry `official_name_verification_required` warnings from review or curation. These are provisional only: no exact-English PokeAPI ja-hrkt check was run, no memory-only name was marked `existing_official`, and no plural-to-singular lookup was assumed. The separate glossary-candidate file contains **30** unapproved place, person, faction, class, badge, and Unbound-feature proposals. Nothing was added to `glossaries/ja.json`; `Cube`, `Shadows`, route names, and other scope-sensitive terms still need context checks.

Technical-fit concerns affect **80** entries. In particular, static QA rejected **31** drafts whose FE/FB sequence differed from the source, **2** drafts that moved a protected control across an existing boundary, and **4** drafts with unsupported Japanese-page characters. Those drafts were cleared and held; controls were not guessed back into a different location. Some other `needs_technical_fit` entries retain token-safe semantic segment drafts, but none is injection-approved. Reviewer placeholders were restored to the exact source tokens before validation.

## Validation

- Exactly **408** source IDs, in input order; duplicate, extra, missing, original, and category mismatches: **0**. FA ID set and segment counts match all **122** segmented inputs.
- FA source text and FE/FA/FB boundary sequence changes: **0**. No segment split, merge, or added layout control appears in retained segment drafts. Segment-boundary *semantic naturalness* remains a review judgment, not a byte-level proof.
- Retained nonempty translations: protected-token order mismatches **0**; FE/FA/FB boundary mismatches **0**; Han characters **0**; unsupported Japanese PCS characters **0**. The same checks pass for every retained FA segment.
- All four output JSON files parse. `needs_context` rows contain no speculative Japanese draft. `needs_technical_fit` does **not** mean slot, pixel width, pointer ownership, or runtime behavior passed.

## Batch 04 style handoff — guidance only

Keep kana-only and moderate wakachigaki; use natural katakana for names, no invented first person when speaker is unknown. Preserve each semantic token and original control boundary, especially FA interactive scroll. Translate FA only through ROM-derived independent segments; mark Japanese word-order collisions `FA_SEGMENT_SEMANTIC_CONFLICT` and retain layout-approval-required status even when semantics are confirmed. Hold unknown buffers and raw suffixes pending writer/value proof. Apply only exact, scoped approved glossary terms; keep new proposals separate. Verify franchise names by exact source-English PokeAPI ja-hrkt before official approval. Do not shorten UI or place controls by intuition. Batch 04 has not started.
