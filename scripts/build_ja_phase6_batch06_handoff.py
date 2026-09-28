#!/usr/bin/env python3
"""Audit Batch 06 ROM and inventory every unresolved Phase 6 selection."""

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
from scripts.build_ja_phase6_batch05_handoff import strict_map

OUT = ROOT / "out/phase6"
FIX = ROOT / "tests/fixtures"
BATCH05_SHA256 = "dcb2b8813cc1257001f38586b5a214bccae24e29a3812f47c4a897fbfef9ec73"
HOLD_CLASSES = (
    "UNKNOWN_BUFFER", "OFFICIAL_NAME_UNRESOLVED", "GLOSSARY_APPROVAL",
    "CONTEXT_REQUIRED", "SPEAKER_REQUIRED", "FA_SEMANTIC_CONFLICT", "FA_LAYOUT",
    "INCOMPLETE_TRANSLATION", "UNSUPPORTED_GLYPH", "CONTROL_BOUNDARY",
    "POINTER_OWNER", "WIDTH_LAYOUT", "STRUCTURED_UI", "OTHER",
)
NEXT_ACTION = {
    "UNKNOWN_BUFFER": "Trace exact caller/value/page state; do not infer substitution.",
    "OFFICIAL_NAME_UNRESOLVED": "Verify exact English entity and official Japanese; review conflicts.",
    "GLOSSARY_APPROVAL": "Approve or reject entry-scoped term; never global-replace by substring.",
    "CONTEXT_REQUIRED": "Trace runtime scene, usage and intended meaning.",
    "SPEAKER_REQUIRED": "Prove speaker/event ownership before assigning voice.",
    "FA_SEMANTIC_CONFLICT": "Request segment-aware retranslation without moving FA.",
    "FA_LAYOUT": "Measure runtime scroll/page behavior and approve each segment.",
    "INCOMPLETE_TRANSLATION": "Obtain a complete kana-only reviewed translation.",
    "UNSUPPORTED_GLYPH": "Request PCS-safe reviewed wording; preserve meaning.",
    "CONTROL_BOUNDARY": "Reconcile each ROM text/control segment with controlfix output.",
    "POINTER_OWNER": "Prove every exact/interior/computed pointer before relocation.",
    "WIDTH_LAYOUT": "Measure renderer and fit without dropping meaning.",
    "STRUCTURED_UI": "Prove field geometry/columns or keep English.",
    "OTHER": "Investigate recorded raw reasons.",
}


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def audit_incremental(previous_rom: Path, current_rom: Path, safe: list[dict],
                      current_map: dict, existing: list[dict], previous_relocations: list[dict]):
    before, after = previous_rom.read_bytes(), current_rom.read_bytes()
    if len(before) != len(after) or hashlib.sha256(before).hexdigest() != BATCH05_SHA256:
        raise ValueError("Batch 05 ROM differs")
    relocation = {x["id"]: x for x in current_map["relocations"]}
    old_relocation = {x["id"]: x for x in previous_relocations}
    if set(relocation) & set(old_relocation):
        raise ValueError("New relocation duplicates an existing ID")
    injector = runpy.run_path(str(ROOT / "005_hybrid_injector.py"))
    codec = Charmap("ja")
    allowed = {"in_place_text": set(), "relocated_text": set(), "pointer_writes": set()}
    for entry in safe:
        key = entry["id"]
        payload = injector["encode_text"](codec, injector["translation_for_injection"](entry),
                                          plain_script=entry["category"] == "plain_scripts")
        old, slot = int(entry["address"], 16), entry["byte_length"]
        moved = relocation.get(key)
        if moved:
            new = int(moved["new_offset"], 16)
            if (moved["storage"] != "vetted_ff" or moved["byte_length"] != len(payload)
                    or after[new:new+len(payload)] != payload):
                raise ValueError(f"Relocation content or storage mismatch: {key}")
            allowed["relocated_text"].update(range(new, new+len(payload)))
            for owner in moved["pointer_sources"]:
                pos = int(owner, 16)
                if (before[pos:pos+4] != (0x08000000+old).to_bytes(4, "little")
                        or after[pos:pos+4] != (0x08000000+new).to_bytes(4, "little")):
                    raise ValueError(f"Pointer write mismatch: {key} {owner}")
                allowed["pointer_writes"].update(range(pos, pos+4))
        else:
            if len(payload) > slot or after[old:old+slot] != payload.ljust(slot, b"\xff"):
                raise ValueError(f"In-place content mismatch: {key}")
            allowed["in_place_text"].update(range(old, old+slot))
    protected = set()
    for entry in existing:
        key = entry["id"]
        moved = old_relocation.get(key)
        if moved:
            new = int(moved["new_offset"], 16)
            protected.update(range(new, new+moved["byte_length"]))
            for owner in moved["pointer_sources"]:
                pos = int(owner, 16)
                protected.update(range(pos, pos+4))
        else:
            pos = int(entry["address"], 16)
            protected.update(range(pos, pos+entry["byte_length"]))
    if protected & set().union(*allowed.values()):
        raise ValueError("Batch 06 permitted write region overlaps existing 1,717")
    if any(allowed[a] & allowed[b] for a, b in
           (("in_place_text", "relocated_text"), ("in_place_text", "pointer_writes"),
            ("relocated_text", "pointer_writes"))):
        raise ValueError("Batch 06 write classes overlap")
    changed = {pos for pos, (old, new) in enumerate(zip(before, after)) if old != new}
    if changed & protected:
        raise ValueError(f"Existing 1,717 bytes changed: {compact_ranges(changed & protected)}")
    unexpected = changed - set().union(*allowed.values())
    if unexpected:
        raise ValueError(f"Unexpected ROM changes: {compact_ranges(unexpected)}")
    return {
        "status": "PASS", "before_sha256": hashlib.sha256(before).hexdigest(),
        "after_sha256": hashlib.sha256(after).hexdigest(),
        "existing_1717_unchanged": True, "changed_byte_count": len(changed),
        "changed_ranges": compact_ranges(changed),
        "classified_changed_bytes": {name: len(changed & area) for name, area in allowed.items()},
        "classified_ranges": {name: compact_ranges(changed & area) for name, area in allowed.items()},
        "unexpected_byte_count": 0, "new_relocation_count": len(relocation),
        "new_pointer_write_count": current_map["stats"]["pointer_writes"],
    }


