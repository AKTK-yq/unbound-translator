#!/usr/bin/env python3
"""Gate Batch 03 review with ROM owners, PokeAPI names and FA segment layout."""

from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.fa_control import join_segments, reconstruct_reviewed_segments
from lib.pcs_text import Charmap, decode_pcs
from lib.translation_glossary import load_glossary
from lib.translation_tokens import semantic_tokens, strip_hma_quotes
from scripts.audit_ja_phase6_batch01_fit import line_widths
from scripts.audit_ja_phase6_batch02_controls import direct_literal, nearby_writers
from scripts.audit_ja_phase6_fa import layout_trace, source_raw
from scripts.build_ja_phase5c_handoff import operand_kind
from scripts.build_ja_phase6_batch02 import owner_audit

OUT = ROOT / "out/phase6"
ROM = ROOT / "rom/unbound.gba"
SOURCE_MD5 = "9cad8e771940e7f7094d13911552cef0"
STATUSES = {"confirmed", "existing_official", "existing_glossary", "needs_context", "needs_technical_fit"}
PROVENANCE = {"Claude CLI", "Codex (user-approved fallback)"}
HAN = re.compile(r"[\u3400-\u9fff]")
RAW_SUFFIX = re.compile(r"\\(?:07|08|0C)(?![0-9A-Fa-f])")
MODEL_BOX_PIXELS = 208  # Existing diagnostic model, not proved Unbound renderer width.


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def boundary_sequence(segments):
    return [segment["after_control"] for segment in segments if segment["after_control"]]


def translated_segments(review):
    return [segment["reviewed_japanese"] for segment in review["segments"]]


def reviewer_conflict(review):
    return any(warning.casefold() == "fa_segment_semantic_conflict"
               for warning in review.get("review_warning", []))


def review_validation(review, source, selection):
    if len(review) != 408 or len(source) != 408:
        raise ValueError("Review/source must each contain 408 entries")
    ids = [row["id"] for row in review]
    if len(ids) != len(set(ids)) or ids != [row["id"] for row in source]:
        raise ValueError("Review IDs/order differ from segmented source")
    selected = {row["id"]: row for row in selection}
    codec = Charmap("ja")
    details = []
    for row, original in zip(review, source):
        errors = []
        if row["original"] != original["original"] or row["category"] != original["category"]:
            errors.append("original_or_category")
        if row["status"] not in STATUSES or row.get("review_provenance") not in PROVENANCE:
            errors.append("status_or_provenance")
        if row.get("conversation_id") != original.get("conversation_id") or row.get("scene_id") != original.get("scene_id"):
            errors.append("conversation_or_scene")
        if row["id"] not in selected:
            errors.append("missing_selection")
        fa = bool(original.get("control_segments"))
        if fa != bool(row.get("fa_segmented")):
            errors.append("fa_flag")
        if fa:
            pieces = row.get("segments", [])
            if len(pieces) != len(original["control_segments"]):
                errors.append("fa_segment_count")
            else:
                for a, b in zip(original["control_segments"], pieces):
                    if a["text"] != b["source"] or a["after_control"] != b["after_control"]:
                        errors.append("fa_source_boundary")
                    text = b["reviewed_japanese"]
                    if not text:
                        continue
                    if semantic_tokens(text) != semantic_tokens(a["text"]):
                        errors.append("fa_protected_token")
                    if HAN.search(text) or any(token in text for token in ("\n", "\\n", "\\l", "\\p")):
                        errors.append("fa_kanji_or_layout")
                    try:
                        codec.encode("[japanese]" + text + "[latin]")
                    except (UnicodeEncodeError, ValueError):
                        errors.append("fa_charmap")
            if row["reviewed_japanese"]:
                errors.append("fa_freeform_text")
        else:
            text = row["reviewed_japanese"]
            if text:
                if semantic_tokens(text) != semantic_tokens(strip_hma_quotes(row["original"])):
                    errors.append("protected_token")
                if HAN.search(text):
                    errors.append("kanji")
                try:
                    codec.encode("[japanese]" + text + "[latin]")
                except (UnicodeEncodeError, ValueError):
                    errors.append("charmap")
        details.append({"id": row["id"], "status": row["status"], "review_source": row["review_provenance"],
                        "fa": fa, "issues": sorted(set(errors))})
    if any(row["issues"] for row in details):
        raise ValueError(f"Review validation failed: {[x for x in details if x['issues']][:4]}")
    return {"metadata": {"count": 408, "issue_count": 0,
                         "review_source_counts": dict(Counter(x["review_source"] for x in details)),
                         "status_counts": dict(Counter(x["status"] for x in details))},
            "entries": details}


