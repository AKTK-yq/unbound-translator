#!/usr/bin/env python3
"""Collect evidence for Phase 5B technical holds and 116 context requests.

This produces review material only. ROM bytes, translations, and glossary stay
unchanged. Byte-neighbor evidence never claims a speaker or map by itself.
"""

from __future__ import annotations

import argparse
from bisect import bisect_left
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib.pcs_text import Charmap, decode_pcs
from lib.gen3_font import text_pixel_width
from lib.translation_tokens import strip_hma_quotes


EXPECTED_MD5 = "9cad8e771940e7f7094d13911552cef0"
SUSPECTED_NON_TEXT = {"scr_1080302"}
UNVERIFIED_PREFIX = {"scr_7A95BA", "scr_750C28"}
CLIPPED_OPTIONS_WARNING = "tbl_menu_game_settings_00000_1F4E274"
BUFFER_TOKEN = re.compile(r"\[buffer[1-3]\]|\[player\]|\[rival\]")
SELF_ID = re.compile(r"\bI am ([A-Z][a-z]+)\b")
SPEAKER_PREFIX = re.compile(r"^\s*([A-Z][A-Za-z'-]{1,24}):")
BLACK_PLAYER_MISSION_IDS = {
    "scr_1F9FBCD", "scr_1F9EAF1", "scr_1F9F08F",
}
BLACK_PLAYER_NAME_EVIDENCE = {
    "source_ids": ["scr_1F9D8D9", "scr_7E9D68", "scr_7EA26A", "scr_1F9DBD7"],
    "source_rom_offsets": ["0x01F9D8D9", "0x007E9D68", "0x007EA26A", "0x01F9DBD7"],
    "conclusion": "Black Emboar is renamed Black [player] after the protagonist; [player] is the protagonist name embedded in the gang name",
    "limit": "Narrative and exact token evidence; does not identify the script opcode that populates the runtime buffer or a specific map coordinate",
}
KNOWN_BUFFER_PRODUCERS = {
    "scr_1F10323": {
        "producer_rom_offset": "0x01EC78B8",
        "call_rom_offset": "0x01E6FEC4",
        "output_ram": "0x02021CD0",
        "source": "variable 0x50DF selects Difficult/Vanilla/Expert table at 0x01FB54CC; Insane fallback at 0x01EC78E4",
        "evidence": "Thumb routine literals and call instruction in source ROM; docs/ja-phase4-reviewed.md",
    },
    "tbl_mission_log_00017_1F560DA": {
        "producer_rom_offset": "0x01EC0064",
        "output_ram": "0x02021CD0",
        "source": "mission-field map/location lookup via ROM 0x003F1CAC",
        "evidence": "ROM trace documented in docs/ja-phase4-reviewed.md; not a person or mission title",
    },
}
DIFFICULTY_ROLES = {
    "tbl_setting_names_00014_1F4DC09": "Options puzzle difficulty setting label",
    "tbl_menu_game_settings_00018_1F4DE12": "Options puzzle difficulty help text",
    "tbl_setting_names_00013_1F4DB23": "Options battle difficulty setting label",
    "tbl_menu_game_settings_00035_1F4E037": "Options battle difficulty help text",
    "scr_1F4E26F": "Options difficulty-reduction warning, branch A, complete old script duplicate",
    "tbl_menu_game_settings_00001_1F4E328": "Options difficulty-reduction warning, branch B",
    "tbl_menu_game_settings_00002_1F4E3CB": "Options puzzle change notice",
    "tbl_menu_game_settings_00003_1F4E454": "Options Cube Space puzzle change notice",
    "scr_1F0FC3F": "recommended difficulty dialogue with buffer1",
    "scr_1F0FD05": "Expert recommendation dialogue",
    "scr_1F0FE27": "puzzle difficulty prompt/title",
    "scr_1F0FE8E": "puzzle difficulty confirmation with buffer1",
    "scr_1F0FF35": "battle difficulty prompt/title",
    "scr_1F0FFA4": "Difficult confirmation and explanation",
    "scr_1F100B9": "Expert confirmation and explanation",
    "scr_1F101AC": "Insane confirmation and warning",
    "scr_1F10323": "normal NEW GAME difficulty result with buffer1",
    "scr_1F103AA": "NEW GAME plus difficulty result with buffer1",
    "scr_1F10621": "Difficult choice and buffer source",
    "scr_1F10630": "Vanilla choice and buffer source",
    "scr_1F1063D": "Expert choice and buffer source",
    "scr_1F10644": "Insane choice and buffer fallback",
    "scr_1F1062B": "Easy puzzle choice",
    "scr_1F10638": "Hard puzzle choice",
    "scr_1F1064B": "Challenging puzzle choice and buffer source",
    "scr_1F10657": "Back choice",
}
DIFFICULTY_BUDGET_EXAMPLES = {
    "scr_1F10621": "むずかしい",
    "scr_1F10630": "バニラ",
    "scr_1F1063D": "エキスパート",
    "scr_1F10644": "インセイン",
}


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, payload):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_offset(value):
    return int(value, 16) if isinstance(value, str) else int(value)


