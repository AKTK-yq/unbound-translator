# Japanese Phase 5D: glossary review

Phase 5D decides the notation this Japanese project adopts for the glossary candidates held in Phase 5B and 5C. It does
not change `glossaries/ja.json`, code, or the ROM. The adoption proposal is in `tests/fixtures/ja_phase5d_glossary_patch.json`.

- Review: `tests/fixtures/ja_phase5d_glossary_review.json` (122 terms)
- Patch proposal: `tests/fixtures/ja_phase5d_glossary_patch.json` (114 terms: `project_standard` only; `unresolved` excluded)
- Re-check of the held entries: `out/ja-phase5d-needs-context-recheck.json` (96 entries)

## Status definitions

| status | Meaning | Count |
|---|---|---:|
| official | Official Japanese confirmed from the input materials | **0** |
| project_standard | Notation this project adopts. Unbound-specific terms, and series-standard terms not confirmed in the inputs | **114** |
| unresolved | Not adopted yet (meaning or usage unclear) | **8** |

Terms such as したっぱ, けんきゅういん, おまわりさん, ずかんナビ, and ○ばんどうろ are in established series use. None was confirmed as official from the inputs, so all are project_standard. Official names from PokeAPI (Pokémon, moves, items, and so on) are outside this review, so the official count is 0.

## 1–4. Totals

Reviewed 122 terms: 114 project_standard, 8 unresolved, 0 official.

- The 78 Phase 5 candidates are all included. Two were restructured: `New Game +` is now `New Game \+`, and `lighter/darker version` was split into two terms.
- 35 terms are new in Phase 5D.

## 5. People (28)

- **project_standard (27):**
  - ジャックス, マーロン, ゼフ, アイボリー, アクラブ, ログはかせ, ログ, ベガ, アーサー, アロス, クルック
  - テッシー, アリス, メル, ミルスクル, ギャラバン, ビッグモー, ジェームズ, ベンジャミン, エルドン, ジガルディア, ジグフリード, フレッド, マイロ, フランシス, フレシア, エース
- **unresolved (1):** Gruff. It is unclear whether this is a name or a descriptor.
- **Rules:** no ヴ (Véga becomes ベガ, Aklove becomes アクラブ). Prof. is はかせ. Zygardia and Zygfried both start with ジ, echoing ジガルデ.
- **NPC label:** Nerd = オタク (a descriptor label, not a name).

## 6. Places (24)

