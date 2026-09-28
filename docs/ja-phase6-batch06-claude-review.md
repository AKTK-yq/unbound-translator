# Phase 6B — Batch 06 Claude CLI review

Batch 06の翻訳レビューのみ。Phase 6通常翻訳バッチの最終分だが、final cleanupには進んでいない。controlfix、inject、ROM生成、PokeAPI実照合、glossary変更、Python変更、commit、pushは未実施。

## 入力と結果

| 項目 | 件数 |
| --- | ---: |
| reviewed total / `review_source=claude_cli` | 461 / 461 |
| non-FA / FA | 461 / 0 |
| FA controls / FA segments / multi-FA entries | 0 / 0 / 0 |
| `confirmed` | 214 |
| `existing_official` | 212 |
| `existing_glossary` | 29 |
| `needs_context` | 6 |
| `needs_technical_fit` | 0 |
| 確定訳が空欄のentry | 6 |
| FA semantic-confirmed / semantic conflict / context hold | 0 / 0 / 0 |
| official-name verification pending | 39 |
| glossary候補（提案のみ） | 25 |
| Battle / Menu-UI / Story-NPC / Mission | 0 / 17 / 0 / 0 |
| その他category | 444 |
| unknown buffer | 0 |
| control-boundary warning / unsupported glyph | 0 / 0 |
| `width_runtime_unverified` | 461 |

その他444件の内訳: `item_names` 58、`move_names` 58、`pokemon_names` 58、`item_descriptions` 46、`move_descriptions` 46、`ability_names` 32、`ability_descriptions` 28、`pokedex_descriptions` 25、`trainer_names` 23、`map_names` 22、`pokedex_species` 16、`trainer_classes` 12、`nature_names` 6、`type_names` 6、`habitat_names` 3、`move_learning` 3、`trade_messages` 2。Menu/UIは`menu_battle` 12、`menu_trainer_card` 5。

入力の241件は既存の決定的候補（PokeAPI `ja-hrkt` 213、承認済みglossary exact 28）。残る220件はClaude CLIが分割レビューした。決定的候補もClaude CLIが照合し、全461件の`review_source`を`claude_cli`とした。Codexは翻訳を生成せず、構造・出所・採用可否の監査を行った。分割中間ファイルは無視対象の`out/phase6/batch06_claude_chunks/`に置いた。

## 保留と名称

空欄保留6件は`needs_context`。`Smogon OU`は使用UIと表記確認待ち、`Grunt`は人名か役職か未確定、`Sea/Cave/Mountain Pokémon`の3件は対象分類の公式表記確認待ち。`Catching Charm`は入力のPokeAPI候補`ゆれないおまもり`と、承認済みglossary候補`ほかくのおまもり`が衝突しており、確定訳を採用していない。6件ともClaude候補を`candidate_japanese`に残し、`reviewed_japanese`は空欄にした。単なる幅未確認のみを理由に保留したentryは0。

公式名未照合の39件は`tests/fixtures/ja_phase6_batch06_official_name_review.json`に保存。うち38件は`official_name_verification_required`警告の暫定名、1件は前述の`Catching Charm`衝突。記憶だけに基づく`existing_official`判定は採用していない。初回Claudeレビューで`existing_official`とされた非決定的16件は、公式出典が入力にないため`confirmed`へ下げ、暫定名の警告とmedium以上のriskを付けた。`existing_official`の212件はすべて入力の`pokeapi-ja-hrkt`決定的候補と`official_terms`に由来する。PokeAPIへの新規照合は未実施。

新規glossary候補25件は`tests/fixtures/ja_phase6_batch06_glossary_candidates.json`にentry限定・未承認の提案として保存。内訳はtrainer class 8、item 7、人名5、feature等3、その他固有名詞1、地名1。Claude出力のglossary使用主張のうち41件は承認済み・scope適合の根拠がなく、訳文を変えずmetadataから除外した。`existing_glossary`の29件は入力の承認済みscopeに対応する。substring一致だけで承認済み扱いにしていない。`glossaries/ja.json`は不変。

## 制御境界・文字の検証

このバッチのsource境界controlはFE 254、FA 0、FB 0。採用した455件について、ROM由来の各text segmentを個別に対応付け、segment数・FEの種類/順番・各segmentのprotected semantic tokenを原文と比較した。FEを別の文節へ移す結合/分割や、訳文中への改行control追加は0。3件の図鑑説明はClaudeにFE境界を再提示してsegment単位で再レビューし、境界を保持した。1件のトレーナー連名はClaude再レビューでPCS対応の表記に修正した。保留6件は候補を注入可能な確定訳と扱わない。

| 検証 | 結果 |
| --- | --- |
| input ID・順序・集合 | 461一致、重複0、欠落0、余分0 |
| `original`・`category`・source controls | 461一致 |
| review source | 461件すべて`claude_cli` |
| FA input / 専用fixture | FA entry 0、空配列一致。追加・削除・移動0 |
| source/translated segment境界 | 採用455件で不一致0。保留6件は非採用 |
| protected token / control token | 採用455件で不一致0 |
| control-boundary warning | 0 |
| 漢字 | 採用訳0 |
| Japanese PCS charmap | 採用訳encode error 0 |
| unknown buffer推測 | 0 |
| memory-only official扱い / glossary scope違反 | 0 / 0 |
| JSON parse | 4 fixtureすべて成功 |

`width_runtime_unverified`は全461件に残した。これは翻訳レビューの警告であり、renderer幅・slot・ポインタ・runtime表示の適合を証明しない。controlfix、inject、mGBA検証は後工程。

## Phase 6 final cleanupへ残す分類

今回の6件の文脈/名称衝突と39件の公式名照合、25件のglossary承認を後で再訪する。過去バッチに残るunknown buffer、未完訳、FA semantic conflict、unsupported glyph、話者依存、pointer/widthなどの技術保留もfinal cleanupで再確認する。**今回はそれらを解決していない。**

成果物は全461件review、空のFA review、official-name review、glossary候補の4 fixtureと本報告のみ。元ROM、Pythonソース、過去バッチ、glossaryは変更していない。
