# Japanese Phase 5B: Claude translation review

Phase 5B covers only the translation-quality work (wording, tone, terminology, and context) for the 750 entries that
Phase 5A selected. It includes no code changes, ROM analysis, controlfix, injection, ROM/BPS build, font, or ASM work.
Technical safety is left to the Codex validation that follows.

- Input: `out/ja_phase5_for_claude.json` (750 rows), `tests/fixtures/ja_phase5_selection.json`, `glossaries/ja.json`
- Output: `tests/fixtures/ja_phase5_claude_review.json` (750 rows), `tests/fixtures/ja_phase5_glossary_review.json` (78 candidates)
- Policy: kana only (no kanji). Normal prose uses wakachigaki (spaces between phrases). Names, menu items, labels, and short headings take no spaces. Save=レポート, Options=せってい.

The `reviewed_japanese` field uses the real token form (such as `[buffer1]` and `\\0F`), not the Phase 5A placeholders. For `needs_context` rows, `reviewed_japanese` is `null` and any candidate wording is stored separately in `candidate_japanese`.

## 1–4. Status counts

| status | Count | Meaning |
|---|---:|---|
| confirmed | 512 | Wording is final. This includes 56 Phase 4 entries and 1 glossary entry (Borrius). 78 of these use provisional proper-noun spellings |
| existing_official | 106 | PokeAPI `ja-hrkt` official names. Not retranslated |
| needs_context | 116 | Not finalized. Includes the 3 Phase 4 entries left unresolved (their approved values are unchanged) |
| needs_technical_fit | 16 | The natural wording overflows the fixed-slot estimate, or its layout spacing needs checking |
| **Total** | **750** | |

`translation_risk`: low 391 / medium 236 / high 123.

## 5. Status counts by category

| category | confirmed | existing_official | needs_context | needs_technical_fit |
|---|---:|---:|---:|---:|
| scripts | 181 | | 49 | |
| battle_messages | 46 | | 7 | 2 |
| menu_* (all) | 164 | | 2 | 9 |
| mission_names / log / objectives / descriptions | 41 | | 19 | |
| map_names | 2 | | 9 | |
| descriptions (move/item/ability/pokedex) | 27 | 1 | | |
| pokemon/move/item/ability/nature/type names | 9 | 102 | | 2 |
| pokedex_species | 3 | 3 | | 1 |
| plain_scripts / pointer_texts | 12 | | 2 | |
| trainer_names / trainer_classes | | | 9 | 1 |
| day_names / gendered_dialogue_fragments / pokedex_form_names / credits_text | | | 18 | |
| setting_names / start_menu_labels / trade / move_learning / habitat | 27 | | 1 | 1 |

Per-category detail can be aggregated from the `category` and `status` fields of `ja_phase5_claude_review.json`.

## 6. Glossary candidates

`ja_phase5_glossary_review.json` holds 78 candidates: the 23 from Phase 5A plus 55 found during translation. None has been confirmed against official Japanese; every row has `official_confirmed: false`. None was added to `glossaries/ja.json`.

- **Phase 5A place names (9):** ベリンタウン, クレータータウン, ドレスコタウン, フローズンハイツ, テールタウン, ブリザードシティ, フォールショアシティ, エピディミータウン, ターミガンタウン
- **Phase 5A mission names (14):** きょうふのグランブル, おわらないあくむ, やどなしに すみかを, するどすぎる はな, きせつの ちょうさ, はかあらし, アンティシスの たたかい, くうかんの さけめ, あばれエレキブル, ぶっつけほんばん, サメの えさ, くうふくの いたみ, ブラックエンブオー, あやしい ふとう
- **New people (11):** ジャックス, マーロン, ゼフ, アイボリー, アクラブ, ログはかせ／ログ, ベガ (ヴ is not in the charmap), アーサー, アロス, クルック
- **New organizations (5):** シャドウズ, ブラックナットレイ, はめつのひかり, ふじみのルカリオ, ジュエルファミリー
- **New places (13):** ビビルタウン, ビビルのもり, つららのどうくつ, たにまのどうくつ, シンダーかざん, サンダーキャップやま, KBTハイウェイ, SESハイウェイ, クリスタルピーク, フラワーパラダイス, シーポートシティ, チャレンジロード, デハラゲームコーナー
- **New features, items, and modes (26):**
  - Features: キューブ, キューブスペース, クラウドバースト, マイニングスキャン, サンドボックスモード, ニューゲーム+ (`\+`), ランダマイザー, リバランスばん, レベルじょうげん, ライトばん/ダークばん, いしょうボックス, パートナーいちらん
  - Items: ダークネスバッジ, ナゾノクサの はっぱ, ステータススキャナー, ポータブルPC, タイムターナー, ベビーモニター, トレーナーカタログ, ほかくのおまもり, フロンティアカード
  - Difficulty modes: バニラ, むずかしい, エキスパート, インセイン, かんたん

