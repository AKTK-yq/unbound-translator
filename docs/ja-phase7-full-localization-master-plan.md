# Phase 7A — Full Localization Master Inventory

調査・計画のみ。翻訳生成、controlfix実行、注入、ROM生成、glossary変更、commit、pushは実施していない。
方針はkana-only。漢字・font/renderer拡張は完了の必須条件にしない。

## 1. 保護と再現

基準ROMは `out/unbound-ja-phase6-cleanup-batch04.gba`。
作業前後のSHA-256は `0d1d00e7b0f4f113514abbcf1907e6d8949fd12b9193bf2cb0ad764ace5559d8`。
入力 `rom/unbound.gba` のMD5は `9cad8e771940e7f7094d13911552cef0`。
既存保護909ファイルの各SHA-256と集約値は不変。
集約値は `f932aab110e4dc228c628314c43ce5b0dc0ba89d5f15f6740da9ef6117bad4df`。

最初に、ユーザー許可の既存3ファイルだけを限定修正した。

- `scripts/build_ja_phase6_cleanup_batch03.py:60`：完全一致の7パスを追加。909件・期待hash・validator gateは変更なし。
- `tests/test_ja_phase6_cleanup_batch03.py:240`：完全一致集合、1件除外時のFAILを検証。
- `tests/test_ja_phase6_cleanup_batch04.py:27`：期待許可集合のみ追従。`:38` の許可外ファイル検出テストは維持。

この限定修正だけの段階で、全pytest **554 PASS + 16 subtests** を確認してから棚卸しに進んだ。
skip、xfail、テスト削除なし。想定外の新規ファイルは従来どおり保護検査でFAILする。
Phase 7Aの追加許可は次の7パスだけ。ディレクトリ許可・ワイルドカードなし。

```text
docs/ja-phase7-full-localization-master-plan.md
out/phase7/ja_full_localization_inventory.json
out/phase7/ja_full_localization_category_stats.json
out/phase7/ja_full_localization_priority_queue.json
out/phase7/ja_full_localization_technical_blockers.json
scripts/build_ja_phase7_inventory.py
tests/test_ja_phase7_inventory.py
```

作成前に対象パスが存在しないことを確認した。既存工程の成果物は上書きしていない。
再現scriptは4 JSONを一括preflightし、既存4件が完全一致なら検証のみ行う。
部分成果物・内容不一致では、1ファイルも上書きせず停止する。

```bash
python scripts/build_ja_phase7_inventory.py
python -m pytest tests/test_ja_phase7_inventory.py -q
python -m pytest -q
python -m py_compile scripts/build_ja_phase7_inventory.py scripts/build_ja_phase6_cleanup_batch03.py tests/test_ja_phase7_inventory.py tests/test_ja_phase6_cleanup_batch03.py tests/test_ja_phase6_cleanup_batch04.py
git diff --check
```

このセッションではpytestのある `.venv/Scripts/python.exe -X utf8` を使用した。
JSON再実行は `VERIFIED_EXISTING_IDENTICAL`。JSONの再生成・上書きではない。

## 2. 25,044と25,045の対応

|集合|ファイル|件数|用途|
|---|---|---:|---|
|canonical|`out/ja-phase5e-prepared.json`|25,044|Phase 6の既存翻訳台帳。今回の進捗集計単位|
|raw|`out/unbound-texts.json`|25,045|保存された生抽出。別配列で全件保持|
|共通ID|両集合|25,043|本文・address・slot一致|
|ID和集合|両集合|25,046|完全文字列の別名1件を含むため、物理文字列数ではない|

17件の共通IDでpointer metadataが異なる。双方のリストを保存し、列挙された参照wordが原ROMの対象addressを指すことを検証した。
原文の変更は0。新しい発見を理由にrawのpointer ownershipを書き換えていない。

|役割|ID|ROM offset / GBA address|slot|参照元|
|---|---|---|---:|---|
|canonical完全警告|`tbl_menu_game_settings_00000_1F4E26F`|`0x01F4E26F / 0x09F4E26F`|185|ROM `0x01EBD7FC` / GBA `0x09EBD7FC`|
|raw完全警告|`scr_1F4E26F`|同上|185|同上|
|raw部分文字列|`tbl_menu_game_settings_00000_1F4E274`|`0x01F4E274 / 0x09F4E274`|180|記録0、全ROM direct pointer検索0|

