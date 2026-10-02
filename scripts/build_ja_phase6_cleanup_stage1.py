#!/usr/bin/env python3
"""Conservative, reproducible Phase 6C-1 hold triage. No new translations."""

from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.pcs_text import Charmap
from lib.translation_glossary import load_glossary
from scripts.audit_ja_phase6_batch01_fit import line_widths
from scripts.build_ja_phase6_batch02 import owner_audit
from scripts.build_ja_phase6_batch05 import control_sequence
from scripts.build_ja_phase6_batch06 import interior_pointer_hits

OUT = ROOT / "out/phase6"
FIX = ROOT / "tests/fixtures"
CLASSES = {
    "DETERMINISTIC_SAFE", "DETERMINISTIC_FIX_REQUIRED", "CLAUDE_TRANSLATION",
    "CLAUDE_GLOSSARY", "CLAUDE_CONTEXT", "CODEX_INVESTIGATION",
    "RUNTIME_REVIEW", "KEEP_ENGLISH",
}
SOURCE_MD5 = "9cad8e771940e7f7094d13911552cef0"
BATCH06_SHA256 = "99e3a0fe0a2c84dee07a3ae6be68292e34344ff1378659b0b824a6e422f5182b"


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def validate_inventory(inventory, selection, applied):
    held = inventory["entries"]
    ids = [x["id"] for x in held]
    selected = {x["id"]: x for x in selection}
    applied_ids = {x["id"] for x in applied}
    assert len(ids) == len(set(ids)) == 1129
    assert len(selected) == 2500 and len(applied_ids) == 2048
    assert set(ids).isdisjoint(applied_ids)
    assert set(ids) == set(selected) - applied_ids
    for row in held:
        assert row["batch"] == selected[row["id"]]["batch_number"]
        assert row["primary_hold"] and isinstance(row["secondary_holds"], list)
        assert row["priority"] in {"P1", "P2", "P3"}
    assert Counter(x["batch"] for x in held) == Counter(
        {int(k): v["held"] for k, v in inventory["metadata"]["batch_counts"].items()}
    )
    return {"validated": True, "held_unique": 1129, "selection": 2500,
            "applied_unchanged": 2048, "overlap": 0,
            "batch_counts": dict(sorted(Counter(x["batch"] for x in held).items()))}


def width_class(row):
    reasons = " ".join(row["raw_hold_reasons"])
    category = row["category"]
    if "width_overflow" in reasons or "screen_width_overflow" in reasons:
        return "C_STATIC_OVERFLOW"
    if category == "battle_messages":
        return "B_DYNAMIC_WORST_CASE"
    if category in {"scripts", "plain_scripts"} and not row["secondary_holds"]:
        return "A_RUNTIME_UNVERIFIED_ONLY"
    return "D_STRUCTURED_OR_UNKNOWN"


def official_evidence():
    result = defaultdict(list)
    for batch in range(2, 7):
        path = OUT / f"ja_phase6_batch{batch:02d}_official_name_audit.json"
        if not path.exists():
            continue
        data = read(path)
        for item in data.get("entries", []):
            key = item.get("entry_id") or item.get("id")
            if key:
                result[key].append(item)
    return result


def normalized_official(items):
    if not items:
        return "NEEDS_HUMAN_TERM_REVIEW"
    states = []
    for item in items:
        state = item.get("verification_result") or item.get("verification class")
        if state is None:
            state = (item.get("PokeAPI result") or {}).get("status")
        states.append(str(state or "unknown").lower())
    if any("difference" in x for x in states):
        return "VERIFIED_DIFFERENCE"
    if states and all("exact" in x for x in states):
        return "VERIFIED_EXACT"
    if any("ambig" in x for x in states):
        return "AMBIGUOUS"
    if any("not_applicable" in x for x in states):
        return "NOT_APPLICABLE"
    if any("no_ja" in x for x in states):
        return "NO_JA_VALUE"
    if any("not_found" in x for x in states):
        return "NOT_FOUND"
    return "NEEDS_HUMAN_TERM_REVIEW"


def buffer_class(row, selected):
    buffers = selected["buffers"]
    if not buffers:
        return "UNRESOLVED"
    if any(x in {"[buffer1]", "[buffer2]", "[buffer3]"} for x in buffers):
        return "CALLER_DEPENDENT"
    if all(x in {"[player]", "[rival]"} for x in buffers):
        return "BUFFER_TYPE_PROVEN"
    if all(x in {"[attacker]", "[defender]", "[move]", "[ability]"} for x in buffers):
        return "BUFFER_TYPE_PROVEN"
    return "DYNAMIC_UNKNOWN"


def control_class(row, selection, review):
    if not row["candidate_japanese"]:
        return "D_INCOMPLETE"
    if row["batch"] == 6 and review:
        segments = review.get("source_segments")
        target = review.get("translated_segments")
        if (isinstance(segments, list) and isinstance(target, list)
                and len(segments) == len(target)
                and review.get("control_boundary_validation") == "pass"):
            return "B_SOURCE_SEGMENTS_UNIQUE"
    if row["category"] == "battle_messages":
        return "C_SEMANTIC_OR_GRAMMAR_CONFLICT"
    return "D_UNPROVEN_SEGMENTS"


