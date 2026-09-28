#!/usr/bin/env python3
"""Reproducible, fail-closed Batch 05 review, fit and injection inputs."""

from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import runpy
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.pcs_text import Charmap, fc_arg_count
from lib.renderer_profiles import normal_line_widths_with_placeholders
from lib.translation_glossary import load_glossary
from lib.translation_tokens import semantic_tokens, strip_hma_quotes
from scripts.audit_ja_phase6_batch01_fit import line_widths
from scripts.build_ja_phase6_batch02 import owner_audit

OUT = ROOT / "out/phase6"
FIX = ROOT / "tests/fixtures"
SOURCE_MD5 = "9cad8e771940e7f7094d13911552cef0"
BASELINE_SHA256 = "3cc314c7ceb3cd6057d8c6fb71194af0e4691f54a06b0174d9b06c41900dae0e"
APPROVED = {"confirmed", "existing_glossary"}
HAN = re.compile(r"[㐀-鿿]")
STRUCTURED = {"structured_columns_unverified", "structured_columns_or_margin",
              "structured_column_collision_risk", "structured_layout_collision",
              "fixed_length_constraint", "fixed_length_field", "no_relocation"}
CONTEXT = {"ui_context_unverified", "fragment_context_unverified", "source_mojibake",
           "source_ambiguous", "term_semantics_unverified", "ambiguous_short_source",
           "term_disambiguation_unverified", "case_variant_collapsed"}


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def inputs():
    rom = (ROOT / "rom/unbound.gba").read_bytes()
    if hashlib.md5(rom).hexdigest() != SOURCE_MD5:
        raise ValueError("Source ROM MD5 differs")
    previous_rom = ROOT / "out/unbound-ja-phase6-batch04.gba"
    if hashlib.sha256(previous_rom.read_bytes()).hexdigest() != BASELINE_SHA256:
        raise ValueError("Batch 04 ROM differs")
    review = read(FIX / "ja_phase6_batch05_claude_review.json")
    source = read(OUT / "ja_phase6_batch05_fa_segmented_input.json")["entries"]
    selected = [row for row in read(FIX / "ja_phase6_selection.json")["entries"]
                if row.get("batch_number") == 5]
    baseline = read(OUT / "ja_phase6_batch04_controlfix.json")["entries"]
    if len(baseline) != 1549:
        raise ValueError("Batch 04 applied baseline is not 1,549")
    return rom, review, source, selected, baseline


def validate(review, source, selected):
    if not (len(review) == len(source) == len(selected)):
        raise ValueError("Review/source/selection count differs")
    ids = [row["id"] for row in review]
    if len(ids) != 408 or len(set(ids)) != 408 or ids != [row["id"] for row in source] or set(ids) != {row["id"] for row in selected}:
        raise ValueError("Batch 05 IDs/order/uniqueness differ")
    codec = Charmap("ja")
    problems = []
    for row, src in zip(review, source):
        issues = []
        if row["original"] != src["original"] or row["category"] != src["category"]:
            issues.append("original_or_category")
        if row.get("review_source") != "claude_cli":
            issues.append("review_source")
        if row.get("source_controls") != src.get("controls"):
            issues.append("control_metadata")
        if row.get("protected_tokens_source") != src.get("protected_tokens"):
            issues.append("protected_token_metadata")
        if row.get("conversation_id") != src.get("conversation_id") or row.get("scene_id") != src.get("scene_id"):
            issues.append("context_metadata")
        is_fa = bool(src.get("control_segments"))
        if bool(row.get("fa_segmented")) != is_fa:
            issues.append("fa_metadata")
        if is_fa:
            pieces = row.get("segments", [])
            if len(pieces) != len(src["control_segments"]):
                issues.append("fa_segment_count")
            else:
                for a, b in zip(src["control_segments"], pieces):
                    if a["text"] != b["source"] or a["after_control"] != b["after_control"]:
                        issues.append("fa_boundary")
                    if b["reviewed_japanese"] and semantic_tokens(b["reviewed_japanese"]) != semantic_tokens(a["text"]):
                        issues.append("fa_tokens")
        elif row.get("reviewed_japanese"):
            target = row["reviewed_japanese"]
            if semantic_tokens(target) != semantic_tokens(strip_hma_quotes(row["original"])):
                issues.append("protected_tokens")
            if HAN.search(target):
                issues.append("kanji")
            try:
                if "latin_page_required" in row.get("review_warning", []) and target == strip_hma_quotes(row["original"]):
                    codec.encode(target)
                else:
                    codec.encode("[japanese]" + target + "[latin]")
            except (UnicodeEncodeError, ValueError):
                issues.append("pcs_encode")
        if issues:
            problems.append({"id": row["id"], "issues": issues})
    if problems:
        raise ValueError(f"Review validation failed: {problems[:8]}")
    statuses = Counter(row["status"] for row in review)
    if statuses != {"confirmed": 317, "existing_glossary": 1, "needs_context": 71, "needs_technical_fit": 19}:
        raise ValueError(f"Review status counts differ: {statuses}")
    fa = [row for row in source if row.get("control_segments")]
    if len(fa) != 4 or sum(row["controls"].get("FA", 0) for row in fa) != 4 or sum(len(row["control_segments"]) for row in fa) != 12:
        raise ValueError("FA count/order/segment accounting differs")
    return {"count": 408, "duplicate": 0, "extra": 0, "issue_count": 0,
            "review_source_counts": {"claude_cli": 408}, "status_counts": dict(statuses),
            "reviewed_nonempty": sum(bool(row.get("reviewed_japanese")) for row in review),
            "fa": 4, "fa_controls": 4, "fa_segments": 12}


