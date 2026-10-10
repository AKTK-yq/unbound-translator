# Phase 6C-4I — Final Cleanup Batch 04 Claude review（NPC会話）

Batch 04（140件）の翻訳レビューだけを行った。これで Phase 6C の Claude 翻訳4バッチのレビューが一通り完了した。既存のROM、翻訳JSON、glossary、Python、injector、controlfix、FA validatorは変更していない。過去Batchのreview JSONや訳文にも触れていない。ROM生成、commit、pushもしていない。かなのみ。

成果物は次の3ファイル。作業前に3つとも未作成であることを確認した。

- `tests/fixtures/ja_phase6_cleanup_batch04_claude_review.json`（140件すべて）
- `tests/fixtures/ja_phase6_cleanup_batch04_voice_audit.json`（口調の監査）
- `docs/ja-phase6-final-cleanup-batch04-claude-review.md`（このファイル）

入力は読み取りだけで使った。`review_source` は全件 `claude_cli`（この Claude Code セッションで実際に翻訳・確認した行のみ。未実施の行はない）。

## 1. 入力140件の検証

140件、ID重複0、欠落0、manifestのID順と一致。CLAUDE_TRANSLATION 105、CLAUDE_CONTEXT 35。original、previous candidate、hold理由、制御メタデータ、protected token、話者信頼度、dialogue_group_idは入力から変えていない。全件 scripts カテゴリ。FAを含む行は71件、未確定バッファを含む行は8件（バッファ11個）。話者は UNKNOWN 139件、PLAUSIBLE 1件で、PROVEN は0件。

## 2. TRANSLATION 105件の結果

confirmed 101件、needs_context 3件、needs_technical_fit 1件。

- needs_context 3件: #0（`[buffer1]`）、#17（設定項目名『Quick HMs』が未承認）、#92（人名『Melony』が未解決）。
- needs_technical_fit 1件: #60（`incomplete_pointer_ownership`。訳文は記録済み）。

## 3. CONTEXT 35件の結果

confirmed 28件、needs_context 7件、needs_technical_fit 0件。保留7件はすべて未確定バッファが原因（#2、#3、#26、#40、#41、#61、#115）。

## 4. 結果の合計

| 区分 | 件数 | confirmed | needs_context | needs_technical_fit |
|---|---:|---:|---:|---:|
| CLAUDE_TRANSLATION | 105 | 101 | 3 | 1 |
| CLAUDE_CONTEXT | 35 | 28 | 7 | 0 |
| **計** | **140** | **129** | **10** | **1** |

confirmed は翻訳上の確定で、ROM注入の安全認定ではない。

## 5. 保留（needs_context 10件）

未確定バッファは `[buffer1]` 5件、`[buffer2]` 2件、`[buffer3]` 3件。名前、敬称、性別、人数、助詞を推測していない。同じ番号が別のイベントで同じ意味とは限らないため、1件ずつ判断した。保留行は `reviewed_japanese` を空にし、既存候補は変えていない。

- `[buffer1]`: #0, #2, #3, #115
- `(バッファ以外の理由)`: #17, #92
- `[buffer1], [buffer2]`: #26
- `[buffer3]`: #40, #61
- `[buffer2], [buffer3]`: #41

`[buffer1]` は呼びかけ語として使われる行（#0 `I do like that about you, [buffer1]`、#3 `we don't need to meet again, [buffer1]`、#115 `my [buffer1]`）が多い。#2 は『Let [buffer1] go』で対象が人かポケモンかも不明。#26 `[buffer1], hit 'em with a [buffer2]!` は戦闘の掛け声で、ポケモン名とわざ名と思われるが、書き込み側が不明。

## 6. needs_technical_fit（1件）

#60 `scr_1F3DACA`（`One of you! Help me get rid of him!`）。入力の hold に `incomplete_pointer_ownership` が残っているため、翻訳は記録したうえで技術確認に回した。固定スロットの超過、物理幅の超過、FAの重要語が待機をまたいで動く行は0件。

## 7. 文脈が解決した件数: 28件

CONTEXT 35件のうち、未確定バッファを含まず文が単独で意味を確定できる28件を翻訳した。根拠は、未確定バッファなし、承認済みglossary、PokeAPIで検証済みの名称。各行の `context_resolution` に evidence、resolved_ambiguity、remaining_risk を記録した。`conversation_id` やROM上の近接だけでは人物を確定していない。会話文中の名前（Arthur、Jax、Marlon、Zeph など）も、話者の同定には使っていない。

