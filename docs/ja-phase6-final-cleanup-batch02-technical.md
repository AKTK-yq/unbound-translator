# Phase 6C-4E — Final Cleanup Batch 02 Technical Integration

142件を検証。適用28件、保留114件。Claude本文は書き換えていない。
日本語適用総数2357、Phase 6残り保留820。

## 結果

|項目|結果|
|---|---|
|review|142 IDs / 重複0 / 欠落0 / confirmed93 / context49 / 元英語・候補・confidence保持|
|話者|PROVEN9/7組、PLAUSIBLE29、UNKNOWN104。公式人物認定・profile昇格0|
|controls|confirmed FE153/FB126/FA67。全142件ではFE238/FB196/FA92。母集団を区別|
|FA|55件、完成38/文脈保留17、適用2|
|in-place/relocation/pointer writes|23/5/5|
|既存2,329件|個別encoded payload・再配置先・全pointer bytes不変。Sarah/Liam/Koji保持|
|strict dry-run|元ROM+2,329+safe全体と基準ROM+safe incrementalを照合。全エラー0|
|controlfix|標準 --no-wrap 2回、本文・境界不変、出力JSON byte-for-byte一致|
|binary audit|1691 bytes、unexpected0、runtime/font/graphics patch0|
|ROM SHA-256|`192b43b79f75174d9fd5618c47276d2a21cf47ec58b2a902becbe872b19a0284`|

## 幅とrenderer根拠

ROM 0x003A73BC / GBA 0x083A73BC の26×4 field templateとROM 0x0006FB38の参照を再照合。
battle template ROM 0x00248330 / GBA 0x08248330、printer ROM 0x003FEB64 / GBA 0x083FEB64 は28 tiles、x=2。
物理横幅208/222pxの小さい方208pxを保守上限とした。240px画面幅では判定しない。
Latin ROM 0x001FB100 / GBA 0x081FB100、Japanese ROM 0x0020F500 / GBA 0x0820F500の幅テーブルはコードと同一。
各entryのcallstd/message/trainer/table/bufferstring経路と生byte列をreviewed JSONに記録。実機で全variantを確認したとは主張しない。
FAは既存Phase 6安全モデルのsource最大幅内、208px内、scroll/page event同型、dynamicなしを追加条件とした。
過去の208px診断だけの承認ではなくROM template再照合も実施。ただしtextbox余白・live caller等の未実測はwarning。

## 個別監査

