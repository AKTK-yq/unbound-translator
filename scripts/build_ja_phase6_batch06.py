#!/usr/bin/env python3
"""Fail-closed Phase 6 Batch 06 review, control and injection inputs."""

from __future__ import annotations

from bisect import bisect_right
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import runpy
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.fa_control import join_segments, parse_raw_segments
from lib.pcs_text import Charmap
from lib.translation_glossary import load_glossary
from lib.translation_tokens import semantic_tokens
from scripts.build_ja_phase6_batch02 import owner_audit
from scripts.build_ja_phase6_batch05 import control_sequence
from scripts.audit_ja_phase6_batch01_fit import line_widths

OUT = ROOT / "out/phase6"
FIX = ROOT / "tests/fixtures"
SOURCE_MD5 = "9cad8e771940e7f7094d13911552cef0"
BATCH05_SHA256 = "dcb2b8813cc1257001f38586b5a214bccae24e29a3812f47c4a897fbfef9ec73"
STATUS_COUNTS = {"confirmed": 214, "existing_official": 212,
                 "existing_glossary": 29, "needs_context": 6}
HAN = re.compile(r"[㐀-鿿]")
APPROVED = {"confirmed", "existing_official", "existing_glossary"}


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def inputs():
    rom = (ROOT / "rom/unbound.gba").read_bytes()
    if hashlib.md5(rom).hexdigest() != SOURCE_MD5:
        raise ValueError("Source ROM MD5 differs")
    if hashlib.sha256((ROOT / "out/unbound-ja-phase6-batch05.gba").read_bytes()).hexdigest() != BATCH05_SHA256:
        raise ValueError("Batch 05 ROM SHA-256 differs")
    review = read(FIX / "ja_phase6_batch06_claude_review.json")
    source = read(OUT / "ja_phase6_batch06_for_claude.json")["entries"]
    selected = [x for x in read(FIX / "ja_phase6_selection.json")["entries"]
                if x["batch_number"] == 6]
    baseline = read(OUT / "ja_phase6_batch05_combined_controlfix.json")["entries"]
    if len(baseline) != 1717:
        raise ValueError("Existing applied count differs")
    return rom, review, source, selected, baseline