完全警告2 IDは原文・位置・容量・pointer ownerが一致。**PROVEN_SAME_STRING**。
部分文字列は同一文字列ではなく、完全警告の5 bytes後から始まるstrict suffix。
欠落prefixは `FC 01 04 D1 BB` = `[red]WA`。
完全警告は `[red]WARNING!`、部分候補は `RNING!` から始まる。
いずれもROM `0x01F4E327` / GBA `0x09F4E327` の同一 `FF` を終端とする。

Git commit `22a425f6850308383ae1bee746a3c4ebdb47cf0d` のextractor差分で、
`POST_POINTER_MANUAL_TEXT_RANGES` のextraPrompts開始を `0x1F4E274` → `0x1F4E26F` に修正し、
`0x1EBD7FC` の明示ownerを追加したことを確認した。
現行 `001_extract_unbound_text.py:803` の範囲を、既存extract関数 `:1256` でメモリ内だけ再走査し、
完全警告ID・本文・185 bytes・ownerが再現することを確認した。
同位置の構造化entry優先は `001_extract_unbound_text.py:1626`。
古いraw JSONに版・生成時刻はなく、その正確な生成コマンドまでは断定しない。

owner wordは `6F E2 F4 09`。参照元周辺のROM `0x01EBD7F6` は
`00 00 28 E3 F4 09 6F E2 F4 09 88 38 FB 09 61 FF`。
`0x01EBD7FC` は4-byte aligned。ポインタ値一致だけでbufferstring opcodeとは認定しない。
inventory.historyの「packed owner」という表現は既存手動owner群の説明であり、このwordのconsumer種別の証明ではない。

**部分候補はUNRESOLVED_MAPPINGのまま保持**する。
direct pointerが0でも、計算参照・親へのinterior access・独立表示は否定できない。
旧監査の「clipped duplicate除外」を、完全日本語化における未使用確定として継承しない。
親警告は現基準ROMで91 bytesの日本語としてin-place適用済み。その一致は確認したが、部分候補の消費経路は未証明。

したがって現在の台帳は25,044 translation units、追加調査義務は1件。
物理的な独立表示対象は暫定 **25,044～25,045件**。さらにextractor外の未発見表示経路は別枠。
部分候補を独立注入すると親slotと重なるため、consumer証明前に別翻訳ownerとして扱ってはならない。

## 3. 適用数と残件の集合関係

```text
canonical 25,044
├─ Phase 5適用677 + Phase 6選定2,500 = 3,177（互いに素）
│  ├─ 現適用 2,403
│  └─ Phase 6保留 774
│     ├─ Cleanup 569内の残り 427
│     └─ Cleanup 569外の残り 347
└─ 上記scope外 21,867
   ├─ Phase 5由来の追加保留 39
   ├─ 明示的英語保持 3（実在スタッフ名credit）
   └─ 未処理・候補なし 21,825

Cleanup 569 = 追加適用142 + 残り427
全canonical = 適用2,403 + 保留813 + 英語保持3 + 未処理21,825
```

2,403件は単なるJSON件数ではない。
9世代の既存mapから最終destinationを照合し、既存injectorのencode処理をメモリ内で呼び出した。
全payloadと全記録pointer ownerが基準ROMと一致。**in-place 1,984 / relocated 419**。
今回の本文write・pointer writeは0。
全参照の網羅性を再証明したわけではなく、`pointer_ownership.completeness=NOT_GLOBALLY_REPROVEN` を残す。

Phase 5の除外43件は、raw部分候補1 + canonical42。
canonical42のうち39は追加保留、3は既存の `resolved_keep_latin_staff_name` dispositionを継承。
Phase 7で新規の英語保持を承認していない。

|主status（排他的）|件数|
|---|---:|
|APPLIED_JAPANESE|2,403|
|CONTEXT_HOLD|217|
|TECHNICAL_HOLD|596|
|KEEP_ENGLISH_APPROVED|3|
|UNTRANSLATED|21,825|
|TRANSLATED_NOT_APPLIED / UNUSED_PROVEN / UNKNOWN|0 / 0 / 0|
|合計|25,044|