def exact_pointer_references(rom, target):
    needle = (0x08000000 + target).to_bytes(4, "little")
    refs = []
    at = 0
    while (at := rom.find(needle, at)) != -1:
        refs.append(at)
        at += 1
    return refs


def operand_kind(rom, owner):
    if owner >= 2 and rom[owner - 2] == 0x0F and rom[owner - 1] <= 3:
        return f"loadpointer {rom[owner - 1]} operand"
    if owner >= 2 and rom[owner - 2] == 0x85 and rom[owner - 1] <= 2:
        return f"bufferstring {rom[owner - 1]} operand"
    if owner >= 1 and rom[owner - 1] == 0x67:
        return "message opcode 0x67 operand"
    if owner % 4 == 0:
        return "aligned pointer field; consumer unproven"
    return "unaligned pointer field; consumer unproven"


def pointer_evidence(rom, selection_row):
    target = int(selection_row["rom_offset"])
    expected = (0x08000000 + target).to_bytes(4, "little")
    owners = [parse_offset(value) for value in selection_row["pointer_owners"]]
    records = []
    for owner in owners:
        if rom[owner:owner + 4] != expected:
            raise ValueError(f"Pointer owner byte mismatch: {selection_row['id']} at {owner:X}")
        records.append({"rom_offset": f"0x{owner:08X}",
                        "gba_address": f"0x{0x08000000 + owner:08X}",
                        "kind": operand_kind(rom, owner),
                        "surrounding_hex": rom[max(0, owner - 8):owner + 12].hex(" ")})
    refs = exact_pointer_references(rom, target) if owners else []
    extra = [ref for ref in refs if ref not in owners]
    return {"recorded_owner_count": len(owners), "recorded_owners": records,
            "all_exact_rom_pointer_count": len(refs) if owners else None,
            "additional_exact_pointer_offsets": [f"0x{ref:08X}" for ref in extra],
            "additional_exact_pointer_evidence": [
                {"rom_offset": f"0x{ref:08X}", "kind": operand_kind(rom, ref),
                 "surrounding_hex": rom[max(0, ref - 8):ref + 12].hex(" ")}
                for ref in extra
            ],
            "additional_pointer_caveat": "Raw 4-byte match; each extra reference needs structural proof"}


def make_owner_index(extracted):
    by_source = []
    for entry in extracted["entries"]:
        for value in entry.get("pointer_sources", []):
            by_source.append((parse_offset(value), entry["id"], strip_hma_quotes(entry["original"])))
    by_source.sort()
    return by_source, [item[0] for item in by_source]


def nearby_owned_texts(selection_row, index, offsets, radius=96, limit=8):
    found = []
    own = selection_row["id"]
    seen = set()
    for value in selection_row["pointer_owners"][:3]:
        owner = parse_offset(value)
        start = bisect_left(offsets, owner - radius)
        end = bisect_left(offsets, owner + radius + 1)
        for source, entry_id, original in index[start:end]:
            if entry_id == own or entry_id in seen:
                continue
            seen.add(entry_id)
            found.append({"id": entry_id, "pointer_source": f"0x{source:08X}",
                          "distance_from_owner": source - owner,
                          "original": original[:240]})
    found.sort(key=lambda row: abs(row["distance_from_owner"]))
    return found[:limit]