def glossary_audit(review, selection, candidates):
    matcher = load_glossary(ROOT / "glossaries/ja.json", expected_language="ja")
    chosen = {row["id"]: row for row in selection}
    all_matches = []
    for row in review:
        source = chosen[row["id"]]
        text = source.get("translation_source") or strip_hma_quotes(row["original"])
        matches = matcher.matches(text, row["category"], entry_id=row["id"])
        approved = [term.source for _begin, _end, term in matches]
        used = [claim.split("=")[0].strip() for claim in row.get("glossary_terms_used", [])
                if isinstance(claim, str)]
        false_substrings = [term.source for term in matcher.terms
                            if term.source.casefold() in text.casefold() and term.source not in approved]
        all_matches.append({"id": row["id"], "approved_matches": approved,
                            "review_claims": used, "claim_scope_valid": all(term in approved for term in used),
                            "filtered_substrings": sorted(set(false_substrings)),
                            "overlap_resolved_by_matcher": len(approved) < len(set(approved + false_substrings))})
    proposals = []
    for candidate in candidates:
        exact = [{"source": term.source, "target": term.target, "kind": term.kind}
                 for term in matcher.terms if term.source.casefold() == candidate["source"].casefold()]
        overlapping = [term.source for term in matcher.terms
                       if term.source.casefold() in candidate["source"].casefold()
                       or candidate["source"].casefold() in term.source.casefold()]
        proposals.append({**candidate, "existing_glossary_conflict": exact,
                          "overlapping_approved_terms": sorted(set(overlapping)),
                          "context_sensitive": candidate["type"] not in {"location", "region"},
                          "pokeapi_applicability": candidate["type"] in
                          {"pokemon", "move", "item", "ability", "type", "nature"},
                          "status": "proposal_only_not_approved"})
    if len(proposals) != 30 or any(not x["claim_scope_valid"] for x in all_matches):
        raise ValueError("Glossary review scope or candidate count changed")
    return {"metadata": {"reviewed": 408, "candidate_count": 30,
                         "scope_collision_count": 0,
                         "filtered_substring_entries": sum(bool(x["filtered_substrings"]) for x in all_matches),
                         "rule": "Only boundary-safe, scoped longest matches count; proposals are not approved."},
            "review_matches": all_matches, "candidate_entries": proposals}


def diagnostic_text(row, original):
    if not original.get("control_segments"):
        return row["reviewed_japanese"] or None
    pieces = row["segments"]
    if any(piece["source"].strip() and not piece["reviewed_japanese"].strip() for piece in pieces):
        return None
    controls = original["control_segments"]
    return reconstruct_reviewed_segments(strip_hma_quotes(original["original"]), controls,
                                         translated_segments(row))


