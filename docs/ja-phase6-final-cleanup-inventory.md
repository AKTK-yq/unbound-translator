# Phase 6 Final Cleanup inventory — 作成のみ

Batch 01–06の残存holdを1件1行で統合した台帳は `out/phase6/ja_phase6_final_cleanup_inventory.json`。今回は分類・優先順位付けのみ。過去の保留訳、glossary、ROM、rendererは修正していない。

| 集計 | 件数 |
| --- | ---: |
| Phase 6選定 / 新規適用 / 残存hold | 2,500 / 1,371 / 1,129 |
| Phase 5以前の適用 / 現在の日本語適用総数 | 677 / 2,048 |
| P1 / P2 / P3 | 610 / 298 / 221 |
| Claude再レビュー候補（重複可） | 530 |
| Codex技術調査候補（重複可） | 808 |
| 自動解決を証明済み | 0 |
| runtime確認だけで解決可能と証明済み | 0 |

Claude候補は不完全訳・文脈・話者・FA意味衝突のいずれかを持つentry。Codex候補はbuffer・制御境界・pointer・幅・構造化UI・FA layoutのいずれかを持つentry。同じentryが両方に入るため合計してはいけない。幅だけが理由の182件も、renderer実測とcaller同定が必要で、単なる目視だけで安全と断定しない。

## Batch別

| Batch | 選定 | 適用 | hold |
| --- | ---: | ---: | ---: |
| 01 | 407 | 385 | 22 |
| 02 | 408 | 164 | 244 |
| 03 | 408 | 125 | 283 |
| 04 | 408 | 198 | 210 |
| 05 | 408 | 168 | 240 |
| 06 | 461 | 331 | 130 |
| 合計 | 2,500 | 1,371 | 1,129 |

## Hold分類

primary分類は1件につき1つ。副理由は`secondary_holds[]`に全て残し、`raw_hold_reasons[]`も保持した。

| primary | 件数 |
| --- | ---: |
| UNKNOWN_BUFFER | 280 |
| OFFICIAL_NAME_UNRESOLVED | 215 |
| WIDTH_LAYOUT | 191 |
| INCOMPLETE_TRANSLATION | 179 |
| CONTROL_BOUNDARY | 88 |
| GLOSSARY_APPROVAL | 69 |
| FA_LAYOUT | 30 |
| CONTEXT_REQUIRED | 23 |
| POINTER_OWNER | 19 |
| OTHER | 18 |
| STRUCTURED_UI | 17 |
| 合計 | 1,129 |

副理由込みのentry数: 公式名未解決215、glossary関係95、unknown buffer334、FA関係179、pointer23、幅387、制御境界88、不完全訳456、unsupported glyph6。FA semantic conflictは43件で、別理由と重なるためprimaryには現れない。これらの数は重複し、合算不可。

P1は公式名・glossary承認・不完全訳を含むもの。P2は主にbuffer、文脈、pointer、制御境界、構造化制約。P3は主にFA layout・幅。これは作業順序であり、適用許可ではない。未分類`OTHER`の18件も個別調査する。

各entryにID、batch、category、原文、候補訳、現在status、primary/secondary/raw理由、公式名・glossary・buffer・話者/文脈・FA・control・pointer・幅の状態、優先順位と次の調査を保存した。情報のない状態は`not_audited`などと明示し、推測で埋めていない。
