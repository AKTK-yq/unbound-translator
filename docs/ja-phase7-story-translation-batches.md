# Phase 7C-1 — Story Priority Translation Batch Preparation

## 結果・範囲

Phase 7BのP0/P1 `READY_FOR_CLAUDE` **706 unique ID**を再照合し、16バッチ計画と**Batch 01入力53件のみ**を作成した。翻訳、Claude実行、PokeAPI呼出し、ROM生成、既訳変更、用語変更、commit/pushは行っていない。

canonical 25,044、raw 25,045、適用済み2,403、Phase 6残保留774を保持。未解決raw suffixも除外・統合しない。MAIN_STORY_VERIFIEDは0のまま。READYは翻訳レビューの準備状態であり、注入承認ではない。

## 706件の照合

- Phase 7B scene index、priority queue、旧16バッチ計画のID集合が完全一致。
- P0 **467** / P1 **239**。duplicate 0、missing 0、既適用混入0。
- 原文、旧日本語候補、speaker/priority confidence、hold、control、glossary scopeを保存。昇格・解除なし。
- 既訳候補の出所74件をmanifestの `existing_candidate_linkage` に登録。候補そのものは変更しない。
- 英語静的可視文字62,192、original文字列長70,110。後者はHMA引用符・token表記・改行を含むUnicode文字数、byte数ではない。可視文字数はPhase 7Aの値を継承し、buffer展開後の長さではない。

|category|706件中の件数|
|---|---:|
|scripts|464|
|plain_scripts|3|
|battle_messages|116|
|menu_battle|34|
|menu_options|6|
|menu_pokemon|3|
|start_menu_labels|3|
|mission_names|48|
|mission_objectives|22|
|mission_log|7|

## 全16バッチ

英語文字数は「静的可視 / original文字列」。FA・buffer・profileはentry数。各entryは一度だけ所属する。

|Batch|件数|P0 / P1|英語文字数|FAあり|未知buffer値|writer未証明|voice profile|
|---|---:|---|---|---:|---:|---:|---:|
|01|53|53 / 0|7,336 / 8,263|21|0|10|0|
|02|43|43 / 0|6,485 / 7,290|22|0|5|0|
|03|37|37 / 0|5,729 / 6,412|12|0|8|0|
|04|56|56 / 0|4,851 / 5,631|11|0|7|0|
|05|42|42 / 0|4,710 / 5,305|10|0|2|0|
|06|30|30 / 0|3,853 / 4,213|9|0|0|0|
|07|37|37 / 0|4,286 / 4,825|13|0|4|0|
|08|30|30 / 0|6,026 / 6,743|15|0|3|0|
|09|31|31 / 0|2,849 / 3,114|6|0|3|0|
|10|31|31 / 0|4,228 / 4,669|14|0|7|0|
|11|34|34 / 0|2,894 / 3,309|6|0|1|0|
|12|42|42 / 0|4,004 / 4,548|8|0|1|0|
|13|60|1 / 59|1,040 / 1,291|1|5|5|0|
|14|60|0 / 60|1,033 / 1,257|0|8|8|0|
|15|60|0 / 60|1,470 / 1,705|1|0|0|0|
|16|60|0 / 60|1,398 / 1,535|0|0|0|0|
|合計|706|467 / 239|62,192 / 70,110|149|13|64|0|

FA待機の総数は273。field player/rival-name tokenあり51件。未知値13件とwriter未証明64件は別軸であり、加算しない。

### 分割規則

P0を先に並べる。PROVEN speaker、同じ実証済みroot参照集合をgroup化し、根拠のないROM近接groupは作らない。参照がない構造化tableはcategoryを作業単位とするが、sceneとは呼ばない。

groupの初期地域候補rank、その後のgroup key・stable IDは再現性の順序であり、story進行順ではない。ordered dynamic programmingで16×30～60件に分割する。work scoreは可視文字数 + 120×FA + 30×FC + 60×FD。件数・workloadの偏りとroot/speaker groupの分割を罰点化する。