def buffer_evidence(original, entry_id):
    text = strip_hma_quotes(original)
    rows = []
    for match in BUFFER_TOKEN.finditer(text):
        known = KNOWN_BUFFER_PRODUCERS.get(entry_id) if match.group() == "[buffer1]" else None
        rows.append({"token": match.group(),
                     "surrounding_text": text[max(0, match.start() - 35):match.end() + 35],
                     "runtime_producer": known,
                     "note": "Proven producer above" if known else
                     "Producer unproven; adjacent wording is not sufficient"})
    return rows


def speaker_evidence(original, category):
    if category not in {"scripts", "plain_scripts", "pointer_texts"}:
        return {"speaker": None, "confidence": "not_applicable", "basis": "table/data entry"}
    text = strip_hma_quotes(original)
    match = SPEAKER_PREFIX.search(text)
    if match and match.group(1) != "???":
        return {"speaker": match.group(1), "confidence": "literal_label",
                "basis": "speaker label printed at start of this text"}
    match = SELF_ID.search(text)
    if match:
        return {"speaker": match.group(1), "confidence": "self_identified",
                "basis": "first-person self-identification within this text; earlier lines may differ"}
    return {"speaker": None, "confidence": "unknown",
            "basis": "pointer ownership and nearby ROM text do not identify the speaker"}


def place_evidence(row, map_names):
    category = row["category"]
    original = strip_hma_quotes(row["original"])
    if category == "map_names":
        return {"place": original, "confidence": "table_label", "basis": "map-name table entry, not event location"}
    if row["runtime_confidence"] == "A" and row["rom_offset"] >= 0x1F0F000:
        return {"place": "NEW GAME introduction", "confidence": "runtime_observed_flow",
                "basis": row["runtime_reason"]}
    mentions = [name for name in map_names if len(name) > 4 and name in original]
    return {"place": None, "confidence": "unknown", "basis": "map/event root not traced",
            "place_names_mentioned_not_location_proof": mentions[:10]}


def context_row(selection, review, rom, owner_index, owner_offsets, map_names):
    entry_id = selection["id"]
    original = selection["original"]
    source_correction = None
    if entry_id == CLIPPED_OPTIONS_WARNING:
        actual_offset = 0x01F4E26F
        actual_owner = 0x01EBD7FC
        decoded = decode_pcs(rom, actual_offset)
        if decoded.byte_length != 185 or rom[actual_owner:actual_owner + 4] != (
                0x08000000 + actual_offset).to_bytes(4, "little"):
            raise ValueError("Options warning extraction correction no longer matches ROM")
        source_correction = {"existing_complete_extracted_id": "scr_1F4E26F",
                             "actual_rom_offset": "0x01F4E26F",
                             "actual_gba_address": "0x09F4E26F", "actual_slot_size": 185,
                             "actual_pointer_owner": "0x01EBD7FC",
                             "actual_full_text": decoded.text,
                             "issue": "Old extraction contains the complete script entry and a duplicate manual entry starting five bytes late; the reviewed manual ID/original omit [red]WA"}
        triage = "review_id_migration_required"
    elif entry_id in SUSPECTED_NON_TEXT:
        triage = "suspected_non_text_do_not_translate"
    elif entry_id in UNVERIFIED_PREFIX:
        triage = "source_prefix_needs_byte_audit"
    else:
        triage = "translation_context_requested"
    buffers = buffer_evidence(original, entry_id)
    story_evidence = None
    if entry_id in BLACK_PLAYER_MISSION_IDS:
        story_evidence = BLACK_PLAYER_NAME_EVIDENCE
        for buffer in buffers:
            if buffer["token"] == "[player]":
                buffer["semantic_meaning"] = "protagonist name inside gang name Black [player]"
                buffer["semantic_evidence_ids"] = BLACK_PLAYER_NAME_EVIDENCE["source_ids"]
    return {"id": entry_id, "category": selection["category"],
            "original": original, "translation_source": selection["translation_source"],
            "review_status": "needs_context", "claude_reason": review["reason"],
            "previous_candidate_japanese": review.get("candidate_japanese"),
            "previous_reviewed_japanese": review.get("reviewed_japanese"),
            "review_warning": review.get("review_warning"),
            "rom_offset": f"0x{selection['rom_offset']:08X}",
            "gba_address": selection["gba_address"], "slot_size": selection["slot_size"],
            "table_name": selection.get("table_name"), "table_index": selection.get("table_index"),
            "runtime_confidence": selection["runtime_confidence"],
            "runtime_evidence": selection["runtime_reason"],
            "pointer_evidence": pointer_evidence(rom, selection),
            "nearby_owned_texts": nearby_owned_texts(selection, owner_index, owner_offsets),
            "nearby_text_caveat": "Same pointer-source byte neighborhood only; speaker, event, and map continuity unproven",
            "speaker_evidence": speaker_evidence(original, selection["category"]),
            "place_evidence": place_evidence(selection, map_names),
            "buffer_evidence": buffers,
            "story_evidence": story_evidence,
            "source_correction": source_correction,
            "protected_tokens": selection["protected_tokens"],
            "semantic_token_placeholders": selection["placeholders"],
            "controls": selection["controls"],
            "glossary_terms": selection["glossary_terms"],
            "rom_neighbor_before": selection["context_before"],
            "rom_neighbor_after": selection["context_after"],
            "rom_neighbor_caveat": selection["notes"],
            "triage": triage,
            "claude_instruction": (
                "Do not translate the clipped old ID; review the corrected full entry tbl_menu_game_settings_00000_1F4E26F separately"
                if triage == "review_id_migration_required" else
                "Do not translate until the extraction is verified" if triage != "translation_context_requested"
                else "Kana only; preserve all protected tokens; do not invent speaker, location, buffer meaning, or official proper names when evidence is absent. Return needs_context if still ambiguous"
            )}


