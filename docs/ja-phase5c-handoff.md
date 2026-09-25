# Phase 5C: technical/context handoff (ROM unchanged)

This is a read-only evidence handoff for the 37 Phase 5B technical holds and 116 `needs_context` reviews. It does **not** approve new Japanese wording, patch the ROM, or claim mGBA runtime PASS. Source is `rom/unbound.gba` (MD5 `9cad8e771940e7f7094d13911552cef0`). Rebuild the ignored JSON evidence with `python scripts/build_ja_phase5c_handoff.py`:

- `out/ja-phase5c-technical-audit.json`: all 37 technical rows, bytes/pixels, pointer evidence, conservative next check.
- `out/ja-phase5c-needs-context-for-claude.json`: all 116 review rows, exact source/candidate/tokens, owner evidence, nearby text with uncertainty labels, known buffer facts.
- `out/ja-phase5c-difficulty-audit.json`: 26 Options/NEW GAME difficulty and choice rows, Phase 5B status, exact ROM anchors, unapproved kana size budgets.

## Priority: Options-menu difficulty change

The user clarified that the English screen was the **menu's difficulty-change screen**, not necessarily the NEW GAME introduction. ROM `0x01FB3948` (GBA `0x09FB3948`) contains three consecutive pointers: `Battle Difficulty` label `0x09F4DB23`, choice-list pointer `0x09FB3A18`, and help-description pointer `0x09F4E037`. The puzzle counterpart at ROM `0x01FB37B8` contains `Puzzle Difficulty` `0x09F4DC09`, choice list `0x09FB3A4C`, and help `0x09F4DE12`. The battle list at ROM `0x01FB3A18` points, in order, to `Vanilla`, `Difficult`, `Expert`, `Insane` at `0x01F10630`, `0x01F10621`, `0x01F1063D`, `0x01F10644`. This is a structured settings record/choice table, not an ASCII occurrence. Its exact consumer function has not yet been disassembled, but the table ownership and observed menu make this the leading runtime path.

| Options field | Entry / ROM offset (GBA = `0x08000000 + offset`) | Slot | Pointer owner | Phase 5B reason for English |
| --- | --- | ---: | --- | --- |
| `Battle Difficulty` label | `tbl_setting_names_00013_1F4DB23`, `0x01F4DB23` | 18 | `0x01FB3948` | Not among the 750 selected entries |
| Battle help, “The battle difficulty for all battles.” | `tbl_menu_game_settings_00035_1F4E037`, `0x01F4E037` | 39 | `0x01FB3950` | Not selected |
| `Puzzle Difficulty` label | `tbl_setting_names_00014_1F4DC09`, `0x01F4DC09` | 18 | `0x01FB37B8` | Not selected |
| Puzzle help, “The difficulty of overworld puzzles.” | `tbl_menu_game_settings_00018_1F4DE12`, `0x01F4DE12` | 37 | `0x01FB37C0` | Not selected |
| Four battle choices | `scr_1F10630`, `scr_1F10621`, `scr_1F1063D`, `scr_1F10644` | 8, 10, 7, 7 | `0x01FB3A18–0x01FB3A24` plus script/buffer owners below | Selected, but all `needs_context`: mode-name glossary not approved |

Options also has two reduction warnings. `tbl_menu_game_settings_00001_1F4E328` (ROM `0x01F4E328`, 163 bytes, pointer `0x01EBD7F8`) was confirmed/applied in Phase 5B. The other warning exposed a **duplicate/coverage error**: real text begins ROM `0x01F4E26F` (GBA `0x09F4E26F`), occupies 185 bytes, and is pointed to by ROM `0x01EBD7FC`; it decodes as `[red]WARNING![black]...cannot be raised to anywhere above Difficult...`. The old extractor already emitted the full `scr_1F4E26F`, but it also emitted a second manual entry `tbl_menu_game_settings_00000_1F4E274` starting five bytes late (`RNING!...`) with no owner. Phase 5A selected the *clipped* entry, not the complete one. `001_extract_unbound_text.py` now starts the manual range at `0x01F4E26F` and records its pointer owner, yielding one complete `tbl_menu_game_settings_00000_1F4E26F`; translate only this corrected ID after review. The baseline extraction went from 25,045 to 25,044 entries solely by removing the duplicate `scripts` row; category `menu_game_settings` remains 81. Puzzle-change notices `tbl_menu_game_settings_00002_1F4E3CB` and `...00003_1F4E454` were confirmed/applied in Phase 5B, but branch-specific runtime display still needs observation.

