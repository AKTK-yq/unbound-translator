# Phase 6C-3B: NPC Voice Profile / Dialogue Style Review

話者ごとの口調設計と、既存日本語訳の改善案を作る工程。**レビューのみ**で、ROM、翻訳JSON、glossary、injector、controlfixは変更していない。かなのみ。commit / pushなし。

再生成: `python scripts/build_ja_phase6_voice_review.py`（出力は下記2つのfixture）。

## 入力と対象

- 入力: `out/phase6/ja_phase6_voice_review_for_claude.json`（56グループ、120件）。Phase 6C-3Aのspeaker attribution、canon候補、handoff v3、適用済みJSONを参照。
- 120件の内訳: 適用済み112、未翻訳でholdのまま8。
- 1グループ＝1つのtrainer ID。複数のtrainer IDを一つの人物にまとめたものはない。同じ名前でもIDが違えば別グループ。
- 本人確認は全グループで **trainer IDの結合（PROVEN）** のみ。公式既存キャラクターの本人確認は0件。日本語版の口調資料は未採集。したがって「原作口調を再現した」という主張はしていない。

## 結果

| 項目 | 数 |
|---|---:|
| レビューしたspeaker group | 56 |
| レビューしたentry | 120 |
| CONFIRMED_VOICE | 1（Bram） |
| PROVISIONAL_VOICE | 31 |
| NEUTRAL_ONLY | 22 |
| INSUFFICIENT_EVIDENCE | 2（Jody、Gogh） |
| 既存訳の変更提案 | 4 |
| 変更不要 | 108 |
| 未翻訳でholdのまま（提案なし） | 8 |
| 公式キャラクターの口調を適用した数 | 0 |
| うち要technical review | 0 |

CONFIRMED_VOICEの条件は、同じtrainer IDの4行以上で観察できる態度が一貫していること。Bramは「闇の怒り」を芝居がかって語る態度が4行で一貫している。確定したのは**話し方**であり、性別・年齢・一人称は確定していない。
Daniel / Renee / Sarahなどは4行あるが、タイプ宣言の定型文なので個人の口調とは言えず、PROVISIONALに留めた。Marlonは2行、Ivoryは1行しかなくPROVISIONAL。Unbound固有の人物としての分類（出典の確度はPLAUSIBLE）はPhase 6C-3Aのまま維持した。

## 既存訳の変更提案（4件）

意味、固有名詞、制御コード、改行数は変えていない。いずれも既存スロットに収まり、画面幅は240px未満。

| entry | 現行 | 提案 | 理由 |
|---|---|---|---|
| `scr_1F02029` Daniel | とくせいの ほのおタイプで… | とくしゅこうげきの ほのおタイプで… | 『とくせい』はポケモンの「とくせい（アビリティ）」と同じ語で誤解される。同型の定型文が『ぶつりこうげきの あくの いかり』と書いているので揃える。『special』を特殊攻撃寄りと解釈する前提（confidence: medium） |
| `scr_1F02145` Sarah | くさタイプは やくに たたなかった。 | くさタイプは たすけてくれなかった。 | 直前の台詞『しょうりに みちびいてくれる』（help）と対応させる。『やくに たたなかった』は原文より辛辣 |
| `scr_740753` Liam | あなたが ママなの？ | もしかして ママ？ | 二人称『あなた』は根拠がなく、子どもの人違いには硬い。人称を省いて意味を保つ |
| `scr_1F06A82` Koji | こてんぱんに してあげる！ | こてんぱんに してやる！ | 『してあげる』は恩恵の言い方で、Roughneckクラスの威嚇と合わない。Daniel等の挑発文と揃える |

`reason`、`speaker_evidence`（trainerbattle operandの位置）、`control_validation`（制御トークン列、保護トークン、改行数、バイト数、スロット、行ごとのpx）、`charmap_validation`、`confidence`、`change_risk`、`requires_technical_review` を各候補に保存した。

## 変更しなかった理由