def technical_row(selection, unresolved, rom):
    reason = unresolved["reason"]
    if reason == "fixed/no-relocation slot overflow":
        if selection["category"] == "type_names":
            recommendation = "Official type name cannot be shortened automatically; requires proven fixed-table/page-state or renderer strategy"
        else:
            recommendation = "Keep English until complete approved wording fits or a proven renderer/table strategy exists"
    elif reason == "known renderer-width budget exceeded":
        recommendation = "Re-wrap by measured Japanese glyph pixels before asking for shorter wording; validate line count and runtime UI"
    elif reason == "Pokédex category suffix behavior unverified":
        recommendation = "Trace Unbound Pokédex renderer suffix; never delete ポケモン by inference"
    else:
        recommendation = "Prove every additional pointer owner or keep original English; do not redirect only the extracted owner subset"
    return {"id": selection["id"], "category": selection["category"],
            "original": selection["original"], "rom_offset": f"0x{selection['rom_offset']:08X}",
            "gba_address": selection["gba_address"], "slot_size": selection["slot_size"],
            "reason": reason, "encoded_size": unresolved["encoded_size"],
            "pixel_width": unresolved["pixel_width"],
            "renderer_width": unresolved["renderer_width"],
            "relocatable": selection["relocatable"], "no_relocation": selection["no_relocation"],
            "pointer_evidence": pointer_evidence(rom, selection),
            "recommended_next_check": recommendation}