|review番号（0始まり）|ID|判定|主理由|
|---|---|---|---|
|0|scr_1F01267|HOLD|review_needs_context|
|1|scr_1F012BD|HOLD|review_needs_context|
|2|scr_1F016AD|HOLD|review_needs_context|
|3|scr_1F01914|HOLD|review_needs_context|
|4|scr_1F02458|HOLD|review_needs_context|
|5|scr_1F0618A|HOLD|review_needs_context|
|6|scr_1F07244|HOLD|review_needs_context|
|7|scr_1F0729E|HOLD|review_needs_context|
|8|scr_1F0734A|HOLD|bufferstring_consumer_width_and_page_unproved|
|9|scr_1F07406|HOLD|CONTROL_BOUNDARY_REVIEW_REQUIRED|
|10|scr_1F0744B|HOLD|CONTROL_BOUNDARY_REVIEW_REQUIRED|
|11|scr_1F07491|HOLD|CONTROL_BOUNDARY_REVIEW_REQUIRED|
|12|scr_1F075CB|HOLD|review_needs_context|
|13|scr_1F07621|HOLD|review_needs_context|
|14|scr_1F0767D|HOLD|review_needs_context|
|15|scr_1F076B9|HOLD|review_needs_context|
|16|scr_1F0771D|HOLD|review_needs_context|
|17|scr_1F078CB|HOLD|fa_source_width_envelope_exceeded|
|18|scr_1F07929|HOLD|CONTROL_BOUNDARY_REVIEW_REQUIRED|
|19|scr_1F079B1|HOLD|fa_source_width_envelope_exceeded|
|20|scr_1F07AB1|HOLD|CLAUDE_VOICE_REVIEW_REQUIRED|
|21|scr_1F07AE2|HOLD|CONTROL_BOUNDARY_REVIEW_REQUIRED|
|22|scr_1F07B4F|HOLD|review_needs_context|
|23|scr_1F07B70|APPLY|全gate通過|
|24|scr_1F07BC4|HOLD|fa_source_width_envelope_exceeded|
|25|scr_1F07C20|HOLD|glossary_scope_or_target_unapproved|
|26|scr_1F07CAD|APPLY|全gate通過|
|27|scr_1F07D00|HOLD|CONTROL_BOUNDARY_REVIEW_REQUIRED|
|28|scr_1F07D7B|HOLD|CONTROL_BOUNDARY_REVIEW_REQUIRED|
|29|scr_1F07E1E|APPLY|全gate通過|
|30|scr_1F07EC2|HOLD|fa_source_width_envelope_exceeded|
|31|scr_1F08005|HOLD|review_needs_context|
|32|scr_1F080EE|HOLD|review_needs_context|
|33|scr_1F082E2|HOLD|CONTROL_BOUNDARY_REVIEW_REQUIRED|
|34|scr_1F083F2|HOLD|review_needs_context|
|35|scr_1F084BC|HOLD|review_needs_context|
|36|scr_1F08691|HOLD|review_needs_context|
|37|scr_1F08849|HOLD|review_needs_context|
|38|scr_1F08A06|HOLD|review_needs_context|
|39|scr_1F08AC4|HOLD|review_needs_context|
|40|scr_1F08C72|HOLD|review_needs_context|
|41|scr_1F08E36|HOLD|review_needs_context|
|42|scr_1F08F28|HOLD|review_needs_context|
|43|scr_1F08FE2|HOLD|review_needs_context|
|44|scr_1F09154|HOLD|CONTROL_BOUNDARY_REVIEW_REQUIRED|
|45|scr_1F09045|HOLD|CONTROL_BOUNDARY_REVIEW_REQUIRED|
|46|scr_1F0935A|HOLD|review_needs_context|
|47|scr_1F09434|HOLD|review_needs_context|
|48|scr_1F095A6|HOLD|field_208px_overflow|
|49|scr_1F096D7|HOLD|review_needs_context|
|50|scr_1F0974F|HOLD|review_needs_context|
|51|scr_1F09838|HOLD|review_needs_context|
|52|scr_1F098EF|HOLD|review_needs_context|
|53|scr_1F0994C|HOLD|review_needs_context|
|54|scr_1F09A3C|HOLD|CONTROL_BOUNDARY_REVIEW_REQUIRED|
|55|scr_1F09B40|HOLD|CLAUDE_VOICE_REVIEW_REQUIRED|
|56|scr_1F09BFC|APPLY|全gate通過|
|57|scr_1F09D6C|HOLD|CONTROL_BOUNDARY_REVIEW_REQUIRED|
|58|scr_1F09E0D|APPLY|全gate通過|
|59|scr_1F09E94|HOLD|field_208px_overflow|
|60|scr_1F0A0E6|HOLD|field_208px_overflow|
|61|scr_1F0A273|HOLD|field_208px_overflow|
|62|scr_1F0A3F7|HOLD|glossary_scope_or_target_unapproved|
|63|scr_1F0A436|HOLD|CONTROL_BOUNDARY_REVIEW_REQUIRED|
|64|scr_1F0A603|HOLD|review_needs_context|
|65|scr_1F0A708|APPLY|全gate通過|
|66|scr_1F0A789|APPLY|全gate通過|
|67|scr_1F0A83E|HOLD|CONTROL_BOUNDARY_REVIEW_REQUIRED|
|68|scr_1F0A86E|APPLY|全gate通過|
|69|scr_1F0A892|APPLY|全gate通過|
|70|scr_1F0A9FD|HOLD|CONTROL_BOUNDARY_REVIEW_REQUIRED|
|71|scr_1F0AABD|HOLD|CONTROL_BOUNDARY_REVIEW_REQUIRED|
|72|scr_1F0AC39|APPLY|全gate通過|
|73|scr_1F0ABA6|HOLD|fa_source_width_envelope_exceeded|
|74|scr_1F0AD1C|HOLD|fa_source_width_envelope_exceeded|
|75|scr_1F0ADCC|HOLD|CONTROL_BOUNDARY_REVIEW_REQUIRED|
|76|scr_1F0AF31|HOLD|glossary_scope_or_target_unapproved|
|77|scr_1F0B2DB|HOLD|CONTROL_BOUNDARY_REVIEW_REQUIRED|
|78|scr_1F0B7A3|HOLD|review_needs_context|
|79|scr_1F0B9B3|HOLD|review_needs_context|
|80|scr_1F0BE99|HOLD|official_or_project_name_unverified|
|81|scr_1F0C34F|HOLD|CONTROL_BOUNDARY_REVIEW_REQUIRED|
|82|scr_1F0C3AF|HOLD|CONTROL_BOUNDARY_REVIEW_REQUIRED|
|83|scr_1F0C40F|HOLD|CONTROL_BOUNDARY_REVIEW_REQUIRED|
|84|scr_1F0C46E|HOLD|dynamic_buffer_contract_unproved|
|85|scr_1F0C52E|HOLD|dynamic_buffer_contract_unproved|
|86|scr_1F0CAF5|HOLD|dynamic_buffer_contract_unproved|
|87|scr_1F0CBFF|HOLD|dynamic_buffer_contract_unproved|
|88|scr_1F0CD3A|HOLD|fa_source_width_envelope_exceeded|
|89|scr_1F0CDAC|APPLY|全gate通過|
|90|scr_1F0CE14|HOLD|fa_source_width_envelope_exceeded|
|91|scr_1F0CE76|APPLY|全gate通過|
|92|scr_1F0CECE|HOLD|dynamic_buffer_contract_unproved|
|93|scr_1F0D8AA|APPLY|全gate通過|
|94|scr_1F0D935|APPLY|全gate通過|
|95|scr_1F0D98F|HOLD|CONTROL_BOUNDARY_REVIEW_REQUIRED|
|96|scr_1F0D9E7|HOLD|CONTROL_BOUNDARY_REVIEW_REQUIRED|
|97|scr_1F0DAA8|HOLD|owner_incomplete_or_interior|
|98|scr_1F0DAD3|HOLD|owner_incomplete_or_interior|
|99|scr_1F0DD47|HOLD|special_0x25_label_consumer_unproved|
|100|scr_1F0DBDC|HOLD|review_needs_context|
|101|scr_1F0DBF5|HOLD|review_needs_context|
|102|scr_1F0DC27|HOLD|review_needs_context|
|103|scr_1F0DC5C|HOLD|review_needs_context|
|104|scr_1F0DC92|HOLD|review_needs_context|
|105|scr_1F0DD20|APPLY|全gate通過|
|106|scr_1F0E10C|HOLD|review_needs_context|
|107|scr_1F0E1D0|HOLD|owner_incomplete_or_interior|
|108|scr_1F0E49D|HOLD|dynamic_buffer_contract_unproved|
|109|scr_1F0E59E|HOLD|owner_incomplete_or_interior|
|110|scr_1F0E66E|APPLY|全gate通過|
|111|scr_1F0E68D|HOLD|CONTROL_BOUNDARY_REVIEW_REQUIRED|
|112|scr_1F0E798|HOLD|CONTROL_BOUNDARY_REVIEW_REQUIRED|
|113|scr_1F0E9EB|HOLD|review_needs_context|
|114|scr_1F0EDB9|HOLD|review_needs_context|
|115|scr_1F0EED7|HOLD|review_needs_context|
|116|scr_1F113ED|HOLD|CONTROL_BOUNDARY_REVIEW_REQUIRED|
|117|scr_1F116D7|APPLY|全gate通過|
|118|scr_1F116E1|APPLY|全gate通過|
|119|scr_1F116E9|APPLY|全gate通過|
|120|scr_1F11888|HOLD|CLAUDE_VOICE_REVIEW_REQUIRED|
|121|scr_1F1194E|HOLD|review_needs_context|
|122|scr_1F11C19|APPLY|全gate通過|
|123|scr_1F11C50|APPLY|全gate通過|
|124|scr_1F121E3|HOLD|review_needs_context|
|125|scr_1F12282|HOLD|review_needs_context|
|126|scr_1F126CE|APPLY|全gate通過|
|127|scr_1F12A15|HOLD|owner_incomplete_or_interior|
|128|scr_1F12CAD|APPLY|全gate通過|
|129|scr_1F12CEE|APPLY|全gate通過|
|130|scr_1F12D0F|APPLY|全gate通過|
|131|scr_1F12D4E|APPLY|全gate通過|
|132|scr_1F12D90|APPLY|全gate通過|
|133|scr_1F12DCE|APPLY|全gate通過|
|134|scr_1F12FC6|HOLD|review_needs_context|
|135|scr_1F130DC|HOLD|CONTROL_BOUNDARY_REVIEW_REQUIRED|
|136|scr_1F13208|HOLD|owner_incomplete_or_interior|
|137|scr_1F1330A|HOLD|CONTROL_BOUNDARY_REVIEW_REQUIRED|
|138|scr_1F132B8|HOLD|field_208px_overflow|
|139|scr_1F13412|HOLD|fa_source_width_envelope_exceeded|
|140|scr_1F13518|HOLD|CONTROL_BOUNDARY_REVIEW_REQUIRED|
|141|scr_1F13575|HOLD|CONTROL_BOUNDARY_REVIEW_REQUIRED|

