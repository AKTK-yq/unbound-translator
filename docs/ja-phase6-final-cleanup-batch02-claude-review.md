# Phase 6C-4D — Final Cleanup Batch 02 Claude review（NPC会話）

Batch 02（142件）の翻訳レビューだけを行った。Batch 03 / 04 には進んでいない。既存のROM、翻訳JSON、glossary、Python実装は変更していない。controlfix、injector、ROM生成、commit、pushもしていない。かなのみ。

成果物は次の3ファイル。作業前に3つとも未作成であることを確認した。

- `tests/fixtures/ja_phase6_cleanup_batch02_claude_review.json`（142件すべて）
- `tests/fixtures/ja_phase6_cleanup_batch02_voice_audit.json`（Batch 03 / 04 で再利用できる口調の監査）
- `docs/ja-phase6-final-cleanup-batch02-claude-review.md`（このファイル）

入力の `ja_phase6_cleanup_batch02_for_claude.json` と manifest は読み取りだけで使った。

## 1. 入力検証

142件、重複0、欠落0。manifest のID順と一致。CLAUDE_TRANSLATION 61、CLAUDE_CONTEXT 81。原文、既存候補、hold理由、制御メタデータ、protected token、話者信頼度、dialogue_group_id は入力から変えていない。レビューは全件 `review_source = claude_cli`。

## 2. 結果

| 区分 | 件数 | confirmed | needs_context | needs_technical_fit |
|---|---:|---:|---:|---:|
| CLAUDE_TRANSLATION | 61 | 61 | 0 | 0 |
| CLAUDE_CONTEXT | 81 | 32 | 49 | 0 |
| **計** | **142** | **93** | **49** | **0** |

confirmed は技術統合に渡せる候補という意味で、ROMへの注入可を意味しない。

## 3. 文脈が解決した32件と、その証拠

CONTEXT 81件を機械的にすべて保留にはしていない。未確定バッファを含まず、文が単独で意味を確定できる32件は翻訳した。各行の `context_resolution.evidence` に証拠を記録した。

| 証拠の種類 | 内容 |
|---|---|
| 未確定バッファなし | 既知は `[player]` のみ。文の意味が原文だけで決まる |
| 承認済みglossary | 例: チャンピオン、ポケモンリーグ、デビルデュオ、ギャンブラー、さいしゅうへいき、わざマシン、フーパ |
| 公式名の検証 | PokeAPIキャッシュで検証済みのポケモン / わざ / どうぐ / とくせい名（`official_names_verified`） |

`conversation_id` やROM上の近接だけでは話者を確定していない。話者の確定は、入力にあるtrainer ID / object bindingの証拠（PROVEN）だけに従った。

## 4. 保留（needs_context 49件）

すべて未確定のバッファが原因。名詞、助数詞、助詞、性別を推測していない。保留行は `reviewed_japanese` を空にし、既存候補（#0〜#5）はそのまま残した。

| 未確定バッファ | 該当entry数（重複あり） |
|---|---:|
| `[buffer1]` | 34 |
| `[buffer2]` | 18 |
| `[buffer3]` | 15 |
| `\07` | 5 |
| `\08` | 4 |
| `\0C` | 3 |

`\Lv` も未確定として扱い、#49、#51 の保留に含まれる。`[player]` を含む保留2件（#106、#115）は、同じ行の `[buffer1]` が原因。

保留のentry番号（バッファの組み合わせ別）:

- `[buffer2]`: #0, #1, #2, #16
- `[buffer2], [buffer3], \07, \08`: #3, #32, #40, #47
- `[buffer3]`: #4, #43, #125
- `[buffer1], \0C`: #5
- `[buffer1]`: #6, #7, #12, #13, #14, #15, #22, #31, #34, #36, #38, #39, #41, #42, #46, #52, #64, #100, #101, #104, #106, #114, #115, #124, #134
- `[buffer2], [buffer3], \07`: #35
- `[buffer2], [buffer3]`: #37
- `[buffer2], \0C`: #49
- `[buffer1], [buffer3]`: #50
- `[buffer1], [buffer2], [buffer3]`: #51, #78, #79, #102, #121
- `\0C`: #53
- `[buffer1], [buffer2]`: #103, #113

必要な追加情報は、各行の `context_resolution.missing` に書いた。共通しているのは、バッファの書き込み側（script / special）と、値の型・語形・助数詞。

## 5. needs_technical_fit

0件。固定・再配置不可のスロットを超える行はなく、制御の境界が日本語の語順と衝突して保留にした行もない。

- Batch 02 のうち、元のスロットより長くなり再配置が必要な行が 7件ある（すべて `fixed` でも `no_relocation` でもない）。警告として記録した: #8、#93、#99、#117、#118、#119、#123。
- 前回の保留 `terminal_fa_without_source_boundary`（#81〜#83）は、候補末尾にあった余分なFAを付けずに、ROMのFE / FA位置どおり3セグメントに分けて解消した。

## 6. 話者の信頼度

