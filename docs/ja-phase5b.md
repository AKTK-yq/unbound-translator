# 日本語 Phase 5B: Claude レビュー750件の技術統合

これは全文翻訳やruntime PASSではなく、かな限定の**技術検証ROM**である。`out/unbound-ja-phase5b.gba` は私的ローカル成果物で、commit・配布・BPS化しない。mGBAでの人間による画面確認は未実施。

## 開始状態と再現手順

- Branch: `japanese-support`; HEAD: `490279c8dfe06b7da5a3f5eac0369cb24acf12d4`。
- 開始時 `python -m pytest`: 227 passed。開始時のdirty/untrackedファイルは保持した。
- 元ROM `rom/unbound.gba`: MD5 `9cad8e771940e7f7094d13911552cef0`。終了時にも同じMD5。
- 入力は `tests/fixtures/ja_phase5_selection.json`、`ja_phase5_claude_review.json`、`ja_phase5_glossary_review.json`、`ja_phase5_runtime_subset.json`。既存 `out/ja-phase5a-prepared.json` は通常のextract→prepare成果物。

```text
python scripts/build_ja_phase5_reviewed.py merge
python 004_controlfix_translations.py out/ja-phase5-reviewed-input.json -o out/ja-phase5b-controlfix.json --source out/ja-phase5a-prepared.json --target-lang ja --report out/ja-phase5b-controlfix-report.json
python 004_controlfix_translations.py out/ja-phase5b-controlfix.json -o out/ja-phase5b-controlfix-twice.json --source out/ja-phase5a-prepared.json --target-lang ja --report out/ja-phase5b-controlfix-twice-report.json
python scripts/build_ja_phase5_reviewed.py evaluate --controlfixed out/ja-phase5b-controlfix.json
python 005_hybrid_injector.py rom/unbound.gba out/ja-phase5b-resolved.json -o out/unbound-ja-phase5b.gba --target-lang ja --dry-run --fail-on-no-space --map-output out/ja-phase5b-strict-dry-map.json
python 005_hybrid_injector.py rom/unbound.gba out/ja-phase5b-resolved.json -o out/unbound-ja-phase5b.gba --target-lang ja --fail-on-no-space --map-output out/ja-phase5b-map.json
python scripts/audit_ja_phase5b.py rom/unbound.gba out/unbound-ja-phase5b.gba out/ja-phase5b-resolved.json out/ja-phase5b-map.json --report out/ja-phase5b-binary-audit.json
python scripts/build_ja_phase5_reviewed.py subset --map out/ja-phase5b-map.json
```

`out/ja-phase5-review-audit.json` は元のreview rowを `review_warning`・`candidate_japanese` を含めて保持する。`out/ja-phase5b-unresolved.json`、`out/ja-phase5b-fixed-audit.json`、`tests/fixtures/ja_phase5_fit_review.json` に個別判定を記録した。`glossaries/ja.json` は変更していない。

## 入力検証と適用

| Status | 入力 | 日本語適用 | 英語維持 | 主な理由 |
| --- | ---: | ---: | ---: | --- |
| confirmed | 512 | 497 | 15 | 幅7、図鑑分類3、pointer ownership4、Latinの `L=A` 1 |
| existing_official | 106 | 94 | 12 | 公式type固定slot超過9、図鑑分類3 |
| needs_technical_fit | 16 | 5 | 11 | Aそのまま3、B再配置2、C固定slot超過11 |
| needs_context | 116 | 0 | 116 | 未確定。candidateも適用しない |
| **合計** | **750** | **596** | **154** | technical unresolved **37** + context 116 + Latin unchanged 1 |

ID重複、selection外ID、欠落ID、original/category差異、protected/control token差異、漢字、未対応status、適用訳のcharmap encode errorはすべて0。`existing_official` 106件はselection内のPokeAPI `ja-hrkt` 値とClaude側の値が一致した。`confirmed` 78件に仮カナ固有名詞があり、さらにtechnical-fit適用1件にも候補があるため、暫定表記の適用entryは計79件。glossary候補78語は全件 `official_confirmed: false` のまま。候補語数と使用entry数は別の尺度である。