72件のShadow Base複数root参照groupは上限60と制御負荷のため29件/43件に分割（Batch 01/02）。分割されるroot集合はこの1組のみ。battle_messagesとmenu_battleのcategory作業単位も分割するが、同一sceneを意味しない。全分割は `group_splits` に記録。

Batch 13だけP0/P1混在。ただしP0の最後の1件を先頭に置き、その後にP1を続ける。P1をP0より先に扱わない。Batch 02～16の実entry payloadや翻訳成果物は作成していない。

## Batch 01選定理由・内容

53件すべてP0 / PROVISIONAL / MAIN_STORY_CANDIDATE。categoryはscripts 50、plain_scripts 3。未訳候補なし44、未承認draft 6、review済み未注入3。既存technical hold 9件はそのまま保持。

最初の5件は条件付きprologue候補と時代表記。Frozen Heightsのrecordから参照される `0x5011=0/2/3` のrootを優先した。初期地域候補18件（この5件、Frozen Heights屋外4件、Route 1の8件、Bellin Townの1件）を先に配置する。これらの変数初期値・進行上の意味・実プレイ順は未証明。

残り35件はRift Cave 5、S.S. Marine 1、Shadow Base参照groupの前半29。**Batch 01全体を序盤シーンとは扱わない**。「前半」はdeterministicなID列の前半であり、同じ人物やstory chronologyの認定ではない。新たなstory所属の確定は行わない。

過去にruntime確認されたNEW GAMEのキャラ/肌/髪選択と、同scriptの難易度promptは既に適用済みなので対象から除外した。未訳の必須UIを捏造して追加しない。時代表記3件はplain-script rendererの別幅制約を確認する必要がある。

### scene/event根拠

以下はPhase 7Bのroot record、script operand、witness pathを継承した静的参照。条件成立、native/specialの副作用、到達性は未評価。

|root / map|script ROM offset / GBA address|record条件|Batch 01対象数|
|---|---|---|---:|
|map_031_005 level_condition 01E702B7 / Frozen Heights|01E702E1 / 09E702E1|5011=0|3|
|map_031_005 level_condition 01E702BF / Frozen Heights|01E70855 / 09E70855|5011=2|1|
|map_031_005 level_condition 01E702C7 / Frozen Heights|01E70889 / 09E70889|5011=3|1|
|map_003_066 coord 00BBAB64 / Frozen Heights|01E6D7A6 / 09E6D7A6|5011=10|3|
|map_003_066 coord 00BBAB04/14/24 / Frozen Heights|01E6DCFD / 09E6DCFD|5011=14|1（3 root共有）|
|map_003_067 level_condition 01E82DBC / Route 1|01E82DF1 / 09E82DF1|5011=13|8|
|map_003_068 level_condition 01EAA6DF / Bellin Town|01EAA6E9 / 09EAA6E9|5019=1|1|
|map_001_034 level_condition 01E82AF4 / Rift Cave|01E82BDC / 09E82BDC|500C=67|5|
|map_001_039 level_condition 01E93C8C/9C / S.S. Marine|01E93CE6 / 09E93CE6|50EA=2/4|1（2 root共有）|
|map_001_045 coord 00BAFEA4/B4/C4 / Shadow Base|01E91CF5 / 09E91CF5|500C=43|29（3 root共有）|

3/66と31/5は別map record。map nameの一致で同じsceneに統合しない。coordinateのvariable/valueはengine条件の意味を完全に証明したものではない。

53件中50件に前後候補224 referenceを添付。ROM上の近接ではなく、同じrootからの実際の静的witness path上の前後text operandを使用する。分岐やopaque effectを含み得るためruntime会話順ではない。前後資料の既存適用訳もread-only contextで、今回の翻訳対象に数えない。