def fa_class(row):
    reasons = " ".join(row["raw_hold_reasons"]).lower()
    if "semantic" in reasons or "FA_SEMANTIC_CONFLICT" in row["secondary_holds"]:
        return "FA_SEMANTIC_CONFLICT"
    if "context" in reasons:
        return "FA_CONTEXT"
    if "dynamic" in reasons or "width" in reasons:
        return "FA_DYNAMIC_WIDTH"
    if "terminal_fa" in reasons or "placement" in reasons:
        return "FA_CONTROL_UNKNOWN"
    return "FA_CONTROL_UNKNOWN"


def structured_class(selection):
    category = selection["category"]
    if selection["fixed"] or selection["no_relocation"]:
        return "fixed_row"
    if category.startswith("menu_"):
        return "unknown_structure"
    if category.startswith("tbl_") or selection.get("table_name"):
        return "table_field"
    return "unknown_structure"


def incomplete_class(row):
    value = row["candidate_japanese"] or ""
    reasons = " ".join(row["raw_hold_reasons"])
    if not value:
        return "empty_translation"
    if "unsupported" in reasons.lower():
        return "unsupported_glyph"
    if "partial" in reasons.lower() or "incomplete" in reasons.lower():
        return "partial_japanese"
    return "candidate_exists_but_unadopted"


def glossary_terms(rows, selection):
    approved = load_glossary(ROOT / "glossaries/ja.json", expected_language="ja")
    groups = defaultdict(lambda: {"affected_ids": set(), "batches": set(),
                                  "categories": set(), "example_sources": [],
                                  "proposals": set(), "types": set()})
    held_ids = {x["id"] for x in rows}
    for batch in range(1, 7):
        path = FIX / f"ja_phase6_batch{batch:02d}_glossary_candidates.json"
        if not path.exists():
            continue
        for candidate in read(path):
            english = candidate["source"]
            kind = candidate.get("type") or "unspecified"
            for key in candidate.get("affected_entry_ids", []):
                if key not in held_ids or english not in selection[key]["original"]:
                    continue
                group = groups[(english.casefold(), kind)]
                group["affected_ids"].add(key)
                group["batches"].add(batch)
                group["categories"].add(selection[key]["category"])
                group["types"].add(kind)
                group["proposals"].add(candidate.get("proposed_japanese") or "")
                if len(group["example_sources"]) < 3:
                    group["example_sources"].append(selection[key]["original"])
    terms = []
    for (english, kind), group in sorted(groups.items()):
        matches = [dict(source=t.source, target=t.target, kind=t.kind) for t in approved.terms
                   if t.source.casefold() == english]
        terms.append({"english_term": english, "candidate_japanese": sorted(group["proposals"]),
                      "term_type": kind, "categories": sorted(group["categories"]),
                      "affected_ids": sorted(group["affected_ids"]), "batches": sorted(group["batches"]),
                      "example_sources": group["example_sources"],
                      "scope_proposal": "entry_scoped_until_reviewed",
                      "existing_glossary_conflict": matches,
                      "official_source_state": "unverified_in_cleanup",
                      "requested_decision": "Approve exact term, Japanese form, and scope; do not auto-apply."})
    return terms


