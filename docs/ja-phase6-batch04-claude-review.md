# Japanese Phase 6B Batch 04: Claude review

This review covers only the 408 rows in Batch 04. Batch 05 and 06 were not started. No code, controlfix, injection,
ROM, glossary, or PokeAPI verification work was done.

Roles are split as before:
- **Claude:** translates the text inside each FA segment.
- **Codex:** reconstructs FE/FA/FB, approves the layout, and injects.

Output files:
- `tests/fixtures/ja_phase6_batch04_claude_review.json` (408 rows)
- `tests/fixtures/ja_phase6_batch04_fa_claude_review.json` (50 FA rows)
- `tests/fixtures/ja_phase6_batch04_official_name_review.json` (112 term occurrences across 81 rows)
- `tests/fixtures/ja_phase6_batch04_glossary_candidates.json` (55 terms)

## 1–5. Totals and FA scope

| Item | Count |
|---|---:|
| reviewed total | 408 |
| review_source | claude_cli: 408 (no other completion source) |
| non-FA | 358 |
| FA (segmented input) | 50 |
| FA controls | 88 |
| entries with 2 or more FA | 22 |
| FA segments in total | 505 |

The FA-row IDs match the 50 rows with `translation_units` in `ja_phase6_batch04_fa_segmented_input.json`. Rows with FA but no segments: 0.

## 6–13. Status

| status | Count |
|---|---:|
| confirmed | 362 |
| existing_official | 0 |
| existing_glossary | 17 (3 deterministic values, 14 Route [N] template rows) |
| needs_context | 28 |
| needs_technical_fit | 1 |

| FA breakdown | Count |
|---|---:|
| FA semantic-confirmed (confirmed + `FA_LAYOUT_APPROVAL_REQUIRED`) | 48 |
| FA segment conflicts (`FA_SEGMENT_SEMANTIC_CONFLICT`) | 1: scr_1F48ED0 |
| FA context holds | 1: scr_1F4C2ED (`my [buffer1]`, unknown buffer) |

FA confirmed means the wording is final. It does not mean the row is safe to inject. Every FA row carries
`fa_segmented=true` and `fa_layout_approval_required=true`, with no FA added, deleted, or moved, no segments merged or
split, and every token kept in its original segment.

**By category:**

| Category | confirmed | needs_context | Other |
|---|---:|---:|---|
| scripts | 231 | 13 | existing_glossary 17, technical_fit 1 |
| mission_names | 32 | 0 | |
| mission_descriptions | 32 | 4 | |
| mission_objectives | 25 | 0 | |
| mission_log | 7 | 0 | |
| battle_messages | 35 | 11 | |

## 14. Official-name verification (not treated as official)

The input has no `official_terms`. Every Pokémon, move, item, and ability name is therefore a **provisional** Japanese
name, marked `official_name_verification_required` with risk medium or higher.

- 54 English terms appear 112 times across 81 rows: pokemon 44, move 22, item 16, ability 1, plus 30 feature, facility, region, and class occurrences.
- 83 occurrences need PokeAPI checking.
- Plural English forms (Pretty Wings, Rawst Berries, Moomoo Milks, and so on) are noted as a possible mismatch with the exact PokeAPI entries.
- Series facility and class terms (Battle Frontier, Safari Zone, Hiker, Seagallop Hi-Speed, and so on) are outside PokeAPI. They are listed for confirmation as project notation.

## 15. Glossary candidates (55, proposals only)

| Kind | Candidates |
|---|---|
| mission_title (32) | Vサイン, もしもそらをとべたら, そしてすあなもなくなった, ナマコブシなげ, バイバイバタフリー, でんげんをきらないで, and 26 more |
| location (13) | レッドウッドビレッジ, がけのどうくつ, ボーリウスのはか, フロストやま, クーツぬま, ターミガンやしき, マグノリアカフェ, plus the Batch 01 candidates: マグノリアタウン, ポルダータウン, ひがしボーリウス, ぶきみなもり, アンティシスシティ, ボイドいせき |
| person (3) | フェイ, メロニー, マキシマ (held) |
| other and feature | シャドウウォリアー, さいしゅうへいき, レイドの すあな, てんじの せきばん, エージェント, クラシックリーダーズガントレット, いあいぎりめいじん |

Only exact, word-boundary matches from the input matcher were used. There were no substring false positives this batch (0 `possible_glossary_collision`).

## 16. Speaker concerns

