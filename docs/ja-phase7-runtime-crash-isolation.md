# Phase 7C-6: Runtime Crash Isolation / Callback Writer Investigation

調査のみ。修正・注入・commit/pushなし。自動操作の許可は撤回済み、追加キー入力なし。

## 比較結果

|条件|ROM|GDB|今回対象試行|結果|
|---|---|---|---:|---|
|A|英語元ROM|なし|0|NOT_RUN|
|B|基準日本語ROM|なし|1|橋の場面でCRASH_OBSERVED、E3E800D8|
|C|英語元ROM|あり|0|NOT_RUN|
|D|基準日本語ROM|あり|0|NOT_RUN（前Phaseのクラッシュ履歴1件は別枠）|

B2は新規portableディレクトリ・独立saveで起動。autoload/cheat/patch/rewindなし、-g/-dなし、2345 listenerなし。
原ROMをbyte同一コピー。installed mGBA Qt0.10.5 executableもコピーし、portable.iniでconfig.ini/qt.iniを隔離。
[mGBA config.c](https://github.com/mgba-emu/mgba/blob/0.10.5/src/core/config.c)と
[Qt ConfigController](https://github.com/mgba-emu/mgba/blob/0.10.5/src/platform/qt/ConfigController.cpp)でrouting確認。
setup-only B1はhidden launchで打切り。再現試行に数えず、新しいB2 saveを使用。削除なし。
B2開始は人間操作。許可されたX1回を序盤で使用後、許可撤回。後続の正確な手動操作列はUNKNOWN。
最後の観測文章は「はるか むかし…」、次の観測はHoopa。クラッシュ直前の文章と正確な時刻はUNKNOWN。
ユーザーの画像と報告で橋のクラッシュを確認。画像SHA/一時ROMSHA/起動argvはfixture・matrixへ記録。
後の読取確認でmGBA processは存在せず、今回RAM/register捕捉なし。

GDB接続はクラッシュの必要条件ではない。ただし英語ROM比較未実施なので、日本語化原因とは断定しない。
新規条件の反復は1件のみ。通常実行PASS・修正済み・全条件再現性とも判定しない。

## callbackライフサイクル（静的根拠）

RAM02039600はScanlineEffect相当。+10=callback、+14=source index、+15=state。
ROM00087EA4 / GBA08087EA4 clearはsource/dest/control/state等をreset。callback +10は消さず、state0でcallしない。
ROM00087EE4 / GBA08087EE4 SetParams、00087F28 / 08087F28 `01 61: str r1,[r0,#10]`がcallback4bytesを設定。
16bit比較literal ROM00087F08=A2600001、pointer literal00087F14=08087FE1。
別分岐literal00087F50=08088001。little endianはe1 7f 08 08 / 01 80 08 08。
これらは静的候補。正常時実値・初回書込み・更新時刻は未観測。
ROM00087F54 / GBA08087F54のhook literalは09ED13F5。
ROM01ED13F4 / GBA09ED13F4はstate0でreturn、3でstop、その他でDMA設定とcallbackを呼ぶ。
ROM01ED1440 / GBA09ED1440 `23 69: ldr r3,[r4,#10]`、01ED1442から01ED1466 / 09ED1466の`18 47: bx r3`へ。
構造/順序は[FireRed scanline_effect.c](https://github.com/pret/pokefirered/blob/master/src/scanline_effect.c)と照合。
対象code/literal blockは元ROMと日本語ROMで同一。全writerを列挙した証明ではない。

## 前PhaseのRAM証拠とPCS照合

以下はPhase7C5のGDB捕捉。今回B2のRAM実測に転用しない。
02039610=d9 00 e8 e3、r3=E3E800D9、PC=E3E800D8、LR=09ED1447、SP=03007DB0。
Thumbビットは立つが、実行先はROM/RAM callback範囲外。state02039615=E6も0/3でなくcall分岐と整合。
02039600の24bytesはROM01F119D4 / GBA09F119D4のPCS本文と完全一致。
scr_1F1194E開始ROM01F1194E / GBA09F1194Eから+0x86(134bytes)、decodeは改行+`than if you were to rem`。
本文437bytes、FF終端、FE7/FA0/FB8/FC0/FD3。PCS roundtrip一致。
pointer owner ROM01E7093B / GBA09E7093B=4e 19 f1 09。
本文全slotとownerは元ROM・基準ROMで同一。このentryは適用済み2403件に含まれず、relocationなし。
source SHA=e3944a9fe0787f81529fca219127c1bab55ba97a11d77088d4c434c63f10f4df。
途中一致はbyte由来の証拠のみ。active renderer、実destination、write関数、overflowの証明ではない。
source pointerが同一でも、他の日本語化entryやdynamic bufferの間接的影響は未除外。

## writer追跡・保留

最初の不正書込みNOT_CAPTURED、writer PC/function UNKNOWN。正常RAM値の実測0。
write watchpointは[mGBA0.10.5 GDB source](https://github.com/mgba-emu/mgba/blob/0.10.5/src/debugger/gdb-stub.c)でZ2の実装を確認。
_setBreakpointはsizeを消費しない。4bytes指定だけで全面監視を証明せず、02039610/11/12/13の各addressを実験検証する。
今回watchpointは実行していない。GDBのみが原因でないと分かったため、先に英語/GDBなしAを比較。
その後必要ならcallback setter/読出し、write watchでold/new、PC/LR/SP、実instructionのwidth/addressを捕捉。
最後のbxをwriterと誤認しない。根拠のない修正patchは作らない。

## 再現計画・保護

tests/fixtures/ja_phase7_crash_repro_plan.json参照。自動キー入力は現在禁止。
A/Bは毎回新しいfolder/save、同version/config、NEW GAME。既存save・savestate禁止。
橋を通過して初めて「対象まで再現せず」とする。title/Hoopaのみ到達はINCOMPLETE。
C/Dは別試行。接続・step・detach順も記録する。前PhaseのDを同条件比較と偽装しない。
前Phaseのfont2/224px/spacing1/FE14は部品観測として維持。font4/5、FA/FB、player、Batch01 53件は未観測のまま。
Batch01注入承認0、既適用2403、Phase6保留774を維持。
元ROM SHA=7aa25bbf568f7cfcf6ee1cf2e9e6ff637350b3d0705c2375cabb6baa7d9739f7、MD5=9cad8e771940e7f7094d13911552cef0。
日本語ROM SHA=0d1d00e7b0f4f113514abbcf1907e6d8949fd12b9193bf2cb0ad764ace5559d8。既存save7ファイル、global config/qt.ini、protected909 hash不変を検証。
実施済み/未実施はmatrixで区別。原因確度UNKNOWN。追加の手動比較が必要なので今回writer追跡を打切り。

再現可能な解析: `python scripts/investigate_ja_phase7_crash_isolation.py --verify-existing`。
新規成果物だけ`--write-new`で生成。既存成果物は無断上書きしない。
pytest/py_compile/diff-check結果は最終報告参照。安全gateと期待SHAは変更せず、完全一致6パスだけ追加。
