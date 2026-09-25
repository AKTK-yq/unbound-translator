# Japanese Phase 5F: held-entry and pacing audit

## Starting state

- Branch `japanese-support`, HEAD `22a425f6850308383ae1bee746a3c4ebdb47cf0d`.
- Existing Phase 5E edits/artifacts were preserved; nothing was reset, deleted,
  committed or pushed. Starting test baseline: 261 passed. Source ROM MD5
  `9cad8e771940e7f7094d13911552cef0`. Phase 5E ROM MD5
  `c067bf8c8e60b8e8ca3bc0df42e8820a`, SHA-256
  `4cccd4887f9056cc14d35839b30d922bd56cada621a36492314c29bf6fbce3fc`.
- The 44-row Phase 5E ledger matches A4/B16/C10/D2/E3/F8/H1. The complete
  row-by-row `id`, category, original, class, current reason/status, ROM/GBA
  address, slot, owners, new evidence and disposition are in
  `out/ja-phase5f-remaining-audit.json`, reproduced by
  `scripts/audit_ja_phase5f_remaining.py`. It preserves the clipped A-row in
  the triage ledger although that row was already removed from extraction.

## 44 held entries

| Class | Count | Phase 5F result | New Japanese applied |
|---|---:|---|---:|
| A | 4 | Three credit staff-name blocks deliberately remain Latin; clipped difficulty warning is superseded by already-translated complete source at ROM `0x01F4E26F`, owner `0x01EBD7FC` | 0 |
| B | 16 | One buffer value pair (`on`/`off`) proven in local script; other insertion grammars/complete values remain unproven | 0 |
| C | 10 | Five held weekday rows gained exact pointer owners; five trainer names remain fixed indexed records without per-name owners | 0 |
| D | 2 | Corrected raw-prefix evidence; neither can be safely skipped/restarted yet | 0 |
| E | 3 | Options label/choices verified in ROM; critical-hit color and A–Z sort semantics unresolved | 0 |
| F | 8 | Form-record relationships documented; trim, VICTORIES and Gruff still need visual/context evidence | 0 |
| H | 1 | `scr_1080302` still strongly resembles data, but its consumer is not proven; remains English and not automatically excluded | 0 |

Four A cases are **disposition-resolved without translation**. Forty of the
original 44 remain translation-unresolved, including the five weekday rows
whose owner *metadata* improved. Claude wording handoff now contains **one**
newly clarified case (`scr_1F1A99A`) at
`out/ja-phase5f-for-claude.json`; the other held entries are not sent as
translation-ready without their missing technical or visual evidence. Human
QA has **12** cases in `tests/fixtures/ja_phase5f_visual_qa.json` (F8, E3,
and text pacing). Its exact-route field explicitly says when a progressed save
or a route discovery is still required; only the Options pacing symptom is
human-confirmed reachable in this phase.

The three A credit blocks have a real PCS roundtrip length mismatch:
source/decoded-reencoded lengths are **35/33, 32/30, 18/16 bytes**. Raw
consecutive `FE FE` line breaks encode as a single `FB` when converted from
decoded text. Their raw and re-encoded byte streams are in the 44-row audit.
Keeping the original ROM bytes, rather than re-injecting even identical Latin
names, preserves the credit layout exactly.

### Buffer source B16 and page restoration

The gendered `He`/`her`/`him`/`boy` fragment owners include packed script
`85 <buffer index> <32-bit pointer>` operands; e.g. `He` at ROM
`0x01F8DD36`, GBA `0x09F8DD36`, has buffer2 writers at ROM
`0x01E9EE36`, `0x01EA34EF`, `0x01EA525E`, `0x01EA57C7`. `her` at
ROM `0x0078922E` is copied to buffers 0 and 1. That proves source type,
not the whole inserted Japanese sentence. `SON` is a different structured
owner case. Six held battle-message fragments use battle grammar operands
(`\00`, `\34`, `\36`, `\38`, `\3B`, `\3C`, `\3D`), not simply the
script FD buffer. Their writer/value ranges are still unproven. Four of the
five held dynamic script messages lack a proven buffer assignment; Zeph,
Arceus-relative, Oddish Leaves and Pokémon-take contexts do not by themselves
prove exact values. No gender fragment or battle grammar was translated.