## 8. 既存候補の扱い

| 区分 | 件数 |
|---|---:|
| previous candidate maintained（そのまま採用） | 10 |
| previous candidate revised（修正） | 37 |
| newly translated（新規訳） | 83 |
| held（保留） | 10 |

- **維持 10件**: #4, #8, #9, #12, #14, #15, #42, #117, #138, #139。
- **修正 37件**のうち、レイドの すあなの掲示 19件（#118〜#136）は、既存候補が1行で原文のFE構造を持たなかったため、語（承認済みの『かくしあな』『レイドの すあな』）を保ったまま3行に並べ替えた。
- 残りの修正と理由:
  - #16: 命令調『きてくれ』を、原文の『Please』に合わせた丁寧な依頼に
  - #20: 旧形式(\p / \n)を原文の構造に直し、命令調『おい』を外した
  - #25: 語句は保ち、原文のFE / FB構造に直した
  - #49: 不要な二人称『きみ』を外した
  - #52: 『キューブ ブイスリー』を承認済みの『キューブV3』に
  - #53: 長い行を意味を保って短く
  - #56: 『マーロン [player]』が1つの名前に読めないよう読点で区切った
  - #57: 乱暴な二人称『おまえ』を外した
  - #71: 語句は保ち、原文のFE / FB構造に直した
  - #72: 構造を直し、二人称『きみ』を外した
  - #82: 語句は保ち、原文のFE / FB構造に直した
  - #90: 語句は保ち、原文のFE / FB構造に直した
  - #98: 語句は保ち、原文のFE / FB構造に直した
  - #99: 構造を直し、呼びかけの読点を足した
  - #101: 『ほうとうの いろ』(砲塔)を『たいほうの いろ』に改め、構造を直した
  - #107: 語句は保ち、原文のFE / FB構造に直した
  - #116: 『ポケモン つうしんクラブ』を承認済みの『ポケモンワイヤレスクラブ』に、構造を直した
  - #137: 語句は保ち、原文のFE / FB構造に直した
- 意味を変えるための口調修正は1件もない。

## 9. 口調と話者

| 信頼度 | 件数 | confirmed | needs_context | needs_technical_fit |
|---|---:|---:|---:|---:|
| PROVEN | 0 | 0 | 0 | 0 |
| PLAUSIBLE | 1 | 1 | 0 | 0 |
| UNKNOWN | 139 | 128 | 10 | 1 |

信頼度は変えていない。PROVEN は0件なので、既存の口調profileの適用も0件。原作ポケモン本編の人物として確定した行は0件で、名前が一致するだけで本人扱いしていない。一人称・二人称は原文に根拠がある場合以外は置かず、性別を連想させる語尾、老人語、方言は付けていない。

- 英語に俗語や砕けた語り（ya / yer / ain't / Howdy など）が明示されている行は、方言を足さず砕けた常体で表した（#23、#24、#27、#29）。『partner』はBatch 02の#69に合わせて『あいぼう』。
- 話し手が不明な行で『old man』『grampa』は、英語に敵意や親しみが明示されている範囲で『じいさん』『じいちゃん』とした（#79、#84、#107、#21 など）。

## 10. 口調が良くなった行: 5件

- #16: 命令調『きてくれ』→ 丁寧な依頼（原文の `Please`）。
- #20: 命令調『おい』を外し、困り果てた頼みに。
- #49: 不要な『きみ』を外した。
- #57: 乱暴な『おまえ』を外した。
- #72: 不要な『きみ』を外した。

## 11. Pokémon公式名称

検証済みの名称（PokeAPIキャッシュで exact 一致）を使った行が 29件。例: フーディン、ムクホーク、ワルビアル、ヘルガー、ドデカバシ、シャワーズ、マンムー、グラードン、サンダー、フリーザー、ファイヤー、フーパ、サイコキネシス、いわくだき、なみのり、ロッククライム、いあいぎり、とくせいカプセル。

`official_name_verification_required` を付けた行（公式名の断定をしていない）:

