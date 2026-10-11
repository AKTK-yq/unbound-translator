# Phase 7C-3: Story Priority Batch 01 Technical Integration

独立監査完了。53件すべて技術保留、適用0件。新ROMは生成していない。Claude confirmed53は変更しない。

## テスト修復・保護

失敗原因はPhase 7C-2のレビュー3成果物が既存909-file snapshotの後工程allowlistに未登録だったこと。
scripts/build_ja_phase6_cleanup_batch03.py の完全一致パス集合と対応するBatch03/04テストだけを更新。
909件・期待aggregate `f932aab110e4dc228c628314c43ce5b0dc0ba89d5f15f6740da9ef6117bad4df` は不変。validator本体/期待hash/skip/xfailは変更なし。
許可から1件を除く負例、許可外ファイルを追加する負例はFAILを確認する回帰テストを追加。
独立監査前に全pytest 610 PASS + 16 subtests。最終回帰は下記。

## 件数

```json
{
  "entries": 53,
  "confirmed_translation": 53,
  "safe": 0,
  "held": 53,
  "in_place": 0,
  "relocations": 0,
  "pointer_writes": 0,
  "japanese_applied_total": 2403,
  "phase6_remaining": 774,
  "phase6_remaining_ids_sha256": "8eda86fd40f3034ceb8e05da0777d8362defe997bf1a5889e8601c22a55c9979",
  "status_counts": {
    "HOLD_POINTER": 15,
    "HOLD_SEMANTIC": 5,
    "HOLD_RENDERER": 15,
    "HOLD_GLOSSARY_SCOPE": 8,
    "HOLD_BUFFER": 9,
    "HOLD_OFFICIAL_NAME": 1
  },
  "all_hold_family_counts": {
    "HOLD_POINTER": 29,
    "HOLD_RENDERER": 53,
    "HOLD_WIDTH": 22,
    "HOLD_SEMANTIC": 5,
    "HOLD_GLOSSARY_SCOPE": 14,
    "HOLD_OFFICIAL_NAME": 2,
    "HOLD_BUFFER": 10
  },
  "fa_entries": 21,
  "fa_segments": 180,
  "fa_controls": 39,
  "fa_semantic_counts": {
    "PASS_WITH_NOTE": 9,
    "FA_SEMANTIC_BOUNDARY_REVIEW_REQUIRED": 3,
    "PASS_PHASE_COMPARISON": 9
  },
  "phrase_notes": 12,
  "name_buffer_entries": 10,
  "scope_gap_entries": 14,
  "official_name_entries": 2,
  "pcs_errors": 0,
  "control_errors": 0,
  "kanji": 0,
  "source_control_counts": {
    "FE": 105,
    "FB": 95,
    "FA": 39,
    "FC": 32,
    "FD": 10
  },
  "normal_spacing0_max_static": 200,
  "normal_spacing1_max_static_diagnostic": 220,
  "spacing1_candidate_208_exceedances": [
    0,
    1,
    6,
    7,
    12,
    13,
    15,
    19,
    20,
    22,
    24,
    28,
    32,
    34,
    36,
    39,
    40,
    41,
    45,
    49,
    52
  ],
  "relocation_candidates": [
    21
  ],
  "exact_raw_extra_hit_entries": [
    50
  ],
  "interior_raw_candidate_entries": 29,
  "interior_raw_candidate_count": 148,
  "runtime_qa_count": 23,
  "runtime_qa_performed": false
}
```

## ROMから確認した描画経路と未証明点

