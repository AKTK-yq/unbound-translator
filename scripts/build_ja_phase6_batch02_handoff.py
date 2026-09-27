#!/usr/bin/env python3
"""Select bounded runtime QA and pass proven Batch 02 rules to Batch 03."""

from __future__ import annotations

import json
import hashlib
from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.pcs_text import Charmap
from scripts.audit_ja_phase5b import compact_ranges
from scripts.audit_ja_phase6_batch01_fit import line_widths

OUT = ROOT / "out/phase6"
QA = ROOT / "tests/fixtures/ja_phase6_batch02_runtime_qa.json"


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def finalize_reviewed(reviewed, selection, controlfixed, injection_map):
    """Replace pre-controlfix estimates with exact final payload and map placement."""
    source_by_id = {row["id"]: row for row in selection["entries"]}
    fixed_by_id = {row["id"]: row for row in controlfixed["entries"]}
    relocations = {row["id"]: row for row in injection_map["relocations"]}
    injector = runpy.run_path(str(ROOT / "005_hybrid_injector.py"))
    codec = Charmap("ja")
    rows = []
    for row in reviewed["entries"]:
        item = dict(row)
        entry_id = row["id"]
        item["final_apply"] = bool(row["apply"])
        if row["apply"]:
            source = source_by_id[entry_id]
            fixed = fixed_by_id[entry_id]
            text = injector["translation_for_injection"](fixed)
            payload = injector["encode_text"](codec, text,
                                               plain_script=source["category"] == "plain_scripts")
            placement = "relocatable" if entry_id in relocations else "in_place"
            if (len(payload) > source["slot_size"]) != (placement == "relocatable"):
                raise ValueError(f"Post-controlfix placement mismatch: {entry_id}")
            item.update({"final_japanese": fixed["translated"], "fit_result": placement,
                         "final_encoded_bytes": len(payload), "final_line_pixels": line_widths(payload),
                         "source_slot_bytes": source["slot_size"],
                         "final_pointer_writes": len(source["pointer_owners"]) if placement == "relocatable" else 0})
        else:
            item.update({"final_encoded_bytes": None, "final_line_pixels": None,
                         "source_slot_bytes": source_by_id[entry_id]["slot_size"],
                         "final_pointer_writes": 0})
            if item["fit_result"] == "pending_controlfix":
                item["fit_result"] = "held_unmeasured"
        rows.append(item)
    result = {**reviewed, "entries": rows}
    result["metadata"] = {**reviewed["metadata"],
                          "finalized_against_map": True,
                          "final_applied_byte_placement_counts": {
                              "in_place": sum(r["apply"] and r["fit_result"] == "in_place" for r in rows),
                              "relocatable": sum(r["apply"] and r["fit_result"] == "relocatable" for r in rows)}}
    return result


def audit_incremental(batch01_rom, batch02_rom, selection, reviewed):
    """Prove the new ROM changes only the newly approved in-place slots."""
    before = Path(batch01_rom).read_bytes()
    after = Path(batch02_rom).read_bytes()
    if len(before) != len(after):
        raise ValueError("Batch 01/02 ROM sizes differ")
    if hashlib.sha256(before).hexdigest() != "52cd6c85aa7d2954159bbbe7a077a09ace895fab858778e5790a2965607fefe6":
        raise ValueError("Batch 01 baseline ROM hash changed")
    selected = {row["id"]: row for row in selection["entries"]}
    applied = [row for row in reviewed["entries"] if row["apply"]]
    if any(row["fit_result"] != "in_place" for row in applied):
        raise ValueError("Incremental audit assumes Batch 02 has no relocation")
    allowed = set()
    for row in applied:
        source = selected[row["id"]]
        start = source["rom_offset"]
        end = start + source["slot_size"]
        allowed.update(range(start, end))
        if before[start:end] == after[start:end]:
            raise ValueError(f"Applied entry did not change: {row['id']}")
        for owner in source["pointer_owners"]:
            at = int(owner, 16)
            if before[at:at + 4] != after[at:at + 4]:
                raise ValueError(f"Batch 02 changed pointer: {row['id']} {owner}")
    changed = {index for index, (old, new) in enumerate(zip(before, after)) if old != new}
    unexpected = changed - allowed
    if unexpected:
        raise ValueError(f"Batch 02 changed unrelated bytes: {compact_ranges(sorted(unexpected)[:100])}")
    return {"status": "PASS", "applied_entries": len(applied),
            "batch01_sha256": hashlib.sha256(before).hexdigest(),
            "batch02_sha256": hashlib.sha256(after).hexdigest(),
            "changed_byte_count": len(changed), "changed_ranges": compact_ranges(changed),
            "unexpected_byte_count": 0, "pointer_writes": 0, "relocations": 0,
            "rule": "Every Batch 01-to-02 changed byte must lie inside one approved Batch 02 source slot."}


