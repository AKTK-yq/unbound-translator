# Japanese Phase 5C: Claude context re-review

Scope: re-review of the 116 Phase 5B `needs_context` rows, using Codex's Phase 5C context evidence. Translation, tone,
and terminology only. No code, ROM, controlfix, injection, pointer, or glossary changes were made.

- Inputs: `out/ja-phase5c-needs-context-for-claude.json`, `out/ja-phase5c-difficulty-audit.json`, `docs/ja-phase5c-handoff.md`,
  Phase 5B review/glossary files, `glossaries/ja.json`.
- Outputs: `tests/fixtures/ja_phase5c_claude_review.json` (116 rows) and `tests/fixtures/ja_phase5c_difficulty_review.json` (30 rows).
- Rules followed: kana only, wakachigaki in prose, tokens unchanged. Rows still held have `reviewed_japanese: null`; any
  candidate is in `candidate_japanese`.

## 1–4. Counts

| Item | Count |
|---|---:|
| Reviewed | 116 |
| Resolved to confirmed | 20 |
| Still needs_context | 96 |
| needs_technical_fit | 0 (`エキスパート` and `インセイン` need relocation, but that is a relocation decision for Codex, not a wording shortening) |

## 5. Difficulty naming decision (glossary_candidate, not added to glossary)

| English | Proposed | Confidence | Reason |
|---|---|---|---|
| Battle Difficulty | バトルのむずかしさ | high | Built from difficulty=むずかしさ (glossary). Pairs with なぞときのむずかしさ |
| Puzzle Difficulty | なぞときのむずかしさ | high | Built from puzzle=なぞとき (glossary) |
| Vanilla | バニラ | medium | Means the unmodified original balance. Kept as a name, the common modding term |
| Difficult | ハード | medium | むずかしい can't be told apart from the adjective and doubles up as むずかしいの むずかしさ. ハード is the familiar game term |
| Expert | エキスパート | medium | Natural as a katakana name |
| Insane | インセイン | medium | Used for top difficulties in Japanese editions of Western games. The same string is shared with the Safari Zone |
| Easy (puzzle/Safari) | イージー | medium | Matches the katakana battle names |
| Challenging (puzzle) | チャレンジ | medium | Avoids clashing with ハード. Familiar as a game term |
| Hard (Safari) | ハード | medium | Same word as battle Difficult, but a different menu, so no clash |
| Medium (Safari, out of scope) | ノーマル (suggestion only) | low | Not in any row, so not translated |

Alternatives considered:
- A Japanese-word ladder: ふつう, むずかしい, すごく むずかしい, げきむず. Rejected: ふつう loses the "original balance" meaning of Vanilla, むずかしい clashes with the adjective, and げきむず is slang.
- Making every name katakana has two benefits:
  - The four levels stay distinct at a glance.
  - A name stands out as a mode name in body text without 「」, which the charmap lacks.

Default (scr_1F10619) was assumed to be a difficulty in Phase 5B. Nearby text shows it is actually the default choice in the battle music/background list, so it was translated as デフォルト.

The four battle explanations keep their different meanings:
- **Difficult:** for players with moderate battle experience, no EV/IV worries, but plan before fights.
- **Expert:** assumes a fully EV-trained team, so team swaps between important battles are probably unnecessary.
- **Expert recommendation:** EV training not needed early, but required later, along with strategy.
- **Insane:** near impossible, unfair and tedious by design, expect many losses, all on the player's own head.

No Vanilla explanation exists in the data, so none was invented.

The Options help texts, which are outside the Phase 5 selection:
- The battle difficulty for all battles. → すべての バトルに かかる むずかしさです。
- The difficulty of overworld puzzles. → マップで とく なぞときの むずかしさです。

## 6. Difficulty-reduction warning (complete entry)

Corrected ID `tbl_menu_game_settings_00000_1F4E26F`: ROM `0x01F4E26F` / GBA `0x09F4E26F`, 185 bytes, owner `0x01EBD7FC`.
Translated fresh from the complete English source.

```
[red]けいこく！[black] バトルの むずかしさを いちど さげると ゲームクリアまで ハードより うえには あげられません！ ほんとうに バトルの むずかしさを さげますか？
```

The limit differs from branch B (`…00001_1F4E328`, confirmed in Phase 5B, "あげなおせません"):
- Branch A says the difficulty cannot go above Difficult (ハード).
- Branch B says it can never be raised again.

The old clipped `tbl_menu_game_settings_00000_1F4E274` stays needs_context and is marked do-not-translate.

## 7. Buffers resolved: 5

| Entry | [buffer] content | Result |
|---|---|---|
| scr_1F10323 | Selected mode name | Confirmed |
| tbl_mission_log_00017_1F560DA | Location name | Confirmed. Same as the approved value |
| scr_1F9FBCD, scr_1F9EAF1, scr_1F9F08F | "Black [player]" is a gang name built from the player's name | Confirmed as ブラック[player] |

Still unresolved: scr_74AE91, scr_7527C2, scr_753107, scr_1F1A99A, scr_75CDB8, tbl_battle_messages_00001_3FB265, and the team/multi-target battle buffers.

## 8. Speakers resolved: 1

scr_74AE91 is confirmed as Zeph. The line still stays needs_context because its [buffer1] is unresolved.

Newly identified as a descriptive label rather than a person's name: scr_1FACB9D, now confirmed as オタク.

No first-person pronouns were added.

## 9. Glossary candidates

- **New:** `Black [player]` → ブラック[player], plus the difficulty set in §5.
- **Improved (still unapproved):**
  - Tomb Raider → トゥームレイダー
  - Wingin' It → つばさ おひろめ
  - Pangs of Hunger → しょくよくふしん
  - Odd Odd Docks → ナゾナゾふとう (keeps the Oddish pun)
- **Unchanged:** the other names, places, and mission titles stay held pending glossary approval.

## 10–12. Wording concerns

- **UI:**
  - えらべるパートナー comes from nearby text only (raid partner selection).
  - The day abbreviations still have no owner and remain held.
  - The Mission Log A-Z sort behavior is unknown.
  - The Exp. Gain / Capped Share option labels must match the Options screen.
- **Battle:**
  - \\36/\\38 team prefixes and \\3D multi-target prefixes are held; they probably insert English words.
  - The critical-hit colour wrapper is held.
  - The boosted-Exp buffer is held.
- **Mission:** the three "Black [player]" descriptions are confirmed. All mission titles remain glossary candidates.

## 13. Still for Codex

- **Byte audits:** the leading-byte prefixes of scr_7A95BA and scr_750C28.
- **Suspected non-text:** scr_1080302.
- **Buffer producers:** scr_74AE91 and the gendered fragments he/her/him/boy/SON (which sentences receive them), scr_7527C2 (son/daughter?), scr_753107, scr_1F1A99A (on/off?), scr_75CDB8.
- **No owners found:** the five trainer_names rows, the five day_names rows, and the form names.
- **Visual check:** scr_1F0F842, which body part "trim" colours.
- **Migration:** use `tbl_menu_game_settings_00000_1F4E26F` only.

## 14. Technical-fit follow-ups (Codex)

- **Relocation:** エキスパート and インセイン need relocation (slot 7). Add the missing `bufferstring` owners (`0x01E6FCEB`, `0x01E6FD0E`) before relocating any mode literal.
- **Width:** measure the Options choice field and the NEW GAME multichoice (x=19 tiles) in mGBA.
- **Out-of-selection strings:** the label and help strings from §5 have to be added to the translation input before they can be injected.
