#!/usr/bin/env python3
"""Reproducibly gate Batch 02 review against ROM, names, controls and fit."""

from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.pcs_text import Charmap, decode_pcs
from lib.translation_glossary import load_glossary
from lib.translation_tokens import semantic_tokens, strip_hma_quotes
from scripts.audit_ja_phase6_batch01_fit import line_widths
from scripts.build_ja_phase5c_handoff import operand_kind, speaker_evidence

OUT = ROOT / "out/phase6"
REVIEW = ROOT / "tests/fixtures/ja_phase6_batch02_claude_review.json"
BATCH = OUT / "ja_phase6_batch02_for_claude.json"
SELECTION = ROOT / "tests/fixtures/ja_phase6_selection.json"
PREPARED = ROOT / "out/ja-phase5e-prepared.json"
BASELINE = OUT / "ja_phase6_batch01_combined_input.json"
NAMES = OUT / "ja_phase6_batch02_official_name_audit.json"
SCROLL = OUT / "ja_phase6_batch02_scroll_audit.json"
BUFFERS = OUT / "ja_phase6_batch02_buffer_audit.json"
CANDIDATES = ROOT / "tests/fixtures/ja_phase6_batch02_glossary_candidates.json"
ROM = ROOT / "rom/unbound.gba"
SOURCE_MD5 = "9cad8e771940e7f7094d13911552cef0"
VALID_STATUSES = {"confirmed", "existing_official", "existing_glossary", "needs_context", "needs_technical_fit"}
VALID_PROVENANCE = {"Claude CLI", "Codex (user-approved fallback)"}
HAN = re.compile(r"[\u3400-\u9fff]")


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def review_validation(review, batch, selection):
    ids = [row["id"] for row in review]
    expected_ids = [row["id"] for row in batch["entries"]]
    if len(ids) != len(set(ids)) or ids != expected_ids or len(ids) != 408:
        raise ValueError("Batch 02 review ID/order/duplicate mismatch")
    selected = {row["id"]: row for row in selection["entries"]}
    codec = Charmap("ja")
    rows = []
    for row, source in zip(review, batch["entries"]):
        issues = []
        if row["category"] != source["category"] or row["original"] != source["original"]:
            issues.append("source_identity")
        if row["status"] not in VALID_STATUSES or row.get("review_provenance") not in VALID_PROVENANCE:
            issues.append("status_or_provenance")
        if row.get("conversation_id") != source.get("conversation_id") or row.get("scene_id") != source.get("scene_id"):
            issues.append("conversation_or_scene")
        target = row.get("reviewed_japanese") or ""
        if row["status"] == "needs_context" and target:
            issues.append("context_hold_has_translation")
        if HAN.search(target):
            issues.append("kanji")
        original = strip_hma_quotes(row["original"])
        protected = Counter(source["protected_tokens"])
        if Counter(semantic_tokens(original)) != protected:
            issues.append("source_protected_metadata")
        if target and Counter(semantic_tokens(target)) != protected:
            issues.append("protected_token_mismatch")
        for control in ("\\l", "\\p", "\\n"):
            if target and target.count(control) != original.count(control):
                issues.append(f"control_count:{control}")
        try:
            encoded = codec.encode(f"[japanese]{target}[latin]") if target else None
        except (UnicodeEncodeError, ValueError) as error:
            encoded = None
            issues.append(f"pcs_encode:{error}")
        if row["id"] not in selected:
            issues.append("missing_selection")
        rows.append({"id": row["id"], "status": row["status"],
                     "review_provenance": row["review_provenance"], "issues": issues,
                     "raw_japanese_bytes": len(encoded) if encoded else None})
    if any(row["issues"] for row in rows):
        raise ValueError(f"Batch 02 review validation failed: {[r for r in rows if r['issues']][:5]}")
    return {"metadata": {"count": 408, "issue_count": 0,
                         "provenance_counts": dict(Counter(row["review_provenance"] for row in rows)),
                         "status_counts": dict(Counter(row["status"] for row in rows))},
            "entries": rows}