def validate(rom, review, source, selected):
    ids = [x["id"] for x in review]
    if (len(ids), len(set(ids))) != (461, 461) or ids != [x["id"] for x in source] or (
            set(ids) != {x["id"] for x in selected}):
        raise ValueError("Batch 06 ID count/order/selection differs")
    if Counter(x["status"] for x in review) != STATUS_COUNTS:
        raise ValueError("Review status counts differ")
    if read(FIX / "ja_phase6_batch06_fa_claude_review.json") != []:
        raise ValueError("FA fixture unexpectedly nonempty")
    codec = Charmap("ja")
    by_selection = {x["id"]: x for x in selected}
    failures = []
    fe = 0
    official = glossary = 0
    for row, src in zip(review, source):
        key = row["id"]
        sel = by_selection[key]
        errors = []
        if row["original"] != src["original"] or row["original"] != sel["original"]:
            errors.append("original")
        if row["category"] != src["category"] or row["category"] != sel["category"]:
            errors.append("category")
        if row["review_source"] != "claude_cli":
            errors.append("review_source")
        if row["source_controls"] != src["controls"] or row["source_controls"] != sel["controls"]:
            errors.append("controls")
        if row["protected_tokens_source"] != src["protected_tokens"]:
            errors.append("protected_metadata")
        if row["conversation_id"] != src["conversation_id"] or row["scene_id"] != src["scene_id"]:
            errors.append("context_metadata")
        raw = rom[sel["rom_offset"]:sel["rom_offset"] + sel["source_encoded_size"]]
        try:
            segments = parse_raw_segments(raw, rom_offset=sel["rom_offset"])
        except ValueError:
            errors.append("raw_source_parse")
            segments = []
        if segments != row["source_segments"] or join_segments(segments) != row["original"].strip('"'):
            errors.append("source_segments")
        controls = [s["after_control"] for s in segments if s["after_control"]]
        fe += controls.count("FE")
        if controls != row["source_boundary_sequence"] or any(x in {"FA", "FB"} for x in controls):
            errors.append("source_boundaries")
        target = row["reviewed_japanese"]
        if target:
            parts = row["translated_segments"]
            if len(parts) != len(segments) or join_segments(segments, parts) != target:
                errors.append("target_segments")
            for a, b in zip(segments, parts):
                if semantic_tokens(a["text"]) != semantic_tokens(b):
                    errors.append("protected_tokens")
                if any(mark in b for mark in ("\n", "\\l", "\\p")):
                    errors.append("inserted_boundary")
            if HAN.search(target):
                errors.append("kanji")
            try:
                encoded = codec.encode("[japanese]" + target + "[latin]")
                if control_sequence(raw) != control_sequence(encoded):
                    errors.append("control_sequence")
            except (UnicodeEncodeError, ValueError):
                errors.append("pcs_encode")
            if row["control_boundary_validation"] != "pass":
                errors.append("control_review")
        elif row["status"] != "needs_context" or row["control_boundary_validation"] != "held_not_adopted":
            errors.append("empty_nonhold")
        if row["status"] == "existing_official":
            official += 1
            deterministic = src.get("deterministic_translation")
            if (src.get("deterministic_origin") != "pokeapi-ja-hrkt"
                    or not src.get("official_terms")
                    or "".join(target.split()) != "".join((deterministic or "").split())):
                errors.append("official_provenance")
        if row["status"] == "existing_glossary":
            glossary += 1
            if src.get("deterministic_origin") not in {"glossary-exact", None}:
                errors.append("glossary_provenance")
        if errors:
            failures.append({"id": key, "issues": sorted(set(errors))})
    if fe != 254 or official != 212 or glossary != 29 or failures:
        raise ValueError(f"Review validation failed: FE={fe}, official={official}, glossary={glossary}, {failures[:8]}")
    return {"reviewed": 461, "unique_ids": 461, "duplicate": 0, "extra": 0,
            "review_source": {"claude_cli": 461}, "status_counts": STATUS_COUNTS,
            "nonempty": 455, "empty": 6, "FA": 0, "FE": fe,
            "protected_control_kanji_pcs_errors": 0}


def glossary_audit(review, selected):
    matcher = load_glossary(ROOT / "glossaries/ja.json", expected_language="ja")
    by_source = {x["id"]: x for x in selected}
    claims = []
    for row in review:
        source = by_source[row["id"]]
        source_text = source["translation_source"]
        matched = matcher.matches(source_text, row["category"], entry_id=row["id"])
        approved = {value for start, end, term in matched
                    for value in (term.source, source_text[start:end])}
        used = set(row["glossary_terms_used"])
        missing = matcher.missing_targets(source["translation_source"],
                                          row["reviewed_japanese"], row["category"],
                                          entry_id=row["id"]) if row["reviewed_japanese"] else []
        scoped = used <= approved and not missing
        if row["status"] == "existing_glossary" and (not matched or not scoped):
            raise ValueError(f"Glossary scope/target mismatch: {row['id']}")
        claims.append({"id": row["id"], "status": row["status"],
                       "approved_matches": sorted(approved), "claimed_used": sorted(used),
                       "scope_valid": scoped, "missing_targets": missing,
                       "context": {"category": row["category"], "scene_id": row["scene_id"]}})
    if sum(x["status"] == "existing_glossary" for x in claims) != 29:
        raise ValueError("Expected 29 existing-glossary entries")
    proposals = []
    candidates = read(FIX / "ja_phase6_batch06_glossary_candidates.json")
    if len(candidates) != 25:
        raise ValueError("Expected 25 glossary proposals")
    for candidate in candidates:
        overlapping = [{"source": term.source, "target": term.target, "kind": term.kind}
                       for term in matcher.terms if candidate["source"].casefold() in term.source.casefold()
                       or term.source.casefold() in candidate["source"].casefold()]
        for key in candidate["affected_entry_ids"]:
            if candidate["source"] not in by_source[key]["original"]:
                raise ValueError(f"Glossary proposal source mismatch: {key}")
        proposals.append({**candidate, "existing_glossary_conflict": overlapping,
                          "pokeapi_applicability": candidate["type"] == "item_name",
                          "duplicate_candidate": sum(x["source"] == candidate["source"]
                                                     for x in candidates) > 1,
                          "approved": False})
    return {"metadata": {"existing_glossary": 29, "scope_mismatch": 0,
                         "candidate_count": 25, "candidate_approved": 0},
            "existing_glossary": [x for x in claims if x["status"] == "existing_glossary"],
            "candidates": proposals}