def runtime_qa(reviewed, selected, safe, injection_map, size=36):
    by_source = {x["id"]: x for x in selected}
    by_fixed = {x["id"]: x for x in safe}
    relocated = {x["id"] for x in injection_map["relocations"]}
    applied = [x for x in reviewed if x["final_apply"]]
    chosen, seen = [], set()

    def add(rows, focus, count):
        for row in rows:
            if count <= 0 or len(chosen) >= size:
                break
            if row["id"] in seen:
                continue
            chosen.append((row, focus))
            seen.add(row["id"])
            count -= 1

    add((x for x in applied if x["category"].startswith("menu_")), "Menu/UI label", 8)
    add((x for x in applied if x["original_status"] == "existing_official"),
        "PokeAPI official name/description", 5)
    add((x for x in applied if x["original_status"] == "existing_glossary"),
        "approved glossary scope", 4)
    add(sorted((x for x in applied if by_source[x["id"]]["controls"].get("FE")),
               key=lambda x: (-by_source[x["id"]]["controls"].get("FE", 0), x["id"])),
        "FE page/line boundaries", 8)
    add(sorted(applied, key=lambda x: (-(x["encoded_bytes"] or 0), x["id"])),
        "long Japanese text", 3)
    add((x for x in applied if x["id"] in relocated), "vetted relocation", 4)
    add((x for x in applied if x["id"] in relocated
         and len(by_source[x["id"]]["pointer_owners"]) > 1), "multiple pointer owners", 2)
    add(applied, "other safe entry", size-len(chosen))
    if len(chosen) != size:
        raise ValueError("Cannot select 36 runtime QA cases")
    result = []
    for number, (row, focus) in enumerate(chosen, 1):
        src = by_source[row["id"]]
        result.append({
            "priority": number, "id": row["id"], "category": row["category"],
            "original": row["original"], "expected_japanese": by_fixed[row["id"]]["translated"],
            "rom_offset": f"0x{src['rom_offset']:08X}", "gba_address": src["gba_address"],
            "pointer_owners": src["pointer_owners"], "controls": src["controls"],
            "placement": "relocated" if row["id"] in relocated else "in_place",
            "focus": focus, "route": "Exact runtime caller not yet proved; use progressed save or trace",
            "runtime_result": "not_human_tested",
        })
    return {"metadata": {"count": size, "focus_counts": dict(Counter(x["focus"] for x in result)),
                         "mGBA_result": "not_run"}, "entries": result}