`tbl_menu_options_00017_419E4B` はClaudeが原文と同じ `L=A` を確定値とした。日本語ページに `=` glyphがないため、既存Latin ROM文字列をそのまま維持した。これは日本語適用件数に入れない。

## controlfixと16件のtechnical fit

初回は633候補にページ制御を付け、253件を折返し、control sequenceを6件修復した。初回の `[buffer1]` 重複2件は `004_controlfix_translations.py` の先頭buffer補修を修正して解消。最終結果はcontrol mismatch **0**、2回目の変更 **0**、2出力はbyte-for-byte同一。FE/FA/FB/FC/FD、動的buffer、placeholderは元のsemantic token数と一致。`[japanese]`/`[latin]` はcontrolfix後に追加され、動的buffer周辺ではLatinへ戻る。

| 分類 | 件数 | 処理 |
| --- | ---: | --- |
| A: そのままfit | 3 | 適用 |
| B: pointer所有の再配置 | 2 | 適用 |
| C: 固定/no-relocation overflow | 11 | 英語維持、短縮案は自動適用しない |
| D: pixel widthのみ | 0 | 該当なし |
| E: whitespace/layoutのみ | 0 | 該当なし |

16件それぞれの原文・訳文・byte数・slot・pixel幅・renderer上限・再配置可否・分類は `tests/fixtures/ja_phase5_fit_review.json` に収録。`proposed_shorter_japanese` は全件null。未承認の短縮訳は作っていない。既知のmove-description行幅122pxを超えた別のconfirmed 7件も安全側で英語維持した。実画面で幅上限が異なる可能性は未確認。

## review_warning 15件の個別監査

| ID | 判定 |
| --- | --- |
| `scr_1F0F842` | Phase 4未確定。needs_contextのため英語維持 |
| `scr_1F10323` | Phase 4未確定、Vanilla/Difficult表記を含む。英語維持 |
| `tbl_mission_log_00017_1F560DA` | Phase 4未確定。英語維持 |
| `tbl_type_names_00000_A4EAD4` | 公式ノーマル 9/7 bytes。英語維持 |
| `tbl_type_names_00001_A4EADB` | 公式かくとう 9/7 bytes。英語維持 |
| `tbl_type_names_00002_A4EAE2` | 公式ひこう 8/7 bytes。英語維持 |
| `tbl_type_names_00004_A4EAF0` | 公式じめん 8/7 bytes。英語維持 |
| `tbl_type_names_00007_A4EB05` | 公式ゴースト 9/7 bytes。英語維持 |
| `tbl_type_names_00008_A4EB0C` | 公式はがね 8/7 bytes。英語維持 |
| `tbl_type_names_00010_A4EB1A` | 公式ほのお 8/7 bytes。英語維持 |
| `tbl_type_names_00015_A4EB3D` | 公式こおり 8/7 bytes。英語維持 |
| `tbl_type_names_00016_A4EB44` | 公式ドラゴン 9/7 bytes。英語維持 |
| `tbl_pokedex_species_00000_1A35814` | `Seed` → `たねポケモン`、11/12 bytes。接尾語未確認で英語維持 |
| `tbl_pokedex_species_00001_1A35838` | 同上。英語維持 |
| `tbl_pokedex_species_00004_1A358A4` | `Flame` → `かえんポケモン`、12/12 bytes。英語維持 |

