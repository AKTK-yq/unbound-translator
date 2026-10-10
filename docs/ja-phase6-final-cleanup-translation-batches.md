# Phase 6C-4A: Final Cleanup Translation Batch Preparation

翻訳・文脈確認キュー569件を、Claude向けの4バッチへ分割した。**分割と情報の付与だけ**で、翻訳、ROM生成、既存訳の修正、glossary更新、話者の判定変更は行っていない。かなのみ。commit / pushなし。

再生成: `python scripts/build_ja_phase6_cleanup_batches.py build`（検証だけなら `validate`）。

## 既存ファイルの保護

- 作成前に、成果物9パスがすべて未作成であることを確認した。
- 生成スクリプトは、`metadata.phase == "6C-4A"` を持つ自分の成果物以外には書き込まない。JSONでない既存ファイルや、別工程のJSONを見つけると `FileExistsError` で止まる（テストで確認）。
- 保護対象は読み取りだけで、内容のハッシュを manifest に記録した。`scripts/build_ja_phase6_voice_integration.py`、`tests/test_ja_phase6_voice_integration.py`、`out/unbound-ja-phase6-voice-pass1.gba` は変更していない。
- 既存ファイルの上書きは **0件**。

## 入力検証（569件）

| 項目 | 結果 |
|---|---|
| ユニークID / 重複 / 欠落 | 569 / 0 / 0 |
| CLAUDE_TRANSLATION / CLAUDE_CONTEXT | 302 / 267 |
| 適用済みJSON（2,261件）との重複 | 0 |
| inventory v3 で適用済みのもの | 0 |
| inventory v3 とのclass不一致 | 0 |
| 基準ROM・voice pass1 ROM のスロットが元ROMと違うもの | 0 |

適用済みの混入は見つからなかったので、除外した件数もない。

## 4バッチ

分割は決定論的で、乱数、時刻、ハッシュ種を使わない。同じ入力から同じファイルが出る（再生成してバイト一致を確認）。

1. **Batch 01**: 話者のない行（NON_DIALOGUE）すべて。(category, ROM offset, id) の順。
2. **Batch 02〜04**: 会話（`scripts` 422件）。`conversation_id` または `dialogue_group_id` を共有する行を1つの単位にまとめ（238単位）、最も小さいROM offsetの順に並べて、3等分に近い位置で切る。単位の途中では切らない。

| Batch | 件数 | 内容 | TRANSLATION / CONTEXT |
|---|---:|---|---|
| 01 | 147 | 戦闘メッセージ78、技説明10、メニュー・設定・図鑑・アイテム等 | 58 / 89 |
| 02 | 142 | 会話。PROVEN 9、PLAUSIBLE 29、UNKNOWN 104 | 61 / 81 |
| 03 | 140 | 会話。PROVEN 3、PLAUSIBLE 8、UNKNOWN 129 | 78 / 62 |
| 04 | 140 | 会話。PLAUSIBLE 1、UNKNOWN 139 | 105 / 35 |
| 計 | **569** | | **302 / 267** |

目安は各140前後で、実際は 147 / 142 / 140 / 140（許容範囲は120〜160）。

## 話者と口調

- 同じ `dialogue_group_id` の行は必ず同じバッチに入る。PROVENの9グループはすべて未分割（Batch 02 に7、Batch 03 に2）。さらに、同じ会話に属する行も分けていない。
- PROVEN 12件の口調情報の付き方:
  - 参考のみ（PROVISIONAL）: 5件（Dave、Roger、Reed）。本人固有の口調として強制しない旨を明記。
  - 中立のみ: 1件（Carly）。口調の手がかり不足: 2件（Jody）。
  - 56グループのvoice reviewに入っていない: 4件（Kenlawa、Anthony、一般NPC2）。profileなしで中立。
  - 承認済み口調（CONFIRMED_VOICE）が付く行は、このキューには0件。
- PLAUSIBLE 38件: 近接オブジェクトから見た候補であることを明示し、傾向の提案を参考として付けた。同一人物とは断定せず、他の行へ波及させない。
- UNKNOWN 372件の会話: 原文の気分の手がかり（感嘆符、疑問符、間のトークン、`please`、くだけた語彙、`[player]`）を付けた。根拠のない一人称、性別語尾、方言、老人語を足さない指示つき。
- NON_DIALOGUE 147件: NPC口調profileは適用しない。
- 公式キャラクター: 本人確認は0件のまま。全行に `official_character_proven: false` を付け、名前一致は本人の証拠にならないこと、原作日本語版の口調には「本人確認・出典作品・日本語版の口調資料」が必要なことを明記した。