def hold_classes(raw_reasons: list[str], review: dict, row: dict) -> list[str]:
    reasons = [reason.casefold() for reason in raw_reasons]
    warnings = {value.casefold() for value in review.get("review_warning", [])}
    classes = set()
    for reason in reasons:
        if "buffer" in reason:
            classes.add("UNKNOWN_BUFFER")
        if "official" in reason:
            classes.add("OFFICIAL_NAME_UNRESOLVED")
        if "glossary" in reason:
            classes.add("GLOSSARY_APPROVAL")
        if "speaker" in reason:
            classes.add("SPEAKER_REQUIRED")
        if "fa_semantic" in reason:
            classes.add("FA_SEMANTIC_CONFLICT")
        if "fa_layout" in reason or "fa_not_" in reason or "terminal_fa" in reason:
            classes.add("FA_LAYOUT")
        if (reason in {"no_reviewed_japanese", "no_complete_reviewed_draft",
                       "translation_incomplete_or_unreviewed", "review_context_or_incomplete"}
                or reason.startswith("no_complete_draft_for_official_name")):
            classes.add("INCOMPLETE_TRANSLATION")
        if "unsupported_glyph" in reason:
            classes.add("UNSUPPORTED_GLYPH")
        if "control_boundary" in reason or "control_sequence" in reason:
            classes.add("CONTROL_BOUNDARY")
        if "pointer" in reason or reason == "owner_incomplete":
            classes.add("POINTER_OWNER")
        if "width" in reason or "screen_" in reason:
            classes.add("WIDTH_LAYOUT")
        if "structured" in reason or "column" in reason or "fixed_or_" in reason:
            classes.add("STRUCTURED_UI")
        if ("context" in reason or "semantic_or_ui" in reason
                or reason.startswith("review_status:")):
            classes.add("CONTEXT_REQUIRED")
    if "unknown_buffer" in warnings:
        classes.add("UNKNOWN_BUFFER")
    if "speaker_uncertain" in warnings:
        classes.add("SPEAKER_REQUIRED")
    if "unsupported_japanese_glyph" in warnings:
        classes.add("UNSUPPORTED_GLYPH")
    if ("fa_segment_semantic_conflict" in warnings
            or row.get("technical_class") == "FA_SEMANTIC_CONFLICT"
            or row.get("fa_semantic_result") in {"conflict", "CONFLICT"}):
        classes.add("FA_SEMANTIC_CONFLICT")
    if not (row.get("candidate_japanese") or review.get("reviewed_japanese")):
        classes.add("INCOMPLETE_TRANSLATION")
    order = ("OFFICIAL_NAME_UNRESOLVED", "GLOSSARY_APPROVAL", "UNKNOWN_BUFFER",
             "INCOMPLETE_TRANSLATION", "UNSUPPORTED_GLYPH", "FA_SEMANTIC_CONFLICT",
             "CONTROL_BOUNDARY", "POINTER_OWNER", "STRUCTURED_UI", "WIDTH_LAYOUT",
             "FA_LAYOUT", "SPEAKER_REQUIRED", "CONTEXT_REQUIRED")
    return [name for name in order if name in classes] or ["OTHER"]