大きなpath配列を反復コピーせず、`witness_reference` にPhase 7Bファイル・entry ID・reference indexを保存。対象entryのpath hashも記録。各refのowner/target/role/command offsetは保存し、元の完全pathへ戻って検証できる。

## Claude入力・口調・FA契約

Batch 01 JSONは英語original、既存日本語candidate、prepared source metadata、prior review record（該当3件）、holds、category、scene/root/owner、speaker/source-game confidence、glossary scope付きhit、公式名警告、controls/protected tokens、buffer・renderer warningを持つ。

新たな翻訳本文・承認値はない。UNKNOWN/nullは推測で埋めない。全706件のspeaker confidenceはUNKNOWNで、既存voice profileを安全に紐付けられる件数は0。名前の言及からMarlon/Zeph等の実話者や公式歴代キャラを認定しない。

style handoffは既存Phase 6C方針を歴史資料として引用し、今回のcurrent rulesと出力契約を別に置く。kana-only、意味・数値・条件・伏線保持、自然なポケモン風の会話、不要な一人称/二人称を加えない、検証済み公式名・entry scopeだけを使う。PROVEN speakerとCONFIRMED_VOICEは別概念。根拠付きprofileがないためBatch 01の添付profile配列は空。

FAあり21件にROM bytesから得たoriginal segments、順序、segment内protected tokens、入力待ちphase、情報開示警告、layout approval requirementを添付。Batch 01のcontrol occurrenceはFE 105、FA 39、FB 95、FC 32、FD 10。

FEは改行・待機なし。FAは待機後1行scroll、FBは待機後clear。ただしlive window・spacing・残る表示行はUNKNOWN。原文segment内の情報をFA/FBの前後へ動かさない。重要な情報・否定・条件のreveal移動は別途審査。自然な日本語、同じcontrol数、PCS encode成功だけでは承認しない。

FA entryは元segmentと同数・同順の訳を返す。control位置の所有はROM構造/既存controlfix側に置く。[japanese]/[latin]をClaudeが追加しない。FC/FD・色・wait・alignment・placeholderを保持する。前回候補があることも自動承認の根拠ではない。

## 技術リスク・新しいbuffer警告

Batch 01全53件でpointer全所有、実renderer consumer/live usable-width、glossary scopeの再審査が必要。使えるpixel幅はnull。240pxやfield候補208pxを一律合格基準にしない。FA layout/reveal未承認21件、field name bufferのwriter・全値・最大幅・page復元未証明10件を警告する。既存9 technical holdは解除しない。

全706件のうちbattle FDあり**13件**について追加注意：codecのFD06表示名 `[rival]` やFD05 `[kun]` をfieldのライバル名/接尾辞と解釈してはいけない。consumer固有のbattle expansion意味・writer・全値を今回確定していない。`buffer_context_warnings` にIDとraw controlを保存。

Phase 7BのREADY判定はそのまま残すが、それをbuffer依存の意味確定と見なさない。対象はBatch 13の5件、Batch 14の8件。今後これらをClaudeへ実行する前にconsumer/writerを証明するか、`needs_context` として戻す。Batch 01には混入していない。

field名tokenで意味型が既知でもwriter・幅・Japanese/Latin page stateは未証明。未知buffer値13件とwriter未証明64件を混同しない。未知bufferを推測翻訳せず、注入安全gateを変えない。

## 作成・変更パスと再現

全新規パスの不存在を作成前に確認。既存Phase 7A/B成果物は上書きしない。新規6完全一致パスのみ登録：

1. out/phase7/ja_story_translation_batch_manifest.json
2. out/phase7/ja_story_translation_batch01_for_claude.json
3. out/phase7/ja_story_translation_style_handoff.json
4. docs/ja-phase7-story-translation-batches.md
5. scripts/build_ja_phase7_story_translation_batches.py
6. tests/test_ja_phase7_story_translation_batches.py