For the next focused Options test, check both difficulty rows, all four choices, switching from Vanilla to Difficult and from Expert to Insane when available, the help descriptions, both reduction-warning branches, the puzzle-change notice, and post-selection persistence after closing/reopening Options and save/load. Measure the actual choice-field clipping in mGBA before approving names longer than English. Do not conflate these Options fields with the separate NEW GAME dialogue prompts.

## Separate NEW GAME difficulty path

The direct NEW GAME script cluster is ROM `0x01E6FC00–0x01E6FF00` (GBA `0x09E6FC00–0x09E6FF00`). Dialogue pointers there lead to the following extracted entries. A recorded script pointer establishes ownership; a particular player branch is not claimed as played unless marked by the user.

| Role | Entry / text ROM offset (GBA = `0x08000000 + offset`) | Slot | Phase 5B | Ownership/evidence |
| --- | --- | ---: | --- | --- |
| Puzzle prompt/title, “Choose your preferred puzzle difficulty” | `scr_1F0FE27`, `0x01F0FE27` | 103 | Japanese applied | script pointer `0x01E6FDB4`; Phase 5B text slot is Japanese |
| Battle prompt/title, “Choose your preferred battle difficulty” | `scr_1F0FF35`, `0x01F0FF35` | 111 | Japanese applied | script pointers `0x01E6FD30`, `0x01E6FE02`; Phase 5B text slot is Japanese |
| Recommended `[buffer1]` prompt | `scr_1F0FC3F`, `0x01F0FC3F` | 198 | Japanese template applied, buffered mode name English | script pointers `0x01E6FCF1`, `0x01E6FD14` |
| Expert recommended explanation | `scr_1F0FD05`, `0x01F0FD05` | 290 | English held (`needs_context`) | script pointer `0x01E6FCCE` |
| Puzzle result `[buffer1]` | `scr_1F0FE8E`, `0x01F0FE8E` | 167 | Japanese template applied | script pointers `0x01E6FC4E`, `0x01E6FDF8` |
| Difficult explanation/confirmation | `scr_1F0FFA4`, `0x01F0FFA4` | 277 | English held (`needs_context`) | script pointers `0x01E6FD7B`, `0x01E6FE71` |
| Expert explanation/confirmation | `scr_1F100B9`, `0x01F100B9` | 243 | English held (`needs_context`) | script pointers `0x01E6FD98`, `0x01E6FE8E` |
| Insane warning/confirmation | `scr_1F101AC`, `0x01F101AC` | 375 | English held (`needs_context`) | script pointer `0x01E6FEAA` |
| Normal NEW GAME result `[buffer1]` | `scr_1F10323`, `0x01F10323` | 135 | English held (`needs_context`) | script pointer `0x01E6FED4` |
| NEW GAME+ result `[buffer1]` | `scr_1F103AA`, `0x01F103AA` | 149 | Japanese template applied, buffered mode name English | script pointer `0x01E6FEE1` |