For the fifth script, bulb interaction `scr_1F1A99A` at ROM `0x01F1A99A`,
GBA `0x09F1A99A`, local `85 00` commands assign literal `on` at ROM
`0x01F1A9C6` and `off` at `0x01F1A9C9` to buffer1. Both literals have five
packed pointer owners: `on` at ROM `0x01E74C91`, `0x01E74CEE`,
`0x01E74D4B`, `0x01E74DA8`, `0x01E74E05`; `off` at `0x01E74CBB`,
`0x01E74D18`, `0x01E74D75`, `0x01E74DD2`, `0x01E74E2F`. All ten are
byte-verified `85 00 <target>` operands. The script locality is strong
evidence for the on/off value, but complete control-flow and all display
paths still need runtime confirmation. Japanese prose around Latin-valued
`[buffer1]` must use `[japanese]... [latin][buffer1][japanese] ...[latin]`;
the page-restore roundtrip and existing controlfix idempotency tests pass.
This pair was sent to Claude for coordinated wording, **not injected**.

### Pointer ownership C10 and extractor delta

Five held short weekday labels at ROM `0x00A4E554` through `0x00A4E564`
are 4-byte fixed slots (the complete table is seven rows through
`0x00A4E56C`). Their seven direct 32-bit pointer owners form a contiguous
table at ROM `0x00A6D0AC–0x00A6D0C7`, GBA
`0x08A6D0AC–0x08A6D0C7`. For example, `Sun` at ROM `0x00A4E554`, GBA
`0x08A4E554`, has owner `0x00A6D0AC`, whose word is `0x08A4E554`.
`001_extract_unbound_text.py` now merges these owners while marking all
seven weekdays `no_relocation`: an indexed/stride consumer or width constraint
is not ruled out. **Five of ten held C rows gained owner metadata; zero are
relocation-approved.** The five held trainer-name rows are fields within the
ROM `0x0023EACC` table (12-byte names, 40-byte record stride). Base-address
references, including ROM `0x00114DD8`, `0x00115068`, `0x0012DF5C`,
do not constitute per-name pointer ownership. They remain English.

Separate from the 44, the extractor now records all ten `on/off` packed
owners above, not just the two generically found owners. A fresh extract to
`out/ja-phase5f-extracted.json` has exactly **25,044** entries and unchanged
IDs/category counts. Against Phase 5E extraction, only weekday owner/guard
metadata (7 rows) and bulb-literal owners (2 rows) changed. Tests cover exact
table structure and source-ROM bytes. No translation or ROM bytes changed.

### Leading/interior D2, structured E3, visual F8, suspected data H1

- `scr_7A95BA`: ROM `0x007A95BA`, GBA `0x087A95BA`. Actual first raw bytes
  are `14 FE ...`, **not raw D1** as the Phase 5E prose claimed. Script text
  operands point at this start. The previous byte, complete decoded span and
  every recorded owner are in the JSON audit; no alternate safe start or
  consumer skip has been proven.
- `scr_750C28`: ROM `0x00750C28`, GBA `0x08750C28`. Actual first raw bytes
  are `02 FE AA AA ...`, **not raw C1**. The apparent Crater Town prose starts
  after the prefix. Multiple script operands point to the earlier start.
  No blind interior rewrite or extractor deletion was made.
- `scr_1F1057C`: Options prose says `Capped Share`, while actual label
  `Exp. Gain` is ROM `0x01F4DB35`, owner `0x01FB3960`; choices are
  `Exp. Share` at `0x01F4DC57`, owner `0x01FB3A10`, and
  `Capped Exp. Share` at `0x01F4DC62`, owner `0x01FB3A14`.
  Display width and reviewed Japanese wording must agree with the screen.
  The critical-hit color span and Mission Log A–Z comparison path are not
  proven, so neither structured text is translated.
- `scr_1F0F842` follows the NEW GAME jacket selector, but ROM script order
  alone does not reveal whether “trim” is a garment edge, accessory or
  second color. `VICTORIES` at ROM `0x004178FD` is a menu-list label near
  EGGS/QUIT/HALL OF FAME, not a proven win-count display. `Gruff` at ROM
  `0x01FAE999` has 14 script pointer sources and is name-label-like, but
  person/nickname spelling is not confirmed.
- The five held Pokédex form names have records in the 8-byte table at ROM
  `0x01A35450`; record pointer and u16 index relations are in the audit JSON.
  `Djinn` has index 1210, `High King` 1211 and 1213, `Unique Horn` 1214 and
  1220, `Dancing` 1224, `Sphere` 1237 and 1238. Shared names and surprising
  adjacent species indices mean index arithmetic alone is not proof of the
  actual form display path. No Japanese form name was invented.