| 信頼度 | 件数 | confirmed | needs_context |
|---|---:|---:|---:|
| PROVEN | 9 | 9 | 0 |
| PLAUSIBLE | 29 | 16 | 13 |
| UNKNOWN | 104 | 68 | 36 |

信頼度は1件も変えていない。公式キャラクターとして確定した行は0。

## 7. 口調profileの使い方

PROVEN 9件は7グループ（`object_003516F0_003`、`object_003516D4_002`、`trainer_0510`、`trainer_0100`、`trainer_0310`、`trainer_0311`、`trainer_0531`）。グループは分割せず、同じ判断でまとめてレビューした。PROVEN は話者の同定であり CONFIRMED_VOICE ではない。profileの信頼度は変えていない。

| グループ | entry | profile | 適用 |
|---|---|---|---|
| trainer_0100（Dave・Youngster） | #127 | PROVISIONAL_VOICE | 参考のみ。既訳『きあい だけじゃ かてないな』に合わせた常体。一人称は原文に無いので省略 |
| trainer_0310（Roger・Bird Keeper） | #128、#129 | PROVISIONAL_VOICE | 参考のみ。熱心な趣味人の態度を常体で反映。一人称なし |
| trainer_0311（Reed・Bird Keeper） | #131、#132 | PROVISIONAL_VOICE | 同上。#129とは別人として扱い、同じ口調の統一はしていない |
| trainer_0510（Kenlawa・Expert） | #72 | なし | 中立の常体。既存候補の女性的な語尾を外した |
| trainer_0531（Anthony・Bug Catcher） | #140 | なし | 中立の常体。子ども口調を付けていない |
| object_003516F0_003 | #54 | なし | 中立の説明口調 |
| object_003516D4_002 | #55 | なし | 英語のくだけた語り（nab 'em）に合わせた常体 |

PLAUSIBLE 29件は傾向を参考にしただけで、声を固定していない。UNKNOWN 104件は英語の態度（丁寧、威圧、感傷、とぼけ、せかす など）だけを反映した。根拠のない わし / ぼく / おれ、性別・年齢の語尾、方言、全員同じ丁寧語は付けていない。

## 8. 口調が良くなった行 / 既存訳を残した行

- 口調を改めた行: #72（既存候補『たしかに あなたは じゅんびが できていたようね』）。二人称の補完と『ようね』の語尾を外し、静的な幅247pxの超過も解消した。
- 既存の語句を残した行: #81〜#83（トロフィー説明）。語句は既存候補のまま、構造だけ直した。
- 既存候補を残して保留にした行: #0〜#5（未確定バッファのため。候補は変更なし）。
- 上記を除く confirmed は、既存候補がなかった行の新規訳。

## 9. Pokémon公式名称

検証済みの名称（PokeAPIキャッシュで exact 一致）を使った行が 68件。例: ムクホーク、ファイアロー、ルチャブル、バタフリー、シェイミ、ミュウ、アルセウス、ミツハニー、アブリー、コンパン、ボスゴドラ、クレセリア、フリーザー、サンダー、ファイヤー、フーパ、ハッサム、ストライク、グランブル、クロバット、チルタリス、ナットレイ、キャタピー、ビードル、ワシボン、バルチャイ、ロッククライム、はたきおとす、いあいぎり、ふくがん、みつあつめ、ハイパーボール、スーパーボール、ハッサムナイト、みかづきのはね、どくけし、しあわせタマゴ、コインケース、きんのたま、あまいミツ、グラシデアのはな、ゴーゴーゴーグル、モンスターボール、かくとう、ドラゴン。

`official_name_verification_required` を付けた行（公式名の断定をしていない）:

- #57 `scr_1F09D6C`: Gracidea flowers
- #58 `scr_1F09E0D`: Gracidea flowers
- #59 `scr_1F09E94`: Gracidea flowers
- #65 `scr_1F0A708`: Frost Mountain=フロストやま
- #67 `scr_1F0A83E`: Roar
- #71 `scr_1F0AABD`: two on two=2たい2
- #75 `scr_1F0ADCC`: two on two=2たい2
- #77 `scr_1F0B2DB`: Crobatman=クロバットマン; Fighting
- #80 `scr_1F0BE99`: Super Cube=スーパーキューブ; Cube=キューブ
- #84 `scr_1F0C46E`: Redwood Village=レッドウッドビレッジ
- #85 `scr_1F0C52E`: Gurun Town=グルンタウン / Route 18=18ばんどうろ
- #93 `scr_1F0D8AA`: Sankren fimbulvetr
- #112 `scr_1F0E798`: Black Ferrothorn=ブラックナットレイ

## 10. glossary

