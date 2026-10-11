# Phase 7C-4: Renderer / Consumer / Layout Investigation

解析のみ。ROM生成・注入・翻訳変更・既存validator変更・commit/pushなし。mGBA未実施、runtime PASSなし。

## 結果

```json
{
  "entries": 53,
  "duplicates": 0,
  "missing": 0,
  "consumer_confidence": {
    "CONDITIONAL": 53
  },
  "primary_classification": {
    "A": 0,
    "B": 15,
    "C": 38,
    "D": 0
  },
  "proven_live_fit": 0,
  "static_rescue_approved": 0,
  "runtime_trace_for_renderer_needed": 53,
  "renderer_only_primary_runtime_candidates": 15,
  "max_advance_by_conditional_font": {
    "2": 220,
    "4": 220,
    "5": 220
  },
  "max_copy_right_by_conditional_font": {
    "2": 219,
    "4": 219,
    "5": 219
  },
  "candidate_208_cursor_exceedance_indices": [
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
  "candidate_208_exceedance_indices": [
    0,
    6,
    7,
    12,
    15,
    19,
    20,
    22,
    24,
    28,
    32,
    34,
    39,
    41,
    45,
    49,
    52
  ],
  "conditional_vertical_exceedance_indices": [],
  "name_buffer_entries": 10,
  "FA_entries": 21,
  "FA_segments": 180,
  "FA_controls": 39,
  "semantic_hold_indices_unchanged": [
    1,
    31,
    40
  ],
  "meaning_review_indices_unchanged": [
    19,
    40,
    49
  ],
  "glossary_scope_entries_unchanged": 14,
  "official_entity_holds_unchanged": [
    19,
    32
  ],
  "relocation_candidate_not_allocated": [
    21
  ],
  "applied_total_unchanged": 2403,
  "phase6_remaining_unchanged": 774,
  "rom_generated": false,
  "runtime_executed": false,
  "translation_changes": 0,
  "glossary_changes": 0,
  "renderer_changes": 0,
  "validator_changes": 0
}
```

53件の局所operandは同じcallstd6/message経路。共通dispatch1系統、条件付きfont profile3、live証明済みprofile0。
PROVENな局所部品と、未証明の実際の呼出状態・viewportを分離。Aも注入承認ではない。

## ROM根拠

|処理|ROM offset / GBA address|確認|
|---|---|---|
|std6|01E7D5DA / 09E7D5DA|8A / message67 / wait66 / close6D / release6C|
|8A table owner / handler|0015FBDC / 0815FBDC、01EC9DD0 / 09EC9DD0|task作成とnative待機。ここではInitWindowsしない|
|field window initializer|0006FB24 / 0806FB24、literal0006FB38 / 0806FB38|InitWindows08003B24へtemplate083A73BC|
|candidate window|003A73BC / 083A73BC|left2/top15、26x4 tiles、208x32px。live適用は未証明|
|message / expansion|00A093AC / 08A093AC、000694C8 / 080694C8、00008FCC / 08008FCC|FD再帰展開後、RAM02021D18でprinter作成|
|setup|000F6D5C / 080F6D5C、000F6CD0 / 080F6CD0|window0/x0/y1/letterSpacing1/lineSpacing1|
|selector|009C9EE0 / 089C9EE0|override RAM020370DA、object index03005074、record02036E38とstyleで条件分岐|
|font-info setter|000F79C8 / 080F79C8、00002C1C / 08002C1C|ROM0041F444をRAM03003D90へ。live pointer変更の排除は未証明|
|glyph dispatch / copy|00005B6C / 08005B6C、00003014 / 08003014|scratch font nibbleからglyph routine。live window幅でcopyをclip|
|cursor advance|00005C28 / 08005C28|Japaneseはglyph幅+letterSpacing。Latinはglyph幅のみ。末尾にも加算|
|FE / FA / FB|00005880 / 08005880、00005C98 / 08005C98、00005C6C / 08005C6C|FE Y+15、FA同Yで15px scroll、FB XYを初期値へ|
|language|00005B10 / 08005B10、00005B18 / 08005B18|FC15/16がprinter+21を切替。FE/FA/FBではresetしない|
|wait hook|00005634 / 08005634、00A0F1CC / 08A0F1CC|Unbound固有auto/input条件。必ず1キー待つとは限らない|

## font 2/4/5

