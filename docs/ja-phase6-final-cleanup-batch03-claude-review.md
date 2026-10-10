# Phase 6C-4G — Final Cleanup Batch 03 Claude review（NPC会話）

Batch 03（140件）の翻訳レビューだけを行った。Batch 04 には着手していない。Phase 6C-4Fで扱ったFA 24件の再翻訳もしていない。既存のROM、翻訳JSON、glossary、Python、injector、controlfix、FA validatorは変更していない。ROM生成、commit、pushもしていない。かなのみ。

成果物は次の3ファイル。作業前に3つとも未作成であることを確認した。

- `tests/fixtures/ja_phase6_cleanup_batch03_claude_review.json`（140件すべて）
- `tests/fixtures/ja_phase6_cleanup_batch03_voice_audit.json`（口調の監査。Batch 04で再利用できる）
- `docs/ja-phase6-final-cleanup-batch03-claude-review.md`（このファイル）

入力は読み取りだけで使った。`review_source` は全件 `claude_cli`（この Claude Code セッションで実際に翻訳・確認した行のみ。未実施の行はない）。

## 1. 入力140件の整合性

140件、ID重複0、欠落0、manifestのID順と一致。CLAUDE_TRANSLATION 78、CLAUDE_CONTEXT 62。原文、既存候補、hold理由、制御メタデータ、protected token、話者信頼度、dialogue_group_id は入力から変えていない。全件 scripts カテゴリ。FAを含む行は76件、未確定バッファを含む行は28件。

## 2. 結果

| 区分 | 件数 | confirmed | needs_context | needs_technical_fit |
|---|---:|---:|---:|---:|
| CLAUDE_TRANSLATION | 78 | 74 | 4 | 0 |
| CLAUDE_CONTEXT | 62 | 38 | 24 | 0 |
| **計** | **140** | **112** | **28** | **0** |

confirmed は翻訳上の確定で、ROM注入の安全認定ではない。

TRANSLATION 78件のうち保留は4件（#44、#50、#137、#138）。いずれも未確定バッファ（[buffer1]）が原因。

## 3. 既存候補の扱い

| 区分 | 件数 |
|---|---:|
| previous candidate maintained（そのまま採用） | 8 |
| previous candidate revised（修正） | 11 |
| newly translated（新規訳） | 93 |
| held（保留） | 28 |

- そのまま採用: #101, #108, #113, #118, #119, #121, #126, #127（意味・段落・口調とも適切）。
- 修正した行と理由:
  - #18: ラテン文字を承認済みの語に置き換え、句読点を全角に
  - #37: 語句は保ち、助詞まわりの余分な空白だけ整理
  - #38: 語句は保ち、助詞まわりの余分な空白だけ整理
  - #39: 語句は保ち、助詞まわりの余分な空白だけ整理
  - #48: ラテン文字を承認済みの語に置き換え、句読点を全角に
  - #52: 性別や年齢を連想させる語尾を丁寧で落ち着いた口調に（意味は不変）
  - #77: ASCIIの『!』を全角に
  - #83: 不要な二人称『きみ』と語尾『だな』を外した
  - #104: 『アーサー [player]』が1つの名前に読めないよう読点を追加
  - #107: 年齢だけの老人語『わかいの』を中立の『わかい ひと』に
  - #117: 2つ目の不要な『きみ』を外した
- 意味を変えるための口調修正は1件もない。

## 4. 文脈が解決した38件と、その証拠

CONTEXT 62件のうち、未確定バッファを含まず文が単独で意味を確定できる38件を翻訳した。各行の `context_resolution` に evidence、resolved_ambiguity、remaining_risk を記録した。

| 証拠の種類 | 内容 |
|---|---|
| 未確定バッファなし | 既知は `[player]` / `[rival]` のみ |
| 承認済みglossary | 例: シャドウズ、ビジョンバッジ、ボイドいせき、してんのう、ジュエル、かたいいし |
| 公式名の検証 | PokeAPIキャッシュで検証済みのポケモン / わざ / どうぐ名（`official_names_verified`） |

`conversation_id` やROM上の近接だけでは人物を確定していない。本文中の呼びかけ（Arthur、Jax、Euler など）も、話者の同定には使っていない。

## 5. 保留（needs_context 28件）

原因は未確定の動的バッファ（`[buffer1]` 25件、`[buffer2]` 3件）と、呼びかけ語の単独entry（#68 `sweetie`）。値の型・語形・助詞との関係が入力資料で証明できないため、名詞や性別を推測していない。保留行は `reviewed_japanese` を空にし、既存候補は変更していない。

`[buffer1]` は『Hey there, [buffer1]』『young [buffer1]』『reliable errand [buffer1]』のように呼びかけ語として使われる行と、数・物の名前らしい行が混在している。同じバッファ番号でも意味が同じとは限らないため、1件ずつ判断して保留にした。

- `[buffer2]`: #9, #84
- `[buffer1]`: #11, #13, #16, #17, #21, #22, #23, #44, #45, #46, #47, #50, #61, #62, #76, #95, #97, #102, #103, #105, #133, #134, #137, #138
- `[buffer1], [buffer2]`: #19
- `(呼びかけ語の単独entry)`: #68