- #10 `scr_1F33968`: Shhhhzzz!
- #11 `scr_1F339B2`: HM=ひでんマシン; Pokédex
- #24 `scr_1F36150`: HM=ひでんマシン
- #37 `scr_1F3B7AD`: 機械音声の文体
- #38 `scr_1F3B7D6`: 機械音声の文体
- #39 `scr_1F3B819`: 機械音声の文体
- #109 `scr_1F4AD47`: Magnolia Town=マグノリアタウン

- 保留にした名称: #92『Melony』（本編のメロンと同一とは証明されておらず、カナ表記も推測しない）、#17『Quick HMs』（設定メニューの項目名が未承認）。
- 擬音・呪文・鳴き声: #10 `Shhhhzzz!` は発音を推測せず原文のまま残した。

## 12. glossary

- 承認済み語を 78回使用（51エントリ）。承認語の欠落0、scope衝突0。glossary本体は変更していない。
- `global_replace=false` の語を、同じ英語だからという理由だけで一括置換していない。
- scope外だが既存のproject_standard語に合わせて使った行が 23件（整合のための使用で、glossary適用とは数えない）。`glossary_scope_warnings` に記録した。対象: Shadows、Shadow Grunts、Shadow Warrior Project、Champion、Hoopa、Route [N]、Surf、Blizzard City、Frozen Heights、Cube、Agent、Battle Difficulty、Epidimy、Aklove など。
- 依頼にあった要注意語のうち、今回の入力に出たのは Cube（#50、#52、#75、#113。glossaryのscope外または空scope。整合のため使用）、Champion（#109、#111、#112。別entryにscope）、Science Society（#51、#58。承認scope内）、Redwood Village（#109。承認scope内）、Grim Woods（#119。承認scope内）、Guardian of Borrius（#115。保留）、Hoenn（#90。承認scope内）、Cloud Burst（#33。global）。Elite Four、Pokémon League、Mega Evolution、TM、Crater Town、Gurun Town、Borrius Region、Frost Mountain は今回の入力に出ない。

## 13. FA

FAを含む行は 71件。confirmed / needs_technical_fit の66件（703セグメント）は、ROM由来のセグメントごとに訳し、FAの追加・削除・移動・結合・分割は0。保留 5件は全セグメントを空のまま残した。全体の `reviewed_japanese` は空のまま。

- 各FA行に `original_segments`、`translated_segments`、`source_control_structure`、`information_reveal_timing`、`fa_phrase_boundary_notes`、`fa_semantic_status`、`fa_layout_approval_required` を記録した。confirmed のFA行はすべて `fa_layout_approval_required = true`。
- `information_reveal_timing` は、固有名・アイテム名・数値・重要語を、原文と同じ待機区間（FA / FBの間）に出しているかを機械的に確認した結果。
- `FA_SEMANTIC_BOUNDARY_REVIEW_REQUIRED` は**0件**。作業中に重要語が待機をまたいで動いた3か所（Jax、Light of Ruin の検出、Hoopa）は、訳を直して解消した。
- 注意: この確認は記録した重要語だけが対象。注記が無いことは意味的な安全の証明ではない。ROM構造や描画の検証はCodexに委ねる。
- `FA_PHRASE_BOUNDARY_NOTE` を付けた行 3件:
  - #58: 『so we should consider ourselves fortunate…』を日本語の語順に合わせ、E15〜E18に『うんが よかったと おもうべきだ』『…つくって いる ことが。』と配した。重要語『living weapons』はE18のまま
  - #70: 『Frozen / Heights』をE9側の『フローズンハイツで』にまとめた(同じ待機区間内)
  - #100: 『his Pokémon』をE9側の『おうの ポケモンは』にまとめた(E8の『what he failed to do, his Pokémon』を日本語の語順で並べ替えた)

## 14. 制御と文字

- 処理した130件の境界: FE 324、FB 296、FA 137。数と順序は原文と同じ。
- 色トークン、ポーズ（`\.` `\CC0818` `\CC0820` `\CC0830` `\CC0840` `\CC0600`）、引用符（`\qo` / `\qc`）、`[player]`、`[rival]` は原文と同じセグメントの同じ順序に残した。
- protected tokenの不一致0、制御の不一致0、FAの不変条件違反0。
- 漢字0。130件すべて日本語PCSでエンコード可能（エラー0）。ラテン文字が残るのは #10（擬音）と、数字・記号（`H005`、`V2`、`1F`）。
- 機械音声の文（#37〜#39）は、英語の全大文字に合わせてカタカナ表記にした。これは訳者判断として警告に記録した。
- 制御コード `\CC0840` の直後に16進文字（A〜F）が続く原文（`\CC0840Alright`）があるため、検証ではトークンを4桁固定で読んだ。

