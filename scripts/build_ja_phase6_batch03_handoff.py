#!/usr/bin/env python3
"""Audit the Batch 03 ROM and prepare bounded runtime/source-only handoffs."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.fa_control import parse_raw_segments
from lib.pcs_text import Charmap
from scripts.audit_ja_phase5b import compact_ranges

OUT = ROOT / "out/phase6"
QA = ROOT / "tests/fixtures/ja_phase6_batch03_runtime_qa.json"
SOURCE_MD5 = "9cad8e771940e7f7094d13911552cef0"
BATCH02_SHA256 = "c7f71c87c644871f2e66c28a6258818ba3523441ff1726183b8340d44872f4a7"


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def audit_rom(source_rom, output_rom, controlfixed, injection_map):
    before = Path(source_rom).read_bytes()
    after = Path(output_rom).read_bytes()
    if len(before) != len(after) or hashlib.md5(before).hexdigest() != SOURCE_MD5:
        raise ValueError("Source ROM size or MD5 differs")
    relocations = {row["id"]: row for row in injection_map["relocations"]}
    injector = runpy.run_path(str(ROOT / "005_hybrid_injector.py"))
    codec = Charmap("ja")
    allowed = {"in_place_text": set(), "relocated_text": set(), "pointer_writes": set()}
    entry_counts = Counter()
    owner_count = 0
    for entry in controlfixed["entries"]:
        entry_id = entry["id"]
        encoded = injector["encode_text"](
            codec, injector["translation_for_injection"](entry),
            plain_script=entry["category"] == "plain_scripts")
        old = int(entry["address"], 16)
        slot = int(entry["byte_length"])
        relocation = relocations.get(entry_id)
        if relocation:
            destination = int(relocation["new_offset"], 16)
            if relocation["storage"] != "vetted_ff" or len(encoded) != relocation["byte_length"]:
                raise ValueError(f"Unvetted relocation or byte mismatch: {entry_id}")
            if after[destination:destination + len(encoded)] != encoded:
                raise ValueError(f"Relocated bytes do not match translation: {entry_id}")
            allowed["relocated_text"].update(range(destination, destination + len(encoded)))
            pointer = (0x08000000 + destination).to_bytes(4, "little")
            for owner in relocation["pointer_sources"]:
                location = int(owner, 16)
                if before[location:location + 4] != (0x08000000 + old).to_bytes(4, "little"):
                    raise ValueError(f"Stale source pointer: {entry_id} {owner}")
                if after[location:location + 4] != pointer:
                    raise ValueError(f"Wrong destination pointer: {entry_id} {owner}")
                allowed["pointer_writes"].update(range(location, location + 4))
                owner_count += 1
            entry_counts["relocated"] += 1
        else:
            if len(encoded) > slot or after[old:old + slot] != encoded.ljust(slot, b"\xff"):
                raise ValueError(f"In-place content or fit mismatch: {entry_id}")
            allowed["in_place_text"].update(range(old, old + slot))
            entry_counts["in_place"] += 1
    if owner_count != injection_map["stats"]["pointer_writes"]:
        raise ValueError("Pointer-write count differs from map")
    if any(allowed[a] & allowed[b] for a, b in
           (("in_place_text", "relocated_text"), ("in_place_text", "pointer_writes"),
            ("relocated_text", "pointer_writes"))):
        raise ValueError("Audit regions overlap")
    changed = {index for index, pair in enumerate(zip(before, after)) if pair[0] != pair[1]}
    unexpected = changed - set().union(*allowed.values())
    if unexpected:
        raise ValueError(f"Unexpected ROM differences: {compact_ranges(sorted(unexpected)[:100])}")
    categories = {key: changed & region for key, region in allowed.items()}
    return {
        "status": "PASS", "source_md5": hashlib.md5(before).hexdigest(),
        "source_sha256": hashlib.sha256(before).hexdigest(),
        "output_sha256": hashlib.sha256(after).hexdigest(),
        "output_bytes": len(after), "entry_counts": dict(entry_counts),
        "pointer_owner_writes": owner_count, "changed_byte_count": len(changed),
        "changed_ranges": compact_ranges(changed),
        "classified_changed_bytes": {key: len(offsets) for key, offsets in categories.items()},
        "classified_ranges": {key: compact_ranges(offsets) for key, offsets in categories.items()},
        "unexpected_byte_count": 0,
        "rule": "Every byte changed from source is owned by an injected in-place slot, vetted relocation, or exact pointer owner."
    }


def audit_incremental(batch02_rom, batch03_rom, selected, reviewed, previous_map, current_map):
    before = Path(batch02_rom).read_bytes()
    after = Path(batch03_rom).read_bytes()
    if len(before) != len(after) or hashlib.sha256(before).hexdigest() != BATCH02_SHA256:
        raise ValueError("Batch 02 baseline differs")
    source_by_id = {row["id"]: row for row in selected["entries"]}
    prior = {row["id"]: row for row in previous_map["relocations"]}
    current = {row["id"]: row for row in current_map["relocations"]}
    changed_relocation_ids = {key for key in prior if key not in current or
                              prior[key]["new_offset"] != current[key]["new_offset"]}
    new_relocation_ids = set(current) - set(prior)
    allowed = {"new_in_place_text": set(), "relocation_destination_changes": set(),
               "pointer_destination_changes": set()}
    for row in reviewed["entries"]:
        if row["apply"] and row["id"] not in current:
            source = source_by_id[row["id"]]
            start = source["rom_offset"]
            allowed["new_in_place_text"].update(range(start, start + source["slot_size"]))
    for key in changed_relocation_ids | new_relocation_ids:
        for relocation in (prior.get(key), current.get(key)):
            if not relocation:
                continue
            start = int(relocation["new_offset"], 16)
            allowed["relocation_destination_changes"].update(range(start, start + relocation["byte_length"]))
            for owner in relocation["pointer_sources"]:
                source = int(owner, 16)
                allowed["pointer_destination_changes"].update(range(source, source + 4))
    changed = {index for index, pair in enumerate(zip(before, after)) if pair[0] != pair[1]}
    unexpected = changed - set().union(*allowed.values())
    if unexpected:
        raise ValueError(f"Unexpected Batch 02-to-03 difference: {compact_ranges(sorted(unexpected)[:100])}")
    overlap = {key: changed & value for key, value in allowed.items()}
    return {"status": "PASS", "batch02_sha256": hashlib.sha256(before).hexdigest(),
            "batch03_sha256": hashlib.sha256(after).hexdigest(),
            "new_entry_count": sum(row["apply"] for row in reviewed["entries"]),
            "new_relocation_count": len(new_relocation_ids),
            "moved_baseline_relocation_count": len(changed_relocation_ids),
            "changed_byte_count": len(changed), "changed_ranges": compact_ranges(changed),
            "classified_changed_bytes": {key: len(value) for key, value in overlap.items()},
            "unexpected_byte_count": 0}


def make_qa(selection, reviewed, controlfixed, injection_map, size=36):
    source_by_id = {row["id"]: row for row in selection["entries"]}
    fixed_by_id = {row["id"]: row for row in controlfixed["entries"]}
    relocated = {row["id"] for row in injection_map["relocations"]}
    safe = [row for row in reviewed["entries"] if row["apply"]]
    chosen, used = [], set()

    def add(rows, focus, maximum):
        for row in rows:
            if maximum <= 0 or len(chosen) >= size:
                break
            if row["id"] in used:
                continue
            chosen.append((row["id"], focus))
            used.add(row["id"])
            maximum -= 1

    add((row for row in safe if row["id"] in relocated), "relocated_text_and_pointer", 2)
    add((row for row in safe if row.get("fa_segmented")), "FA_button_scroll_and_page_state", 10)
    add((row for row in safe if source_by_id[row["id"]]["slot_size"] <= 32), "short_slot", 6)
    add((row for row in safe if "?" in row["original"]), "question_or_choice", 4)
    add((row for row in safe if source_by_id[row["id"]]["controls"].get("FB")), "page_clear", 6)
    add(safe, "general_story_dialogue", size - len(chosen))
    if len(chosen) != size:
        raise ValueError("Cannot choose 36 Batch 03 QA entries")
    entries = []
    for priority, (entry_id, focus) in enumerate(chosen, 1):
        source = source_by_id[entry_id]
        entries.append({
            "priority": priority, "id": entry_id, "category": source["category"],
            "rom_offset": f"0x{source['rom_offset']:08X}", "gba_address": source["gba_address"],
            "pointer_owners": source["pointer_owners"], "original": source["original"],
            "expected_japanese": fixed_by_id[entry_id]["translated"],
            "test_focus": focus, "placement": "relocated" if entry_id in relocated else "in_place",
            "controls": source["controls"], "buffers": source["buffers"],
            "conversation_id": source.get("conversation_id"), "scene_id": source.get("scene_id"),
            "route": "Exact map/event caller not proven; locate with progressed save or script trace",
            "route_confidence": "unverified", "runtime_result": "not_human_tested"
        })
    return {"metadata": {"phase": "6B-3", "count": size,
                         "limitation": "Static ROM and pointer checks pass; no mGBA route or displayed layout is asserted."},
            "entries": entries}


def make_batch04_segmented(source, rom):
    batch = {**source, "metadata": {**source["metadata"]}}
    batch["entries"] = []
    count = 0
    for row in source["entries"]:
        target = dict(row)
        if row["controls"].get("FA", 0):
            offset = int(row["id"].split("_")[-1], 16)
            raw = rom[offset:offset + row["slot_size"]]
            segments = parse_raw_segments(raw, rom_offset=offset)
            target["control_segments"] = segments
            target["source_boundary_sequence"] = [segment["after_control"] for segment in segments
                                                  if segment["after_control"]]
            target["fa_placement_policy"] = "require_segments"
            target["translation_units"] = [{"segment_index": index, "english": segment["text"]}
                                           for index, segment in enumerate(segments)]
            count += 1
        batch["entries"].append(target)
    batch["metadata"].update({
        "fa_policy": "Source-only translation_units; translator must not place FA. Return per-segment text for technical layout approval.",
        "fa_annotated_entries": count,
        "status": "source_only_not_translated"})
    return batch


def verify_fa_invariant(fa_audit, controlfixed):
    fixed = {row["id"]: row for row in controlfixed["entries"]}
    codec = Charmap("ja")
    rows = []
    for row in fa_audit["entries"]:
        if not row["apply"]:
            continue
        output = parse_raw_segments(codec.encode(fixed[row["id"]]["translated"]))
        controls = [segment["after_control"] for segment in output if segment["after_control"]]
        if (controls != row["source_controls"] or len(output) != len(row["source_segments"])
                or controls.count("FA") != row["FA_count"]
                or row["layout_status"] != "LAYOUT_PASS"):
            raise ValueError(f"FA source/output invariant failed: {row['id']}")
        rows.append({"id": row["id"], "source_controls": row["source_controls"],
                     "output_controls": controls, "segment_count": len(output),
                     "fa_count": controls.count("FA"), "status": "PASS"})
    if len(rows) != 16:
        raise ValueError("Expected 16 approved FA entries")
    return {"status": "PASS", "applied_count": len(rows), "error_count": 0, "entries": rows}


def make_style(previous, names, fa_invariant):
    if names["metadata"]["term_count"] != 108 or fa_invariant["status"] != "PASS":
        raise ValueError("Batch 03 name or FA gate failed")
    return {
        **previous,
        "phase": "6B-3-to-6B-4", "status": "guidance_only_batch04_not_translated",
        "batch04_gate": "STATIC_GO_SEGMENTED_INPUT_ONLY",
        "gate_reason": "Sixteen Batch 03 FA entries pass segmented reconstruction, static layout and strict ROM audit; mGBA runtime remains unverified. Ambiguous FA remains held.",
        "official_name_results": names["metadata"]["result_counts"],
        "glossary_candidate_count": 30,
        "fa_translation_input": "out/phase6/ja_phase6_batch04_fa_segmented_input.json",
        "fa_translation_output_contract": "Translate only each ROM-derived segment text and return translated_segments in source order. Never choose FA positions. Codex/controlfix reconstructs FE/FA/FB boundaries and approves layout; otherwise hold.",
        "fa_claude_instruction": "Translate segment text only; do not place, remove, or move FA/FE/FB. No freeform combined FA string is approved.",
        "fa_layout_approval_rule": "Semantic confirmation is insufficient. Require all source segment boundaries, ROM-width diagnostics, complete pointer owners, and explicit LAYOUT_PASS; hold dynamic/ambiguous cases.",
        "fa_runtime_status": "not_human_tested",
        "known_bad_patterns": previous["known_bad_patterns"] + [
            "Recontrolfixing raw Batch 02 input holds 78 already-approved FA entries; merge from the controlfixed baseline.",
            "Static 208px diagnostic treated as pixel-perfect runtime proof.",
            "Case-sensitive FA warning aggregation missed lowercase segment_conflict labels."],
        "batch03_safe_applied": 125, "batch03_fa_applied": 16,
    }


def main():
    phase6_ids = {row["id"] for row in read(OUT / "ja_phase6_batch03_for_claude.json")["entries"]}
    selected = {"entries": [row for row in read(ROOT / "tests/fixtures/ja_phase6_selection.json")["entries"]
                            if row["id"] in phase6_ids]}
    reviewed = read(OUT / "ja_phase6_batch03_reviewed.json")
    fixed = read(OUT / "ja_phase6_batch03_controlfix.json")
    injection_map = read(OUT / "ja_phase6_batch03_map.json")
    source_rom = ROOT / "rom/unbound.gba"
    output_rom = ROOT / "out/unbound-ja-phase6-batch03.gba"
    audit = audit_rom(source_rom, output_rom, fixed, injection_map)
    baseline = (ROOT / "out/unbound-ja-phase6-batch02.gba").read_bytes()
    if hashlib.sha256(baseline).hexdigest() != BATCH02_SHA256:
        raise ValueError("Batch 02 ROM baseline changed")
    qa = make_qa(selected, reviewed, fixed, injection_map)
    fa_invariant = verify_fa_invariant(read(OUT / "ja_phase6_batch03_fa_audit.json"), fixed)
    incremental = audit_incremental(ROOT / "out/unbound-ja-phase6-batch02.gba", output_rom,
                                    selected, reviewed,
                                    read(OUT / "ja_phase6_batch02_map.json"), injection_map)
    batch04 = make_batch04_segmented(read(OUT / "ja_phase6_batch04_for_claude.json"),
                                     source_rom.read_bytes())
    style = make_style(read(OUT / "ja_phase6_batch03_style_handoff.json"),
                       read(OUT / "ja_phase6_batch03_official_name_audit.json"), fa_invariant)
    write(OUT / "ja_phase6_batch03_rom_audit.json", audit)
    write(OUT / "ja_phase6_batch03_incremental_audit.json", incremental)
    write(OUT / "ja_phase6_batch03_fa_invariant.json", fa_invariant)
    write(QA, qa)
    write(OUT / "ja_phase6_batch04_fa_segmented_input.json", batch04)
    write(OUT / "ja_phase6_batch04_style_handoff.json", style)
    print({"rom_audit": audit["status"], "changed_bytes": audit["changed_byte_count"],
           "classified": audit["classified_changed_bytes"],
           "incremental": incremental["status"], "incremental_bytes": incremental["changed_byte_count"],
           "runtime_qa": len(qa["entries"]),
           "batch04_fa": batch04["metadata"]["fa_annotated_entries"]})


if __name__ == "__main__":
    main()
