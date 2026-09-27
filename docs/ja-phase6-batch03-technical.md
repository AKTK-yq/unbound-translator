# Phase 6B-3 — Batch 03 technical integration

Static gate: **PASS for 125 safe entries; 283 held in English.** Runtime display and
event reachability are **not yet human-tested**. Branch `japanese-support`, initial
HEAD `34c2866b1ffe380ea8abd63c5752f109926bdccc`. Initial worktree was already
dirty (six tracked modifications and numerous untracked Phase 6 files); none was
reset or deleted. Initial pytest: 324 passed. The private input ROM MD5 was
`9cad8e771940e7f7094d13911552cef0`; Batch 02 ROM SHA-256 was
`c7f71c87c644871f2e66c28a6258818ba3523441ff1726183b8340d44872f4a7`.
Initial safely applied total: 1,226.

1. **408 review validation:** exactly 408 unique IDs in source order; extra,
   duplicate, original/category, protected-token, control, kanji and PCS charmap
   errors: 0. See `out/phase6/ja_phase6_batch03_review_validation.json`.
2. **Review source:** Claude CLI 160, user-approved Codex completion 248. Original
   statuses: confirmed 234, existing_official 0, existing_glossary 29,
   needs_context 65, needs_technical_fit 80.
3. **All 122 FA:** semantic-confirmed 51, segment-conflict 41, context-only hold
   21, other technical hold 9; disjoint sum 122. FA source structure: 2 simple,
   120 complex. The earlier report's 29 conflict labels were uppercase; 12 more
   lowercase labels were found case-insensitively. Five of the 41 conflicts also
   have a context hold, so the reported 26 context holds become 21 *context-only*.
   Thus the purported “remaining 16” is not an independent class: 12 previously
   uncounted conflict labels plus 9 true technical-other rows, offset by 5
   double-counted context/conflict rows. See FA audit and retranslation handoff.
4. **108 name pairs / 84 entries:** checked through the existing PokeAPI `ja-hrkt`
   localizer with exact English entity identity and PCS encodability.
5. **Verified exact:** 90 pairs; no memory-only official value was accepted.
6. **Verified differences:** 0.
7. **Unresolved names:** ambiguous 6, not_found 12, unsupported 0. Where a
   Japanese name is necessary and unverified, the entry is held. Gems/Hard
   Stones and cross-kind or non-contiguous English terms are not guessed.
8. **FA semantic-confirmed 51:** reconstructed from ROM-derived source segments
   plus reviewed Japanese segment text, never by a reviewer-chosen FA index.
9. **FA layout PASS:** 16; all 16 are applied. The normal-font ROM widths and
   source FE/FA/FB boundaries support a conservative static pass.
10. **FA layout overflow:** 3 exceed 240px and are held.
11. **FA ambiguous:** 32 among the 51; dynamic substitution, unmodelled layout,
    or lines beyond the observed source/208px diagnostic envelope are held.
    Remaining 71 FA are not semantically approved. The 208px/two-line model is
    diagnostic, not a pixel-perfect proof of Unbound's runtime renderer.
12. **Segment conflict 29:** the 29 originally uppercase-labelled rows remain
    untranslated; a case-insensitive audit also finds 12 lowercase-labelled
    rows. `out/phase6/ja_phase6_batch03_fa_retranslation.json` lists all 41,
    source FA-adjacent segment pairs, and asks for reviewer confirmation of the
    actual linguistic collision. No new wording was authored.
13. **Context hold 26:** five overlap with segment conflicts, leaving 21
    context-only in the disjoint FA account. All remain English.
14. **Earlier remaining 16:** explained by the case/overlap arithmetic in item
    3, not silently marked approved.
15. **Needs-technical-fit 80:** 9 in_place, 4 width_overflow, 2 owner_incomplete,
    65 layout_ambiguous. All rows record slot, pointer owners, controls, renderer
    evidence, and measurable Japanese bytes/width. For 65 without a complete
    reviewed draft, exact Japanese width/bytes cannot honestly be measured;
    these are explicitly null and held, not estimated as fits.
16. **Fixed overflow:** 0; selected Batch 03 entries are event dialogue, not
    fixed/no_relocation/structured-table slots.
17. **Width overflow:** 4 of the 80 technical-fit rows; the separate FA layout
    audit finds 3 >240px rows. Byte fit is never treated as UI-width proof.
18. **Owner incomplete:** 2 technical-fit rows; whole Batch 03 audit finds four
    entries with extra whole-ROM exact pointer hits and holds them. See
    `ja_phase6_batch03_owner_audit.json` for every address.
19. **Needs-context 65:** script-operand kind, nearby writers, buffers, source
    neighbors, speaker and caller evidence were recorded. Technically resolved:
    0; pointer proximity does not prove event reachability or speaker. No new
    translation was invented.
20. **Glossary candidates 30:** proposal-only, not merged into `glossaries/ja.json`.
21. **Matcher audit:** all 408 checked with the existing scoped,
    boundary-safe/longest match matcher; scope collisions 0, filtered-substring
    entries 68. Proposal duplicates/overlaps are listed in the glossary audit.
22. **Safe Batch 03 application:** 125, including 16 FA; only these were appended
    to the 1,226-entry Batch 02 controlfixed baseline.
23. **Held:** 283 in English with per-entry reason in the reviewed JSON.
24. **Batch 03 in-place:** 123 newly applied entries. Full ROM map: 1,127
    in-place entries including the baseline.
