# Japanese Phase 4 reviewed runtime build

This is a private, kana-only 59-entry ROM for human mGBA verification. It is **not** a runtime PASS or a release build. The 56 `confirmed` rows in `tests/fixtures/ja_phase4_claude_review.json` exactly match `tests/fixtures/ja_phase4_selection.json`: 37 wordings changed, 19 stayed the same. Two `needs_context` rows have evidence-based wording; `scr_1F0F842` still keeps the earlier provisional wording. No ROM, save, or BPS file belongs in Git.

## Three context checks

- `scr_1F0F842` (ROM `0x01F0F842`, pointer operand `0x01E6FAF8`): the NEW GAME script sets selector variable `0x8001` to `3` for jacket colour, then `4` for trim colour, and calls the same selector routine at ROM `0x01EBE42C`. The separate fourth colour component is proven. The pixels affected by that component have not been visually mapped, so “clothing accent” versus “outline” versus “accessory” remains unproven. The provisional `ふちのいろをえらんで` remains; check the preview sprite in mGBA before approving it.
- `scr_1F10323` (ROM `0x01F10323`, pointer operand `0x01E6FED4`): ROM `0x01EC78B8` reads variable `0x50DF`, indexes the three pointers at ROM `0x01FB54CC` (`Difficult`, `Vanilla`, `Expert`), uses `Insane` as fallback, and copies the selected literal into `0x02021CD0` (`[buffer1]`). The final NEW GAME script calls this path at ROM `0x01E6FEC4`. Consequently, `[buffer1]` can be an English difficulty name; the current 59-entry build does not translate those four source literals. The sentence uses literal `Vanilla` and `Difficult` to avoid a mixed English/Japanese name mismatch. Exact branch reachability of `Expert`/`Insane` at this one message still needs playthrough.
- `tbl_mission_log_00017_1F560DA` (ROM `0x01F560DA`, pointer owners `0x01EBFFF8`, `0x01EC013C`): the Mission Log reward-ready path at ROM `0x01EC0064` passes a mission-field byte to `0x080C4D79`, whose lookup table is ROM `0x003F1CAC`. Its first records decode to `Frozen Heights`, `Bellin Town`, `Dresco Town`, etc.; the result goes into `0x02021CD0` before expansion of the reward template. `[buffer1]` is a location/map name on this path, not a person or mission title. The location-neutral reviewed wording is `[buffer1]に もどって ごほうびを うけとろう！`.

`\qo` and `\qc` encode as `B1` and `B2`. In Japanese normal font, ROM glyph data for those codes is nonempty at `0x0020A120` and `0x0020A140`, and ROM width bytes `0x0020F5B1/0x0020F5B2` both equal 10 pixels. The whole normal Japanese font asset at ROM `0x00207500–0x0020F4FF` matches the local FireRed JPN ROM byte-for-byte. A Latin switch is unnecessary for these two glyph codes; controlfix does switch to Latin around `[buffer1]`. The actual quote shapes and spacing on this Unbound screen still need mGBA confirmation. Adding `\qo/\qc` to the reviewed sentence would add semantic tokens absent from the source, so this build does not do that. `Vanilla` and `Difficult` are not registered as Japanese glossary translations.

## Rebuild and checks

From the repository root, using the selected Python environment:

```text
python 001_extract_unbound_text.py rom/unbound.gba -o out/unbound-ja-phase4-reviewed-extracted.json
python 002_prepare_translation_text.py out/unbound-ja-phase4-reviewed-extracted.json -o out/unbound-ja-phase4-reviewed-prepared.json
python scripts/build_ja_phase4_selection.py out/unbound-ja-phase4-reviewed-prepared.json tests/fixtures/ja_phase4_selection.json -o out/unbound-ja-phase4-reviewed-translated.json
python 004_controlfix_translations.py out/unbound-ja-phase4-reviewed-translated.json -o out/unbound-ja-phase4-reviewed-controlfix.json --source out/unbound-ja-phase4-reviewed-prepared.json --report out/unbound-ja-phase4-reviewed-controlfix-report.json --target-lang ja
python 005_hybrid_injector.py rom/unbound.gba out/unbound-ja-phase4-reviewed-controlfix.json -o out/unbound-ja-phase4-reviewed.gba --target-lang ja --map-output out/unbound-ja-phase4-reviewed-dry-run-map.json --dry-run --fail-on-no-space
python 005_hybrid_injector.py rom/unbound.gba out/unbound-ja-phase4-reviewed-controlfix.json -o out/unbound-ja-phase4-reviewed.gba --target-lang ja --map-output out/unbound-ja-phase4-reviewed-map.json --fail-on-no-space
python scripts/audit_ja_phase4.py rom/unbound.gba out/unbound-ja-phase4-reviewed.gba out/unbound-ja-phase4-reviewed-controlfix.json tests/fixtures/ja_phase4_selection.json out/unbound-ja-phase4-reviewed-map.json --report out/unbound-ja-phase4-reviewed-audit.json --markdown out/unbound-ja-phase4-reviewed-report.md
```