def official_index(audit):
    grouped = defaultdict(list)
    for row in audit["entries"]:
        grouped[row["entry_id"]].append(row)
    if len(grouped) != 67:
        raise ValueError("Official-name audit must cover 67 entries")
    return grouped


def glossary_proposals(candidates):
    matcher = load_glossary(ROOT / "glossaries/ja.json", expected_language="ja")
    result = []
    for row in candidates:
        source = row["source"]
        overlapping = [term.source for term in matcher.terms
                       if source.casefold() in term.source.casefold() or term.source.casefold() in source.casefold()]
        result.append({**row, "scope": "entry_scoped_proposal", "existing_conflict": overlapping,
                       "pokeapi_applicability": row["type"] in {"pokemon", "move", "item", "ability", "type", "nature"},
                       "status": "proposal_only_not_approved"})
    if len(result) != 4:
        raise ValueError("Expected four glossary proposals")
    return result


def glossary_claim(row, selection):
    matcher = load_glossary(ROOT / "glossaries/ja.json", expected_language="ja")
    text = selection.get("translation_source") or strip_hma_quotes(row["original"])
    matches = matcher.matches(text, row["category"], entry_id=row["id"])
    approved = {term.source for _, _, term in matches}
    claims = {part.split("=")[0].strip() for part in row.get("glossary_terms_used", [])}
    return {"claims": sorted(claims), "approved_matches": sorted(approved),
            "scope_valid": claims <= approved}


def prelim(row, source, owner, names, glossary):
    hold = []
    if row["status"] not in APPROVED:
        hold.append("review_status:" + row["status"])
    if row.get("fa_segmented"):
        hold.append("fa_not_semantically_approved")
    if not row.get("reviewed_japanese"):
        hold.append("translation_incomplete_or_unreviewed")
    if any(item["PokeAPI result"]["status"] not in {"verified_exact", "verified_difference"} for item in names):
        hold.append("unresolved_official_name")
    if owner["missing"] or owner["stale"]:
        hold.append("pointer_owner_incomplete")
    if not glossary["scope_valid"]:
        hold.append("glossary_scope_unproved")
    if row["status"] == "existing_glossary" and row["reviewed_japanese"] != "バトルせってい":
        hold.append("existing_glossary_value_changed")
    warnings = set(row.get("review_warning", []))
    if warnings & STRUCTURED:
        hold.append("known_structured_constraint")
    if warnings & CONTEXT:
        hold.append("semantic_or_ui_context_unproved")
    if source.get("buffers"):
        hold.append("dynamic_buffer_width_or_page_unproved")
    if row["category"] == "menu_options" and source.get("renderer_confidence") == "PARTIAL":
        # Label and setting value share a row; no proved column boundary.
        hold.append("options_shared_row_column_unproved")
    if row["category"] == "menu_battle" and "\\CC13" in row.get("reviewed_japanese", ""):
        hold.append("two_column_cursor_margin_unproved")
    if row.get("reviewed_japanese") == strip_hma_quotes(row["original"]):
        hold.append("no_japanese_change")
    return list(dict.fromkeys(hold))