def make_qa(selection, reviewed, injection_map, controlfixed, size=30):
    by_id = {row["id"]: row for row in selection["entries"]}
    safe = [row for row in reviewed["entries"] if row["apply"]]
    fixed_by_id = {row["id"]: row for row in controlfixed["entries"]}
    relocations = {row["id"]: row for row in injection_map["relocations"]}
    chosen, used = [], set()

    def add(candidates, tag, count):
        for row in candidates:
            if count <= 0 or len(chosen) >= size:
                break
            if row["id"] in used:
                continue
            chosen.append((row["id"], tag))
            used.add(row["id"])
            count -= 1

    add((r for r in safe if "\\l" in r["original"]), "reviewed_FA_scroll", 5)
    add((r for r in safe if r["id"] in relocations), "relocation", 6)
    add((r for r in safe if by_id[r["id"]]["buffers"]), "known_token_or_dynamic_buffer", 5)
    add((r for r in safe if by_id[r["id"]]["slot_size"] <= 32), "short_label_or_choice", 5)
    add((r for r in safe if "?" in r["original"]), "choice_or_question", 3)
    add((r for r in safe if "\n\n" in r["original"]), "multi_page_story_or_NPC", 3)
    add(safe, "general_script", size - len(chosen))
    result = []
    for priority, (entry_id, tag) in enumerate(chosen, 1):
        source = by_id[entry_id]
        result.append({"priority": priority, "id": entry_id, "category": source["category"],
                       "rom_offset": f"0x{source['rom_offset']:08X}",
                       "gba_address": source["gba_address"], "pointer_owners": source["pointer_owners"],
                       "original": source["original"],
                       "expected_japanese": fixed_by_id[entry_id]["translated"],
                       "test_focus": tag, "placement": "relocated" if entry_id in relocations else "in_place",
                       "controls": source["controls"], "buffers": source["buffers"],
                       "route": "Map/event caller not proved; use progressed save or script trace to locate this event",
                       "route_confidence": "unverified",
                       "runtime_result": "not_human_tested"})
    if len(result) != size:
        raise ValueError("Unable to choose 30 safe Batch 02 QA candidates")
    return {"metadata": {"phase": "6B-2", "count": len(result),
                         "scope": "applied Batch 02 scripts only; no confirmed battle/mission table rows",
                         "limitations": ["30 provisional-FA rows are English and excluded",
                                         "49 unknown-buffer rows remain English; no resolved-value candidate is applied",
                                         "No Batch 02 relocation is approved after compact-width gating; use Batch 01 relocation QA",
                                         "No official-name difference occurred in applied Batch 02 entries",
                                         "Map/event reachability is not proven; human mGBA QA remains pending"]},
            "entries": result}


