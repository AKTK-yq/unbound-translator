# Phase 6C-4J — Final Cleanup Batch 04 Technical Integration

Claudeレビュー済みBatch 04の140件を独立に監査し、20件だけをROMへ注入した。120件は保留。
既存の2,383件、過去Batchの成果物、glossary、validator、injector、controlfixは変更していない。
日本語適用総数 **2,403件**、Phase 6残り保留 **774件**（794 − 20）。
今回の適用は静的な安全gateの承認であり、mGBAでのruntime確認ではない。runtimeは未実施。

## 1. 最終集計

|項目|結果|
|---|---|
|入力|140 IDs、重複0、欠落0、manifest順序一致。TRANSLATION 105 / CONTEXT 35|
|Claudeレビュー|confirmed 129 / needs_context 10 / needs_technical_fit 1。original・previous candidate・hold・制御・token・話者信頼度は不変|
|技術判定|**APPLY 20 / HOLD 120**（confirmed 129 → 適用20・技術保留109、context 10、technical 1）|
|FA|71件：完成66（703 segments）、context保留5。意味判定は保留42 / 通過24。適用は2件（#18、#94）|
|in-place / relocation / pointer writes|19 / 1 / 1（再配置は #4 のみ）|
|変更byte|1,454（in-place text 1,431、relocated text 19、pointer 4）。**想定外0**|
|strict dry-run|incremental 20 / 基準ROMからのfull 2,403。encode・pointer・space・truncation・patchエラー0|
|controlfix|`--no-wrap` 2回。出力JSON byte一致、本文・境界変更0|
|回帰|全pytest **553 passed / 16 subtests passed**、py_compile PASS、git diff --check PASS|
|runtime QA|22件作成、**操作未実施**|
|範囲|Batch 01–03の保留救済・過去FA保留の再処理・unknown buffer解析・glossary拡張・commit・pushなし|

## 2. STEP 1–2 既存テスト1件の修復

失敗していたのは `tests/test_ja_phase6_cleanup_batch03.py::test_original_909_files_preserved_and_no_existing_validator_edit`。
原因はコードで確認した。`scripts/build_ja_phase6_cleanup_batch03.py` の `protected_snapshot()` は
`rom/`・`out/`・`glossaries/` と `git ls-files --cached --others` の全ファイルをハッシュし、
`NEW_PATHS`（Batch 03自身の成果物）を除いて「ちょうど909件・固定aggregate」を要求する。
Batch 04のClaude成果物3件（review JSON、voice audit JSON、review doc）はこの許可リストに無く、912件になって失敗した。
再現時の集計は912件、909件を超えた3件はその3ファイルだけだった。

修正（Batch 03のscript/testのみ、保護対象のhashと期待値は不変）：

- `LATER_STAGE_PATHS` を追加。Batch 04のClaude成果物3件と、今回のBatch 04技術成果物を**完全一致のパス**で列挙（ワイルドカード・prefix・全許可なし）。
- `protected_snapshot()` は `NEW_PATHS | LATER_STAGE_PATHS` を除外。**期待数909、INITIAL_SNAPSHOTのhash、既存validator不変の検証はそのまま**。
- `out/phase6/ja_phase6_cleanup_batch04_for_claude.json`（既に909件に含まれる入力）は許可リストに入れない。
- 追加テスト：許可リストが完全一致・ワイルドカード無しであること、許可リストから1件外すと同じ検証が失敗すること。
- Batch 04側テストでも、未登録の新規ファイルを置くと `protected_snapshot()` が失敗することを一時ファイルで確認（終了後に削除）。

修正後の全pytest：**522 passed / 16 subtests passed**。その後Batch 04のテスト31件を追加して最終 **553 passed**。
テストの削除・skip・xfail・hash確認の削除・909の変更は行っていない。

## 3. ROM

