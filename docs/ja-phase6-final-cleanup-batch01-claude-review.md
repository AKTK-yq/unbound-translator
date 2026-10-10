# Phase 6C-4B — Final Cleanup Batch 01 Claude review

Batch 01（147件、すべて話者のないテキスト）の翻訳レビューだけを行った。Batch 02〜04には進んでいない。コード、ROM、glossary、既存の翻訳JSON、controlfix、injectorは変更していない。かなのみ、commit / pushなし。

成果物は `tests/fixtures/ja_phase6_cleanup_batch01_claude_review.json`（147件すべて）。作業前に出力パスが未作成であることを確認し、入力の `ja_phase6_cleanup_batch01_for_claude.json` と manifest は読み取りだけで使った。

## 入力検証

147件、重複0、欠落0。manifest のID順と一致。TRANSLATION 58、CONTEXT 89。レビューは全件 `review_source = claude_cli`（利用上限による未処理はない）。

## 結果

| 区分 | 件数 | confirmed | needs_context | needs_technical_fit |
|---|---:|---:|---:|---:|
| CLAUDE_TRANSLATION | 58 | 58 | 0 | 0 |
| CLAUDE_CONTEXT | 89 | 56 | 32 | 1 |
| **計** | **147** | **114** | **32** | **1** |

TRANSLATION 58件の内訳は、既存候補を採用15、修正37、候補なしで新規6。CONTEXT のうち confirmed 56件は、既存候補の採用9、修正13、新規35（#140の1件はneeds_technical_fit側）。修正の主な理由は、承認済みglossaryとの不一致（21件）、意味のずれ、画面に収まらない長さ、「ひらがなの語間」の整理。

## 文脈が解決した56件と、その証拠

89件を機械的にすべて保留にはしていない。解決した56件は、証拠をエントリごとに `context_resolution.evidence` に記録した。

| 種類 | 件数 | 証拠 |
|---|---:|---|
| 戦闘メッセージ（型が確定したバッファ） | 39 | pret/pokefirered の `battle_message.h` で、`\12` `\16` `\18` `\19` `\1B` `\20` `\21`（名前・アイテム名・とくせい名・リンク相手名）と、以前から型が確定している `\0F` `\10` `\11` `\13` `\14` `\1A` の定義を確認 |
| 承認済みglossary | 10 | Uproar=さわぐ（5件）、Taunt、Torment（メッセージ中の活用形）、Catching Charm、Grunt（トレーナー名表）など |
| 隣接entryの適用済み訳 | 24 | 並べ替えラベル（Most/Least/Amount/type など7件）は、同じ画面の `[buffer1]で…` と Type/Name の適用済み訳に合わせた。BRONZE/SILVER/GOLD との並びで COPPER、Right/Left、さんか（enter）も解決 |
| UI語の対 | 3 | Shift / Send Out など |
| 慣例 | 1 | 階数表示（5F）はASCIIのまま |

注意: pret の定義は Unbound ROM を直接追跡した証拠ではない。以前の型確定コードと同じ基準で拡張した。ここを厳しく見るなら、`\12` `\16` `\18` `\19` `\1B` `\20` `\21` を使った戦闘メッセージ（33件）が再確認の対象になる。

## 保留（needs_context 32件）

すべて未確定のバッファが原因で、推測していない。

- `\00`（BUFF1）: 28件。値の型が戦闘スクリプトごとに変わり、このentryの書き込み側が入力資料で証明されていない。
- `\2A`（ATK_PREFIX2）と `\28`（ATK_PREFIX1）: 各1件。英語の接頭辞文字列で、内容と文法を確定できない。
- `[buffer1]`: 3件（共通メニュー、リンク画面の `[buffer1]P LINK`、ショップの `In Bag:`）。書き込み側が不明。

必要な追加情報（各行の `context_resolution.missing`）は、バッファの書き込み側と値の集合。

## needs_technical_fit（1件）

`tbl_start_menu_labels_00001_A4E4E4`（Cube V3）: 承認済みglossaryの『キューブV3』は、固定・再配置不可のスロット8 byteに対し、ページ制御を含めて11 byteかかる。訳文は記録し、Codexの確認に回した。

## Pokémon公式名称