## 各entryに付けた情報

元の入力フィールドは削除も変更もしていない（全569件で元フィールドとの完全一致をテスト）。追加したのは次のとおり。

- バッチ情報: `cleanup_batch`、`batch_position`（既存の `batch` は元のPhase 6バッチ番号のまま）。
- `previous_japanese_candidate`（既存 `candidate` の写し）、`current_hold_reason`（hold理由、前の主なhold、副次的なhold）、`claude_task`（作業区分、許される結果3種、制御をまたぐ語順変更が必要なときの扱い）。
- `translation_source`、`protected_tokens`、`placeholders`、`source_control_structure`（制御の数、境界の順序、ROM由来の表示セグメント、スロット、fixed / no_relocation）。
- `buffer_metadata`（トークンごとの状態。型が確定しているもの、holdのもの、未確定のもの）。
- `approved_glossary_terms`（scope、entry_ids、global_replace）、`glossary_matcher_hits`、`unresolved_glossary_warnings`。
- `speaker_id`、`speaker_confidence`、`voice_application`、`voice_profile`、`speaker_group_context`、`translation_risk`（low / medium / high と理由）。
- FA行（206件）: `translation_units`（ROM由来のセグメント）、`fa_placement_policy: require_segments`、`fa_output_contract`。FAの追加・削除・移動は禁止で、セグメントごとに訳す。

## glossary

統合済みの292語を使う。Phase 6Cの153語はすべて `global_replace=false`（テストで確認）。承認語は元の `glossary.approved_terms` と一致し、未解決語の警告も元と一致する。部分文字列の一致での自動適用は無い。`glossary_matcher_hits` は照合結果の参考情報にとどめた。

## 共通のstyle handoff

`out/phase6/ja_phase6_cleanup_translation_style_handoff.json` に次を入れた。

- かなのみ、漢字禁止。文字表の探査結果（`、` は使える。`ヴ` `「」` `：` `〜` `()` `%` `=` `+` は使えない）。
- ポケモン本編らしい自然な口調。意味とイベント条件は変えない。公式名称を記憶だけで確定しない。
- 話者の信頼度ごとの扱い（PROVEN、CONFIRMED / PROVISIONAL、PLAUSIBLE、UNKNOWN、NON_DIALOGUE）。一人称・二人称は原文か承認済みprofileが要求するときだけ。
- 制御、バッファ、FAの契約。未確定のバッファは推測せず `needs_context`。制御をまたぐ語順変更が必要なら `needs_technical_fit`。
- 幅が実機未確認だけでは翻訳を止めない（Codexが後工程でtechnical fitを確認）。ただし意味は削らない。
- 返却の形式（`confirmed` / `needs_context` / `needs_technical_fit`、FAは `segments`）。過去のバッチと同じ形式。
- 過去の失敗例、助数詞、未解決のglossary語。

## 検証

- 569件がそれぞれちょうど1回割り当て。重複0、欠落0。各バッチは120〜160件。
- PROVENのグループは未分割。元の英語、前回の日本語候補、hold情報、制御、protected tokenは不変。
- 翻訳は1件も作っていない（`reviewed_japanese` を持つ行は0）。
- voiceの信頼度は維持。未解決の文脈を自動で解決した行は0。
- 全JSONが読み込める。再生成の結果はバイト一致。
- 実機表示は未確認。Batch 01の翻訳には着手していない。

## 生成物

- `out/phase6/ja_phase6_cleanup_batch01〜04_for_claude.json`、`out/phase6/ja_phase6_cleanup_translation_style_handoff.json`（`out/` はローカル生成物）
- `tests/fixtures/ja_phase6_cleanup_batch_manifest.json`（分割規則、入力のハッシュ、保護ファイルのハッシュ、各バッチのID一覧）
- `scripts/build_ja_phase6_cleanup_batches.py`、`tests/test_ja_phase6_cleanup_batches.py`、本ドキュメント
