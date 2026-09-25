#!/usr/bin/env python3
"""Read-only ROM-backed triage of the 44 Phase 5E held Japanese entries."""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib.pcs_text import Charmap
from lib.translation_tokens import strip_hma_quotes


ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {"A": 4, "B": 16, "C": 10, "D": 2, "E": 3, "F": 8, "H": 1}
DAY_START = 0xA4E554
DAY_PTR_START = 0xA6D0AC
FORM_TABLE_START = 0x1A35450
FORM_TABLE_COUNT = 22
POKEMON_NAMES_START = 0x166A98C


def load(path: str):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def save(path: str, data):
    (ROOT / path).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def word(rom: bytes, offset: int) -> int:
    return int.from_bytes(rom[offset:offset + 4], "little")


def main():
    held = load("out/ja-phase5e-remaining-context.json")["entries"]
    review = {row["id"]: row for row in load("tests/fixtures/ja_phase5c_claude_review.json")}
    old = {row["id"]: row for row in load("out/ja-phase5e-extracted.json")["entries"]}
    fresh = {row["id"]: row for row in load("out/ja-phase5f-extracted.json")["entries"]}
    rom = (ROOT / "rom/unbound.gba").read_bytes()
    counts = Counter(row["technical_classification"] for row in held)
    assert len(held) == 44 and dict(counts) == EXPECTED
    assert len({row["id"] for row in held}) == 44
    assert len(old) == len(fresh) == 25044 and old.keys() == fresh.keys()

    audited = []
    for row in held:
        identifier = row["id"]
        extracted = fresh.get(identifier)
        old_entry = old.get(identifier)
        if extracted is None:
            # Phase 5C already removed this clipped, ownerless difficulty
            # warning. Retain it in the 44-row triage ledger for accounting.
            assert identifier == "tbl_menu_game_settings_00000_1F4E274"
            source = row["evidence"][0]
            extracted = {"category": row["category"], "original": review[identifier]["original"],
                         "address": source["source_rom_offset"], "byte_length": None,
                         "pointer_sources": []}
        address = int(extracted["address"], 16)
        classification = row["technical_classification"]
        assert extracted["category"] == row["category"]
        if "original" in row["evidence"][0]:
            assert extracted["original"] == row["evidence"][0]["original"]
        item = {
            "id": identifier,
            "category": extracted["category"],
            "original": extracted["original"],
            "classification": classification,
            "current_reason": row["reason"],
            "current_translation_status": row["resolution_status"],
            "rom_offset": extracted["address"],
            "gba_address": f"0x{0x08000000 + address:08X}",
            "slot_size": extracted["byte_length"],
            "pointer_sources": extracted["pointer_sources"],
            "owner_delta": sorted(set(extracted["pointer_sources"]) - set(old_entry["pointer_sources"])) if old_entry else [],
            "evidence": [],
            "disposition": "held_english",
        }
        evidence = item["evidence"]
        if classification == "A":
            if extracted["category"] == "credits_text":
                item["disposition"] = "resolved_keep_latin_staff_name"
                encoded = Charmap("ja").encode(strip_hma_quotes(extracted["original"]))
                source_bytes = rom[address:address + extracted["byte_length"]]
                evidence.append({"credit_staff_names": True,
                                 "raw_source_hex": source_bytes.hex(" "),
                                 "roundtrip_encoded_hex": encoded.hex(" "),
                                 "source_byte_length": len(source_bytes),
                                 "roundtrip_byte_length": len(encoded),
                                 "reason_for_difference": "raw consecutive FE newlines collapse to FB when encoded from decoded text",
                                 "action": "keep original ROM bytes and Latin names; do not reinject"})
            else:
                item["disposition"] = "resolved_exclude_clipped_duplicate"
                evidence.append("The complete owned warning at 0x1F4E26F was already translated in Phase 5C; this clipped row has no owner.")
        elif classification == "B":
            if extracted["category"] == "gendered_dialogue_fragments":
                script_operands = []
                for source_hex in extracted["pointer_sources"]:
                    source = int(source_hex, 16)
                    if rom[source - 2] == 0x85 and rom[source - 1] <= 2:
                        script_operands.append({"pointer_source": source_hex,
                                                "opcode": "bufferstring 0x85",
                                                "buffer_index": rom[source - 1]})
                if script_operands:
                    evidence.append({"direct_bufferstring_operands": script_operands,
                                     "limit": "Writer/source string proven; insertion sentence and complete runtime values not proven."})
                else:
                    evidence.append("Structured/manual owner only; buffer assignment and insertion sentence unproven.")
            elif identifier == "scr_1F1A99A":
                for source, target in ((0x1E74C91, 0x1F1A9C6),
                                       (0x1E74CBB, 0x1F1A9C9)):
                    assert rom[source - 2:source] == b"\x85\x00"
                    assert word(rom, source) == 0x08000000 + target
                evidence.append({"buffer_index": 0, "writer": "bufferstring 0x85 00",
                                 "source_data": [{"value": "on", "rom_offset": "0x1F1A9C6", "pointer_source": "0x1E74C91"},
                                                 {"value": "off", "rom_offset": "0x1F1A9C9", "pointer_source": "0x1E74CBB"}],
                                 "value_type": "literal Latin on/off", "actual_values_proven": True,
                                 "limit": "Same local script block; control-flow relation to dialogue and all repeated owners still need tracing."})
            elif extracted["category"] == "battle_messages":
                evidence.append("Battle grammar operand is not an FD script buffer; writer and all dynamic values not proven.")
            else:
                evidence.append("FD dynamic buffer in script text; writer and all possible values not proven.")
        elif classification == "C":
            if extracted["category"] == "day_names":
                index = extracted["table_index"]
                source = DAY_PTR_START + index * 4
                assert address == DAY_START + index * 4
                assert word(rom, source) == 0x08000000 + address
                assert extracted["pointer_sources"] == [f"0x{source:X}"]
                assert extracted.get("no_relocation") is True
                evidence.append({"owner_type": "direct 32-bit pointer table", "pointer_source": f"0x{source:X}",
                                 "table_rom_range": "0xA6D0AC-0xA6D0C7", "fixed_stride": 4,
                                 "relocation_safe": False,
                                 "limit": "Computed fixed-stride references and display width remain unproven."})
            else:
                evidence.append({"owner_type": "fixed trainer record field", "record_stride": 40,
                                 "name_field_size": 12, "direct_per_name_pointer": False,
                                 "base_pointer_examples": ["0x114DD8", "0x115068", "0x12DF5C"],
                                 "relocation_safe": False,
                                 "limit": "Indexed table consumer and runtime use of these legacy names unproven."})
        elif classification == "D":
            prefix = rom[address:address + 12]
            evidence.append({"actual_raw_prefix_hex": prefix.hex(" "),
                             "first_raw_byte": f"0x{rom[address]:02X}",
                             "previous_raw_byte": f"0x{rom[address - 1]:02X}",
                             "reported_as_D1_or_C1_previously": "incorrect byte interpretation",
                             "limit": "Script operand is real, but special prefix semantics and safe interior start not proven."})
        elif classification == "E":
            if identifier == "scr_1F1057C":
                evidence.append({"actual_options_label": "Exp. Gain", "label_rom_offset": "0x1F4DB35",
                                 "label_pointer_source": "0x1FB3960",
                                 "choices": [{"text": "Exp. Share", "rom_offset": "0x1F4DC57", "owner": "0x1FB3A10"},
                                             {"text": "Capped Exp. Share", "rom_offset": "0x1F4DC62", "owner": "0x1FB3A14"}],
                                 "limit": "Help prose says Capped Share; screen wording/width requires visual approval."})
            elif extracted["category"] == "mission_log":
                evidence.append("A-Z is a sort/UI label; whether comparison uses displayed bytes is unproven.")
            else:
                evidence.append("Color controls surround English critical-hit phrase; Japanese grammar may alter color span.")
        elif classification == "F":
            if extracted["category"] == "pokedex_form_names":
                records = []
                for index in range(FORM_TABLE_COUNT):
                    record = FORM_TABLE_START + index * 8
                    if word(rom, record) != 0x08000000 + address:
                        continue
                    number = int.from_bytes(rom[record + 4:record + 6], "little")
                    name_offset = POKEMON_NAMES_START + number * 11
                    records.append({"record_rom_offset": f"0x{record:X}", "u16_index": number,
                                    "pokemon_name_rom_offset": f"0x{name_offset:X}"})
                evidence.append({"form_table_records": records,
                                 "limit": "u16 relation proven; form/species display semantics not proven, especially shared names."})
            elif identifier == "scr_1F0F842":
                evidence.append("NEW GAME appearance sequence after jacket; trim could mean edge/secondary garment color. Visual screen required.")
            elif identifier == "tbl_menu_list_labels_00005_4178FD":
                evidence.append("Menu list label near EGGS/QUIT/HALL OF FAME; destination/number meaning not proven.")
            else:
                evidence.append("Reused script name label with 14 pointer owners; person/nickname spelling not proven.")
        else:
            assert classification == "H"
            assert address == 0x1080302
            evidence.append({"pointer_sources": extracted["pointer_sources"],
                             "source_bytes_match_pointer": all(word(rom, int(source, 16)) == 0x09080302
                                                               for source in extracted["pointer_sources"]),
                             "target_prefix_hex": rom[address:address + 32].hex(" "),
                             "limit": "No renderer consumer proven; exclude from translation, but do not remove extractor row without owner/data proof."})
        audited.append(item)

    assert Counter(item["classification"] for item in audited) == counts
    assert sum(bool(item["owner_delta"]) for item in audited) == 5
    result = {"phase": "5F", "total": len(audited), "classification_counts": dict(counts),
              "resolved_disposition_count": sum(item["disposition"].startswith("resolved_") for item in audited),
              "new_japanese_translation_count": 0, "day_owner_metadata_resolved_count": 5,
              "entries": audited}
    save("out/ja-phase5f-remaining-audit.json", result)

    bulb = next(item for item in audited if item["id"] == "scr_1F1A99A")
    old_candidate = review[bulb["id"]]
    handoff = {"phase": "5F", "purpose": "Wording review only; do not inject without buffer/control-flow validation",
               "entries": [{"id": bulb["id"], "original": bulb["original"],
                            "old_candidate": old_candidate["candidate_japanese"],
                            "newly_discovered_context": bulb["evidence"],
                            "buffer_meaning": "buffer1 is assigned literal on/off by nearby script operands",
                            "speaker": "system/object interaction; not a person",
                            "runtime_use": "Bulb interaction, exact event reachability not verified in emulator",
                            "glossary_terms": [],
                            "technical_constraints": "Keep [green][buffer1][black], restore Latin around dynamic value; coordinate on/off translations and all owners."}]}
    save("out/ja-phase5f-for-claude.json", handoff)

    visual_ids = [item["id"] for item in audited if item["classification"] == "F"]
    visual_ids += ["scr_1F1057C", "tbl_battle_messages_00004_A4A9A2", "tbl_mission_log_00001_1F5604A"]
    cases = []
    for identifier in visual_ids:
        item = next(row for row in audited if row["id"] == identifier)
        route = {
            "scr_1F0F842": "NEW GAME > appearance selection > jacket then trim selector",
            "scr_1F1057C": "NEW GAME/options > Exp. Gain setting and level-cap explanation",
            "tbl_menu_list_labels_00005_4178FD": "Open relevant records/menu list; exact route needs a progressed save",
            "tbl_mission_log_00001_1F5604A": "Open Mission Log and its sort selector",
            "tbl_battle_messages_00004_A4A9A2": "Trigger a critical hit in battle",
        }.get(identifier, "Use a progressed save to locate this label; exact route not proven")
        width_check = item["category"] in {"menu_list_labels", "mission_log", "pokedex_form_names"} or identifier == "scr_1F1057C"
        cases.append({"id": identifier, "screen": item["category"], "how_to_reach": route,
                      "what_to_look_at": item["original"] + ("; check full label fits and is not clipped" if width_check else ""),
                      "ui_width_check": width_check, "screenshot_needed": True,
                      "possible_interpretations": item["evidence"],
                      "runtime_reachability_proven": False})
    cases.append({"id": "options_text_pacing", "screen": "Options help text", "how_to_reach": "Open Options and move between Text Speed, battle/puzzle help",
                  "what_to_look_at": "Record text display at each Text Speed setting with and without A/B; compare same help line in English baseline and Phase 5E ROM",
                  "screenshot_needed": False, "video_or_frame_capture_needed": True,
                  "possible_interpretations": ["per-glyph cadence", "page transition", "menu redraw or cursor animation"],
                  "runtime_reachability_proven": True})
    save("tests/fixtures/ja_phase5f_visual_qa.json",
         {"phase": "5F", "note": "Do not infer translation approval from this checklist", "cases": cases})
    print(f"44 audited: {dict(counts)}; 4 disposition-resolved, 5 day-owner metadata improved; 0 new translations; {len(cases)} visual cases")


if __name__ == "__main__":
    main()