Descriptive place names (Icicle Cave, Valley Cave) were translated into Japanese. Coined names (Vivill, Dresco, Bellin) were written in katakana. Whether to keep this split is a decision for the glossary approver.

## 7. Speaker and tone concerns

- Every row has `speaker: unknown`. First-person pronouns (ぼく, おれ, わたし, わし) were added **nowhere**. Where the English has "I", "my", or "mine", Japanese omits the subject naturally.
- Tone that matches the speaker was used only for lines whose speaker is identified in the text by a name label or self-introduction: Zeph, Arthur, Jax, Marlon, Ivory, the Grunt, [rival], Log, the father and daughter, and Véga.
  - Zeph and Marlon use われわれ, which corresponds to the English "we/our".
- [rival] changes with the player's choice, so their lines avoid endings that strongly signal gender (ぞ, だぜ).
- Tone differences in the English were kept, not smoothed out:
  - A villain's parting shot (scr_7505FA)
  - A rural accent (scr_746093)
  - Stoner humor (scr_753107, scr_746471)
  - Sarcasm (scr_74E1A0, scr_74BCAD)
  - A guardian's domineering speech (scr_74FC26)
  - Mission-text jokes (communism, capitalism, trash)
- Speaker guessed from context but not confirmed: scr_7418A6 (probably Véga), scr_74B022 (probably Zeph), scr_750560, scr_75CA45 (companion).
- Four lines depend on gendered buffers and stay needs_context: scr_74AE91, scr_7527C2, scr_753107, and the five gendered_dialogue_fragments.

## 8. UI wording concerns

- Official FRLG UI terms were preferred:
  - Menus and actions: やめる, もたせる, あずかる, あずける, つれていく, ならびかえ, つよさをみる, ずかん, とじる
  - Options: しあいのルール, せんとうアニメ, いれかえ/かちぬき, ウインドウ, みる
- `tbl_menu_options_00010` (On → みる) assumes FRLG option-table order, where index 10 is Battle Scene ON. Confirm this.
- Layout spacing: the space in Yes/No (`menu_battle_00002`) and the column-alignment spaces in the battle menus (`00000`, `A4C7B7`) may not line up once kana width is applied. Marked needs_technical_fit.
- Mission Log A-Z sorting stops meaning anything once names are in kana (`tbl_mission_log_00001`, needs_context).
- The day abbreviations (Sun–Thu) become ambiguous in kana: a single か could be almost anything. Decide whether to keep ASCII.
- Setting names (かんたんひでん, レポートかくにん, こうそくメッセージ, and so on) are provisional feature names. Check them against the actual settings screen.

## 9. Mission wording concerns

- Glossary terms applied throughout: Missions=ミッション, reward=ごほうび, Active=しんこうちゅう. The opposite of Active, Inactive, was set to みちゃくしゅ.
- Three descriptions that contain "Black [player]" (scr_1F9FBCD, scr_1F9EAF1, scr_1F9F08F) are needs_context. It is unclear whether the `[player]` token there is the player's name or the gang-name buffer.
- Some wordplay could not survive translation:
  - scr_1F016FD: "saving lives" / "saving the game", made incompatible by the Save=レポート rule.
  - scr_7E842C: "adore the ores".
  - The meaning was kept and each case is noted in its `reason`.