def inventory():
    selected = read(FIX / "ja_phase6_selection.json")["entries"]
    if len(selected) != 2500 or len({x["id"] for x in selected}) != 2500:
        raise ValueError("Phase 6 selection not exactly 2,500 unique IDs")
    by_selected = {x["id"]: x for x in selected}
    all_rows = []
    batch_counts = {}
    for number in range(1, 7):
        review = read(FIX / f"ja_phase6_batch{number:02}_claude_review.json")
        by_review = {x["id"]: x for x in review}
        result = read(OUT / f"ja_phase6_batch{number:02}_reviewed.json")["entries"]
        if len(result) != len([x for x in selected if x["batch_number"] == number]):
            raise ValueError(f"Batch {number} selected/reviewed count differs")
        if number == 1:
            applied_ids = {x["id"] for x in read(OUT / "ja_phase6_batch01_safe_input.json")["entries"]}
        else:
            applied_ids = {x["id"] for x in result if x["final_apply"]}
        if not applied_ids <= {x["id"] for x in result}:
            raise ValueError(f"Batch {number} applied ID outside selection")
        batch_counts[number] = {"selected": len(result), "applied": len(applied_ids),
                                "held": len(result)-len(applied_ids)}
        for row in result:
            key = row["id"]
            if key in applied_ids:
                continue
            src, claude = by_selected[key], by_review[key]
            raw_reasons = row.get("hold_reason") or row.get("validation_issues") or []
            if isinstance(raw_reasons, str):
                raw_reasons = [raw_reasons]
            if number == 1:
                raw_reasons = list(raw_reasons) + [row["technical_status"]]
            candidate = (row.get("candidate_japanese") or row.get("reviewed_japanese")
                         or claude.get("reviewed_japanese") or claude.get("candidate_japanese"))
            fields = {**row, "candidate_japanese": candidate}
            classes = hold_classes(raw_reasons, claude, fields)
            primary, secondary = classes[0], classes[1:]
            priority = ("P1" if any(x in {"OFFICIAL_NAME_UNRESOLVED", "GLOSSARY_APPROVAL",
                                          "INCOMPLETE_TRANSLATION"} for x in classes)
                        else "P3" if primary in {"FA_SEMANTIC_CONFLICT", "FA_LAYOUT", "WIDTH_LAYOUT"}
                        else "P2")
            all_rows.append({
                "id": key, "batch": number, "category": src["category"], "original": src["original"],
                "candidate_japanese": candidate, "current_status": row.get(
                    "original_status", row.get("review_status", row.get("status",
                    row.get("technical_status")))),
                "hold_category": primary, "primary_hold": primary,
                "secondary_holds": secondary, "raw_hold_reasons": raw_reasons,
                "hold_reason": "; ".join(raw_reasons) or row.get("reason") or "unclassified hold",
                "official_name_state": row.get("official_result", row.get("official_name_result",
                                        "review_pending" if "official_name_verification_required"
                                        in claude.get("review_warning", []) else "not_flagged")),
                "glossary_state": row.get("glossary_result",
                                  "candidate_unapproved" if claude.get("new_glossary_candidates")
                                  else "not_flagged"),
                "buffer_state": row.get("buffer_result",
                                "source_buffer_present" if src["buffers"] else "none"),
                "speaker_context_state": {"speaker": src["speaker"],
                                          "confidence": src["speaker_confidence"],
                                          "conversation_id": src.get("conversation_id"),
                                          "scene_id": src.get("scene_id")},
                "FA_state": row.get("fa_result", row.get("fa_layout_result",
                            "source_FA_present" if src["controls"].get("FA") else "none")),
                "control_state": row.get("control_result", row.get("semantic_status",
                                 "source_controls_preserved_or_not_audited")),
                "pointer_state": row.get("pointer_owner_result",
                                 row.get("pointer_ownership", row.get("pointer_owner_complete",
                                 "not_audited"))),
                "width_state": row.get("width_result", row.get("layout_result",
                               "runtime_unverified")),
                "priority": priority, "suggested_next_action": NEXT_ACTION[primary],
            })
    if (sum(x["selected"] for x in batch_counts.values()) != 2500
            or sum(x["applied"] for x in batch_counts.values()) != 1371
            or len(all_rows) != 1129 or len({x["id"] for x in all_rows}) != 1129):
        raise ValueError(f"Phase 6 accounting mismatch: {batch_counts}, holds={len(all_rows)}")
    if set(x["id"] for x in all_rows) != {x["id"] for x in selected} - {
            x["id"] for n in range(1, 7) for x in
            (read(OUT / "ja_phase6_batch01_safe_input.json")["entries"] if n == 1 else
             [y for y in read(OUT / f"ja_phase6_batch{n:02}_reviewed.json")["entries"]
              if y["final_apply"]])}:
        raise ValueError("Master hold set differs from selected-minus-applied")
    return {
        "metadata": {"selected": 2500, "phase6_applied": 1371, "phase6_held": 1129,
                     "pre_phase6_applied": 677, "current_japanese_applied": 2048,
                     "batch_counts": {str(k): v for k, v in batch_counts.items()},
                     "primary_category_counts": dict(Counter(x["primary_hold"] for x in all_rows)),
                     "all_category_counts": dict(Counter(
                         h for x in all_rows for h in [x["primary_hold"], *x["secondary_holds"]])),
                     "priority_counts": dict(Counter(x["priority"] for x in all_rows)),
                     "rule": "Inventory only; no held entry resolved, translated or injected."},
        "entries": all_rows,
    }


