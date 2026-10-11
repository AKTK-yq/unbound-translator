# Phase 7C-2 — Story Priority Batch 01 Translation Review

Phase 7C-1の53件を、翻訳レビューのみ行った。ROM生成、既存Python・翻訳JSON・glossaryの変更、commit/pushはしていない。
confirmedは訳文の確定であり、ROM注入の承認ではない。ストーリー所属は全件 `MAIN_STORY_CANDIDATE / PROVISIONAL` のままで、`MAIN_STORY_VERIFIED` への昇格は0件。
runtime（mGBA）での確認はしていない。

基準ROM `out/unbound-ja-phase6-cleanup-batch04.gba` のSHA-256は期待値 `0d1d00e7b0f4f113514abbcf1907e6d8949fd12b9193bf2cb0ad764ace5559d8` と一致した。

## 1. 53件のvalidation

|項目|結果|
|---|---|
|ID|53件、重複0、欠落0、manifest（`P7C_batch_01`）と順序まで一致|
|category|scripts 50 / plain_scripts 3|
|不変の確認|original英語、previous candidate、scene/event metadata、speaker confidence、priority confidence、control metadata、protected tokensを入力と照合し、変更0|
|処理|53件すべてをClaude（このセッション）がレビュー。別モデルで埋めた分、未処理の分はなし|
|`review_source`|全件 `claude_cli`|

英語・日本語の突き合わせは独立した検証スクリプトでも行った（ID・原文・候補・scene・speaker・priority・制御順序・token・FA数・漢字・PCS・幅）。不一致0。

## 2–4. status

|status|件数|
|---|---:|
|confirmed|**53**|
|needs_context|0|
|needs_technical_fit|0|

保留0の理由：名前bufferはplayer名のみで未知bufferは0件、訳文が値に依存しない形にできた。FAは待機区間ごとの対訳を比べ、重要語・主述語が原文と同じ待機区間にあることを確認した。
幅は後述のとおり全行200px以下に収めた。ただしこれは「翻訳としての確定」であり、ROM注入の安全性はCodexの既存gateで別に判定される（ポインタ所有・renderer consumer・FA layout・glossary scope・名前buffer幅の警告を全件に残してある）。

## 5. 既存候補

|区分|件数|ID（review index）|
|---|---:|---|
|語句を維持|1|#5 サボネア / いあいぎり（Batch 03レビューのまま）|
|語句を維持・レイアウト補正のみ|3|#2〜#4 年表示（plain_scripts。先頭の空白を日本語頁の空白幅で補った）|
|修正|5|#0、#1、#6、#7、#8|
|新規翻訳|44||

修正の理由：#0はFA待機をまたいで述語『つくりかえた』が後ろへ遅れていたため組み替え。#1は未承認draftでFA区切りと制御（末尾の`\l`）が原文と合わなかった。
#6は語を維持して1行（204px）だけ短縮。#7は原文のFE/FB構造と合わず不要な『きみ』があった。#8は『こだ』『のかね』が年齢・人物像を足していた。

## 6. glossaryの使用

glossaryは変更していない。承認済み語は原文・entry・scopeに沿って使用した。

- 承認済み・global/entry scope内で使用：Aklove、Marlon、Zeph、Ivory、Aros、Borrius、Frozen Heights、Vivill Town、Icicle Cave、Light of Ruin、Cube Space、journey、Ultimate Weapon（#0のscope内）。
- scope外だが同一entityの既存project_standard語として使用し、`glossary_scope_warnings` を記録：14 entry。対象は Shadows、Shadow Warriors、Fey、Hoopa、Cube、Ruins of Void、Hoenn、Guardian of Borrius、Euler / Log、Mart（『フレンドリィショップ』は適用済みミッション文に合わせた）。
- これらをscope拡張・承認済みglossary適用として扱っていない。

## 7. 公式名称（official-name pending）

- PokeAPIキャッシュで完全一致を確認：サボネア、いあいぎり、フーパ、いましめのツボ。
- `official_name_verification_required`：2 entry。
  - #19 `Rift Cave` → 『さけめのどうくつ』。glossary未登録のUnbound地名。『Icicle Cave=つららのどうくつ』の型と『rift=さけめ』に合わせた仮表記で、検証できていない。
  - #32 `Prison Bottle` → 『いましめのツボ』。適用済みのどうぐ名と英語が完全一致するが、Unboundのそれが同じ物であることは独立に証明されていない。

## 8. FA 21件

21件すべて、ROMのsegmentと同数・同順の訳を作成した（合計180 segment、FA制御39）。FAの追加・削除・移動・結合・分割・buffer移動は0。
各entryに `original_segments`、`translated_segments`、`phase_view`（待機区間ごとの英日対訳）、`information_reveal_timing`、`fa_layout_approval_required=true` を付けた。**完成21件 / 保留0件**。

幅の制約（1 segmentが1行、約200px以下）のため、述語を前の区間に残す倒置などで要素を原文の待機区間に合わせた。

## 9. FA意味境界warning

- `FA_SEMANTIC_BOUNDARY_REVIEW_REQUIRED`：**0件**。ただし機械チェックは指定した重要語だけで、その有無は安全の証明ではない。Phase 6で、制御の数が一致していても意味境界が崩れた例を多数見たため、全21件で待機区間ごとの英日対訳を目視で比較した（重要語・主述語が同じ待機区間にあるかを確認）。
- `FA_PHRASE_BOUNDARY_NOTE`：12 entry（#0、#1、#13、#15、#30、#31、#32、#34、#35、#37、#40、#48）。
  承認済み語を分けられない（`Light of / Ruin`）、述語を前に残す倒置、慣用句がFAをまたぐ、といった軽微な語句移動。注記のみで安全とは認定していない。