53 ownerの命令はすべて`0F 00 <text pointer> 09 06`。callstd handler ROM0006A180/GBA0806A180が
ROM00160450/GBA08160450のstd tableを使用し、slot6 owner ROM00160468/GBA08160468は
ROM01E7D5DA/GBA09E7D5DAへ向く。bytes `8a 67 00 00 00 00 66 6d 6c 03 03`。
message opcode67のtable owner ROM0015FB50/GBA0815FB50 → ROM00A093AC/GBA08A093AC。
そのhandlerがliteral ROM00A093F8の0806943Dを呼び、ROM000694C8/GBA080694C8で
ROM00008FCC/GBA08008FCCのplaceholder展開、ROM000F6D5C/GBA080F6D5Cのprinter setupへ進む。
ROM000F6D78がfont selector ROM000CBE00/GBA080CBE00を呼ぶ。これは
ROM000CBE04の089C9EE1によるhookで、ROM009C9EE0/GBA089C9EE0がRAM状態から分岐する。
setupはfont4/5/2へ分岐。ROM000F6CD0/GBA080F6CD0のprinter templateにはx=0,y=1,letterSpacing=1。
ROM00002CF4/GBA08002CF4がtemplateをprinterへコピーする。これらは局所コード証拠であり全rootのlive状態証明ではない。
field候補template ROM003A73BC/GBA083A73BCは26×4 tiles=208pxだが、各rootのnative opcode8A/別window初期化・
override・font4/5 metricsの全variantを証明できていない。208px/240pxやscript分類による一律承認は禁止。

幅table: Latin ROM001FB100/GBA081FB100、Japanese normal ROM0020F500/GBA0820F500(280 bytes)をROMで再照合。
既存width calculatorでnormal/spacing0静的最大200px。
しかしROMで観測したspacing1をnormal fontに条件付き適用すると最大220px。
候補208超indices=[0, 1, 6, 7, 12, 13, 15, 19, 20, 22, 24, 28, 32, 34, 36, 39, 40, 41, 45, 49, 52]。実font4/5のoverflow確定とは区別する。
FDを幅0の本文として合格にせず、動的幅はUNKNOWN。英語最大行幅を超える既存FA gateも変更しない。

## FA・意味監査

ROMの終端境界から21件180 segments/FA39を再取得。FE/FBもwait区間へ反映し、Claude phase_viewを承認には使わない。
意味監査は全文/全FA区間で実施。#19 mustの確度、#40 most importantの欠落、#49 no known methodsの断定化を
CLAUDE_REVIEW_REQUIREDにした。#1/16/24/41/47の語気差は台帳の個別noteに記録。訳文は一文字も修正していない。
#1のdark force完成形、#31/#40のLight of Ruin完成形の先行はFA_SEMANTIC_BOUNDARY_REVIEW_REQUIRED。
#31原文P3→日本語P2、#40原文P2→日本語P1。英語のLight ofが先に見える点も検討したが、
完成形の早期開示と同等であること、驚き/伏線への影響は証明できない。FAを動かして救済しない。

|index|ID|FA注記の独立判定|根拠|
|---:|---|---|---|
|0|scr_1F113ED|PASS_WITH_NOTE|P2で機械の変換述語、P3でweapon/Ultimate Weapon。倒置だが重要名は後のwait。|
|1|scr_1F11594|FA_SEMANTIC_BOUNDARY_REVIEW_REQUIRED|原文P3 dark / P4 force。訳P3やみのちから。重要な力の完成形の早期開示を同等と証明できない。|
|13|scr_1F2F55D|PASS_WITH_NOTE|求めた報酬への道(P1)、加入した時(P2)。修飾の後置を注記。|
|15|scr_1F2F5EA|PASS_WITH_NOTE|必要品の条件(P1)、operation/科学者が作る(P2)、母の望む手足(P3)。倒置を注記。|
|30|scr_1F3EE0A|PASS_WITH_NOTE|指揮をとる(P3)、残るShadows(P4)。後置所有句で読みにくいが対象は後のwait。|
|31|scr_1F3EED6|FA_SEMANTIC_BOUNDARY_REVIEW_REQUIRED|原文完成形Light of Ruin=P3、訳はめつのひかり=P2。攻撃対象名をFA前に完成させる。|
|32|scr_1F3EF60|PASS_WITH_NOTE|Prison Bottle/Warriors/remainingのwait維持。奪還述語の再掲とoff guardの倒置を注記。|
|34|scr_1F3F277|PASS_WITH_NOTE|could not care lessの否定を先に言い、Aklove goalsを後に言う。無関心の強意完成は早まるが固有目的は維持。|
|35|scr_1F3F3C9|PASS_WITH_NOTE|hitchの完結はP1→P0。進行条件/固有名の開示ではなくwithout aの修飾を先に完成する自然な語順差。|
|37|scr_1F3F64A|PASS_WITH_NOTE|trip inside(P0)はなかに(P1)へ遅れる。Cube名と第三者/存在の知識は原文waitに残る。|
|40|scr_1F3F846|FA_SEMANTIC_BOUNDARY_REVIEW_REQUIRED|原文完成形Light of Ruin=P2、訳はめつのひかり=P1。攻撃対象名をFA前に完成させる。|
|48|scr_1F3FC2A|PASS_WITH_NOTE|thought about trying(P0)、bring him back(P1)。蘇生の目的はFA後に残る。|

