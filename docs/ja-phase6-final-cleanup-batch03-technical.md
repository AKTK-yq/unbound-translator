# Phase 6C-4H — Final Cleanup Batch 03 Technical Integration

140件を検証。26件適用、114件保留。既存訳・validator・glossaryは変更していない。
日本語適用総数 **2383件**、Phase 6残り保留 **794件**。
今回の適用は静的安全gateの承認。mGBAでのruntime PASSを意味しない。

## 1. 最終集計

|項目|結果|
|---|---|
|入力|140 IDs、重複0、欠落0、manifest順序一致|
|レビュー|confirmed112 / needs_context28。TRANSLATION74+4 / CONTEXT38+24|
|話者|PROVEN3（trainer_0442 / trainer_0444の2組）、PLAUSIBLE8、UNKNOWN129。不変|
|FA|76件：完成63（501 segments）、context保留13。適用12 / 完成だが保留51|
|意味境界|13件にFA_SEMANTIC_REVIEW_REQUIRED。Claude注記なしの#110/#130/#135も検出|
|口調|#52/#83/#107/#117は原文が許す範囲。独自修正・人物認定なし。全4件はdynamic等で保留|
|公式warning / scope gap|13件 / 14件、全exact IDを監査JSONへ保存|
|適用 / 保留|26 / 114（context28 + confirmed技術保留86）|
|in-place / relocation / pointer writes|26 / 0 / 0|
|新規合計 / 残保留|2,383 / 794|
|strict dry-run|incremental26、元ROMからのcombined2,383。encode/pointer/space/truncation/patchエラー0|
|controlfix|標準 --no-wrap 2回。出力JSON byte-for-byte一致、本文・境界変更0|
|binary|全32MB比較。3,074 bytesがin-place textのみ。relocated0 / pointer0 / unexpected0|
|保護|既存909ファイルのSHA-256集合不変。既存2,357 payload・storage・pointer個別不変|
|回帰|focused38 passed。全pytest521 passed / 16 subtests passed。py_compile / git diff --check PASS|
|runtime QA|25件、操作未実施。到達map/event未証明はUNKNOWN|
|範囲|Batch04・過去FA57件救済・新規翻訳・commit・pushなし|

## 2. ROM / renderer / controls

基準: `out/unbound-ja-phase6-cleanup-batch02.gba`。
SHA-256: `192b43b79f75174d9fd5618c47276d2a21cf47ec58b2a902becbe872b19a0284`（生成前後一致）。
出力: `out/unbound-ja-phase6-cleanup-batch03.gba`。
SHA-256: `546f18a50e0ab0eadb9ed0eb53d5773c2cf5aefae1028cc8e8a631379292cc62`。

ROM 0x003A73BC / GBA 0x083A73BC のfield templateは `00 02 0f 1a 04 0f 98 01`、26 tiles = 208px。
参照ROM 0x0006FB38 / GBA 0x0806FB38は0x083A73BC。battle template ROM 0x00248330 / GBA 0x08248330は28 tiles、
printer ROM 0x003FEB64 / GBA 0x083FEB64のx=2から222px。通常field経路を208pxで判定し、240pxを承認理由にしない。
Latin幅ROM 0x001FB100 / GBA 0x081FB100、日本語幅ROM 0x0020F500 / GBA 0x0820F500をコードのtableと再照合。
entry別のloadpointer/callstd/message/trainer候補、隣接バイト、pointer ownerをreviewed JSONへ記録。
実際の全live renderer variant・letter spacing・余白は未実測。未証明consumerは保留、静的fitにはruntime warningを残す。

|母集団（ROMから再計数）|FE|FA|FB|FC|FD|FC01|FC08|
|---|---:|---:|---:|---:|---:|---:|---:|
|全140件|307|125|279|143|69|124|19|
|confirmed112件|240|105|204|91|33|76|15|

