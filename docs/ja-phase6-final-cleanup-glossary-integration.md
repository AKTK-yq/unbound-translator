# Phase 6C-2B: Glossary統合と安全な伝播

承認済み用語を `glossaries/ja.json` に統合し、保留entryへ伝播できるかを判定した。新規翻訳、言い換え、本文の修正は行っていない。かなのみ。commit / pushなし。

基準ROM: `out/unbound-ja-phase6-cleanup-codex.gba`（SHA-256 `9123192a…ba79`）。ソースROM MD5 `9cad8e771940e7f7094d13911552cef0`。

## 1. Glossary統合

| 項目 | 結果 |
|---|---:|
| レビュー済み語 | 208 |
| 承認（OFFICIAL 16、PROJECT_STANDARD 142、CONTEXT_SCOPED 10、KEEP_EXISTING 2） | 170 |
| 統合したglossary term（同一語・同一scopeを束ねた後） | 153 |
| 統合後の総term数 | 292（既存139＋153） |
| 既存139語 | 内容・順序とも不変 |
| 新規termの `global_replace` | すべて false |
| 新規termに `entry_ids` なし | 0 |
| 未解決・却下語のmerge | 0（Cut / Strength / Fighting も不在） |

- 既存glossaryの退避: `out/phase6/ja_glossary_pre_phase6c2b.json`。再実行は退避ファイルを基準にするので冪等。
- KEEP_EXISTING（Grunt、Shadows）は既存termを上書きせず、同じ訳で別scope（トレーナー名表、大文字始まりの組織名）の行を追加した。
- Psychicはscr_1F3394E（わざ）だけ統合。scr_1F1516B（エスパー系NPC）は未解決のまま。

### OFFICIAL扱いの再確認

過去のPokeAPI監査（`out/phase6/*official*audit*.json`）から、完全一致の証拠を機械的に再照合した（対象28行: 公式・複数形・わざ名など official_state が verified 系の行）。

| 結果 | 行数 |
|---|---:|
| 英語＋日本語が完全一致 | 12 |
| 図鑑の分類名: 英語genus「X Pokémon」＝日本語「Yポケモン」の組で一致 | 10 |
| 単数形が完全一致、複数形は機械的な複数（公式の複数形照合ではない） | 5 |
| PokeAPIのエンティティは完全一致だが、過去監査が行折り返しのためambiguous | 1（Qualot Berry） |
| 証拠なし | 0 |

要確認: **Qualot Berry=タポルのみ**。公式扱いにせず、glossary上は `status=context_scoped` と `needs_human_confirmation` を付けた。
図鑑の分類名は、表に「ポケモン」を含まない語幹を使っている。日本語側で「ポケモン」が自動で付くかは実機で要確認。

### 衝突と誤適用

- 既存glossaryとの訳の矛盾: **0**。
- 新旧glossaryを25,044件の全文に当てて比較: 新しく増えた一致は295。旧termの一致が長い新termに置き換わったのは9件で、すべて旧訳を含む（例: Antisis → Antisis City、Zeph → Zeph Jr.）。矛盾する置換は0。
- scope collision（entry_ids外への適用）: **0**。collision-risk 63語（high 48、medium 15）を含めて確認した。
- Ace / Aerial Ace、Cut、Lucky Egg、Egg、Hard、Difficult、Optionの回帰テストを追加または維持した。

## 2. 伝播判定（用語確定と注入可否を分離）

対象282 entries（語未特定の47 entriesは別枠）。

| 区分 | entries |
|---|---:|
| 用語が確定 | **245** |
| └ すでに適用済み | 11 |
| └ **安全に注入可能** | **43** |
| └ 用語は確定、技術gateで失敗 | 26 |
| └ 用語は確定、他のholdが残る | 165 |
| 未解決語が残る（blocked） | 32 |
| 偽陽性のみで用語が不要 | 4 |
| 適用済み（未解決語あり） | 1 |

「安全に注入可能」の条件（すべて満たすもの）:
- 既存のcandidate Japaneseが完全で、承認した日本語を**そのまま含む**（ラベル類は完全一致）。candidateを書き換えない。
- 残っているholdが用語系の理由だけ（`unverified_official_name`、`official_name_unresolved`、`mission_title_glossary_proposal_not_approved` など）。
- 監査された公式名が、解決済みtermで覆われている。未解決の語を含まない。
- バッファ、FA、control境界、owner/pointer、技術fit、文脈の未解決がない。
- controlfix後、source control列が不変、画面幅240px未満、スロットに収まる。

注入可能な43件の内訳: ミッション名19、図鑑の分類名10、トレーナー名5、トレーナークラス4、戦闘メニュー3、アイテム名1、アイテム説明1。すべて既存スロット内の上書き（relocationなし）。

gate失敗26件の理由: 改行のない1行の長文が画面幅を超える・source controlが変わる（25件、候補の書き直しが必要）、トレーナークラス表のスロット超過（1件。エリートトレーナー）。

## 3. 安全適用とROM

- 新ROM: `out/unbound-ja-phase6-cleanup-glossary.gba`（MD5 `16c6659980982053250be6bcf475c5cd`、SHA-256 `3cd6d07baa4c287e10dab9d0a04960455311d6ee829e189abc57940040af638a`）。過去ROMは上書きしていない。
- controlfix: `--target-lang ja`。2回目の出力はバイト一致（冪等）。remaining_control_mismatches 0。既存2,218 entriesは不変。
- strict incremental dry-run＝ビルド: 43件、in-place 43、relocation 0、pointer write 0。pointer mismatch、implausible pointer、no space、encode error、truncation、ability圧縮、runtime patch、graphics patchすべて0。
- 参考のfull-from-English strict dry-run（2,261件）: 同じ指標がすべて0。vetted FF使用 4,929 byte、残り 610,904 byte。これはビルドには使っていない。
- binary audit（基準ROM→新ROM）: 変更741 byte＝すべてin-place text。**unexpected 0**。既存2,218 entriesの本文・relocation先・pointerは不変。ASM、font、graphics、runtime patchのbyteなし。
- 実機（mGBA）は未確認。