注記なし9件も同じ基準で全wait区間を比較。重要名詞・述語は概ね維持（#49の本文断定化は別保留）。

## 名前buffer・用語

FD01はfield展開ROM00009004/GBA08009004→ROM000091E0/GBA080091E0のdispatch。
table ROM00231E70/GBA08231E70、FD01 owner ROM00231E74/GBA08231E74→ROM00009120/GBA08009120。
producerはRAM0300500Cのrecord pointerを返し、展開器は再帰copyする。renderer側のFD skipとは別。
名前keyboard ROM003E22D0/GBA083E22D0、player template ROM003E245C/GBA083E245Cは7文字上限。
既存rom_naming_profilesのnormal Latin条件付き最大42px。writer→保存recordの全経路/外部値/
各fontの最悪幅は未証明、10件ともbuffer保留。controlfixは[latin][player][japanese]を入れるが、
任意buffer内のFCを含む値までpage安全とする証明ではない。FE/FA/FBのhandlersは言語flagをresetしない。

scope警告14件: 台帳にはexact ID、英語語句、候補、glossaryのcategory/entry IDs/scope、
独立証拠を記録。全14件、既存使用歴だけでは新scope承認にしない。
#19 Rift Caveはevent map bindingで地名と確認できるが、さけめのどうくつの正式project承認なし。
#32 Prison Bottleは原文literalと既存どうぐ名の一致だけ。該当会話をitem番号へ結ぶoperand証明なし、entity保留。

## Pointer・容量・dry-run・controlfix

#21 scr_1F46217: ROM01F46217/GBA09F46217、owner ROM01E82C9B/GBA09E82C9B。
元slot19 bytes、日本語23 bytes（FC15/16と終端を含む）。whole-ROM exact/interior scanは台帳に記録。
唯一のoversized候補。live renderer未承認なので実際の割当・pointer writeは0。
#21のexact ownerは記録と一致、interior raw hit0。53件全体では29件にinterior候補、#50に追加exact raw hit。
それらは実ownerと確定したものではない。圧縮/画像等の偶然一致を除く構造証明はUNKNOWNで、保守的にpointer保留。
vetted FFの残量はinjectorのempty planに記録されるが、#21にdestinationは選んでいない。
controlfix --no-wrapを53件の診断入力に2回。FA layout未承認flagはfalseのまま、21件が正しく拒否される。
32 non-FAは既存page処理とnewlineのescape表記化のみ、candidateのencoded bytes変更0。
結果は2回byte-identical、control mismatch0。これはFA21注入承認ではない。
既存2403件はcontrolfix入力へ渡していない。
strict incremental dry-runは本物のinjectorにsafe subset0件を渡した診断。encode/pointer/truncation/
runtime/graphics patch等0を既存assert_strict_mapで確認。ただし53件のcapacity/注入承認と誤記しない。

## Binary audit・ROM

基準ROM SHA-256 `0d1d00e7b0f4f113514abbcf1907e6d8949fd12b9193bf2cb0ad764ace5559d8` が作業前後不変。2403件のpayloadとrecorded ownerも基準ROMで再照合。
新ROMなし、新ROMhash=null。in-place/relocated/pointer writes各0、changed offsetなし。
これは基準ROMの不変監査であり、存在しない新ROMとの差分PASSを捏造しない。Phase6残774件のID集合も不変。

## 全53件