|項目|値|
|---|---|
|元ROM MD5|`9cad8e771940e7f7094d13911552cef0`（一致）|
|基準ROM|`out/unbound-ja-phase6-cleanup-batch03.gba`|
|基準ROM SHA-256|`546f18a50e0ab0eadb9ed0eb53d5773c2cf5aefae1028cc8e8a631379292cc62`（Batch 03監査記録と一致、生成前後で不変）|
|出力ROM|`out/unbound-ja-phase6-cleanup-batch04.gba`（新規。生成前に不存在を確認）|
|出力ROM SHA-256|`0d1d00e7b0f4f113514abbcf1907e6d8949fd12b9193bf2cb0ad764ace5559d8`|
|出力ROM MD5|`ddaa2cff9931d0d0b71f3eab5fb685b9`|

書き込み前に全出力パス（JSON 14件、runtime QA、doc、script、test、ROM）の不存在を確認した。
Batch 01–03の成果物63ファイル（`out/phase6` の各出力、review/voice/runtime QA fixture、doc、Batch 01–03のROM）のaggregate SHA-256
`ac2f7b5b1a9754d4bfe1d231533e91b2e6130044d0670c8c18d8f73c930eb1e6` を実行前・実行後で照合し、不変。

## 4. confirmed 129件の技術判定

|判定|件数|主な理由（entry単位でreviewed JSONに記録）|
|---|---:|---|
|APPLY|20|全gate通過|
|HOLD：dynamic buffer|45|`[player]` / `[rival]` の最大幅・展開後ページ状態が未証明|
|HOLD：FA意味境界|24|主たる保留理由がFA意味境界：重要語または主述語が別の待機区間で開示される|
|HOLD：renderer consumer未証明|23|pointer ownerがmessage/callstdでない（レイド掲示18件＋地名・ラベル等5件）。レイド19件のうち #122 の主たる理由はglossary|
|HOLD：FA幅envelope|6|日本語の行がsource英語の最大行幅を超える|
|HOLD：owner / interior|5|ROM内の整列外の偶然一致を構造的に分類できない|
|HOLD：glossary scope|4|スコープ外で、同一entityの独立根拠が無い|
|HOLD：公式名称|1|#10 擬音|
|HOLD：Claude語句|1|#54 「help」の脱落|
|合計|129||

保留120件の内訳は、上の109件に context 10 と technical 1 を足したもの。複数gateに掛かる行は全holdを `all_holds` に保存している。

適用20件（review index）：#4、#9、#18、#28、#29、#32、#37、#38、#39、#52、#59、#62、#67、#82、#90、#94、#98、#99、#107、#137。
最大の静的行幅は199px（#29、#38）、全行208px以下、`[player]`等の動的buffer無し。

## 5. context 10件

#0 #2 #3 #26 #40 #41 #61 #115 は未確定buffer（`[buffer1-3]`）、#17 は設定項目名 `Quick HMs`、#92 は人名 `Melony`。
全件保留を維持した。writer・値の型・値域・語形・最大幅の証拠が入力に無く、推測でconfirmedにしていない。
Melonyは名前だけで本編の公式人物と断定せず、Quick HMsも公式名称と設定項目名を区別して保留。

## 6. needs_technical_fit 1件（#60 `scr_1F3DACA`）

記録済みownerは `0x01E59488`（loadpointer + callstd 6）。ROM全体の完全一致がもう1件 `0x012CE3E5` にある。
周辺バイトは滑らかな連続値でPCM標本データに見えるが、sample header / voicegroup等の構造的証明は行っていない。
**偶然一致とは断定せず、未分類として保留**。interior hitも2件（`0x01295F19`、`0x014708A0`）ある。
再配置はしていない。reviewed JSONに文脈hexと隣接バイト差の平均（診断値）を保存。

## 7. FA 71件

- 構造監査（66件・703 segments）：FAの数・順序、FE/FA/FBの順序、segment数、protected token、per-segment token、ROM source controlがすべて一致。FA追加・削除・移動・結合・分割は0。
- 意味監査：全66件を、英語segmentと日本語segmentを**待機区間（FA/FB単位）ごと**に並べて手動で比較した。
  基準はBatch 03と同じ。重要名詞・固有語（M1）または情報を担う主述語（M2）が別の待機区間で開示されたら保留。
  否定・様態副詞・従属節の移動（M3）はnoteとして記録し保留にしない。FEは待機ではない。