FC引数内のbyteやglyphをcontrolとして数えず、ROM decodeの長さで再取得。全140件のmetadataと一致。
完成112件のsource/target controls（FC15/16の言語ページのみ除外）、segment別protected token、FE/FA/FB順序を照合。漢字0 / encode error0。
ページ制御は既存controlfixだけを利用。呪文#92/#115は原文ASCII literalに `[latin]literal[japanese]` を加えた診断用候補。
文字・意味・制御境界は変えず、PCS byte roundtripを確認。両件はowner未証明で注入していない。
PCS decodeは空白・カンマ・pauseを既存canonical aliasに戻すため、文字列綴りの同一ではなくencode→decode→encodeのbyte同一をテスト。

## 3. FA注記10件と修正済み主張

|index（0始まり）|ID|意味境界判定 / 最終判定|
|---|---|---|
|2|scr_1F137A5|HOLD：children/spiritsとlost woodsがFAを跨いで移動。stump possessed by spiritsも逆向き|
|5|scr_1F13870|HOLD：PumpkabooがFA後から前へ移る。CityのFE統合とは別|
|29|scr_1F14D23|HOLD：entranceが2回目FAの前から後へ遅延。導入副詞だけを2回待たせる|
|31|scr_1F14E8B|HOLD：in the tombがFAを跨ぐ。最後のfind every itemの述語も欠落|
|40|scr_1F157E9|HOLD：titanの開示がFA前へ早まる。名称自体も未承認|
|53|scr_1F1653E|意味PASS・APPLY：Leader/Crater Town GymはFE内だけの統合。入力待ちを跨がない|
|63|scr_1F17415|意味PASS・HOLD：Blizzard CityはFE内の統合。owner/interior未分類が残る|
|69|scr_1F17516|HOLD：any ol cowpokeの対象条件がFA前へ早まる|
|98|scr_1F2FE44|意味PASS・HOLD：Ruins of Voidは同じ待機後。source幅制限・owner gateで保留|
|132|scr_1F32467|HOLD：Grim / WoodsをFA前にまとめた。幅・glossaryも未解決|

#109 (`scr_1F309BE`): Moltres/Articuno、Shadows、Dehara Cityは原文の待機区間に留まる。
ただしretrievingはsource E3（FA前）からtarget E5（FA後）の「とりかえす」へ遅延。FD/player幅とownerも未解決。
#132: Cinder VolcanoはFA後に保持されたが、Grim Woods完成名はFA前へ移動。全体の意味・幅の承認にはならない。
両件ともprevious_candidate=null。添付入力には修正前draftがないため、「2件を修正して解消」のbefore/after証明は不可。
報告を事実として追認せず、現行segmentsの独立比較で保留した。

注記なし#110（challenge遅延）、#130（次のGym Badge早期開示）、#135（interference遅延・triedの弱化）も保留。
既存英語最大幅gateは32候補でFAIL（secondary込み）。過剰制限の可能性は残すが、今回無効化しない。
FAの数・順序PASSやClaudeのkey-name checkerだけでは、述語・条件・開示タイミングの承認にならない。

## 4. 公式名称13件 / glossary14件

|index|対象|名称gate|
|---|---|---|
|40|titan Pokémon|Unbound固有categoryの承認訳がなくHOLD|
|41,42|Victory Road|同名だけではUnbound locationと本編の同一性を証明できずHOLD|
|49|TM|scope外。独立した正式名称資料なしでHOLD|
|56|HM|Cut=いあいぎりのPokeAPI検証はHM表記の証明ではない。HOLD|
|85|Oak|Professorの記述はあるが本編本人の独立同定はない。HOLD|
|86,87|Pokédex|既存候補使用例から公式辞書名称を承認せずHOLD。#87は日本語文法も再レビュー|
|91|Cac!|サボはサボネア由来の推測。鳴き声の独立証明なしでHOLD|
|92,115|Sankren spells|原文Latin literalとページ切替はPASS、owner不足で最終HOLD|
|123|Ravia!|バードはムクバード由来の推測。独立証明なしでHOLD|
|124|Shadowy reign of terror|quoted question/Seriously?/evilの反論文脈から通常の修辞表現と判定。固有名承認ではない。幅/ownerで最終HOLD|