- All 14 candidate mission names are needs_context. Titles built on puns or metaphors (Wingin' It, Shark Bait, Odd Odd Docks) also need a decision on how freely to translate.

## 10. Battle wording concerns

- Standard messages follow the official Japanese patterns: level up, learning a move, forgetting a move, fainting, status effects, blacking out, and trainer recall (○○は ○○を ひっこめた！).
- In battle strings, `[player]` is FD 01 (B_BUFF2: a number or move name) and `[rival]` is FD 06 (opposing Pokémon 1's name). This is recorded in `speaker_notes`.
- needs_context: CFRU multi-target buffers (`\\3D`) and team prefixes (`\\36`, `\\38`) probably insert English prefixes such as "your" or "the opposing", so the Japanese word order cannot be fixed.
- needs_context: `\\00 gained[player]`, where the English inserts " a boosted" through a buffer.
- needs_context: tbl_battle_messages_00004_A4A9A2, where the colour controls wrap only the words "A critical hit".
- Not yet checked against official wording: the phrasing of the Healing Wish and Lunar Dance messages, and frostbite (しもやけ) when it is inserted into a sentence.

## 11. High length-risk entries

**needs_technical_fit (16):**

| Kind | Entries |
|---|---|
| Fixed slots | tbl_menu_shop_00003, tbl_menu_standalone_labels_00000, tbl_menu_cube_00000/00002, tbl_battle_messages_00023_3FB4BE (91/57), tbl_battle_messages_00000_9678F0, tbl_menu_saving_messages_00003, tbl_pokedex_species_00005, tbl_start_menu_labels_00001, tbl_type_names_00013/00014, tbl_trainer_classes_00001 |
| Layout | tbl_menu_battle_00000/00002/A4C7B7, tbl_menu_trainer_card_00009 |

- Estimates count the page switches at both ends (`[japanese]` … `[latin]`) plus the terminator, so there are about 4–5 bytes of fixed overhead.
- Very short fixed slots such as type names (7 bytes) overflow **even with the official names**. That is a structural problem in how the pages are switched, not a wording problem.
- `review_warning` is set on 9 official type names and 3 pokedex_species rows.
- The longest texts get many page breaks after wakachigaki. They are all relocatable:

| Entry | Content | Slot (bytes) |
|---|---|---:|
| scr_1F0F004 | New Game+ explanation | 1442 |
| scr_1F10A07 | Sandbox explanation | 955 |
| scr_74AE91 | | 401 |
| scr_75D44B / scr_75D5FC | | |

## 12. Entries for Codex to investigate

- **Untokenized raw bytes and suspected legacy data:**
  - scr_7A95BA (leading `Ñ `)
  - scr_750C28 (leading `Á 9999999999999`)
  - scr_1080302 (garbage)
  - tbl_menu_game_settings_00000_1F4E274 (starts mid-string at `RNING!`)
- **Buffer contents to identify:**
  - Gendered fragments (He/her/him/boy/SON) and the sentences that receive them
  - `[buffer1]` in scr_1F1A99A, scr_75CDB8, scr_74AE91, scr_7527C2, scr_753107
  - Sort keys in `tbl_menu_cube_system_00011/00012`
- **Option labels** that must match: Exp. Gain / Capped Share (scr_1F1057C), and the full set of difficulty mode names.
- **Glyphs:** whether the `\pk\mn` PKMN glyphs render in the Japanese font (tbl_trainer_classes_00001).
- **Characters outside the Japanese charmap:** `L=A` needs the Latin page for "=". The parentheses in scr_75CDB8 are in the original. The long texts were rewritten to avoid ")" and "%".
- **Possible "〜ポケモン ポケモン" duplication** in pokedex_species. The approved value "たねポケモン" may be doubled if the engine appends "Pokémon".
- **Phase 4 carry-over:** the 3 Phase 4 needs_context entries have approved values in the input data. In particular, scr_1F10323 leaves Vanilla/Difficult in English in the body text. Status stays needs_context and the values were not changed.
- **Unverified official text:** 6 Pokédex descriptions and 3 species names that PokeAPI did not verify. The official Japanese should be fetched and swapped in.

## 13. Overall terminology variation (unified)

| Concept | Japanese used |
|---|---|
| Save (in game) | レポート (a real save file is セーブファイル) |
| Options / Option | せってい (settings names: きほんせってい, サウンドせってい) |
| WARNING / NOTE | けいこく！ / ちゅうい！ |
| Cancel / Exit / QUIT / See Ya! | やめる (the pause-menu Exit is とじる) |
| PC | パソコン (Pokémon Storage System = ポケモン あずかりシステム) |
| Mart | フレンドリィショップ |
| HM / TM | ひでんマシン / わざマシン |
| EVs / IVs | どりょくち / こたいち |
| Gem | ジュエル |
| Terrain | フィールド (the battle-location sense only is written as おくないで たたかう とき) |
| Route N | Nばんどうろ |
| enable / disable | ゆうこうに する / むこうに する |
| Counters | ひき/ぴき/びき (Pokémon), こ (items), かい (times) |

Unresolved variation: the full set of difficulty mode names (Vanilla/Difficult/Expert/Insane/Easy, and the puzzle levels Default/Hard/Challenging), and the lighter/darker story version names.

## 14. Handoff to Phase 5B technical validation

1. Before controlfix, turn the `reviewed_japanese` of the 512 confirmed and 16 needs_technical_fit rows into translation input. The 116 needs_context rows keep their current values (English, or the approved value).
2. After glossary approval, bulk-replace the provisional proper nouns in the 78 confirmed rows that use them (see `new_glossary_candidates`).
3. After running controlfix twice, check the fixed-slot, `no_relocation`, and pixel-width audits in the order of section 11.
4. Verify the section 12 items (buffer contents, raw bytes, glyphs, option-table order) against the runtime subset in mGBA.
5. `review_warning` rows (15): 9 type names, 3 species names, and the 3 Phase 4 carry-over entries. Existing official values were not changed.