必要な追加情報は各行の `context_resolution.missing` に書いた。

## 6. needs_technical_fit

0件。固定・再配置不可のスロットを超える行はなく、FA / FBの待機をまたいで重要な語が動いた行もない。

## 7. 話者の信頼度と口調profile

| 信頼度 | 件数 | confirmed | needs_context |
|---|---:|---:|---:|
| PROVEN | 3 | 3 | 0 |
| PLAUSIBLE | 8 | 5 | 3 |
| UNKNOWN | 129 | 104 | 25 |

信頼度は変えていない。公式キャラクターとして確定した行は0。

PROVEN 3件は2グループ。グループは分割せず、まとめてレビューした。PROVEN は話者の同定であり CONFIRMED_VOICE ではない。profileの信頼度は変えていない。

| グループ | entry | profile | 適用 |
|---|---|---|---|
| trainer_0442（Carly・Medium） | #1 | NEUTRAL_ONLY | 同じ話者の既訳『あの なきごえは ぶきみだ』『しているんだろう？』に合わせた独白調の常体。一人称・二人称なし |
| trainer_0444（Jody・Medium） | #3、#4 | INSUFFICIENT_EVIDENCE | 中立の常体のみ。口癖や性格は足していない |

PLAUSIBLE 8件は傾向を参考にしただけで声を固定していない。UNKNOWN 129件は英語の態度だけを反映した。英語に俗語（ya / thin's / dat）や西部風の砕けた語り（Howdy / yer / ain't）が明示されている行は、方言を足さず、砕けた常体や荒い口調で表した。

## 8. 口調が良くなった行

- #52: 既存候補の『もらおうか』『ようだな』（性別・年齢を連想させる語尾）を、丁寧で落ち着いた口調に改めた。
- #83: 不要な『きみは』と『だな』を外した。
- #107: 年齢だけの老人語『わかいの』を『わかい ひと』にした。
- #117: 2つ目の不要な『きみの』を外した。

## 9. Pokémon公式名称

検証済みの名称（PokeAPIキャッシュで exact 一致）を使った行が 30件。例: ボクレー、バケッチャ、ヨノワール、サボネア、ムクバード、ムックル、タツベイ、ボーマンダ、グラードン、カイオーガ、フリーザー、サンダー、ファイヤー、フーパ、グランブル、どろぼう、つばめがえし、いわくだき、かいりき、いあいぎり、ダウジングマシン、むしよけスプレー。

`official_name_verification_required` を付けた行（公式名の断定をしていない）:

- #40 `scr_1F157E9`: titan Pokémon=タイタンポケモン
- #41 `scr_1F158DA`: Victory Road=チャンピオンロード
- #42 `scr_1F159D8`: Victory Road=チャンピオンロード
- #49 `scr_1F15FD6`: TM=わざマシン
- #56 `scr_1F1687D`: HM=ひでんマシン
- #85 `scr_1F2EF1C`: Oak=オーキド
- #86 `scr_1F2F01A`: Pokédex=ポケモンずかん
- #87 `scr_1F2F045`: Pokédex=ポケモンずかん
- #91 `scr_1F2F72C`: Cac!
- #92 `scr_1F2F759`: Sankren fimbulvetr
- #115 `scr_1F3102E`: Sankren bolganone
- #123 `scr_1F317F2`: Ravia!
- #124 `scr_1F318B2`: Shadowy reign of terror=かげの きょうふせいじ

## 10. glossary

- 承認済み語を 33回使用（31エントリ）。承認語の欠落0、scope衝突0。
- glossary本体は変更していない。`global_replace=false` の語を、同じ英語だからという理由だけで一括置換していない。
- scope外だが既存の project_standard 語に合わせて使った行が 14件（整合のための使用で、glossary適用とは数えない）。`glossary_scope_warnings` に理由を記録した。対象: Elite Four（glossaryは『Elite 4』のみ）、Champion、Pokémon League、Guardian of Borrius、Grim Woods、Mega Evolution、Route [N]、Borrius、KBT Expressway、TM、Crater Town など。
- 独立した根拠（PokeAPIで検証済み、またはglossary上のproject_standard）がある語だけを使い、根拠のない語は使っていない。

## 11. FA

FAを含む行は 76件。confirmed 63件（501セグメント）は、ROM由来のセグメントごとに訳し、FAの追加・削除・移動・結合・分割は0。保留 13件は未確定バッファのため、全セグメントを空のまま残した。