def name_result(row, name_rows, text, segments):
    """Apply only exact, traceable ja-hrkt names; return held reason otherwise."""
    reasons = []
    for term in name_rows:
        status = term["verification_result"]
        if status not in {"verified_exact", "verified_difference"}:
            reasons.append(f"unverified_official_name:{term['English term']}:{status}")
            continue
        final = term["final_value"]
        proposal = term["proposed_japanese"]
        if not final:
            reasons.append(f"official_value_missing:{term['English term']}")
            continue
        if final in text:
            continue
        old = proposal if proposal and proposal in text else term["English term"]
        if old not in text:
            reasons.append(f"official_value_not_located:{term['English term']}")
            continue
        if segments is None:
            text = text.replace(old, final)
        else:
            changed = 0
            for index, piece in enumerate(segments):
                if old in piece:
                    segments[index] = piece.replace(old, final)
                    changed += 1
            if changed != 1:
                reasons.append(f"official_name_crosses_segment:{term['English term']}")
            else:
                text = join_segments([{"text": "", "after_control": s["after_control"]}
                                      for s in row["segments"]], segments)
    return text, segments, reasons


def fa_class(row):
    if row["status"] in {"confirmed", "existing_glossary", "existing_official"}:
        return "semantic_confirmed_review"
    if reviewer_conflict(row):
        return "segment_conflict"
    if row["status"] == "needs_context":
        return "context_hold_only"
    return "technical_nonconflict_hold"


def fa_layout(row, source, owner, rom, segments):
    raw = source_raw(rom, source)
    source_controls = source["controls"]
    result = {"source_line_pixels": line_widths(raw), "japanese_line_pixels": None,
              "source_layout_trace": layout_trace(raw), "japanese_layout_trace": None,
              "source_control_counts": source_controls,
              "output_controls": None,
              "box_width_pixels_model": MODEL_BOX_PIXELS,
              "box_width_proof": "not pixel-perfect; 208px is a diagnostic model",
              "visible_lines_model": 2, "font": "ROM normal Latin/Japanese glyph-width tables",
              "buffer_width_estimate": 54,
              "input_wait_semantics": "FA waits then scrolls one line; FB waits then clears",
              "layout_status": "NOT_SEMANTICALLY_APPROVED",
              "layout_reason": "Semantic review is not confirmed"}
    if row["status"] not in {"confirmed", "existing_glossary", "existing_official"}:
        return result
    if not segments or any(source_piece["text"].strip() and not translated.strip()
                           for source_piece, translated in zip(source["control_segments"], segments)):
        result.update(layout_status="LAYOUT_AMBIGUOUS", layout_reason="Missing translated segment")
        return result
    rebuilt = reconstruct_reviewed_segments(strip_hma_quotes(source["original"]),
                                             source["control_segments"], segments)
    payload = Charmap("ja").encode("[japanese]" + rebuilt + "[latin]")
    target_trace = layout_trace(payload)
    widths = line_widths(payload)
    target_controls = boundary_sequence(source["control_segments"])
    result.update(japanese_line_pixels=widths, japanese_layout_trace=target_trace,
                  output_controls=target_controls,
                  encoded_japanese_bytes=len(payload),
                  source_segment_count=len(source["control_segments"]),
                  output_segment_count=len(segments),
                  source_fa_count=source_controls.get("FA", 0),
                  output_fa_count=target_controls.count("FA"),
                  source_max_line_pixels=max(result["source_line_pixels"]),
                  japanese_max_line_pixels=max(widths))
    if owner["missing"] or owner["stale"]:
        result.update(layout_status="TECHNICAL_OWNER_HOLD", layout_reason="Pointer ownership incomplete")
    elif source.get("buffers") or RAW_SUFFIX.search(source["original"]):
        result.update(layout_status="LAYOUT_AMBIGUOUS", layout_reason="Dynamic substitution width/page state unproved")
    elif any(token in source["original"] for token in ("\\al", "\\ar", "\\au", "\\ad")):
        result.update(layout_status="LAYOUT_AMBIGUOUS", layout_reason="Horizontal/vertical alignment control unmodelled")
    elif max(widths) > 240:
        result.update(layout_status="LAYOUT_OVERFLOW", layout_reason="Wider than 240px GBA display")
    elif max(widths) > MODEL_BOX_PIXELS or max(widths) > max(result["source_line_pixels"]):
        result.update(layout_status="LAYOUT_AMBIGUOUS",
                      layout_reason="Japanese line exceeds diagnostic 208px or observed source-line envelope")
    elif target_controls != source["source_boundary_sequence"]:
        result.update(layout_status="LAYOUT_AMBIGUOUS", layout_reason="FE/FA/FB boundary mismatch")
    else:
        result.update(layout_status="LAYOUT_PASS",
                      layout_reason="Same ROM-derived boundaries and line count; Japanese width at most 208px and source maximum")
    return result