主statusのUNKNOWNが0でも、文脈やruntimeが判明したという意味ではない。
raw追加候補にはUNKNOWNを付け、canonicalのcontent_familyには15,209件のUNKNOWNがある。

|翻訳軸|件数|意味|
|---|---:|---|
|APPLIED_REVIEWED|2,403|現基準ROMでbyte検証済み|
|REVIEWED_NOT_APPLIED|306|今回のCleanup reviewでconfirmed、技術gate未通過|
|DRAFT_UNAPPROVED|324|過去候補。品質・完全性・安全性の確定ではない|
|NONE|22,011|候補なし。英語保持credit3を含む|

未注入で既存候補があるのは630件（306 + 324）。
324の内訳はかな候補317 + 英字のみの未承認案7。
後者は `L=A`、`LR`、`1F`～`4F`、`HP`。英語保持承認とは扱わない。
**候補なしの未訳22,008件**、英字保持提案も含め「かな候補なし」は22,015件。
既存候補を翻訳完了と数えてはいけない。残りROM適用対象は **22,638件**（25,044 - 2,403 - 3）。

context hold軸217件、technical hold軸794件、重複198件、和集合813件。
主TECHNICAL_HOLD596はcontextより後に選ぶ排他的bucketなので、794と一致する必要はない。
未訳entryのpotential_unassessed_gatesは調査課題であり、確認済み保留へ一括昇格していない。

## 4. 分類とカテゴリ別進捗

ROM近接、地名の言及、英語の口調だけからscene・speaker・到達性を決めない。
extractorの構造化category/tableと、既存speaker attributionのPROVEN bindingのみを分類に使った。
PLAUSIBLEなobject proximityは、NPC所属や場所の確定根拠として使用していない。
メインストーリー・サブイベント・クリア後は、全件規模のscene binding未証明につき分割未確定。
UNKNOWNには通常script、pointer_texts、gendered fragment、credits、tradeなど、より細かいfamily未確定のものを含む。

|内容family|総数|適用|候補なし未訳|review未注入|未承認案|technical軸|context軸|
|---|---:|---:|---:|---:|---:|---:|---:|
|UNKNOWN|15,209|1,103|13,745|255|103|468|139|
|名称（ポケモン・技・特性・タイプ・性格）|2,559|233|2,318|0|8|8|2|
|図鑑|1,916|47|1,868|0|1|1|6|
|アイテム|1,433|129|1,300|0|4|4|4|
|技・特性説明、生息区分|1,252|80|1,166|0|6|6|3|
|トレーナー名・クラス|850|38|810|0|2|7|1|
|メニュー・設定|766|377|347|1|41|51|15|
|戦闘・技習得|545|79|290|43|133|215|45|
|ミッション|247|131|88|2|26|29|2|
|トレーナー会話（binding証明）|137|134|0|3|0|3|0|
|地名|109|33|76|0|0|0|0|
|NPC会話（binding証明）|18|16|0|2|0|2|0|
|必須NEW GAME UI（観測3件）|3|3|0|0|0|0|0|

元の55 categoryを以下に保持。technical/context列は重複し得る。
未訳は「候補なし」、平均長は原ROMをPCS decodeした本文から既知制御表記を除く静的文字数で、buffer展開後の幅ではない。
制御複雑度・P0～P3の内訳はcategory_stats JSONに記録した。
batch列はカテゴリを混ぜず、会話/戦闘/fragment 120件・他200件として切った場合のceil合計用。