- 結果：**保留42 / 通過24**。通過24のうち、他のgateも全て通って適用されたのは #18、#94 の2件。
- Claude側の「FA意味境界警告0」は重要語リストの機械チェックの結果で、意味安全の証明ではなかった。
  今回の独立比較で、Claudeの注記が無い行にも重要語の移動を多数検出した（例：#7 `kid`、#50 `Cube Space`、#97 `the Weapon`、#103 `scapegoat`）。
  これらは「Claudeのレビューが誤り」という意味ではなく、FA待機をまたぐ開示順の保存という追加基準での判定である。
  各行の根拠は `semantic_voice_state.fa_issue` / `fa_note` と待機区間別の対訳（`wait_phases`）に保存。
- FA完成行はすべてClaude側で `fa_layout_approval_required=true`。適用した2件も実機での待機・スクロール確認が必要。
- #18：条件節（P1）・結論（P2）・皮肉（P3）が各待機区間内に収まる。
- #94：`there's a chance`（可能性の表現）だけが次の待機区間に移る（M3 note）。`won't notice` と `sneak past` は同じ待機区間。

## 8. FA_PHRASE_BOUNDARY_NOTE 3件

|index|判定|根拠|
|---|---|---|
|#58|保留|注記は「E15〜E18を日本語の語順に並べ替えた」。この4 segmentは4つの待機区間(P9–P12)にまたがるため、`consider ourselves` と `fortunate` がFAをまたいで入れ替わる。`living weapons` はP12のまま（その部分の主張は正しい）。|
|#70|注記は妥当・entryは保留|`Frozen / Heights` のE9/E10はFEで繋がる同一待機区間(P6)内。ただし `Shadow Warriors` が英語ではP4/P5に割れているのに日本語は完全な語をP4に出す、主述語 `there are only so many` がP5へ遅れる、さらにinterior pointer未分類。|
|#100|保留|注記は「`his Pokémon` をE9側にまとめた」と述べるが、E8とE9の間にFAがあり、主節の主語が1待機分遅れて開示される。同一待機区間の移動ではない。|

## 9. レイド掲示 19件（#118〜#136）

英語FE 2・日本語FE 2、FA/FB 0、日本語3行、動的buffer無し、各行の静的幅は200px以下（最大200、英語最大195〜196）。原文との制御構造は一致している。
**全件保留（`renderer_consumer_unproved`）**。理由：pointer ownerはROM `0x01E613B0`〜`0x01E615B0` の16バイト×32件のtable
（`[名称ptr][説明ptr][EWRAM flag ptr][id]`）の説明ptrで、このtable先頭への参照がROM内に見つからず、
表示window・幅・font・FEの扱いが未証明。3行構造や幅が英語envelope内に近いことは表示枠への収まりの証明にならない。
Batch 03の `renderer_consumer_unproved` と同じ基準。entry単位の対訳・幅・table recordは `audits.raid_notice` に保存。
`原文のFE構造に合わせて既存候補を3行に直した` というClaudeの修正自体は、制御構造の面では正しいことを確認した。

## 10. 口調修正 5件（#16 #20 #49 #57 #72）

英語との照合で全件「原文の範囲内」。命令調の除去、不要な二人称の除去、丁寧な依頼への修正であり、一人称・性別・年齢語尾・方言・人物像は足していない。
Codex側で新しい口調は作っていない。ただし全5件が `[player]` を含むため、dynamic buffer gateで**保留**。

## 11. 公式名称警告 7件

|index|分類|判定|
|---|---|---|
|#10 Shhhhzzz!|擬音|保留。発音を推測せずラテン文字を維持した点は妥当だが、公式の鳴き声表記として検証できず、`[japanese]` 頁上のラテン文字は元のラテン頁の描画と同一でない。注入しても意図した変化が無い。|
|#11 / #24 HM|一般用語|保留。`ひでんマシン` はBatch 01との整合のみで、リポジトリ内に独立した公式名称証拠が無い（PokeAPI cacheにHM無し、glossary未登録）。|
|#37 #38 #39 機械音声|訳者判断の文体|**通過**。全大文字をカタカナ機械文体にした訳者判断。名称ではなく公式・glossary主張なし。PAYLOAD RECEIVED = ペイロード ジュシン、SENTIENT MATTER DETECTED = イシキ ヲ モツ ブッシツ ヲ ケンチ、H005は原文のまま、pauseの位置・数は原文と同一で、意味はsegment単位で一致。|
|#109 Magnolia Town|未確認の地名|保留。glossaryにあるのは `Magnolia Fields` のみ。独立根拠なしに公式扱いしない。|