|index|ID|slot / encoded|normal0 / conditional1 px|primary|secondary|
|---:|---|---|---|---|---|
|0|scr_1F113ED|254 / 146|200 / 220|HOLD_POINTER:unresolved_owner_or_interior_reference|HOLD_WIDTH:existing_fa_source_envelope_gate_retained; HOLD_RENDERER:font_variants_and_live_viewport_unproved; HOLD_WIDTH:conditional_normal_spacing1_exceeds_candidate_208|
|1|scr_1F11594|240 / 131|190 / 209|HOLD_SEMANTIC:FA_SEMANTIC_BOUNDARY_REVIEW_REQUIRED|HOLD_RENDERER:font_variants_and_live_viewport_unproved; HOLD_WIDTH:conditional_normal_spacing1_exceeds_candidate_208|
|2|scr_1F1184B|25 / 19|135 / 149|HOLD_RENDERER:font_variants_and_live_viewport_unproved||
|3|scr_1F11864|26 / 18|125 / 138|HOLD_RENDERER:font_variants_and_live_viewport_unproved||
|4|scr_1F11CFD|24 / 17|120 / 132|HOLD_RENDERER:font_variants_and_live_viewport_unproved||
|5|scr_1F2F718|20 / 20|115 / 127|HOLD_POINTER:unresolved_owner_or_interior_reference|HOLD_RENDERER:font_variants_and_live_viewport_unproved|
|6|scr_1F2E8E9|239 / 129|194 / 214|HOLD_POINTER:unresolved_owner_or_interior_reference|HOLD_WIDTH:existing_fa_source_envelope_gate_retained; HOLD_RENDERER:font_variants_and_live_viewport_unproved; HOLD_WIDTH:conditional_normal_spacing1_exceeds_candidate_208|
|7|scr_1F2EB85|133 / 88|197 / 217|HOLD_POINTER:unresolved_owner_or_interior_reference|HOLD_RENDERER:font_variants_and_live_viewport_unproved; HOLD_WIDTH:conditional_normal_spacing1_exceeds_candidate_208|
|8|scr_1F2EC73|98 / 66|170 / 187|HOLD_RENDERER:font_variants_and_live_viewport_unproved||
|9|scr_1F2F468|43 / 31|177 / 195|HOLD_GLOSSARY_SCOPE:entry_scope_not_approved|HOLD_RENDERER:font_variants_and_live_viewport_unproved|
|10|scr_1F2F493|17 / 17|120 / 132|HOLD_RENDERER:font_variants_and_live_viewport_unproved||
|11|scr_1F2F4A4|31 / 23|178 / 196|HOLD_RENDERER:font_variants_and_live_viewport_unproved||
|12|scr_1F2F4C3|154 / 96|200 / 220|HOLD_POINTER:unresolved_owner_or_interior_reference|HOLD_WIDTH:existing_fa_source_envelope_gate_retained; HOLD_RENDERER:font_variants_and_live_viewport_unproved; HOLD_WIDTH:conditional_normal_spacing1_exceeds_candidate_208|
|13|scr_1F2F55D|97 / 68|190 / 209|HOLD_RENDERER:font_variants_and_live_viewport_unproved|HOLD_WIDTH:conditional_normal_spacing1_exceeds_candidate_208|
|14|scr_1F2F5BE|44 / 23|100 / 110|HOLD_RENDERER:font_variants_and_live_viewport_unproved||
|15|scr_1F2F5EA|180 / 110|200 / 220|HOLD_POINTER:unresolved_owner_or_interior_reference|HOLD_WIDTH:existing_fa_source_envelope_gate_retained; HOLD_RENDERER:font_variants_and_live_viewport_unproved; HOLD_WIDTH:conditional_normal_spacing1_exceeds_candidate_208|
|16|scr_1F2F69E|122 / 74|170 / 187|HOLD_POINTER:unresolved_owner_or_interior_reference|HOLD_RENDERER:font_variants_and_live_viewport_unproved|
|17|scr_1FA54AC|61 / 37|170 / 187|HOLD_RENDERER:font_variants_and_live_viewport_unproved||
|18|scr_1F460D1|22 / 19|103 / 114|HOLD_RENDERER:font_variants_and_live_viewport_unproved||
|19|scr_1F460E7|146 / 98|200 / 220|HOLD_SEMANTIC:CLAUDE_REVIEW_REQUIRED|HOLD_OFFICIAL_NAME:entity_or_project_name_approval_missing; HOLD_RENDERER:font_variants_and_live_viewport_unproved; HOLD_WIDTH:conditional_normal_spacing1_exceeds_candidate_208|
|20|scr_1F46179|158 / 108|200 / 220|HOLD_BUFFER:writer_values_page_and_live_width_unproved|HOLD_GLOSSARY_SCOPE:entry_scope_not_approved; HOLD_RENDERER:font_variants_and_live_viewport_unproved; HOLD_WIDTH:conditional_normal_spacing1_exceeds_candidate_208|
|21|scr_1F46217|19 / 23|176 / 194|HOLD_RENDERER:font_variants_and_live_viewport_unproved||
|22|scr_1F4622A|266 / 159|198 / 218|HOLD_BUFFER:writer_values_page_and_live_width_unproved|HOLD_RENDERER:font_variants_and_live_viewport_unproved; HOLD_WIDTH:conditional_normal_spacing1_exceeds_candidate_208|
|23|scr_1F751D8|23 / 20|150 / 165|HOLD_RENDERER:font_variants_and_live_viewport_unproved||
|24|scr_1F3EA65|174 / 108|200 / 220|HOLD_GLOSSARY_SCOPE:entry_scope_not_approved|HOLD_POINTER:unresolved_owner_or_interior_reference; HOLD_WIDTH:existing_fa_source_envelope_gate_retained; HOLD_RENDERER:font_variants_and_live_viewport_unproved; HOLD_WIDTH:conditional_normal_spacing1_exceeds_candidate_208|
|25|scr_1F3EB13|167 / 98|168 / 185|HOLD_POINTER:unresolved_owner_or_interior_reference|HOLD_RENDERER:font_variants_and_live_viewport_unproved|
|26|scr_1F3EBBA|49 / 40|145 / 160|HOLD_BUFFER:writer_values_page_and_live_width_unproved|HOLD_POINTER:unresolved_owner_or_interior_reference; HOLD_RENDERER:font_variants_and_live_viewport_unproved|
|27|scr_1F3EBEB|137 / 96|180 / 199|HOLD_POINTER:unresolved_owner_or_interior_reference|HOLD_RENDERER:font_variants_and_live_viewport_unproved|
|28|scr_1F3EC74|299 / 193|200 / 220|HOLD_BUFFER:writer_values_page_and_live_width_unproved|HOLD_POINTER:unresolved_owner_or_interior_reference; HOLD_WIDTH:existing_fa_source_envelope_gate_retained; HOLD_RENDERER:font_variants_and_live_viewport_unproved; HOLD_WIDTH:conditional_normal_spacing1_exceeds_candidate_208|
|29|scr_1F3EDA8|98 / 75|176 / 194|HOLD_BUFFER:writer_values_page_and_live_width_unproved|HOLD_POINTER:unresolved_owner_or_interior_reference; HOLD_WIDTH:existing_fa_source_envelope_gate_retained; HOLD_RENDERER:font_variants_and_live_viewport_unproved|
|30|scr_1F3EE0A|204 / 120|180 / 198|HOLD_BUFFER:writer_values_page_and_live_width_unproved|HOLD_GLOSSARY_SCOPE:entry_scope_not_approved; HOLD_RENDERER:font_variants_and_live_viewport_unproved|
|31|scr_1F3EED6|138 / 86|189 / 208|HOLD_SEMANTIC:FA_SEMANTIC_BOUNDARY_REVIEW_REQUIRED|HOLD_POINTER:unresolved_owner_or_interior_reference; HOLD_RENDERER:font_variants_and_live_viewport_unproved|
|32|scr_1F3EF60|694 / 392|200 / 220|HOLD_OFFICIAL_NAME:entity_or_project_name_approval_missing|HOLD_GLOSSARY_SCOPE:entry_scope_not_approved; HOLD_POINTER:unresolved_owner_or_interior_reference; HOLD_WIDTH:existing_fa_source_envelope_gate_retained; HOLD_RENDERER:font_variants_and_live_viewport_unproved; HOLD_WIDTH:conditional_normal_spacing1_exceeds_candidate_208|
|33|scr_1F3F216|97 / 55|159 / 175|HOLD_GLOSSARY_SCOPE:entry_scope_not_approved|HOLD_RENDERER:font_variants_and_live_viewport_unproved|
|34|scr_1F3F277|338 / 209|200 / 220|HOLD_GLOSSARY_SCOPE:entry_scope_not_approved|HOLD_POINTER:unresolved_owner_or_interior_reference; HOLD_RENDERER:font_variants_and_live_viewport_unproved; HOLD_WIDTH:conditional_normal_spacing1_exceeds_candidate_208|
|35|scr_1F3F3C9|159 / 107|180 / 198|HOLD_BUFFER:writer_values_page_and_live_width_unproved|HOLD_POINTER:unresolved_owner_or_interior_reference; HOLD_RENDERER:font_variants_and_live_viewport_unproved|
|36|scr_1F3F514|310 / 187|190 / 209|HOLD_BUFFER:writer_values_page_and_live_width_unproved|HOLD_GLOSSARY_SCOPE:entry_scope_not_approved; HOLD_POINTER:unresolved_owner_or_interior_reference; HOLD_RENDERER:font_variants_and_live_viewport_unproved; HOLD_WIDTH:conditional_normal_spacing1_exceeds_candidate_208|
|37|scr_1F3F64A|171 / 89|189 / 208|HOLD_GLOSSARY_SCOPE:entry_scope_not_approved|HOLD_POINTER:unresolved_owner_or_interior_reference; HOLD_RENDERER:font_variants_and_live_viewport_unproved|
|38|scr_1F3F6F5|124 / 78|149 / 164|HOLD_BUFFER:writer_values_page_and_live_width_unproved|HOLD_GLOSSARY_SCOPE:entry_scope_not_approved; HOLD_POINTER:unresolved_owner_or_interior_reference; HOLD_RENDERER:font_variants_and_live_viewport_unproved|
|39|scr_1F3F771|213 / 138|200 / 220|HOLD_POINTER:unresolved_owner_or_interior_reference|HOLD_RENDERER:font_variants_and_live_viewport_unproved; HOLD_WIDTH:conditional_normal_spacing1_exceeds_candidate_208|
|40|scr_1F3F846|386 / 230|190 / 209|HOLD_SEMANTIC:CLAUDE_REVIEW_REQUIRED|HOLD_SEMANTIC:FA_SEMANTIC_BOUNDARY_REVIEW_REQUIRED; HOLD_BUFFER:writer_values_page_and_live_width_unproved; HOLD_GLOSSARY_SCOPE:entry_scope_not_approved; HOLD_RENDERER:font_variants_and_live_viewport_unproved; HOLD_WIDTH:conditional_normal_spacing1_exceeds_candidate_208|
|41|scr_1F3F9C8|140 / 83|199 / 219|HOLD_GLOSSARY_SCOPE:entry_scope_not_approved|HOLD_POINTER:unresolved_owner_or_interior_reference; HOLD_RENDERER:font_variants_and_live_viewport_unproved; HOLD_WIDTH:conditional_normal_spacing1_exceeds_candidate_208|
|42|scr_1F3FA54|97 / 66|168 / 185|HOLD_RENDERER:font_variants_and_live_viewport_unproved||
|43|scr_1F3FAB5|103 / 58|166 / 183|HOLD_POINTER:unresolved_owner_or_interior_reference|HOLD_RENDERER:font_variants_and_live_viewport_unproved|
|44|scr_1F3FB1C|66 / 33|98 / 108|HOLD_POINTER:unresolved_owner_or_interior_reference|HOLD_RENDERER:font_variants_and_live_viewport_unproved|
|45|scr_1F3FB5E|81 / 52|199 / 219|HOLD_RENDERER:font_variants_and_live_viewport_unproved|HOLD_WIDTH:conditional_normal_spacing1_exceeds_candidate_208|
|46|scr_1F3FBAF|53 / 33|140 / 154|HOLD_POINTER:unresolved_owner_or_interior_reference|HOLD_RENDERER:font_variants_and_live_viewport_unproved|
|47|scr_1F3FBE4|70 / 51|178 / 196|HOLD_POINTER:unresolved_owner_or_interior_reference|HOLD_RENDERER:font_variants_and_live_viewport_unproved|
|48|scr_1F3FC2A|90 / 62|189 / 208|HOLD_RENDERER:font_variants_and_live_viewport_unproved||
|49|scr_1F3FC84|381 / 243|200 / 220|HOLD_SEMANTIC:CLAUDE_REVIEW_REQUIRED|HOLD_POINTER:unresolved_owner_or_interior_reference; HOLD_WIDTH:existing_fa_source_envelope_gate_retained; HOLD_RENDERER:font_variants_and_live_viewport_unproved; HOLD_WIDTH:conditional_normal_spacing1_exceeds_candidate_208|
|50|scr_1F3FE01|46 / 33|188 / 207|HOLD_POINTER:unresolved_owner_or_interior_reference|HOLD_RENDERER:font_variants_and_live_viewport_unproved|
|51|scr_1F3FE2F|116 / 68|170 / 187|HOLD_GLOSSARY_SCOPE:entry_scope_not_approved|HOLD_RENDERER:font_variants_and_live_viewport_unproved|
|52|scr_1F3FEA3|369 / 199|198 / 218|HOLD_GLOSSARY_SCOPE:entry_scope_not_approved|HOLD_POINTER:unresolved_owner_or_interior_reference; HOLD_RENDERER:font_variants_and_live_viewport_unproved; HOLD_WIDTH:conditional_normal_spacing1_exceeds_candidate_208|