|category|総数|適用|候補なし|review未注入|未承認案|technical|context|平均文字数|batch|
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|ability_descriptions|252|31|218|0|3|3|0|25.76|2|
|ability_names|293|49|244|0|0|0|0|9.71|2|
|battle_messages|536|71|289|43|133|215|45|21.41|4|
|credits_text|6|0|3|0|0|0|0|19.00|1|
|day_names|7|0|7|0|0|5|0|3.00|1|
|gendered_dialogue_fragments|54|0|54|0|0|5|5|3.83|1|
|habitat_names|9|3|3|0|3|3|3|15.11|1|
|item_descriptions|704|53|651|0|0|0|0|81.53|4|
|item_names|729|76|649|0|4|4|4|9.29|4|
|map_names|109|33|76|0|0|0|0|11.54|1|
|menu_battle|65|28|32|0|5|5|3|12.97|1|
|menu_common|36|30|1|0|5|6|1|16.72|1|
|menu_cube|5|3|2|0|0|0|0|9.00|1|
|menu_cube_system|28|19|9|0|0|0|0|11.39|1|
|menu_game_settings|81|43|34|0|4|4|1|33.78|1|
|menu_item_storage|18|14|0|0|4|4|0|20.39|1|
|menu_link_controls|60|17|41|0|2|3|1|15.93|1|
|menu_list_labels|180|39|133|0|8|8|5|9.54|1|
|menu_mining|1|1|0|0|0|0|0|216.00|0|
|menu_multiplayer|4|4|0|0|0|0|0|12.00|0|
|menu_options|21|15|1|0|5|5|0|5.48|1|
|menu_pause|11|10|1|0|0|1|1|5.18|1|
|menu_pc|88|45|42|0|1|1|1|14.12|1|
|menu_pcoptions|3|3|0|0|0|0|0|9.00|0|
|menu_pokedex|1|1|0|0|0|0|0|7.00|0|
|menu_pokemon|23|20|3|0|0|0|0|20.09|1|
|menu_pokemon_options|7|5|2|0|0|0|0|5.43|1|
|menu_pokemon_summary|29|16|8|0|5|5|1|37.24|1|
|menu_save|10|10|0|0|0|0|0|10.20|0|
|menu_save_prompts|1|1|0|0|0|0|0|32.00|0|
|menu_saving_messages|6|5|1|0|0|0|0|31.67|1|
|menu_shop|5|4|1|0|0|1|1|10.80|1|
|menu_standalone_labels|1|0|1|0|0|0|0|7.00|1|
|menu_trainer_card|33|19|14|0|0|0|0|8.61|1|
|mission_descriptions|82|43|30|2|7|9|2|77.62|1|
|mission_log|23|16|1|0|6|7|0|10.74|1|
|mission_names|85|37|36|0|12|12|0|15.88|1|
|mission_objectives|57|35|21|0|1|1|0|44.81|1|
|move_descriptions|991|46|945|0|0|0|0|69.09|5|
|move_learning|9|8|1|0|0|0|0|24.78|1|
|move_names|923|79|844|0|0|0|0|9.37|5|
|nature_names|25|23|2|0|0|0|0|5.48|1|
|plain_scripts|14|11|0|0|3|3|0|97.71|1|
|pointer_texts|3,307|5|3,302|0|0|2|0|26.58|17|
|pokedex_descriptions|993|32|961|0|0|0|0|95.56|5|
|pokedex_form_names|19|0|19|0|0|0|5|8.32|1|
|pokedex_species|904|15|888|0|1|1|1|7.51|5|
|pokemon_names|1,294|77|1,215|0|2|2|2|7.39|7|
|scripts|11,979|1,233|10,386|260|100|463|134|86.76|90|
|setting_names|32|18|13|1|0|1|0|12.25|1|
|start_menu_labels|10|7|1|0|2|2|0|10.70|1|
|trade_messages|7|7|0|0|0|0|0|38.14|0|
|trainer_classes|107|15|90|0|2|2|1|8.98|1|
|trainer_names|743|23|720|0|0|5|0|5.47|4|
|type_names|24|5|13|0|6|6|0|4.08|1|

## 5. 重複・未使用候補

- 原文完全一致：distinct **22,024**、重複group **2,205**、group内entry **5,225**、余剰member **3,020**。
- layoutのみ除いた再利用候補：distinct **21,879**、group **2,320**、member **5,485**、余剰 **3,165**。
- pointer記録0：**5,132**。legacy/unused/debugというtable名候補：**176**。両者の和集合：**5,307**。
- **UNUSED_PROVENは0**。候補をtranslation targetから削除していない。

構造化固定stride tableは、各文字列へのpointerがなくてもbase + indexで表示される。
同じ英語でもspeaker、buffer型、renderer、slot、FAの意味区間が違えば同じ訳を共有できない。
layout候補keyはFE/FA等の表示差を弱めた比較用であり、semantic boundary同一の証明ではない。
完全一致だけを再利用する仮定で、独立した訳文作成単位は暫定 **22,024～25,044**。
意味的類似文の同一化は未評価。物理ownerの注入・QA単位は減らない。