## 12. glossary scope gap 23件

glossaryは変更していない。各警告を「現スコープ」「entry_ids」「独立した公式根拠」で分類した。

|分類|件数（用語単位）|内容|
|---|---:|---|
|`global` の既存permission|5|Blizzard City、KBT Expressway、Cloud Burst、Véga、Frozen Heights|
|termの `entry_ids` に当entryを含む|3|#11 / #21 の Shadows、#23 の Epidimy|
|同一entityの独立根拠（PokeAPI）|2|#35 の Surf（move `surf`＝なみのり）、#109 の Hoopa（species `hoopa`＝フーパ）。entry単位のみ。承認済みglossary適用としては扱わない|
|**未解決（スコープ外・独立根拠なし）**|18|Shadow Grunts、Route [N]（#19 #21 #22 #122）、Shadows（#74 #76 #78 #80 #109）、Shadow Warrior Project、Agent、Cube（#75 #113）、Champion（#109 #111 #112）、Battle Difficulty|

未解決を含む17 entryはglossary gateで保留。`scope_extension_proposal.json` に全23 entryの判定と次の作業を保存（提案のみ）。

## 13. 動的な名前 45件

`[player]` / `[rival]` を含むconfirmed 45件（context保留5件は別）。全件保留。
ROM証拠：Unboundの命名画面は最大7文字、キーボードの最大advance 6pxで、**ローカル入力の上限は42px**。
ただしリンク・外部名・保存データ・展開後のページ状態は未証明のため、この値は診断にとどめ、承認根拠にしない。
参考計算（reviewed JSONに全件保存）：
42px/名で最大行が208pxを超える行は0件、広い条件付き上限84px/名では11件が208pxを超える。
静的本文が208px以内でも、動的buffer行は安全と認定していない。

## 14. 幅・ページ

- 静的最大幅208px（保留行のみ）、208px超過0件。適用20件は最大199px。240px（画面全体）は承認理由にしていない。
- field textboxは208px（26 tiles）、battleは222px。ROM上のtemplate・printer・幅tableを再照合。textbox内の開始座標・余白・scroll時位置は未実測で、静的fitはruntime warning付き。
- ページ制御byteは必要容量に含めて計算した（`[japanese]`/`[latin]` を含む `encoded_bytes`）。
- FAの幅は既存validator（source英語の最大行幅envelope）をそのまま適用。緩和していない。

## 15. 再配置候補

|index|slot→必要|判定|
|---|---|---|
|#4 Hoo.pa.|18→20|**適用（再配置）**。owner 1件 `0x01E58F51`（message opcode 0x67）、whole-ROM完全一致と一致、interior 0、固定/no_relocation無し。vetted FF `0x00C151F8`（20 byte）へ移動、pointer 1件を更新。|
|#10|13→17|保留（擬音未検証。ownerは3件完全一致だが自動適用しない）|
|#139 Maxima|7→9|保留（owner 9件はloadpointerだがconsumer未証明）|
|#12（Claude未報告）|18→20|保留（`[player]` ＋ consumer未証明）。**報告は3件、実際は4件**|

## 16. control / PCS

- source controls、protected token、FE/FA/FB/FC/FD順序、buffer位置、待機位置：適用20件でROM source比較一致（FC15/16の言語頁のみ除外）。
- ROMから再計数したconfirmed 129件のcontrol：FE 324 / FB 295 / FA 137 / FD 51 / FC 118。全140件のmetadataと一致。
- 漢字0、unsupported glyph 0、PCS encode error 0。controlfixは標準 `--no-wrap` を2回適用し、出力JSON byte-for-byte一致。
- 適用20件のASCII文字（`H005`、`V3`、`KBT` 等）は日本語頁でエンコードされる。ベースライン既存行にも同種があり、問題としていない。実機の見え方は未確認。

## 17. strict dry-run と binary audit