- 特に注意：#31・#40は『はめつのひかり』全体を英語より1待機区間早く出す。#1は『やみの ちから』の『force』が1待機分早い。#32はP5/P6で動詞を繰り返し、P12で慣用句を保った。

## 10. 名前buffer 10件

対象：#20、#22、#26、#28、#29、#30、#35、#36、#38、#40（いずれも `[player]`、FD 01、PLAYER_NAME）。未知buffer値は0件。

- token identity：`FD 01` = `[player]`。戦闘用のFD05/FD06とは無関係。
- writer / 最大幅 / 展開後のページ状態：未証明のまま警告を残した（`BUFFER_WRITER_UNKNOWN`、`DYNAMIC_NAME_WIDTH_UNVERIFIED`、`BUFFER_PAGE_STATE_REQUIRES_PROOF`）。
- 訳文は値（人名・性別・人数）に依存しない。助詞は『[player]の』『[player]は』『[player]なのか』のように直後に置き、敬称は付けていない。#28は『[player]の かおを かぶる』でも名前として成立する。
- 判定：10件とも **confirmed**。注入可否はCodexが判断する。ラテン文字の名前に対する言語頁の切り替えはcontrolfix側で、Claudeはtokenを追加していない。

## 11. 口調

承認済みvoice profileの紐付けは0件。英語の態度（冷たい詰問、動揺、気づかい、報告など）だけを反映し、根拠のない一人称・二人称・性別/年齢語尾・方言・老人語は足していない。

- 修正例：#7で不要な『きみ』を外し、#8で『こだ』（子どもと断定）と『のかね』（年配めいた語尾）を外した。
- 『sir』は敬語（です・ます）で表現し、呼称を足していない（#10、#12、#14）。
- 二人称『あなた』は原文に `you` があり呼びかけとして必要な #27・#40 だけ。荒い二人称（おまえ・きさま）は使っていない。
- 同一scriptの前後文や名前の言及（Marlon、Zeph等）から話者を同定していない。

## 12. 静的幅・動的幅

- 日本語は1マス約10px（空白も10px）。FE/FA/FBの区切りごとが1行なので約20マス以下に収める必要があり、全segmentの最大幅は **200px**、208px超は0件。
- 幅を詰めるために意味を削らず、語順・言い回しを調整した。ただし語気や修飾が弱まった箇所が7件ある（#1 `fought`、#16 `my`、#19 `must be / our`、#24 `Frankly`、#40 `most important`、#41 `visit him`の目的語、#47 `much too young`）。内容は `translation_audit.json` の `width_driven_nuance_losses` に記録した。
- 動的幅は名前buffer 10件で未証明のまま警告。field 208px / battle 222pxは参考値、240pxは画面全体として使っていない。実際の描画先・開始座標・余白は未測定。

## 13. relocation候補

- #21 `No\. not this time\.`：encode 23B、元スロット19B。再配置が必要（`needs_relocation`）。意味を削って短縮していない。pointer ownerの全確認と可否はCodexが行う。
- 他のentryは元スロット内に収まる。#2〜#4はplain_scripts（先頭空白の補正を含め17〜19B）で、幅・中央寄せはplain-script rendererで未検証。

## 14. PCS / control

- 漢字0、confirmed全件のPCS encode error 0、未対応glyph 0。protected tokenの不一致0、control順序の不一致0、segmentごとのtoken配置の不一致0。
- 全53件で `[japanese]`/`[latin]` はClaudeが追加していない。
- 未知buffer（`[buffer1-3]`、`\00` 等）は0件。

## 15. Codex技術統合の候補数

confirmed 53件がすべて技術統合の候補。ただし入力段階で全件に、pointer所有の再審査、renderer consumer・実幅の未確認、glossary scopeの再審査が残り、FA 21件はlayout承認が必要。
#0〜#8の9件は既存のtechnical hold（FA意味境界・幅・pointer）を持つので解除しない。

## 16. 作成ファイル

- `tests/fixtures/ja_phase7_story_batch01_claude_review.json`（53件）
- `tests/fixtures/ja_phase7_story_batch01_translation_audit.json`
- `docs/ja-phase7-story-batch01-claude-review.md`

## 17. Batch 02への注意事項

- 日本語の幅は1マス10px（空白込み）。1 segment ≒ 20マス以下で、わかちがきの空白も幅に入る。
- Batch 02はShadow Base参照groupの後半（43件）。同じ場面の続きだが、話者は不明のままで、人物名の言及から同定しない。
- 『dark force』は適用済みの近接文脈に合わせて『やみの ちから』を使用した（Phase 6C Batch 04の未適用レビューは『あんこくの ちから』で不一致）。
- 『Shadow Warriors』『Shadows』『Fey』『Euler』『Hoenn』『Cube』などはscopeがentry単位。後続Batchでscope拡張提案をまとめて審査したい。
- 『Rift Cave』『Prison Bottle』の表記を揃える。
- FAで承認済み語が英語の途中で分かれる場合、語を分けずどちらかの待機区間に置いて注記する方針。

## 18. 検証

- JSON parse PASS。独立検証 FAIL 0。入力ファイル（batch、manifest、style handoff）は処理中・後でSHA-256不変。
- pytest / git status は最終報告に記載（テスト結果は下記ではなく実行ログを正とする）。