def owner_audit(selection, rom):
    rows = []
    for source in selection:
        offset = source["rom_offset"]
        needle = (0x08000000 + offset).to_bytes(4, "little")
        found = []
        cursor = 0
        while (cursor := rom.find(needle, cursor)) >= 0:
            found.append(cursor)
            cursor += 1
        recorded = {int(x, 16) for x in source["pointer_owners"]}
        actual = set(found)
        rows.append({"id": source["id"],
                     "recorded": [f"0x{x:08X}" for x in sorted(recorded)],
                     "whole_rom_exact_hits": [f"0x{x:08X}" for x in found],
                     "missing": [f"0x{x:08X}" for x in sorted(actual - recorded)],
                     "missing_kinds": [operand_kind(rom, x) for x in sorted(actual - recorded)],
                     "stale": [f"0x{x:08X}" for x in sorted(recorded - actual)],
                     "owner_kinds": [operand_kind(rom, x) for x in sorted(recorded)],
                     "note": "Raw exact hits are conservative risk signals; extra hits require independent structural ownership proof."})
    return {"metadata": {"audited": len(rows),
                         "mismatch_count": sum(bool(r["missing"] or r["stale"]) for r in rows)},
            "entries": rows}


def fit_audit(review, selection, owners, rom):
    codec = Charmap("ja")
    by_owner = {row["id"]: row for row in owners["entries"]}
    rows = []
    for row in review:
        if row["status"] != "needs_technical_fit":
            continue
        source = selection[row["id"]]
        address = source["rom_offset"]
        original = rom[address:address + decode_pcs(rom, address, source["slot_size"]).byte_length]
        source_widths = line_widths(original)
        text = row["reviewed_japanese"]
        if text:
            payload = codec.encode(f"[japanese]{text}[latin]")
            widths = line_widths(payload)
            encoded = len(payload)
        else:
            widths, encoded = [], None
        incomplete = bool(by_owner[row["id"]]["missing"] or by_owner[row["id"]]["stale"])
        positional = source["original"].startswith('" ') or any(
            token in source["original"] for token in ("\\al", "\\ar", "\\au", "\\ad"))
        if not text or positional:
            fit_result = "structured_constraint"
        elif incomplete:
            fit_result = "owner_incomplete"
        elif encoded > source["slot_size"] and (source["fixed"] or source["no_relocation"]):
            fit_result = "fixed_overflow"
        elif encoded > source["slot_size"]:
            fit_result = "relocatable"
        else:
            fit_result = "in_place"
        width_status = ("not_measured" if not widths else
                        "positional_renderer_unverified" if positional else
                        "exceeds_source_line_width_before_controlfix" if max(widths) > max(source_widths) else
                        "within_source_max_line_width_before_controlfix")
        rows.append({"id": row["id"], "rom_offset": f"0x{address:08X}",
                     "source_bytes": source["source_encoded_size"], "slot_size": source["slot_size"],
                     "japanese_encoded_bytes": encoded, "fixed": source["fixed"],
                     "no_relocation": source["no_relocation"], "pointer_owners": source["pointer_owners"],
                     "relocation_possible": source["relocation_possible"] and not incomplete,
                     "source_line_pixels": source_widths, "japanese_line_pixels": widths,
                     "renderer_width_limit_pixels": None,
                     "renderer_width_evidence": "Exact event/choice/sign window bound not established for this operand",
                     "width_status": width_status, "controls": source["controls"],
                     "fit_result": fit_result, "apply": False,
                     "hold_reason": "Byte fit is measured on reviewed text before controlfix; unknown renderer width, provisional wording, or FA placement remains unapproved."})
    if len(rows) != 50:
        raise ValueError(f"Expected 50 technical-fit rows; got {len(rows)}")
    return {"metadata": {"count": len(rows),
                         "result_counts": dict(Counter(row["fit_result"] for row in rows)),
                         "width_status_counts": dict(Counter(row["width_status"] for row in rows)),
                         "confirmed_width_overflow": 0,
                         "note": "Japanese normal-font glyph advances measured; exact renderer bounds are unknown. Raw pre-controlfix line growth is not a confirmed overflow."},
            "entries": rows}


