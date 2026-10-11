# Phase 7B — Story / Event / Scene Attribution

## 結論

25,044 canonical entry、25,045 raw entry、適用済み2,403件、Phase 6保留774件、未解決suffix 1件を保持した。翻訳、既訳変更、ROM生成、glossary変更、Claude呼出しは行っていない。

実ROMのmap lookupを解析し、57 groupの復号tableから645 map record、7,290 event/script root、60,932 bytecode commandを調査。4,450 entryに静的なevent参照を付けた。**メインストーリー必須進行を確定できたentryは0件**。候補717件は調査用であり、任意イベント・クリア後要素を含み得る。

P0/P1の翻訳レビュー計画は706件・16バッチ。これは初期handoff候補であり、注入承認でも「これだけで最後まで日本語で遊べる」保証でもない。話者不明は中立口調とし、未確定な進行・buffer・rendererの調査を継続する。

## 1. 保護・集合の整合

|集合|件数|処置|
|---|---:|---|
|canonical|25,044|ID・original・既存訳候補・status・hold・pointer metadata不変|
|raw|25,045|全entry/sourceとmappingを保持|
|APPLIED_JAPANESE|2,403|既存ROM・本文・pointerを変更しない|
|Phase 6残保留|774|ID集合そのものを保持、解除なし|
|UNRESOLVED_MAPPING|1|`tbl_menu_game_settings_00000_1F4E274`を削除しない|

全25,044件を新priority queueに一度ずつ登録。重複ID・欠落IDは0。`scr_1F4E26F`とcanonical `tbl_menu_game_settings_00000_1F4E26F`は同一全文のID alias。`RNING!`のsuffixは+5 byteの部分一致で、独立表示は未証明・否定もしない。原文終端とpointer調査はPhase 7Aのmappingをそのまま引き継ぐ。

保護909ファイルの期待aggregate SHA-256は変更しない。

```text
f932aab110e4dc228c628314c43ce5b0dc0ba89d5f15f6740da9ef6117bad4df
```

Phase 7Aの7成果物も追加でSHA-256固定。既存validator・injector・controlfix・codecは変更なし。今回の既存3ファイル修正は、下記8完全一致パスの許可と対応テストのみ。ワイルドカード・ディレクトリ許可・skip・xfail・期待hash変更なし。

## 2. 発見したROM上の根拠

### live map group lookup

|用途|ROM offset|GBA address|根拠|
|---|---|---|---|
|map lookup hook|`0x0055238`|`0x08055238`|`00 4A 10 47 D5 15 ED 09`：literalをロードしてThumb routineへ分岐|
|復号routine|`0x01ED15D4`|`0x09ED15D4`|group/indexを各4倍し、group wordをXOR後、header pointerを取得|
|group table literal|`0x01ED15E4`|`0x09ED15E4`|`98 04 B7 08`|
|XOR key literal|`0x01ED15E8`|`0x09ED15E8`|`DE 49 B7 00`＝`0x00B749DE`|
|encoded group table|`0x00B70498`|`0x08B70498`|57復号可能baseの後に`F7 F7 F7 F7`|
|region name lookup|`0x000C4D78`|`0x080C4D78`|section IDから88を引き、上限108を判定|
|bias literal|`0x000C4D9C`|`0x080C4D9C`|`00 00 A8 FF`をshift済みsectionへ加算|
|name pointer table literal|`0x000C4DB8`|`0x080C4DB8`|`AC 1C 3F 08`|
|name pointer table|`0x003F1CAC`|`0x083F1CAC`|109 pointer、index=`section_id - 88`|
|script command table literal|`0x00069B1C`|`0x08069B1C`|`B4 F9 15 08 08 FD 15 08`、context setupのtable/end|
|script command table|`0x0015F9B4`|`0x0815F9B4`|各opcodeのhandler pointerを検証|

復号routineの16 bytes：

```text
03 4B 80 00 C2 58 03 4B 89 00 53 40 C8 58 70 47
```