## 特別FA / trophy / voice

- `scr_1F09154`: HOLD; Science Society is merged into E4 across FE; cloned shifts E4 to E5.; width [140, 79, 100, 130, 159, 209, 140]
- `scr_1F0A436`: HOLD; Paradise moves E1 to E0 across FE; Honey Gather also splits differently at FE.; width [170, 140, 100, 100, 180, 160, 208, 140]
- `scr_1F1330A`: HOLD; endangered/growing-back exchange E5/E6 across FA; service/obligation exchange E8/E9 across FA.; width [170, 140, 168, 149, 160, 180, 90, 169, 160, 90]
- `scr_1F0C34F`: HOLD; Frontier Brain moves E1 to E0; Single Battle moves E2 to E1 before FA; trophy moves after FA.; width [189, 169, 114]
- `scr_1F0C3AF`: HOLD; Frontier Brain moves E1 to E0; Double Battle moves E2 to E1 before FA; trophy moves after FA.; width [189, 159, 114]
- `scr_1F0C40F`: HOLD; Frontier Brain moves E1 to E0; Multi Battle moves E2 to E1 before FA; trophy moves after FA.; width [189, 159, 114]
- `scr_1F0AC39`: APPLY; 語句・waitを保持; width [167]

#44/#63/#137は意味境界の移動が残るため保留。#81～#83はFE/FA/終端の3 segmentsを正しく再構築できるが、
Battle formatがFAの後から前へ移るため、構造PASSと意味境界PASSを区別して保留。
#72は「あなたは」「ようね」を削除したClaude訳のまま計算。以前247pxから167pxへ短縮。
追加の口調/意味問題もCLAUDE_VOICE_REVIEW_REQUIREDとして台帳に保存。新規訳なし。