def stage_prepare():
    rom, review, source, selected, baseline = inputs()
    validation = validate(review, source, selected)
    names = official_index(read(OUT / "ja_phase6_batch05_official_name_audit.json"))
    owners = owner_audit(selected, rom)
    by_owner = {x["id"]: x for x in owners["entries"]}
    by_source = {x["id"]: x for x in source}
    by_select = {x["id"]: x for x in selected}
    prepared = {x["id"]: x for x in read(ROOT / "out/ja-phase5e-prepared.json")["entries"]}
    baseline_ids = {x["id"] for x in baseline}
    candidates, plan = [], []
    for row in review:
        key = row["id"]
        if key in baseline_ids:
            raise ValueError(f"Batch 05 overlaps baseline: {key}")
        glossary = glossary_claim(row, by_select[key])
        hold = prelim(row, by_source[key], by_owner[key], names[key], glossary)
        plan.append({"id": key, "preliminary_hold": hold, "glossary": glossary})
        if not hold:
            candidate = dict(prepared[key])
            candidate["translated"] = row["reviewed_japanese"]
            candidates.append(candidate)
    write(OUT / "ja_phase6_batch05_review_validation.json", {"metadata": validation})
    write(OUT / "ja_phase6_batch05_owner_audit.json", owners)
    write(OUT / "ja_phase6_batch05_preliminary_plan.json", {"entries": plan})
    write(OUT / "ja_phase6_batch05_candidates_input.json", {"entries": baseline + candidates})
    print({"validated": 408, "preliminary_candidates": len(candidates),
           "owner_mismatches": owners["metadata"]["mismatch_count"]})


def technical_class(row):
    if row["status"] != "needs_technical_fit":
        return None
    if not row["reviewed_japanese"] and "claude_cli_session_limit_prevented_revision" in row["review_warning"]:
        return "TRANSLATION_INCOMPLETE"
    if row.get("fa_segmented"):
        return "FA_SEMANTIC_CONFLICT"
    if row["category"] == "menu_options":
        return "STRUCTURED_CONSTRAINT"
    if set(row.get("review_warning", [])) & STRUCTURED:
        return "STRUCTURED_CONSTRAINT"
    return "OTHER"


def control_sequence(data):
    """Source/output structural controls, excluding added Japanese page switches."""
    result = []
    index = 0
    while index < len(data):
        byte = data[index]
        index += 1
        if byte == 0xFF:
            break
        if byte in (0xFE, 0xFA, 0xFB):
            result.append(f"{byte:02X}")
        elif byte == 0xFC:
            code = data[index]
            index += 1
            arguments = data[index:index + fc_arg_count(code)]
            index += len(arguments)
            if code not in (0x15, 0x16):
                result.append(f"FC{code:02X}:{arguments.hex()}")
        elif byte == 0xFD:
            code = data[index]
            index += 1
            result.append(f"FD{code:02X}")
    return result