def triage():
    inventory = read(OUT / "ja_phase6_final_cleanup_inventory.json")
    selection_list = read(FIX / "ja_phase6_selection.json")["entries"]
    selection = {x["id"]: x for x in selection_list}
    baseline = read(OUT / "ja_phase6_batch06_combined_controlfix.json")["entries"]
    validation = validate_inventory(inventory, selection_list, baseline)
    rom = (ROOT / "rom/unbound.gba").read_bytes()
    assert hashlib.md5(rom).hexdigest() == SOURCE_MD5
    assert hashlib.sha256((ROOT / "out/unbound-ja-phase6-batch06.gba").read_bytes()).hexdigest() == BATCH06_SHA256
    held = inventory["entries"]
    pointer_selection = [selection[x["id"]] for x in held if x["primary_hold"] == "POINTER_OWNER"]
    owner = {x["id"]: x for x in owner_audit(pointer_selection, rom)["entries"]}
    interiors = interior_pointer_hits(rom, pointer_selection)
    official = official_evidence()
    reviews = {}
    for batch in range(1, 7):
        path = FIX / f"ja_phase6_batch{batch:02d}_claude_review.json"
        if path.exists():
            reviews.update({x["id"]: x for x in read(path) if isinstance(x, dict) and "id" in x})
    normalized = []
    for row in held:
        key, primary = row["id"], row["primary_hold"]
        source = selection[key]
        facts = {"raw_hold_reasons": row["raw_hold_reasons"],
                 "source_slot": source["slot_size"], "pointer_owners": source["pointer_owners"],
                 "renderer_group": source["renderer_group"], "buffers": source["buffers"],
                 "controls": source["controls"], "rom_offset": source["rom_offset"],
                 "fixed": source["fixed"], "no_relocation": source["no_relocation"]}
        resolution = "CODEX_INVESTIGATION"
        if primary == "WIDTH_LAYOUT":
            facts["width_class"] = width_class(row)
            resolution = ("DETERMINISTIC_SAFE" if facts["width_class"].startswith("A_")
                          else "RUNTIME_REVIEW" if facts["width_class"].startswith("B_")
                          else "CLAUDE_TRANSLATION" if facts["width_class"].startswith("C_")
                          else "CODEX_INVESTIGATION")
        elif primary == "OFFICIAL_NAME_UNRESOLVED":
            facts["official_class"] = normalized_official(official[key])
            facts["official_evidence"] = official[key]
            resolution = ("CODEX_INVESTIGATION" if facts["official_class"].startswith("VERIFIED_")
                          else "CLAUDE_GLOSSARY")
        elif primary == "UNKNOWN_BUFFER":
            facts["buffer_class"] = buffer_class(row, source)
            resolution = "CODEX_INVESTIGATION" if facts["buffer_class"] != "BUFFER_TYPE_PROVEN" else "CLAUDE_CONTEXT"
        elif primary == "CONTROL_BOUNDARY":
            facts["control_class"] = control_class(row, source, reviews.get(key))
            resolution = ("DETERMINISTIC_FIX_REQUIRED" if facts["control_class"].startswith("B_")
                          else "CLAUDE_TRANSLATION" if facts["control_class"].startswith(("C_", "D_INCOMPLETE"))
                          else "CODEX_INVESTIGATION")
        elif primary == "POINTER_OWNER":
            check = owner[key]
            facts["pointer_audit"] = check
            facts["interior_hits"] = interiors[key]
            facts["pointer_class"] = ("complete_exact_no_interior" if not check["missing"] and not check["stale"]
                                      and not interiors[key] else "unresolved_owner_or_interior")
        elif primary == "STRUCTURED_UI":
            facts["structured_class"] = structured_class(source)
        elif primary == "INCOMPLETE_TRANSLATION":
            facts["incomplete_class"] = incomplete_class(row)
            resolution = "CLAUDE_TRANSLATION"
        elif primary == "GLOSSARY_APPROVAL":
            resolution = "CLAUDE_GLOSSARY"
        elif primary == "CONTEXT_REQUIRED":
            resolution = "CLAUDE_CONTEXT"
        elif primary == "FA_LAYOUT":
            facts["fa_class"] = fa_class(row)
            resolution = "CLAUDE_TRANSLATION" if facts["fa_class"] == "FA_SEMANTIC_CONFLICT" else "CODEX_INVESTIGATION"
        elif primary == "OTHER":
            if row["raw_hold_reasons"] == ["no_japanese_change"]:
                facts["reclassified_as"] = "unchanged_latin_label"
                resolution = "KEEP_ENGLISH"
            else:
                facts["reclassified_as"] = "technical_fit_or_structured_layout"
        assert resolution in CLASSES
        normalized.append({"id": key, "batch": row["batch"], "category": row["category"],
                           "original": row["original"], "candidate_japanese": row["candidate_japanese"],
                           "priority": row["priority"], "previous_primary_hold": primary,
                           "previous_secondary_holds": row["secondary_holds"],
                           "normalized_technical_facts": facts, "resolution_class": resolution,
                           "deterministic": resolution.startswith("DETERMINISTIC_"),
                           "final_current_status": "held", "next_queue": None,
                           "apply_status": "not_applied"})
    assert len(normalized) == 1129
    write(OUT / "ja_phase6_final_cleanup_inventory_v2.json", {
        "metadata": {**validation, "resolution_counts": dict(Counter(x["resolution_class"] for x in normalized)),
                     "rule": "Triage only; deterministic candidates require strict controlfix/inject gate."},
        "entries": normalized})
    glossary = glossary_terms(held, selection)
    write(OUT / "ja_phase6_cleanup_for_claude_glossary.json", {
        "metadata": {"term_count": len(glossary), "approved": 0}, "terms": glossary})
    return normalized