def difficulty_audit(extracted, selection, review, resolved, source_rom, phase5b_rom):
    """Report NEW GAME evidence; example kana are byte budgets, not approvals."""
    extracted_by_id = {row["id"]: row for row in extracted["entries"]}
    selected_by_id = {row["id"]: row for row in selection["entries"]}
    review_by_id = {row["id"]: row for row in review}
    resolved_by_id = {row["id"]: row for row in resolved["entries"]}
    cmap = Charmap("ja")
    entries = []
    for entry_id, role in DIFFICULTY_ROLES.items():
        source = extracted_by_id[entry_id]
        selected = selected_by_id.get(entry_id)
        offset = parse_offset(source["address"])
        slot = source["byte_length"]
        owned = selected or {"id": entry_id, "rom_offset": offset,
                             "pointer_owners": source["pointer_sources"]}
        pointers = pointer_evidence(source_rom, owned)
        review_row = review_by_id.get(entry_id)
        resolved_row = resolved_by_id.get(entry_id)
        example = DIFFICULTY_BUDGET_EXAMPLES.get(entry_id)
        budget = None
        if example:
            encoded = f"[japanese]{example}[latin]"
            budget = {"unapproved_example": example,
                      "encoded_size": len(cmap.encode(encoded)),
                      "pixel_width": text_pixel_width(encoded, cmap),
                      "fits_source_slot": len(cmap.encode(encoded)) <= slot}
        entries.append({"id": entry_id, "runtime_role": role,
                        "category": source["category"], "original": source["original"],
                        "rom_offset": f"0x{offset:08X}",
                        "gba_address": f"0x{0x08000000 + offset:08X}",
                        "slot_size": slot,
                        "selected_in_phase5a": selected is not None,
                        "phase5b_review_status": review_row["status"] if review_row else None,
                        "phase5b_review_reason": review_row.get("reason") if review_row else None,
                        "phase5b_translated": bool(resolved_row and resolved_row.get("translated")),
                        "phase5b_source_slot_unchanged":
                            source_rom[offset:offset + slot] == phase5b_rom[offset:offset + slot],
                        "fixed_slot": selected["fixed_slot"] if selected else None,
                        "relocatable": selected["relocatable"] if selected else None,
                        "pointer_evidence": pointers, "technical_budget_example": budget})

    # These byte signatures pin the claimed NEW GAME path to this exact ROM.
    anchors = {
        "options_puzzle_record": (0x01FB37B8, "09 dc f4 09 4c 3a fb 09 12 de f4 09"),
        "options_battle_record": (0x01FB3948, "23 db f4 09 18 3a fb 09 37 e0 f4 09"),
        "options_puzzle_first_two_choices": (0x01FB3A4C, "2b 06 f1 09 4b 06 f1 09"),
        "options_battle_four_choices": (0x01FB3A18, "30 06 f1 09 21 06 f1 09 3d 06 f1 09 44 06 f1 09"),
        "options_unextracted_warning_pointer": (0x01EBD7FC, "6f e2 f4 09"),
        "recommended_vanilla_bufferstring": (0x01E6FD0C, "85 00 30 06 f1 09"),
        "recommended_difficult_bufferstring": (0x01E6FCE9, "85 00 21 06 f1 09"),
        "puzzle_multichoice": (0x01E6FDD5, "6f 11 08 20 01"),
        "battle_multichoice": (0x01E6FE3F, "6f 13 05 22 01"),
        "result_buffer_routine_call": (0x01E6FEC4, "23 f5 78 ec 09"),
        "mode_name_table": (0x01FB54CC, "21 06 f1 09 30 06 f1 09 3d 06 f1 09"),
        "mode_name_fallback": (0x01EC78E4, "44 06 f1 09"),
    }
    anchor_rows = []
    for name, (offset, hex_bytes) in anchors.items():
        expected = bytes.fromhex(hex_bytes)
        if source_rom[offset:offset + len(expected)] != expected:
            raise ValueError(f"Difficulty runtime anchor mismatch: {name}")
        anchor_rows.append({"name": name, "rom_offset": f"0x{offset:08X}",
                            "gba_address": f"0x{0x08000000 + offset:08X}",
                            "bytes": hex_bytes})
    return {"metadata": {"phase": "5C-difficulty", "source_rom_md5": EXPECTED_MD5,
                         "policy": "Read-only evidence. Kana byte budgets are not approved translations."},
            "runtime_anchors": anchor_rows,
            "buffer1_result": {"routine_rom_offset": "0x01EC78B8",
                               "routine_gba_address": "0x09EC78B8",
                               "selector_variable": "0x50DF",
                               "pointer_table_rom_offset": "0x01FB54CC",
                               "fallback_entry": "scr_1F10644",
                               "destination_ram": "0x02021CD0",
                               "source_note": "Thumb disassembly and ROM literals; see docs/ja-phase4-reviewed.md"},
            "duplicate_clipped_options_warning": {
                "actual_rom_offset": "0x01F4E26F", "actual_gba_address": "0x09F4E26F",
                "actual_slot_size": 185, "actual_pointer_owner": "0x01EBD7FC",
                "existing_complete_extracted_id": "scr_1F4E26F",
                "incorrect_extracted_id": CLIPPED_OPTIONS_WARNING,
                "note": "Old extraction has both complete script and clipped manual duplicate. Corrected extraction has one complete menu_game_settings row; do not translate the clipped review row"},
            "alternative_non_new_game_labels": [
                "scr_A4ED04", "scr_A4ED0C", "scr_A4ED16", "scr_A4ED28", "scr_A4ED2F"],
            "options_record_layout": "three successive 32-bit pointers: setting label, choice pointer list, help description",
            "entries": entries}