- The speaker is unknown for every row. No first-person pronoun or gendered sentence ending was added.
- Tone was kept only where the English itself shows it:
  - The Aklove-type lines ('tis, Unhand me, uncouth brute) are archaic and pompous: 〜ぬ, きさま, ぶれいもの.
  - The rival-type lines are rough and casual (old man = じいさん).
  - The Ivory-type red-text lines are the mother's voice, with わ, の, and かしら removed and a neutral ending used.
- "wench" (scr_1F49E7A) was rendered as the gender-neutral あの うそつきめ. The insult's strength is kept, but its gender marking was not reproduced.
- "my sister" (scr_1F47B99) was rendered as きょうだい because older or younger cannot be determined.

## 17. Buffer concerns (needs_context)

- **`[bufferN]` producers unproven (13 rows):** scr_1F3E6F0, scr_1F41BFB, scr_1F486AA, scr_1F62EF4, scr_1F63C25, scr_1F69F58, scr_1F7927C, scr_1F581E2, scr_1F63D8E, scr_1F65E97, scr_1F6A020, and the FA row scr_1F4C2ED.
- **Gendered fragment:** scr_1F41B12 (the standalone string "daughter").
- **English list built by the engine:** scr_1F6DDE6 (`\\0C`).
- **Battle buffers (11 rows):**

  | Buffer | Rows |
  |---|---|
  | `\\00` (B_BUFF1) | 00004, 00032–00035 |
  | `\\2A` (CFRU-specific) | 00048–00051 |
  | `\\38` (team prefix) | 00052, 00055 |

- **Standalone names pending glossary approval:** scr_1F52A74 (Polder Town), scr_1F67E9C (Ruins of Void), scr_1F7A406 (Maxima).
- **Confirmed as engine-defined:** the fixed battle name buffers `\\0F`, `\\10`, `\\11`, `\\13` and the ability buffer `\\1A`, plus `[player]` and `[rival]` in scripts.

## 18. Technical fit concerns (Codex)

- **Long FA segments:** 60 segments in 39 rows exceed 18 kana; the longest are 26 and 29 characters (scr_1F41F58 seg3, scr_1F42454 seg2). The meaning is fixed, so no unnatural shortening was done. Measure pixel width during layout approval.
- **FA segment conflict:** scr_1F48ED0 seg2–4. With the English boundary kept, the object ends up post-positioned, which is unnatural in a polite report. A candidate segment translation is attached.
- **Glossary term split across segments:** "Light of Ruin" and "Magnolia Town" were each split in the source between two segments. In Japanese, the whole term was placed in the earlier segment.
- **Long mission titles:** Codex decides whether relocation is needed for long titles such as もしもそらをとべたら and ダーウィンはただしかった. Byte counts were not measured.

## 19. Consistency with Batch 03 style

- **Kept:** ナゾノクサのはっぱ, わざマシン, レポートを かく; the counters ひき / こ / かい / とおり; `$` for money.
- **Signposts:** Route [N] uses the approved template `[N]ばんどうろ`.
- **Official names:** Batch 03 kept unverified official names in English. Batch 04 uses provisional Japanese with a warning, as instructed for this batch. All of them are gathered in the official-name review file so Codex can replace them in one pass after verification. Rows that fail verification should be reverted to English under `official_name_rule`.
- **FA contract:** the same as Batch 03. Segments only; FA placement is Codex's decision.

## 20. Style notes for Batch 05

1. **Battle messages.** Batch 05 has many, so use these Gen 3 JP forms:
   - Status: 「○○は ねむってしまった！」, 「どくを あびた！」, 「やけどを おった！」, 「こおりついた！」, 「まひして わざが でにくくなった！」
   - Ability-caused status: 「○○の △△で ××は ～」
   - Confusion and love: 「こんらん した！」, 「メロメロに なった！」
2. **Battle buffers.**
   - Confirm `\\0F`, `\\10`, `\\11`, `\\13`, `\\14`, and `\\1A` as engine-defined names.
   - Hold `\\00` / `\\01` (B_BUFF1/2), `\\2A`, and `\\36` / `\\38` (team prefixes) as needs_context.
3. **Mission text.**
   - Titles have no spaces and are recorded as glossary candidates.
   - Descriptions end with an instruction in the 〜しよう！ form.
   - Objectives use 「○○ジムに ちょうせん しよう！」 and 「○○へ むかおう！」.
4. **Mission log labels:** つかまえた, みつけた, よんだ, もどる, すべて, クリア.
5. **FA segments.**
   - When Japanese word order needs to change, first try to keep each segment's key words inside that segment: postpose, split a clause at the boundary, or end a segment with 「〜ね。」.
   - If the result is still unnatural in formal speech, use `FA_SEGMENT_SEMANTIC_CONFLICT`.
6. **Recurring terms:** Raid Den text is 「この レイドの すあなは ～ かくしあなで みつかった。」. Braille = てんじの せきばん. HQ/base = アジト.