def fit_row(review, source, owner, rom, diagnostic):
    raw = source_raw(rom, source)
    entry = {"id": review["id"], "category": source["category"],
             "rom_offset": f"0x{source['rom_offset']:08X}", "slot_size": source["slot_size"],
             "source_encoded_bytes": source["source_encoded_size"], "fixed": source["fixed"],
             "no_relocation": source["no_relocation"], "pointer_owners": source["pointer_owners"],
             "owner_missing": owner["missing"], "owner_stale": owner["stale"],
             "relocation_allowed": source["relocation_possible"] and not bool(owner["missing"] or owner["stale"]),
             "renderer_group": source["renderer_group"], "renderer_width_pixels": None,
             "renderer_width_evidence": "Exact Unbound event window width unproved; 208px is only diagnostic",
             "source_line_pixels": line_widths(raw), "japanese_line_pixels": None,
             "japanese_encoded_bytes": None, "controls": source["controls"],
             "fa": bool(source.get("controls", {}).get("FA")),
             "structured_table_constraint": source["renderer_group"] != "event_dialogue",
             "fit_result": "layout_ambiguous", "apply": False,
             "measurement_note": "No complete, encodable reviewed draft"}
    if owner["missing"] or owner["stale"]:
        entry.update(fit_result="owner_incomplete", measurement_note="Whole-ROM exact pointer hits exceed metadata")
    if not diagnostic:
        return entry
    try:
        payload = Charmap("ja").encode("[japanese]" + diagnostic + "[latin]")
    except (UnicodeEncodeError, ValueError) as error:
        entry["measurement_note"] = f"Draft is not Japanese-PCS encodable: {error}"
        return entry
    widths = line_widths(payload)
    entry.update(japanese_encoded_bytes=len(payload), japanese_line_pixels=widths,
                 measurement_note="Diagnostic only; original review remains held")
    if owner["missing"] or owner["stale"]:
        return entry
    if source["renderer_group"] != "event_dialogue":
        entry["fit_result"] = "structured_constraint"
    elif len(payload) > source["slot_size"] and (source["fixed"] or source["no_relocation"]):
        entry["fit_result"] = "fixed_overflow"
    elif max(widths) > 240:
        entry["fit_result"] = "width_overflow"
    elif len(payload) > source["slot_size"]:
        entry["fit_result"] = "relocatable"
    elif max(widths) > max(entry["source_line_pixels"]):
        entry["fit_result"] = "layout_ambiguous"
    else:
        entry["fit_result"] = "in_place"
    return entry