## 公式名称 / glossary

- `scr_1F09D6C`: PASS; ['VERIFIED_EXACT_ENTITY', 'VERIFIED_EXACT_ENTITY']; HOLD
- `scr_1F09E0D`: PASS; ['VERIFIED_EXACT_ENTITY', 'VERIFIED_EXACT_ENTITY', 'VERIFIED_EXACT_ENTITY']; APPLY
- `scr_1F09E94`: PASS; ['VERIFIED_EXACT_ENTITY', 'VERIFIED_EXACT_ENTITY']; HOLD
- `scr_1F0A708`: PASS; ['PROJECT_SCOPED_APPROVED']; APPLY
- `scr_1F0A83E`: HOLD; ['Capitalized Roar may name move roar; ほえごえ is not its exact official name ほえる. Caller semantics unproved.']; HOLD
- `scr_1F0AABD`: PASS; ['VERIFIED_EXACT_ENTITY', 'VERIFIED_EXACT_ENTITY', 'ORDINARY_BATTLE_FORMAT']; HOLD
- `scr_1F0ADCC`: PASS; ['VERIFIED_EXACT_ENTITY', 'VERIFIED_EXACT_ENTITY', 'ORDINARY_BATTLE_FORMAT']; HOLD
- `scr_1F0B2DB`: HOLD; ['Crobat species verification does not approve the new proper name Crobatman.']; HOLD
- `scr_1F0BE99`: HOLD; ['Cube is approved in restricted scope, but Super Cube is a distinct unapproved form.']; HOLD
- `scr_1F0C46E`: HOLD; ['Redwood Village is outside its approved entry scope; no independent location identity proof.']; HOLD
- `scr_1F0C52E`: HOLD; ['Gurun Town and Route 18 are outside approved scopes; no independent map binding proof.']; HOLD
- `scr_1F0D8AA`: PASS; ['SOURCE_SPELLING_RETAINED']; APPLY
- `scr_1F0E798`: HOLD; ['Ferrothorn species name does not prove the Black Ferrothorn organization identity in this script.']; HOLD

