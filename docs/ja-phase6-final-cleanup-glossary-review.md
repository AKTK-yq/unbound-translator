# Phase 6C-2A Glossary レビュー（Phase 6 Final Cleanup）

用語の決定だけを行った。entry本文の再翻訳、ROM生成、Python変更、controlfix、inject、commit、pushは行っていない。
`glossaries/ja.json` も未変更（139語のまま）。かなのみ、漢字なし。

入力: `out/phase6/ja_phase6_cleanup_for_claude_glossary.json`（208語、affected 282 entries＋語未特定の47 entries）。

## 成果物

| ファイル | 内容 |
|---|---|
| `tests/fixtures/ja_phase6_cleanup_glossary_claude_review.json` | 208語すべてのレビュー（decision / scope / collision_risk / charmap_ok） |
| `out/phase6/ja_phase6_cleanup_glossary_approved.json` | 承認語のmerge用パッチ（153エントリ。APPROVED_*とKEEP_EXISTINGのみ） |
| `out/phase6/ja_phase6_cleanup_glossary_unresolved.json` | 未解決・却下語（39エントリ。必要な追加情報つき） |
| `out/phase6/ja_phase6_cleanup_translation_glossary_handoff.json` | 442件の翻訳レビュー用handoff |

## 判断の基準

- **OFFICIAL**: 過去のPokeAPI監査（`out/phase6/*official_name_audit*.json` 等）に完全一致の証拠がある語だけ。記憶だけではOFFICIALにしない。
- **PROJECT_STANDARD**: Unbound固有語、既存の適用済み訳、シリーズ標準語で公式表記が入力資料にないもの。公式とは主張しない。
- **複数形**: 単数が過去監査で完全一致している場合のみ、複数形を「機械的な複数」としてproject standardにした（`plural_surface_inferred`）。単数が未確認のもの（Rawst / Belue / Watmel Berries など）は未解決。
- **図鑑の分類名**: 過去監査にPokeAPIの英語genus（例: `Butterfly Pokémon`）と日本語genus（`ちょうちょポケモン`）の組が残っていた。表の英語は「Pokémon」を含まない語幹なので、接尾辞を除いた語幹をOFFICIALにした。ただし日本語側で「ポケモン」が自動で付くかは未確認（実機で要確認）。
- 承認語はすべて `global_replace=false`。entry_ids・category・entityで限定し、語境界・完全語一致・長い語優先を要求する。
- 分かち書き: 固有名（地名・組織名・ミッション名）は内部に空白なし。説明的な語句（称号・機能名の句）は分かち書き。

## 報告（1〜20）

1. **total terms**: 208
2. **affected entries**: 282（語未特定の `entry_scope_reviews` 47件は別枠。合計329）
3. **approved official**: 16
   Butterfly=ちょうちょ、Cocoon=さなぎ、Flame=かえん、Hairy Bug=けむし、Lizard=とかげ、Poison Bee=どくばち、Shellfish=こうら、Tiny Turtle=かめのこ、Turtle=かめ、Worm=いもむし、Fresh Water=おいしいみず、Lemonade=ミックスオレ、Soda Pop=サイコソーダ、Play Rough=じゃれつく、Qualot Berry=タポルのみ、Hoopa=フーパ
4. **approved project standard**: 142
5. **approved context scoped**: 10
   Egg=タマゴ、Gem/Gems=ジュエル、Grudge=おんねん、Taunt=ちょうはつ、Torment=いちゃもん、Uproar=さわぐ、Surf=なみのり、Honey Gather=みつあつめ、Psychic=サイコキネシス（scr_1F3394E のみ。scr_1F1516B は未解決）
6. **keep existing**: 2
   Grunt=したっぱ（トレーナー名表へ適用範囲を拡張）、Shadows=シャドウズ（大文字始まりの組織名のみ。小文字shadowsは対象外）
7. **unresolved context**: 10（＋Psychicの残り1エントリ）
   [buffer1]、[buffer3]、Curse、Magnitude、Sandstorm、Stockpile、Glimmer Ticket（2行）、sankren bolganone、the soil
8. **unresolved term**: 25
   Belue / Rawst / Watmel Berries、Big Nuggets、Pretty Wings、Black Augurite（2行）、Mimikium Z、Utility Parasol（2行）、Ylw Nectar（2行）、Cactus Pokémon、Tiny Bird、Cave / Mountain / Sea Pokémon、cyclist、melony、Nidoran♀♂、Oricorio-Pa'u系（3行）、quick hms、SPA
9. **rejected candidates**: 3
   Cut（動詞 "cut them off"）、Strength（普通名詞 "strength"）、Fighting（動詞 "fighting"）。いずれも用語ではない偽陽性。