Phase 5B's four **direct choice literals** were selected but not translated because the review marked all four `needs_context`: the difficulty-name glossary had not been approved. They are distinct from the duplicate `scr_A4ED04` etc. literals at ROM `0x00A4ED04–0x00A4ED35`, whose recorded owners are around `0x00A13488–0x00A134D0` and whose NEW GAME use is not established. The Options settings labels `tbl_setting_names_00014_1F4DC09` (“Puzzle Difficulty”) and `...00013_1F4DB23` (“Battle Difficulty”) were not in the 750 selection and are **not** the proven NEW GAME dialogue prompts above.

| Mode | Direct entry / ROM offset | Slot | Script choice operand | Other recorded data owners | Additional exact pointer |
| --- | --- | ---: | --- | --- | --- |
| Difficult | `scr_1F10621`, `0x01F10621` | 10 | `0x01E6FD4A`, `0x01E6FE1C` | `0x01FB3A1C`, `0x01FB54CC` | `0x01E6FCEB`: `85 00` `bufferstring 0` operand |
| Vanilla | `scr_1F10630`, `0x01F10630` | 8 | `0x01E6FD3C`, `0x01E6FE0E` | `0x01FB3A18`, `0x01FB54D0` | `0x01E6FD0E`: `85 00` `bufferstring 0` operand |
| Expert | `scr_1F1063D`, `0x01F1063D` | 7 | `0x01E6FD58`, `0x01E6FE2A` | `0x01FB3A20`, `0x01FB54D4` | none found |
| Insane | `scr_1F10644`, `0x01F10644` | 7 | `0x01E6FE38` | `0x01E8D98E`, `0x01E8DC59`, `0x01EC78E4`, `0x01FB3A24` | none found |