全official_names_verifiedをローカルPokeAPIのen/ja-hrkt exact entityとSHA256で再検証。
Gracideaはcache flavorに花・花束・感謝の独立記述があり名称を検証。Roarはmove/一般語未確定のため保留。
2たい2は普通の対戦形式、Fighting動詞はタイプ名に置換しない。Frost Mountainの対象entryは承認scope内。
Sankren fimbulvetr!は原文スペルをそのまま保持し、意味や音写を創作しない。
13 warningと技術HOLDは同一ではない。Botanical項目は公式根拠が解決しても意味境界/幅gateで別途保留になり得る。

scope gap報告10件をmatcherで再検証。Borrius/Region・Cloud Burstは実際には既存global scope。
Honey Gatherはability exact entityで独立確認し、mission titleのscopeを広げない。その他のgapは保留。
9語proposalは既存scope/entry IDs/entity未解決点を保存するだけ。glossary 292語・global_replace不変。

## 再配置7件 / buffer台帳

- `scr_1F0734A`: slot9, encoded10; HOLD; owners ['0x01E6AD2C']; missing []; interior []
- `scr_1F0D8AA`: slot20, encoded24; APPLY; owners ['0x01E6E125']; missing []; interior []
- `scr_1F0DD47`: slot4, encoded10; HOLD; owners ['0x01E6EDE2']; missing []; interior []
- `scr_1F116D7`: slot10, encoded11; APPLY; owners ['0x01E70568']; missing []; interior []
- `scr_1F116E1`: slot8, encoded10; APPLY; owners ['0x01E7058F']; missing []; interior []
- `scr_1F116E9`: slot9, encoded11; APPLY; owners ['0x01E705B9']; missing []; interior []
- `scr_1F11C50`: slot15, encoded17; APPLY; owners ['0x01E70BAA']; missing []; interior []

49 context holdは重複を含むbuffer別membershipとunique IDの両方を保存。値を推測して昇格しない。
追加で[player]は名前上限だけではexpansion page/全値の幅を証明できず保留。bufferstringもconsumer未証明を保留。
再配置は既存基準ROMでFFのvetted範囲だけを使用。全owner更新・旧exact pointerなし・interiorなし・旧本文保持を監査。

interior/exactの追加hitは生4byteの一致であり、graphics等の偶然一致を実pointerと断定しない。未分類hitは安全側で保留。
28件の適用には原文ラテン表記を維持した呪文1件を含む。新規かな本文は27件。
初回30件buildは意味境界の最終再検査後、out/phase6/recovery_cleanup_batch02_attempt1/に全成果物を退避。上書き・削除なし。

## 再現 / QA / 次工程

`python scripts/build_ja_phase6_cleanup_batch02.py all`。全成果物は既存なら再計算一致・監査のみ、上書き禁止。
reviewed/technical_holds/scope_extension_proposal/controlfix/maps/binary_auditをout/phase6へ保存。
runtime QA fixtureは20件、操作未実施。PROVEN話者・FA・再配置・長文・用語確認・#72・negative holdを含む。
Batch03以降は同じspeakerのprofile confidenceを維持。FAは語句を入力待ちの前後へ移すと構造一致でも保留。
glossary referenceとscope match、species名とorganization名を区別。PokeAPI対象外の名称は公式と呼ばない。
wrapで208px超過を隠さない。全値が未証明のbufferには仮54pxを使って承認しない。
最終pytest/py_compile/git diff --checkはvalidation JSONに記録。Batch03/04・commit/pushは未実施。

## 最終回帰検証

pytest: 483 passed / 16 subtests passed。
py_compile PASS、git diff --check PASS。
system pythonにpytestがないため、既存 .venv/Scripts/python.exe を使用。
incremental vetted FF使用73 bytes、残610,199 bytes、reclaimed使用0。
tracked既存ファイル変更0。新規script/test/report/runtime QA fixtureの4ファイル。