def main():
    previous = ROOT / "out/unbound-ja-phase6-batch05.gba"
    current = ROOT / "out/unbound-ja-phase6-batch06.gba"
    dry = read(OUT / "ja_phase6_batch06_incremental_dry_run_map.json")
    built = read(OUT / "ja_phase6_batch06_incremental_map.json")
    full_dry = read(OUT / "ja_phase6_batch06_full_dry_run_map.json")
    strict_map(dry, built, 331)
    if full_dry["stats"]["input_entries"] != 2048:
        raise ValueError("Full dry-run entry count differs")
    previous_fixed = read(OUT / "ja_phase6_batch05_combined_controlfix.json")["entries"]
    safe = read(OUT / "ja_phase6_batch06_safe_controlfix.json")["entries"]
    merged = read(OUT / "ja_phase6_batch06_combined_controlfix.json")
    if len(previous_fixed) != 1717 or merged["entries"] != previous_fixed + safe:
        raise ValueError("Existing 1,717 controlfixed entries changed")
    if not all((OUT / "ja_phase6_batch06_combined_controlfix.json").read_bytes() ==
               (OUT / name).read_bytes() for name in (
                   "ja_phase6_batch06_safe_controlfix_rebuilt.json",
                   "ja_phase6_batch06_controlfix_twice.json")):
        raise ValueError("Controlfix rebuild/second pass is not byte-identical")
    earlier = (read(OUT / "ja_phase6_batch04_map.json")["relocations"]
               + read(OUT / "ja_phase6_batch05_incremental_map.json")["relocations"])
    incremental = audit_incremental(previous, current, safe, built, previous_fixed, earlier)
    combined_map = {**built, "relocations": earlier + built["relocations"],
                    "stats": {**built["stats"],
                              "pointer_writes": (read(OUT / "ja_phase6_batch04_map.json")["stats"]["pointer_writes"]
                                                 + read(OUT / "ja_phase6_batch05_incremental_map.json")["stats"]["pointer_writes"]
                                                 + built["stats"]["pointer_writes"])}}
    source_audit = audit_rom(ROOT / "rom/unbound.gba", current, merged, combined_map)
    if incremental["unexpected_byte_count"] or source_audit["unexpected_byte_count"]:
        raise ValueError("Unexpected ROM difference")
    write(OUT / "ja_phase6_batch06_incremental_audit.json", incremental)
    write(OUT / "ja_phase6_batch06_rom_audit.json", source_audit)
    reviewed = read(OUT / "ja_phase6_batch06_reviewed.json")["entries"]
    selected = [x for x in read(FIX / "ja_phase6_selection.json")["entries"]
                if x["batch_number"] == 6]
    write(FIX / "ja_phase6_batch06_runtime_qa.json", runtime_qa(reviewed, selected, safe, built))
    cleanup = inventory()
    write(OUT / "ja_phase6_final_cleanup_inventory.json", cleanup)
    print({"incremental_changed_bytes": incremental["changed_byte_count"],
           "incremental_classes": incremental["classified_changed_bytes"],
           "source_changed_bytes": source_audit["changed_byte_count"],
           "unexpected": 0, "QA": 36, "inventory": cleanup["metadata"]["phase6_held"],
           "priority": cleanup["metadata"]["priority_counts"]})


if __name__ == "__main__":
    main()