## 6. 優先度

|priority|全canonical件数|理由|
|---|---:|---|
|P0|56|NEW GAME既観測3件、必須save/menu workflow候補|
|P1|13,600|会話調査、イベント・ミッション・主要戦闘/UIのfamily policy|
|P2|7,905|図鑑・名称・説明・残る表示経路|
|P3|3,483|generic pointer_texts、legacy/debug候補のconsumer調査|

これにraw追加候補1件のP3を別枠で保持。
3件以外の **25,041件にPRIORITY_UNVERIFIED**。
P0の残りは「必須画面を先に調べる」policyで、entryごとの現runtime到達証明ではない。
P1のgeneric scriptsは仮の調査順。メインストーリーをP1と確定したものではない。
scene graphを復元して必須ストーリーをP0へ再割当てする工程が必要。
P2/P3も完全日本語化の対象。未証明・未使用候補を無断で除外しない。

runtime軸は、人間が具体的に観測した3件、既資料がruntimeと述べるがbranch未照合17件、
owner/tableのみで未プレイ25,024件。過去の全体的な「runtime PASS」を全25,044 IDの証明へ拡大していない。

## 7. 技術保留の統合

最新reviewを優先し、適用済みentryに古い保留を残さない。
774 Phase 6残件に加え、39 Phase 5残件も全体inventoryへ戻した。
以下は813 hold entriesのprimaryと、secondaryを含む影響件数。影響件数の合算は禁止。

|原因|primary|影響entry（非加算）|未評価の潜在gate|
|---|---:|---:|---:|
|unknown buffer|246|379|2,228|
|FA semantic boundary|107|134|2,238|
|dynamic name width|0|219|2,228|
|renderer consumer|49|141|0|
|width overflow|94|265|0|
|incomplete pointer ownership|40|126|0|
|official name|64|77|0|
|glossary scope|43|76|0|
|text slot capacity|12|80|4,877|
|glyph/font・未確定raw prefix|2|2|0|
|other（文脈・未完訳・口調・英字保持提案等）|156|253|0|
|primary合計|813|—|—|

潜在gate 0は問題がないという意味ではなく、今回の簡易source feature判定で数えていないものがある。
原因familyは既存hold reasonの正規化bucket。例えばwidth overflowにはWIDTH_LAYOUTの未証明width/layout gateも含むため、265件すべてで実overflowを測定したという意味ではない。個別の原reasonを必ず参照する。
全件のrenderer consumer、pointer completeness、公式対応を実解析済みとは主張しない。
既知buffer/owner/FA auditを原IDと紐付けて保存し、推測で値の集合や話者を追加しない。

推奨解消順：

1. buffer writer → 値の全候補 → insertion sentence → page restore → 最大幅を一括で証明（379件に影響）。
2. width/consumerごとに実window・font・x・spacing・スクロールを確認（265/141件）。240px未満だけで承認しない。
3. FAのwait phaseごとの命題・名称公開タイミングをClaudeと再レビュー（134件）。FEとFAを同一視しない。
4. 追加exact/interior hitsの構造化ownerを証明（126件）。一致wordだけを新ownerに昇格しない。
5. official nameとscoped glossaryを解決（77/76件）。同名らしい近接textで別entryのscopeを拡張しない。
6. fixed/no-relocation complete wording（80件）。truncation、無断略語、lossy fit不可。

normal Japanese width tableは既存 `lib/gen3_font.py:31` にROM `0x0020F500` / GBA `0x0820F500`、280 bytesとして定義済み。
戦闘geometryの証明anchorは `lib/renderer_profiles.py:15`、window ROM `0x00248330` / GBA `0x08248330`、
printer ROM `0x003FEB64` / GBA `0x083FEB64`。
callersの同定にはそれぞれROM `0x0000F348` / GBA `0x0800F348`、ROM `0x000D8814` / GBA `0x080D8814` の参照を使う。
font ID・実利用幅・buffer展開幅はrendererごとに違う。日本語normal幅だけで全UIを合格にしない。
既存208px等のgate・dynamic bound未証明時のHOLDは今回変更していない。