Unbound ROMの分類欄は `Seed` のみ（例: ROM `0x01A35814` / GBA `0x09A35814`）。[pret/pokefirered の `DexScreen_PrintMonCategory`](https://github.com/pret/pokefirered/blob/master/src/pokedex_screen.c) は分類文字列の後ろに別の `gText_PokedexPokemon` を描く。Unbound ROM内にも独立した `POKéMON` 文字列（ROM `0x00834ACC` / GBA `0x08834ACC`）があるが、これが現行Unbound図鑑rendererの接尾語だという参照経路は未証明。よって警告3件だけでなく、同じ `〜ポケモン` 形式の分類名計6件を英語維持した。推測で接尾語を削除していない。7件目の分類名は固定slot超過で別途保留。

## 固定slot、初回dry-run、厳密build

固定slot **135** 件全件を監査。needs_context 11件は英語維持で日本語fit failureに含めない。日本語候補124件のうちbyte-fit 104、overflow **20**（通常固定17、`no_relocation` 3）。byte-fitでも図鑑接尾語未確認6件を保留し、実適用固定slotは98件。overflow20件はtype名11、battle2、menu Cube2、shop1、standalone1、saving1、start menu1、図鑑分類1。これらは `translated_fixed` で意味を削らず、英語維持。

最初のdry-runは633候補を投入した。`--fail-on-no-space` は最初の固定slot超過で期待通り停止するため、診断用に同flagなしのdry-runを再実行し、ROMを出力せずmapを取得した。結果はin-place 446、relocation 167、pointer writes 852、relocated payload 2610 bytes、実vetted FF使用2429 bytes、残量613404 bytes。固定slot超過20件は `skipped_no_space` として記録されたが、FF容量不足ではない。`missing_relocations` 0、encode/pointer mismatch/implausible/truncation/control mismatch/runtime patch/graphics patchはいずれも0。

最終厳密版は、固定超過20、move-description幅7、図鑑分類の非overflow6、owner不足4の計37件を候補から外した**596件**。`--fail-on-no-space` dry-runおよびbuild双方で、encode error、pointer mismatch、implausible pointer、missing relocation、skipped no space、固定/no-relocation truncation、ability compaction、runtime/graphics patchがすべて0。

## relocation・容量・ROM差分

| 指標 | 実測 |
| --- | ---: |
| 適用596件の原文encoded bytes合計 | 30,622 |
| 日本語controlfixed encoded bytes合計 | 21,078 |
| in-place / relocation | 433 / 163 |
| pointer writes | 829 owner fields |
| relocated payload bytes | 2,508（同一payload再利用15件を含む） |
| vetted FF実使用 / 残量 | 2,327 / 613,506 bytes |
| 最大残存span | 150,618 bytes |
| 固定 / no-relocation overflow | 20 / 3（すべて英語維持） |

Phase 5Aの粗い上側予測579 relocation・約52,488 bytesに対し、実測は163件（−416）・2,508 bytes（−49,980）。予測は未レビュー文の推定量であり、同条件の改善率ではない。destinationは全件 `lib/unbound_free_space.py` のvetted FF内、元バイトはFF、全pointer ownerは旧→新を確認。重複payloadは1つのprimary allocationと15件の参照再利用で、異なるallocation同士の重なりは0。旧slotは全件不変、適用entryの旧pointer残存0。code/font/runtime予約範囲への衝突0。

最初のbinary auditでは4件にowner一覧外の旧pointerが残った。battle message `tbl_battle_messages_00000_800880`（ROM `0x00FA6636`, `0x00FA6C32`）、`tbl_battle_messages_00002_965C16`（`0x0096552F`）、ability説明 `tbl_ability_descriptions_00000_24F3C4`（`0x0024FB08`）、script `scr_1A6211`（少なくとも14参照、例 `0x016A28A`, `0x007616E5`）。pointer周辺に同型のROM参照・table構造が見えるため偶然のbyte一致と決めつけず、4件を英語維持して再buildした。今後owner追跡が必要。

最終binary auditは **PASS**。変更byteはin-place text 28,165、relocated text 2,179、pointer write 2,871。変更byte全件がこれら3分類の所有範囲内で、unrelated byte・ASM・font・graphics・runtime patchは0。完全な差分rangeとentry別destination/ownersは `out/ja-phase5b-binary-audit.json` と `out/ja-phase5b-map.json` に保持。

出力ROM MD5 `2f1887c7959fec6159f345986521eacd`、SHA256 `73cf11be571a89696a6b8cf139fbf8104c896fd8b6c8bd21a54613c6942ab086`。

## category / renderer別件数

`failure` はneeds_contextを除いたtechnical unresolved。`fixed overflow` はfailureに内包。`menus` の差1件は既存Latinの `L=A`。

| Category group | Selected | Applied | Context | Failure | Relocation | Fixed overflow |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| scripts | 244 | 192 | 51 | 1 | 19 | 0 |
| battle | 55 | 44 | 7 | 4 | 21 | 2 |
| menus | 191 | 181 | 3 | 6 | 94 | 6 |
| missions | 60 | 41 | 19 | 0 | 10 | 0 |
| Pokémon names | 21 | 21 | 0 | 0 | 0 | 0 |
| moves | 33 | 26 | 0 | 7 | 3 | 0 |
| items | 28 | 28 | 0 | 0 | 0 | 0 |
| abilities | 24 | 23 | 0 | 1 | 0 | 0 |
| types | 16 | 5 | 0 | 11 | 0 | 11 |
| natures | 17 | 17 | 0 | 0 | 15 | 0 |
| other | 61 | 18 | 36 | 7 | 1 | 1 |

| Renderer group | Selected | Applied | Context | Failure | Relocation | Fixed overflow |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| event_dialogue | 237 | 187 | 49 | 1 | 19 | 0 |
| battle_text_printer | 55 | 44 | 7 | 4 | 21 | 2 |
| description_ui | 21 | 13 | 0 | 8 | 0 | 0 |
| menu renderers | 191 | 181 | 3 | 6 | 94 | 6 |
| mission renderers | 60 | 41 | 19 | 0 | 10 | 0 |
| name tables | 134 | 105 | 18 | 11 | 16 | 11 |
| pokedex_ui | 19 | 7 | 5 | 7 | 0 | 1 |
| unknown/other | 33 | 18 | 15 | 0 | 3 | 0 |

## mGBA runtime QA（未実施）

`tests/fixtures/ja_phase5b_runtime_subset.json` は既存80件から実適用のみ**69件**を選び、指定されたポケモン名・技名・どうぐ名/個数buffer検証のため、同じ750件selection内の適用済み3件を補足した。計**72件**。補足行には `supplemental: true` を付けた。各行に到達手順、category、renderer、controls、元ROM offset、再配置有無、確認点、到達根拠の限界を記録。ROM中のpointer ownershipはruntime表示の証明ではない。人間は以下の順に確認する。

1. 新規ゲームで導入会話を進める。キャラ・肌・髪の選択、名前入力・確認、難易度質問を両分岐で読む。`scr_1F0F89C` は再配置＋player buffer。`scr_1F0F8AD` はFB/FE。`scr_1F0FC3F` は色FCとdynamic buffer、FA/FB/FE。スクロール・ページ送り・英語名から日本語への復帰を確認。
2. 初期メニューでBag/ポケモン/PC/Option/Saveを開く。選択肢配置、固定slot、item/Pokémon名、英語buffer混在を確認。PCのどうぐ引出し `tbl_menu_item_storage_00005_4177C5` でどうぐ名と個数bufferを確認。
3. 捕獲・入手時のニックネーム質問 `scr_1A56A7` でポケモン名bufferを確認。レベルアップ時の `tbl_move_learning_00002_416DF7` でポケモン名・技名bufferを確認。通常戦闘で該当条件を作り、battle messagesを確認。`tbl_battle_messages_00017_3FB400` はFB/FD/FE。戦闘状態に依存する文は表示できなければ未確認と記録。
4. Mission Log解放後、説明・目標・タブを確認。該当ミッションの状態・解放条件は別途記録。
5. NPC長文はentryのROM script operandが確認できているが、正確なマップ/イベントの到達経路は未証明。見つからないIDをruntime PASSに含めない。
6. セーブ・ロード後も表示を再確認する。今回のROM生成自体はmGBA runtime結果を保証しない。

## 未解決と検証

- needs_context 116件は未確定のまま。technical unresolved 37件は `out/ja-phase5b-unresolved.json` を参照。固定slot20件は公式表記・意味を削らずに入れる方法の承認が必要。
- 図鑑分類の接尾語、move-description実画面幅7件、owner不足4件は追加ROM追跡またはmGBA確認が必要。owner不足はextractor/ownershipの別監査対象。
- 暫定glossary候補78語は公式未承認。runtime QA 72件は手順書であり、まだ画面確認済み件数ではない。
- `python -m pytest`: **241 passed**。変更Pythonの`py_compile`と`git diff --check`もPASS。開始時の既存dirty/untracked成果物を保持し、commit/pushしていない。