108件は既訳が原文の調子に合っており、変更は無意味な差分になる。口調のためだけの変更を大量に作らないという方針に従った。次の3件は検討して据え置いた。

- `scr_74BFC6`（Ivory）: 『まけなかったのに』は原文『you would've lost』のやや弱い言い換えだが、意味は通る。
- `scr_1F0207D`: 擬音『ブクブク』の解釈が割れる。根拠がない。
- `scr_1F0B02C`（Gogh）: 『しゃしん』という媒体を断定している可能性があるが、場面が未確認。

## 一人称・二人称・性別の扱い

- 全56プロファイルで、一人称と二人称の値は **null（未確定）**。現行訳で使われている『わたし』『きみ』などは参考値として `observed_in_current_japanese` に記録しただけ。
- 『きみ』は主人公への一般的な呼びかけとして残っている。話者固有の二人称とは扱わない。
- 性別・年齢を示す語尾は追加していない。『Youngin』『Oh, my goodness』『this dude』などは呼びかけや感嘆の手がかりとして記録したが、年齢・性別の確定には使っていない。

## PLAUSIBLE / UNKNOWN

- **PLAUSIBLE 38件**: すべて「近くのオブジェクト・script」から候補を絞っただけで、話者の本人確認は未了。`plausible_pool` に、原文の言い回しから読める**傾向の提案**だけを入れた（PROVISIONAL 35、NEUTRAL_ONLY 3）。提案は他のentryへ波及させない。例えば『I am Véga』と本文で名乗る `scr_1F1653E` も、本人確認を昇格させていない。
- **UNKNOWN**: 会話候補372件、非会話147件。キャラ付けはしない。原文の気分（元気・怒り・説明・皮肉・驚き・落胆）に合わせて文末を選び、全員を同じ無機質な敬語に揃えないための規則と、原文の手がかり件数（感嘆符168、疑問符85、間のトークン126、くだけた語彙19など）を `unknown_pool` に記録した。老人語・女性語・方言は、原文に根拠がなければ足さない。
- 未翻訳の8件（Dave、Roger、Reed、Carly、Jodyの各行）は翻訳しない。口調の目安はプロファイルにだけ記録した。RogerとReedは同じ趣味の対立相手だが、別のtrainer IDなので統合していない。

## 公式キャラクター

- 名前が本編の人物と同じ（Lucas、Larry、Marlon、Nate、Aaron）グループには、同一視しない旨を `prohibited_assumptions` に入れた。これは記憶に基づく注意喚起で、同一性の証拠ではない。
- 本人確認に必要な3点（本人確認、出典作品、日本語版の口調資料）は揃っていない。資料が揃うまで、原作口調の適用は行わない。

## 範囲外の観察（変更していない）

`out_of_scope_observations` に記録した。

- `scr_1F0AECE`: 『フロストマウンテン』は承認済みglossaryの『フロストやま』と異なる。
- `scr_1F0B076`: 『ルート8』は文中のRoute表記で、glossaryの Route [N]=[N]ばんどうろ は map_names 限定のため方針確認が必要。
- `scr_1F0B284`: 末尾の『!』が半角。
- 『きみ』の使用: 方針上の慣例として残す。

## 検証

- speaker group数一致（56）、entry ID欠落0、重複0。
- identity confidence維持（全件PROVEN、昇格0）。公式キャラクター誤認0。根拠なしの一人称確定0。複数trainer IDの統合0。
- 提案4件: 制御トークン列の一致、保護トークンの一致、改行数の一致、漢字0、日本語文字表でエンコード可、承認済みglossaryの語は不変。
- 適用済み翻訳JSON（2,261件）は未変更。pytest 全PASS、`py_compile`、`git diff --check` も確認。
- 実機表示は未確認。

## 次の工程

PLAUSIBLEの本人確認（map group/index、オブジェクトと台詞の結合）、日本語版口調資料の採集、4件の提案の採否判断。採用する場合は、controlfixとinjectorを通す別工程で行う。