|font|wrapper / glyph routine (ROM)|Japanese glyph / width (ROM)|Latin width (ROM)|normalとのJapanese差|
|---:|---|---|---|---|
|2|000053E8 / 000065B8|00207500 / 0020F500|00207300|なし|
|4|00005458 / 000067EC|00217818 / 0021F818|00217618|0x2F「ぁ」9→10px|
|5|00005490 / 00006958|00227B30 / 0022FB30|00227930|0x86「ョ」9→8px|

表中GBA addressはROM offset+08000000。exact literal owners・width280 bytes・code生bytes/命令はprofiles JSON。
selector result0=font4、1=font5、その他=font2。font4/5をカテゴリや話者だけから選ばない。
3種類とも日本語glyph高12、Latin高14。font record max-height14なのでFE/FAは14+lineSpacing1=15。
日本語space00はtable byte0でなく特殊処理で10px、spacing込み11px。Latin space6px、追加spacingなし。
最終Japanese glyph後の+1はcursor advanceに含む。copy footprintの右端と最終cursorは区別する。
右端は自動FE/FAしない。copyのclipは欠損救済ではない。printer Xはu8なので256以上のadvanceはwrapの別リスク。

## viewport / 共通profileの条件

ROM00003014はlive window record+3のtile幅×8からcurrentXを引き、glyph copy幅を制限する。
同helper内に追加padding減算なし。ただしwindowの直前初期化・上書き・portrait等の予約領域は未証明。
26x4 templateを見つけても全53件へ208pxを適用しない。全entryの実usable-widthとlive最大幅はnull。
8Aはwindow初期化ではなくtask/native待機だった。window0がいつどのtemplateで作成されたかはroot別traceが必要。
spacing1・font2/4/5・font-info ROM0041F444・window0が確認された時だけ条件付き計測を利用可能。
FC06/FC14/未モデル位置・icon/F9・未知buffer・別window/font pointer/rendererは除外。

## 幅再計測

既存normal/spacing0最大200pxと、今回の各font/spacing1 cursor・copy右端をinventoryに分離。
FD01を0幅で合格にせず、unknown dynamicがあればconditional_max_total=null。静的部分の幅だけを表示。
208x32での超過は条件付き診断であり、実consumerのoverflow確定ではない。全entryのFE/FA/FB Y/page traceを保存。
cursor>208は21件、copy-footprint>208は17件。#1/#13/#36/#40はcursor209/copy208。末尾spacingだけの超過をglyph欠損と同一視しないが、UNKNOWN viewportを理由にhold維持。
旧English envelope gateはそのまま。今回の再計測で閾値を緩和しない。

## 名前buffer10件

FD01 owner ROM00231E74/GBA08231E74、producer ROM00009120/GBA08009120は*RAM0300500Cを返す。
ROM00008FCCで子FFを除く再帰copy。FDをrendererで展開しているわけではなく、embedded FC/FE/FAもcopyされる。
naming ROM0009D954/GBA0809D954のincoming r1はstate+1E30へROM0009D9A6で保存。
commit ROM0009F7EC/GBA0809F7EC、copy call ROM0009F830/GBA0809F830はstate+1800から保存destへtemplate長+1をcopy。
local player template7文字なので8 bytes。keyboardはROM003E22D0/GBA083E22D0、参照ROM0009F664。
このkeyboardの通常Latin値だけなら3fontsとも最大6×7=42px。入力→任意保存名の全経路証明ではない。
任意ordinary Latin7文字の84pxも長さ・ordinary-only条件の仮定付き。普遍上限ではない。
既定名候補・外部save・別writer・実NEW GAME destとFD producerの一致はUNKNOWN。10件全hold維持。
外側[latin][player][japanese]は通常local名のpageを維持。embedded FC等はfont/位置/制御parserにも影響し、万能安全ではない。

## FA / 別blocker

FA21件/180segments/39controlsは不変。#1/#31/#40 semantic hold、#19/#40/#49 meaning reviewは維持。
#31/#40「はめつのひかり」の完成形が1wait早い問題はrenderer証明で解消しない。
#19/#32公式entity、glossary scope14件、raw/interior owner候補、#21 slot19/encoded23のrelocation承認も変更しない。
A=renderer/layout証明済み、B=renderer traceが主、C=独立した別gateが主、D=consumerをたどれない。primary排他的、secondary別記。

## mGBA: ROM変更なしの観測手順