The manual selection builder is the reviewed translation-data stage. Do not invoke the LLM for these 59 rows. The strict glossary resume validator intentionally demands exact target occurrences; four reviewed Japanese sentences use inflection or fewer repeated occurrences than the English source. It would queue those hand-reviewed sentences for machine translation. Future full translation must decide how to validate inflected Japanese glossary terms safely.

Final controlfix: 59 translated, 23 wrapped, 0 control mismatches. A second pass has `changed: 0` and byte-identical JSON. The Japanese wrapper prefers word spaces, removes spaces at line/page boundaries, retains interior phrase spaces, and preserves `[latin][buffer1][japanese]`. Dry-run: 59 input, 0 encode errors, 0 pointer mismatches, 0 implausible pointers, 0 truncations, 0 missing relocations/fixed slots, 0 runtime patches, 0 graphics patches. Placement: 42 in-place, 17 relocated, 21 pointer writes; 231 vetted FF bytes used.

Audit: original MD5 `9cad8e771940e7f7094d13911552cef0`; output MD5 `a4716035071e6adde68a7edd5e6388bb`. Changed bytes: 1,944 in-place text, 214 relocated text, 70 pointer bytes, 2,228 total. Unexpected bytes: 0. Every relocation destination starts in an original `FF` span, lies in vetted FF space outside the injector's reserved code/font regions, does not overlap another write, has all listed owners updated, and leaves its old slot unchanged. The audit also scans for each old pointer value; none remains. Exact byte ranges and all 59 entries are in `out/unbound-ja-phase4-reviewed-audit.json` and `out/unbound-ja-phase4-reviewed-report.md`.

Relocation destinations and pointer owners (ROM offsets):

| Entry | Destination | Owners |
| --- | --- | --- |
| battle 00011 | `0x00B50B80` | `0x003FE450` |
| battle 00012 | `0x00B50B96` | `0x003FDFB4` |
| battle 00017 | `0x00B5E2C4` | `0x003FDF7C` |
| battle 00343 | `0x00B5E2D6` | `0x000D7650`, `0x009BE13C` |
| pause Bag | `0x00B50BB1` | `0x00120674` |
| pause Pokémon | `0x00B5E2EA` | `0x000DABF4`, `0x003A734C` |
| pause Save | `0x00B5E2F3` | `0x003A7364` |
| pause Option | `0x00BC8880` | `0x003A736C` |
| common Yes/No | `0x00BC8889` | `0x001100A0` |
| Text Speed | `0x00BC8894` | `0x003CC314` |
| option Slow | `0x00B5E2FC` | `0x003CC330` |
| option Fast | `0x00BC88A0` | `0x003CC338` |
| Missions | `0x00BC88A8` | `0x01EBE988` |
| mission Type | `0x00BC88B3` | `0x01EBE9D4` |
| mission Active | `0x00B63308` | `0x01EBFFC8`, `0x01FB40B8` |
| mission Location | `0x00B63314` | `0x01EBF178`, `0x01EC0010` |
| name confirmation | `0x00B63323` | `0x01E6FB8E` |

## UI width audit

Widths use the ROM normal Japanese width table at `0x0020F500`; Japanese space `00` is 10 pixels by the ROM renderer's special case. These are glyph advances, before any per-printer extra letter spacing.

