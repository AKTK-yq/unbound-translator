# Phase 6C-3C: NPC Voice Rewrite Technical Integration

判定: **3件適用、1件保留**。基準 `out/unbound-ja-phase6-cleanup-glossary.gba` の2,261件のうち、変更提案4件だけを検査した。基準ROM・元ROM・既存の統合翻訳JSON・glossaryは上書きしていない。新ROMはローカル専用 `out/unbound-ja-phase6-voice-pass1.gba`。569件の翻訳キューには進んでいない。

## 4件の判定

| Entry / 話者 | 元の英語・意味 | 判定 / 訳文 | ROM offset、slot、pointer owner | PCS / 幅 |
|---|---|---|---|---|
| `scr_1F02029` Daniel | “My special [green]Fire[blue]-types will burn\nyou to a crisp!” の **special** は「特殊攻撃の能力値」を明示していない。既存の「とくせいの」も誤解の余地があるが、「とくしゅこうげきの」は別のゲームプレイ上の断定を加える。「とくこう」も同じ理由で不採用。 | **HOLD**、既存訳のまま。文脈を追加確認してから別案を審査する。 | `0x01F02029` / `0x09F02029`、54 byte、owner `0x01E68A9E` | 提案40 byte、169/105px。機械的には収まるが意味判定で保留。 |
| `scr_1F02145` Sarah | “My Grass-types didn’t help me.”。同じtrainer IDの前文 `scr_1F02118` は “will help me win!”。`help` の対応を保ち、既訳「やくに たたなかった」より原文の含みが近い。 | **APPLY**「くさタイプは\nたすけてくれなかった。」 | `0x01F02145` / `0x09F02145`、31 byte、owner `0x01E68B11` | 23→23 byte、60/109px。 |
| `scr_740753` Liam | “Are you my mommy?”。硬い「あなた」を削り、「もしかして ママ？」で相手への問いを保持。 | **APPLY**「もしかして ママ？」 | `0x00740753` / `0x08740753`、18 byte、owner `0x00741343` | 15→14 byte、89px。 |
| `scr_1F06A82` Koji | “I’m going to rough you up!” は威嚇。「してやる」は恩恵を表す「してあげる」より合う。 | **APPLY**「こてんぱんに してやる！」 | `0x01F06A82` / `0x09F06A82`、27 byte、owner `0x01E6AAA1` | 18→17 byte、115px。 |

ROM offsetのGBAアドレスは `0x08000000` を加えた値。全4件の基準ROMスロットは既存controlfixed JSONをPCSでエンコードしたバイト列と一致し、ownerの4 byteは元ROM・基準ROM・新ROMで一致した。Claude fixtureの英語原文は元ROMのPCS decodeとも一致した。

## 制御、文字表、renderer