def context_audit(review, source, rom):
    rows = []
    for row in review:
        if row["status"] != "needs_context":
            continue
        selected = source[row["id"]]
        owners = []
        for pointer in selected["pointer_owners"]:
            offset = int(pointer, 16)
            owners.append({"rom_offset": pointer, "kind": operand_kind(rom, offset),
                           "direct_buffer_writer": direct_literal(rom, offset),
                           "nearby_writer_candidates": nearby_writers(rom, offset)[:8]})
        dynamic = [buffer for buffer in selected["buffers"] if buffer.startswith("[buffer")]
        rows.append({"id": row["id"], "overall_status": row["status"],
                     "fa": bool(selected["controls"].get("FA")),
                     "rom_offset": f"0x{selected['rom_offset']:08X}",
                     "scene_id": row["scene_id"], "speaker": selected["speaker"],
                     "runtime_evidence": selected["runtime_evidence"],
                     "buffer_tokens": dynamic, "raw_suffixes": RAW_SUFFIX.findall(row["original"]),
                     "pointer_owners": owners, "context_before": selected.get("context_before", []),
                     "context_after": selected.get("context_after", []),
                     "technical_resolution": "unproved",
                     "hold_reason": "Writer/value, runtime caller, speaker, or meaning remains unresolved; no new translation authored"})
    if len(rows) != 65:
        raise ValueError("Expected 65 Batch 03 context holds")
    return {"metadata": {"count": 65, "fa_count": sum(x["fa"] for x in rows),
                         "technically_resolved": 0}, "entries": rows}


def retranslation_handoff(fa_rows):
    entries = []
    for row in fa_rows:
        if row["semantic_status"] != "segment_conflict":
            continue
        segments = row["source_segments"]
        pairs = [{"left_segment_index": index, "right_segment_index": index + 1,
                  "left_source_end": segment["text"][-75:],
                  "right_source_start": segments[index + 1]["text"][:75],
                  "source_fa_after_left": True}
                 for index, segment in enumerate(segments[:-1]) if segment["after_control"] == "FA"]
        entries.append({"id": row["id"], "source_control_structure": row["source_controls"],
                        "candidate_conflict_boundaries": pairs,
                        "boundary_specificity": "source FA pairs listed; Claude must confirm which pair(s) collide",
                        "conflict_reason": row["hold_reason"],
                        "renderer_constraint": row["layout_reason"],
                        "no_new_translation": True})
    return {"metadata": {"count": len(entries), "previous_uppercase_warning_count": 29,
                         "newly_detected_lowercase_warning_count": 12,
                         "rule": "Source FA boundaries are fixed; Claude may revise segment wording only."},
            "entries": entries}