def stage_finalize():
    rom, review, source, selected, baseline = inputs()
    plan = {x["id"]: x for x in read(OUT / "ja_phase6_batch05_preliminary_plan.json")["entries"]}
    owners = {x["id"]: x for x in read(OUT / "ja_phase6_batch05_owner_audit.json")["entries"]}
    official_audit = read(OUT / "ja_phase6_batch05_official_name_audit.json")
    names = official_index(official_audit)
    by_source, by_select = ({x["id"]: x for x in rows} for rows in (source, selected))
    controlled = read(OUT / "ja_phase6_batch05_candidates_controlfix.json")["entries"]
    if controlled[:1549] != baseline:
        raise ValueError("Controlfix altered an existing Batch 04 entry")
    diag = {x["id"]: x for x in controlled[1549:]}
    injector = runpy.run_path(str(ROOT / "005_hybrid_injector.py"))
    codec = Charmap("ja")
    rows, safe = [], []
    for row in review:
        key, src, sel = row["id"], by_source[row["id"]], by_select[row["id"]]
        hold = list(plan[key]["preliminary_hold"])
        payload = widths = None
        fit = "not_measured_held"
        if key in diag:
            payload = injector["encode_text"](codec, injector["translation_for_injection"](diag[key]),
                                               plain_script=sel["category"] == "plain_scripts")
            source_bytes = rom[sel["rom_offset"]:sel["rom_offset"] + sel["source_encoded_size"]]
            if control_sequence(source_bytes) != control_sequence(payload):
                hold.append("source_control_sequence_changed")
            widths = line_widths(payload)
            if max(widths) >= 240:
                hold.append("screen_width_overflow")
                fit = "WIDTH_OVERFLOW"
            elif sel["category"] == "battle_messages" and max(widths) >= 222:
                hold.append("battle_window_width_overflow")
                fit = "WIDTH_OVERFLOW"
            elif len(payload) > sel["slot_size"]:
                fit = "relocation_required"
                if sel["fixed"] or sel["no_relocation"] or not sel["relocation_possible"]:
                    hold.append("fixed_or_unrelocatable_slot_overflow")
                if owners[key]["missing"] or owners[key]["stale"]:
                    hold.append("relocation_pointer_owner_incomplete")
            else:
                fit = "in_place"
        if not hold:
            safe.append(diag[key])
        for item in names[key]:
            item["apply impact"] = ("applied" if not hold else "entry_held")
        rows.append({"id": key, "category": row["category"], "original": row["original"],
                     "original_review_status": row["status"], "review_source": row["review_source"],
                     "official_name_result": [{"English term": n["English term"],
                                               "result": n["PokeAPI result"]["status"]} for n in names[key]],
                     "buffer_result": "unproved_hold" if src.get("buffers") else "none",
                     "width_result": {"renderer_confidence": src.get("renderer_confidence"),
                                      "profile": src.get("renderer_profile_id"), "line_pixels": widths,
                                      "limit_pixels": 222 if sel["category"] == "battle_messages" else 240,
                                      "runtime_unverified": row["width_runtime_unverified"]},
                     "fit_result": fit, "technical_class": technical_class(row),
                     "slot_size": sel["slot_size"], "encoded_bytes": len(payload) if payload else None,
                     "pointer_ownership": "complete" if not owners[key]["missing"] and not owners[key]["stale"] else "incomplete",
                     "final_japanese": diag[key]["translated"] if not hold else None,
                     "final_apply": not hold, "hold_reason": list(dict.fromkeys(hold))})
    if len(rows) != 408:
        raise ValueError("Reviewed output incomplete")
    categories = Counter("Battle" if r["category"] == "battle_messages" else "Menu/UI" for r in rows)
    if categories != {"Battle": 189, "Menu/UI": 219}:
        raise ValueError("Category accounting differs")
    technical = Counter(r["technical_class"] for r in rows if r["technical_class"])
    if sum(technical.values()) != 19 or technical["TRANSLATION_INCOMPLETE"] != 6:
        raise ValueError("Technical-fit accounting differs")
    controlled_safe = baseline + safe
    raw_prepared = {x["id"]: x for x in read(ROOT / "out/ja-phase5e-prepared.json")["entries"]}
    reviewed_by_id = {x["id"]: x for x in review}
    safe_raw = []
    for fixed_row in safe:
        raw_row = dict(raw_prepared[fixed_row["id"]])
        raw_row["translated"] = reviewed_by_id[fixed_row["id"]]["reviewed_japanese"]
        safe_raw.append(raw_row)
    write(OUT / "ja_phase6_batch05_reviewed.json", {"metadata": {
        "reviewed": 408, "safe_application_count": len(safe), "hold_count": 408-len(safe),
        "status_counts": dict(Counter(r["status"] for r in review)), "category_counts": dict(categories),
        "technical_fit_classes": dict(technical),
        "hold_reason_counts": dict(Counter(h for r in rows for h in r["hold_reason"]))}, "entries": rows})
    official_audit["metadata"]["apply_impact_counts"] = dict(Counter(
        row["apply impact"] for row in official_audit["entries"]))
    write(OUT / "ja_phase6_batch05_official_name_audit.json", official_audit)
    write(OUT / "ja_phase6_batch05_safe_controlfix.json", {"entries": safe})
    write(OUT / "ja_phase6_batch05_safe_input.json", {"entries": baseline + safe_raw})
    write(OUT / "ja_phase6_batch05_combined_controlfix.json", {"entries": controlled_safe})
    write(OUT / "ja_phase6_batch05_glossary_audit.json", {"entries": glossary_proposals(
        read(FIX / "ja_phase6_batch05_glossary_candidates.json")),
        "existing_glossary": [r for r in rows if r["original_review_status"] == "existing_glossary"]})
    write(OUT / "ja_phase6_batch05_fa_audit.json", {"metadata": {
        "entries": 4, "controls": 4, "segments": 12, "applied": 0}, "entries": [
        {"id": r["id"], "source_segments": by_source[r["id"]]["control_segments"],
         "source_boundary_sequence": by_source[r["id"]]["source_boundary_sequence"],
         "reviewed_segments": r["segments"], "status": r["status"], "apply": False}
        for r in review if r.get("fa_segmented")]})
    print({"safe": len(safe), "hold": 408-len(safe), "technical": dict(technical),
           "categories_safe": dict(Counter(r["category"] for r in rows if r["final_apply"]))})


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in {"prepare", "finalize"}:
        raise SystemExit("Usage: python scripts/build_ja_phase6_batch05.py prepare|finalize")
    stage_prepare() if sys.argv[1] == "prepare" else stage_finalize()


if __name__ == "__main__":
    main()
