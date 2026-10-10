# Phase 6C-4F — FA Bottleneck Investigation

調査・改善案のみ。ROM生成、翻訳/用語/codec/controlfix/injector/rendererの変更、Claude実行なし。
適用総数 **2357**、全Phase残保留 **820** を維持。新規適用・新規安全確定 **0**。
新規出力の存在を作成前に確認し、同名既存ファイルなし。既存成果物は上書きしない。

## 1. Accounting / 判定

|母集団|FA全件|適用済み|FA保留|完成訳の保留|文脈保留|
|---|---:|---:|---:|---:|---:|
|Cleanup Batch 01|4|0|4|3|1|
|Cleanup Batch 02|55|2|53|36|17|
|合計|59|2|57|39|18|

Batch02完成FA訳38件=既存適用2+保留36。unique IDで重複0、欠落0。
reviewed / technical_holds / Claude reviewのID集合、原文と実ROM PCS、元slotと全記録ownerを照合。
全保留57件のslot・記録pointer bytesは原ROMと基準ROMで一致。

|分類|Batch01|Batch02完成36|Batch02文脈17|合計|
|---|---:|---:|---:|---:|
|A STATIC_SAFE_CANDIDATE|0|6|0|6|
|B CLAUDE_RESEGMENT_REQUIRED|0|24|0|24|
|C RUNTIME_VERIFICATION_REQUIRED|3|2|0|5|
|D BLOCKED_BY_CONTEXT|1|4|17|22|

分類は「次に何を証明するか」であり承認ではない。Aも現行English-width-envelope gateに落ちている。
現行基準のまま新規適用可能なものは0。Bは再レビューが必要という意味で、必ず訳文を書き換えるという意味ではない。
CはmGBAだけで解決しないowner/writer証明も含む。Dの追加4件はunknown buffer17件ではなく、名称/地名scope未証明の完成訳。
`Crobatman / Super Cube / Redwood Village / Gurun Town・Route 18` のIDはJSONに分離。

Batch02既存hold理由のmembership（重複あり）:
English envelope26、semantic注記18、buffer contract21（context17+player4）、raw owner/interior12、
208px超過10、glossary6、official/project name5、special control未モデル5、dynamic幅/page4、voice1。
この合計は53ではない。primary/secondaryのunique accountingとは区別。

今回の全57件primary cause:
UNKNOWN_BUFFER18、LINE_WIDTH_OVERFLOW10、SEMANTIC_BOUNDARY_AMBIGUITY15、FA_LAYOUT_UNVERIFIED5、
DYNAMIC_WIDTH_UNVERIFIED3、OFFICIAL_NAME_UNVERIFIED4、POINTER_OWNER_INCOMPLETE1、OTHER1。
secondary込みではFA_LAYOUT_UNVERIFIED57、DYNAMIC_WIDTH_UNVERIFIED25、SEMANTIC_BOUNDARY_AMBIGUITY21、
POINTER_OWNER_INCOMPLETE13、GLOSSARY_UNRESOLVED6、TRANSLATION_SEGMENT_INCOMPLETE18等。
CONTROL_BOUNDARY_MISMATCHは0。意味注記をbyte/control不一致と取り違えない。
FA_LAYOUT_UNVERIFIEDの全件membershipは共通未完証明であり、57件すべてが同じ根本原因という意味ではない。

全entryの英日原文、境界、raw bytes、offset/GBA、slot、owner、幅、buffer、旧判定、primary/secondary、
runtime根拠、次の作業は `out/phase6/ja_phase6_fa_bottleneck_inventory.json` に保存。
再現する新規専用scriptは `scripts/audit_ja_phase6_fa_bottleneck.py:281`。既存buildのmainは呼ばない。

## 2. Unbound ROMによるFA printer照合

既存docsのdispatchだけでなく、状態本体とフック先をThumb逆アセンブル。
下記blockの生byte列・命令をinventoryのprinter_evidenceに保存。原ROMと基準ROMで全block同一。
GBAアドレスはROM offset+0x08000000。upstreamと同一と決めつけていない。

