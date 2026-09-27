# Phase 6B-2.5: FA / `\l` display-boundary gate

Status: **Batch 03 static GO only with segmented FA input**; the 30 Batch 02 provisional drafts remain held. No Batch 03 translation, FA PoC ROM, renderer patch, commit, or push was made. Human mGBA confirmation is **runtime_unverified**.

Start state: branch `japanese-support`, HEAD `34c2866b1ffe380ea8abd63c5752f109926bdccc`; the worktree was already dirty with `.gitignore`, `glossaries/ja.json`, `tests/test_ja_phase5e.py`, `tests/test_translation_glossary.py` and previous Phase 6 untracked artifacts. Baseline pytest: **309 passed, 16 subtests passed**. Source ROM MD5: `9cad8e771940e7f7094d13911552cef0`. Existing Batch 02 ROM SHA-256: `c7f71c87c644871f2e66c28a6258818ba3523441ff1726183b8340d44872f4a7`. No prior edits or artifacts were reset or removed.

## 1–3. Renderer semantics and FE/FB comparison

`0xFA` is `\l`, not a newline. In the verified source ROM, `RenderText` starts at ROM `0x00005790` / GBA `0x08005790`; the F8–FF dispatch at ROM `0x00005848` uses the table at ROM `0x00005860`. Its FA, FB, FE targets are respectively GBA `0x08005B26`, `0x08005B22`, `0x08005880` (ROM `0x00005B26`, `0x00005B22`, `0x00005880`). Bytes at ROM `0x00005B22–0x00005B29` are `02 20 00 E0 03 20 30 77`: FB stores state 2 and FA state 3. [The local ROM assertion](../scripts/audit_ja_phase6_batch02_controls.py) and [regression test](../tests/test_ja_phase6_fa.py) recheck these anchors.

