# Phase 6C-3A: 話者の技術的帰属

この段階はメタデータ調査のみ。訳文、口調、glossary、control、ROMを変更しない。再生成はリポジトリ直下で `python scripts/build_ja_phase6_speaker_attribution.py`。入力ROMの MD5 は `9cad8e771940e7f7094d13911552cef0` に固定して検査する。

## 入出力と母集団

- 入力: `out/phase6/ja_phase6_cleanup_translation_handoff_v2.json` 569件、`out/phase6/ja_phase6_final_cleanup_inventory_v3.json`、`out/phase6/ja_phase6_cleanup_glossary_combined_controlfix.json` 2,261件、`rom/unbound.gba`。
- 出力: `out/phase6/ja_phase6_speaker_attribution.json`、`out/phase6/ja_phase6_canon_character_candidates.json`、`out/phase6/ja_phase6_cleanup_translation_handoff_v3.json`、`out/phase6/ja_phase6_voice_review_for_claude.json`。`out/` はローカル生成物。
- 569件の内訳は `CLAUDE_CONTEXT` 267、`CLAUDE_TRANSLATION` 302。`scripts` 422件を会話候補とし、それ以外147件は今回の *NPC口調調査上* `NON_DIALOGUE` に分類した。後者が実ゲームで絶対に会話にならないという意味ではない。
- 保留キューで `PROVEN` 12件、`PLAUSIBLE` 38件、`UNKNOWN` 519件。`UNKNOWN` には上記147件の非対象を含む。会話候補の未確定は410件（`PLAUSIBLE` 38 + `UNKNOWN` 372）。
- 日本語適用済み2,261件のうち、直接の話者根拠を得た口調校正候補143件を **読み取り専用** で抽出。保留分と併せて91個の異なる実証済みspeaker ID、Claude向けには複数発話またはUnbound主要人物の56グループ・120件を整理した。これらはruntime表示を再現検証した件数ではない。

## 根拠と判定規則

ROM offset はすべて0始まり、GBAアドレスは `0x08000000 + offset`。ROMのポインタ値は読み取り時に再照合する。構造の解釈には [pret/pokefirered の MapHeader / MapEvents / ObjectEventTemplate](https://github.com/pret/pokefirered/blob/master/include/global.fieldmap.h) と [event script マクロ](https://github.com/pret/pokefirered/blob/master/asm/macros/event.inc) を参照し、Unbound側では構造・ポインタ・命令バイトを実測した。

1. MapHeader候補は layout/events/script/connections のポインタ、layout寸法、event配列、region section等を検査し、さらにROM内のリテラルポインタから参照されるものだけを採用した。158構造候補、154参照確認済みheader、790 object-script結合。group/indexのマスターテーブルは立証していないため `map_id=null`。section name はmap nameの代用品ではない。
2. object直接メッセージは、object record +`0x10` のscript pointer、`faceplayer` (`5A`)、`loadword` (`0F 00`)、text pointer、`callstd` (`09 02` または `09 06`) の連続を条件にする。同じscriptの近くにあるだけなら `PLAUSIBLE`、speaker IDは付けない。
3. trainerbattle (`5C`) のtrainer IDと最初の二つのtext operandのみを解析する。operandが対象textを指し、trainer record（base ROM `0x0023EAC8`, stride 40）からclass/nameを読める場合にその **trainer ID** への帰属を `PROVEN` とする。名前だけから歴代作品の人物とは認定しない。複数IDが同一文を指すときは個人へ統合しない。
4. `PROVEN` はポインタに対する *objectまたはtrainer IDの結合* の確度であり、そのNPCの固有名、作品の初出、原作日本語口調、あるいはruntime到達を保証しない。`UNBOUND_ORIGINAL` の二人はUnbound固有classと名前の組合せから得た分類で、出典作品の確度は別フィールドで `PLAUSIBLE` と明記する。
5. `dialogue_group_id` は直接実証された同一trainer ID、または同一map header + local object IDにだけ付ける。元データの `conversation_id`、ROM上の近接、英語の話し方、同名trainerだけでは統合しない。

実測例:

| Entry | 帰属 | ROM根拠 | 限界 |
|---|---|---|---|
| `scr_1F09A3C` | `object_003516F0_003` / `GENERIC_NPC` | MapHeader ROM `0x003516F0` (GBA `0x083516F0`)、object record ROM `0x00B7185C`、script ROM `0x01E6BC9D`、text operand ROM `0x01E6BCA0`。bytes `5A 0F 00 3C 9A F0 09 09 06` | region sectionは Magnolia Fields。map group/index とNPC固有名は未同定。 |
| `scr_1F0AC39` | `trainer_0510` / Expert Kenlawa | opcode ROM `0x01E6D1D1`、text operand ROM `0x01E6D1D7`、trainer record ROM `0x00243A78`。bytes `5C 03 FE 01 00 04 39 AC F0 09` | 作品人物としての本人認定ではない。 |
| `scr_1F33CAE` | `UNKNOWN_SPEAKER` | trainerbattle operandがtrainer ID 332/333/334から同じtextを参照 | 同文共有なので一人に割り当てない。 |

GBAアドレス例: text operand `0x01E6BCA0` → `0x09E6BCA0`、trainer record `0x00243A78` → `0x08243A78`。map headerの参照元、script、pointer ownerは生成JSONに個別収録した。

## Canon人物と口調レビュー

公式既存キャラクターの `PROVEN` は0、候補も0。ROM trainer recordで `Lucas` は trainer ID 194 / `Hiker`、`Barry` は ID 242 / `Swimmer` だったが、固有名の一致だけなので `rejected_name_only_matches` に残し、DP等の公式人物候補へ昇格させなかった。外見・party・event・人物関係・原作出典を相互検証できるまで、source game別候補数も0とする。公式日本語名、初登場作品、原作日本語口調は **未採集**。

既適用分では、Unbound固有trainer class + 主要人物名に合致する `trainer_0028` (Marlon) と `trainer_0353` (Ivory) を `UNBOUND_ORIGINAL` に分類した。ただし「Unbound以外に一切存在しない」という外部史実は証明していないため、`source_game_candidate.confidence=PLAUSIBLE`。保留569件側にこの分類は0件。汎用NPCは保留2件、既適用13件。その他のtrainer固有名は `TRAINER_CLASS` に留めた。

Claude向け出力には原文、既存和訳、明示的なscript/trainer/object根拠、scene context（存在するとき）、speaker identity status、単語・句読点から観察したstyle *clue*、原作日本語資料の未採集状態を含める。英語中の `please` や `!` は口調決定ではなく観測値であり、性別・年齢・一人称・語尾を推定していない。次工程で原作日本語資料とruntime場面を人間が照合してから訳文の口調校正を判断する。

## 不変性と残課題

`v3` は `v2` の569行に8つのspeaker欄だけを追加したもの。既存ID、original、reviewed_japanese、controls、protected tokens、hold reasons、glossary/buffer data、配列順を保持する。2,261件の適用済みJSONも読み取りのみ。生成器は入力件数、ID一意性、ROM MD5を検査し、回帰テストは元行全フィールドとの深い等価性とポインタ実体を検査する。

主な未解決事項は map group/index を持つ親テーブル、分岐・callをまたぐscript制御フロー、動的speaker、複数trainer IDの同一人物判定、canonical外見/party/イベント照合、ゲーム上の実際の表示経路、原作日本語版の口調資料である。これらを推測で埋めない。ROM/patch/injector/controlfixを変更していない。