def context_audit(review, selection, rom):
    rows = []
    for row in review:
        warnings = row["review_warning"]
        if not ("speaker_uncertain" in warnings or "context_uncertain" in warnings):
            continue
        source = selection[row["id"]]
        speaker = speaker_evidence(row["original"], row["category"])
        rows.append({"id": row["id"], "warnings": [w for w in warnings if w in {"speaker_uncertain", "context_uncertain"}],
                     "rom_offset": f"0x{source['rom_offset']:08X}",
                     "pointer_owners": source["pointer_owners"],
                     "script_owner_kinds": [operand_kind(rom, int(x, 16)) for x in source["pointer_owners"]],
                     "speaker_evidence": speaker, "conversation_id": row["conversation_id"],
                     "context_before": source.get("context_before", []), "context_after": source.get("context_after", []),
                     "map_event_identity": None,
                     "conclusion": "Pointer operand proves text reference, not map/event actor or speaker voice. No new persona inferred."})
    return {"metadata": {"entries": len(rows),
                         "speaker_warning_count": sum("speaker_uncertain" in r["warnings"] for r in rows),
                         "context_warning_count": sum("context_uncertain" in r["warnings"] for r in rows)},
            "entries": rows}


def glossary_audit(review, candidates, selection):
    glossary = load_glossary(ROOT / "glossaries/ja.json", expected_language="ja")
    rows = []
    for row in review:
        source = selection[row["id"]].get("translation_source") or strip_hma_quotes(row["original"])
        matched = [term.source for _start, _end, term in glossary.matches(source, row["category"], entry_id=row["id"])]
        used = row.get("glossary_terms_used", [])
        rows.append({"id": row["id"], "approved_matches": matched, "claimed_used": used,
                     "claim_scope_valid": all(term in matched for term in used)})
    proposals = []
    for item in candidates:
        conflicts = [{"source": term.source, "target": term.target, "kind": term.kind}
                     for term in glossary.terms if term.source.casefold() == item["source"].casefold()]
        proposals.append({**item, "existing_conflict": conflicts,
                          "context_sensitive": item["type"] not in {"location", "region"},
                          "pokeapi_applicability": item["type"] in {"pokemon", "move", "item", "ability", "type", "nature"},
                          "status": "proposal_only"})
    if len(candidates) != 18 or any(not row["claim_scope_valid"] for row in rows):
        raise ValueError("Batch 02 glossary scope/candidate count mismatch")
    return {"metadata": {"candidate_count": 18, "scope_mismatch_count": 0,
                         "collision_warning_count": sum("possible_glossary_collision" in r["review_warning"] for r in review),
                         "rule": "No candidate added to approved glossary; no substring or out-of-scope match."},
            "candidate_entries": proposals, "review_matches": rows}