def prepare_candidates():
    rows = triage()
    selection = {x["id"]: x for x in read(FIX / "ja_phase6_selection.json")["entries"]}
    prepared = {x["id"]: x for x in read(ROOT / "out/ja-phase5e-prepared.json")["entries"]}
    baseline = read(OUT / "ja_phase6_batch06_combined_controlfix.json")["entries"]
    codec = Charmap("ja")
    injector = runpy.run_path(str(ROOT / "005_hybrid_injector.py"))
    rom = (ROOT / "rom/unbound.gba").read_bytes()
    normal, no_wrap, rejected = [], [], []
    review = {x["id"]: x for x in read(FIX / "ja_phase6_batch06_claude_review.json")}
    for row in rows:
        key = row["id"]
        if row["resolution_class"] not in {"DETERMINISTIC_SAFE", "DETERMINISTIC_FIX_REQUIRED"}:
            continue
        source = selection[key]
        candidate = row["candidate_japanese"]
        if row["resolution_class"] == "DETERMINISTIC_FIX_REQUIRED":
            item = review.get(key, {})
            if item.get("reviewed_japanese") != candidate:
                rejected.append({"id": key, "reason": "review_candidate_difference"})
                continue
            parts = item.get("translated_segments", [])
            src_parts = item.get("source_segments", [])
            if not parts or len(parts) != len(src_parts):
                rejected.append({"id": key, "reason": "segment_mapping_missing"})
                continue
            if source["category"] == "move_descriptions":
                max_lines, max_pixels, max_chars = 6, 122, None
            elif source["category"] == "pokedex_descriptions":
                max_lines, max_pixels, max_chars = 3, 239, 43
            elif source["category"] == "item_descriptions":
                max_lines, max_pixels, max_chars = 3, 239, 34
            elif source["category"] == "ability_descriptions":
                max_lines, max_pixels, max_chars = 1, 191, 34
            else:
                rejected.append({"id": key, "reason": "unproved_renderer"})
                continue
            try:
                raw = injector["encode_text"](codec, "[japanese]" + candidate + "[latin]",
                                              plain_script=False)
            except (UnicodeEncodeError, ValueError) as exc:
                rejected.append({"id": key, "reason": "encode_error", "detail": str(exc)})
                continue
            widths = line_widths(raw)
            visible_lines = candidate.replace("\\n", "\n").split("\n")
            if (len(widths) > max_lines or max(widths, default=0) > max_pixels
                    or (max_chars is not None and any(len(x) > max_chars for x in visible_lines))):
                rejected.append({"id": key, "reason": "proven_static_layout_overflow",
                                 "line_pixels": widths})
                continue
            source_bytes = rom[source["rom_offset"]:source["rom_offset"] + source["source_encoded_size"]]
            if control_sequence(source_bytes) != control_sequence(raw):
                rejected.append({"id": key, "reason": "raw_control_mismatch"})
                continue
        entry = dict(prepared[key])
        entry["translated"] = "[japanese]" + candidate + "[latin]"
        (no_wrap if row["resolution_class"] == "DETERMINISTIC_FIX_REQUIRED" else normal).append(entry)
    write(OUT / "ja_phase6_cleanup_candidate_normal_input.json", {"entries": baseline + normal})
    write(OUT / "ja_phase6_cleanup_candidate_control_input.json", {"entries": baseline + no_wrap})
    write(OUT / "ja_phase6_cleanup_candidate_rejections.json", {"entries": rejected})
    return {"normal": len(normal), "source_segment": len(no_wrap), "rejected": len(rejected)}


def finalize_candidates():
    inventory = read(OUT / "ja_phase6_final_cleanup_inventory_v2.json")
    rows = inventory["entries"]
    selection = {x["id"]: x for x in read(FIX / "ja_phase6_selection.json")["entries"]}
    baseline = read(OUT / "ja_phase6_batch06_combined_controlfix.json")["entries"]
    normal = read(OUT / "ja_phase6_cleanup_candidate_normal_controlfix.json")["entries"]
    control = read(OUT / "ja_phase6_cleanup_candidate_control_controlfix.json")["entries"]
    assert normal[:2048] == control[:2048] == baseline
    candidates = {x["id"]: x for x in normal[2048:] + control[2048:]}
    assert len(candidates) == len(normal[2048:]) + len(control[2048:])
    all_selected = [selection[x] for x in candidates]
    rom = (ROOT / "rom/unbound.gba").read_bytes()
    owners = {x["id"]: x for x in owner_audit(all_selected, rom)["entries"]}
    interiors = interior_pointer_hits(rom, all_selected)
    codec = Charmap("ja")
    injector = runpy.run_path(str(ROOT / "005_hybrid_injector.py"))
    safe, rejected = [], []
    for row in rows:
        key = row["id"]
        if key not in candidates:
            continue
        entry, source = candidates[key], selection[key]
        failures = []
        try:
            payload = injector["encode_text"](codec, injector["translation_for_injection"](entry),
                                              plain_script=source["category"] == "plain_scripts")
        except (UnicodeEncodeError, ValueError) as exc:
            payload = b""
            failures.append(f"encode:{exc}")
        raw = rom[source["rom_offset"]:source["rom_offset"] + source["source_encoded_size"]]
        if payload and control_sequence(raw) != control_sequence(payload):
            failures.append("source_control_sequence_changed")
        if payload and max(line_widths(payload), default=0) >= 240:
            failures.append("physical_screen_width_overflow")
        if payload and len(payload) > source["slot_size"]:
            if source["fixed"] or source["no_relocation"] or not source["relocation_possible"]:
                failures.append("fixed_or_no_relocation_overflow")
            if owners[key]["missing"] or owners[key]["stale"]:
                failures.append("pointer_owner_unproved")
            if interiors[key]:
                failures.append("interior_pointer_unproved")
            if not source["pointer_owners"]:
                failures.append("no_pointer_owner")
        if row["resolution_class"] == "DETERMINISTIC_FIX_REQUIRED":
            # The source FE segmentation is exact only if the no-wrap output kept it.
            if entry["translated"] != "[japanese]" + row["candidate_japanese"] + "[latin]":
                failures.append("segment_reconstruction_changed_candidate")
        row["normalized_technical_facts"]["gate"] = {
            "encoded_bytes": len(payload), "line_pixels": line_widths(payload) if payload else [],
            "fit": "in_place" if payload and len(payload) <= source["slot_size"] else "relocation",
            "owner_missing": owners[key]["missing"], "owner_stale": owners[key]["stale"],
            "interior_hits": interiors[key], "failures": failures,
        }
        if failures:
            row["resolution_class"] = "CODEX_INVESTIGATION"
            row["deterministic"] = False
            rejected.append({"id": key, "failures": failures})
        else:
            safe.append(entry)
            row["final_current_status"] = "deterministic_safe_ready"
            row["apply_status"] = "approved_for_strict_dry_run"
    write(OUT / "ja_phase6_final_cleanup_inventory_v2.json", inventory)
    write(OUT / "ja_phase6_cleanup_gate_rejections.json", {"entries": rejected})
    write(OUT / "ja_phase6_cleanup_safe_controlfix.json", {"entries": safe})
    write(OUT / "ja_phase6_cleanup_combined_controlfix.json", {"entries": baseline + safe})
    return {"safe": len(safe), "rejected": len(rejected),
            "in_place": sum(x["normalized_technical_facts"]["gate"]["fit"] == "in_place"
                            for x in rows if x["apply_status"] == "approved_for_strict_dry_run"),
            "relocation": sum(x["normalized_technical_facts"]["gate"]["fit"] == "relocation"
                              for x in rows if x["apply_status"] == "approved_for_strict_dry_run")}


