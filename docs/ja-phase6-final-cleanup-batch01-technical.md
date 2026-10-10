# Phase 6C-4C — Final Cleanup Batch 01 Technical Integration

147件を監査し、68件を適用、79件を保留。今回の範囲はBatch 01のみ。
既存2,261件の本文・pointer、Sarah/Liam/Koji修正、Daniel既存訳は全て保持。

## 検証結果

|項目|結果|
|---|---|
|review validation|147 IDs / duplicate 0 / missing 0 / source・provenance・controls・metadata一致|
|status|confirmed 114 / needs_context 32 / needs_technical_fit 1|
|source boundary|FE 124 / FB 15 / FA 4|
|context unique accounting|32 unique / 33 memberships; 00と28の重複はtbl_battle_messages_00081_3FBC62|
|semantic context resolved|56 unique; 根拠39 battle / 10 glossary / 24 siblingは重複と複数根拠を含む|
|special battle buffers|confirmed 33件、contextを含め37件。7コードを実ROMでdispatchまで追跡。全経路・writer/caller未証明のためUNVERIFIEDとして保留|
|safe / holds|68 / 79|
|in-place / relocation|48 / 20|
|pointer writes|33|
|Japanese applied total|2329|
|Phase 6 remaining holds|848|
|existing 2,261|個別payload照合・storage・全pointer bytes保持 PASS|
|strict dry-run|2,261 + safe全体と基準ROMへのincremental両方PASS|
|controlfix|safe subsetを標準controlfix --no-wrapで2回実行、完全一致・idempotent|
|binary audit|2418 changed bytes / unexpected 0 / runtime patch 0 / font・graphics change 0|
|ROM SHA256|`02c3fcb7a488e6620a274491d5490bd3339eda6935f69973f1b083e67932533c`|
|runtime QA|20 cases; mGBA操作は未実施、実行用fixtureあり|

## Battle buffers — proof boundary

ROM `0x000D77F4`のwrapperは`0x080D7868`を呼び、そこは`ldr r2; bx r2`で
`0x089BD050`へ飛ぶ。ROM `0x009BD0BA`でFDを判別し、code<=0x3Dを検査し、
`0x08964ABE`経由でROM `0x009BD0D0`の62 halfword dispatch tableを使う。
FireRed vanilla番号一致だけの互換判定は無効。

|code|実ROM handler|追跡した情報|分類|
|---|---|---|---|
|12|0x089BD36C|active selector RAM 0x02023BC4、条件付き接頭辞とname helper|UNVERIFIED|
|16|0x089BD434|RAM 0x02023D68 halfword -> helper 0x08099E91|UNVERIFIED|
|18|0x089BD45C|selector 0x02023D6B、shared ability/species helper path|UNVERIFIED|
|19|0x089BD462|selector 0x02023D6C、同shared path|UNVERIFIED|
|1B|0x089BD480|selector 0x02023D6E、同shared path|UNVERIFIED|
|20|0x089BD5A0|0x0202273C link records、28-byte stride、side xor 1|UNVERIFIED|
|21|0x089BD5B2|同link records、side xor 3|UNVERIFIED|