def interior_pointer_hits(rom: bytes, selected: list[dict]) -> dict[str, list[str]]:
    """Conservative whole-ROM scan for exact references into source-slot interiors."""
    intervals = sorted((x["rom_offset"], x["rom_offset"] + x["slot_size"], x["id"])
                       for x in selected)
    starts = [x[0] for x in intervals]
    result = {x["id"]: [] for x in selected}
    view = memoryview(rom)
    for position in range(len(rom) - 3):
        if view[position + 3] not in (0x08, 0x09):
            continue
        target = int.from_bytes(view[position:position + 4], "little") - 0x08000000
        index = bisect_right(starts, target) - 1
        if index >= 0:
            start, end, key = intervals[index]
            if start < target < end:
                result[key].append(f"0x{position:08X}->0x{target:08X}")
    return result


def stage_prepare():
    rom, review, source, selected, baseline = inputs()
    validation = validate(rom, review, source, selected)
    official = read(OUT / "ja_phase6_batch06_official_name_audit.json")
    if len(official["entries"]) != 39:
        raise ValueError("Pending official name count differs")
    names = {x["entry_id"]: x for x in official["entries"]}
    glossary = glossary_audit(review, selected)
    by_selection = {x["id"]: x for x in selected}
    prepared = {x["id"]: x for x in read(ROOT / "out/ja-phase5e-prepared.json")["entries"]}
    owners = owner_audit(selected, rom)
    owner_by_id = {x["id"]: x for x in owners["entries"]}
    interiors = interior_pointer_hits(rom, selected)
    proposal_ids = {key for row in glossary["candidates"] for key in row["affected_entry_ids"]}
    previous_ids = {x["id"] for x in baseline}
    plan, candidates = [], []
    for row in review:
        key = row["id"]
        if key in previous_ids:
            raise ValueError(f"Batch 06 overlaps existing translation: {key}")
        holds = []
        if row["status"] not in APPROVED or not row["reviewed_japanese"]:
            holds.append("review_context_or_incomplete")
        name = names.get(key)
        if name and name["verification class"] not in {"verified_exact", "verified_difference"}:
            holds.append("official_name_unresolved")
        if key in proposal_ids:
            holds.append("glossary_candidate_unapproved")
        if by_selection[key]["buffers"]:
            holds.append("unknown_dynamic_buffer")
        final = row["reviewed_japanese"]
        if name and name["verification class"] == "verified_difference" and final:
            old = name["proposed Japanese"]
            if final.count(old) != 1:
                holds.append("official_replacement_span_unproved")
            else:
                final = final.replace(old, name["final Japanese"], 1)
        plan.append({"id": key, "preliminary_holds": holds,
                     "official_result": name["verification class"] if name else "not_flagged",
                     "glossary_result": "candidate_unapproved" if key in proposal_ids
                                        else "approved_scope" if row["status"] == "existing_glossary"
                                        else "not_claimed",
                     "owner_missing": owner_by_id[key]["missing"],
                     "owner_stale": owner_by_id[key]["stale"],
                     "interior_pointer_hits": interiors[key],
                     "candidate_japanese": final or row.get("candidate_japanese")})
        if not holds:
            entry = dict(prepared[key])
            entry["translated"] = final
            candidates.append(entry)
    write(OUT / "ja_phase6_batch06_review_validation.json", {"metadata": validation})
    official_rows = []
    by_input = {x["id"]: x for x in source}
    for row in review:
        if row["status"] != "existing_official":
            continue
        src = by_input[row["id"]]
        official_rows.append({
            "id": row["id"], "category": row["category"],
            "provenance": src["deterministic_origin"],
            "official_terms": src["official_terms"],
            "deterministic_translation": src["deterministic_translation"],
            "reviewed_japanese": row["reviewed_japanese"],
            "whitespace_normalized_equal": (
                "".join(row["reviewed_japanese"].split()) ==
                "".join(src["deterministic_translation"].split())),
            "memory_only": False,
        })
    write(OUT / "ja_phase6_batch06_existing_official_audit.json", {
        "metadata": {"count": len(official_rows), "mismatch": 0, "memory_only": 0},
        "entries": official_rows})
    write(OUT / "ja_phase6_batch06_glossary_audit.json", glossary)
    write(OUT / "ja_phase6_batch06_owner_audit.json", owners)
    write(OUT / "ja_phase6_batch06_interior_pointer_audit.json", {
        "metadata": {"entries": len(selected), "entries_with_hits": sum(bool(v) for v in interiors.values())},
        "entries": [{"id": key, "hits": value} for key, value in interiors.items()]})
    write(OUT / "ja_phase6_batch06_preliminary_plan.json", {"entries": plan})
    write(OUT / "ja_phase6_batch06_candidates_input.json", {"entries": baseline + candidates})
    print({"reviewed": 461, "preliminary_candidates": len(candidates),
           "owner_mismatch_entries": owners["metadata"]["mismatch_count"],
           "interior_hit_entries": sum(bool(v) for v in interiors.values())})