### ROM容量

最新incremental mapの残vetted spaceは610,169 bytes。
同じ現基準ROMを既存 `005_hybrid_injector.py:328` と `lib/unbound_free_space.py:8` の範囲でread-only再走査すると、
131 blocks / **610,162 bytes**。
差7 bytesは最新allocationの終端FFを含むrunで安全marginを再適用する差。
最新20-byte payloadはROM `0x00C151F8` / GBA `0x08C151F8`、末尾FFは `0x00C1520B`。
mapの次cursor相当 `0x00C1520C` と、FF run開始 + 8の `0x00C15213` は7 bytes違う。
容量を楽観視せず、将来のfresh strict buildでは後者を基準にする。

未適用原文は約1,308,036静的文字。翻訳のbyte量・relocation率は未生成につき不明。
この数字だけで全訳が空きに収まると断定しない。
日本語fontは既存assetを使用し、今回font/code用領域を確保していない。
将来graphics/code用領域を追加する場合はtext relocation poolから独立した予約ledgerが必要。
未所有slot回収やvetted外FF利用はしない。実験的script slot reclaimを自動有効化しない。

## 8. extractor外の漏れ

`graphics/manifest.json` はverified assets **12件**、coverage.complete=false。
追加graphics、metatile看板、PC/link UI、継承FR assetの到達性が未完。
名前入力keyboard旧候補はmanifestのrejected/unverifiedで、確定ROM offsetとして採用しない。

|経路|今回の認定|25,044内数か|
|---|---|---|
|画像に埋め込まれた英字・typeラベル・title等|verified subsetのみ。その他のlayout/owner要確認|PCS censusとは別枠|
|動的生成メニュー・special・buffer writers|既存の個別調査のみ。全画面未網羅|一部あり、全体内数は未証明|
|名前入力・入力制約・保存時encoding|kana表示の成功は入力/validation/save対応の証明ではない|未証明|
|battle grammar・suffix・CFRU生成文|抽出battle 536、fragment等はあるが全経路の網羅証明なし|部分的、完全性未証明|
|script外UI・独自indexed/packed tables|既存table抽出＋個別auditのみ|追加対象数UNKNOWN|
|クリア後・必須/サブイベント|scene/flag/branchを全編追跡していない|既抽出との対応UNKNOWN|

未発見経路の件数を25,044の内数として埋め合わせない。
debug/dead候補の未使用認定には、call graph・flags・table selector等の強い証拠と記録を要求する。

## 9. 推奨翻訳バッチと作業量

初回のcategory単位見積もりは **189 batches**（会話等120・単純table200）。
JSONの `batches_upper_bound` はこの固定分割仮定に限るceil値で、全体の最大作業量保証ではない。
未適用のHIGH complexity **5,606件** を40件単位へ分け、他を120/200にすると **292 batches**。
LOW 9,232 / MEDIUM 7,800 / HIGH 5,606 = 未適用対象22,638。
長文でprompt容量を超える場合はさらに細分化する。

PokeAPIの既存対応category内の未適用候補は **6,652件**。
`lib/pokeapi_localizer.py:11` はja → ja-hrkt、`:14` は名称/分類/説明等のresource mapping。
今回はAPI呼出し・新翻訳なし。
将来は既存cacheのsource identity・Unbound独自種/フォーム・table index対応を検証した上で公式kanaを優先する。
対象categoryに入るだけで全件のja-hrktが得られるとは限らない。
名前はbyte/width制限、説明はGen/versionの意味一致とcontrol制約を再検証する。
全件LLM方式の189～292からAPI対応分が減る可能性はあるが、ROM/QA target数は減らない。

Claude用分割：

- P0 workflowから、証明されたscene/caller/renderer単位で開始。
- 不明bufferやFA多用は最大40件。全文・wait phase・writer evidence・width budget・speaker確度を添付。
- 通常会話は最大120件。ROM近接や `script_operand_neighborhood` をscene証明の代用にしない。
- 名前・単純説明は最大200件。公式resource IDと固定slot/consumer budgetを添付。
- review confirmedとtechnical approvedを分離。意味保留を短文化で回避しない。
- 774旧保留の再処理は原因clusterでまとめ、既承認2,403件は変更対象から外す。