- 4案とも漢字0、日本語PCS encode可能。現行訳と提案訳で `[japanese]` / `[latin]`、FE/FA/FB、FC/FD、色指定、protected tokenの列は同一。今回の実エントリでFA/FB/FDは使われていない。SarahのFE改行位置は句の境界へ移るが、FEの数は1のままで、前後関係と意味は保たれる。
- 4件の英語原文に対する現在の `glossaries/ja.json` のentry-scoped matcherはヒット0。ほのお／くさ等の既存表記と色controlは、提案前後で保持した。正式用語との新しい対応付けはこの口調工程で作らない。
- 既存訳3件を `006_decontrolfix_translations.py` と同じ `clean_translation` で編集可能な形に戻し、Claude提案を入れて通常の `004_controlfix_translations.py` を2回実行。1回目・2回目とも `changed=0`、`remaining_control_mismatches=0`、出力JSONは入力と完全一致。レイアウトを自動調整した結果を黙認していない。
- 対象は `trainerbattle` text operand。CFRUの [trainerbattle13 macro](https://github.com/Skeli789/Complete-Fire-Red-Upgrade/blob/master/xse_commands.s) はmode 13をmode 0と同形のintro/loss pointerとして定義する。FireRedの [trainer intro → ShowFieldMessage](https://github.com/pret/pokefirered/blob/master/src/battle_setup.c) は経路解釈の参考で、Unbound自身の全mode分岐を実機トレースした証明ではない。
- Unbound ROMのfield text window templateは `0x003A73BC` / `0x083A73BC` に `00 02 0F 1A 04 0F 98 01`（26×4 tiles、内側の物理横幅 **208px**）。ROM `0x0006FB22` の `InitWindows` call直前のliteral ownerは `0x0006FB38` / GBA `0x0806FB38`。Battle message windowは `0x00248330` / `0x08248330` の28×4 tiles、printer `0x003FEB64` / `0x083FEB64` のx=2・font 2で物理幅 **222px**。各値は [既存renderer調査](ja-phase6-renderer-widths.md) と今回のROM byte再照合に基づく。
- intro/lossの実際の描画先の全分岐および最後のglyphの右端マージンは未実測。今回は候補の全行が両方の物理幅の小さい側208pxを十分下回り、さらに **そのentryの元英語の最大行幅以下** で、動的bufferもないことを採用条件にした。Sarahは最大109px（元英語166px）、Liamは89px（元英語101px）、Kojiは115px（元英語148px）。「240px未満」だけでは承認していない。mGBAでの視認は別途必要。

## Glossary不一致（監査のみ）

- `scr_1F0AECE`: 英語原文に **Frost Mountain**、既訳に「フロストマウンテン」。承認済み「フロストやま」は `scripts` の **`scr_1F0A708` のみ** へentry-scoped適用。英語の地名は同一表記だが、その承認scopeを無断拡大しない。今回変更0。
- `scr_1F0B076`: 英語原文に **Route 8**、既訳に「ルート8」。`Route [N] → [N]ばんどうろ` は `map_names` 限定で、この `scripts` entryにはmatcherがヒットしない。本文への適用方針は別途審査。今回変更0。

機械可読の個別判定、scope検証、幅、ポインタ、制御、diff全offsetは `tests/fixtures/ja_phase6_voice_integration_audit.json` に保存した。

## 注入と全バイナリ差分

基準ROMから3件のみを入力にして `--fail-on-no-space` のdry-run、その後に同じ入力でbuildした。両mapのstatsは一致: input 3、in-place 3、relocation 0、pointer write 0、used free bytes 0、encode error 0、pointer mismatch 0、implausible pointer 0、no-space 0、truncation 0、missing relocation 0、runtime patch 0、graphics patch 0。

新ROMと基準ROMはともに32 MiB。異なるのは **24 byte** で、すべて以下の3つの元スロット内。pointer bytes、保留Danielのスロット、その他2,258件の本文、その他のROM領域は不変。想定外差分0。

| Entry | 変更されたROM offset（両端を含む） | 変更byte数 |
|---|---|---:|
| Liam | `0x00740755–0x0074075A`, `0x0074075C–0x00740760` | 11 |
| Sarah | `0x01F0214D–0x01F02153` | 7 |
| Koji | `0x01F06A8D–0x01F06A92` | 6 |

基準ROM SHA-256 `3cd6d07baa4c287e10dab9d0a04960455311d6ee829e189abc57940040af638a`。新ROM MD5 `45915b5cdb4898b608ffa451bcfe8c64`、SHA-256 `68a6fecdbcf48a70d2e17cebc4c747a4095cfa242b8fc963e17a82722a68bc55`。元の英語ROM MD5 `9cad8e771940e7f7094d13911552cef0`。

## 再現手順

```bash
python scripts/build_ja_phase6_voice_integration.py prepare
python 004_controlfix_translations.py out/phase6/ja_phase6_voice_pass1_input.json -o out/phase6/ja_phase6_voice_pass1_controlfix.json --source out/unbound-texts.json --target-lang ja --report out/phase6/ja_phase6_voice_pass1_controlfix_report.json
python 004_controlfix_translations.py out/phase6/ja_phase6_voice_pass1_controlfix.json -o out/phase6/ja_phase6_voice_pass1_controlfix_twice.json --source out/unbound-texts.json --target-lang ja --report out/phase6/ja_phase6_voice_pass1_controlfix_twice_report.json
python 005_hybrid_injector.py out/unbound-ja-phase6-cleanup-glossary.gba out/phase6/ja_phase6_voice_pass1_controlfix.json -o out/unbound-ja-phase6-voice-pass1.gba --target-lang ja --map-output out/phase6/ja_phase6_voice_pass1_dry_run_map.json --dry-run --fail-on-no-space
python 005_hybrid_injector.py out/unbound-ja-phase6-cleanup-glossary.gba out/phase6/ja_phase6_voice_pass1_controlfix.json -o out/unbound-ja-phase6-voice-pass1.gba --target-lang ja --map-output out/phase6/ja_phase6_voice_pass1_map.json --fail-on-no-space
python scripts/build_ja_phase6_voice_integration.py audit
python -m pytest
```

`prepare` は事前に基準ROM SHA-256、元ROM MD5、4件の現行スロットとownerを検査する。`audit` は全32 MiBをbyte単位で比較し、承認3スロット以外に1 byteでも差分があれば失敗する。ROMと `out/` の作業JSON/mapはGit対象外。新訳・glossary変更・commit・pushは行っていない。