適用総数: 2,218 → **2,261**。Phase 6の残り保留: 959 → **916**。

## 4. 翻訳handoff v2

`out/phase6/ja_phase6_cleanup_translation_handoff_v2.json`（翻訳は未実施）。

- 569 entries（重複なし）＝旧キュー442＋glossary-primaryから振り替えた127。CLAUDE_CONTEXT 267、CLAUDE_TRANSLATION 302。
- 旧キュー442のフィールドは、`requested_claude_task` を除き1つも変えていない（テストで確認）。
- 各entryに追加: 承認済み用語（日本語・scope・official_state）、未解決語のwarning、偽陽性語、`remaining_holds`（用語以外のhold理由）、`original_english`、`current_japanese`。
- 用語の状態: 用語確定170、未解決語あり8、用語なし391。
- 未解決語39件と、語の特定が必要な47 entriesもhandoffに同梱した（`unresolved_terms`、`term_identification_needed`）。
- 振り分け（glossary-primary 258）: 注入43、未解決語・語未特定のまま glossary キュー75、翻訳へ56、文脈確認へ71、Codexへ13。

### 話者・キャラクター情報

- selection fixtureの `speaker`、`speaker_confidence`、`scene_id`、`conversation_id`、`sequence_index`、`group_evidence`、`context_before/after`、`context_confidence`、`runtime_evidence`、script位置（category、ROM offset、GBA address、pointer owner）をそのまま保持。
- 569件すべてで speaker=unknown。話者を同一NPCへ統合していない。`character_name` は null（speaker_unproved）。
- `source_game` は全件「未証明」。`trainer_class_or_label` はトレーナー表のentryのみ。
- `name_mentions`（72 entries）は、glossaryの人名が本文に出ることを示す**名前一致の記録だけ**。同一人物・公式キャラとは断定していない。
- キャラの口調の創作・修正は行っていない。

## 5. 未解決（次のClaude作業へ）

未解決ファイルは39件（unresolved context 10＋unresolved term 25＋却下3＋Psychicの残り1。却下3語は用語ではない偽陽性）。推測では解決していない。必要な追加情報は `ja_phase6_cleanup_glossary_unresolved.json` と handoff v2 の `unresolved_terms` に、参考案は「未検証」と明記して保存した。

- PokeAPIの単数形照合で解けそうなもの: Rawst / Belue / Watmel Berry、Big Nugget、Pretty Wing、Mimikium Z、Yellow Nectar、Cacnea と Pidgey の分類名。
- 方針決定や入力資料が必要なもの: cyclist、melony、SPA、呪文 Sankren bolganone、The Soil、生息地ラベル、Glimmer Isle、ニドラン♀♂。
- 偽陽性（Cut / Strength / Fighting）は復活させていない。この4 entriesは用語なしとして翻訳キューへ回したが、candidateが誤ってわざ名・タイプ名を使っていないかは未確認。

## 6. 検証

pytest 404 PASS（既存388、新規16）＋16 subtests。新規テスト `tests/test_ja_phase6_cleanup_glossary.py`（16件）は、208語のdecision保持、glossary merge整合、global_replace=false、誤適用0、未解決語の自動適用0、affected ID欠落0、inventory accounting、既存2,218不変、controlfix冪等、strict map、binary auditの変異テスト、handoff v2のmetadata保持を含む。
`tests/test_ja_phase5e.py` と `tests/test_ja_phase6a.py` は、glossaryが139語固定・旧一致と完全一致を前提にしていたため、旧139語に限定する形で修正した（検証内容は維持）。
`py_compile`、`git diff --check` も問題なし。

## 再現

```bash
python scripts/build_ja_phase6_cleanup_glossary.py merge
python scripts/build_ja_phase6_cleanup_glossary.py propagate
python 004_controlfix_translations.py out/phase6/ja_phase6_cleanup_glossary_candidates_input.json -o out/phase6/ja_phase6_cleanup_glossary_candidates_controlfix.json --source out/ja-phase5e-prepared.json --report out/phase6/ja_phase6_cleanup_glossary_candidates_controlfix_report.json --target-lang ja
python scripts/build_ja_phase6_cleanup_glossary.py finalize
python 005_hybrid_injector.py out/unbound-ja-phase6-cleanup-codex.gba out/phase6/ja_phase6_cleanup_glossary_safe_controlfix.json -o out/unbound-ja-phase6-cleanup-glossary.gba --target-lang ja --map-output out/phase6/ja_phase6_cleanup_glossary_incremental_map.json --fail-on-no-space
python scripts/build_ja_phase6_cleanup_glossary.py audit
python scripts/build_ja_phase6_cleanup_glossary.py handoff
```

## 生成物

- 変更: `glossaries/ja.json`、`tests/test_ja_phase5e.py`、`tests/test_ja_phase6a.py`
- 新規: `scripts/build_ja_phase6_cleanup_glossary.py`、`tests/test_ja_phase6_cleanup_glossary.py`、本ドキュメント
- private（`out/`、gitignore）: `ja_phase6_cleanup_glossary_propagation.json`、`ja_phase6_cleanup_translation_handoff_v2.json`、`ja_phase6_final_cleanup_inventory_v3.json`、`ja_phase6_cleanup_glossary_*`（merge report、map、audit、controlfix）、ROM。ROMはcommit・upload・releaseしない。