1. 基準ROM hashを確認。saveをrepo外へ退避し、使い捨てcopyで観測。battery autosaveは本番saveに向けない。
2. QA JSONのroot/map/条件とoperandを使う。到達手順はUNKNOWNで、map名や変数値だけで進行イベントを断定しない。
3. Frozen Heightsの#2/#3/#4 time-cardから候補。次に#0/#1、Rift Cave #19/#21、Shadow Base #31/#40/#49。進行済みsaveが必要なら用意。
4. debuggerでsetup080F6D5C/selector089C9EE0を止め、override/object/style、font-info pointer、window0 recordを読む。
5. 080F6D44でtemplate、08005790/08003014でprinter fields/currentCharを読む。native240x160のfirst/last glyphを記録。
6. FE前後、FA待機/scroll後、FB clear前後にX/Y/language/stateと15px移動を比較。auto条件も別記。
7. 名前付き10件では08009120/08008FCCの入力/展開結果、0809D954/0809F830のdest/長さを観測。RAM/saveを編集しない。
8. 53件は未注入で英語のまま。ここで証明できるのはgeometry。既存2403件の日本語を測る場合も同じlive consumerとの照合が必要。
9. 全条件・全分岐が記録できない場合はCONDITIONAL/UNKNOWN維持。未実施をruntime PASSにしない。

## 再利用・検証

Batch02〜16はprofileの適用条件、除外条件、pointer/script境界、live値とwindow、FD契約をentry別に照合。自動承認しない。
今回の打切り点: live window/style状態と全name値域は静的局所解析だけでは確定不能。次は上記traceを採取し、同じ仮説を再走査しない。
新規6完全一致パスのみallowlist追加。既存全function AST、909件/期待aggregate、未許可ファイル検出を維持。
新規出力はexclusive作成。既存出力が1件でもあれば全writer開始前に拒否。--check-existingは再生成bytes照合だけ。
`python scripts/investigate_ja_phase7_renderer.py --check-existing`
`python -m pytest`、変更Pythonの`py_compile`、`git diff --check`。最終実行結果は作業完了報告。

## 全53件