|処理|ROM offset / GBA address|実バイト・命令からの確認|
|---|---|---|
|RenderText / state dispatch|00005790 / 08005790、table000057B0 / 080057B0|printer+1Cのstateで0～6分岐|
|文字読み取り|00005840 / 08005840|currentCharから1 byte取得、pointerを先に+1|
|F8～FF dispatch|00005848 / 08005848、table00005860 / 08005860|FA→08005B26、FB→08005B22、FE→08005880|
|FA/FB state store|00005B22 / 08005B22|`02 20 00 E0 03 20 30 77`。FB=2、FA=3をprinter+1Cに保存|
|FA待機開始state3|00005C98 / 08005C98|08005634のwait成功後080055D4で矢印領域を消去。font recordの+5とlineSpacing(printer+B)を加算しscrollDistance(+1F)へ。currentX(+8)=initialX(+6)、state4|
|scroll state4|00005CD0 / 08005CD0～00005D42 / 08005D42|speed table ROM001EA650 / GBA081EA650で移動量を分割。080044A8(window scroll)をdirection0で呼び、背景色で空いた領域を埋める。08003F20でVRAM転送。distance0でstate0|
|scroll helper|000044A8 / 080044A8|window tile幅/高さとpixel bufferを読み、移動後の領域をcopy/fill。全variantの実機動作は未実施|
|FE|00005880 / 08005880|X初期値へ、Y(+9)にfont max-height+lineSpacingを加算、REPEAT。待機なし|
|FB state2|00005C6C / 08005C6C|wait後0800445Cでpixel fill、X/Y両方初期値へ、state0|
|Japanese/Latin|FC table000058CC / 080058CC、00005B10 / 08005B10、00005B18 / 08005B18|FC15/16でprinter+21に1/0。FA/FB/FE状態処理はこのflagをリセットしない|
|glyph選択・描画|00005BAA / 08005BAA、00005BEE / 08005BEE|font別decompressにJapanese flagを渡し、08003014でwindowへcopy|
|glyph advance|00005C28 / 08005C28～00005C4E / 08005C4E|通常glyph幅をXへ加算。JapaneseではletterSpacing(+A)も加算。確認したRenderText経路に右端判定→自動FE/FAなし|
|FD|000058A8 / 080058A8→00005B0A / 08005B0A|printerはFD引数をskipするだけ。ここでbuffer内容を展開していない|

FAは入力後、windowを「font最大高さ+lineSpacing」の1行分スクロールし、printer Yは変更しない。
次segmentは初期X・同じprinter Yで始まる。見えている上行は失われ、下行が上へ移る。
色設定もFAだけでは初期化されない。scroll/FBの背景塗りは現在の背景色を使用する。
ただしlive font・lineSpacing・2行viewportはcallerごとに確認が必要。
glyph copy helperまで全条件の描画を証明したわけではなく、自動wrapを救済根拠には使わない。

### 重要: waitはUnbound固有hook

ROM00005634 / GBA08005634は `00 49 08 47` のldr/bx。
literal ROM00005638の `CD F1 A0 08` → Thumb entry **ROM00A0F1CC / GBA08A0F1CC**。
これはvanilla関数の残り命令をそのまま使う経路ではない。
実hookはtext flags RAM03003E50を調べ、auto時08005608、通常時080054F8(矢印)を呼ぶ。
RAM030030F0の+2Eの下位2bitが非zeroなら成功。+2Cのbit8が立つ時は追加条件080ではなく
GBA08A0F190を呼ぶ。後者はflag IDs 16E4/16DB/082Cをhelper0806E6D0経由で確認。
auto wait counterの50/120閾値もROM00005608 / GBA08005608に存在。
flag名・全option/held-inputの意味と実時間は未証明なので、A/Bで必ず1回待機するとは断定しない。