## Runtime QAと次の作業

QA fixtureは23件。序章/初期候補→FA→Rift Caveのbuffer/#21→Shadow Baseの#31/#40/長文の順。
静的map/event条件は記載したが、具体的save flag・実到達ルートはUNKNOWN。今回mGBA実行なし。
まず基準ROMでwindow0/font/X/Y/spacingとfont selectorのRAM値を観測し、保存name writerを追う。
次に#1/#31/#40のwait境界と#19/#40/#49の本文をClaude再レビュー。scope/名称entityの承認を別途取得。
全gateが揃った時だけ別の承認済みintegrationとしてsafe subsetをcontrolfix/injectする。Batch02以降には進まない。

## 再現・最終回帰

`python scripts/build_ja_phase7_story_batch01.py --analyze` は監査のみ。`--write` は全pytest等のPASS後に
新規5成果物をexclusive-createする。既存出力があれば上書きせず停止。既存ROMを書く処理はない。

```json
{
  "pytest": {
    "state": "PASS",
    "returncode": 0,
    "command": [
      "-X",
      "utf8",
      "-m",
      "pytest",
      "-q"
    ],
    "passed": 638,
    "subtests_passed": 16
  },
  "py_compile": {
    "state": "PASS",
    "returncode": 0,
    "command": [
      "-X",
      "utf8",
      "-m",
      "py_compile",
      "scripts/build_ja_phase7_story_batch01.py",
      "tests/test_ja_phase7_story_batch01.py",
      "scripts/build_ja_phase6_cleanup_batch03.py",
      "tests/test_ja_phase6_cleanup_batch03.py",
      "tests/test_ja_phase6_cleanup_batch04.py"
    ]
  },
  "git_diff_check": {
    "state": "PASS",
    "returncode": 0,
    "command": [
      "diff",
      "--check"
    ]
  }
}
```

作成: このreport、holds/validation/binary audit JSON、runtime QA fixture、再現script、test。
変更: Batch03 allowlist管理scriptとBatch03/04対応testのみ。glossary/既訳/injector/controlfix/font/renderer/FA validator不変。
docs-sync skillの方針に従い詳細は本専用reportへ集約し、README/AGENTSは変更していない。