The script loads the four name pointers before a battle choice at ROM `0x01E6FE3F`: `6F 13 05 22 01` (`multichoice`, x=19, y=5, list `0x22`, no cancel). Puzzle choice is at `0x01E6FDD5`: `6F 11 08 20 01`. The byte meanings follow the [FireRed event-script macros](https://github.com/pret/pokefirered/blob/master/asm/macros/event.inc); Unbound's exact menu special behavior and pixel clipping still require runtime verification. This directly associates the four `0x01F106xx` literals with the NEW GAME choice path, not merely an ASCII hit.

The recommended prompt buffers mode text through `85 00 <pointer>` at ROM `0x01E6FCE9` (Difficult) and `0x01E6FD0C` (Vanilla). The normal result calls Thumb routine ROM `0x01EC78B8` (GBA `0x09EC78B8`) from `0x01E6FEC4`. That routine reads variable `0x50DF`, selects the three pointers at `0x01FB54CC` (Difficult, Vanilla, Expert), falls back to Insane via literal `0x01EC78E4`, and copies to RAM `0x02021CD0` (`[buffer1]`); the earlier disassembly is recorded in `docs/ja-phase4-reviewed.md`. Thus `[buffer1]` in `scr_1F10323` is the selected mode name, **not** the player's name. The puzzle result has its own `bufferstring` path and must not be assumed to use this four-mode table.

The four choice strings are ordinary pointer-owned, not `fixed_slot`, but relocation is safe only when **all** real consumers are updated. The two missing `bufferstring` owners above must be added to the extraction/injection ownership before either string is relocated. As byte-budget examples only (not approved translations), page-marked `バニラ` is 8 bytes / 30 px, `むずかしい` 10 / 50 px, `エキスパート` 11 / 60 px, and `インセイン` 10 / 50 px. The first two could fit their current slots; the latter two require relocation with the present wording. The NEW GAME choice starts at x=19 tiles on a 30-tile GBA screen, leaving nominally 88 px before border/padding; this is **not** a proven text-width budget and does not establish the Options layout. A Japanese test ROM must verify both menus, all four choices, and each buffered confirmation. Keep `[latin][buffer1][japanese]` around dynamically inserted text until the chosen literal/page behavior is tested.

If the user's English observation includes only the four menu choices or the held confirmations, Phase 5B status explains it. If the exact puzzle/battle prompt sentences above are also English in the loaded Phase 5B ROM, that conflicts with the source-slot bytes (both already decode as Japanese); another runtime path, build, or save-state context must be identified from a screenshot/exact wording. No assumption is made yet.

## The 37 technical holds

- **20 fixed/no-relocation overflows:** 11 type names plus 9 other rigid UI/battle/one Pokédex species slots. Example `tbl_type_names_00000_A4EAD4` needs 9 encoded bytes in 7. Do not truncate official terms or omit page controls on the assumption that a shared renderer is already Japanese. They stay English until a complete approved in-slot wording or proven table/renderer change exists.
- **7 move-description pixel overflows:** measured Japanese lines are 138–160 px against a 122 px budget, although encoded bytes fit slots. `004_controlfix_translations.py` currently selects character-count wrapping for `ja` before the category pixel-width branch, so this is a mechanical layout issue to test/fix separately; do not approve these seven solely from byte fit.
- **6 Pokédex category suffix holds:** byte slots appear adequate, but whether Unbound adds `ポケモン` separately has not been established. Retain original wording until the Unbound renderer path is traced or photographed.
- **4 incomplete-pointer holds:** `scr_1A6211` has 14 additional exact pointers, each preceded by script message opcode `0x67` (strong structural owners); `tbl_ability_descriptions_00000_24F3C4` has aligned adjacent-table pointer `0x0024FB08`; `tbl_battle_messages_00000_800880` has two matching structured-bank candidates `0x00FA6636`, `0x00FA6C32`; `tbl_battle_messages_00002_965C16` has one `0x0096552F`. The last four pointer fields still need consumer/table proof. Do not relocate any of these four entries using the incomplete lists.

## The 116 context holds

The handoff includes all 116 originals, review reasons/candidates, exact pointer bytes, adjacent pointer-owned text (marked **proximity only**), buffer tokens, and protected controls. **112** are plausible translation-context requests; **2** have unverified leading bytes (`scr_7A95BA`, `scr_750C28`); **1** is the now-corrected duplicate Options warning whose *old* review ID must be migrated; **1** (`scr_1080302`) looks like non-text and must not be translated before extraction proof. Exact raw pointer matches beyond recorded owners occur for 22 entries (112 extra matches total); raw matches do not all establish consumers.

Known context clarified from the ROM:

- `scr_1F10323` `[buffer1]` is the selected difficulty literal via the route above.
- `tbl_mission_log_00017_1F560DA` `[buffer1]` is a map/location name, from the mission-field lookup traced in `docs/ja-phase4-reviewed.md` (ROM `0x01EC0064`, table `0x003F1CAC`, output RAM `0x02021CD0`).
- In `scr_1F9FBCD`, `scr_1F9EAF1`, `scr_1F9F08F`, “Black [player]” is a gang name containing the protagonist's name: the narrative explicitly renames Black Emboar after the protagonist in `scr_1F9D8D9` (ROM `0x01F9D8D9`), `scr_7E9D68` (`0x007E9D68`), `scr_7EA26A` (`0x007EA26A`), and `scr_1F9DBD7` (`0x01F9DBD7`). Preserve `[player]` inside the organization name.
- `scr_74AE91` self-identifies the speaker as Zeph. A map/event location for this entry, and speakers/actual map coordinates for the other script rows, are **not** proven by nearby ROM text. The handoff explicitly records unknown instead of inventing continuity.

No fresh Claude-reviewed 116-row translation file is present in this handoff. Give Claude `out/ja-phase5c-needs-context-for-claude.json` and the difficulty audit, require one status/wording per source ID while preserving token sequences, and leave ambiguous or suspect rows held. After receiving that reviewed file: validate IDs, controls, kana encodability and approved names; merge only confirmed rows; run controlfix twice for idempotency; strict injector dry-run; build a new private ROM; audit every in-place byte, relocation destination, and pointer write; then mGBA-test the NEW GAME difficulty branches. Phase 5B ROM and translation files are not overwritten.
