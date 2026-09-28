#!/usr/bin/env python3
"""Audit the Batch 04 ROM and prepare runtime QA plus Batch 05 source-only handoffs."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.fa_control import parse_raw_segments
from lib.pcs_text import Charmap
from scripts.audit_ja_phase5b import compact_ranges
from scripts.build_ja_phase6_batch03_handoff import audit_rom, make_batch04_segmented
from scripts.build_ja_phase6_batch04 import BATTLE_HOLD, BATTLE_SAFE, FIELD_SAFE

OUT = ROOT / "out/phase6"
QA = ROOT / "tests/fixtures/ja_phase6_batch04_runtime_qa.json"
BATCH03_SHA256 = "535509572cf3f61951a58b6c700eea8ca669776bb9c596f890938405c1afdae3"
QA_SIZE = 36


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def audit_incremental(batch03_rom, batch04_rom, selected, reviewed, previous_map, current_map):
    before = Path(batch03_rom).read_bytes()
    after = Path(batch04_rom).read_bytes()
    if len(before) != len(after) or hashlib.sha256(before).hexdigest() != BATCH03_SHA256:
        raise ValueError("Batch 03 baseline differs")
    source_by_id = {row["id"]: row for row in selected}
    prior = {row["id"]: row for row in previous_map["relocations"]}
    current = {row["id"]: row for row in current_map["relocations"]}
    moved = {key for key in prior if key not in current or prior[key]["new_offset"] != current[key]["new_offset"]}
    new = set(current) - set(prior)
    allowed = {"new_in_place_text": set(), "relocation_destination_changes": set(),
               "pointer_destination_changes": set()}
    for row in reviewed["entries"]:
        if row["apply"] and row["id"] not in current:
            source = source_by_id[row["id"]]
            allowed["new_in_place_text"].update(range(source["rom_offset"], source["rom_offset"] + source["slot_size"]))
    for key in moved | new:
        for relocation in (prior.get(key), current.get(key)):
            if not relocation:
                continue
            start = int(relocation["new_offset"], 16)
            allowed["relocation_destination_changes"].update(range(start, start + relocation["byte_length"]))
            for owner in relocation["pointer_sources"]:
                location = int(owner, 16)
                allowed["pointer_destination_changes"].update(range(location, location + 4))
    changed = {i for i, pair in enumerate(zip(before, after)) if pair[0] != pair[1]}
    unexpected = changed - set().union(*allowed.values())
    if unexpected:
        raise ValueError(f"Unexpected Batch 03-to-04 difference: {compact_ranges(sorted(unexpected)[:100])}")
    return {"status": "PASS", "batch03_sha256": hashlib.sha256(before).hexdigest(),
            "batch04_sha256": hashlib.sha256(after).hexdigest(),
            "new_entry_count": sum(row["apply"] for row in reviewed["entries"]),
            "new_relocation_count": len(new), "new_relocation_ids": sorted(new),
            "moved_baseline_relocation_count": len(moved),
            "changed_byte_count": len(changed), "changed_ranges": compact_ranges(changed),
            "classified_changed_bytes": {k: len(changed & v) for k, v in allowed.items()},
            "unexpected_byte_count": 0}


def verify_fa_invariant(fa_audit, controlfixed, injection_map):
    fixed = {row["id"]: row for row in controlfixed["entries"]}
    relocated = {row["id"]: row for row in injection_map["relocations"]}
    codec = Charmap("ja")
    rows = []
    for row in fa_audit["entries"]:
        if not row["apply"]:
            continue
        output = parse_raw_segments(codec.encode(fixed[row["id"]]["translated"]))
        controls = [s["after_control"] for s in output if s["after_control"]]
        if (controls != row["source_controls"] or len(output) != len(row["source_segments"])
                or controls.count("FA") != row["FA_count"] or row["layout_status"] != "LAYOUT_PASS"):
            raise ValueError(f"FA source/output invariant failed: {row['id']}")
        rows.append({"id": row["id"], "source_controls": row["source_controls"], "output_controls": controls,
                     "segment_count": len(output), "fa_count": controls.count("FA"),
                     "fa_added": 0, "fa_removed": 0, "fa_moved": 0, "segment_merge": 0, "segment_split": 0,
                     "placement": "relocated" if row["id"] in relocated else "in_place",
                     "status": "PASS"})
    if len(rows) != fa_audit["metadata"]["applied_count"]:
        raise ValueError("FA invariant count differs from applied FA")
    return {"status": "PASS", "applied_count": len(rows), "error_count": 0, "entries": rows}


def make_qa(selection, reviewed, controlfixed, injection_map, names, fa_audit):
    source_by_id = {row["id"]: row for row in selection}
    fixed = {row["id"]: row for row in controlfixed["entries"]}
    relocated = {row["id"] for row in injection_map["relocations"]}
    rows = reviewed["entries"]
    safe = [r for r in rows if r["apply"]]
    verified_ids = {n["entry_id"] for n in names["entries"] if n["verification_result"] == "verified_exact"}
    chosen, used = [], set()

    def add(candidates, focus, maximum):
        for row in candidates:
            if maximum <= 0 or len(chosen) >= QA_SIZE:
                break
            if row["id"] not in used:
                chosen.append((row, focus))
                used.add(row["id"])
                maximum -= 1

    fa_rows = [r for r in safe if r["fa_segmented"]]
    add([r for r in fa_rows if r["source_boundary_sequence"].count("FA") > 1], "FA_multi_scroll", 4)
    long_ids = {seg["id"] for seg in fa_audit["long_segments"]}
    add([r for r in fa_rows if r["id"] in long_ids], "FA_long_segment", 2)
    add(fa_rows, "FA_button_scroll_and_page_state", 4)
    add([r for r in safe if r["id"] in relocated], "relocated_text_and_pointer", 2)
    add([r for r in safe if r["id"] in verified_ids], "pokeapi_verified_name", 4)
    add([r for r in safe if r["buffer_result"]["field_tokens"]], "player_or_rival_buffer", 4)
    add([r for r in safe if r["category"] == "mission_objectives"], "mission_objective_ui", 3)
    add([r for r in safe if r["category"] == "mission_descriptions"], "mission_description_ui", 3)
    add([r for r in safe if r["slot_size"] <= 16], "short_slot_width", 2)
    add([r for r in rows if r["category"] == "battle_messages" and not r["apply"]
         and r["buffer_result"]["battle_safe"]], "held_english_regression_battle_status", 2)
    add([r for r in rows if r["review_status"] == "existing_glossary" and not r["apply"]],
        "held_english_regression_route_template_sign", 2)
    add(safe, "general_story_dialogue", QA_SIZE - len(chosen))
    if len(chosen) != QA_SIZE:
        raise ValueError("Cannot choose Batch 04 QA entries")
    entries = []
    for priority, (row, focus) in enumerate(chosen, 1):
        source = source_by_id[row["id"]]
        entries.append({
            "priority": priority, "id": row["id"], "category": source["category"],
            "rom_offset": f"0x{source['rom_offset']:08X}", "gba_address": source["gba_address"],
            "pointer_owners": source["pointer_owners"], "original": source["original"],
            "expected_japanese": fixed[row["id"]]["translated"] if row["apply"] else None,
            "expected_display": "Japanese" if row["apply"] else "English (held)",
            "test_focus": focus,
            "placement": ("relocated" if row["id"] in relocated else "in_place") if row["apply"] else "held_english",
            "controls": source["controls"], "buffers": source["buffers"],
            "renderer_group": source["renderer_group"],
            "conversation_id": source.get("conversation_id"), "scene_id": source.get("scene_id"),
            "route": "Exact map/event caller not proven; locate with progressed save or script trace",
            "route_confidence": "unverified", "runtime_result": "not_human_tested"})
    return {"metadata": {"phase": "6B-4", "count": QA_SIZE,
                         "focus_counts": dict(Counter(e["test_focus"] for e in entries)),
                         "limitation": "Static ROM and pointer checks pass; no mGBA route or displayed layout is asserted."},
            "entries": entries}


def make_style(previous, names, fa_invariant, fa_audit, reviewed):
    if fa_invariant["status"] != "PASS":
        raise ValueError("Batch 04 FA gate failed")
    return {
        **previous,
        "phase": "6B-4-to-6B-5", "status": "guidance_only_batch05_not_translated",
        "batch05_gate": "STATIC_GO_SEGMENTED_INPUT_ONLY",
        "gate_reason": (f"{fa_invariant['applied_count']} Batch 04 FA entries pass segmented reconstruction, "
                        "static layout and strict ROM audit; mGBA runtime remains unverified. Ambiguous FA remains held."),
        "fa_translation_input": "out/phase6/ja_phase6_batch05_fa_segmented_input.json",
        "fa_segment_length_guidance": ("Each FA segment is one rendered line with no automatic wrap. "
                                       "Keep a segment within about 18-20 kana (<=208px measured); longer segments are held."),
        "official_name_rule": ("Provisional Japanese may be proposed only with official_name_verification_required; "
                               "Codex applies a name only after exact English PokeAPI ja-hrkt match. Plurals, "
                               "line-wrapped terms and non-PokeAPI franchise terms (facilities, classes, regions, "
                               "features) are not verified and hold the entry."),
        "official_name_results": names["metadata"]["result_counts"],
        "battle_buffer_rule": {
            "engine_defined_types": BATTLE_SAFE, "hold": BATTLE_HOLD,
            "evidence": "pret/pokefirered include/battle_message.h B_TXT_* constants; CFRU codes above 0x30 are unverified",
            "width_note": ("Vanilla FireRed B_WIN_MSG is 28 tiles, but the Unbound/CFRU battle window and "
                           "NAME_WITH_PREFIX expansion width are unproved; Batch 04 battle messages stayed English on width.")},
        "field_buffer_rule": {"safe": FIELD_SAFE, "hold": "Any [bufferN] without a traced writer and value set"},
        "mission_title_rule": "Mission titles: no spaces, proposal-only glossary; standalone mission_names entries are held until glossary approval.",
        "batch04_safe_applied": reviewed["metadata"]["safe_application_count"],
        "batch04_fa_applied": fa_invariant["applied_count"],
        "batch04_fa_layout_counts": fa_audit["metadata"]["layout_counts"],
        "known_bad_patterns": previous["known_bad_patterns"] + [
            "Provisional official names from memory applied without PokeAPI verification.",
            "Plural or line-wrapped English item names treated as exact PokeAPI matches.",
            "FA segments longer than the rendered line (>208px) treated as layout-safe.",
            "Battle NAME_WITH_PREFIX width assumed from the 54px buffer estimate."],
    }


def main():
    batch_ids = {row["id"] for row in read(OUT / "ja_phase6_batch04_for_claude.json")["entries"]}
    selected = [row for row in read(ROOT / "tests/fixtures/ja_phase6_selection.json")["entries"] if row["id"] in batch_ids]
    reviewed = read(OUT / "ja_phase6_batch04_reviewed.json")
    fixed = read(OUT / "ja_phase6_batch04_controlfix.json")
    injection_map = read(OUT / "ja_phase6_batch04_map.json")
    source_rom = ROOT / "rom/unbound.gba"
    output_rom = ROOT / "out/unbound-ja-phase6-batch04.gba"
    audit = audit_rom(source_rom, output_rom, fixed, injection_map)
    incremental = audit_incremental(ROOT / "out/unbound-ja-phase6-batch03.gba", output_rom, selected, reviewed,
                                    read(OUT / "ja_phase6_batch03_map.json"), injection_map)
    fa_audit = read(OUT / "ja_phase6_batch04_fa_audit.json")
    fa_invariant = verify_fa_invariant(fa_audit, fixed, injection_map)
    placements = {row["id"]: row["placement"] for row in fa_invariant["entries"]}
    for row in fa_audit["entries"]:
        row["rom_placement"] = placements.get(row["id"], "held_english")
    names = read(OUT / "ja_phase6_batch04_official_name_audit.json")
    qa = make_qa(selected, reviewed, fixed, injection_map, names, fa_audit)
    batch05 = make_batch04_segmented(read(OUT / "ja_phase6_batch05_for_claude.json"), source_rom.read_bytes())
    style = make_style(read(OUT / "ja_phase6_batch04_style_handoff.json"), names, fa_invariant, fa_audit, reviewed)
    write(OUT / "ja_phase6_batch04_rom_audit.json", audit)
    write(OUT / "ja_phase6_batch04_incremental_audit.json", incremental)
    write(OUT / "ja_phase6_batch04_fa_invariant.json", fa_invariant)
    write(OUT / "ja_phase6_batch04_fa_audit.json", fa_audit)
    write(QA, qa)
    write(OUT / "ja_phase6_batch05_fa_segmented_input.json", batch05)
    write(OUT / "ja_phase6_batch05_style_handoff.json", style)
    print({"rom_audit": audit["status"], "changed_bytes": audit["changed_byte_count"],
           "classified": audit["classified_changed_bytes"], "entry_counts": audit["entry_counts"],
           "incremental": incremental["status"], "incremental_bytes": incremental["changed_byte_count"],
           "incremental_classified": incremental["classified_changed_bytes"],
           "new_relocations": incremental["new_relocation_ids"],
           "moved": incremental["moved_baseline_relocation_count"],
           "fa_invariant": fa_invariant["applied_count"], "runtime_qa": len(qa["entries"]),
           "qa_focus": qa["metadata"]["focus_counts"],
           "batch05_entries": len(batch05["entries"]), "batch05_fa": batch05["metadata"]["fa_annotated_entries"]})


if __name__ == "__main__":
    main()
