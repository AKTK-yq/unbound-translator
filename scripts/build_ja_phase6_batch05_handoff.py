#!/usr/bin/env python3
"""Audit incremental Batch 05 ROM without moving earlier relocated strings."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.pcs_text import Charmap
from scripts.audit_ja_phase5b import compact_ranges
from scripts.build_ja_phase6_batch03_handoff import audit_rom

OUT = ROOT / "out/phase6"
FIX = ROOT / "tests/fixtures"
OLD_SHA256 = "3cc314c7ceb3cd6057d8c6fb71194af0e4691f54a06b0174d9b06c41900dae0e"
ZERO = ("encode_errors", "skipped_pointer_mismatch", "skipped_implausible_pointer",
        "skipped_no_space", "fixed_truncated", "no_relocation_truncated",
        "runtime_patches", "graphics_patches")


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def strict_map(dry, built, expected_entries):
    for item in (dry, built):
        if any(item["stats"][key] != 0 for key in ZERO):
            raise ValueError("Incremental injector safety count is nonzero")
        if item["missing_relocations"] or item["missing_fixed_slots"]:
            raise ValueError("Missing relocation/fixed slot")
        if item["runtime_patches"] or item["graphics_patches"]:
            raise ValueError("Unexpected runtime or graphics patch")
    if dry["stats"] != built["stats"] or dry["relocations"] != built["relocations"]:
        raise ValueError("Incremental build differs from dry-run")
    if dry["stats"]["input_entries"] != expected_entries:
        raise ValueError("Incremental input count changed")


def incremental_audit(before_path, after_path, safe, map_data, baseline_entries, baseline_map):
    before, after = before_path.read_bytes(), after_path.read_bytes()
    if len(before) != len(after) or hashlib.sha256(before).hexdigest() != OLD_SHA256:
        raise ValueError("Batch 04 ROM differs")
    reloc = {row["id"]: row for row in map_data["relocations"]}
    old_reloc = {row["id"]: row for row in baseline_map["relocations"]}
    if set(reloc) & set(old_reloc):
        raise ValueError("New relocation overlaps previous ID")
    injector = runpy.run_path(str(ROOT / "005_hybrid_injector.py"))
    codec = Charmap("ja")
    allowed = {"in_place_text": set(), "relocated_text": set(), "pointer_writes": set()}
    for entry in safe:
        entry_id = entry["id"]
        data = injector["encode_text"](codec, injector["translation_for_injection"](entry),
                                       plain_script=entry["category"] == "plain_scripts")
        old, slot = int(entry["address"], 16), entry["byte_length"]
        move = reloc.get(entry_id)
        if move:
            new = int(move["new_offset"], 16)
            if move["storage"] != "vetted_ff" or move["byte_length"] != len(data) or after[new:new+len(data)] != data:
                raise ValueError(f"Relocation content/storage mismatch: {entry_id}")
            allowed["relocated_text"].update(range(new, new+len(data)))
            for owner in move["pointer_sources"]:
                offset = int(owner, 16)
                if before[offset:offset+4] != (0x08000000+old).to_bytes(4, "little"):
                    raise ValueError(f"Old pointer mismatch: {entry_id} {owner}")
                if after[offset:offset+4] != (0x08000000+new).to_bytes(4, "little"):
                    raise ValueError(f"New pointer mismatch: {entry_id} {owner}")
                allowed["pointer_writes"].update(range(offset, offset+4))
        else:
            if len(data) > slot or after[old:old+slot] != data.ljust(slot, b"\xff"):
                raise ValueError(f"In-place content mismatch: {entry_id}")
            allowed["in_place_text"].update(range(old, old+slot))
    protected = set()
    for entry in baseline_entries:
        old = int(entry["address"], 16)
        move = old_reloc.get(entry["id"])
        if move:
            new = int(move["new_offset"], 16)
            protected.update(range(new, new+move["byte_length"]))
            for owner in move["pointer_sources"]:
                offset = int(owner, 16)
                protected.update(range(offset, offset+4))
        else:
            protected.update(range(old, old+entry["byte_length"]))
    changed = {i for i, (a, b) in enumerate(zip(before, after)) if a != b}
    if changed & protected:
        raise ValueError(f"Existing 1,549 text/pointer bytes changed: {compact_ranges(changed & protected)}")
    if any(allowed[a] & allowed[b] for a, b in (("in_place_text", "relocated_text"),
                                                ("in_place_text", "pointer_writes"),
                                                ("relocated_text", "pointer_writes"))):
        raise ValueError("New write classes overlap")
    unexpected = changed - set().union(*allowed.values())
    if unexpected:
        raise ValueError(f"Unexpected incremental ROM bytes: {compact_ranges(unexpected)}")
    return {"status": "PASS", "batch04_sha256": hashlib.sha256(before).hexdigest(),
            "candidate_sha256": hashlib.sha256(after).hexdigest(),
            "existing_1549_unchanged": True, "changed_byte_count": len(changed),
            "changed_ranges": compact_ranges(changed),
            "classified_changed_bytes": {key: len(changed & region) for key, region in allowed.items()},
            "unexpected_byte_count": 0, "new_relocation_count": len(reloc),
            "new_pointer_write_count": map_data["stats"]["pointer_writes"]}


def retranslation(review, selected):
    source = {r["id"]: r for r in selected}
    result = []
    for row in review:
        if row["status"] != "needs_technical_fit" or "claude_cli_session_limit_prevented_revision" not in row["review_warning"]:
            continue
        sel = source[row["id"]]
        result.append({"id": row["id"], "English": row["original"],
                       "failed_or_provisional_Japanese": row.get("candidate_japanese"),
                       "exact_failure": "Claude draft had an unsupported Japanese PCS glyph; revision unavailable at CLI session limit",
                       "unsupported_glyph": "not_recorded_in_review_fixture",
                       "issue": row["review_warning"], "context_metadata": {
                           "category": row["category"], "scene_id": row.get("scene_id"),
                           "speaker": sel.get("speaker"), "context_before": sel.get("context_before"),
                           "context_after": sel.get("context_after"), "rom_offset": sel["rom_offset"],
                           "slot_size": sel["slot_size"], "controls": sel["controls"],
                           "pointer_owners": sel["pointer_owners"]},
                       "recommended_retranslation_constraint": (
                           "Translate anew in kana-only PCS-safe glyphs; preserve source controls/tokens; "
                           "do not infer short-label width or approve a fixed slot from byte length alone"),
                       "no_codex_translation": True})
    if len(result) != 6:
        raise ValueError("Incomplete translation handoff must contain six entries")
    return {"metadata": {"count": 6, "status": "TRANSLATION_INCOMPLETE"}, "entries": result}


def runtime_qa(reviewed, selected, safe, map_data, names):
    by_source = {x["id"]: x for x in selected}
    by_fixed = {x["id"]: x for x in safe}
    relocated = {x["id"] for x in map_data["relocations"]}
    verified = {x["entry_id"] for x in names["entries"] if x["PokeAPI result"]["status"] == "verified_exact"}
    applied = [x for x in reviewed["entries"] if x["final_apply"]]
    chosen, used = [], set()

    def add(rows, focus, limit):
        for row in rows:
            if limit == 0 or len(chosen) >= 36:
                break
            if row["id"] not in used:
                chosen.append((row, focus))
                used.add(row["id"])
                limit -= 1

    add((r for r in applied if r["category"] == "battle_messages"), "battle_message", 8)
    add((r for r in applied if r["category"] == "menu_game_settings"), "game_settings", 5)
    add((r for r in applied if r["category"] in {"menu_pc", "menu_item_storage"}), "PC_and_item_storage", 4)
    add((r for r in applied if r["category"] == "menu_cube_system"), "Cube_menu", 3)
    add((r for r in applied if r["category"] == "menu_list_labels"), "list_choice", 3)
    add((r for r in applied if r["id"] in verified), "PokeAPI_verified_name", 3)
    add((r for r in applied if r["id"] in relocated), "relocation_and_pointer", 4)
    add((r for r in applied if r["slot_size"] <= 8), "short_slot", 2)
    add((r for r in reviewed["entries"] if not r["final_apply"] and r["buffer_result"] == "unproved_hold"),
        "held_English_dynamic_buffer", 2)
    add(applied, "other_menu", 36-len(chosen))
    if len(chosen) != 36:
        raise ValueError("Cannot fill runtime QA set")
    entries = []
    for priority, (row, focus) in enumerate(chosen, 1):
        source = by_source[row["id"]]
        entries.append({"priority": priority, "id": row["id"], "category": row["category"],
                        "original": row["original"], "expected_japanese": by_fixed[row["id"]]["translated"] if row["final_apply"] else None,
                        "expected_display": "Japanese" if row["final_apply"] else "English (held)",
                        "rom_offset": f"0x{source['rom_offset']:08X}", "gba_address": source["gba_address"],
                        "pointer_owners": source["pointer_owners"], "controls": source["controls"],
                        "buffers": source["buffers"], "focus": focus,
                        "placement": "held" if not row["final_apply"] else "relocated" if row["id"] in relocated else "in_place",
                        "route": "Exact live caller/route not proved; identify screen with progressed save or runtime trace",
                        "route_confidence": "unverified", "runtime_result": "not_human_tested"})
    return {"metadata": {"count": 36, "focus_counts": dict(Counter(r["focus"] for r in entries)),
                          "limitation": "Static ROM/pointer audit only; mGBA route and display not asserted"},
            "entries": entries}


def main():
    baseline_rom = ROOT / "out/unbound-ja-phase6-batch04.gba"
    staged_rom = OUT / "ja_phase6_batch05_candidate.gba"
    candidate_rom = staged_rom if staged_rom.exists() else ROOT / "out/unbound-ja-phase6-batch05.gba"
    dry = read(OUT / "ja_phase6_batch05_incremental_dry_run_map.json")
    built = read(OUT / "ja_phase6_batch05_incremental_map.json")
    previous = read(OUT / "ja_phase6_batch04_map.json")
    baseline = read(OUT / "ja_phase6_batch04_controlfix.json")["entries"]
    safe = read(OUT / "ja_phase6_batch05_safe_controlfix.json")["entries"]
    merged = read(OUT / "ja_phase6_batch05_combined_controlfix.json")
    reviewed = read(OUT / "ja_phase6_batch05_reviewed.json")
    names = read(OUT / "ja_phase6_batch05_official_name_audit.json")
    selected = [row for row in read(FIX / "ja_phase6_selection.json")["entries"] if row.get("batch_number") == 5]
    strict_map(dry, built, len(safe))
    if merged["entries"][:1549] != baseline or merged["entries"][1549:] != safe:
        raise ValueError("Merged controlfixed JSON changed baseline or new subset")
    if ((OUT / "ja_phase6_batch05_combined_controlfix.json").read_bytes() !=
            (OUT / "ja_phase6_batch05_safe_controlfix_rebuilt.json").read_bytes() or
            (OUT / "ja_phase6_batch05_combined_controlfix.json").read_bytes() !=
            (OUT / "ja_phase6_batch05_controlfix_twice.json").read_bytes()):
        raise ValueError("Safe-only controlfix or second pass differs")
    incremental = incremental_audit(baseline_rom, candidate_rom, safe, built, baseline, previous)
    combined_map = {**previous, "stats": {**previous["stats"],
                    "pointer_writes": previous["stats"]["pointer_writes"] + built["stats"]["pointer_writes"]},
                    "relocations": previous["relocations"] + built["relocations"]}
    source = audit_rom(ROOT / "rom/unbound.gba", candidate_rom, merged, combined_map)
    if source["unexpected_byte_count"] or incremental["unexpected_byte_count"]:
        raise ValueError("Unexpected ROM difference")
    write(OUT / "ja_phase6_batch05_incremental_audit.json", incremental)
    write(OUT / "ja_phase6_batch05_rom_audit.json", source)
    write(FIX / "ja_phase6_batch05_retranslation.json", retranslation(
        read(FIX / "ja_phase6_batch05_claude_review.json"), selected))
    write(FIX / "ja_phase6_batch05_runtime_qa.json", runtime_qa(reviewed, selected, safe, built, names))
    prior_style = read(OUT / "ja_phase6_batch05_style_handoff.json")
    batch06 = [row for row in read(FIX / "ja_phase6_selection.json")["entries"] if row.get("batch_number") == 6]
    fa06 = [row for row in batch06 if row["controls"].get("FA", 0)]
    style = {**prior_style, "phase": "6B-5-to-6B-6", "status": "guidance_only_batch06_not_translated",
             "batch06_gate": "STATIC_GO_SOURCE_ONLY", "batch05_applied": len(safe),
             "batch05_held": 408-len(safe), "applied_total": 1549+len(safe),
             "batch05_incomplete_hold": 6, "batch05_fa_hold": 4,
             "batch05_unknown_buffer_hold": 68,
             "batch05_official_name_results": names["metadata"]["result_counts"],
             "width_rule": "width_runtime_unverified alone never holds; use proved geometry and explicit risk",
             "existing_baseline_rule": "Inject incrementally into audited Batch 04 ROM; full source reinjection moves earlier relocation destinations",
             "batch06_source_count": len(batch06), "batch06_fa_count": len(fa06),
             "translation_status": "source_only_no_batch06_translation"}
    write(OUT / "ja_phase6_batch06_style_handoff.json", style)
    if fa06:
        write(OUT / "ja_phase6_batch06_fa_segmented_input.json", {"metadata": {
            "status": "source_only_not_translated", "entries": len(fa06)}, "entries": fa06})
    print({"incremental_changed": incremental["changed_byte_count"],
           "incremental_classes": incremental["classified_changed_bytes"],
           "source_changed": source["changed_byte_count"], "unexpected": 0,
           "qa": 36, "batch06_sources": len(batch06), "batch06_fa": len(fa06)})


if __name__ == "__main__":
    main()