25. **Batch 03 relocation:** 2 new entries, `scr_1F2C0A9` and
    `scr_1F2FA62`, into vetted FF space; full map 224 relocations. Allocation
    order also moves 10 existing baseline relocation destinations, without
    changing their translations.
26. **Pointer writes:** 3 new owners for the two entries; full map 2,036 owner
    writes including baseline. Every old owner value and new destination value
    was checked against ROM bytes.
27. **Japanese applied total:** 1,351 (= 1,226 baseline + 125 Batch 03).
28. **FA applied count:** 16; Batch 02's provisional 30 FA drafts remain held
    and unchanged.
29. **Strict dry-run:** 1,351 inputs; encode errors, pointer mismatches,
    implausible pointers, missing relocations, skipped no-space, fixed/no-reloc
    truncation, runtime patches and graphics patches: all 0. Vetted FF use:
    3,160 bytes; remaining 612,673. Reclaimed storage: 0. See dry-run map.
30. **FA invariant:** all 16 applied entries preserve source segment count,
    exact FE/FA/FB order and FA count in the *encoded post-controlfix bytes*;
    error 0. See `ja_phase6_batch03_fa_invariant.json`.
31. **Controlfix:** 1,351 translated, 0 remaining control mismatches, 0
    FA_PLACEMENT_REVIEW_REQUIRED, 16 segmented rebuilds. Second pass produces
    byte-for-byte identical JSON. Initial attempt to merge from raw Batch 02
    input re-held 78 old FA entries; switching to the already-controlfixed
    Batch 02 baseline preserved all 1,226 complete entry objects exactly.
32. **ROM:** `out/unbound-ja-phase6-batch03.gba`, 32 MiB, SHA-256
    `535509572cf3f61951a58b6c700eea8ca669776bb9c596f890938405c1afdae3`.
    Input and Batch 01/02 ROMs were not overwritten.
33. **Binary audit:** source→Batch 03: 95,805 changed bytes: 85,286 in-place
    text, 2,954 relocated text, 7,565 pointer bytes; unexpected 0. Batch 02→03:
    12,445 changed bytes, all attributable to new slots or old/new vetted
    relocation destinations/pointer owners; unexpected 0. ASM/runtime/font/
    graphics changes: 0. Full exact ranges are in the two audit JSON files.
34. **Runtime QA:** 36 candidates in
    `tests/fixtures/ja_phase6_batch03_runtime_qa.json`, including 10 FA and 2
    relocations. Event routes are *unverified*; mGBA screenshots and progressed
    saves are still needed. No battle/mission/choice renderer claim is made for
    this event-dialogue-only selection.
35. **Pytest:** 331 passed using `.venv/Scripts/python.exe -m pytest`.
36. **Static checks:** changed Python compiles; `git diff --check` passes.
37. **Batch 04 style:** `out/phase6/ja_phase6_batch04_style_handoff.json`
    carries prior speaker, official-name, glossary, buffer, counter, sign,
    mission and pacing rules plus explicit segmented-only FA wording and layout
    approval gates. This is guidance, not translated Batch 04 output.
38. **Batch 04 segmented source:** 408 source-only entries; 50 FA entries have
    ROM-derived `control_segments` and `translation_units` in
    `out/phase6/ja_phase6_batch04_fa_segmented_input.json`. No Batch 04 prose
    was translated.
39. **GO/HOLD:** **STATIC GO** for Batch 04's segmented *input method* only:
    reconstruction, control invariants, idempotence, name lookup and ROM audit
    pass. **RUNTIME HOLD** for claiming layout/display correctness or release
    until mGBA checks; ambiguous FA remains automatic hold.
40. **Created files:** `scripts/audit_ja_phase6_batch03_names.py`,
    `scripts/build_ja_phase6_batch03.py`,
    `scripts/build_ja_phase6_batch03_handoff.py`,
    `tests/test_ja_phase6_batch03.py`,
    `tests/fixtures/ja_phase6_batch03_runtime_qa.json`, and this report.
    Generated JSON/ROM live under ignored `out/`; no shared codec, renderer,
    font, glossary or injector source was changed in this phase.
41. **`git diff --stat`:** six pre-existing tracked files, 86 insertions and 4
    deletions: `.gitignore` +1, `004_controlfix_translations.py` +54/−1,
    `README.md` +1, `glossaries/ja.json` +5/−2,
    `tests/test_ja_phase5e.py` +2/−1,
    `tests/test_translation_glossary.py` +23. Git does not include the newly
    created, still-untracked Batch 03 files in this stat.
42. **`git status --short`:** the same six tracked modifications plus the new
    Batch 03 scripts, test, QA fixture and report listed in item 40, and the
    pre-existing untracked Phase 6A/Batch 01/Batch 02/FA/review source and
    documentation files. `out/` ROM/JSON artifacts are ignored and absent from
    status. No commit or push was made.

Reproduce: run `python scripts/audit_ja_phase6_batch03_names.py`, then
`python scripts/build_ja_phase6_batch03.py`, controlfix, strict injector
`--dry-run --fail-on-no-space`, real injector only after gate success, and
`python scripts/build_ja_phase6_batch03_handoff.py`. Use the existing
`.venv/Scripts/python.exe` on this Windows checkout to run the full test suite.