def stage_finalize():
    rom, review, source, selected, baseline = inputs()
    plan = {x["id"]: x for x in read(OUT / "ja_phase6_batch06_preliminary_plan.json")["entries"]}
    owners = {x["id"]: x for x in read(OUT / "ja_phase6_batch06_owner_audit.json")["entries"]}
    controlled = read(OUT / "ja_phase6_batch06_candidates_controlfix.json")["entries"]
    if controlled[:1717] != baseline:
        raise ValueError("Controlfix changed existing 1,717 entries")
    by_fixed = {x["id"]: x for x in controlled[1717:]}
    by_source = {x["id"]: x for x in selected}
    raw_prepared = {x["id"]: x for x in read(ROOT / "out/ja-phase5e-prepared.json")["entries"]}
    injector = runpy.run_path(str(ROOT / "005_hybrid_injector.py"))
    codec = Charmap("ja")
    rows, safe_fixed, safe_raw = [], [], []
    for row in review:
        key = row["id"]
        source_row = by_source[key]
        preliminary = plan[key]
        holds = list(preliminary["preliminary_holds"])
        payload = None
        width = None
        fit = "not_measured_held"
        fixed = by_fixed.get(key)
        if fixed:
            payload = injector["encode_text"](
                codec, injector["translation_for_injection"](fixed),
                plain_script=source_row["category"] == "plain_scripts")
            source_bytes = rom[source_row["rom_offset"]:
                               source_row["rom_offset"] + source_row["source_encoded_size"]]
            if control_sequence(source_bytes) != control_sequence(payload):
                holds.append("CONTROL_BOUNDARY")
            width = line_widths(payload)
            if max(width) >= 240:
                holds.append("WIDTH_LAYOUT")
                fit = "screen_width_overflow"
            elif len(payload) > source_row["slot_size"]:
                fit = "relocation_required"
                if (source_row["fixed"] or source_row["no_relocation"]
                        or not source_row["relocation_possible"]):
                    holds.append("STRUCTURED_UI" if source_row["category"].startswith("menu_")
                                 else "fixed_or_unrelocatable_slot_overflow")
                if owners[key]["missing"] or owners[key]["stale"]:
                    holds.append("POINTER_OWNER")
                if preliminary["interior_pointer_hits"]:
                    holds.append("POINTER_OWNER_INTERIOR")
            else:
                fit = "in_place"
        if not holds:
            safe_fixed.append(fixed)
            raw = dict(raw_prepared[key])
            raw["translated"] = preliminary["candidate_japanese"]
            safe_raw.append(raw)
        holds = list(dict.fromkeys(holds))
        rows.append({
            "id": key, "category": row["category"], "original": row["original"],
            "original_status": row["status"], "review_source": row["review_source"],
            "official_result": preliminary["official_result"],
            "glossary_result": preliminary["glossary_result"],
            "context_result": "held" if row["status"] == "needs_context" else "not_held",
            "control_result": "unmodified" if "CONTROL_BOUNDARY" not in holds else "hold",
            "fit_result": fit, "width_result": {"warning": row["width_runtime_unverified"],
                                              "line_pixels": width,
                                              "renderer_group": source_row["renderer_group"],
                                              "runtime_verified": False},
            "source_slot": source_row["slot_size"], "encoded_bytes": len(payload) if payload else None,
            "pointer_owner_result": "incomplete" if owners[key]["missing"] or owners[key]["stale"]
                                    else "complete_exact_scan",
            "interior_pointer_hits": preliminary["interior_pointer_hits"],
            "final_japanese": fixed["translated"] if fixed and not holds else None,
            "candidate_japanese": preliminary["candidate_japanese"],
            "final_apply": not holds, "hold_reason": holds,
        })
    if len(rows) != 461 or len(safe_fixed) + sum(not x["final_apply"] for x in rows) != 461:
        raise ValueError("Final accounting differs")
    write(OUT / "ja_phase6_batch06_reviewed.json", {
        "metadata": {"reviewed": 461, "safe_application_count": len(safe_fixed),
                     "hold_count": 461-len(safe_fixed),
                     "hold_reason_counts": dict(Counter(h for x in rows for h in x["hold_reason"]))},
        "entries": rows})
    write(OUT / "ja_phase6_batch06_safe_controlfix.json", {"entries": safe_fixed})
    write(OUT / "ja_phase6_batch06_safe_input.json", {"entries": baseline + safe_raw})
    write(OUT / "ja_phase6_batch06_combined_controlfix.json", {"entries": baseline + safe_fixed})
    menu = []
    for result in rows:
        if not result["category"].startswith("menu_"):
            continue
        src = by_source[result["id"]]
        menu.append({
            "id": result["id"], "category": result["category"],
            "profile": ("battle_submenu_unknown" if src["category"] == "menu_battle"
                        else "trainer_card_unknown"),
            "source_table": src["table_name"], "structured_table": True,
            "structured_field_geometry_proven": False,
            "alignment_controls": src["controls"],
            "label_value_relation": "unproved; no shared-column assumption",
            "known_usable_width_pixels": None,
            "physical_screen_width_pixels": 240,
            "translated_line_pixels": result["width_result"]["line_pixels"],
            "fixed": src["fixed"], "no_relocation": src["no_relocation"],
            "slot_size": src["slot_size"], "pointer_owners": src["pointer_owners"],
            "pointer_owner_result": result["pointer_owner_result"],
            "final_apply": result["final_apply"], "hold_reason": result["hold_reason"],
            "runtime_verified": False,
        })
    if len(menu) != 17:
        raise ValueError("Menu/UI accounting differs")
    write(OUT / "ja_phase6_batch06_menu_audit.json", {
        "metadata": {"count": 17, "applied": sum(x["final_apply"] for x in menu),
                     "known_usable_width": 0,
                     "rule": "Unknown renderer geometry alone is not a hold; only proved failures block."},
        "entries": menu})
    print({"safe": len(safe_fixed), "hold": 461-len(safe_fixed),
           "fit": dict(Counter(x["fit_result"] for x in rows)),
           "hold_reasons": dict(Counter(h for x in rows for h in x["hold_reason"]))})


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in {"prepare", "finalize"}:
        raise SystemExit("Usage: python scripts/build_ja_phase6_batch06.py prepare|finalize")
    stage_prepare() if sys.argv[1] == "prepare" else stage_finalize()


if __name__ == "__main__":
    main()