| Entry / final text | Old width | Slot / encoded bytes | New width | Placement | Display-width conclusion |
| --- | ---: | ---: | ---: | --- | --- |
| Text Speed / `はなしのはやさ` | 59 px | 11 / 12 | 70 px | relocated | Widest original option label is `Battle Scene` at 68 px; new label is 2 px wider. Exact option-column bound unproven. |
| mission Active / `しんこうちゅう` | 33 px | 7 / 12 | 69 px | relocated | Large width growth. Tab/neighbor bounds unproven. |
| mission Missions / ` ミッション` | 46 px | 10 / 11 | 58 px | relocated | Leading blank is present in original and retained. Neighbor bounds unproven. |
| pause Save / `レポート` | 24 px | 5 / 9 | 40 px | relocated | Below the original pause-menu maximum of 54 px (`[player]` conservative buffer estimate). Runtime check still required. |
| pause Option / `せってい` | 32 px | 7 / 9 | 39 px | relocated | Below the same 54 px baseline. Runtime check still required. |
| character prompt / `キャラを えらんで ください。` | 109 px | 20 / 20 | 149 px | in-place | Single line; NEW GAME-specific window capacity not independently measured. |

Relocation solves ROM storage only. It does not prove that longer labels fit their drawn windows or avoid neighbors. In particular, verify Text Speed, Active, and Missions on mGBA.

## Seven lengthened dialogues

Counts below refer to controlfixed PCS bytes including terminator. Lines count displayed line segments; pages count clear-page (`FB`) segments. All seven stay in-place with zero pointer writes. `FE/FA/FB` lists byte counts before and after.

The reviewed translation-data wording before controlfix is as follows (the injector uses the wrapped version):

| ID | Before | Reviewed after |
| --- | --- | --- |
| `scr_1F0FE27` | なぞときのむずかしさをえらんでください。むずかしいほどかんがえるなぞやかくれるなぞがてごわくなります。 | なぞときの むずかしさを えらんで ください。 むずかしいほど あたまを つかう なぞときや こっそり すすむ なぞときが てごわく なります。 |
| `scr_1F0FC3F` | `[green][buffer1][black]があなたへのおすすめです。もっとむずかしいレベルもえらべますがたのしめなくなるかもしれません。[green][buffer1][black]でつづけますか？` | `[green][buffer1][black]が あなたへの おすすめの むずかしさです。 もっと うえの むずかしさも えらべますが たのしめなく なるかも しれません。 [green][buffer1][black]で つづけますか？` |
| `scr_1F0FF35` | バトルのむずかしさをえらんでください。むずかしいほどトレーナーややせいのポケモンがつよくなります。 | バトルの むずかしさを えらんで ください。 むずかしいほど トレーナーは つよく やせいの ポケモンは かしこく なります。 |
| `scr_1F0F9FA` | むずかしいなぞときはすきですか？かくれたりいわをおしたりするなぞときもあります。 | むずかしい なぞときは すきですか？ こっそり すすんだり いわを おしたり する なぞときも あります。 |
| `scr_1F0FB85` | ときどきチームのポケモンをあたらしくそだててもいいですか？ | ときどき あたらしい ポケモンを そだてて チームに いれても だいじょうぶですか？ |
| `scr_740088` | ねえきみ！おばあちゃんのばんごはんはとってもおいしいんだ！いつかたべにきてよ！ | ねえ きみ！ おばあちゃんの ばんごはんは とっても おいしいんだ！ こんど たべて いってよ！ |
| `scr_7401A9` | パパがポケモンをたくさんきたえたんだ！いまはすごくつよいよ！ | パパが うちの ポケモンを たくさん きたえたんだ！ いまは すごく つよいよ！ |

| ID | Slot | Bytes before/after | Lines before/after | FE before/after | FA before/after | FB before/after | Pages before/after |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `scr_1F0FE27` | 103 | 59 / 77 | 4 / 5 | 1 / 2 | 1 / 1 | 1 / 1 | 2 / 2 |
| `scr_1F0FC3F` | 198 | 88 / 102 | 5 / 7 | 2 / 2 | 1 / 2 | 1 / 2 | 2 / 3 |
| `scr_1F0FF35` | 111 | 57 / 68 | 4 / 4 | 1 / 1 | 1 / 1 | 1 / 1 | 2 / 2 |
| `scr_1F0F9FA` | 105 | 47 / 58 | 3 / 4 | 1 / 1 | 1 / 1 | 0 / 1 | 1 / 2 |
| `scr_1F0FB85` | 66 | 35 / 47 | 2 / 3 | 1 / 1 | 0 / 1 | 0 / 0 | 1 / 1 |
| `scr_740088` | 92 | 46 / 53 | 3 / 4 | 1 / 1 | 1 / 1 | 0 / 1 | 1 / 2 |
| `scr_7401A9` | 60 | 36 / 45 | 2 / 3 | 1 / 1 | 0 / 1 | 0 / 0 | 1 / 1 |