def reviewed_input(review, selection, prepared, baseline, validation, names, scroll, buffers, fit, owners, rom):
    prepared_by_id = {row["id"]: row for row in prepared["entries"]}
    issue_by_id = {row["id"]: row["issues"] for row in validation["entries"]}
    names_by_id = defaultdict(list)
    for row in names["entries"]:
        names_by_id[row["entry_id"]].append(row)
    scroll_by_id = {row["id"]: row for row in scroll["entries"]}
    buffer_by_id = {row["id"]: row for row in buffers["entries"]}
    fit_by_id = {row["id"]: row for row in fit["entries"]}
    owner_by_id = {row["id"]: row for row in owners["entries"]}
    codec = Charmap("ja")
    annotated, safe = [], []
    for row in review:
        entry_id = row["id"]
        source = selection[entry_id]
        name_results = [term["verification_result"] for term in names_by_id[entry_id]]
        incomplete = bool(owner_by_id[entry_id]["missing"] or owner_by_id[entry_id]["stale"])
        hold = []
        if row["status"] not in {"confirmed", "existing_glossary", "existing_official"}:
            hold.append(row["status"])
        if issue_by_id[entry_id]:
            hold.append("review_validation")
        if any(result not in {"verified_exact", "verified_difference"} for result in name_results):
            hold.append("unverified_official_name")
        if entry_id in scroll_by_id:
            hold.append("unresolved_fa_placement")
        if entry_id in buffer_by_id and buffer_by_id[entry_id]["buffer_status"] != "resolved_value":
            hold.append("unresolved_dynamic_buffer")
        if incomplete:
            hold.append("incomplete_pointer_ownership")
        if "possible_glossary_collision" in row["review_warning"]:
            hold.append("possible_glossary_collision")
        target = row["reviewed_japanese"]
        if ("\\l" in row["original"] and target.rstrip().endswith("\\l")
                and not strip_hma_quotes(row["original"]).rstrip().endswith("\\l")):
            hold.append("terminal_fa_without_source_boundary")
        if entry_id in fit_by_id:
            hold.append("technical_fit_unapproved")
        if not target:
            hold.append("no_reviewed_japanese")
        if target and source["slot_size"] <= 32:
            address = source["rom_offset"]
            original_payload = rom[address:address + decode_pcs(rom, address, source["slot_size"]).byte_length]
            japanese_payload = codec.encode(f"[japanese]{target}[latin]")
            if max(line_widths(japanese_payload)) > max(line_widths(original_payload)):
                hold.append("compact_width_unproven")
        apply = not hold
        status = "validated_for_controlfix" if apply else "held_english"
        final = target if apply else None
        annotated.append({**row, "original_review_status": row["status"],
                          "technical_status": status, "official_name_result": name_results,
                          "buffer_result": buffer_by_id[entry_id]["buffer_status"] if entry_id in buffer_by_id else "not_applicable",
                          "scroll_result": scroll_by_id[entry_id]["placement_class"] if entry_id in scroll_by_id else "not_applicable",
                          "fit_result": fit_by_id[entry_id]["fit_result"] if entry_id in fit_by_id else "pending_controlfix",
                          "pointer_owner_complete": not incomplete, "apply": apply,
                          "final_japanese": final, "hold_reason": hold})
        if apply:
            source_entry = dict(prepared_by_id[entry_id])
            source_entry["translated"] = final
            safe.append(source_entry)
    combined = list(baseline["entries"]) + safe
    if len({row["id"] for row in combined}) != len(combined):
        raise ValueError("Batch 01/02 input ID overlap")
    return ({"metadata": {"phase": "6B-2", "reviewed": len(annotated),
                          "safe_application_count": len(safe), "hold_count": len(annotated) - len(safe),
                          "technical_status_counts": dict(Counter(row["technical_status"] for row in annotated))},
             "entries": annotated}, {"entries": safe}, {"entries": combined})


def main():
    rom = ROM.read_bytes()
    if hashlib.md5(rom).hexdigest() != SOURCE_MD5:
        raise ValueError("Source ROM MD5 mismatch")
    review = read(REVIEW)
    batch = read(BATCH)
    selection = read(SELECTION)
    selected = {row["id"]: row for row in selection["entries"]}
    validation = review_validation(review, batch, selection)
    names = read(NAMES)
    scroll = read(SCROLL)
    buffers = read(BUFFERS)
    chosen_selection = [selected[row["id"]] for row in review]
    owners = owner_audit(chosen_selection, rom)
    fit = fit_audit(review, selected, owners, rom)
    contexts = context_audit(review, selected, rom)
    glossary = glossary_audit(review, read(CANDIDATES), selected)
    reviewed, safe, combined = reviewed_input(review, selected, read(PREPARED), read(BASELINE),
                                              validation, names, scroll, buffers, fit, owners, rom)
    for filename, payload in (
        ("ja_phase6_batch02_review_validation.json", validation),
        ("ja_phase6_batch02_owner_audit.json", owners),
        ("ja_phase6_batch02_fit.json", fit),
        ("ja_phase6_batch02_context_audit.json", contexts),
        ("ja_phase6_batch02_glossary_audit.json", glossary),
        ("ja_phase6_batch02_reviewed.json", reviewed),
        ("ja_phase6_batch02_safe_input.json", safe),
        ("ja_phase6_batch02_combined_input.json", combined),
    ):
        write(OUT / filename, payload)
    print({"review": validation["metadata"], "owners": owners["metadata"],
           "fit": fit["metadata"], "safe": reviewed["metadata"],
           "combined": len(combined["entries"])})


if __name__ == "__main__":
    main()