- incremental dry-run（基準ROM→20件）：encode 0 / pointer mismatch 0 / implausible 0 / no-space 0 / truncation 0 / runtime patch 0 / graphics 0 / relocation overlap 0。
- full dry-run（元ROM→2,403件）：同一の全エラー0。
- binary audit（32MB全比較）：変更1,454 byteが全て承認済みentryに紐づく。
  in-place text 1,431（19 entry）、relocated text 19（#4 1件）、pointer 4（#4の1箇所）。想定外0、font/graphics/ASM/runtime patch変更0。
- 既存2,383件のpayload・storage・pointerは個別に不変を確認。Sarah / Liam / Kojiの口調修正（`scr_1F02145`、`scr_740753`、`scr_1F06A82`）は保持、Danielは新規適用なし。
- 保留120件の本文slotと全ownerはROM上で不変。

## 18. hold inventory

`out/phase6/ja_phase6_cleanup_batch04_technical_holds.json`（120件）。各行にentry ID、batch index、状態、reviewed Japanese、primary/secondary hold、FA・buffer・公式名・glossary・動的幅・pointerの状態、次の作業を保存。
過去Batchの保留台帳は変更していない。

## 19. runtime QA（未実施）

`tests/fixtures/ja_phase6_cleanup_batch04_runtime_qa.json`：22件（適用8＋保留14）。
適用：再配置 #4、FA長文 #18、幅の長い会話 #29 #38、機械音声 #37 #38、他。保留：FA注記 #58 #70 #100、口調 5件、再配置 #10 #139、レイド #118 #119、#60、#109。
map/eventは `UNKNOWN`（到達可能性の証明ではない）。mGBAの操作は今回行っていない。

## 20. 全4バッチ集計

翻訳レビュー（569件）：

|Batch|confirmed|needs_context|needs_technical_fit|合計|
|---|---:|---:|---:|---:|
|01|114|32|1|147|
|02|93|49|0|142|
|03|112|28|0|140|
|04|129|10|1|140|
|計|**448**|**119**|**2**|**569**|

ROM適用（各Batchのtechnical validationを正とする）：Batch 01–03 = 68 + 28 + 26 = **122**、Batch 04 = **20**、合計 **142**（重複なし：4バッチのIDは互いに素）。
4バッチの内訳：適用142 ＋ confirmedだが技術保留306 ＋ context 119 ＋ technical 2 ＝ 569。
**Phase 6全体の残り保留774件は別の数字**（これには上記の保留に加え、4バッチ外の保留が含まれる。4バッチ内の保留427件と混同しない）。

## 21. テスト

`tests/test_ja_phase6_cleanup_batch04.py`（31件）：既存909ファイル保護と許可リスト、未登録ファイルの検出、過去成果物の不変、140件accounting、metadata改変の拒否、
confirmed 129 / context 10 / technical 1、FA 71 / 66 / 703、全FA行の意味判定の網羅、構造一致≠意味通過、FA注記3件、レイド19件、口調5件、公式名称7件、
glossary gap 23件、動的名前45件、再配置3件（＋未報告1件）と適用1件、#60のpointer、安全gateの独立再判定、PCS/control、controlfix byte一致、
strict dry-run（改変で失敗）、既存2,383件保持、binary audit（1byte改変で失敗）、想定外diff 0、保留本文・owner不変、hold台帳とruntime QAの形、4バッチ集計。

## 22. 未解決事項

- Claudeへ戻す候補：FA意味境界の保留42件（待機区間別の対訳と根拠はreviewed JSONに保存）、#54 `help Marlon` の語句、#89 `for just long enough` の脱落。
- 証拠待ち：`[player]`/`[rival]` 45件の最大幅、レイド掲示table（19件）のconsumer、interior/unaligned hitの構造的分類（37件）、`HM`・`Magnolia Town`・擬音の独立証拠、glossary scope拡張（`scope_extension_proposal.json`）、#60 のpointer分類。
- 実機未確認：適用20件の待機・スクロール・色・言語頁の復帰。特に適用FA 2件（#18、#94）、再配置 #4、機械音声 #37–#39。
- 過去Batchの未解決（今回は変更していない）：Batch 03 #99 のpointer ownership、Batch 03の鳴き声表記 #91 / #123。
