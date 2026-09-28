# Phase 6B — Batch 05 Claude CLI review

Batch 05のみ。Batch 06未着手。翻訳レビューと技術保留の記録であり、controlfix・inject・ROM生成・glossary変更・PokeAPI実照合は未実施。

## 範囲と結果

| 項目 | 件数 |
| --- | ---: |
| reviewed total / review_source=`claude_cli` | 408 / 408 |
| non-FA / FA | 404 / 4 |
| FA controls / source segments | 4 / 12 |
| `confirmed` | 317 |
| `existing_official` | 0 |
| `existing_glossary` | 1 |
| `needs_context` | 71 |
| `needs_technical_fit` | 19 |
| FA semantic-confirmed / conflict / context hold | 0 / 1 / 3 |
| official-name verification pending | 67 entries |
| new glossary candidates, proposal only | 4 terms |
| battle / menu-UI | 189 / 219 |
| unknown-buffer warning | 68 entries |
| `width_runtime_unverified` | 408 entries |

Claude CLIが全408件の初回レビューを行った。出力のID・順序・トークンを照合して保存。幅のmGBA未確認だけでは保留にしていない。`runtime_unverified=true`と`width_runtime_unverified=true`を全件保持し、自然な訳文を幅合わせだけの略語に変更していない。話者は入力408件すべて `unknown`。近接IDや `conversation_id` から人物・一人称を補っていない。

Claude CLIの利用上限（Asia/Tokyo 1:00リセット）に達したため、PCSで使えない字形を含む残り6件の再依頼は未完。**別モデルによる補訳なし。** 当該6件はClaudeの不適合候補訳を採用せず、`needs_technical_fit`、空の `reviewed_japanese`、`unsupported_japanese_glyph` 警告にした。ID: `tbl_menu_link_controls_00000_41DF4C`, `tbl_menu_link_controls_00001_41DF6B`, `tbl_setting_names_00008_1F4DADB`, `tbl_menu_game_settings_00010_1F4DD41`, `tbl_menu_game_settings_00011_1F4DD4E`, `tbl_menu_game_settings_00012_1F4DD5F`。別の6件はClaude CLIへの再依頼でPCS適合表現に修正済み。技術保留の追加・候補訳不採用はCodex監査であり、新しい翻訳をCodexが作ったものではない。`review_source` は初回レビューの出所を表す。

## FAとbuffer

FAの4件はROM由来の3 segmentをそれぞれ維持。FA追加0、削除0、移動0、segment結合0、分割0、境界跨ぎ0。`source_control_structure`と各 `after_control` を独立fixtureに保存。本文の自由結合なし。`tbl_battle_messages_00122_3FC048` は既存境界で自然な語順が成立しないため `FA_SEGMENT_SEMANTIC_CONFLICT` / `needs_technical_fit`。残り3件は `\\19`・`\\00` などの意味が確定せず `needs_context`。FA semantic-confirmed 0。全4件 `FA_LAYOUT_APPROVAL_REQUIRED`、訳segmentは空。最終FA再構築はCodexの後工程で行う。

Battle bufferの安全リストはstyle handoffの `\\0F`, `\\10`, `\\11`, `\\13`, `\\14`, `\\1A`。`[player]` と `[rival]` は別途既知。これ以外のbattle buffer、書き手未確認のfield `[buffer1]` は意味・値域を推測しない。該当68件は `unknown_buffer` を記録し、うちClaudeが作った35件の候補訳はCodexの技術監査で不採用、`needs_context`へ移した。初回Claude出力をそのまま無条件に「confirmed」としたものは残していない。

## 名称・glossary・文体

入力の `official_terms` は空。名称を記憶だけで公式扱いしない。67件の `official_name_verification_required` は `tests/fixtures/ja_phase6_batch05_official_name_review.json` に列挙し、英語ROM名表との完全な語境界一致は候補としてのみ記録した（50件に表候補、17件は個別同定待ち）。PokeAPI実照合は次工程。該当訳のriskは `medium` 以上。

新規候補は `SPA`, `Cube V3`, `Semi-Shift`, `Capped Exp. Share` の4語。`tests/fixtures/ja_phase6_batch05_glossary_candidates.json` にscope・確度・対象IDを記録。既に承認済みの `Cube` は新候補から除外した。`Options` は既存glossaryの `settings_ui` scopeのみ、`DexNav` は入力で許された既存項目のみ使用。substringだけで用語を適用していない。glossary本体は不変。

Battle 189件はGen 3風の簡潔さ、メニュー219件は自然な短い表記を優先。`ナゾノクサのはっぱ`、`わざマシン`、`レポートを かく`、匹/個/回の既存方針は文脈が合う範囲で維持。`$`、保護トークン、button・色・FC制御は翻訳しない。漢字なし。ASCIIやカタカナを自然な語に使用。`L=A` は原文通りのLatinラベルとして保持し、`latin_page_required` を記録。

## 品質監査

| 検証 | 結果 |
| --- | --- |
| Batch 05選定とのID集合 | 408一致。重複0、余分0、欠落0。 |
| `original`・`category`・source controls | 408一致。 |
| FA input ID・segment数 | 4一致、各3 segment。FA計4。 |
| 保護semantic/control token | 採用した331件の非空訳で不一致0。保留の空訳は適用対象外。 |
| FE/FA/FB | source metadataを408件保持。FA境界4件一致。review段階で改行・ページを再構築せず、controlfixも未実施。 |
| 漢字 | 採用訳0。 |
| Japanese PCS charmap | 採用訳のencode error 0。`L=A` はLatin pageとして検証。 |
| unknown buffer推測 | 68件を保留。未証明の値・文法の採用0。 |
| official名記憶だけの確定 | 0。 |
| glossary scope違反 | 0。 |
| JSON parse | 4 fixtureすべて成功。 |

`tests/fixtures/ja_phase6_batch05_claude_review.json` に全408件、`ja_phase6_batch05_fa_claude_review.json` にFA全4件を保存。前者は原文、会話/scene ID、話者注記、警告、source controls、技術保留理由を保持。未検証の訳を注入可能とみなさない。

## Batch 06への文体メモ（作業は未着手）

自然なかな・適度なわかちがき。幅の実機未確認だけでは翻訳を止めず警告にする。未知buffer、FA意味衝突、構造化UI、固定slot/no_relocation、制御・pointer不明は引き続き技術保留。公式名は入力で確認済みのものだけ確定扱い。FAはsegment単位の文を先に作り、境界移動をしない。

作成した追跡対象ファイルは上記4 fixtureと本報告のみ。Claude CLIへの分割入力・中間出力は無視対象の `out/phase6/batch05_claude_chunks/` に保存。Pythonソース、ROM、glossary、renderer、controlfix/inject結果は変更していない。commit・pushなし。
