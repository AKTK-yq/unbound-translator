#!/usr/bin/env python3
"""Gate Batch 04 review: PokeAPI names, battle buffers, FA segments and measured width.

Two stages, both regenerable:

* ``candidates`` writes every encodable reviewed candidate (plus the Batch 03
  controlfixed baseline) so ordinary controlfix can wrap the prose;
* ``finalize`` measures the controlfixed candidates with ROM glyph widths and
  writes the reviewed audit, the safe subset and the combined baseline+safe input.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import runpy
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.fa_control import reconstruct_reviewed_segments
from lib.pcs_text import Charmap
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
BASELINE = OUT / "ja_phase6_batch03_controlfix.json"
BASELINE_COUNT = 1351
STATUSES = {"confirmed", "existing_official", "existing_glossary", "needs_context", "needs_technical_fit"}
APPROVED = {"confirmed", "existing_glossary", "existing_official"}
HAN = re.compile(r"[㐀-鿿]")
RAW_SUFFIX = re.compile(r"\\(?:07|08|0C)(?![0-9A-Fa-f])")
BATTLE_CODE = re.compile(r"\\\\([0-9A-F]{2})")
MODEL_BOX_PIXELS = 208  # Existing diagnostic model, not proved Unbound renderer width.
GBA_WIDTH = 240
SEGMENT_TOKENS = re.compile(r"\[[a-z0-9_]+\]|\\\.|\\CC[0-9A-F]+|\\qo|\\qc")

# pret/pokefirered include/battle_message.h: fixed engine meanings (names/move/ability).
BATTLE_SAFE = {"0F": "B_TXT_ATK_NAME_WITH_PREFIX", "10": "B_TXT_DEF_NAME_WITH_PREFIX",
               "11": "B_TXT_EFF_NAME_WITH_PREFIX", "13": "B_TXT_SCR_ACTIVE_NAME_WITH_PREFIX",
               "14": "B_TXT_CURRENT_MOVE", "1A": "B_TXT_SCR_ACTIVE_ABILITY"}
BATTLE_HOLD = {"00": "B_TXT_BUFF1 (value written per battle script; type varies)",
               "01": "B_TXT_BUFF2 (value written per battle script; type varies)",
               "2A": "B_TXT_ATK_PREFIX2 (English side-prefix string)",
               "36": "CFRU extension above vanilla 0x30; English team prefix, meaning unproved",
               "38": "CFRU extension above vanilla 0x30; English team prefix, meaning unproved"}
# FireRed StringExpandPlaceholders: FD 01 = player name, FD 06 = rival name.
FIELD_SAFE = {"[player]": "PLACEHOLDER_ID_PLAYER (FD 01)", "[rival]": "PLACEHOLDER_ID_RIVAL (FD 06)"}


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_inputs():
    rom = ROM.read_bytes()
    if hashlib.md5(rom).hexdigest() != SOURCE_MD5:
        raise ValueError("Source ROM MD5 mismatch")
    review = read(ROOT / "tests/fixtures/ja_phase6_batch04_claude_review.json")
    segmented = read(OUT / "ja_phase6_batch04_fa_segmented_input.json")["entries"]
    selection = [row for row in read(ROOT / "tests/fixtures/ja_phase6_selection.json")["entries"]
                 if row.get("batch_number") == 4]
    names = read(OUT / "ja_phase6_batch04_official_name_audit.json")
    return rom, review, segmented, selection, names


def review_validation(review, source, selection):
    if len(review) != 408 or len(source) != 408 or len(selection) != 408:
        raise ValueError("Review/source/selection must each contain 408 entries")
    ids = [row["id"] for row in review]
    if len(ids) != len(set(ids)) or ids != [row["id"] for row in source]:
        raise ValueError("Review IDs/order differ from segmented source")
    if set(ids) != {row["id"] for row in selection}:
        raise ValueError("Review IDs differ from Batch 04 selection")
    codec = Charmap("ja")
    details = []
    for row, original in zip(review, source):
        errors = []
        if row["original"] != original["original"] or row["category"] != original["category"]:
            errors.append("original_or_category")
        if row["status"] not in STATUSES or row.get("review_source") != "claude_cli":
            errors.append("status_or_review_source")
        if row.get("conversation_id") != original.get("conversation_id") or row.get("scene_id") != original.get("scene_id"):
            errors.append("conversation_or_scene")
        fa = bool(original.get("control_segments"))
        if fa != bool(row.get("fa_segmented")):
            errors.append("fa_flag")
        if fa:
            pieces = row.get("segments", [])
            if len(pieces) != len(original["control_segments"]):
                errors.append("fa_segment_count")
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
            for key in ("reviewed_japanese", "candidate_japanese"):
                text = row.get(key)
                if not text:
                    continue
                expected = semantic_tokens(strip_hma_quotes(row["original"]))
                actual = semantic_tokens(text)
                # Held candidates may reorder tokens (never apply); reviewed text must keep order.
                if (actual != expected if key == "reviewed_japanese"
                        else Counter(map(str, actual)) != Counter(map(str, expected))):
                    errors.append(f"{key}_protected_token")
                if HAN.search(text):
                    errors.append(f"{key}_kanji")
                try:
                    codec.encode("[japanese]" + text + "[latin]")
                except (UnicodeEncodeError, ValueError):
                    errors.append(f"{key}_charmap")
        details.append({"id": row["id"], "status": row["status"], "review_source": row["review_source"],
                        "fa": fa, "issues": sorted(set(errors))})
    if any(row["issues"] for row in details):
        raise ValueError(f"Review validation failed: {[x for x in details if x['issues']][:4]}")
    fa_rows = [s for s in source if s.get("control_segments")]
    return {"metadata": {
        "count": 408, "issue_count": 0,
        "review_source_counts": dict(Counter(x["review_source"] for x in details)),
        "status_counts": dict(Counter(x["status"] for x in details)),
        "non_fa": 408 - len(fa_rows), "fa": len(fa_rows),
        "fa_controls": sum(s["controls"]["FA"] for s in fa_rows),
        "fa_segments": sum(len(s["control_segments"]) for s in fa_rows),
        "multiple_fa_entries": sum(s["controls"]["FA"] > 1 for s in fa_rows)},
        "entries": details}


def glossary_audit(review, selection, candidates):
    matcher = load_glossary(ROOT / "glossaries/ja.json", expected_language="ja")
    chosen = {row["id"]: row for row in selection}
    rows = []
    for row in review:
        source = chosen[row["id"]]
        text = source.get("translation_source") or strip_hma_quotes(row["original"])
        matches = matcher.matches(text, row["category"], entry_id=row["id"])
        approved = [term.source for _begin, _end, term in matches]
        used = [claim.split("=")[0].strip() for claim in row.get("glossary_terms_used", [])]
        filtered = [term.source for term in matcher.terms
                    if term.source.casefold() in text.casefold() and term.source not in approved]
        rows.append({"id": row["id"], "approved_matches": approved, "review_claims": used,
                     "claim_scope_valid": all(term in approved for term in used),
                     "filtered_substrings": sorted(set(filtered))})
    proposals = []
    for candidate in candidates:
        exact = [{"source": t.source, "target": t.target, "kind": t.kind}
                 for t in matcher.terms if t.source.casefold() == candidate["source"].casefold()]
        overlapping = [t.source for t in matcher.terms
                       if t.source.casefold() in candidate["source"].casefold()
                       or candidate["source"].casefold() in t.source.casefold()]
        proposals.append({**candidate, "existing_glossary_conflict": exact,
                          "overlapping_approved_terms": sorted(set(overlapping)),
                          "context_scope": ("mission_names" if candidate["type"] == "mission_title" else
                                            "global_location" if candidate["type"] == "location" else
                                            "entry_scoped_proposal"),
                          "pokeapi_applicability": candidate["type"] in
                          {"pokemon", "move", "item", "ability", "type", "nature"},
                          "status": "proposal_only_not_approved"})
    if len(proposals) != 55 or any(not x["claim_scope_valid"] for x in rows):
        raise ValueError("Glossary review scope or candidate count changed")
    return {"metadata": {"reviewed": 408, "candidate_count": 55,
                         "candidate_type_counts": dict(Counter(x["type"] for x in proposals)),
                         "scope_collision_count": 0,
                         "filtered_substring_entries": sum(bool(x["filtered_substrings"]) for x in rows),
                         "rule": "Only boundary-safe, scoped matches count; proposals are not approved."},
            "review_matches": rows, "candidate_entries": proposals}


def existing_glossary_audit(review, selection):
    matcher = load_glossary(ROOT / "glossaries/ja.json", expected_language="ja")
    chosen = {row["id"]: row for row in selection}
    rows = []
    for row in review:
        if row["status"] != "existing_glossary":
            continue
        source = strip_hma_quotes(row["original"])
        match = re.fullmatch(r"Route (\d+)", source)
        det = chosen[row["id"]]["deterministic_translation"]
        if match:
            expected = f"{match.group(1)}ばんどうろ"
            kind = "route_template"
        else:
            hits = matcher.matches(source, row["category"], entry_id=row["id"])
            expected = hits[0][2].target if len(hits) == 1 and hits[0][0] == 0 and hits[0][1] == len(source) else None
            kind = "deterministic_location"
        rows.append({"id": row["id"], "source": source, "kind": kind,
                     "reviewed": row["reviewed_japanese"], "expected": expected,
                     "deterministic_value": det,
                     "number_preserved": bool(match) and match.group(1) in row["reviewed_japanese"],
                     "valid": row["reviewed_japanese"] == expected and (det is None or det == expected)})
    route_prose = [r["id"] for r in review
                   if re.search(r"\broute\b", strip_hma_quotes(r["original"]), re.IGNORECASE)
                   and r["status"] != "existing_glossary"
                   and any(t.startswith("Route") for t in (r.get("glossary_terms_used") or []))]
    if len(rows) != 17 or not all(r["valid"] for r in rows):
        raise ValueError("Existing glossary entries do not match approved scope")
    return {"metadata": {"count": 17, "kinds": dict(Counter(r["kind"] for r in rows)),
                         "route_template_misapplied_to_prose": route_prose},
            "entries": rows}


def buffer_audit(selected_row, original):
    tokens = BATTLE_CODE.findall(original)
    safe, hold = [], []
    for code in tokens:
        (safe if code in BATTLE_SAFE else hold).append(code)
    field = [t for t in selected_row["buffers"] if not t.startswith("\\")]
    field_hold = [t for t in field if t not in FIELD_SAFE]
    result = "none"
    if tokens or field:
        result = "resolved_type" if not hold and not field_hold and not RAW_SUFFIX.search(original) else "unknown"
    return {"battle_codes": tokens, "battle_safe": sorted(set(safe)), "battle_hold": sorted(set(hold)),
            "field_tokens": field, "field_hold": field_hold,
            "raw_suffix": RAW_SUFFIX.findall(original), "result": result}


def apply_names(row, name_rows, text, segments):
    reasons = []
    for term in name_rows:
        status = term["verification_result"]
        if status not in {"verified_exact", "verified_difference"}:
            reasons.append(f"unverified_official_name:{term['English term']}:{status}")
            continue
        final, proposal = term["final_value"], term["proposed_japanese"]
        if final in text:
            continue
        if not proposal or proposal not in text:
            reasons.append(f"official_value_not_located:{term['English term']}")
            continue
        if segments is None:
            text = text.replace(proposal, final)
        else:
            hit = [i for i, piece in enumerate(segments) if proposal in piece]
            if len(hit) != 1:
                reasons.append(f"official_name_crosses_segment:{term['English term']}")
                continue
            segments[hit[0]] = segments[hit[0]].replace(proposal, final)
    return text, segments, reasons


def long_segment_audit(source, segments):
    """Every translated FA segment above 18 visible kana, measured in ROM glyph pixels."""
    codec = Charmap("ja")
    rows = []
    for index, text in enumerate(segments or []):
        if not text:
            continue
        visible = len(SEGMENT_TOKENS.sub("", text))
        if visible <= 18:
            continue
        pixels = max(line_widths(codec.encode("[japanese]" + text + "[latin]")))
        rows.append({"segment_index": index, "visible_chars": visible, "pixels": pixels,
                     "class": ("WIDTH_OVERFLOW" if pixels > GBA_WIDTH else
                               "LAYOUT_AMBIGUOUS" if pixels > MODEL_BOX_PIXELS else
                               "RENDERER_UNKNOWN" if source.get("buffers") else "FIT")})
    return rows


def fa_layout(row, source, owner, rom, segments):
    raw = source_raw(rom, source)
    result = {"source_line_pixels": line_widths(raw), "japanese_line_pixels": None,
              "source_layout_trace": layout_trace(raw), "japanese_layout_trace": None,
              "source_control_counts": source["controls"], "output_controls": None,
              "box_width_pixels_model": MODEL_BOX_PIXELS,
              "box_width_proof": "not pixel-perfect; 208px is a diagnostic model",
              "visible_lines_model": 2, "font": "ROM normal Latin/Japanese glyph-width tables",
              "automatic_wrap": "none modelled; each segment is one rendered line",
              "buffer_width_estimate": 54,
              "input_wait_semantics": "FA waits then scrolls one line; FB waits then clears",
              "layout_status": "NOT_SEMANTICALLY_APPROVED", "layout_reason": "Semantic review is not confirmed",
              "long_segments": long_segment_audit(source, segments)}
    if row["status"] not in APPROVED:
        return result
    if not segments or any(p["text"].strip() and not (t or "").strip()
                           for p, t in zip(source["control_segments"], segments)):
        result.update(layout_status="LAYOUT_AMBIGUOUS", layout_reason="Missing translated segment")
        return result
    rebuilt = reconstruct_reviewed_segments(strip_hma_quotes(source["original"]),
                                            source["control_segments"], segments)
    payload = Charmap("ja").encode("[japanese]" + rebuilt + "[latin]")
    widths = line_widths(payload)
    target = [s["after_control"] for s in source["control_segments"] if s["after_control"]]
    result.update(japanese_line_pixels=widths, japanese_layout_trace=layout_trace(payload),
                  output_controls=target, encoded_japanese_bytes=len(payload),
                  source_segment_count=len(source["control_segments"]), output_segment_count=len(segments),
                  source_fa_count=source["controls"].get("FA", 0), output_fa_count=target.count("FA"),
                  source_max_line_pixels=max(result["source_line_pixels"]),
                  japanese_max_line_pixels=max(widths))
    if owner["missing"] or owner["stale"]:
        result.update(layout_status="TECHNICAL_OWNER_HOLD", layout_reason="Pointer ownership incomplete")
    elif source.get("buffers") or RAW_SUFFIX.search(source["original"]):
        result.update(layout_status="LAYOUT_AMBIGUOUS", layout_reason="Dynamic substitution width/page state unproved")
    elif max(widths) > GBA_WIDTH:
        result.update(layout_status="LAYOUT_OVERFLOW", layout_reason="Wider than 240px GBA display")
    elif max(widths) > MODEL_BOX_PIXELS or max(widths) > max(result["source_line_pixels"]):
        result.update(layout_status="LAYOUT_AMBIGUOUS",
                      layout_reason="Japanese line exceeds diagnostic 208px or observed source-line envelope")
    elif target != source["source_boundary_sequence"]:
        result.update(layout_status="LAYOUT_AMBIGUOUS", layout_reason="FE/FA/FB boundary mismatch")
    else:
        result.update(layout_status="LAYOUT_PASS",
                      layout_reason="Same ROM-derived boundaries; each Japanese line <=208px and <= source maximum")
    return result


def context_audit(review, selected, rom):
    rows = []
    for row in review:
        if row["status"] != "needs_context":
            continue
        source = selected[row["id"]]
        owners = []
        for pointer in source["pointer_owners"]:
            offset = int(pointer, 16)
            owners.append({"rom_offset": pointer, "kind": operand_kind(rom, offset),
                           "direct_buffer_writer": direct_literal(rom, offset),
                           "nearby_writer_candidates": nearby_writers(rom, offset)[:8]})
        buffers = buffer_audit(source, row["original"])
        dynamic = [b for b in source["buffers"] if b.startswith("[buffer")]
        text = strip_hma_quotes(row["original"])
        classification = ("battle_buffer" if buffers["battle_hold"] else
                          "field_buffer" if dynamic else
                          "raw_suffix" if buffers["raw_suffix"] else
                          "gendered_fragment" if text in {"daughter", "son", "boy", "girl"} else
                          "standalone_name")
        resolution = "unknown"
        if classification == "battle_buffer":
            resolution = "runtime_dynamic"
        rows.append({"id": row["id"], "fa": bool(row.get("fa_segmented")),
                     "classification": classification, "source": text,
                     "buffer_tokens": dynamic, "battle_codes": buffers["battle_codes"],
                     "battle_hold_meanings": {c: BATTLE_HOLD.get(c, "unclassified") for c in buffers["battle_hold"]},
                     "raw_suffixes": buffers["raw_suffix"], "pointer_owners": owners,
                     "resolution": resolution,
                     "technical_resolution": "unproved",
                     "hold_reason": "Writer/value, runtime caller or meaning remains unresolved; no translation authored"})
    if len(rows) != 28:
        raise ValueError(f"Expected 28 Batch 04 context holds, got {len(rows)}")
    return {"metadata": {"count": 28, "classification_counts": dict(Counter(r["classification"] for r in rows)),
                         "technically_resolved": 0}, "entries": rows}


def fa_class(row):
    if row["status"] in APPROVED:
        return "semantic_confirmed_review"
    if any(w.casefold() == "fa_segment_semantic_conflict" for w in row.get("review_warning", [])):
        return "segment_conflict"
    if row["status"] == "needs_context":
        return "context_hold_only"
    return "technical_nonconflict_hold"


def retranslation_context(review, source):
    row = next(r for r in review if r["id"] == "scr_1F48ED0")
    segs = source["scr_1F48ED0"]["control_segments"]
    return {"id": "scr_1F48ED0", "status": "hold_for_claude_retranslation",
            "reviewer_reason": row["reason"], "source_boundary_sequence": source["scr_1F48ED0"]["source_boundary_sequence"],
            "conflict_segments": [{"segment_index": i, "english": segs[i]["text"],
                                   "after_control": segs[i]["after_control"],
                                   "claude_candidate": row["segments"][i]["reviewed_japanese"]} for i in (2, 3, 4)],
            "constraint": "Keep FA after segment 3 (source). Revise wording inside segments 2-4 only; do not move FA.",
            "no_codex_translation": True}


def stage_candidates():
    rom, review, segmented, selection, names = load_inputs()
    selected = {row["id"]: row for row in selection}
    source = {row["id"]: row for row in segmented}
    names_by_id = defaultdict(list)
    for name in names["entries"]:
        names_by_id[name["entry_id"]].append(name)
    prepared = {row["id"]: row for row in read(ROOT / "out/ja-phase5e-prepared.json")["entries"]}
    baseline = read(BASELINE)["entries"]
    if len(baseline) != BASELINE_COUNT:
        raise ValueError("Batch 03 controlfixed baseline changed")
    candidates = []
    for row in review:
        if row["status"] not in APPROVED or row.get("fa_segmented"):
            continue
        text = row["reviewed_japanese"]
        text, _, reasons = apply_names(row, names_by_id[row["id"]], text, None)
        if reasons:
            continue
        prepared_row = dict(prepared[row["id"]])
        prepared_row["translated"] = text
        candidates.append(prepared_row)
    write(OUT / "ja_phase6_batch04_candidates_input.json", {"entries": baseline + candidates})
    print({"candidates": len(candidates), "combined": len(baseline) + len(candidates)})


def stage_finalize():
    rom, review, segmented, selection, names = load_inputs()
    selected = {row["id"]: row for row in selection}
    source = {row["id"]: row for row in segmented}
    names_by_id = defaultdict(list)
    for name in names["entries"]:
        names_by_id[name["entry_id"]].append(name)
    validation = review_validation(review, segmented, selection)
    owners = owner_audit([selected[row["id"]] for row in review], rom)
    by_owner = {row["id"]: row for row in owners["entries"]}
    glossary = glossary_audit(review, selection, read(ROOT / "tests/fixtures/ja_phase6_batch04_glossary_candidates.json"))
    glossary_by_id = {row["id"]: row for row in glossary["review_matches"]}
    existing = existing_glossary_audit(review, selection)
    contexts = context_audit(review, selected, rom)
    prepared = {row["id"]: row for row in read(ROOT / "out/ja-phase5e-prepared.json")["entries"]}
    baseline = read(BASELINE)["entries"]
    baseline_ids = {row["id"] for row in baseline}
    diag = {row["id"]: row for row in read(OUT / "ja_phase6_batch04_candidates_controlfix.json")["entries"]}
    injector = runpy.run_path(str(ROOT / "005_hybrid_injector.py"))
    codec = Charmap("ja")
    candidate_ids = {cand["source"] for cand in
                     read(ROOT / "tests/fixtures/ja_phase6_batch04_glossary_candidates.json")
                     if cand["type"] == "mission_title"}
    annotated, fa_rows, fit_rows, safe, name_audit = [], [], [], [], []
    for row in review:
        entry_id = row["id"]
        src, sel, owner = source[entry_id], selected[entry_id], by_owner[entry_id]
        fa = bool(src.get("control_segments"))
        pieces = [p["reviewed_japanese"] for p in row["segments"]] if fa else None
        text = row["reviewed_japanese"] if not fa else None
        hold = []
        if row["status"] not in APPROVED:
            hold.append("review_status:" + row["status"])
        name_reasons = []
        if row["status"] in APPROVED:
            if fa:
                if all(pieces):
                    _, pieces, name_reasons = apply_names(row, names_by_id[entry_id], " ".join(pieces), list(pieces))
            else:
                text, _, name_reasons = apply_names(row, names_by_id[entry_id], text, None)
        hold.extend(name_reasons)
        if owner["missing"] or owner["stale"]:
            hold.append("incomplete_pointer_ownership")
        if not glossary_by_id[entry_id]["claim_scope_valid"] or "possible_glossary_collision" in row["review_warning"]:
            hold.append("glossary_scope_unproved")
        buffers = buffer_audit(sel, row["original"])
        if buffers["result"] == "unknown":
            hold.append("dynamic_buffer_or_suffix_unproved")
        if row["category"] == "mission_names" and strip_hma_quotes(row["original"]) in candidate_ids:
            hold.append("mission_title_glossary_proposal_not_approved")
        if entry_id in baseline_ids:
            raise ValueError(f"Batch 04 overlaps existing applied baseline: {entry_id}")
        layout = None
        payload = None
        widths = None
        fit_result = "not_measurable"
        if fa:
            layout = fa_layout(row, {**sel, **src}, owner, rom, pieces)
            if row["status"] in APPROVED and layout["layout_status"] not in {"LAYOUT_PASS", "LAYOUT_WRAP_SAFE"}:
                hold.append("fa_layout:" + layout["layout_status"])
            if layout.get("encoded_japanese_bytes"):
                fit_result = "relocatable" if layout["encoded_japanese_bytes"] > sel["slot_size"] else "in_place"
        elif row["status"] in APPROVED and entry_id in diag:
            payload = injector["encode_text"](codec, injector["translation_for_injection"](diag[entry_id]),
                                              plain_script=sel["category"] == "plain_scripts")
            widths = line_widths(payload)
            source_widths = line_widths(source_raw(rom, sel))
            renderer = sel["renderer_group"]
            if max(widths) > GBA_WIDTH:
                fit_result = "width_overflow"
            elif renderer in {"event_dialogue", "battle_text_printer"} and (
                    max(widths) > MODEL_BOX_PIXELS or max(widths) > max(source_widths)):
                fit_result = "layout_ambiguous"
            elif renderer not in {"event_dialogue", "battle_text_printer"} and max(widths) > max(source_widths):
                fit_result = "layout_ambiguous"
            elif len(payload) > sel["slot_size"]:
                fit_result = "relocatable"
            else:
                fit_result = "in_place"
            if fit_result in {"width_overflow", "layout_ambiguous"}:
                hold.append("width_unproved:" + fit_result)
            if len(payload) > sel["slot_size"] and (sel["fixed"] or sel["no_relocation"] or not sel["relocation_possible"]):
                hold.append("unrelocatable_slot_overflow")
        elif row["status"] in APPROVED and not name_reasons:
            hold.append("no_complete_reviewed_draft")
        if row["status"] in APPROVED and fit_result in {"relocatable"} and (owner["missing"] or owner["stale"]):
            fit_result = "owner_incomplete"
        apply = not hold
        final = None
        if apply:
            prepared_row = dict(prepared[entry_id])
            if fa:
                prepared_row.update({"translated": None, "translated_segments": pieces,
                                     "control_segments": src["control_segments"],
                                     "source_boundary_sequence": src["source_boundary_sequence"],
                                     "fa_placement_policy": "require_segments",
                                     "fa_layout_reviewed": True, "controls": src["controls"]})
                final = reconstruct_reviewed_segments(strip_hma_quotes(src["original"]),
                                                      src["control_segments"], pieces)
            else:
                prepared_row["translated"] = text
                final = text
            safe.append(prepared_row)
        for term in names_by_id[entry_id]:
            name_audit.append({"entry_id": entry_id, "English term": term["English term"],
                               "term type": term["term_type"], "provisional Japanese": term["provisional_japanese"],
                               "PokeAPI Japanese": term["pokeapi_japanese"],
                               "verification result": term["verification_result"],
                               "final value": term["final_value"], "changed": term["changed"],
                               "apply impact": ("applied" if apply else
                                                "entry_held_unverified_name" if term["final_value"] is None else
                                                "verified_but_entry_held_for_other_reason"),
                               "notes": term["notes"]})
        item = {"id": entry_id, "category": row["category"], "original": row["original"],
                "review_status": row["status"], "review_source": row["review_source"],
                "semantic_status": fa_class(row) if fa else row["status"],
                "official_name_result": [{"term": t["English term"], "result": t["verification_result"],
                                          "final_value": t["final_value"]} for t in names_by_id[entry_id]],
                "glossary_result": {"approved_matches": glossary_by_id[entry_id]["approved_matches"],
                                    "claim_scope_valid": glossary_by_id[entry_id]["claim_scope_valid"],
                                    "proposal_terms": [c["source"] for c in row.get("new_glossary_candidates", [])]},
                "buffer_result": buffers,
                "fa_segmented": fa,
                "fa_semantic_result": fa_class(row) if fa else "not_applicable",
                "fa_layout_result": layout["layout_status"] if fa else "not_applicable",
                "fit_result": fit_result,
                "japanese_line_pixels": layout["japanese_line_pixels"] if fa else widths,
                "japanese_encoded_bytes": (layout.get("encoded_japanese_bytes") if fa else
                                           len(payload) if payload else None),
                "slot_size": sel["slot_size"], "renderer_group": sel["renderer_group"],
                "pointer_owner_complete": not bool(owner["missing"] or owner["stale"]),
                "apply": apply, "final_apply": apply,
                "hold_reason": list(dict.fromkeys(hold)),
                "final_japanese": final}
        if fa:
            item.update(source_boundary_sequence=src["source_boundary_sequence"], translated_segments=pieces)
        annotated.append(item)
        if fa:
            fa_rows.append({"id": entry_id, "rom_offset": f"0x{sel['rom_offset']:08X}",
                            "source_segments": src["control_segments"], "japanese_segments": pieces,
                            "source_controls": src["source_boundary_sequence"],
                            "segment_count": len(src["control_segments"]), "FA_count": src["controls"]["FA"],
                            "controls": src["controls"],
                            "semantic_status": fa_class(row), "overall_status": row["status"],
                            "context_status": "hold" if row["status"] == "needs_context" else "clear",
                            "fit_status": fit_result, "apply": apply,
                            "hold_reason": list(dict.fromkeys(hold)),
                            "pointer_owners": sel["pointer_owners"], "rom_placement": None,
                            "placement": "pending_controlfix" if apply else "held_english",
                            **{k: v for k, v in layout.items()}})
        if row["status"] in APPROVED or row["status"] == "needs_technical_fit":
            fit_rows.append({"id": entry_id, "category": sel["category"], "renderer_group": sel["renderer_group"],
                             "slot_size": sel["slot_size"], "source_encoded_bytes": sel["source_encoded_size"],
                             "fixed": sel["fixed"], "no_relocation": sel["no_relocation"],
                             "pointer_owners": sel["pointer_owners"],
                             "owner_missing": owner["missing"], "owner_stale": owner["stale"],
                             "relocation_possible": sel["relocation_possible"],
                             "japanese_encoded_bytes": item["japanese_encoded_bytes"],
                             "japanese_line_pixels": item["japanese_line_pixels"],
                             "source_line_pixels": line_widths(source_raw(rom, sel)),
                             "renderer_width_pixels": None,
                             "renderer_width_evidence": "Exact window width unproved; 208px diagnostic for dialogue/battle, source envelope for mission UI",
                             "structured_constraint": sel["renderer_group"] not in {"event_dialogue", "battle_text_printer"},
                             "fit_result": fit_result if row["status"] in APPROVED else "not_measured_held",
                             "apply": apply})
    if len(annotated) != 408 or len(fa_rows) != 50:
        raise ValueError("Batch 04 review/FA accounting incomplete")
    fa_counts = Counter(r["semantic_status"] for r in fa_rows)
    if fa_counts != {"semantic_confirmed_review": 48, "segment_conflict": 1, "context_hold_only": 1}:
        raise ValueError(f"Unexpected FA classification: {fa_counts}")
    long_rows = [dict(seg, id=r["id"]) for r in fa_rows for seg in r.get("long_segments", [])]
    write(OUT / "ja_phase6_batch04_review_validation.json", validation)
    write(OUT / "ja_phase6_batch04_owner_audit.json", owners)
    write(OUT / "ja_phase6_batch04_glossary_audit.json", glossary)
    write(OUT / "ja_phase6_batch04_existing_glossary_audit.json", existing)
    write(OUT / "ja_phase6_batch04_context_audit.json", contexts)
    write(OUT / "ja_phase6_batch04_official_name_audit.json",
          {**names, "technical_entries": name_audit})
    write(OUT / "ja_phase6_batch04_fit.json", {"metadata": {
        "count": len(fit_rows), "result_counts": dict(Counter(r["fit_result"] for r in fit_rows)),
        "fixed_count": sum(r["fixed"] for r in fit_rows)}, "entries": fit_rows})
    write(OUT / "ja_phase6_batch04_fa_audit.json", {"metadata": {
        "fa_entries": 50, "fa_controls": sum(r["FA_count"] for r in fa_rows),
        "segments": sum(r["segment_count"] for r in fa_rows),
        "classification_counts": dict(fa_counts),
        "layout_counts": dict(Counter(r["layout_status"] for r in fa_rows)),
        "long_segment_count": len(long_rows),
        "long_segment_entries": len({r["id"] for r in long_rows}),
        "long_segment_class_counts": dict(Counter(r["class"] for r in long_rows)),
        "applied_count": sum(r["apply"] for r in fa_rows)},
        "long_segments": long_rows, "entries": fa_rows})
    write(OUT / "ja_phase6_batch04_fa_retranslation.json", retranslation_context(review, source))
    write(OUT / "ja_phase6_batch04_reviewed.json", {"metadata": {
        "phase": "6B-4", "reviewed": 408, "safe_application_count": len(safe),
        "hold_count": 408 - len(safe),
        "original_status_counts": dict(Counter(r["status"] for r in review)),
        "hold_reason_counts": dict(Counter(h.split(":")[0] for r in annotated for h in r["hold_reason"]))},
        "entries": annotated})
    write(OUT / "ja_phase6_batch04_safe_input.json", {"entries": safe})
    write(OUT / "ja_phase6_batch04_combined_input.json", {"entries": baseline + safe})
    print({"safe": len(safe), "fa": dict(fa_counts),
           "fa_layout": dict(Counter(r["layout_status"] for r in fa_rows)),
           "fa_applied": sum(r["apply"] for r in fa_rows),
           "fit": dict(Counter(r["fit_result"] for r in fit_rows)),
           "long": dict(Counter(r["class"] for r in long_rows)),
           "holds": dict(Counter(h.split(":")[0] for r in annotated for h in r["hold_reason"]))})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["candidates", "finalize"])
    args = parser.parse_args()
    stage_candidates() if args.stage == "candidates" else stage_finalize()
