# Phase 7C-5: mGBA Runtime Renderer Trace

実ROM実行・人間のSTART補助あり。解析のみ。ROM/訳文/セーブ/validator変更、注入承認、commit/pushなし。

## 結果と範囲

mGBA Qt 0.10.5 + localhost GDBでレジスタ・メモリを読み、hardware breakpointを使用。
SDL起動ではlistenerなし。GDB単体実行ファイル不要。独自RSP readerは書込みpacketを拒否。
制約は[mGBA 0.10.5実装](https://github.com/mgba-emu/mgba/blob/0.10.5/src/debugger/gdb-stub.c)に照合。
一時フォルダへbyte同一ROMをコピーし、既存saveのautoloadなし。基準ROM SHA-256は不変。
最初の停止は08008FCCの意図したbreak。後でbreak全解除・detachして再開。停止をgame freezeと誤認しない。

## 直接観測

NEW GAME注意画面: scr_1F0F5A6、ROM 01F0F5A6 / GBA 09F0F5A6。
08008FCCのr1=09F0F5A6、捕捉128byteと基準ROM一致。static owner 01E6F945の4byte=a6 f5 f0 09。
caller LR=09EB2FCD。owner命令が実行された証明とは別。原文Welcome to Pokémon Unbound!。
既適用日本語の注意文を画面で確認。途中からのpointer/類似文/アドレス近接でID一致判定しない。

CopyGlyph ROM00003014 / GBA08003014: r0=02020010のlive printer。
font template2/dispatch2、window0、initial/current X38/Y4、letterSpacing1/lineSpacing0、Japanese=true。
window RAM020204B4: left0/top2、28x18tiles =224x144px、画面origin0/16。
このsampleの開始Xから右境界まで186px。追加padding/予約領域とoverflowの実測はUNKNOWN。
glyph scratch03003DA0+80/+81=10/12px、copy右端exclusive48（最終pixel47）。
08005C4Eはstore直前、r0=49、r1=11。10px glyph+1px spacingを実測。
FE入口08005880でr3=FE、0800589EでY書込後r0=18、step r1=14。
field想定の15pxではない（font max-height14+lineSpacing0）。全行・末尾・clip/wrapの実測ではない。
source->stack expansion->printerは時系列整合。return時buffer全文を捕捉していないため完全な連結証明は未完。

別のfield setup観測: 080F6D5C r0=1はflagでありtext pointerではない。
selector ROM009C9EE0/GBA089C9EE0の実行、戻り080F6D7C r0=3、override020370DA=00FF。
RAMfont info03003D90=0841F444、window0は26x4tiles=208x32px（left16/top120）。
selector3→font2はstatic branch。printer作成時font/spacingは未捕捉。
context r5=03000EB0のdata2=09F0F79Cは以前の文の残存値。現在Choose a characterとの一致証明に使用しない。
このfield sampleはUNKNOWN_ENTRY。共通field経路を部分観測したが、完全なID/font/window連結は未証明。

## 保留を維持

Batch01全53件NOT_REACHED、consumer CONDITIONAL53、live-fit PROVEN0、注入承認0。
B15/C38、既適用2403、Phase6保留774は変更しない。font4/5、FA/FB、FD01展開はNOT_REACHED。
名前入力1例の42pxを全writer/外部saveの上限にしない。#1/#31/#40のFA意味境界はClaude再レビューへ。
対照sample224pxをfield53件へ転用しない。208候補超過も今回救済しない。

## 再現・次工程

repro fixtureの手順とhelperを使用。NEW GAMEのfield文についてexpander r1、selector戻り、F6D44 template、
CopyGlyph r0を同一接続で捕捉する。RenderText側はr6を使い、固定printer番地を仮定しない。
次に到達可能なFA1件とFD01 name1件を追跡。未注入Batch01日本語のruntime PASSは別工程。
全raw records/packet checksum/失敗試行はtrace JSONに保持。capture03切断、capture04待機中の手動中断も隠さない。
既存global mGBA設定はQt終了時更新され得るが、既存ROM/訳文/909保護対象とは別。既存saveを読み込まない。
新規4成果物をexclusive作成。再生成は別出力へ比較し、無断上書きしない。

## 検証

pytest・py_compile・git diff --checkの実行結果は最終報告参照。
helper testで書込packet拒否、exact pointer照合、観測欠落時UNKNOWN、全53件の未承認維持、
exact allowlist除去/許可外追加FAIL、保護909の期待hash不変を確認する。

## 後続クラッシュ（実行全体はPASSではない）

ユーザー報告後、GUIのエラー `Jumped to invalid address: E3E800D8` を直接確認。
GDB読取だけでPC=E3E800D8、r3=E3E800D9、LR=09ED1447、r4=02039600を取得。
ROM01ED1440/GBA09ED1440のldr r3,[r4,#10]、01ED1442のBL、01ED1466のbx r3と整合。
RAM02039610のcallback欄=d9 00 e8 e3。不正な関数pointerにPCS本文が入っている。
RAM02039600の24bytesはROM01F119D4/GBA09F119D4と完全一致、scr_1F1194Eの途中。
PCS decodeは改行+`than if you were to rem`。本文途中一致は表示entry/owner実行の証明ではない。
このためBatch01のNOT_REACHED判定を昇格しない。callback codeは元英語ROMから不変。
誰がRAMを書いたか、デバッガなしで再現するかはUNKNOWN。翻訳、renderer、デバッガのいずれにも原因を断定しない。
次回は同一hashの隔離ROMをGDBなしでNEW GAME再現し、再現時にcallback欄へのwriterを追跡する。
クラッシュdialogは閉じず保全。今回のtraceで観測できた部品は有効だが、ゲーム進行runtime PASSは撤回/不成立。