Full old/new translation text and review reasons are recorded by ID in `tests/fixtures/ja_phase4_claude_review.json`; final wrapped text is in `out/unbound-ja-phase4-reviewed-report.md`. The extra page in `scr_1F0FC3F`, `scr_1F0F9FA`, and `scr_740088` is an intentional layout consequence of the complete reviewed wording, not storage relocation.

## Human mGBA checklist

Use a new save/NEW GAME on `out/unbound-ja-phase4-reviewed.gba`; the old Phase 4 save may skip intro. Inspect glyphs, line breaks, control pacing, page advance, choice selection, and neighboring UI. Mark each item observed or unreachable; no result below is asserted as observed.

1. NEW GAME opening: `scr_1F0F79C`, region introduction and pause token.
2. Character: `scr_1F0F7EC`, `scr_1F0F858`; verify the 149-pixel prompt and choice transition.
3. Skin/hair/jacket/trim: `scr_1F0F800`, `scr_1F0F814`, `scr_1F0F82A`, `scr_1F0F842`; watch which sprite pixels change at trim.
4. Name selection/confirmation: `scr_1F0F874`, `scr_1F0F89C`; try a Latin player name and verify page restoration after `[player]`.
5. Difficulty questions: `scr_1F0F8AD`, `scr_1F0F9DD`, `scr_1F0F9FA`, `scr_1F0FB85`; exercise branches, not just defaults.
6. Recommended difficulty buffer: `scr_1F0FC3F`; check both `[buffer1]` occurrences, green/black colour, three pages.
7. Puzzle choice: `scr_1F0FE27`; check `FE`, `FA`, `FB` pacing and five lines across two pages.
8. Battle choice: `scr_1F0FF35`; check page and full “wild Pokémon become smarter” clause.
9. Final difficulty message: `scr_1F10323`; record actual `[buffer1]` value for Vanilla, Difficult, and harder branches; compare literal mode names.
10. A relocated ordinary dialogue: `scr_1F0F89C`; verify name-confirmation text and no freeze.
11. After intro, pause menu: `tbl_menu_pause_00001_416285`, `...00002_415A66`, `...00007_416291`, `...00008_416296` for Bag, Pokémon, レポート, せってい.
12. Options screen: `tbl_menu_options_00001_419DD3` (`はなしのはやさ`), Slow/Fast rows; inspect value-column collision and neighboring labels.
13. Party/Bag: `tbl_menu_pokemon_00000_4171DF`; inspect item rows `tbl_item_names_00004_8762B0`, `...00013_87643C`, `...00014_876468`.
14. Species/moves when available: `tbl_pokemon_names_00001_166A997`, `...00025_166AA9F`, `...00344_166B854`; `tbl_move_names_00015_A40AD3`, `...00033_A40BBD`, `...00085_A40E61`.
15. Battle: trigger next-Pokémon prompt `tbl_battle_messages_00011_3FB359`; trigger poison/faint/move texts `...00012_3FB5E2`, `...00017_3FB400`, `...00343_3FD57B` under matching conditions.
16. Mission Log when unlocked: `tbl_mission_log_00000_1F56040` (ミッション), `...00002_1F56055` (Type), `...00003_1F5605C` (しんこうちゅう); inspect tab collisions.
17. Mission detail/location and reward-ready state: `tbl_mission_log_00014_1F560B1`, `...00017_1F560DA`; record the actual place name in `[buffer1]`.
18. Mission titles: `scr_1F2CB91`, `scr_1F2CBA2` when the corresponding hero/heroine mission is active.
19. NPCs: `scr_740088`, `scr_7401A9`, `scr_740753`, `scr_74145B`, `scr_744C3D`, `scr_744F54`, `scr_7450DB`, `scr_745D0D`, `scr_745D25`. Script operands are owned; exact maps/events have not been independently located, so log any unreachable ID.
20. Save through `レポート`, then reset mGBA.
21. Load the new save, reopen pause/options/Mission Log, and confirm both translated and unmodified English text still render and controls remain functional.

No kanji, font/ASM/runtime/graphics patch, full translation, release BPS, ready-translations JSON, commit, or push is part of this build.