def ranges(positions):
    data = sorted(positions)
    if not data:
        return []
    result = []
    start = last = data[0]
    for pos in data[1:]:
        if pos != last + 1:
            result.append(f"0x{start:08X}-0x{last:08X}")
            start = pos
        last = pos
    result.append(f"0x{start:08X}-0x{last:08X}")
    return result


def assert_strict_map(plan, built, input_count):
    assert plan["stats"] == built["stats"]
    assert plan["relocations"] == built["relocations"]
    assert built["stats"]["input_entries"] == input_count
    for key in ("skipped_pointer_mismatch", "skipped_implausible_pointer", "skipped_no_space",
                "encode_errors", "fixed_truncated", "no_relocation_truncated",
                "ability_descriptions_compacted", "runtime_patches", "graphics_patches",
                "skipped_unsafe", "skipped_bounds"):
        assert built["stats"][key] == 0, (key, built["stats"][key])
    assert not built["missing_relocations"] and not built["missing_fixed_slots"]
    assert not built["runtime_patches"] and not built["graphics_patches"]


def audit_rom():
    before_path = ROOT / "out/unbound-ja-phase6-batch06.gba"
    after_path = ROOT / "out/unbound-ja-phase6-cleanup-codex.gba"
    before, after = before_path.read_bytes(), after_path.read_bytes()
    assert len(before) == len(after) == 0x2000000
    assert hashlib.sha256(before).hexdigest() == BATCH06_SHA256
    plan = read(OUT / "ja_phase6_cleanup_incremental_dry_run_map.json")
    built = read(OUT / "ja_phase6_cleanup_incremental_map.json")
    assert_strict_map(plan, built, 170)
    full = read(OUT / "ja_phase6_cleanup_full_dry_run_map.json")
    for key in ("skipped_pointer_mismatch", "skipped_implausible_pointer", "skipped_no_space",
                "encode_errors", "fixed_truncated", "no_relocation_truncated",
                "ability_descriptions_compacted", "runtime_patches", "graphics_patches"):
        assert full["stats"][key] == 0
    safe = read(OUT / "ja_phase6_cleanup_safe_controlfix.json")["entries"]
    baseline = read(OUT / "ja_phase6_batch06_combined_controlfix.json")["entries"]
    assert read(OUT / "ja_phase6_cleanup_combined_controlfix.json")["entries"][:2048] == baseline
    assert len(safe) == 170 and len(baseline) == 2048
    relocated = {x["id"]: x for x in built["relocations"]}
    codec = Charmap("ja")
    injector = runpy.run_path(str(ROOT / "005_hybrid_injector.py"))
    allowed = {"in_place_text": set(), "relocated_text": set(), "pointer_writes": set()}
    for entry in safe:
        key = entry["id"]
        raw = injector["encode_text"](codec, injector["translation_for_injection"](entry),
                                      plain_script=entry["category"] == "plain_scripts")
        old, size = int(entry["address"], 16), entry["byte_length"]
        move = relocated.get(key)
        if move:
            new = int(move["new_offset"], 16)
            assert move["storage"] == "vetted_ff" and move["byte_length"] == len(raw)
            assert after[new:new+len(raw)] == raw and before[new:new+len(raw)] == b"\xff" * len(raw)
            allowed["relocated_text"].update(range(new, new+len(raw)))
            for pointer in move["pointer_sources"]:
                pos = int(pointer, 16)
                assert before[pos:pos+4] == (0x08000000 + old).to_bytes(4, "little")
                assert after[pos:pos+4] == (0x08000000 + new).to_bytes(4, "little")
                allowed["pointer_writes"].update(range(pos, pos+4))
        else:
            assert len(raw) <= size and after[old:old+size] == raw.ljust(size, b"\xff")
            allowed["in_place_text"].update(range(old, old+size))
    previous_maps = [OUT / "ja_phase6_batch04_map.json",
                     OUT / "ja_phase6_batch05_incremental_map.json",
                     OUT / "ja_phase6_batch06_incremental_map.json"]
    old_relocations = {}
    for path in previous_maps:
        old_relocations.update({x["id"]: x for x in read(path)["relocations"]})
    protected = set()
    for entry in baseline:
        key = entry["id"]
        old = old_relocations.get(key)
        if old:
            pos = int(old["new_offset"], 16)
            protected.update(range(pos, pos+old["byte_length"]))
            for pointer in old["pointer_sources"]:
                p = int(pointer, 16)
                protected.update(range(p, p+4))
        else:
            pos = int(entry["address"], 16)
            protected.update(range(pos, pos+entry["byte_length"]))
    allowed_all = set().union(*allowed.values())
    assert not protected & allowed_all, "cleanup overlaps existing translation storage"
    for a, b in (("in_place_text", "relocated_text"), ("in_place_text", "pointer_writes"),
                 ("relocated_text", "pointer_writes")):
        assert not allowed[a] & allowed[b], (a, b)
    changed = {i for i, (x, y) in enumerate(zip(before, after)) if x != y}
    unexpected = changed - allowed_all
    assert not changed & protected, f"existing translations changed: {ranges(changed & protected)[:5]}"
    assert not unexpected, f"unexpected bytes: {ranges(unexpected)[:5]}"
    result = {"status": "PASS", "batch06_sha256": hashlib.sha256(before).hexdigest(),
              "cleanup_md5": hashlib.md5(after).hexdigest(),
              "cleanup_sha256": hashlib.sha256(after).hexdigest(),
              "existing_2048_unchanged": True, "changed_bytes": len(changed),
              "changed_ranges": ranges(changed),
              "classified_changed_bytes": {name: len(changed & area) for name, area in allowed.items()},
              "classified_ranges": {name: ranges(changed & area) for name, area in allowed.items()},
              "unexpected_bytes": 0, "relocated": len(relocated),
              "pointer_writes": built["stats"]["pointer_writes"],
              "strict_full_dry_run": "PASS", "strict_incremental_dry_run": "PASS"}
    write(OUT / "ja_phase6_cleanup_binary_audit.json", result)
    inventory = read(OUT / "ja_phase6_final_cleanup_inventory_v2.json")
    safe_ids = {x["id"] for x in safe}
    for row in inventory["entries"]:
        if row["id"] in safe_ids:
            row["apply_status"] = "applied"
            row["final_current_status"] = "applied_deterministically"
    inventory["metadata"]["resolution_counts"] = dict(Counter(x["resolution_class"] for x in inventory["entries"]))
    inventory["metadata"]["deterministic_applied"] = len(safe_ids)
    write(OUT / "ja_phase6_final_cleanup_inventory_v2.json", inventory)
    return {k: result[k] for k in ("status", "changed_bytes", "classified_changed_bytes",
                                     "unexpected_bytes", "cleanup_sha256")}