The [FireRed `RenderText` reference](https://github.com/pret/pokefirered/blob/master/src/text.c) identifies state 3 as `SCROLL_START`: it waits for input with the down arrow, resets `currentX` to the initial X, sets `scrollDistance = maxLetterHeight + lineSpacing`, scrolls the window by that *one rendered line*, then resumes reading the next byte. It does **not** reset `currentY`; the window contents move. In contrast, FE immediately resets X and increments Y by one line with no input wait. FB waits, fills/clears the window, and resets both X and Y. Thus FA is a text-box state boundary and input/scroll event, not a punctuation mark or page clear. [The FireRed character definitions](https://github.com/pret/pokefirered/blob/master/include/characters.h) independently label FA as wait-and-scroll, FB as wait-and-clear, and FE as newline. The Unbound branch targets and state writes are directly verified; exact Unbound state-body equivalence, active window template, font/line spacing at every call site, and whether auto-scroll suppresses a manual button press are **not** independently proved here.

Cursor model: FE advances from line *n* to *n+1*; FA keeps the printer's Y coordinate but scrolls the **window** upward by one line, leaving the next text at the same printer Y on a newly blank rendered row; FB resets to the initial row. A normal dialogue box is modelled as two visible lines, but the exact Unbound window template has not been traced, so this is a diagnostic assumption, not a release fit limit. `\l = line break` would miss the input wait and moving contents.

## 4. Source 30 and static layout

[The complete ROM-backed 30-row audit](../out/phase6/ja_phase6_fa_30_audit.json) records each raw byte string, decoded English, exact ROM control offsets, ordered text/control segments, FA boundary signals, pointer owners, Japanese draft, provisional FA positions, and source/draft layout trace. The parser skips FC/FD/F7/F8/F9 arguments, so a parameter byte equal to FA is not mistaken for a scroll. All 30 raw strings match the extracted source, with **56 actual FA bytes**. In the source, each FA is necessarily an input/scroll and rendered-line boundary; under the two-line model 56/56 occur with the printer at the second-line Y coordinate. Only 1/56 follows a comma or similar clause punctuation and 0/56 follows sentence-final punctuation. A sentence rule therefore cannot recover these boundaries. Actual player-visible use of each row was not proven from a pointer alone.

`N=FE`, `S=FA`, `C=FB` in this index. All statuses are `STILL_AMBIGUOUS`, with `chosen_fa_location=null` and low confidence. The JSON is the authoritative full per-entry analysis; the table is only an index.

| ID | FA | Source boundary sequence | ROM offset |
|---|---:|---|---|
| scr_1F07524 | 2 | CNSSC | 0x01F07524 |
| scr_1F08242 | 1 | NS | 0x01F08242 |
| scr_1F08182 | 2 | CNSSCN | 0x01F08182 |
| scr_1F085F2 | 1 | NS | 0x01F085F2 |
| scr_1F08909 | 2 | CNSCNSCN | 0x01F08909 |
| scr_1F08C1E | 1 | NS | 0x01F08C1E |
| scr_1F08F8A | 1 | NS | 0x01F08F8A |
| scr_1F099C2 | 1 | NCNS | 0x01F099C2 |
| scr_1F09CF0 | 1 | CNS | 0x01F09CF0 |
| scr_1F09F94 | 2 | NCNSSC | 0x01F09F94 |
| scr_1F0A62D | 1 | NSCC | 0x01F0A62D |
| scr_1F0A694 | 1 | NSCC | 0x01F0A694 |
| scr_1F0A939 | 1 | NS | 0x01F0A939 |
| scr_1F0AC54 | 1 | NS | 0x01F0AC54 |
| scr_1F0B209 | 1 | NCNS | 0x01F0B209 |
| scr_1F0B584 | 2 | NSCCNS | 0x01F0B584 |
| scr_1F0B934 | 1 | NCNS | 0x01F0B934 |
| scr_1F0BB4B | 1 | CNCCNCNS | 0x01F0BB4B |
| scr_1F0BC67 | 1 | NCNCNCNS | 0x01F0BC67 |
| scr_1F0BD67 | 4 | NSCNSSS | 0x01F0BD67 |
| scr_1F0C11C | 2 | CNCNSSCC | 0x01F0C11C |
| scr_1F0D3E1 | 8 | NSSCNSCNSSSCCNSCNSCNC | 0x01F0D3E1 |
| scr_1F0E20F | 2 | NCNSSCN | 0x01F0E20F |
| scr_1F0E300 | 1 | NSCN | 0x01F0E300 |
| scr_1F0E12B | 2 | NCNSS | 0x01F0E12B |
| scr_1F0EA44 | 2 | NCNSCCNS | 0x01F0EA44 |
| scr_1F11594 | 4 | NSSCNSS | 0x01F11594 |
| scr_1F11EE2 | 2 | NCNCNSS | 0x01F11EE2 |
| scr_1F123E2 | 3 | NCNCNSSS | 0x01F123E2 |
| scr_1F140AF | 2 | NSSCN | 0x01F140AF |

The trace uses the repository's normal Latin/Japanese ROM glyph-width tables, Latin/Japanese space widths, and a 54-pixel dynamic-buffer estimate. It replays FE, FA, FB, current X, model line and page; it does **not** invent implicit wrapping. A 208-pixel/2-line normal dialogue box is only a model. Under it 0/30 English sources but 26/29 encodable Japanese provisional drafts exceed 208 px on a line; one draft is empty. This strongly rejects the drafts' terminal-FA layout, but does not prove the exact safe alternative. Font changes, icon widths, colors, dynamic buffer contents, other renderers and actual window templates can invalidate pixel-perfect predictions; no draft is approved on model width alone.

## 5–11. Placement rules, 30 decisions, runtime QA, PoC

| Candidate | Engine fit | Decision |
|---|---|---|
| A: keep source boundary | Preserves scroll/input event and current line, but requires Japanese prose divided at that boundary. | Adopt as a constraint, not by copying source character index. |
| B: keep segment count | Count alone can move input/scroll to a different event; unsafe. | Reject alone. |
| C: recompute from Japanese line occupancy | Could place scrolling when a row fills, but actual window metrics, renderer, and dynamic expansions are not fully known. | Diagnostic only; never auto-place now. |
| D: keep sentence/clause boundary | 55/56 source FAs are neither sentence-final nor clause-final by simple punctuation. | Reject alone. |
| E: source-defined display segments + renderer/layout review | Reconstructs the exact FE/FA/FB sequence after independently translated segments; rejects token migration, then checks layout/context. | **Adopt.** |

Every one of the 30 Batch 02 drafts has provisional FA placement after freeform prose rather than reviewed segment translations. Resolved source-boundary: **0**; resolved layout: **0**; resolved segmented: **0**; still ambiguous: **30**. The source structure is known, but the Japanese text-to-segment assignment is not. All 30 remain English. Do not promote a guessed point or append FA at the end.

The [four-case runtime QA fixture](../tests/fixtures/ja_phase6_fa_runtime_qa.json) prioritizes apparent early mother/Super Cube/Costume Box dialogue (`scr_1F0BB4B`, `scr_1F0BC67`, `scr_1F0BD67`, `scr_1F0C11C`). Event identity and routes are text-inferred, not played or map-traced. It records source English, tentative route, exact FA offsets, expected future segment sequence, input/scroll checkpoints and failure signs. There is no approved Japanese sequence yet, so **no focused FA PoC ROM** was built; human mGBA status is `runtime_unverified`.

## 12–15. Controlfix, segmented translation, fallback, schema

For a new Japanese FA entry, Claude receives ROM-derived `translation_units` (English text only) from [the annotated Batch 03 input](../out/phase6/ja_phase6_batch03_fa_segmented_input.json); it must return `translated_segments` in order, without inserting FE/FA/FB or page switches. `control_segments` (`text`, `after_control`), `source_boundary_sequence`, existing `controls` counts and `fa_placement_policy=require_segments` are additive fields; the original 408-row input is unchanged. The source may include a buffer or critical token; these must remain in the same segment. Segmenting can constrain natural Japanese sentence order and may require human rewriting of adjacent units, but cannot silently move a wait boundary.

`004_controlfix_translations.py` now reconstructs the boundary sequence from source segments **only when** all segments, their source order/counts and per-segment critical tokens agree, and `fa_layout_reviewed=true` records a separate human/renderer fit review. It then adds the Japanese/Latin page controls; re-running is idempotent. Any new freeform FA draft, missing units, changed controls, moved token, or unreviewed layout becomes `translated=null`, with `fa_unplaced_candidate` retained and `fa_placement_status=FA_PLACEMENT_REVIEW_REQUIRED`. It therefore cannot be injected accidentally. Legacy already-controlfixed Japanese entries with matching critical controls remain unchanged for compatibility; they are **not** retroactively certified by this new rule. No character-index restoration or automatic line-occupancy insertion occurs.

## 16–20. Scale, Batch 03 handoff, gate, limits

[The Phase 6 selection audit](../out/phase6/ja_phase6_fa_selection_counts.json) covers 2,500 entries: **352 FA entries / 628 FA bytes**, 150 entries with multiple FA, 352 with FE, 294 with FB, 98 with dynamic buffers, 51 with FC08 timed pause, and 164 with other FC/F7/F8/F9 controls (overlapping groups). These are from extracted `controls`, not a raw ASCII substring count. [The Batch 03 audit](../out/phase6/ja_phase6_batch03_fa_audit.json) covers all 408 entries: **286 no FA, 2 simple FA, 120 complex FA**; all **122 FA entries need segmented handoff**. “Simple” means one FA and no FB, buffer or FC; it does not grant auto-placement. No Batch 03 translation was performed.

[The updated Batch 03 style handoff](../out/phase6/ja_phase6_batch03_style_handoff.json) prohibits Claude from choosing or deleting FA, names the annotated input and `translated_segments` contract, uses a technical `fa_placement_review_required` warning instead of `needs_context`, and assigns final placement to Codex/controlfix. **Static GO is conditional on use of the annotated input and the fail-closed controlfix path**; the old freeform Batch 03 input is not GO for FA rows. Translation quality, dynamic-buffer grammar, actual renderer widths and runtime behavior remain separate gates. The 30 old drafts do not become approved by this Batch 03 GO. No runtime or release GO is claimed.

## 21–23. Verification and workspace state

`tests/test_ja_phase6_fa.py` covers the ROM state fixture, raw parser including FC argument `FA`, FE+FA, FA+FB, multiple FA, buffer, source reconstruction, no character-index restoration, hold on ambiguous/unreviewed/moved-token/unknown-glyph cases, idempotency and Batch 03 handoff. Final `python -m pytest -q`: **324 passed, 16 subtests passed**. `py_compile` of changed Python and `git diff --check`: **PASS** (the latter printed only pre-existing Windows LF/CRLF warnings).

Changed/created for this phase: `004_controlfix_translations.py`, `lib/fa_control.py`, `scripts/audit_ja_phase6_fa.py`, `scripts/build_ja_phase6_batch02_handoff.py` (already untracked from Phase 6B-2), `tests/test_ja_phase6_fa.py`, `tests/test_ja_phase6_batch02.py` (already untracked), `tests/fixtures/ja_phase6_fa_semantics.json`, `tests/fixtures/ja_phase6_fa_runtime_qa.json`, `README.md`, this report, and the ignored `out/phase6/ja_phase6_fa_30_audit.json`, `ja_phase6_fa_selection_counts.json`, `ja_phase6_batch03_fa_audit.json`, `ja_phase6_batch03_fa_segmented_input.json`, `ja_phase6_batch03_style_handoff.json`. No source or Batch 02 ROM was rewritten. Other status entries below predate this task.

`git diff --stat` (tracked files only; pre-existing unrelated changes included):

```text
 .gitignore                         |  1 +
 004_controlfix_translations.py     | 55 +++++++++++++++++++++++++++++++++++++-
 README.md                          |  1 +
 glossaries/ja.json                 |  7 +++--
 tests/test_ja_phase5e.py           |  3 ++-
 tests/test_translation_glossary.py | 23 ++++++++++++++++
 6 files changed, 86 insertions(+), 4 deletions(-)
```

`git status --short --branch` at completion (untracked Phase 6 history deliberately retained):

```text
## japanese-support...origin/japanese-support
 M .gitignore
 M 004_controlfix_translations.py
 M README.md
 M glossaries/ja.json
 M tests/test_ja_phase5e.py
 M tests/test_translation_glossary.py
?? docs/ja-phase6-batch01-claude-review.md
?? docs/ja-phase6-batch01-technical.md
?? docs/ja-phase6-batch02-claude-review.md
?? docs/ja-phase6-batch02-technical.md
?? docs/ja-phase6-fa-control.md
?? docs/ja-phase6a.md
?? lib/fa_control.py
?? scripts/audit_ja_phase6_batch01_buffers.py
?? scripts/audit_ja_phase6_batch01_fit.py
?? scripts/audit_ja_phase6_batch01_names.py
?? scripts/audit_ja_phase6_batch02_controls.py
?? scripts/audit_ja_phase6_batch02_names.py
?? scripts/audit_ja_phase6_fa.py
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
?? tests/fixtures/ja_phase6_fa_runtime_qa.json
?? tests/fixtures/ja_phase6_fa_semantics.json
?? tests/fixtures/ja_phase6_runtime_candidates.json
?? tests/fixtures/ja_phase6_selection.json
?? tests/test_ja_phase6_batch01.py
?? tests/test_ja_phase6_batch02.py
?? tests/test_ja_phase6_fa.py
?? tests/test_ja_phase6a.py
```