## 15. 幅とページ

実機の幅は未確認。既知の参考値は field textbox 208px、battle message 222px（240pxは画面全体の幅）。

- 静的な幅の最大は208px。208pxを超える行は0（今回は最初から208px以内に収めた。意味は削っていない）。画面の物理幅240pxを超える行も0。
- `[player]` / `[rival]` を含む行がある45件は、名前の長さで幅が変わるため `dynamic_name_width_uncertain` を付けた。`renderer_width_warning` に行ごとの静的な幅、動的トークンのある行、profile、ページ制御のbyte算入を記録した。
- ページ制御（`[japanese]` / `[latin]`）のbyteは必要容量に含めて計算した。

## 16. 再配置とポインタ

元のスロットより長く再配置が必要な行が 3件（#4（20B > 18B）、#10（17B > 13B）、#139（9B > 7B））。いずれも固定・再配置不可ではない。`relocation_warning` に原スロット、必要byte、owner数、owner確認の状況を記録した。Claudeは注入していない。全ownerの確認はCodexが行う。

## 17. Codexに渡せる技術統合候補

**129件**（confirmed）。ROMへの注入可は意味しない。技術統合で確認すること: FA行（`fa_layout_approval_required`、とくに `FA_PHRASE_BOUNDARY_NOTE` の3件）、`official_name_verification_required` の行、幅の実機確認（動的名前の45件）、再配置が必要な3件、#60のpointer ownership。

## 18. 全4バッチの翻訳レビュー完了状況

| Batch | 件数 | confirmed | needs_context | needs_technical_fit | 備考 |
|---|---:|---:|---:|---:|---|
| 01（非会話） | 147 | 114 | 32 | 1 | |
| 02（NPC会話） | 142 | 93 | 49 | 0 | |
| 03（NPC会話） | 140 | 112 | 28 | 0 | |
| 04（NPC会話） | 140 | 129 | 10 | 1 | |
| **計** | **569** | **448** | **119** | **2** | 569件すべて `review_source = claude_cli` |

Phase 6Cの Claude 翻訳レビューは4バッチ569件すべて完了した。

## 19. 未解決事項

- **保留 119件**: 大半は未確定の動的バッファ。バッファの書き込み側（script / special）と値の型・語形・助詞との関係が分かれば再開できる。特に呼びかけ語に使われる `[bufferN]` は、名前、敬称、性別、親密度の判断が必要。
- **Batch 03の #99（`incomplete_pointer_ownership`）**: 当時は confirmed のまま警告を付けたが、今回の方針（pointer ownership未確定は needs_technical_fit）に合わせると技術確認の対象。過去Batchのreview JSONは変更していない。Codexの技術統合で扱うこと。
- **鳴き声の扱い**: Batch 03の #91（`サボ！`）、#123（`バード！`）は、名前から取った推測の表記で警告付き。今回の方針（鳴き声は発音を推測してカタカナ化しない）では見直し候補。過去Batchの訳文は変更していない。
- **Batch 02〜03の機械的な語の扱い**: 同様の擬音・造語（呪文）はラテン文字のまま残している（Batch 02 #93、Batch 03 #92 / #115、今回の #10）。
- **公式名の確認**: 『Quick HMs』（設定項目名）、『Melony』（人名）、『Magnolia Town』、『Victory Road』（Batch 03）、『titan Pokémon』（Batch 03）、『HM』の表記などは人手またはglossaryでの承認が必要。
- **glossaryのscope拡張の検討候補**（無断拡張はしていない）: Shadows、Champion、Hoopa、Route [N]、Surf、Cube、Agent、Battle Difficulty など、複数Batchで『別entryにscope』と記録した語。
- **FA**: `FA_PHRASE_BOUNDARY_NOTE` 付きの行と、情報開示タイミングの機械チェックの対象外の語は、Codexと人手の確認が必要。
- **幅**: 実機の幅は全Batchで未確認。動的な名前を含む行は実機で確認する必要がある。