10. **places**: 31語（承認29、未解決2）。
11. **people**: 13語（承認12、未解決1: melony）。
12. **mission titles**: 32語（すべて承認。うち1つは公式とくせい名に置換）。
13. **trainer classes**: 18語（承認16、keep existing 1、未解決1: cyclist）。
14. **items/features**: 95語（item 76＋feature 19）。承認は64、未解決は28、却下は3。
15. **organization**: 12語（承認11、keep existing 1）。
16. **other**: 7語（承認4、未解決3）。
17. **collision-risk terms**: 63語（high 48、medium 15）。
    high は Egg / Gem(s) / TM(s) / Champion / Surf / Psychic / Grunt / shadows / 図鑑分類名 / 戦闘わざ名など、他の語に含まれる、または別entityで出現するもの。medium は既存glossaryの語を含む・含まれるもの（Antisis City、Zeph Jr.、Shadow Warrior Project など）。これらは長い語を先に照合する必要がある。
18. **terms affecting multiple batches**: 9
    antisis city、great desert、grim woods、Hard Stones、Hoopa、maxima、melony、ruins of void、Safari Zone
19. **charmap validation**: 承認語153エントリと未解決の参考案をすべて日本語PCS文字表で検証し、エラー0。漢字0。ヴ・「」・♀♂ は使っていない（♀♂が使えないためニドラン♀♂は未解決）。
20. **affected entries now glossary-resolvable**: 282 entries のうち **245**
    - 用語確定済み: 245（うち、戦闘メッセージのわざ名とHoopaの綴り分けなど手作業で使う必要があるもの10）
    - 未解決の用語が残る: 33
    - 用語が不要（偽陽性のみ）: 4
    - Claudeの「glossary-primary」258 entries のうち、用語確定は179、偽陽性で用語不要が4、未解決で保留が28、語未特定の47件は今回の対象外。

「glossary-resolvable」は用語が決まったという意味で、適用可能という意味ではない。本文の翻訳、幅、owner、バッファは後続の442件レビューとCodex側の確認で決まる。

## 採用時に特に判断した点

- **既存glossaryとの整合**: Antisis City=アンティシスシティ、Epidimy=エピディミー（候補『エピデミー』は既存のEpidimy Townと矛盾するので置換）、Zeph Jr.=ゼフジュニア、Tomb of Borrius=ボーリウスのはか。既存glossaryとの矛盾は0。
- **候補の置換（20行）**: Gem=ジェム→ジュエル（既存のGem Family=ジュエルファミリーと適用済み訳に合わせる）、Frost Mountain=フロストマウンテン→フロストやま（既存のサンダーキャップやま等と同形式）、Ruins of Void（3候補が衝突）=ボイドいせき、Science Society=かがくかい→かがくきょうかい、Smogon OU=スモゴンオーユー→スモゴンOU（適用済みの『OUダブル』に合わせる）、Honey Gather=あまいミツあつめ→みつあつめ（公式とくせい名）、Butterfly=ちょう→ちょうちょ（公式genus）など。
- **Hoopa**: 語としては公式（フーパ）だが、対象2エントリは『Hoo. pa.』と間を空けた綴りで、機械置換はできない。
- **戦闘メッセージのわざ名**: Taunt / Torment / Grudge / Uproar は公式わざ名が確認済みだが、メッセージでは活用・言い換えされる。参照語としてだけ使い、機械置換しない。Curse / Magnitude / Sandstorm / Stockpile は過去監査がambiguousのままなので未解決。
- **ミッション名**: 32語中31語を承認。題名に含まれる公式名（Butterfree=バタフリー、Pyukumuku=ナマコブシ）は過去監査で完全一致。Batch 04で止まっていた「ミッション名のglossary承認待ち」はこれで解消できる。

## 既存の適用済みエントリとの食い違い（情報のみ・今回は修正しない）

handoff の `applied_entry_conflicts` に ID を記録した。

- Shadows=シャドウズ（既存glossary）に対し、適用済みの4エントリが『シャドー』を使っている。
- Shadow Warriors の適用済み訳に『シャドーせんし』が混在（7エントリ）。今回の承認語は『シャドウせんし』。
- Frost Mountain: 適用済み1エントリが『フロストマウンテン』。
- Tarmigan Mansion（2）、Guardian of Borrius（1）、Shadow Warrior(s) Project（1）も表記が異なる。

## 未解決語のうち、Codexで解ける見込みのもの

PokeAPIの単数形照合で解ける見込み: Rawst / Belue / Watmel Berry、Big Nugget、Pretty Wing、Mimikium Z、Yellow Nectar、Cacnea と Pidgey のgenus。
入力資料にない知識や方針決定が必要: cyclist（公式クラス名）、melony（SwShのMelonyと同一人物か）、SPA（施設の特定）、呪文 Sankren bolganone、The Soil、生息地ラベル、ニドラン♀♂の表記。

## 今回やっていないこと

`glossaries/ja.json` の編集、entry本文の再翻訳、442件の翻訳queue、Codexの技術queue、ROM生成、controlfix、injector、PokeAPI新規実装、ASM / renderer / font / graphics、commit、push。