- 承認済み語を 43回使用（37エントリ）。承認語が文中から欠けたものは0。
- 新規統合した語の `global_replace` は false のまま。scope外への適用（glossary適用としての数え入れ）は0。文字列置換はしていない。
- scope外だが既存の project_standard 語に合わせて使った行が 10件（整合のための使用で、glossary適用とは数えない）。`glossary_scope_gaps` に記録した。scope拡張の検討候補: Cube、Redwood Village、Gurun Town、Route [N]、Borrius Region、Frost Mountain、Black Ferrothorn、Science Society、Cloud Burst。
- 未解決のglossary語『Fighting』（#77）はタイプ名ではなく動詞の用法なので適用していない。
- 『かくしあなの レイドバトル』（#25）はFEをまたぐ語で、日本語の語中の空白が原文の改行位置と一致している。

## 11. 未確定バッファの扱い

§4を参照。confirmed の行に未確定バッファは1件も含まれない（`[player]` を除く）。

## 12. FA

FAを含む行は 55件。confirmed 38件は、ROM由来のセグメントごとに訳し、FAの追加・削除・移動・結合・分割は0。保留 17件は未確定バッファのため、全セグメントを空のまま残した。

- 全体の `reviewed_japanese` は空のまま（セグメントがすべて揃っている行を未翻訳と扱わない）。
- confirmed のFA行はすべて `fa_layout_approval_required = true`。
- 区切りの意味が1セグメント分ずれた行 3件は `PASS_WITH_PHRASE_BOUNDARY_NOTE` と `fa_phrase_boundary_note` を付けた（固有名を1行に保つため等）:
  - #44: Science Society(かがくきょうかい)を1つの語として保つため、『Society』を含む語をE4側に置いた
  - #63: Flower Paradise(フラワーパラダイス)を1つの語として保つため、『Paradise』を含む語をE0側に置いた
  - #137: 日本語の語順に合わせ、『しごとの たいか(for your service)』をE8側に置き、『ぎむが あります(obligated)』をE9側にした

## 13. 制御の境界

- confirmed 93件の境界: FE 153、FB 126、FA 67。数と順序は原文と同じ。
- 色トークン、ボタンアイコン（`\btn02` / `\btn03` / `\btn04`）、ポーズ（`\.` `\CC0818` `\CC0820`）、引用符（`\qo` / `\qc`）、`[player]` は、原文と同じセグメントの同じ順序に残した。
- 意図しない変更0、`CONTROL_BOUNDARY_REVIEW_REQUIRED` で保留した行0、バッファが改行をまたぐ並びの変更0。
- 色トークンが改行をまたぐ行: #63、#75（原文でもトークンは同じセグメントにあり、色の範囲が次の行に続く）。#123 はポーズで区切った『フー…パ』。

## 14. 文字とcharmap

- 漢字0。confirmed 93件すべて日本語PCSでエンコード可能（エラー0）。使えない記号は使っていない（括弧、ヴ、全角記号、ダッシュなど）。『、』『…』『ー』『！』『？』『。』は使用。
- #93（`Sankren fimbulvetr!`）は造語の呪文に見えるため、意味を推測せず元のスペルを残した。かなに音写すると発音の推測が入るため。ここだけラテン文字が残る。
- 静的な幅の最大は210px。画面の物理幅240pxを超える行は0。dialogueの幅は実機で未確認のため `width_runtime_unverified` を警告として付けた。209〜210pxの行が16行ある。

## 15. 検証

- 142 IDの一致、重複0、欠落0、原文 / 既存候補 / hold理由 / 制御メタデータ / protected token / 話者信頼度の不変、PROVENグループの非分割、制御トークン列の一致、FAの数と順序の一致、漢字0、PCSエンコードエラー0、承認語の欠落0、JSONの読み込み。
- 既存のpytestは `.venv/Scripts/python.exe -m pytest -q` で実行した（結果は最終報告に記載）。

## 16. Codexに渡せる候補

**93件**（confirmed）。ROMへの注入可は意味しない。技術統合では次を確認すること: 再配置が必要な7件、FA行（`fa_layout_approval_required`）、`official_name_verification_required` の行、幅の実機確認。

## 17. Batch 03への引き継ぎ（口調）

- `ja_phase6_cleanup_batch02_voice_audit.json` を同じ形式で使い回せる。
- PROVENグループは分割せず同時に見る。PROVEN ≠ CONFIRMED_VOICE。profileの信頼度は維持する。
- UNKNOWN / PLAUSIBLE は英語の態度だけを反映する。一人称は原文に根拠がなければ置かない。
- 同じ英語の行には同じ日本語を当てる（例: 『Wonderful, wonderful.』→『ありがたい、 ありがたい。』）。話者が別の可能性があるので、口調を人物像でそろえない。
- バッファは `[player]` 以外は証拠がなければ保留。FAは全セグメントを翻訳するか、全セグメントを空のままにする。
- 日本語の1行は静的に210px以内を目安にした（かな約20字）。

## 18. 保留しなかった判断で注意が必要なもの

- #112 のブラックナットレイ、#80 のスーパーキューブ、#77 のクロバットマンは、公式名が確認できないまま既存方針に沿った訳語を置いた（警告付き）。
- #67 の『Roar』は、わざ名か一般語か不明のため一般語『ほえごえ』にした。
- #99 の『TMs』は4 byteのスロットに対し『わざマシン』は長く、再配置が必要。
