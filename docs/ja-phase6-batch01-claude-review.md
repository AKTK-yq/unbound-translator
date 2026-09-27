# Japanese Phase 6B Batch 01: Claude review

This review covers only the 407 rows in `out/phase6/ja_phase6_batch01_for_claude.json`. Batch 02 and later were not
touched, and no code, glossary, ROM, or controlfix changes were made.

Rules followed:
- Kana only, with wakachigaki (spaces between phrases) in prose.
- Tokens are unchanged.
- Speakers are all unknown, so no first-person pronouns and no character voice were added.

Output files:
- `tests/fixtures/ja_phase6_batch01_claude_review.json` (407 rows)
- `tests/fixtures/ja_phase6_batch01_glossary_candidates.json` (24 terms)

## 1–6. Counts

| Item | Count |
|---|---:|
| reviewed | 407 |
| confirmed | 401 |
| existing_official | 0 (no deterministic values in the input) |
| existing_glossary | 0 |
| needs_context | 6 |
| needs_technical_fit | 0 |

`translation_risk`: low 270 / medium 129 / high 8.

## 7–11. By category and kind

| Category | Count |
|---|---:|
| scripts | 404 |
| plain_scripts | 3 |

- **Story and NPC text:** 407 rows. These are the three plain_scripts intro narrations, trainer battle lines, townspeople, gym guides, Trainer House, and facility NPCs (Move Deleter, Evolution House, Inverse Battle House, Mission HQ).
- **Battle messages:** 0 rows. Trainer challenge and defeat lines are NPC text, so they are counted under story.
- **Mission category:** 0 rows. The Mission HQ explanations (#397–406) are NPC text.
- **UI-like choice labels inside scripts:** 15 rows (#213, #230–232, #255–257, #260–261, #271–274, and others).

## 12. Glossary candidates (24)

| Kind | Candidates |
|---|---|
| Places | くらやみのもり, ぶきみなもり, だいさばく, ボイドいせき, マグノリアタウン, ポルダータウン, ひがしボーリウス, アンティシスシティ, アンティシスのみなと, フォールショアマーケット, フォールショアジム, さかさバトルハウス, しんかハウス, ミッションほんぶ, トレーナーハウス, デュープの じてんしゃや, ソイル |
| Items and features | フォールバッジ, スーパーキューブ, リンクストーン, ドリームミスト, さかさバトル |
| Other | つりにいちゃん (a descriptor label), ボーリウスの しゅごしゃ |

Rows that contain these names are translated with provisional spellings, and their `translation_risk` is medium or higher.

## 13. Holds involving speakers

No row is held because of the speaker.
- Every row with a name label (Marlon, Ivory, Jax, Krook, and so on) keeps the tone within what the original text says.
- Elderly speech was kept only where the text itself shows it (the older couple in #296–304, the "Youngin'" line in #36).
- Stereotyped sentence endings (わ, じゃ, わし) and invented first-person pronouns were removed.

## 14. Holds involving buffers (6 needs_context)

| Entry | Reason |
|---|---|
| scr_1F01267, scr_1F012BD, scr_1F016AD | `[buffer2]` is probably son/daughter (a gendered English fragment), but its producer is unproven. Same as Phase 5 scr_7527C2 |
| scr_1F02458 | `[buffer3]` is a form of address; its content and producer are unproven |
| scr_1F01914 | `\\07` / `\\08` appear to add the English plural "s". Japanese doesn't need them, but tokens cannot be removed |
| scr_1F0618A | `\\0C` appears to be an English evolution-condition sentence built by the engine |

**Confirmed from sentence structure** (the buffer is clearly a Pokémon name, count, box name, or player name): #156, #193, #194, #198, #234–238, #242, #262, #290, #316, #349, #380–386, #401, #402, and others.

## 15. Technical fit concerns (no needs_technical_fit applied)

- **Choice labels:** multichoice width for いちを かえる, てもちから えらぶ, ちいさなキノコ ぜんぶ, and similar.
- **Signposts:** the gaps between the arrow tokens `\al` `\ar` `\au` `\ad` and the place names (#8, #10, #11, #53).
- **Long texts:** scr_1F06C7F (733 bytes), scr_1F0591E, scr_1F03CBD, scr_1F00D23. Check page breaks and the three-line layout.
- **ASCII parentheses:** #181 uses `(オープニングと おなじ ないようです)`. Parentheses are not in the Japanese charmap, so the page has to switch to Latin.

## 16. Wording concerns

- **Unverified official names:** 56 rows use Pokémon, move, and item names from series memory (サボネア, かげうち, ダークボール, マグマブースター, and so on). The input has no `official_terms`, so PokeAPI verification is recommended.
- **Pun that doesn't carry over:** scr_1F033D5 plays on Epidimy and "epitome". It was kept as エピトミー, but the meaning is weak in Japanese (risk high).
- **Word order changes:** #182 (the kidnapper's note) and #266, #372 swap the text inside identically typed colour pairs to fit Japanese word order. The number and kinds of tokens are unchanged.

## 17. For Codex to check

- **Glossary matcher false positive:** scr_75C267 (the "Ace" in "Aerial Ace" matched the name term Ace=エース). Recorded in `review_warning`.
- **Buffer producers:** the 6 rows in section 14, plus `[buffer3]` in scr_74FB23 (confirmed with medium risk on the assumption that it is a name).
- **Script choice labels:** menu width and cursor behavior.
- **Money amounts:** "$550" and "$6600" keep the `$` symbol as in the source.

## 18. batch_style_notes (for Batch 02 onward)

1. **Trainer battle lines**
   - Challenge: 「〜で ○○に してやる！」
   - Defeat: 「〜を けされちゃった。」
   - Keep them short, and drop "my", e.g. 「ほのおタイプで まるこげに してやる！」.
2. **Endings when the speaker is unknown**
   - Default to neutral forms: 〜んだ / 〜よ / 〜ね / 〜だ.
   - Don't use わ, のよ, じゃ, or わし without evidence.
   - Rough, threatening, or rustic speech is allowed only when the English shows it (Youngin', roughnecks, Aye, threats).
3. **Name labels:** write them as 「なまえ: [color]本文」, with the approved glossary spelling for the name.
4. **Town signs:** 「まちの なまえ せつめい。」 on one line.
5. **Signposts:** 「ちめい [arrow] ちめい」.
6. **Counters and money:** Pokémon ひき, items こ, times かい, choices とおり. Keep `$` for money.
7. **Glossary spellings to reuse:**
   - Items: ナゾノクサのはっぱ (no space), わざマシン, わざマシンケース
   - Places: トレーナーハウス, さかさバトル
   - Save = レポートを かく, and the Trainer House rebattle notice as in #80 and #209.
8. **Facility wording:** Move Deleter = 「わざを わすれさせる もの」, used descriptively rather than as a title.
9. **Self-reference:** "This dude" becomes 「この にいちゃん」. It must not be linked to a specific NPC.