|index|ID|confidence|A/B/C/D|font2/4/5 static advance px|secondaryの要点|
|---:|---|---|---|---|---|
|0|scr_1F113ED|CONDITIONAL|C|220/220/220|HOLD_POINTER:unresolved_owner_or_interior_reference|
|1|scr_1F11594|CONDITIONAL|C|209/209/209|HOLD_SEMANTIC:FA_SEMANTIC_BOUNDARY_REVIEW_REQUIRED|
|2|scr_1F1184B|CONDITIONAL|B|149/149/149|Live renderer/window observation required|
|3|scr_1F11864|CONDITIONAL|B|138/138/138|Live renderer/window observation required|
|4|scr_1F11CFD|CONDITIONAL|B|132/132/132|Live renderer/window observation required|
|5|scr_1F2F718|CONDITIONAL|C|127/127/127|HOLD_POINTER:unresolved_owner_or_interior_reference|
|6|scr_1F2E8E9|CONDITIONAL|C|214/214/214|HOLD_POINTER:unresolved_owner_or_interior_reference|
|7|scr_1F2EB85|CONDITIONAL|C|217/217/217|HOLD_POINTER:unresolved_owner_or_interior_reference|
|8|scr_1F2EC73|CONDITIONAL|B|187/187/187|Live renderer/window observation required|
|9|scr_1F2F468|CONDITIONAL|C|195/195/194|HOLD_GLOSSARY_SCOPE:entry_scope_not_approved|
|10|scr_1F2F493|CONDITIONAL|B|132/132/132|Live renderer/window observation required|
|11|scr_1F2F4A4|CONDITIONAL|B|196/196/196|Live renderer/window observation required|
|12|scr_1F2F4C3|CONDITIONAL|C|220/220/220|HOLD_POINTER:unresolved_owner_or_interior_reference|
|13|scr_1F2F55D|CONDITIONAL|B|209/209/209|Live renderer/window observation required|
|14|scr_1F2F5BE|CONDITIONAL|B|110/110/110|Live renderer/window observation required|
|15|scr_1F2F5EA|CONDITIONAL|C|220/220/220|HOLD_POINTER:unresolved_owner_or_interior_reference|
|16|scr_1F2F69E|CONDITIONAL|C|187/187/187|HOLD_POINTER:unresolved_owner_or_interior_reference|
|17|scr_1FA54AC|CONDITIONAL|B|187/187/187|Live renderer/window observation required|
|18|scr_1F460D1|CONDITIONAL|B|114/114/114|Live renderer/window observation required|
|19|scr_1F460E7|CONDITIONAL|C|220/220/220|HOLD_SEMANTIC:CLAUDE_REVIEW_REQUIRED|
|20|scr_1F46179|CONDITIONAL|C|220/220/220|HOLD_BUFFER:writer_values_page_and_live_width_unproved|
|21|scr_1F46217|CONDITIONAL|B|194/194/194|Live renderer/window observation required|
|22|scr_1F4622A|CONDITIONAL|C|218/218/218|HOLD_BUFFER:writer_values_page_and_live_width_unproved|
|23|scr_1F751D8|CONDITIONAL|B|165/165/165|Live renderer/window observation required|
|24|scr_1F3EA65|CONDITIONAL|C|220/220/220|HOLD_GLOSSARY_SCOPE:entry_scope_not_approved|
|25|scr_1F3EB13|CONDITIONAL|C|185/185/185|HOLD_POINTER:unresolved_owner_or_interior_reference|
|26|scr_1F3EBBA|CONDITIONAL|C|160/160/160|HOLD_BUFFER:writer_values_page_and_live_width_unproved|
|27|scr_1F3EBEB|CONDITIONAL|C|199/199/199|HOLD_POINTER:unresolved_owner_or_interior_reference|
|28|scr_1F3EC74|CONDITIONAL|C|220/220/220|HOLD_BUFFER:writer_values_page_and_live_width_unproved|
|29|scr_1F3EDA8|CONDITIONAL|C|194/194/194|HOLD_BUFFER:writer_values_page_and_live_width_unproved|
|30|scr_1F3EE0A|CONDITIONAL|C|198/198/198|HOLD_BUFFER:writer_values_page_and_live_width_unproved|
|31|scr_1F3EED6|CONDITIONAL|C|208/208/208|HOLD_SEMANTIC:FA_SEMANTIC_BOUNDARY_REVIEW_REQUIRED|
|32|scr_1F3EF60|CONDITIONAL|C|220/220/220|HOLD_OFFICIAL_NAME:entity_or_project_name_approval_missing|
|33|scr_1F3F216|CONDITIONAL|C|175/175/175|HOLD_GLOSSARY_SCOPE:entry_scope_not_approved|
|34|scr_1F3F277|CONDITIONAL|C|220/220/220|HOLD_GLOSSARY_SCOPE:entry_scope_not_approved|
|35|scr_1F3F3C9|CONDITIONAL|C|198/198/198|HOLD_BUFFER:writer_values_page_and_live_width_unproved|
|36|scr_1F3F514|CONDITIONAL|C|209/209/209|HOLD_BUFFER:writer_values_page_and_live_width_unproved|
|37|scr_1F3F64A|CONDITIONAL|C|208/208/208|HOLD_GLOSSARY_SCOPE:entry_scope_not_approved|
|38|scr_1F3F6F5|CONDITIONAL|C|164/164/164|HOLD_BUFFER:writer_values_page_and_live_width_unproved|
|39|scr_1F3F771|CONDITIONAL|C|220/220/220|HOLD_POINTER:unresolved_owner_or_interior_reference|
|40|scr_1F3F846|CONDITIONAL|C|209/209/209|HOLD_SEMANTIC:CLAUDE_REVIEW_REQUIRED|
|41|scr_1F3F9C8|CONDITIONAL|C|219/219/219|HOLD_GLOSSARY_SCOPE:entry_scope_not_approved|
|42|scr_1F3FA54|CONDITIONAL|B|185/185/185|Live renderer/window observation required|
|43|scr_1F3FAB5|CONDITIONAL|C|183/183/183|HOLD_POINTER:unresolved_owner_or_interior_reference|
|44|scr_1F3FB1C|CONDITIONAL|C|108/108/108|HOLD_POINTER:unresolved_owner_or_interior_reference|
|45|scr_1F3FB5E|CONDITIONAL|B|219/219/219|Live renderer/window observation required|
|46|scr_1F3FBAF|CONDITIONAL|C|154/154/154|HOLD_POINTER:unresolved_owner_or_interior_reference|
|47|scr_1F3FBE4|CONDITIONAL|C|196/196/196|HOLD_POINTER:unresolved_owner_or_interior_reference|
|48|scr_1F3FC2A|CONDITIONAL|B|208/208/208|Live renderer/window observation required|
|49|scr_1F3FC84|CONDITIONAL|C|220/220/220|HOLD_SEMANTIC:CLAUDE_REVIEW_REQUIRED|
|50|scr_1F3FE01|CONDITIONAL|C|207/207/207|HOLD_POINTER:unresolved_owner_or_interior_reference|
|51|scr_1F3FE2F|CONDITIONAL|C|187/187/187|HOLD_GLOSSARY_SCOPE:entry_scope_not_approved|
|52|scr_1F3FEA3|CONDITIONAL|C|218/218/218|HOLD_GLOSSARY_SCOPE:entry_scope_not_approved|