- 公式名として断定した語はない。承認済みglossaryの語だけを使った。
- `official_name_verification_required` を付けた6件:
  - Curse（`\0F cut its own HP and laid a Curse on…`）: glossaryでは未解決。普通の語『のろい』で表した。
  - HM=ひでんマシン: 適用済み訳の表記で、glossary未登録。
  - Qualot Berry=タポルのみ: 要人手確認（glossary上は context_scoped）。
  - Go-Goggles=ゴーゴーゴーグル、Graveler=ゴローン: 入力資料に検証済みの公式名がない。
- Day-Care=そだてや と Fresh Water=おいしいみず は、承認語に表記を合わせたが、glossaryのscopeが別entryに限られている。glossaryによる適用ではないと記録した（scopeの拡張を検討）。
- Ability（とくせい）とSpecial Attack（とくこう）の混同はない。能力値の種類を英語の文脈から推測した訳もない。

## glossary

- 承認済み語を33回使用（32エントリ）。承認語が文中から欠けたものは0。
- 新規統合した語の `global_replace` は false のまま。scope外への適用は0（検証済み）。
- Uproar（活用形で使うため語幹『さわ…』を許容）、Taunt、Torment は参照語として文型に合わせて使った。

## 制御と文字

- 制御の境界（Batch 01全体）: FE 124、FB 15、FA 4。レビュー済み（confirmed / needs_technical_fit）のうち FE 96、FB 12、FA 3。
- FA は4件。3件は ROM 由来のセグメントごとに訳し（`#21 Curse`、`#39`、`#56`）、1件（`\00` を含む）は文脈保留。FA の追加・削除・移動・結合・分割は0、`FA_SEGMENT_SEMANTIC_CONFLICT` も0。FA 行の `reviewed_japanese`（全体）は空のまま。`fa_layout_approval_required` を付けた。
- FE は行替えの制御として、数と順序を保った。2件で、バッファの位置が改行をまたぐ並びになったのを見つけたので、原文の順序（バッファ→FE→バッファ）に戻した。`CONTROL_BOUNDARY_REVIEW_REQUIRED` で保留した件は0。
- 制御トークンの列、protected token、制御の境界順序は、レビュー済み115件で不一致0。FD 87、FC 18 ほかも原文と同じ。
- 未対応文字0、漢字0。採用訳（レビュー済み115件）はすべて日本語PCSでエンコード可能。使えない記号は避けた（括弧は『/』、& は『と』）。『、』は使える。

## 幅

実機の幅は未確認のため、警告にとどめた。

- `width_runtime_unverified`: 86件。
- 説明文の静的な幅は、種類ごとの上限内（とくせい説明191px、わざ説明122px、アイテム・図鑑説明239px）。
- 戦闘メッセージ1件（`はたきおとした`、`\10の \16を…`）は、動的な名前を足す前でも静的に223pxで、物理幅222pxを1px超える。警告を付けた。
- 固定スロットの8件（アイテム名2、図鑑分類名、トレーナークラス2、トレーナー名2、Cube V3）のうち、7件は収まり、1件（Cube V3）が収まらない。

## 引き継ぎ

- 技術統合に渡せる候補: **114件**（confirmed）。ROMへの注入可能を意味しない。
- 未解決: 33件（needs_context 32、needs_technical_fit 1）。
- ポケモン図鑑の分類名は、ゲーム側が『ポケモン』を自動で付けるか未証明。Butterfly=ちょうちょ に警告を付けた。重複削除や語尾変更はしていない。

## Batch 02への注意

- 話者のある会話（PROVEN 12件、PLAUSIBLE 38件、UNKNOWN 372件）。PROVEN の口調profileは参考扱い。話者が不明な行にキャラ付けしない。
- バッファは Batch 01 と同じ方針。`\00` `\01` `\28` `\2A` `\36` `\38` と `[buffer1-3]` は証拠がなければ保留。
- 206件のFA行のうち残りは Batch 02〜04 にある。FA は ROM 由来のセグメントごとに訳し、語順で境界をまたがない。
- 承認済みglossaryの scope が entry 単位なので、同じ語でも別 entry では適用外になる（Day-Care、Fresh Water で発生）。