def make_handoff():
    inventory = read(OUT / "ja_phase6_final_cleanup_inventory_v2.json")
    rows = inventory["entries"]
    selection = {x["id"]: x for x in read(FIX / "ja_phase6_selection.json")["entries"]}
    reviews = {}
    verified_entities = defaultdict(list)
    for audit_rows in official_evidence().values():
        for evidence in audit_rows:
            if normalized_official([evidence]) != "VERIFIED_EXACT":
                continue
            english = evidence.get("source_term") or evidence.get("English term")
            kind = evidence.get("term_type") or evidence.get("type")
            entity = evidence.get("pokeapi_entity")
            japanese = evidence.get("pokeapi_japanese") or evidence.get("final_value")
            if english and kind and entity and japanese:
                verified_entities[(english, kind, entity)].append(japanese)
    for batch in range(1, 7):
        path = FIX / f"ja_phase6_batch{batch:02d}_claude_review.json"
        if path.exists():
            reviews.update({x["id"]: x for x in read(path) if isinstance(x, dict) and "id" in x})
    pre_rejected = {x["id"]: x["reason"] for x in read(
        OUT / "ja_phase6_cleanup_candidate_rejections.json")["entries"]}
    for row in rows:
        if row["apply_status"] == "applied":
            continue
        key = row["id"]
        facts = row["normalized_technical_facts"]
        if row["previous_primary_hold"] == "POINTER_OWNER":
            pointer = facts["pointer_audit"]
            facts["pointer_reference_details"] = {
                "direct_recorded_owners": pointer["recorded"],
                "duplicate_exact_hits": pointer["missing"],
                "recorded_owner_kinds": pointer["owner_kinds"],
                "additional_exact_hit_kinds": pointer["missing_kinds"],
                "interior_pointer_hits": facts["interior_hits"],
                "table_reference": bool(selection[key].get("table_name")),
                "computed_reference": "not_proven_or_disproved",
                "relocation_safety": "unproved; keep English",
            }
        if row["previous_primary_hold"] == "OFFICIAL_NAME_UNRESOLVED":
            cross = []
            for evidence in facts["official_evidence"]:
                english = evidence.get("source_term") or evidence.get("English term")
                kind = evidence.get("term_type") or evidence.get("type")
                entity = evidence.get("pokeapi_entity")
                values = set(verified_entities.get((english, kind, entity), []))
                if values:
                    cross.append({"english_exact": english, "entity_type": kind,
                                  "entity": entity, "verified_japanese": sorted(values),
                                  "propagated_into_candidate": False})
            facts["cross_entry_entity_evidence"] = cross
        if row["previous_primary_hold"] == "FA_LAYOUT":
            facts["fa_class"] = fa_class({"raw_hold_reasons": facts["raw_hold_reasons"],
                                          "secondary_holds": row["previous_secondary_holds"]})
        if key in pre_rejected:
            facts["pre_gate_rejection"] = pre_rejected[key]
            row["resolution_class"] = ("CLAUDE_TRANSLATION" if pre_rejected[key] in {
                "proven_static_layout_overflow", "segment_mapping_missing"}
                                       else "CODEX_INVESTIGATION")
        gate_failures = facts.get("gate", {}).get("failures", [])
        if "physical_screen_width_overflow" in gate_failures:
            row["resolution_class"] = "CLAUDE_TRANSLATION"
        elif any(x in gate_failures for x in ("source_control_sequence_changed", "interior_pointer_unproved")):
            row["resolution_class"] = "CODEX_INVESTIGATION"
        if row["previous_primary_hold"] == "OFFICIAL_NAME_UNRESOLVED":
            if facts["official_class"] == "VERIFIED_EXACT" and not row["candidate_japanese"]:
                row["resolution_class"] = "CLAUDE_TRANSLATION"
        if row["previous_primary_hold"] == "UNKNOWN_BUFFER" and not row["candidate_japanese"]:
            row["resolution_class"] = "CLAUDE_CONTEXT"
        if row["previous_primary_hold"] == "CONTROL_BOUNDARY" and facts["control_class"] == "B_SOURCE_SEGMENTS_UNIQUE":
            # Source segments are proved, but the existing candidate can still fail fit.
            if key in pre_rejected:
                row["resolution_class"] = "CLAUDE_TRANSLATION"
        if row["previous_primary_hold"] == "FA_LAYOUT" and facts["fa_class"] == "FA_SEMANTIC_CONFLICT":
            row["resolution_class"] = "CLAUDE_TRANSLATION"
        if row["previous_primary_hold"] == "POINTER_OWNER" and not row["candidate_japanese"]:
            row["resolution_class"] = "CLAUDE_TRANSLATION"
        row["deterministic"] = row["resolution_class"] in {
            "DETERMINISTIC_SAFE", "DETERMINISTIC_FIX_REQUIRED"}
        row["next_queue"] = {
            "CLAUDE_TRANSLATION": "claude_translation",
            "CLAUDE_CONTEXT": "claude_translation",
            "CLAUDE_GLOSSARY": "claude_glossary",
            "CODEX_INVESTIGATION": "codex_investigation",
            "RUNTIME_REVIEW": "runtime_review",
        }.get(row["resolution_class"])
        row["final_current_status"] = "held_classified"
    classes = Counter(x["resolution_class"] for x in rows)
    assert len(rows) == 1129 and sum(classes.values()) == 1129
    assert all(x["resolution_class"] in CLASSES for x in rows)
    assert sum(x["apply_status"] == "applied" for x in rows) == 170
    assert all(x["apply_status"] == "applied" for x in rows if x["deterministic"])
    inventory["metadata"]["resolution_counts"] = dict(classes)
    inventory["metadata"]["deterministic_applied"] = 170
    write(OUT / "ja_phase6_final_cleanup_inventory_v2.json", inventory)

    translation, investigation, runtime = [], [], []
    for row in rows:
        if row["apply_status"] == "applied":
            continue
        source = selection[row["id"]]
        facts = row["normalized_technical_facts"]
        common = {"id": row["id"], "batch": row["batch"], "category": row["category"],
                  "original": row["original"], "candidate": row["candidate_japanese"],
                  "exact_reason": facts["raw_hold_reasons"],
                  "previous_primary_hold": row["previous_primary_hold"],
                  "secondary_holds": row["previous_secondary_holds"],
                  "context": {"speaker": source["speaker"], "speaker_confidence": source["speaker_confidence"],
                              "scene_id": source["scene_id"], "conversation_id": source["conversation_id"],
                              "context_before": source["context_before"],
                              "context_after": source["context_after"],
                              "runtime_evidence": source["runtime_evidence"]},
                  "controls": source["controls"], "buffers": source["buffers"],
                  "known_technical_constraints": {"rom_offset": source["rom_offset"],
                                                  "slot_size": source["slot_size"],
                                                  "fixed": source["fixed"],
                                                  "no_relocation": source["no_relocation"],
                                                  "pointer_owners": source["pointer_owners"],
                                                  "normalized_facts": facts}}
        if row["resolution_class"] in {"CLAUDE_TRANSLATION", "CLAUDE_CONTEXT"}:
            translation.append({**common, "requested_claude_task": (
                "Review context and wording; preserve source controls and named buffers. No approval inferred."
                if row["resolution_class"] == "CLAUDE_CONTEXT" else
                "Provide complete kana-only wording satisfying documented controls, terms, and fit.")})
        elif row["resolution_class"] == "CODEX_INVESTIGATION":
            investigation.append({**common, "requested_codex_task":
                                  "Prove remaining mechanics using ROM/script/renderer evidence; do not translate."})
        elif row["resolution_class"] == "RUNTIME_REVIEW":
            runtime.append({**common, "requested_runtime_task":
                            "Measure dynamic-value maximum and typical display in the actual renderer."})
    write(OUT / "ja_phase6_cleanup_for_claude_translation.json", {
        "metadata": {"entries": len(translation), "no_new_translation_generated": True},
        "entries": translation})
    write(OUT / "ja_phase6_cleanup_for_codex_investigation.json", {
        "metadata": {"entries": len(investigation)}, "entries": investigation})
    write(OUT / "ja_phase6_cleanup_runtime_review.json", {
        "metadata": {"entries": len(runtime), "rule": "Only dynamic worst-case renderer values."},
        "entries": runtime})

    terms = read(OUT / "ja_phase6_cleanup_for_claude_glossary.json")["terms"]
    term_keys = {(x["english_term"].casefold(), x["term_type"]) for x in terms}
    grouped = defaultdict(lambda: {"ids": set(), "batches": set(), "categories": set(),
                                  "sources": [], "proposals": set(), "states": set(), "entity": set()})
    for row in rows:
        if row["resolution_class"] != "CLAUDE_GLOSSARY":
            continue
        facts = row["normalized_technical_facts"]
        for evidence in facts.get("official_evidence", []):
            state = normalized_official([evidence])
            if state == "VERIFIED_EXACT":
                continue
            english = evidence.get("source_term") or evidence.get("English term")
            kind = evidence.get("term_type") or evidence.get("type") or "unclassified"
            if not english:
                continue
            group = grouped[(english, kind)]
            group["ids"].add(row["id"])
            group["batches"].add(row["batch"])
            group["categories"].add(row["category"])
            group["sources"].append(row["original"])
            group["proposals"].add(evidence.get("proposed_japanese") or evidence.get("provisional_japanese") or "")
            group["states"].add(state)
            if evidence.get("pokeapi_entity"):
                group["entity"].add(evidence["pokeapi_entity"])
    for (english, kind), group in sorted(grouped.items()):
        if (english.casefold(), kind) in term_keys:
            term = next(x for x in terms if x["english_term"].casefold() == english.casefold()
                        and x["term_type"] == kind)
            term["affected_ids"] = sorted(set(term["affected_ids"]) | group["ids"])
            term["batches"] = sorted(set(term["batches"]) | group["batches"])
            term["categories"] = sorted(set(term["categories"]) | group["categories"])
            term["official_source_state"] = sorted(group["states"])
            term["exact_pokeapi_entities"] = sorted(group["entity"])
        else:
            terms.append({"english_term": english, "candidate_japanese": sorted(group["proposals"]),
                          "term_type": kind, "categories": sorted(group["categories"]),
                          "affected_ids": sorted(group["ids"]), "batches": sorted(group["batches"]),
                          "example_sources": list(dict.fromkeys(group["sources"]))[:3],
                          "scope_proposal": "exact_term_and_entity_only",
                          "existing_glossary_conflict": [],
                          "official_source_state": sorted(group["states"]),
                          "exact_pokeapi_entities": sorted(group["entity"]),
                          "requested_decision": "Verify term identity, Japanese form, and scope; do not auto-apply."})
    terms.sort(key=lambda x: (x["english_term"].casefold(), x["term_type"]))
    assert len({(x["english_term"].casefold(), x["term_type"]) for x in terms}) == len(terms)
    covered_ids = {key for term in terms for key in term["affected_ids"]}
    entry_scope_reviews = []
    for row in rows:
        if row["resolution_class"] != "CLAUDE_GLOSSARY" or row["id"] in covered_ids:
            continue
        entry_scope_reviews.append({"id": row["id"], "batch": row["batch"],
                                    "category": row["category"], "original": row["original"],
                                    "candidate": row["candidate_japanese"],
                                    "review_reason": reviews.get(row["id"], {}).get("reason"),
                                    "official_state": row["normalized_technical_facts"].get("official_class"),
                                    "requested_decision":
                                    "Identify the exact term and entity/scope before term-level approval."})
    glossary_class_ids = {x["id"] for x in rows if x["resolution_class"] == "CLAUDE_GLOSSARY"}
    assert glossary_class_ids <= covered_ids | {x["id"] for x in entry_scope_reviews}
    write(OUT / "ja_phase6_cleanup_for_claude_glossary.json", {
        "metadata": {"term_count": len(terms), "affected_entries": len(covered_ids | {x["id"] for x in entry_scope_reviews}),
                     "glossary_class_entries": classes["CLAUDE_GLOSSARY"],
                     "term_identification_needed_entries": len(entry_scope_reviews),
                     "approved": 0, "rule": "Exact English term + entity type; no substring propagation."},
        "terms": terms, "entry_scope_reviews": entry_scope_reviews})
    return {"classes": dict(classes), "translation_queue": len(translation),
            "glossary_terms": len(terms), "investigation_queue": len(investigation),
            "runtime_queue": len(runtime)}


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "prepare":
        print(prepare_candidates())
    elif len(sys.argv) == 2 and sys.argv[1] == "finalize":
        print(finalize_candidates())
    elif len(sys.argv) == 2 and sys.argv[1] == "audit":
        print(audit_rom())
    elif len(sys.argv) == 2 and sys.argv[1] == "handoff":
        print(make_handoff())
    else:
        print(Counter(x["resolution_class"] for x in triage()))