- 全体の `reviewed_japanese` は空のまま。セグメント訳が完了している行は `translated_segments` に全文を記録した（完成状況は `fa_semantic_status` と `segments` で確認できる）。
- confirmed のFA行はすべて `fa_layout_approval_required = true`。
- 各FA行に `original_segments`、`translated_segments`、`information_reveal_timing` を記録した。`information_reveal_timing` は、固有名・アイテム名・バッジ名・数値などの重要語が、原文と同じ待機区間（FA / FB の間）に出るかを機械的に確認した結果。
- `FA_SEMANTIC_BOUNDARY_REVIEW_REQUIRED` を付けた行: **0件**。重要語が待機をまたいで動いた行はなかった（動いた2行は訳を直して解消した）。
- 注意: この確認は、記録した重要語だけが対象。注記が無いことは、意味的な安全の証明ではない。ROM構造や描画の検証はCodexに委ねる。
- `FA_PHRASE_BOUNDARY_NOTE` を付けた行 10件（日本語の語順や固有名を1行に保つため、語を同じ待機区間内の隣のセグメントに寄せた）:
  - #2: 『lost in these woods』をE2側(3行目)に置いた。同じ文の続きで、FAをまたいで開示される情報の内容は変わらない
  - #5: 『Seaport City』を分割しないため、『City』と『Pumpkaboo』の位置を隣のセグメントに寄せた(同じ文内。FAは次のセグメントとの間のみ)
  - #29: 『to stumble upon the entrance to the』(E1〜E2)の内容をE3の『ボーリウスのはかの いりぐちを みなかったか？』にまとめた。固有名は最後(E3)で開示され、原文と同じ。E1〜E2は短い導入のみ
  - #31: 『in the tomb』(E8)を『はかには』としてE6側に置いた
  - #40: 『commemorate when』(E1)と『finished building』(E2〜E3)を、日本語の語順で『ひらいた』『つくりおえた』『いわう』に配した
  - #53: 『the Leader of the / Crater Town Gym』を『クレータータウンジムの リーダーです。』の1行にまとめた(同じ文)
  - #63: 『Blizzard / City』を1つの語として保つため、『ブリザードシティ』をE2側に置いた
  - #69: 『any ol' cowpoke』は『どこの だれにでも』で受けた(E17の語をE16側に置いた)
  - #98: 『at a place called the / Ruins of Void』を、日本語の語順に合わせて『あつめられる ばしょは、/ ボイドいせき。』に配した(E7〜E8)
  - #132: 『Grim / Woods』の語を1行目(E1)にまとめた

## 12. 制御と文字

- confirmed 112件の境界: FE 240、FB 204、FA 105。数と順序は原文と同じ。
- 色トークン、ポーズ（`\.` `\CC0818` `\CC0820` `\CC0830`）、引用符（`\qo` / `\qc`）、`\Lv`、`[player]`、`[rival]` は、原文と同じセグメントの同じ順序に残した。
- protected tokenの不一致0、制御の不一致0、FAの不変条件違反0。
- 漢字0。confirmed 112件すべて日本語PCSでエンコード可能（エラー0）。使えない記号は使っていない。
- ラテン文字が残る箇所: 呪文の造語 `Sankren fimbulvetr`（#92）と `Sankren bolganone`（#115）。意味や発音を推測しないため、Batch 02の #93 に準じて残した。
- 鳴き声の表記（#91 `サボ！`、#123 `バード！`）は、名前から取った推測の表現で、警告を付けた。

## 13. 幅

実機の幅は未確認。既知のfield textbox 208pxを超える静的な行は5件で、警告にとどめた: #36（217px）、#85（210px）、#118（227px）、#127（225px）、#132（210px）。うち#118と#127は既存候補をそのまま採用した行。
静的な幅の最大は227pxで、画面の物理幅240pxを超える行は0。意味を削って短くはしていない。
元のスロットより長く再配置が必要な行が2件（#91、#123）。どちらも固定・再配置不可ではない。

## 14. 検証

140 ID、重複0、欠落0、原文 / 既存候補 / hold理由 / 制御メタデータ / protected token / 話者信頼度の不変、PROVENグループの非分割、制御トークン列の一致、セグメントごとのトークン位置の一致、FAの数と順序の一致、漢字0、PCSエンコードエラー0、承認語の欠落0、JSONの読み込み。既存のpytestは `.venv/Scripts/python.exe -m pytest -q` で実行した（結果は最終報告）。

## 15. Codexに渡せる技術統合候補

**112件**（confirmed）。ROMへの注入可は意味しない。技術統合で確認すること: FA行（`fa_layout_approval_required`、とくに `FA_PHRASE_BOUNDARY_NOTE` の10件）、`official_name_verification_required` の行、幅の実機確認、再配置が必要な2件、`incomplete_pointer_ownership` を引き継いだ #99。

## 16. Batch 04への注意

- `ja_phase6_cleanup_batch03_voice_audit.json` を同じ形式で使い回せる。
- バッファは `[player]` / `[rival]` 以外は証拠がなければ保留。特に `[buffer1]` は、呼びかけ語を入れる行が多く、性別・親しさの判断が必要になる。
- 本文中の人名（Arthur、Jax、Euler、Zeph、Ivory など）を話者の同定に使わない。
- FAは全セグメントを翻訳するか、全セグメントを空のままにする。重要語（アイテム名、バッジ名、敵の正体、条件）は、FA / FBの待機をまたいで動かさない。
- 英語に俗語や方言の根拠がある行も、日本語で方言を足さず、砕けた常体や荒い口調にとどめる。
- 日本語の1行は静的に208px以内（かな約20字）を目安にした。
