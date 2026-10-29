# Phase 7C-6 静的追補：buffer3自己参照仮説

画面取得・キー入力・mGBA起動なし。OWへ干渉するUI操作なし。新規runtime試行0。
既存のPhase7C6成果物は上書きせず、追補だけ作成。ROM・訳文・glossary変更、commit/pushなし。

## 新しい根拠

通常のfield表示はROM000694C8/GBA080694C8、literal ROM000694E0=RAM02021D18を展開先にする。
expander入口 ROM00008FCC/GBA08008FCC、通常1byte書込ROM000090A6/GBA080090A6。
FD処理ROM00009004、再帰call00009010、FF書込000090AE。容量引数・範囲検査はこの経路にない。
FD04 factory table owner ROM00231E80/GBA08231E80=0800913D、factory0000913C、literal00009140=02021D04。
buffer3はfield展開先の20bytes手前。これはライブRAM値ではなくROM上の対応関係。

scr_1F1194Eは先頭283bytesをコピーした後、最初のFD04（buffer3）に到達する。
先頭283bytesにFC/FD/FFはない。FE/FBはexpanderでそのままコピーする。
buffer3の20bytesにFFも再帰を起こすFDもない場合、再帰copyが既に展開した本文へ入り込む。
その場合は20+283=303bytes周期の自己参照copyが継続する。単なる有限長437bytesのoverflowとは別の仮説。

## 限定モデルの照合

モデルはPython bytearrayの仮想RAMだけを使用。実Thumb実行・mGBA試行・ライブPC捕捉ではない。
FF/FD/通常byteの該当経路だけをモデル化し、FC/未知FDはエラー。書込回数・再帰深度・範囲を制限。
初期callback=08087FE1、buffer3=20個の00は仮定であり観測値ではない。
RAM02039600の位相は (02039600-02021D18-283)%303=154。
最初の20bytesを引くと原文offset134（ROM01F119D4/GBA09F119D4）となる。
このモデルが予測する24bytesは、前Phaseで観測した02039600の24bytesと完全一致。
callback02039610..13はd9 00 e8 e3、Thumb pointer E3E800D9、bx後 E3E800D8を予測する。
通常byte書込候補は080090A6だが、実行時writer PCの捕捉ではない。
正常なhim/he/son、her/she/daughterをFF終端で設定した対照モデルは有限長で戻り、callbackへ書かない。

## 正常な設定経路も存在する

会話直前のscript call owner ROM01E70929/GBA09E70929は helper ROM01E709DB/GBA09E709DBを呼ぶ。
opcode A0 handler ROM0006C4F0/GBA0806C4F0は*RAM0300500Cの+8をraw u8で読む。
helperは結果0でROM01E709F3、1でROM01E70A06へ分岐し、opcode85でbuffer1/2/3を設定。
0ならhim/he/son（各4/3/4bytes、FF込み）、1ならher/she/daughter（各4/4/9bytes）。
他の値ではこのhelperのbuffer設定をせずreturnする。ただし橋での実際の値はUNKNOWN。
bufferstring handler ROM0006BF14/GBA0806BF14、table literal owner0006BF38=08B2A250。
table ROM00B2A250/54/58の宛先は02021CD0/02021CF0/02021D04。
StringCopyのbyte書込はROM00008D8A、FF書込00008D9A。設定が実行されれば終端を付ける。
このcode/table/helper/son等の本文とpointerは英語ROM・日本語ROMで一致。
途中のnative header ROM01EB59D0は、局所source ROM01F2CAE8の???（4bytes、FF込み）を扱う。
このheader sourceも不変。437-byte本文をこの小さいheader stackへコピーすると決めつけない。

## 判定と次の必要観測

CONDITIONAL_EXACT_MATCH_NOT_RUNTIME_PROVEN。単なる類似文より強い位相一致だが、原因確定ではない。
なぜbuffer3が未終端になるか、helperがどのbranchを実行したか、後から誰が壊したかは未証明。
文字列途中一致だけで推定した任意destinationを置かず、ROMで確定したFIELD/buffer3配置から計算した。
正常な設定branchがあるため「元ROMも必ず壊れる」「日本語化が無関係」とも断定しない。

次回ユーザーが操作可能な時だけ、expander r1=09F1194Eでbuffer3の20bytesとfield初期状態を捕捉。
最初のFD04直前（08009004）のr4/r5とbuffer3終端、helperのraw gender、opcode85実行を確認。
080090A6でr4=02039610の条件付き停止ができれば、実際の書込みとbefore/afterを記録。
FD04前に有効なFFがあれば、この仮説の前提は成立しない。他のwriterを調べ、仮説を押し通さない。
英語・GDBなし比較は依然NOT_RUN。新しいruntime PASSなし、Batch01 53件承認0を維持。

再現: python scripts/investigate_ja_phase7_crash_static_followup.py --verify-existing
旧成果物・保護909のハッシュ検証、新規追補のexclusive生成、負例テストを実施。結果は最終報告参照。