- `scr_1080302` at ROM `0x01080302`, GBA `0x09080302`, is a high-entropy,
  control-heavy decoded run. Three apparent pointer words at ROM `0x00B2A2BC`,
  `0x01181A4C`, `0x011B71F4` match its GBA address but are within non-text-like
  data. With no renderer or definitive data-table consumer traced, excluding
  the extractor row would overstate the evidence. It remains a quarantined
  English-only extraction candidate; the regression test rejects applying it.

## Text pacing and safety outcome

The focused report `docs/ja-phase5f-text-pacing.md` documents ROM
`0x00005790`/GBA `0x08005790` renderer flow, `textSpeed`/`delayCounter`,
Japanese/Latin page flag, blank-space glyph path, punctuation and exact
Options examples. Japanese-page spaces do traverse the ordinary glyph path,
but sampled Options Japanese help strings have **22** glyphs versus English
**38/36**, and fewer spaces. Zero of 674 translations add explicit
`FC08/09/0A` wait controls; sampled Options help also adds no page break.
Pacing classification for the actual subjective symptom is **P7, unresolved**.
P1's mechanism exists but does not explain this sample; P2 explicit pauses
are ruled out in the static audit. Controlfix added 32 FA/28 FB across 8
other entries; these may need separate screen QA. The text-only A/B proposal
in `out/ja-phase5f-pacing-proposal.json` is **not applied**. No ASM,
renderer, font or glossary change was made for pacing.

Because newly approved Japanese entries = **0**, the condition for another
controlfix, strict dry-run, injection and binary audit was not met. No
`out/unbound-ja-phase5f.gba` was generated. The existing Phase 5E strict map
and binary audit remain PASS, but are **not** mislabeled as a Phase 5F build.
Japanese applied total remains **674**. Source and Phase 5E ROM hashes remain
the starting hashes above.

## Validation and next actions

- `python -m pytest`: **270 passed**. `python -m py_compile` for changed Python:
  PASS. `git diff --check`: PASS (Windows checkout line-ending warnings only).
- Added regression checks: weekday/bulb pointer ownership and source bytes,
  held 44 classifications, D/H quarantine, Claude/visual fixture parsing,
  Japanese→Latin dynamic→Japanese byte roundtrip, spaces/punctuation as
  ordinary glyphs, no added explicit waits, sampled Options step reduction,
  and stable ROM renderer bytes. Existing controlfix twice-idempotent tests
  remain passing.
- Next human action: record matched Text Speed Options video/frame captures
  in source and Phase 5E ROMs; inspect 12 QA cases and return exact screenshots
  for trim, VICTORIES, Gruff, forms and the structured UI cases.
- Next technical action: trace C trainer table consumer, D prefix/special
  semantics, E comparator/color path, H data-table owner and remaining B
  producer/insertion control flow before accepting translations. Send only
  the bulb `on/off` wording/context to Claude now; do not treat its draft as
  translation approval.

## Changed files and Git status

Phase 5F edits: `001_extract_unbound_text.py`, `tests/test_extraction.py`,
`tests/test_ja_phase5f.py`, `scripts/audit_ja_phase5f_remaining.py`,
`scripts/audit_ja_phase5f_pacing.py`, `tests/fixtures/ja_phase5f_visual_qa.json`,
this report, and `docs/ja-phase5f-text-pacing.md`. Local ignored outputs:
`out/ja-phase5f-extracted.json`, `out/ja-phase5f-remaining-audit.json`,
`out/ja-phase5f-for-claude.json`, `out/ja-phase5f-pacing-analysis.json`,
`out/ja-phase5f-pacing-proposal.json`.

At report generation, tracked `git diff --stat` (including pre-existing
Phase 5E edits, excluding untracked files): **9 files, 1,458 insertions,
43 deletions**. `git status`: branch `japanese-support`, no staged changes;
tracked modifications are `.agents/skills/unbound-translation-run/SKILL.md`,
`001_extract_unbound_text.py`, `003_llm_translate.py`, `README.md`,
`glossaries/ja.json`, `lib/translation_glossary.py`,
`tests/test_extraction.py`, `tests/test_ja_phase5_dataset.py`, and
`tests/test_translation_glossary.py`. Untracked: the pre-existing Phase 5D/E
review/build/test artifacts plus the Phase 5F files listed above. ROMs and
generated JSON remain ignored local artifacts. No commit or push.