def build(selection, review, unresolved, extracted, rom):
    if hashlib.md5(rom).hexdigest() != EXPECTED_MD5:
        raise ValueError("Source ROM MD5 mismatch")
    selected = {row["id"]: row for row in selection["entries"]}
    extracted_by_id = {row["id"]: row for row in extracted["entries"]}
    for evidence_id in BLACK_PLAYER_NAME_EVIDENCE["source_ids"]:
        evidence = extracted_by_id.get(evidence_id)
        if evidence is None or "Black [player]" not in evidence["original"]:
            raise ValueError(f"Gang-name evidence missing: {evidence_id}")
    needs = [row for row in review if row["status"] == "needs_context"]
    if len(needs) != 116 or len(unresolved["entries"]) != 37:
        raise ValueError("Phase 5B context/technical counts changed")
    owner_index, owner_offsets = make_owner_index(extracted)
    map_names = [strip_hma_quotes(row["original"]) for row in extracted["entries"]
                 if row["category"] == "map_names"]
    context = [context_row(selected[row["id"]], row, rom, owner_index, owner_offsets, map_names)
               for row in needs]
    technical = [technical_row(selected[row["id"]], row, rom)
                 for row in unresolved["entries"]]
    summary = {"context_count": len(context), "technical_count": len(technical),
               "context_by_category": dict(Counter(row["category"] for row in context)),
               "context_triage": dict(Counter(row["triage"] for row in context)),
               "technical_reasons": dict(Counter(row["reason"] for row in technical)),
               "proven_speaker_count": sum(row["speaker_evidence"]["confidence"] in
                                           {"literal_label", "self_identified"} for row in context),
               "proven_map_event_location_count": 0,
               "note": "Map labels and NEW GAME flow are not proof of NPC map coordinates"}
    return {"metadata": {"phase": "5C-context", "source_rom_md5": EXPECTED_MD5,
                         "selection_count": 750, "context_count": 116,
                         "policy": "Evidence handoff only; no translation or ROM changes"},
            "summary": summary, "entries": context}, {
                "metadata": {"phase": "5C-technical", "source_rom_md5": EXPECTED_MD5,
                             "technical_count": 37, "policy": "Analysis only; no automatic shortening"},
                "summary": summary, "entries": technical}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selection", default="tests/fixtures/ja_phase5_selection.json")
    parser.add_argument("--review", default="tests/fixtures/ja_phase5_claude_review.json")
    parser.add_argument("--unresolved", default="out/ja-phase5b-unresolved.json")
    parser.add_argument("--extracted", default="out/ja-phase5a-extracted.json")
    parser.add_argument("--rom", default="rom/unbound.gba")
    parser.add_argument("--phase5b-resolved", default="out/ja-phase5b-resolved.json")
    parser.add_argument("--phase5b-rom", default="out/unbound-ja-phase5b.gba")
    parser.add_argument("--context-output", default="out/ja-phase5c-needs-context-for-claude.json")
    parser.add_argument("--technical-output", default="out/ja-phase5c-technical-audit.json")
    parser.add_argument("--difficulty-output", default="out/ja-phase5c-difficulty-audit.json")
    args = parser.parse_args()
    selection = read_json(args.selection)
    review = read_json(args.review)
    extracted = read_json(args.extracted)
    source_rom = Path(args.rom).read_bytes()
    context, technical = build(selection, review, read_json(args.unresolved),
                               extracted, source_rom)
    difficulty = difficulty_audit(extracted, selection, review,
                                  read_json(args.phase5b_resolved), source_rom,
                                  Path(args.phase5b_rom).read_bytes())
    write_json(args.context_output, context)
    write_json(args.technical_output, technical)
    write_json(args.difficulty_output, difficulty)
    print(json.dumps(context["summary"], ensure_ascii=True, indent=2))
    print(f"context: {args.context_output}\ntechnical: {args.technical_output}"
          f"\ndifficulty: {args.difficulty_output}")


if __name__ == "__main__":
    main()