def make_style(previous, scroll, names, buffers, glossary):
    if scroll["metadata"]["class_counts"] != {"C": 30}:
        raise ValueError("Provisional FA status changed")
    return {
        "phase": "6B-2-to-6B-3", "status": "guidance_only_batch03_not_translated",
        "batch03_gate": "STATIC_GO_SEGMENTED_INPUT_ONLY",
        "gate_reason": "The 30 Batch 02 FA drafts remain held. Batch 03 FA entries use ROM-derived translation_units and require translated_segments plus layout review; unsegmented placements are automatically held. Unknown buffers also remain held pending producer proof. Runtime FA placement remains unverified.",
        "speaker_rules": previous["approved_style_notes"][:2] + [
            "Pointer proximity and conversation_id do not prove speaker or map event; use neutral voice without invented persona."],
        "unknown_buffer_rule": "Trace bufferstring writer, all call sites, possible values and page state. Keep English if grammar or producer remains unresolved; do not remove FD raw suffix tokens.",
        "official_name_rule": "Require exact source-English PokeAPI entity match and PCS-safe ja-hrkt. No plural singularization or memory-only official names; unresolved terms stay English.",
        "official_name_results": names["metadata"]["result_counts"],
        "glossary_boundary_rule": "Only approved exact/word-boundary and context-scope matches. Ace is not Aerial Ace. Proposal-only terms never enter matcher automatically.",
        "glossary_candidate_count": glossary["metadata"]["candidate_count"],
        "counters": previous["counters"],
        "sign_formatting": previous["sign_formatting"],
        "mission_formatting": previous["mission_formatting"],
        "fa_scroll_rule": "\\l is PCS FA: wait for button then scroll one dialogue line. Claude translates source display segments only; Codex/controlfix reconstructs FE/FA/FB boundaries from ROM-derived control_segments after layout review. Never append or move FA by character index. Hold if segments or layout approval are absent.",
        "fa_translation_input": "out/phase6/ja_phase6_batch03_fa_segmented_input.json",
        "fa_translation_output_contract": "For FA entries translate translation_units independently into translated_segments in the same order; do not insert, remove or move FA/\\l, FE, FB, or page switches. Preserve each segment's protected tokens. Do not submit a freeform combined translation as final placement.",
        "fa_claude_instruction": "Do not choose any FA/\\l position. Do not delete source FA. When a source FA boundary is fixed in an input segment, preserve that boundary by returning segment text only. Codex/controlfix owns final placement.",
        "fa_ambiguous_warning": "fa_placement_review_required (technical warning, not needs_context); controlfix emits FA_PLACEMENT_REVIEW_REQUIRED and holds the entry.",
        "fa_runtime_status": "runtime_unverified",
        "dangerous_controls": ["FE newline", "FA interactive scroll", "FB wait-and-clear",
                               "FC Japanese/Latin page and style", "FD dynamic substitution and raw 07/08/0C",
                               "colors, quote, button, alignment and pause controls"],
        "known_bad_patterns": previous["known_bad_patterns"] + [
            "Claude draft omitted FA and it was restored at string end",
            "single bufferstring writer assumed to cover multiple call sites",
            "raw exact pointer hit ignored during relocation",
            "short label declared width-safe from byte fit alone"],
        "text_pacing": "Keep Phase 5F P7 baseline: no new waits, pause removal, renderer change or wakachigaki policy change.",
        "unresolved_buffers": buffers["metadata"]["status_counts"],
    }


def main():
    selection = read(ROOT / "tests/fixtures/ja_phase6_selection.json")
    reviewed = read(OUT / "ja_phase6_batch02_reviewed.json")
    injection_map = read(OUT / "ja_phase6_batch02_map.json")
    controlfixed = read(OUT / "ja_phase6_batch02_controlfix.json")
    reviewed = finalize_reviewed(reviewed, selection, controlfixed, injection_map)
    write(OUT / "ja_phase6_batch02_reviewed.json", reviewed)
    incremental = audit_incremental(ROOT / "out/unbound-ja-phase6-batch01.gba",
                                    ROOT / "out/unbound-ja-phase6-batch02.gba", selection, reviewed)
    write(OUT / "ja_phase6_batch02_incremental_audit.json", incremental)
    qa = make_qa(selection, reviewed, injection_map, controlfixed)
    style = make_style(read(OUT / "ja_phase6_batch02_style_handoff.json"),
                       read(OUT / "ja_phase6_batch02_scroll_audit.json"),
                       read(OUT / "ja_phase6_batch02_official_name_audit.json"),
                       read(OUT / "ja_phase6_batch02_buffer_audit.json"),
                       read(OUT / "ja_phase6_batch02_glossary_audit.json"))
    write(QA, qa)
    write(OUT / "ja_phase6_batch03_style_handoff.json", style)
    print({"qa": len(qa["entries"]), "incremental": incremental["status"],
           "batch03_gate": style["batch03_gate"]})


if __name__ == "__main__":
    main()