全体作業量：22,638 ROM units + unresolved raw1 + 未発見表示経路。
独立訳文作成約22,024～25,044、初回review約189～292回、同数規模のtechnical integration単位が目安。
追加review・scene/buffer tracing・full-route mGBA・graphics QA・release検証は別途。
仮に各初回batchの人間/技術確認を45～90分と置けば約142～438時間（8h換算18～55人日）。
これは**入力仮定による計画値**で、未知15,209件の文脈調査や全編play時間を含まない。
完成日をこの数値だけで約束しない。次工程の30～50件pilotで平均時間・relocation率を測って見積もり更新する。

## 10. 完了条件と次工程

1. 全reachable textをscene/caller/branch単位で調査。UNKNOWN・raw未対応・extractor外経路の解決、または強いunused証明。
2. 翻訳対象のkana訳を確定。公式名称・glossary scope整合。英語保持はentry単位の明示理由と承認。
3. encode/decode・page state・FE/FA/FB/FC/FD・buffer・全owner・実renderer幅・complete fixed wordingを検証。
4. strict injectionでencode/pointer mismatch/implausible/truncation/missing relocationを0にする。
5. 全binary diffをtext/relocation/owner writes/明示許可patchに分類。無関係差分0。
6. mGBAでnew game、story分岐、save/load、NPC、battle、missions、menus、postgameの表示・進行を検証。
7. canonical inputからBPSを再現可能に生成。元ROM MD5固定。ROMは配布しない。

次はscene/consumer master coverage作成を先行する。
必須ストーリーP0のID集合、Options/NEW GAME差、名前入力、CFRU/buffer生成のcoverageを証明する。
その後、保留cluster調査と公式名候補の照合、30～50件pilot、全体容量予測、段階的翻訳/strict統合へ進む。
これは計画だけで、今回その工程には着手していない。
Phase 7の追加成果物許可は本工程の7パスのみ。将来の別工程成果物を今回の許可で無制限に除外しない。

## 11. 検証・成果物

棚卸しを再計算し、保存済み4 JSONとの構造・byte一致を確認。
ID重複0・対応未計上0、原文変更0、glossary変更0、ROM変更0。
2,403 payload / 記録pointer mismatch0、Phase 6残774の未計上0。
既存909 per-file hashes不変、想定外の新規ファイル0（明示許可の成果物は別管理）。
最終検証：全pytest **568 PASS + 16 subtests、88.38秒**。
新規Phase 7A regression 14件。py_compile PASS、git diff --check PASS。
新規Python/docについてもno-index whitespace検査で指摘0（diff存在時のexit 1は通常動作）。
新しい4 JSONは2回目の再現script実行でbyte-identicalを確認し、上書きしていない。
許可リスト1件除外時FAIL、許可外probe追加時FAILは全pytest内でも検証済み。probeはテスト自身が除去し、残存0。

新規成果物は上記7パス。
inventoryにはcanonical/raw両source metadata、statusの別軸、mapping、重複候補、coverage gaps、23入力のSHA-256を格納。
category_statsは55 categoryの進捗・平均長・control complexity・batch数。
priority_queueは全25,044 IDを一度ずつ＋supplemental1件。
technical_blockersは813件のprimary/secondaryと潜在gateを分離。
docs-syncに従い、one-off計画・見積もり・schemaは本書に集約した。AGENTS.md/README.mdは変更していない。

最終git statusは、許可の既存3ファイルM、新規docs/script/testと `out/phase7/` が未追跡。
staging、commit、pushなし。既存ROM・翻訳・glossary・validatorは変更していない。

```text
 M scripts/build_ja_phase6_cleanup_batch03.py
 M tests/test_ja_phase6_cleanup_batch03.py
 M tests/test_ja_phase6_cleanup_batch04.py
?? docs/ja-phase7-full-localization-master-plan.md
?? out/phase7/
?? scripts/build_ja_phase7_inventory.py
?? tests/test_ja_phase7_inventory.py
```

`git diff --stat`（未追跡成果物は含まない）：既存3ファイル、42 insertions / 3 deletions。
ROMはGit管理対象にしていない。JSON/doc/script/testにもstaging操作を行っていない。