既存の変更は次の3ファイルのexact allowlist/対応テストだけ：

- scripts/build_ja_phase6_cleanup_batch03.py: PHASE7C1_PATHS 6パスを追加。909期待hash・safe gate・snapshot本体を変更しない。
- tests/test_ja_phase6_cleanup_batch03.py: exact set、1パス除外FAIL、同directory内の許可外probe FAILを追加。
- tests/test_ja_phase6_cleanup_batch04.py: expected setへ同じexact setを加える。

scriptはoffline計算。3 JSONが全不存在ならexclusive-create。全存在ならbyte-identical検証だけ。部分存在・競合・許可外outputは書込み前に停止する。docsは本工程の説明資料でありJSON builderの書込み先には含めない。

```bash
python scripts/build_ja_phase7_story_translation_batches.py --analyze
python scripts/build_ja_phase7_story_translation_batches.py
python -m pytest tests/test_ja_phase7_story_translation_batches.py -q
python -m pytest -q
python -m py_compile scripts/build_ja_phase7_story_translation_batches.py tests/test_ja_phase7_story_translation_batches.py scripts/build_ja_phase6_cleanup_batch03.py tests/test_ja_phase6_cleanup_batch03.py tests/test_ja_phase6_cleanup_batch04.py
git diff --check
```

ローカル実行はpytest入りの `.venv/Scripts/python.exe -X utf8` を使用。Claudeは今回呼ばない。Batch 01 JSON＋style JSONを次の人間レビューへ渡せる状態だが、翻訳実行・controlfix・ROM適用には別工程の承認と既存gateが必要。

## 検証結果

- 限定allowlist修正直後：588 PASS + 16 subtests。
- 新規focused suite：20 PASS（20.02秒）。
- 全pytest：**608 PASS + 16 subtests**（129.74秒）。skip/xfail/テスト削除なし。
- JSON parse、exact706、16所属一意、applied混入0、原文/候補/hold/confidence/control/scope保持PASS。
- 順序を逆転した入力からも同じ分割。再buildと保存JSONのbyte-identical照合PASS。競合・部分出力を上書きしないテストPASS。
- FC引数FA/FB/FE/FFを境界と誤認しない。FA phase・source segments・witness参照のregression PASS。
- py_compile PASS、git diff --check PASS。
- 保護909ファイルhash不変。Phase 7A/B 15成果物を含む26入力SHA-256も保存・再照合。

保護aggregate：`f932aab110e4dc228c628314c43ce5b0dc0ba89d5f15f6740da9ef6117bad4df`。

基準ROM `out/unbound-ja-phase6-cleanup-batch04.gba` SHA-256：
`0d1d00e7b0f4f113514abbcf1907e6d8949fd12b9193bf2cb0ad764ace5559d8`（不変）。

元ROM、全既存翻訳JSON、glossary、injector、controlfix、renderer、FA validator不変。new MAIN_STORY確定0、new speaker/voice確定0、new translation0、new injection0。

git diff --stat（未追跡新規成果物を含まない）：既存3ファイル、48 insertions / 3 deletions。

```text
 M scripts/build_ja_phase6_cleanup_batch03.py
 M tests/test_ja_phase6_cleanup_batch03.py
 M tests/test_ja_phase6_cleanup_batch04.py
?? docs/ja-phase7-story-translation-batches.md
?? out/phase7/ja_story_translation_batch01_for_claude.json
?? out/phase7/ja_story_translation_batch_manifest.json
?? out/phase7/ja_story_translation_style_handoff.json
?? scripts/build_ja_phase7_story_translation_batches.py
?? tests/test_ja_phase7_story_translation_batches.py
```

staging/commit/pushなし。生成ROMなし。ROMをGit管理対象へ追加していない。one-off schema・計画はdocs-sync方針に従い本書へ集約し、AGENTS.md/README.md/既存skillは変更していない。