上記はpartial evidence。helperの全呼出し、species-sensitive table、message writer、
active/link/Frontier状態、出力言語と最大幅まで同一ROMでつながっていない。
既存の0F/10/11/13/14/1Aについても以前のpret-only承認を新規適用へ流用しない。
00/28/2A/[buffer1]はCALLER_DEPENDENT。詳細machine-code prefixesと33/37 ID一覧はreviewed JSONに保存。
[CFRU hooks](https://github.com/Skeli789/Complete-Fire-Red-Upgrade/blob/master/hooks) と
[battle_strings.c](https://github.com/Skeli789/Complete-Fire-Red-Upgrade/blob/master/src/battle_strings.c)
は探索用の一次資料であり、このROMのbuild identityや互換証明ではない。

## Official / glossary scope

- `tbl_battle_messages_00122_3FC048`: VERIFIED; Curse=のろい (VERIFIED_EXACT_ENTITY); HOLD
- `tbl_battle_messages_00239_3FCC39`: HOLD; HM=ひでんマシン (UNVERIFIED_OFFICIAL_NAME); HOLD
- `tbl_menu_pokemon_summary_00014_419A3D`: VERIFIED; Day-Care=そだてや (INDEPENDENT_PROJECT_WORDING); APPLY
- `scr_1EEA8A9`: VERIFIED; Qualot Berry=タポルのみ (VERIFIED_EXACT_ENTITY); Pecha Berry=モモンのみ (VERIFIED_EXACT_ENTITY); Fresh Water=おいしいみず (VERIFIED_EXACT_ENTITY); HOLD
- `tbl_mission_objectives_00033_1F56736`: VERIFIED; Go-Goggles=ゴーゴーゴーグル (VERIFIED_EXACT_ENTITY); APPLY
- `tbl_pokedex_descriptions_00013_166896A`: VERIFIED; Graveler=ゴローン (VERIFIED_EXACT_ENTITY); APPLY

PokeAPI cacheはen exact entityとja-hrktを照合し、entity ID・cache SHA256を保存。
CurseはHP犠牲による呪いの効果、Gravelerは電気を帯びたアローラ個体の種名として確認。
HMは既存使用例だけでは公式entityを証明できず保留。Day-Careは夫婦が見つけたタマゴという
独立した文脈から育成施設「そだてや」を採用し、公式検証済みとは主張しない。
Fresh Water/Pecha Berryは独立したitem cache照合。292 termsのscope・global_replaceを変更しない。
全147件にscoped matcher結果、review used/not-used、元handoff metadataを保持。

## FA / controls / width

- `tbl_battle_messages_00122_3FC048`: COMPLETED_SEGMENTS; HOLD_DYNAMIC_BUFFER_AND_LAYOUT_UNPROVED; HOLD
- `tbl_battle_messages_00185_3FC75D`: COMPLETED_SEGMENTS; HOLD_DYNAMIC_BUFFER_AND_LAYOUT_UNPROVED; HOLD
- `tbl_battle_messages_00216_3FCA49`: needs_context; HOLD_UNKNOWN_00; HOLD
- `tbl_battle_messages_00219_3FCAAA`: COMPLETED_SEGMENTS; HOLD_DYNAMIC_BUFFER_AND_LAYOUT_UNPROVED; HOLD

完成segments3件は元のFE/FA順・segment数・segment別protected controlsを確認して再構築。
全体reviewed_japanese空欄を未完訳とは扱わない。ただしbufferとdynamic幅未証明のため
layout approvalを付与せず全FA保留。00を含む1件は意味上も未解決。
通常entryも元のsegment境界に対してtokensを比較し、移動したものは保留。

Cube V3 (`tbl_start_menu_labels_00001_A4E4E4`) は8-byte fixed/no-relocation枠に
キューブV3の11 bytesが必要で保留。切詰め・制御削除・隣接上書きなし。

223px case (`tbl_battle_messages_00158_3FC421`) は旧診断の「静的幅」というラベルが誤り。
静的幅は[10,115]pxで、223pxは2つのFDを54pxずつ加えた仮の幅。
222px battle spanを満たす証明にはならず、意味・実dynamic bounds未証明で保留。
この差異を推測で修正して採用しない。

Low/Medium/High括弧→slashの3件は同一選択肢の値/速度注記で意味を保持。
Bike&Surf Musicの&→とは両方の移動状態の音楽という論理ANDを保持。
ただし169px setting labelは既存93px制約で保留。charmap対応だけで採用しない。

文面をwrapし直してsource FE/FB/FAを動かさず、既存controlfixの言語ページのみ付与。
確立済み能力191px/1行、技122px/6行、mission172px/3行、setting93px制約を使用。
vendor FC13 column x=87の手前にitem nameが収まるか個別比較。後続FC0600の価格のfont0は
元controlと価格を維持し、normal-fontで価格幅を証明したとは主張しない。
renderer実機未測定だけならwarning。全保留理由をprimary/secondaryとして残した。

## Reproduction / preservation / handoff

`.venv\Scripts\python.exe -X utf8 scripts/build_ja_phase6_cleanup_batch01.py all`

全出力は存在確認し、JSON再計算一致またはROM/map監査のみ。既存成果物を上書きしない。
strict full dry-runは元ROMから容量/owner/pointer/encodeを検証する診断であり、
実ROM生成はvoice-pass1基準へのincremental適用。全差分をin-place/relocation/pointerに分類。
旧relocation mapと既存2261個別encoded payload・本文範囲・全pointerを照合し保持。
他工程スクリプト、glossary、旧ROM、6件の既存未追跡ファイルは変更なし。

Batch 02準備に進むためのtechnical gate/reportは揃ったが、buffer検証の課題は残る。
今回Batch 02〜04の翻訳を開始しない。次回はROM固有helper/writerとdynamic幅を証明し、
FAではsegment translationとlayout approvalを分離、official exact entityとentry scopeを独立検証する。
unknown rendererを一律保留へ戻さず、確実なoverflow/column collision/固定枠だけを別のgateで止める。

作成: 新script/test、technical report、runtime QA fixture、out/phase6のBatch01専用JSON/maps、
`out/unbound-ja-phase6-cleanup-batch01.gba`。tracked既存ファイル変更なし。commit/pushなし。
最終pytest/py_compile/git diff --check結果はvalidation JSONに保存。
