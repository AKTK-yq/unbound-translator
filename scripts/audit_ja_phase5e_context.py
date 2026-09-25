#!/usr/bin/env python3
"""Evidence-backed triage of the Phase 5D entries left in English."""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def write(path, data):
    (ROOT / path).write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def form_evidence(rom, entry, extracted):
    address = int(entry["address"], 16)
    records = []
    table = 0x1A35450
    for index in range(22):
        record = table + index * 8
        name_pointer = int.from_bytes(rom[record:record + 4], "little")
        if name_pointer != address + 0x08000000:
            continue
        species = int.from_bytes(rom[record + 4:record + 6], "little")
        species_name_address = 0x166A98C + species * 11
        species_name = next((row["original"] for row in extracted.values()
                             if row["category"] == "pokemon_names"
                             and int(row["address"], 16) == species_name_address), None)
        records.append({
            "record_rom_offset": f"0x{record:08X}",
            "species_id": species,
            "species_name": species_name,
            "species_name_rom_offset": f"0x{species_name_address:08X}",
        })
    return records


def classify(row):
    category = row["category"]
    entry_id = row["id"]
    if category == "pokedex_form_names":
        return "F", "Species mapping is proven, but form wording and in-game appearance need review."
    if entry_id in {"scr_1F0F842", "tbl_menu_list_labels_00005_4178FD", "scr_1FAE999"}:
        return "F", "Inspect the actual screen or speaker before approving Japanese wording."
    if category in {"day_names", "trainer_names"}:
        return "C", "Trace fixed-table consumer, index, and runtime use; do not infer from zero literal pointers."
    if category in {"gendered_dialogue_fragments", "battle_messages"} and entry_id != "tbl_battle_messages_00004_A4A9A2":
        return "B", "Trace the exact buffer producer and destination sentence before setting Japanese grammar."
    if entry_id in {"scr_74AE91", "scr_7527C2", "scr_753107", "scr_1F1A99A", "scr_75CDB8"}:
        return "B", "Trace setbuffer/bufferstring or script variable to each insertion site."
    if entry_id in {"scr_7A95BA", "scr_750C28"}:
        return "D", "Audit the leading byte and every interior/direct reference before changing extraction."
    if category == "credits_text":
        return "A", "Keep verified staff names in their original Latin spelling; no kana guess."
    if entry_id == "tbl_menu_game_settings_00000_1F4E274":
        return "A", "Exclude clipped duplicate; use already translated complete source 0x01F4E26F."
    if entry_id in {"scr_1F1057C", "tbl_battle_messages_00004_A4A9A2", "tbl_mission_log_00001_1F5604A"}:
        return "E", "Trace Options/help, color scope, or sort comparator before changing this structured UI text."
    if entry_id == "scr_1080302":
        return "H", "Prove a real text consumer and valid PCS byte boundaries; otherwise remove false extraction."
    raise ValueError(f"Unclassified context row: {entry_id}")


def main():
    recheck = read("out/ja-phase5d-needs-context-recheck.json")["entries"]
    remaining = [row for row in recheck if not row["ready_for_retranslation"]]
    if len(remaining) != 44 or sum(row["codex_technical_investigation"] for row in remaining) != 36:
        raise ValueError("Phase 5D context counts changed")
    extracted = {row["id"]: row for row in read("out/ja-phase5e-extracted.json")["entries"]}
    applied = {row["id"] for row in read("out/ja-phase5e-controlfix.json")["entries"]}
    rom = (ROOT / "rom/unbound.gba").read_bytes()
    rows = []
    for prior in remaining:
        entry_id = prior["id"]
        entry = extracted.get(entry_id)
        classification, next_action = classify(prior)
        if entry_id in applied:
            raise ValueError(f"Unresolved entry was translated: {entry_id}")
        evidence = []
        if entry:
            offset = int(entry["address"], 16)
            evidence.append({"kind": "extraction", "rom_offset": entry["address"],
                             "gba_address": f"0x{offset + 0x08000000:08X}",
                             "original": entry["original"],
                             "slot_size": entry["byte_length"],
                             "pointer_sources": entry["pointer_sources"],
                             "raw_prefix_hex": rom[offset:offset + min(16, entry["byte_length"])].hex(" ")})
            if classification == "F" and prior["category"] == "pokedex_form_names":
                evidence.append({"kind": "form_table_species_mapping",
                                 "table_rom_offset": "0x01A35450",
                                 "interpretation": "The second u16 indexes the species-name table; whether the renderer uses this as a direct form-to-species mapping is not proven.",
                                 "records": form_evidence(rom, entry, extracted)})
        else:
            if entry_id != "tbl_menu_game_settings_00000_1F4E274":
                raise ValueError(f"Missing extracted entry: {entry_id}")
            evidence.append({"kind": "clipped_duplicate",
                             "source_rom_offset": "0x01F4E274",
                             "complete_entry_id": "tbl_menu_game_settings_00000_1F4E26F",
                             "complete_rom_offset": "0x01F4E26F",
                             "complete_pointer_owner": "0x01EBD7FC"})
        if entry_id == "scr_1F1057C":
            evidence.append({"kind": "options_records", "labels": [
                {"text": "Exp. Gain", "rom_offset": "0x01F4DB35", "owner": "0x01FB3960"},
                {"text": "Exp. Share", "rom_offset": "0x01F4DC57", "owner": "0x01FB3A10"},
                {"text": "Capped Exp. Share", "rom_offset": "0x01F4DC62", "owner": "0x01FB3A14"},
            ], "observation": "Capped Share is prose shorthand, not the extracted choice label."})
        if entry_id == "scr_1FAE999":
            evidence.append({"kind": "script_reference", "count": len(entry["pointer_sources"]),
                             "observation": "Repeated script name label; person vs nickname still unproven."})
        if classification == "C":
            evidence.append({"kind": "fixed_table", "table_name": entry.get("table_name"),
                             "table_index": entry.get("table_index"),
                             "observation": "Zero literal pointer sources does not establish runtime deadness."})
        if classification == "D":
            evidence.append({"kind": "leading_byte", "byte": f"0x{rom[int(entry['address'], 16)]:02X}",
                             "observation": "Exact pointer metadata exists; cannot label this a clipped duplicate without consumer proof."})
        if classification == "H":
            evidence.append({"kind": "text_integrity", "observation":
                             "Control-heavy decoded string and high-entropy prefix; consumer unproven."})
        status = "confirmed_leave_english" if prior["category"] == "credits_text" else (
            "superseded_by_complete_entry" if entry_id == "tbl_menu_game_settings_00000_1F4E274" else "held_english")
        rows.append({
            "id": entry_id, "category": prior["category"],
            "reason": prior["previous_reason"], "technical_classification": classification,
            "evidence": evidence, "resolution_status": status,
            "claude_needed": classification in {"F", "G"} or entry_id == "scr_1F1057C",
            "human_visual_check_needed": classification == "F" or entry_id == "scr_1F1057C",
            "codex_investigation_possible": classification in {"B", "C", "D", "E", "H"},
            "recommended_next_action": next_action,
        })
    counts = dict(sorted(Counter(row["technical_classification"] for row in rows).items()))
    result = {"phase": "5E", "total": len(rows), "technical_input": 36,
              "visual_context_input": 8, "classification_counts": counts,
              "translated_from_remaining": 0, "entries": rows}
    write("out/ja-phase5e-remaining-context.json", result)
    print(f"Remaining context: {len(rows)}, classes {counts}")


if __name__ == "__main__":
    main()