`0x0055238`からの分岐、literal pool、`LSL group,2 / LDR groupword / EOR / LSL index,2 / LDR header`が整合する。通常のliteral pointer検索ではencoded group tableの参照関係を復元できなかった。旧FireRed master候補 `0x003526A8 / 0x083526A8`をlive masterとして採用しない。

|map|group/index|header ROM / GBA|header pointer owner ROM / GBA|
|---|---|---|---|
|Frozen Heights|3/66|`0x007738E4 / 0x087738E4`|`0x00B6D658 / 0x08B6D658`|
|Route 1|3/67|`0x00775030 / 0x08775030`|`0x00B6D65C / 0x08B6D65C`|
|Bellin Town|3/68|`0x00775870 / 0x08775870`|`0x00B6D660 / 0x08B6D660`|

これらはprimary CFRUのUnbound map constantsとも一致するが、名前一致から推定したのではない。実ROMの復号pointer、header section、lookup結果を照合した。[CFRU map constants](https://github.com/Skeli789/Complete-Fire-Red-Upgrade/blob/b637a27898b14e25dd24d0f69a3e302f0069deb8/include/constants/maps.h)

旧Phase 6解析の`section < 109`は拡張mapを取りこぼす。旧speaker metadata中のmap nameはbias未適用のため、今回のmap labelとは整合しない場合がある。**旧speaker JSONは変更しない**。新`event_bindings`のgroup/index/nameを使用し、旧近接候補の地名を新しい根拠に昇格させない。

### 構造の範囲

headerは28 bytes、object recordは24 bytes、coordは16 bytes、backgroundは12 bytes。CFRU objectのscript fieldは+0x10、visibility fieldsは+0x14/+0x16。backgroundのhidden-item unionをscriptとして追わない。[CFRU field-map structures](https://github.com/Skeli789/Complete-Fire-Red-Upgrade/blob/b637a27898b14e25dd24d0f69a3e302f0069deb8/include/global.fieldmap.h)

map scriptsのtypeとpointer list、type 2/4のvariable/value/script recordsを解析する。[FireRed map-script types](https://github.com/pret/pokefirered/blob/037335f4c725d7c9aecdac87066f2002b4bd7e14/include/constants/map_scripts.h)

group末尾は次のdecoded table base、非ROM pointer、256-index上限で保守的に区切る。645は受理したrecord数であり、「ゲームの全map数」とは断定しない。拒否slot 43件と各groupのstorage auditを保存。headerの空eventsはnullを許容する。warp・connection fieldから実プレイ経路を捏造しない。

## 3. script解析と参照信頼度

|参照信頼度|entry数|定義|
|---|---:|---|
|DIRECT_REFERENCE|4,153|構造rootからcall stack深さ0で到達したtext operand、または既存difficultyの構造検証済み参照|
|INDIRECT_REFERENCE|307|rootからscript call先のtext operand、DIRECTなし|
|HEURISTIC_CANDIDATE|15,452|canonical pointer wordは実ROMと一致するが、root/consumer未証明。局所opcode形状も候補止まり|
|UNKNOWN_REFERENCE|5,132|今回event/consumer参照を証明できない。pointerなしは未使用証明ではない|

event参照付き4,450件とDIRECT+INDIRECT 4,460件は定義が異なる。差10件はdifficulty構造参照のみ。全状態は25,044件に一致する。

|root種別|数|
|---|---:|
|object|3,847|
|coord|1,114|
|background|939|
|level|877|
|level condition|510|
|過去human-observed UI anchor|3|
|合計|7,290|

call/returnは実際のreturn stackを保持。条件分岐は両側を静的候補として追い、成立条件は評価しない。script pointerのtargetがPCS slot内なら停止。ROMの近接をrootやspeakerの根拠に使用しない。

`message`、`messageautoscroll`、`loadword 0 + callstd 2/6`、trainerbattle text operands、bufferstring writerを区別する。**loadwordだけでは表示consumerを証明しない**。native/special/standard-scriptの効果はopaque。native codeをbytecodeとして追わず、callstd内の追加表示も未解析。

固定argument構造はpinned BPRE primaryを参照し、現在ROMのcommand handlerも記録した。[FireRed event macros](https://github.com/pret/pokefirered/blob/037335f4c725d7c9aecdac87066f2002b4bd7e14/asm/macros/event.inc)、[command table](https://github.com/pret/pokefirered/blob/037335f4c725d7c9aecdac87066f2002b4bd7e14/data/script_cmd_table.inc)

Unboundでhookされた`46 / 78 / 81 / 8A / B2 / B6 / D3`はoperand消費を今回確定していないため解析停止。trainerbattle modes 10–15、virtual-address commands、未対応opcodeも停止。保守的停止は1,782 root、gap occurrence 1,886件（unique offset/reason 1,066）。内訳：patched handler 1,120、未対応opcode/mode 764、invalid script target 2。map script recordの未対応49、level pointer invalid 2も別に記録。

このdecoderは全Unbound命令の形式証明ではない。委譲helperやnative効果、全branchの可到達性は未解決。条件の意味を再解析する前に静的参照をruntime PASSへ昇格しない。

## 4. story/eventと優先度

|story category|件数|
|---|---:|
|MAIN_STORY_VERIFIED|0|
|MAIN_STORY_CANDIDATE|717|
|MANDATORY_GAMEPLAY_UI|5|
|IMPORTANT_SIDE_EVENT|0|
|OPTIONAL_NPC|0|
|POSTGAME|0|
|NON_DIALOGUE|9,677|
|UNKNOWN|14,645|

717件は同一map contextでlevel/coord rootから直接表示される候補。shared common scriptのcall先や多map共通文を自動的にmain storyへ分類しない。それでもbattle house等の任意要素を含むためPROVISIONAL。object参照があるだけでOPTIONAL_NPCと確定しない。フラグのcheck/setだけでは必須進行・クリア後判定を付けない。

UI 5件：過去に人間が確認した`1F0F7EC / 1F0F800 / 1F0F814`がVERIFIED。今回、同じ選択scriptのparsed flowから`message`される難易度prompt `1F0FE27 / 1F0FF35`をSUPPORTEDで追加。後者の個別branchは今回実プレイしていない。

major NPCの**支持されたidentity**はIvory `scr_74BFC6`、Marlon `scr_75D3DA / scr_75D407`の3件。過去のtrainer record/classによる分類を保持しただけで、必須main storyの確定件数ではない。canonical cross-game character本人認定は追加していない。

|priority|件数|confidence|
|---|---:|---|
|P0|722|VERIFIED 3 / SUPPORTED 2 / PROVISIONAL 717|
|P1|869|SUPPORTED 869|
|P2|12,606|SUPPORTED 12,606|
|P3|10,847|UNKNOWN 10,847|

P1は支持されたmajor NPC、構造化battle/主要UI/missionのusage policy。P2は参照・reference-data所有根拠、P3は参照未証明。SUPPORTEDはpolicy/静的根拠であり、実プレイ頻度を測ったものではない。P2/P3も最終調査対象から除外しない。

|priority|既適用|未訳・候補なし status|context hold status|technical hold status|合計|
|---|---:|---:|---:|---:|---:|
|P0|172|441|24|85|722|
|P1|277|344|49|199|869|

上表はPhase 7Aのexclusive status。secondary holdを足して二重計上しない。Phase 6保留774件との重複はP0 109件、P1 240件、合計349件。集合全体774件は保持。

内容UNKNOWNは15,209→10,849、4,360件減。`EVENT_SCRIPT_REFERENCED_TEXT`/`EVENT_SCRIPT_LOADED_DATA`への分類であり、main story所属や話者確定ではない。story UNKNOWN 14,645とは別軸。

`scene_ids`/root IDsは具体的なobject/coord/level recordに対応する技術的context単位。映画的なscene名・story sequenceではない。進行順序は未証明のため`story_progression_sequence=[]`、next eventをaddress順で作らない。flag/varの値とcheck/set opcodeは記録するが、story上の意味・必須条件はUNKNOWN。

## 5. speaker・voice・glossary・buffer

旧speaker metadata全件をそのまま保持：PROVEN 155、PLAUSIBLE 38。他entryへ話者を自動付与しない。新rootを発見しても、interaction objectと実際の発話主体は同一とは限らない。旧voice profile 56件も変更なし。新speaker昇格0、根拠なしMAIN_STORY_VERIFIED 0。

entryごとにoriginal、current Japanese（適用済みのみ）、既存candidate、translation/injection状態、hold、pointer、glossary matcherのscope付きhit、speaker/voiceを紐付けた。glossaryの本文・scope・matcherを変更しない。照合結果は再承認・自動置換ではない。

bufferstring writerを記録しても、placeholderの展開実体を自動確定しない。FDやbuffer1等はpath依存writer/native/common-scriptのreaching-definition調査が必要。`[player]`/`[rival]`の意味が既知でもdynamic widthの注入gateは残る。difficultyは既存auditのrole/anchor照合を使用し、それ以外のunknown bufferを推測解除しない。

完全一致重複2,205組、余剰3,020件は再利用候補。member ID/物理slotを個別に保持し、話者・event・renderer・controlの差異をレビューしてから再利用する。自動訳文複製やpointer統合は承認していない。

## 6. Claude readinessとバッチ計画

|translation readiness|全体|P0|P1|
|---|---:|---:|---:|
|ALREADY_APPLIED|2,403|172|277|
|READY_FOR_CLAUDE|10,430|467|239|
|NEEDS_EVENT_CONTEXT|10,489|5|0|
|NEEDS_BUFFER_ANALYSIS|1,659|76|348|
|NEEDS_OFFICIAL_TERM|58|2|5|
|NEEDS_TECHNICAL_REVIEW|5|0|0|

既存context holdは静的map参照だけで解除しない。loadword/buffer writerのみで表示consumer不明のdialogueはNEEDS_EVENT_CONTEXT。glyph/raw不明、公式名称、unknown bufferは対応状態で保留。KEEP_ENGLISH 3件は保持し、Claude計画から除外する。

READY_FOR_CLAUDEは文脈付きの**翻訳レビュー準備**。FA semantic boundary、fixed slot、renderer、width、pointer ownershipの注入gateは引き続き必須。未適用entryのinjection readinessはすべて`NOT_APPROVED_REQUIRES_EXISTING_GATES`。既存translation statusやholdは変えない。

今回計画したP0 467 + P1 239 = 706 unique entry、16バッチ。通常目標120–160件、FAを含むgroupは上限40件、visible source 16,000文字上限。groupや末尾により120未満を許容。件数は次のとおり。

```text
40, 40, 40, 40, 40, 39, 15, 40, 38, 33, 40, 38, 24, 133, 40, 66
```

PROVEN speaker group、またはunique static event rootを可能な限り保持する。複数rootのshared textは個別unit。scene単位でまとめても同一人物の口調を意味しない。大groupを分割する場合は理由を記録。ID sortは再現性のためだけでstory orderではない。

Claudeへのhandoff前にcandidate priority、root prerequisite、話者不明の中立口調、FA・buffer保持を人間が確認する。今回はClaudeを実行していない。

## 7. mGBA確認候補 — 実プレイ経路は分離

全entryの`qa`にmap/event/NPC record/条件/expected IDを保存。今回新たにゲーム操作はしていない。

|候補|text ROM / GBA|根拠と人間による確認|
|---|---|---|
|キャラ選択 `scr_1F0F7EC`|`0x01F0F7EC / 0x09F0F7EC`|過去Phase 3のNEW GAME表示PASS。message operand ROM `0x01E6F9F2 / GBA 0x09E6F9F2`を再検証|
|肌色 `scr_1F0F800`|`0x01F0F800 / 0x09F0F800`|同上。NEW GAME側owner `0x01E6FA32 / 0x09E6FA32`|
|髪色 `scr_1F0F814`|`0x01F0F814 / 0x09F0F814`|同上。NEW GAME側owner `0x01E6FA74 / 0x09E6FA74`|
|Puzzle prompt `scr_1F0FE27`|`0x01F0FE27 / 0x09F0FE27`|parsed NEW GAME flowのmessage。選択branchごとに表示と次の遷移を確認。新human PASSではない|
|Battle prompt `scr_1F0FF35`|`0x01F0FF35 / 0x09F0FF35`|同上。Options難易度変更とは別entry/path|
|prologue候補 `scr_1F11016 / scr_1F110D5`|`0x01F11016 / 0x09F11016`、`0x01F110D5 / 0x09F110D5`|Frozen Heights 3/66のlevel condition、variable `0x5011=0`から参照。実際のsave初期値・起動経路は未証明|
|雪の障害物 `scr_1F5AE1C`|`0x01F5AE1C / 0x09F5AE1C`|Route 1 3/67 object roots。座標/visibility fieldsはindex参照。表示可能な進行状態はUNKNOWN|
|町看板 `scr_1F709B2`|`0x01F709B2 / 0x09F709B2`|Bellin Town 3/68 background record。看板座標をindexで確認し、通行経路と表示を人間が検証|
|Trainer Tips `scr_1F72A6D`|`0x01F72A6D / 0x09F72A6D`|同map background。条件や実到達は未確認|

確認の優先順は、既知のNEW GAME3画面、同scriptの難易度UI、次に静的map候補。後半の町・道路への「NEW GAMEから何手で到達」といったrouteは作っていない。既存基準ROMを読み、screen/text ID・save状態・選択branch・page transitionを記録する。元セーブを上書きしない。

Frozen Heights rootsには英語のtest/grunt textも静的に結び付く。map tableにあるだけでruntime可到達とはしない。これはデバッグ候補の証拠にはなるが、UNUSED_PROVENにはしない。

## 8. 次の解析課題

1. `0x5011`等の初期化・writer・判定を追い、prologueから必須進行sequenceを証明する。check/setの同時出現だけでは足りない。
2. 7 patched opcodeとextended trainerbattle modesのargument消費を現在ROMのhandler/helperから確認。停止後にあるdialogueをlosslessに追加調査。
3. native/common/list/menu consumerを特定し、unknown bufferのreaching definitionsとwidth、shared suffixを分離する。
4. 645受理record以外の拒否43 slot、各group末尾・runtime bounds、warp/connection、実ゲーム経路を確認。
5. Major NPCのevent identity・actual speakerを確定し、旧近接候補や旧誤labelを新しい証拠に使わない。
6. 1件のinterior suffixとPhase 7A extractor coverage gapsを継続。画像英字、独自UI、名前入力、battle専用/dynamic表示は25,044内数と断定しない。

P0 candidate717件を、そのまま必須storyと承認しない。まず初期sceneの条件証明、未対応opcode、branch/native/bufferの実体を確認し、runtime観察でSUPPORTED/PROVISIONALを補強する。

## 9. 新規成果物・再現手順

今回作成した完全一致8パス：

- `docs/ja-phase7-story-event-attribution.md`
- `out/phase7/ja_story_scene_index.json`
- `out/phase7/ja_story_priority_queue.json`
- `out/phase7/ja_story_evidence_gaps.json`
- `out/phase7/ja_story_translation_batch_plan.json`
- `tests/fixtures/ja_phase7_story_attribution_manifest.json`
- `scripts/build_ja_phase7_story_attribution.py`
- `tests/test_ja_phase7_story_attribution.py`

scriptは書込み前に全5 JSONの存在を確認する。全不存在ならexclusive-create。全存在ならbytes一致の検証のみ。部分存在・内容競合は書込み前に停止。Phase 7A成果物を再生成しない。JSONは原文・参照根拠を含む大きなローカル台帳であり、ROMや生成ROMを公開しない。

```bash
python scripts/build_ja_phase7_story_attribution.py --analyze
python scripts/build_ja_phase7_story_attribution.py
python -m pytest tests/test_ja_phase7_story_attribution.py -q
python -m pytest
python -m py_compile scripts/build_ja_phase7_story_attribution.py tests/test_ja_phase7_story_attribution.py scripts/build_ja_phase6_cleanup_batch03.py tests/test_ja_phase6_cleanup_batch03.py tests/test_ja_phase6_cleanup_batch04.py
git diff --check
```

ローカルではpytest入りの`.venv/Scripts/python.exe -X utf8`を使用。

既存ファイル変更は次の3ファイルのexact allowlistのみ（Phase 7Aの既存変更も維持）：

- `scripts/build_ja_phase6_cleanup_batch03.py`: `PHASE7B_PATHS`8パスのみ追加。
- `tests/test_ja_phase6_cleanup_batch03.py`: exact-path一致、1パス除外時FAIL、許可外probe追加時FAILを追加。
- `tests/test_ja_phase6_cleanup_batch04.py`: 上記exact setを期待値へ追加。

## 10. 検証

新規回帰テスト18件。実ROMの全entry再解析・JSON照合、call/return stack、native opaque、条件両側の静的探索、未知opcode停止、hook停止、trainer mode停止、text slot侵入停止、参照byte/witness一致、speaker/voice/hold/原文/旧訳保持、exact-pathと上書き拒否を確認する。

検証結果：

- 許可リスト関連72テスト PASS。許可パス1件除外、許可外probe追加は期待どおりFAIL。
- 新規18テスト PASS。
- 全pytest **587 PASS + 16 subtests PASS**（92.28秒）。初回の新規テスト1件にあったsnapshot件数の型参照ミスを修正し、全件再実行した。既存テスト・期待hash・安全gateは変更していない。
- py_compile PASS、git diff --check PASS（既存3ファイルにGitのLF/CRLF注意のみ）。
- 全5 JSON parse PASS。実ROM・旧入力からのoffline再解析が既存5 JSONのbytesと一致、`VERIFIED_EXISTING_IDENTICAL`。書換えなし。
- 原文/既訳/hold変更0、speaker昇格0、根拠なしmain story確定0。
- 保護909件・Phase 7A 7成果物・基準ROM・glossaryのhash一致。

基準ROM SHA-256（変更禁止）：

```text
0d1d00e7b0f4f113514abbcf1907e6d8949fd12b9193bf2cb0ad764ace5559d8
```

commit/push、翻訳、ROM生成は実施しない。

最終`git diff --stat`（trackedのみ、Phase 7A既存変更を含む）：

```text
 scripts/build_ja_phase6_cleanup_batch03.py | 21 ++++++++-
 tests/test_ja_phase6_cleanup_batch03.py    | 73 +++++++++++++++++++++++++++++-
 tests/test_ja_phase6_cleanup_batch04.py    |  2 +-
 3 files changed, 93 insertions(+), 3 deletions(-)
```

`git status --short`：

```text
 M scripts/build_ja_phase6_cleanup_batch03.py
 M tests/test_ja_phase6_cleanup_batch03.py
 M tests/test_ja_phase6_cleanup_batch04.py
?? docs/ja-phase7-full-localization-master-plan.md
?? docs/ja-phase7-story-event-attribution.md
?? out/phase7/
?? scripts/build_ja_phase7_inventory.py
?? scripts/build_ja_phase7_story_attribution.py
?? tests/fixtures/ja_phase7_story_attribution_manifest.json
?? tests/test_ja_phase7_inventory.py
?? tests/test_ja_phase7_story_attribution.py
```

Phase 7Aのuntracked成果物は作業前から存在し、今回変更していない。新規8パスと既存exact allowlist 3ファイル以外に意図しない変更はない。