def build():
    rom = ROM.read_bytes()
    if hashlib.md5(rom).hexdigest() != SOURCE_MD5:
        raise ValueError("Source ROM MD5 mismatch")
    review = read(ROOT / "tests/fixtures/ja_phase6_batch03_claude_review.json")
    segmented = read(OUT / "ja_phase6_batch03_fa_segmented_input.json")["entries"]
    selection = read(ROOT / "tests/fixtures/ja_phase6_selection.json")["entries"]
    selected = {row["id"]: row for row in selection}
    original = {row["id"]: row for row in segmented}
    names = read(OUT / "ja_phase6_batch03_official_name_audit.json")["entries"]
    names_by_id = defaultdict(list)
    for name in names:
        names_by_id[name["entry_id"]].append(name)
    validation = review_validation(review, segmented, selection)
    owners = owner_audit([selected[row["id"]] for row in review], rom)
    by_owner = {row["id"]: row for row in owners["entries"]}
    glossary = glossary_audit(review, selection,
                              read(ROOT / "tests/fixtures/ja_phase6_batch03_glossary_candidates.json"))
    glossary_by_id = {row["id"]: row for row in glossary["review_matches"]}
    contexts = context_audit(review, selected, rom)
    prepared = {row["id"]: row for row in read(ROOT / "out/ja-phase5e-prepared.json")["entries"]}
    # Preserve Batch 02's already-approved FA placement during a second controlfix.
    baseline = read(OUT / "ja_phase6_batch02_controlfix.json")["entries"]
    baseline_ids = {row["id"] for row in baseline}
    codec = Charmap("ja")
    annotated, fa_rows, fit_rows, safe = [], [], [], []
    for row in review:
        entry_id = row["id"]
        source, selected_row, owner = original[entry_id], selected[entry_id], by_owner[entry_id]
        fa = bool(source.get("control_segments"))
        pieces = translated_segments(row) if fa else None
        candidate = diagnostic_text(row, source)
        name_reasons = []
        if candidate:
            candidate, pieces, name_reasons = name_result(row, names_by_id[entry_id], candidate, pieces)
        elif names_by_id[entry_id]:
            name_reasons = ["no_complete_draft_for_official_name"]
        hold = []
        if row["status"] not in {"confirmed", "existing_glossary", "existing_official"}:
            hold.append("review_status:" + row["status"])
        hold.extend(name_reasons)
        if owner["missing"] or owner["stale"]:
            hold.append("incomplete_pointer_ownership")
        if not glossary_by_id[entry_id]["claim_scope_valid"] or "possible_glossary_collision" in row["review_warning"]:
            hold.append("glossary_scope_unproved")
        for claim in row.get("glossary_terms_used", []):
            term = claim.split("=")[0].strip() if isinstance(claim, str) else ""
            value = selected_row.get("glossary_terms", {}).get(term)
            if value and (not candidate or value not in candidate):
                hold.append("approved_glossary_target_absent:" + term)
        if selected_row["buffers"] or RAW_SUFFIX.search(row["original"]):
            hold.append("dynamic_buffer_or_suffix_unproved")
        if not candidate:
            hold.append("no_complete_reviewed_draft")
        try:
            if candidate:
                payload = codec.encode("[japanese]" + candidate + "[latin]")
                if semantic_tokens(candidate) != semantic_tokens(strip_hma_quotes(row["original"])):
                    hold.append("protected_token_mismatch_after_name_resolution")
            else:
                payload = None
        except (UnicodeEncodeError, ValueError):
            payload = None
            hold.append("japanese_pcs_encode_error")
        layout = None
        if fa:
            layout = fa_layout(row, {**selected_row, **source}, owner, rom, pieces)
            if layout["layout_status"] != "LAYOUT_PASS":
                hold.append("fa_layout:" + layout["layout_status"])
        elif payload:
            source_widths = line_widths(source_raw(rom, selected_row))
            target_widths = line_widths(payload)
            if max(target_widths) > MODEL_BOX_PIXELS or max(target_widths) > max(source_widths):
                hold.append("script_width_unproved")
            if any(token in row["original"] for token in ("\\al", "\\ar", "\\au", "\\ad")):
                hold.append("alignment_renderer_unproved")
        if payload and len(payload) > selected_row["slot_size"]:
            if selected_row["fixed"] or selected_row["no_relocation"] or not selected_row["relocation_possible"]:
                hold.append("unrelocatable_slot_overflow")
        if entry_id in baseline_ids:
            raise ValueError(f"Batch 03 overlaps existing safely applied baseline: {entry_id}")
        apply = not hold
        if apply:
            prepared_row = dict(prepared[entry_id])
            if fa:
                prepared_row.update({"translated": None, "translated_segments": pieces,
                                     "control_segments": source["control_segments"],
                                     "source_boundary_sequence": source["source_boundary_sequence"],
                                     "fa_placement_policy": "require_segments",
                                     "fa_layout_reviewed": True, "controls": source["controls"]})
            else:
                prepared_row["translated"] = candidate
            safe.append(prepared_row)
        item = {**row, "original_review_status": row["status"],
                "semantic_status": fa_class(row) if fa else row["status"],
                "official_name_result": [{"term": term["English term"],
                                          "result": term["verification_result"],
                                          "final_value": term["final_value"]}
                                         for term in names_by_id[entry_id]],
                "fa_result": layout["layout_status"] if fa else "not_applicable",
                "layout_result": layout["layout_status"] if fa else
                                 ("SOURCE_WIDTH_ENVELOPE_PASS" if candidate and "script_width_unproved" not in hold
                                  else "LAYOUT_AMBIGUOUS"),
                "fit_result": ("relocatable" if payload and len(payload) > selected_row["slot_size"]
                               else "in_place" if payload else "not_measurable"),
                "pointer_owner_complete": not bool(owner["missing"] or owner["stale"]),
                "apply": apply, "final_apply": apply,
                "hold_reason": list(dict.fromkeys(hold)),
                "final_japanese": candidate if apply else None,
                "review_source": row["review_provenance"],
                "japanese_encoded_bytes_pre_controlfix": len(payload) if payload else None}
        annotated.append(item)
        if fa:
            controls = source["control_segments"]
            fa_rows.append({"id": entry_id, "rom_offset": f"0x{selected_row['rom_offset']:08X}",
                            "source_segments": controls,
                            "japanese_segments": pieces,
                            "source_controls": source["source_boundary_sequence"],
                            "output_controls": layout.get("output_controls"),
                            "segment_count": len(controls), "FA_count": source["controls"]["FA"],
                            "semantic_status": fa_class(row), "overall_status": row["status"],
                            "layout_status": layout["layout_status"],
                            "technical_fit_status": item["fit_result"],
                            "apply": apply, "hold_reason": list(dict.fromkeys(hold)),
                            "pointer_owners": selected_row["pointer_owners"],
                            "rom_destination": None,
                            "placement": "pending_controlfix" if apply else "held_english",
                            **layout})
        if row["status"] == "needs_technical_fit":
            fit_rows.append(fit_row(row, selected_row, owner, rom, candidate))
    if len(annotated) != 408 or len(fa_rows) != 122 or len(fit_rows) != 80:
        raise ValueError("Batch 03 review/FA/fit accounting incomplete")
    if len({row["id"] for row in baseline + safe}) != len(baseline) + len(safe):
        raise ValueError("Combined input overlaps prior applied entries")
    fa_class_counts = Counter(row["semantic_status"] for row in fa_rows)
    if fa_class_counts != {"semantic_confirmed_review": 51, "segment_conflict": 41,
                           "context_hold_only": 21, "technical_nonconflict_hold": 9}:
        raise ValueError(f"Unexpected FA classification: {fa_class_counts}")
    for filename, data in (
        ("ja_phase6_batch03_review_validation.json", validation),
        ("ja_phase6_batch03_owner_audit.json", owners),
        ("ja_phase6_batch03_glossary_audit.json", glossary),
        ("ja_phase6_batch03_context_audit.json", contexts),
        ("ja_phase6_batch03_fit.json", {"metadata": {"count": 80,
              "result_counts": dict(Counter(row["fit_result"] for row in fit_rows))}, "entries": fit_rows}),
        ("ja_phase6_batch03_fa_audit.json", {"metadata": {
              "counts": {"no_FA": 286, "FA_simple_structure": 2, "FA_complex_structure": 120},
              "segmented_handoff_required": 122, "classification_counts": dict(fa_class_counts),
              "layout_counts": dict(Counter(row["layout_status"] for row in fa_rows)),
              "applied_count": sum(row["apply"] for row in fa_rows)}, "entries": fa_rows}),
        ("ja_phase6_batch03_fa_retranslation.json", retranslation_handoff(fa_rows)),
        ("ja_phase6_batch03_reviewed.json", {"metadata": {"phase": "6B-3", "reviewed": 408,
              "safe_application_count": len(safe), "hold_count": 408 - len(safe),
              "original_status_counts": dict(Counter(row["status"] for row in review))},
              "entries": annotated}),
        ("ja_phase6_batch03_safe_input.json", {"entries": safe}),
        ("ja_phase6_batch03_combined_input.json", {"entries": baseline + safe}),
    ):
        write(OUT / filename, data)
    print({"review": 408, "FA": dict(fa_class_counts),
           "FA_layout": dict(Counter(row["layout_status"] for row in fa_rows)),
           "fit": dict(Counter(row["fit_result"] for row in fit_rows)),
           "safe": len(safe), "combined": len(baseline) + len(safe)})


if __name__ == "__main__":
    build()