全official_names_verifiedをローカルPokeAPI cacheのentity/en/ja-hrktとSHA-256で再検証。新しい名称訳は作っていない。
公式資料が不足するwarningは名称HOLDを維持し、width warningへ格下げしない。

scope warning exact IDs: #6 `scr_1F139EF`, #12 `scr_1F143CA`, #41 `scr_1F158DA`, #42 `scr_1F159D8`,
#53 `scr_1F1653E`, #56 `scr_1F1687D`, #59 `scr_1F16B96`, #66 `scr_1F1721D`, #73 `scr_1F1785D`,
#79 `scr_1F2E742`, #110 `scr_1F30B8F`, #112 `scr_1F30E6A`, #129 `scr_1F31FED`, #132 `scr_1F32467`。
Borrius (#6/#79)、KBT Expressway (#12)、Crater Town (#53)、Aklove/Vivill (#59)は既存global許可を確認。
14件中4件のscope問題は既存許可で解決（うち#79はdynamic等により最終保留）。10件には独立entity/scope証明が残る。
Elite Four/Champion/League/Guardian/TM/Mega Evolution/Route [N]/The Shadows/Grim Woodsはscopeを広げず保留。
scope_extension_proposal JSONへexact ID・既存scope・global_replaceを記録。substring置換・global昇格・glossary更新0。

## 5. 幅5件 / 再配置 / pointer

|index|ID|Claude値|今回の判定|
|---|---|---:|---|
|36|scr_1F153ED|217|静的217 > field208、HOLD|
|85|scr_1F2EF1C|210|静的210 > field208、名称も未確定、HOLD|
|118|scr_1F31574|227|静的173 + 仮名幅54の診断値。実際の全name幅/page契約は未証明、HOLD|
|127|scr_1F31E7A|225|静的225 >208、さらに[player]幅未証明、HOLD|
|132|scr_1F32467|210|静的210 >208、FA/glossaryも保留|

#118を173pxだからPASSとはしない。Claudeの227pxは既知最大幅と証明できず、固定54pxを承認budgetへ使わない。
#118/#127は以前の候補を維持したことも承認根拠にしない。通常field/battleの小さい208px制約、独立caller証拠、
source envelope、scroll/page event shapeを併用。自動wrap・240pxまでの余白は仮定しない。

報告再配置候補: #91 `scr_1F2F72C` slot8 / encoded11、#123 `scr_1F317F2` slot10 / encoded12。
両件は先に鳴き声意味gateで保留し、vetted FFがあっても移動させない。
追加の実測候補: #118 slot30 / encoded32。既存controlfixの[player] Latin/Japanese guardsにより増加。
reported候補2件とactual候補3件を混同せず、全3件保留。今回free-space使用0 / pointer writes0。

#99 `scr_1F30020`: ROM 0x01F30020 / GBA 0x09F30020、slot81 / encoded58。
記録owner ROM 0x01E67EEF / GBA 0x09E67EEFはloadpointer 0; 次にcallstd 6。
同一pointer値の追加hit ROM 0x009FF6C2 / GBA 0x089FF6C2は非整列データでconsumer未証明。interior hit0 / stale0。
偶然一致を実pointerと断定しない一方、未分類hitを無視して移動しない。owner gateで保留。

## 6. context / voice / 保護

context28 unique。buffer1=25 / buffer2=3 / #19重複1 / sweetie #68単独。
writer全経路・caller依存・型・値域・最大幅・expansion language pageを証明できないため、全28を維持。
さらにconfirmed内[player]/[rival]33件も未知幅・page契約を理由に保留。名前上限だけでは横幅の証明にならない。
buffer台帳には元handoffの証拠と今回のpointer caller/隣接bytesを保存。値・性別・年齢・親密度を創作しない。

#52の「わたし」はmy testに対応、#83の余分な「きみ」は削除済み、#107は老人語を除去し原文youngsterの呼びかけだけ、
#117は認識文you/playerに対応する最初の「きみ」だけを残す。全4件ともdynamic等で注入なし。
PROVENは話者同定のみ。Carly profileはNEUTRAL_ONLY、JodyはINSUFFICIENT_EVIDENCE。不確実な口調を昇格しない。

既存2,357件のencoded payload（再配置先を含む）、storage全range、全pointer bytesを個別照合。
Sarah `scr_1F02145`、Liam `scr_740753`、Koji `scr_1F06A82`の3修正を保持。
Daniel `scr_1F02029`は既存「とくせいの…」を不変で保持。新たなspecial Attack解釈・voice適用なし。
保留114件のsource slotとownerも前後一致。font/graphics/ASM/renderer/hook変更0。
既存909ファイルをSHA-256集合で保護（ROM・JSON・監査・glossary・voice scriptを含む）。
aggregate: `f932aab110e4dc228c628314c43ce5b0dc0ba89d5f15f6740da9ef6117bad4df`。

## 7. 全140件台帳（全文・metadataはreviewed JSON）

|index|ID|slot|encoded|判定|primary hold|
|---:|---|---:|---:|---|---|
|0|scr_1F136E9|77|48|HOLD|CLAUDE_WORDING_REVIEW_REQUIRED|
|1|scr_1F13736|51|32|APPLY|全gate通過|
|2|scr_1F137A5|122|70|HOLD|FA_SEMANTIC_REVIEW_REQUIRED|
|3|scr_1F1381F|40|28|HOLD|owner_incomplete_or_interior|
|4|scr_1F13847|41|30|APPLY|全gate通過|
|5|scr_1F13870|99|62|HOLD|FA_SEMANTIC_REVIEW_REQUIRED|
|6|scr_1F139EF|129|66|APPLY|全gate通過|
|7|scr_1F13A70|250|134|HOLD|owner_incomplete_or_interior|
|8|scr_1F13DB9|140|88|APPLY|全gate通過|
|9|scr_1F13EED|26|未完成|HOLD|review_needs_context|
|10|scr_1F1404F|96|67|APPLY|全gate通過|
|11|scr_1F142BE|268|未完成|HOLD|review_needs_context|
|12|scr_1F143CA|181|102|APPLY|全gate通過|
|13|scr_1F14516|232|未完成|HOLD|review_needs_context|
|14|scr_1F145FE|37|26|APPLY|全gate通過|
|15|scr_1F14623|211|124|HOLD|fa_source_width_envelope_exceeded|
|16|scr_1F14710|26|未完成|HOLD|review_needs_context|
|17|scr_1F1472A|121|未完成|HOLD|review_needs_context|
|18|scr_1F147A3|28|17|APPLY|全gate通過|
|19|scr_1F147BF|57|未完成|HOLD|review_needs_context|
|20|scr_1F147F8|45|31|APPLY|全gate通過|
|21|scr_1F14825|75|未完成|HOLD|review_needs_context|
|22|scr_1F14870|281|未完成|HOLD|review_needs_context|
|23|scr_1F14989|217|未完成|HOLD|review_needs_context|
|24|scr_1F14B1C|86|56|HOLD|CLAUDE_WORDING_REVIEW_REQUIRED|
|25|scr_1F14B72|220|119|APPLY|全gate通過|
|26|scr_1F14C4E|54|30|APPLY|全gate通過|
|27|scr_1F14C84|22|20|APPLY|全gate通過|
|28|scr_1F14C9A|56|36|HOLD|CLAUDE_WORDING_REVIEW_REQUIRED|
|29|scr_1F14D23|217|108|HOLD|FA_SEMANTIC_REVIEW_REQUIRED|
|30|scr_1F14DFC|143|95|APPLY|全gate通過|
|31|scr_1F14E8B|465|250|HOLD|FA_SEMANTIC_REVIEW_REQUIRED|
|32|scr_1F1505C|129|75|APPLY|全gate通過|
|33|scr_1F15193|93|52|APPLY|全gate通過|
|34|scr_1F151F0|170|88|APPLY|全gate通過|
|35|scr_1F15329|153|86|APPLY|全gate通過|
|36|scr_1F153ED|57|46|HOLD|field_208px_overflow|
|37|scr_1F154D2|68|44|HOLD|renderer_consumer_unproved|
|38|scr_1F15516|60|44|HOLD|renderer_consumer_unproved|
|39|scr_1F1558F|62|44|HOLD|renderer_consumer_unproved|
|40|scr_1F157E9|241|125|HOLD|FA_SEMANTIC_REVIEW_REQUIRED|
|41|scr_1F158DA|254|151|HOLD|FA_SEMANTIC_REVIEW_REQUIRED|
|42|scr_1F159D8|247|148|HOLD|FA_SEMANTIC_REVIEW_REQUIRED|
|43|scr_1F15ACF|180|102|APPLY|全gate通過|
|44|scr_1F15C6C|156|未完成|HOLD|review_needs_context|
|45|scr_1F15D08|58|未完成|HOLD|review_needs_context|
|46|scr_1F15E32|152|未完成|HOLD|review_needs_context|
|47|scr_1F15EFF|171|未完成|HOLD|review_needs_context|
|48|scr_1F15FAA|44|37|HOLD|dynamic_buffer_contract_unproved|
|49|scr_1F15FD6|172|120|HOLD|official_or_project_name_unverified|
|50|scr_1F16082|419|未完成|HOLD|review_needs_context|
|51|scr_1F1640F|97|68|HOLD|CLAUDE_WORDING_REVIEW_REQUIRED|
|52|scr_1F164BE|102|85|HOLD|dynamic_buffer_contract_unproved|
|53|scr_1F1653E|558|329|APPLY|全gate通過|
|54|scr_1F167A0|178|115|HOLD|fa_source_width_envelope_exceeded|
|55|scr_1F16852|43|35|HOLD|dynamic_buffer_contract_unproved|
|56|scr_1F1687D|277|165|HOLD|official_or_project_name_unverified|
|57|scr_1F16992|145|75|APPLY|全gate通過|
|58|scr_1F16ABA|153|89|HOLD|owner_incomplete_or_interior|
|59|scr_1F16B96|310|184|HOLD|glossary_scope_or_target_unapproved|
|60|scr_1F16CCC|170|104|HOLD|dynamic_buffer_contract_unproved|
|61|scr_1F16D8E|370|未完成|HOLD|review_needs_context|
|62|scr_1F16F00|327|未完成|HOLD|review_needs_context|
|63|scr_1F17415|220|121|HOLD|owner_incomplete_or_interior|
|64|scr_1F17172|128|85|HOLD|CLAUDE_WORDING_REVIEW_REQUIRED|
|65|scr_1F171F2|43|37|HOLD|dynamic_buffer_contract_unproved|
|66|scr_1F1721D|192|110|HOLD|glossary_scope_or_target_unapproved|
|67|scr_1F172DD|312|168|HOLD|fa_source_width_envelope_exceeded|
|68|scr_1F174F7|8|未完成|HOLD|review_needs_context|
|69|scr_1F17516|531|316|HOLD|FA_SEMANTIC_REVIEW_REQUIRED|
|70|scr_1F17729|109|64|HOLD|fa_consumer_unproved|
|71|scr_1F17796|159|101|APPLY|全gate通過|
|72|scr_1F17835|40|35|HOLD|dynamic_buffer_contract_unproved|
|73|scr_1F1785D|303|169|HOLD|glossary_scope_or_target_unapproved|
|74|scr_1F1F8F0|236|140|HOLD|fa_source_width_envelope_exceeded|
|75|scr_1F2171A|24|24|APPLY|全gate通過|
|76|scr_1F2DC22|12|未完成|HOLD|review_needs_context|
|77|scr_1F2E4F2|29|29|HOLD|dynamic_buffer_contract_unproved|
|78|scr_1F2E593|363|206|HOLD|dynamic_buffer_contract_unproved|
|79|scr_1F2E742|423|240|HOLD|dynamic_buffer_contract_unproved|
|80|scr_1F2E8E9|239|130|HOLD|fa_source_width_envelope_exceeded|
|81|scr_1F2E9D8|99|65|HOLD|dynamic_buffer_contract_unproved|
|82|scr_1F2EA3B|96|65|HOLD|dynamic_buffer_contract_unproved|
|83|scr_1F2EAAD|48|29|HOLD|dynamic_buffer_contract_unproved|
|84|scr_1F2ECD5|583|未完成|HOLD|review_needs_context|
|85|scr_1F2EF1C|254|147|HOLD|official_or_project_name_unverified|
|86|scr_1F2F01A|43|38|HOLD|dynamic_buffer_contract_unproved|
|87|scr_1F2F045|222|130|HOLD|CLAUDE_WORDING_REVIEW_REQUIRED|
|88|scr_1F2F123|298|173|HOLD|dynamic_buffer_contract_unproved|
|89|scr_1F2F2F2|374|192|HOLD|owner_incomplete_or_interior|
|90|scr_1F2F718|20|20|HOLD|owner_incomplete_or_interior|
|91|scr_1F2F72C|8|11|HOLD|official_or_project_name_unverified|
|92|scr_1F2F759|180|116|HOLD|owner_incomplete_or_interior|
|93|scr_1F2F82B|49|37|APPLY|全gate通過|
|94|scr_1F2F896|291|165|HOLD|owner_incomplete_or_interior|
|95|scr_1F2F9B9|30|未完成|HOLD|review_needs_context|
|96|scr_1F2F9D7|139|85|HOLD|owner_incomplete_or_interior|
|97|scr_1F2FCB5|265|未完成|HOLD|review_needs_context|
|98|scr_1F2FE44|442|253|HOLD|fa_source_width_envelope_exceeded|
|99|scr_1F30020|81|58|HOLD|fa_source_width_envelope_exceeded|
|100|scr_1F30071|165|107|HOLD|dynamic_buffer_contract_unproved|
|101|scr_1F30116|81|61|HOLD|dynamic_buffer_contract_unproved|
|102|scr_1F303F6|272|未完成|HOLD|review_needs_context|
|103|scr_1F30506|229|未完成|HOLD|review_needs_context|
|104|scr_1F305EB|60|48|HOLD|dynamic_buffer_contract_unproved|
|105|scr_1F3068C|254|未完成|HOLD|review_needs_context|
|106|scr_1F307EB|174|105|HOLD|dynamic_buffer_contract_unproved|
|107|scr_1F30899|154|91|HOLD|dynamic_buffer_contract_unproved|
|108|scr_1F30933|139|89|HOLD|dynamic_buffer_contract_unproved|
|109|scr_1F309BE|193|131|HOLD|dynamic_buffer_contract_unproved|
|110|scr_1F30B8F|158|92|HOLD|FA_SEMANTIC_REVIEW_REQUIRED|
|111|scr_1F30C2D|573|380|HOLD|dynamic_buffer_contract_unproved|
|112|scr_1F30E6A|248|135|HOLD|CLAUDE_WORDING_REVIEW_REQUIRED|
|113|scr_1F30F62|25|24|HOLD|dynamic_buffer_contract_unproved|
|114|scr_1F30F7B|129|74|HOLD|dynamic_buffer_contract_unproved|
|115|scr_1F3102E|187|106|HOLD|owner_incomplete_or_interior|
|116|scr_1F3129D|186|108|HOLD|fa_source_width_envelope_exceeded|
|117|scr_1F3145D|146|102|HOLD|dynamic_buffer_contract_unproved|
|118|scr_1F31574|30|32|HOLD|dynamic_buffer_contract_unproved|
|119|scr_1F3164B|59|38|APPLY|全gate通過|
|120|scr_1F31686|105|66|HOLD|fa_source_width_envelope_exceeded|
|121|scr_1F3174B|54|38|HOLD|dynamic_buffer_contract_unproved|
|122|scr_1F31781|87|53|HOLD|dynamic_buffer_contract_unproved|
|123|scr_1F317F2|10|12|HOLD|official_or_project_name_unverified|
|124|scr_1F318B2|241|143|HOLD|fa_source_width_envelope_exceeded|
|125|scr_1F31AF5|139|82|HOLD|dynamic_buffer_contract_unproved|
|126|scr_1F31B80|175|83|HOLD|dynamic_buffer_contract_unproved|
|127|scr_1F31E7A|121|78|HOLD|dynamic_buffer_contract_unproved|
|128|scr_1F31F9F|78|46|APPLY|全gate通過|
|129|scr_1F31FED|320|183|HOLD|glossary_scope_or_target_unapproved|
|130|scr_1F32300|178|100|HOLD|dynamic_buffer_contract_unproved|
|131|scr_1F323B2|154|80|APPLY|全gate通過|
|132|scr_1F32467|99|53|HOLD|FA_SEMANTIC_REVIEW_REQUIRED|
|133|scr_1F32527|20|未完成|HOLD|review_needs_context|
|134|scr_1F3253B|163|未完成|HOLD|review_needs_context|
|135|scr_1F325DE|385|196|HOLD|FA_SEMANTIC_REVIEW_REQUIRED|
|136|scr_1F3275F|95|65|HOLD|fa_source_width_envelope_exceeded|
|137|scr_1F3296E|64|未完成|HOLD|review_needs_context|
|138|scr_1F329AE|79|未完成|HOLD|review_needs_context|
|139|scr_1F329FD|124|80|HOLD|dynamic_buffer_contract_unproved|

## 8. 再現 / QA / 引継ぎ

```text
python scripts/build_ja_phase6_cleanup_batch03.py analyze
python scripts/build_ja_phase6_cleanup_batch03.py build
python scripts/build_ja_phase6_cleanup_batch03.py validate
python -m pytest tests/test_ja_phase6_cleanup_batch03.py -q
python -m pytest -q
python -m py_compile scripts/build_ja_phase6_cleanup_batch03.py tests/test_ja_phase6_cleanup_batch03.py
git diff --check
```

今回pytestはsystem Pythonにpytestがないため既存 `.venv/Scripts/python.exe` を使用。focused38 / all521 / subtests16 PASS。
全出力は既存なら再計算一致を検証するだけ。CLIはpartial出力があれば停止し、既存成果物は上書きしない。
レビューJSONは指定SHAに固定し、違う訳に同じ手動意味判定を流用しない。
controlfix/maps/binary audit/validation等の生成物はout/以下、ROMは非公開・Git対象外。

QA fixtureは25件。FA適用、注記10、口調4、推測鳴き声2、owner99、長文・widthを含む。
全map/eventは未証明のためUNKNOWN。source caller/trainer/object証拠を使って到達イベントを探し、
baselineと新ROMで各FE/FA/FB view、scroll後の行、color/pause、次の英語テキストを比較する。
negative QAのHOLDは基準ROMの本文のままであることを確認。今回mGBA操作は行っていない。

次工程用（実施はしない）: unresolved buffer writer/value/page/width、公式鳴き声・造語、exact glossary scope、
FA述語/条件の待機区間、unclassified pointer hits、物理幅・letter spacing、source envelopeの過剰制限可能性を別々に解消する。
訳文の意味・文法保留はClaude再レビューへ戻し、Codexで独自に書き換えない。過去FA57件の台帳・validatorは不変。
Batch04を開始していない。commit / pushなし。