比較用の一次資料は [pret text.c](https://github.com/pret/pokefirered/blob/master/src/text.c) と
[text.h](https://github.com/pret/pokefirered/blob/master/include/text.h)。構造体field名と状態名の照合用。
この報告のstate-body確認は上記ローカルROMの命令が根拠であり、pret-only VERIFIEDではない。

## 3. Renderer / widthの限界

- field candidate: ROM003A73BC / GBA083A73BC、`00 02 0F 1A 04 0F 98 01`、26×4 tiles=208px。
  ROM0006FB22 / GBA0806FB22のldr literal owner ROM0006FB38 / GBA0806FB38→083A73BC、08003B24 InitWindowsを照合。
  `scripts/build_ja_phase6_cleanup_batch02.py:226` のloadword/callstd/message patternはfield候補の根拠だが、
  各entryの実行経路、live window/initial X/右余白/font/spacingは未完。**208を全entryのusable幅にしない**。
- battle profile: ROM00248330 / GBA08248330=28×4 tiles。printer ROM003FEB64 / GBA083FEB64はx2/font2。
  224-2=222pxはこのtemplate/printerのspan。Batch01 battleテーブル候補と対応するが、各writer/variantは別途確認。
  inventoryのBatch01 `proved_entry_usable_width=222` は既存battle profileの数値を保存したもの。
  `entry_live_path_proved=false`であり、特定の未実行entryへの全経路証明ではない。
- normal Latin幅: ROM001FB100 / GBA081FB100、Japanese幅: ROM0020F500 / GBA0820F500、0x118 bytes。
  `lib/gen3_font.py:30` と実ROMの一致を再確認。Japanese space byte00は10px、ASCII-space aliasはdecodeで全角spaceへ正規化。
- `lib/renderer_profiles.py:248` はnormal glyph加算でletterSpacing0を仮定。
  ROM描画にはJapanese letterSpacing加算があるため、live spacing≠0なら幅過小評価。
  特殊FC位置指定は `lib/renderer_profiles.py:298` のtraceと合わせて評価し、未モデルfont/icon/dynamicを無視しない。
- 仮buffer54pxは上限ではない。player local keyboardの7文字/42px証明も、外部save・default・embedded FC・expansion全値の証明ではない。
- 209～210pxの静的行10件（inventoryに全行幅）は現行field candidateを超える**blocking overflow**のまま。
  Claudeへの調整候補Bとし、runtime warningに格下げしない。異なる実rendererを証明しない限り適用不可。
- English-source最大幅はROM描画の容量チェックではない。たとえばscr_1F079B1は日本語200px。
  元英語がより短いことだけでは実際のoverflowを意味しないが、initial Xや余白を未確認のまま解除もしない。

## 4. Validatorの誤検知 / 見逃し

`lib/fa_control.py:66` はsegment数/構造/空欄/新規layout tokenを検査する。
**英語と日本語の同じ単語が同segmentにあることを一般アルゴリズムで要求してはいない**。
`scripts/build_ja_phase6_cleanup_batch02.py:53,200` の手動BOUNDARY_NOTESが語句移動をholdにし、
`:244,255` が英語最大幅を追加上限としている。これが主な保留圧力。

過剰に厳しい可能性:

1. FEは入力待ちやpage clearではない。2行の同じ表示view内で固有名や述語を組み替える日本語を、
   一律「意味境界違反」にしない。#44/#63とscr_1F130DCのCutなど。
2. 英語で「two on / two」のようにFA跨ぎで分割された単語/名詞を、日本語で前行にまとめただけで危険とはいえない。
3. trophyの修飾節→名詞は自然な日本語。ただし入力待ち前のreveal内容が変わるので、明示的checkpointレビューは必要。
4. 全ROMのraw4byte interior hitは構造的pointer証明ではない。graphics等の偶然一致を「owner不足確定」と呼ばない。
   ただし未分類のまま承認しない。relocation時だけでなくin-placeで参照先途中の表示が変わる可能性も調べる。

見逃し/テスト不足:

1. 注記のないIDをsemantic PASSとするのは全件意味一致の証明ではない。
   scr_1F078CBは英語defeatingがFA前、日本語たおしたはFA後なのに既存semantic PASS。
   今回Bに送り、良い日本語語順ならcheckpoint差を承認できる設計にする。危険と即断して書き直さない。
2. `lib/fa_control.py:24` は各raw pieceを初期Latinでdecodeする。
   `[japanese]あ\nい\lう[latin]` = `FC15 01 FE 02 FA 03 FC16 FF` をsplitすると、
   後続pieceは `Á`、`Â[latin]` になることを再現。元英語のsegment抽出は問題なし。
   日本語本文の意味/glyph検証にはpageを継承するparserが必要。今回既存parserは変更しない。
3. `scripts/build_ja_phase6_cleanup_batch01.py:236` のsegment_checkはpage付与前の日本語をencodeするため、
   Latin未知kanaが黙って落ちる。既存auditに空target segmentがある。**control/token検査に限ったPASS**であり本文保存証明ではない。
   今回は全文page-aware encode→decode→再encodeのbyte roundtripを完成訳に実施。space alias差は許容、byte差は許容しない。
4. `004_controlfix_translations.py:1198` のlegacy idempotency pathはrequire_segments指定なしでsegmented gateを回避し得る。
   古い承認済みデータ保存と新しい未検証draftの区別をID/provenanceでテストする案。
   `:1222` のfa_layout_reviewed boolean自体はlive幾何/意味proofを持たない。
5. `005_hybrid_injector.py:143` のencodeとtransaction/pointer監査はsemantic timingを検証しない。
   strict dry-run成功だけでFA approvalにしない。

提案する安全契約（今回は実装なし）:

- byte-level FE/FA/FB順序・数・FC/FD意味tokenとsource ownershipは独立必須gate。
- FE単位の「単語一致」ではなく、同じvisible viewとFA入力待ち直前/直後の意味checkpointをレビュー。
- FAの1行scrollで失われる情報、残る下行、否定/条件/主語/効果/選択肢のrevealを明示。
  完全文をFAごとに要求しない。自然な連体修飾の継続を認めるが、否定の反転や別pageへの参照消失は止める。
- FBは前のview全体を消すので、依存する語句を別pageへ勝手に移さない。
- 色・wait・sound・position等FCのscopeを維持。dynamic tokenはwriter/type/全値/page/boundが証明されるまで移動許可しない。
- English envelopeを実callerのusable-widthに置き換える案。font/letterSpacing/min-spacing/icon/shiftを含む右端traceと垂直traceを併用。
- proofを構造/意味/幅/owner/runtimeに分け、reviewerが未確認をfalseでなくUNKNOWNとして残す。
  共通bool一つで全proofを代用しない。

必要な次工程regression:
Japanese pageがFE/FA/FBをまたぐraw parser、FC引数FA誤検知、FC15/16保持、Japanese字間0/1、
FE内自然な再配置許可とFA否定reveal保留、同FA数だが位置意味異なるnegative、FB跨ぎ照応、
3回以上scroll、FC font/shift/min-spacing、FD埋込みFC/FE/FA/FB、全buffer writer variant、
legacy bypass、未知glyph、owner追加/偶然hit、controlfix idempotency、full byte roundtrip。

## 5. 特別6件（Batch02 zero-based index照合済み）

すべてraw/FC/FD/boundary構造の既存control auditはPASS。以下は本文や意味の評価でありcodec変更なし。
English/Japaneseの**全**segment表と境界offsetはinventory、B24件の同じ表はClaude handoffへ。

|index / ID|FE / FA / FB|日本語各行幅px|判定・根拠|
|---|---|---|---|
|44 scr_1F09154|3 / 1 / 2|140,79,100,130,159,209,140|B。Science Society/clonedはFE内移動、copy結論はFA後を維持。209pxと用語scopeは実ブロッカー|
|63 scr_1F0A436|3 / 2 / 2|170,140,100,100,180,160,208,140|B。Paradise/Honey GatherはFE regroup。とくせいが / みつあつめも の日本語文法再レビュー。208pxは余白次第|
|137 scr_1F1330A|4 / 2 / 3|170,140,168,149,160,180,90,169,160,90|B。endangered/growing back、義務/対価の語順と待ち位置。物理超過ではない|
|81 scr_1F0C34F|1 / 1 / 0|189,169,114|B。Single BattleがFA前へ、trophy名詞がFA後へ。自然な修飾節だがreveal review。raw interior未分類|
|82 scr_1F0C3AF|1 / 1 / 0|189,159,114|B。同上Double、raw interior未分類|
|83 scr_1F0C40F|1 / 1 / 0|189,159,114|B。同上Multi、追加interior signalなし|

重要な区間比較（→は制御。省略部分はinventory参照）:

44:
English: `We cloned it at the Science` →FE `Society, so the version you have` →FA `is nothing more than a copy.`
Japanese: `わたしたちは かがくきょうかいで` →FE `クローンに した。 だから その ミュウは` →FA `ただの コピーに すぎない。`
クローン説明のFE位置は変わるが同じpre-FA view。語句同segment必須では無用なholdになり得る。

63:
English: `Combee can be found all over Flower` →FE `Paradise, however they are more` →FA
`likely to appear in the [blue]blue[red]` →FA `flowers.` →FB
Japanese: `ミツハニーは フラワーパラダイスの` →FE `どこにでも いますが、 より` →FA
`でやすいのは [blue]あおい[red]` →FA `はなの ところです。` →FB
後半Honey Gatherは英語FEで固有名が割れていたものを日本語行にまとめる。
protected green/redは同segmentのままだが、`とくせいが / みつあつめも` は述語を再確認する。

137:
English: `Apparently the tall grass around` →FE `here is endangered, despite always` →FA `growing back.` →FB
Japanese: `どうやら ここの たかい くさは` →FE `いつも はえて くるのに ぜつめつの` →FA `きき だそうです。` →FB
English: `However, I am still contractually` →FE `obligated to pay you for your` →FA `service.`
Japanese: `とはいえ、 けいやく じょう まだ` →FE `しごとの たいかを おはらいする` →FA `ぎむが あります。`
対価→義務という日本語修飾関係自体は自然。待機前に判明する義務と冗談の落ちの違いをreviewする。

81/82/83:
English: `It’s a trophy proving you defeated` →FE `the Battle Tower Frontier Brain in` →FA
`a standard Single/Double/Multi Battle!`
Japanese共通: `バトルタワーの フロンティアブレーンに` →FE
`ふつうの シングル/ダブル/マルチバトルで かった` →FA `あかしの トロフィーだ！`
修飾節→あかしのトロフィーは自然。battle形式は入力前、trophy結論は入力後へ移る。
全文意味は保持されるが、sourceと同じ情報開示ではない。許容reviewなしで自動解除しない。

## 6. 17 context FA holds

|ID|未確定token（繰返し/複数membershipはunique件数と別）|
|---|---|
|scr_1F012BD|buffer2×2|
|scr_1F01914|buffer2, raw FD07, buffer3, raw FD08|
|scr_1F0729E|buffer1|
|scr_1F080EE|buffer2, FD07, buffer3, FD08|
|scr_1F083F2|buffer1|
|scr_1F08691|buffer1|
|scr_1F08849|buffer2, buffer3|
|scr_1F08AC4|buffer1|
|scr_1F08C72|buffer2, FD07, buffer3, FD08|
|scr_1F08E36|buffer1|
|scr_1F08F28|buffer1|
|scr_1F0935A|buffer1|
|scr_1F0994C|raw FD0C|
|scr_1F0B7A3|buffer1, buffer2, buffer3|
|scr_1F0B9B3|buffer1, buffer2, buffer3|
|scr_1F121E3|buffer1|
|scr_1F12282|buffer3|

意味型/書込側/全値/接尾辞/助数詞/page/上限が未証明。Claudeは完成segmentsを出していない。
previous_candidateを承認済み訳として使わない。各ownerの直前bufferstring→message/loadpointerを
`scripts/audit_ja_phase6_batch02_controls.py:101` の既存厳密隣接パターンで再確認、17件すべて直接literal writerなし。
これは上流special・分岐経由writerが存在しない証明ではなく、追加CFG解析が必要という結果。
raw FD07/08/0Cを単なる英語pluralと確定しない。
Batch01のcontext1件は `tbl_battle_messages_00216_3FCA49`、FD00含むcaller-dependent値。
完成battle3件もFD0F/10/18/19/14等のhigh-bank helper/writer/full-values未証明でC。
ROM000D7868 / GBA080D7868→089BD050のbattle expansionとROM009BD0BA / GBA089BD0BAのFD dispatchは
既存Batch01監査が部分追跡済みだが、低位RenderText FD skipだけで互換性を証明できない。

## 7. mGBA最小QA / 次工程

新fixture `tests/fixtures/ja_phase6_fa_runtime_qa_plan.json` に8ケース。**操作未実施**。
map/eventの到達が未証明なので全ケースUNKNOWN。物語文から地図・一本道の到達手順を創作しない。
既存ownerとevent metadataを使ってsave/runtime traceで到達を特定してから、以下の順で確認する。

1. 適用済み `scr_1F0D935`：FE→FA、180px。元ROM offset01F0D935 / GBA09F0D935、owner01E6EA9C。
2. 適用済み `scr_1F126CE`：FB→FE→FA、190px。ROM01F126CE / GBA09F126CE、owner01E71731。
3. `scr_1F0BE99`：3回以上scroll、FE/FB/FA・button混在。現ROMでは英語。
4. `scr_1F0CAF5` player、`tbl_battle_messages_00122_3FC048` battle FD、`scr_1F0B7A3` unknown buffer。
   最長受理名・embedded FC・出力bytesの実測。現在は英語、JP候補には幅/意味gateが残る。
5. `scr_1F0C40F` trophy、`scr_1F1330A` predicate timing。現ROMでは英語。

native240×160でFA前、input待ち、scroll中、次行先頭/末尾、FB後を撮影。
printer currentChar/windowId/fontId/x/y/currentX/currentY/spacing/state/Japanese flagをlog。
NG: clipping/欠落/重描画、FAで全消去、wait増減、ページ/色崩れ、誤glyph、意味の先行reveal、未解決writer/owner。
通常入力→auto/held-inputを別runで比較。owner同定と全transition一致が必要。
**現ROMに保留訳は入っていない**。英語でrenderer traceを先に取り、JP確認用buildは別工程で承認後。
UNKNOWNを実機PASSや到達済みへ昇格させていない。

推奨順:

1. unchanged基準ROMで上記適用FA2件をtraceし、field usable-width、letterSpacing、scroll/wait条件を確定。
2. validator改善を別工程で実施：page-aware parser、checkpoint proof、source envelopeのprofile化、boolean/legacy gateのテスト。
3. B24件をClaude checkpoint/grammar/必要な幅調整へ。新handoffは既存訳をコピーした調査資料で、今回は送信/再翻訳なし。
4. C5件のlive buffer/ownerとD22件のcontext/名称scopeを別々に解消。
5. strict controlfix/dry-run/binary auditとfocused runtime後に進行判断。**Batch03翻訳を先にしない**。

救済見込み: 完成保留36件のうちA **6件**が未変更訳での優先候補。
`scr_1F079B1 / scr_1F0ABA6 / scr_1F0AD1C / scr_1F0CD3A / scr_1F130DC / scr_1F13412`。
さらにowner hit分類とlive marginが解決すれば `scr_1F09045 / scr_1F0CE14` の2件、計 **最大8件の条件付き短期候補**。
実際に安全確認済み0。B24やD4を同じ救済見込みに足さない。
語順・否定・物理超過・名称問題には独立承認が必要で、最終救済総数は現時点UNKNOWN。

## 8. 保護・検証・created files

新scriptは既存入力/ROM/glossary等 **901ファイル**の個別SHA256とaggregateを記録。
調査開始・出力後に同一:
`ea8f4deae2c3462b50816e33913f3a03a5186f9d723b510e6a84274306db5ab7`。
基準ROM SHA256:
`192b43b79f75174d9fd5618c47276d2a21cf47ec58b2a902becbe872b19a0284`。
glossary SHA256:
`d5fd815806dfc8ab4c584bb117df19a413f53e0c63ae28977d5722601523f296`。
input JSON・元ROM・全既存ROM・glossary・既存ソース/テスト不変。既存成果物の上書き0。

- `.venv/Scripts/python.exe -m pytest -q`: **483 passed, 16 subtests passed in 58.92s**。
- 新artifact作成後にも全pytest再実行: **483 passed, 16 subtests passed in 59.22s**。
- 新script `py_compile`: PASS。
- JSON parse / 57 unique IDs / missing0 / B02 53=36+17: PASS。
- `git diff --check`: PASS。tracked diff/statは空（新規untrackedはstatに出ない）。
- existing validatorの変更なし、追加テストの実装なし。必要なregressionは改善案として上に列挙。
- ROM build/dry-runなし。今回binary diffは発生させず、全既存ROM hash不変を検証。

新規5ファイル:

1. `docs/ja-phase6-fa-bottleneck-investigation.md`
2. `scripts/audit_ja_phase6_fa_bottleneck.py`
3. `out/phase6/ja_phase6_fa_bottleneck_inventory.json`（ignored）
4. `out/phase6/ja_phase6_fa_claude_resegment_handoff.json`（ignored）
5. `tests/fixtures/ja_phase6_fa_runtime_qa_plan.json`

git status: branch japanese-support、tracked変更0。開始時のuntracked17件を保持し、新規untracked3件のみ追加。
commit/pushなし。別Phaseのscriptは変更していない。