- **Towns and cities:** ○○タウン / ○○シティ.
  - ベリンタウン, クレータータウン, ドレスコタウン, テルタウン (changed from Phase 5B's テール), エピディミータウン, ターミガンタウン
  - ブリザードシティ, フォールショアシティ, シーポートシティ, ビビルタウン
- **Descriptive names translated for meaning:** つららのどうくつ, たにまのどうくつ, ビビルのもり
- **Mixed style:** シンダーかざん, サンダーキャップやま
- **Katakana:** フローズンハイツ, クリスタルピーク, フラワーパラダイス, チャレンジロード
- **Abbreviation kept:** KBTハイウェイ, SESハイウェイ
- **Other:** デハラゲームコーナー, アンティシス (new), Route [N] = [N]ばんどうろ (template)

## 7. Mission titles (14, all project_standard)

Titles are headings, so they have no spaces.

| English | Adopted | Note |
|---|---|---|
| The Terror Granbull | きょうふのグランブル | |
| The Endless Nightmare | おわらないあくむ | |
| Home for a Hobo | やどなしにすみかを | |
| Extreme Hyperosmia | スーパーきゅうかく | Changed. The katakana-hiragana break keeps it readable without spaces |
| Seasonal Research | きせつのちょうさ | |
| Tomb Raider | トゥームレイダー | Kept as a parody of the game title |
| The Battle of Antisis | アンティシスのたたかい | |
| A Rift in Space | くうかんのさけめ | |
| The Rogue Electivire | あばれエレキブル | |
| Wingin' It | はねをのばして | Changed. The idiom 羽を伸ばす keeps both the wings and the carefree sense |
| Shark Bait | サメのえさ | |
| Pangs of Hunger | しょくよくふしん | |
| Odd Odd Docks | ナゾナゾふとう | Keeps the Oddish pun |
| The West Borrius Pokédex | にしボーリウスずかん | |

The Black Emboar = ブラックエンブオー is counted as an organization (organization and mission-title scope).

## 8. Trainer classes (6)

- **Unbound-specific:**
  - Light of Ruin Leader = はめつのひかりリーダー (spaces removed; the doubled の avoided)
  - Terror Granbull = きょうふのグランブル
  - Black Ferrothorn Boss = ブラックナットレイのボス
  - Black Ferrothorn = ブラックナットレイ, recorded as an organization that is also a trainer class
- **Series-standard (project_standard):** Grunt = したっぱ, Scientist = けんきゅういん, Officer = おまわりさん

## 9. Difficulty (10, all adopted as project_standard)

| English | Adopted | context_scope |
|---|---|---|
| Battle Difficulty | バトルのむずかしさ | options_setting_label |
| Puzzle Difficulty | なぞときのむずかしさ | options_setting_label |
| Vanilla | バニラ | battle_difficulty |
| Difficult | **ハード** | battle_difficulty |
| Expert | エキスパート | battle_difficulty |
| Insane | インセイン | battle_and_safari_difficulty |
| Easy | イージー | puzzle_and_safari_difficulty |
| Challenging | チャレンジ | puzzle_difficulty |
| Hard | **ハード** | safari_difficulty |
| Medium | ノーマル | safari_difficulty (no entry uses it yet) |

Difficult and Hard are both ハード, but they belong to different menus, so this is allowed. Neither is registered for global replacement: `global_replace: false`, with a review_warning on each.

## 10. Other terms

- **Organizations:**
  - シャドウズ: organization name only; plain "shadows" is not replaced
  - はめつのひかり, ふじみのルカリオ, ジュエルファミリー
- **Template:** Black [player] = ブラック[player] (`mission_gang_name_template`; the `[player]` token must stay)
- **Modes and features:**
  - Modes: サンドボックスモード, ニューゲーム\+ (the `\+` token is kept)
  - Features: ランダマイザー, リバランスばん, レベルじょうげん, ライトばん / ダークばん, いしょうボックス, マイニングスキャン, キューブ, キューブスペース, クラウドバースト, ずかんナビ
- **UI terms:** Default = デフォルト, Available Partners = えらべるパートナー, Mission Log = ミッションログ
- **Items (no spaces):** ダークネスバッジ, ナゾノクサのはっぱ, ステータススキャナー, ポータブルPC, タイムターナー, ベビーモニター, トレーナーカタログ, ほかくのおまもり, フロンティアカード
- **unresolved (7 besides Gruff):**
  - Exp. Gain and Capped Share: option labels that must match the Options screen
  - Form names High King, Unique Horn, Sphere, Djinn, Dancing: the Pokémon each form belongs to is unknown

## 11. Context-sensitive terms (37 with a non-global scope)

These must not be applied as simple global replacements. In the patch they are `global_replace: false`.

| Group | Terms |
|---|---|
| Needs particular care | Log (Mission Log collides), The Shadows (collides with the plain word), Cube (collides with the plain word), Difficult, Hard, Black [player] (template), Route [N] (template), New Game \+ (token) |
| Difficulty scopes | Battle Difficulty, Puzzle Difficulty, Vanilla, Expert, Insane, Easy, Challenging, Medium |
| Class and label scopes | Light of Ruin Leader, Terror Granbull, Black Ferrothorn Boss, Grunt, Scientist, Officer, Nerd, Gruff |
| Other scopes | Black Ferrothorn, The Black Emboar, lighter/darker version, Available Partners, Default, Exp. Gain, Capped Share, the 5 form names |

## 12. New candidates (35)

- **People and names:** Tessy through Ace (16 names), Gruff, Nerd
- **Places and templates:** Antisis, Route [N], Black [player]
- **Classes:** Grunt, Scientist, Officer
- **Features and UI:** darker version, Mission Log, Default, DexNav, Exp. Gain, Capped Share
- **Form names:** the 5 form names

All come from entries that are in the input data.

## 13–15. Re-check of the 96 held entries

| Item | Count |
|---|---:|
| **Ready for retranslation on glossary approval alone** | **52** |
| Not resolved by glossary alone | 44 |
| of which need Codex technical investigation | 36 |
| of which need context or visual confirmation only | 8 |

- **The 52 ready entries:**
  - 25 name labels (all except Gruff)
  - 9 place names
  - 14 mission titles
  - 4 trainer classes

  In every case the entry text is the term itself, so its `proposed_japanese` becomes final once the term is approved.
- **Codex technical investigation (36):**
  - Buffer producers: scr_74AE91, scr_7527C2, scr_753107, scr_1F1A99A, scr_75CDB8, and 7 battle rows
  - Leading-byte prefixes (2), suspected non-text (1), the old clipped warning (1)
  - Days of the week (5, no pointer owner), trainer_names (5, no pointer owner), gendered fragments (5, insertion sentences unknown)
  - Credits (3, encoded-length mismatch), the A-Z sort (1), option labels (1, scr_1F1057C)
- **Context or visual confirmation (8):** trim (scr_1F0F842), VICTORIES, Gruff, and the 5 form names.

## review_warning

- **ナゾノクサのはっぱ:** the adopted item name has no space, but the Phase 5B confirmed text in scr_746471 and scr_75318A writes it with a space as ナゾノクサの はっぱ. Decide whether to align them.
- **Log, The Shadows, Cube, Difficult, Hard:** risk of wrongly replacing plain English words. Scope restrictions are required.
- **Medium:** no entry uses it.
- **Existing glossary:** `Option(s)=せってい` is limited to the `menu_pause` category, but Phase 5B/5C also use せってい for "Options Menu" in body text. Widening the scope is recommended, though it was not changed here. No other conflicts with `glossaries/ja.json`.

## Verification

- 122 terms, no duplicate `source`.
- No kanji and no characters outside the charmap in any adopted notation; tokens are excluded from the check.
- No empty strings except the 8 unresolved terms.
- Every `affected_entry_ids` and `already_used_in_confirmed_ids` value exists in the Phase 5 ID set.
- All three JSON files parse.
