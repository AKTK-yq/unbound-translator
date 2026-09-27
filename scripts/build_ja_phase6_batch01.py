#!/usr/bin/env python3
"""Validate Claude Batch 01 and construct a conservative reviewed input."""

from __future__ import annotations

from collections import Counter
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.pcs_text import Charmap
from lib.translation_glossary import TranslationGlossary, load_glossary
from lib.translation_tokens import semantic_tokens, strip_hma_quotes
from scripts.audit_ja_phase6_batch01_names import build as audit_names, lookup, PokeAPILocalizer

PHASE6 = ROOT / "out/phase6"
REVIEW = ROOT / "tests/fixtures/ja_phase6_batch01_claude_review.json"
BATCH = PHASE6 / "ja_phase6_batch01_for_claude.json"
SELECTION = ROOT / "tests/fixtures/ja_phase6_selection.json"
PREPARED = ROOT / "out/ja-phase5e-prepared.json"
PHASE5 = ROOT / "out/ja-phase5f-final-reviewed-input.json"
ROM = ROOT / "rom/unbound.gba"
CANDIDATES = ROOT / "tests/fixtures/ja_phase6_batch01_glossary_candidates.json"
VALID_STATUSES = {"confirmed", "existing_official", "existing_glossary", "needs_context", "needs_technical_fit"}
HAN = re.compile(r"[\u3400-\u9fff]")


def technical_target(row):
    """Replace one unencodable ASCII punctuation pair, not prose wording."""
    text = row.get("reviewed_japanese") or ""
    if row["id"] == "scr_1F010E6":
        plain = "(オープニングと おなじ ないようです)"
        if text.count(plain) != 1:
            raise ValueError("Expected one ASCII parenthetical in scr_1F010E6")
        text = text.replace(plain, "オープニングと おなじ ないようです。")
    return text


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def validate_review(review, batch, selection):
    by_id = {row["id"]: row for row in batch["entries"]}
    selected = {row["id"]: row for row in selection["entries"]}
    ids = [row["id"] for row in review]
    if len(ids) != len(set(ids)) or set(ids) != set(by_id) or len(ids) != 407:
        raise ValueError("Claude review must contain each Batch 01 ID exactly once")
    codec = Charmap(target_lang="ja")
    results = []
    for row in review:
        entry_id = row["id"]
        source = by_id[entry_id]
        expected = selected[entry_id]
        issues = []
        if row["category"] != source["category"] or row["original"] != source["original"]:
            issues.append("source_identity")
        if row["status"] not in VALID_STATUSES:
            issues.append("invalid_status")
        if row.get("conversation_id") != source.get("conversation_id"):
            issues.append("conversation_id")
        target = row.get("reviewed_japanese") or ""
        if HAN.search(target):
            issues.append("kanji")
        source_tokens = Counter(semantic_tokens(strip_hma_quotes(row["original"])))
        target_tokens = Counter(semantic_tokens(target))
        protected = Counter(source["protected_tokens"])
        if source_tokens != protected or (target and target_tokens != protected):
            issues.append("protected_control_token_mismatch")
        try:
            encoded_size = len(codec.encode(f"[japanese]{technical_target(row)}[latin]")) if target else None
        except (UnicodeEncodeError, ValueError) as error:
            encoded_size = None
            issues.append(f"pcs_encode:{error}")
        results.append({"id": entry_id, "status": row["status"], "issues": issues,
                        "source_bytes": expected["source_encoded_size"],
                        "slot_size": expected["slot_size"],
                        "raw_japanese_bytes": encoded_size,
                        "fixed": expected["fixed"],
                        "relocation_possible": expected["relocation_possible"],
                        "controls": expected["controls"], "buffers": expected["buffers"],
                        "technical_risk": expected["technical_risk"]})
    return results


def glossary_audit(selection, glossary):
    old_terms = [replace(term, global_replace=True, context_scope="global", entry_ids=())
                 if term.source == "Ace" else term for term in glossary.terms]
    old_glossary = TranslationGlossary("ja", old_terms)
    changes = []
    composite = []
    for row in selection["entries"]:
        source = row.get("translation_source") or strip_hma_quotes(row["original"])
        old = [(start, end, term.source) for start, end, term in
               old_glossary.matches(source, row["category"], entry_id=row["id"])]
        new = [(start, end, term.source) for start, end, term in
               glossary.matches(source, row["category"], entry_id=row["id"])]
        if old != new:
            changes.append({"id": row["id"], "category": row["category"],
                            "source": source, "before": old, "after": new})
        for start, end, term in new:
            prefix = source[:start]
            suffix = source[end:]
            if (re.search(r"[A-Z][a-z]+\s+$", prefix) or re.match(r"^\s+[A-Z][a-z]+", suffix)):
                composite.append({"id": row["id"], "term": term,
                                  "matched": source[start:end], "context": source[max(0, start-24):end+24],
                                  "note": "Capitalized compound proximity; manual review, not asserted false positive"})
    return {"metadata": {"selection_count": len(selection["entries"]),
                         "changed_entry_count": len(changes),
                         "potential_compound_match_count": len(composite)},
            "changed_matches": changes, "potential_compound_matches": composite}


def candidate_audit(candidates, glossary, selection, localizer):
    by_id = {row["id"]: row for row in selection["entries"]}
    if len(candidates) != 24:
        raise ValueError("Expected 24 Claude glossary proposals")
    rows = []
    for candidate in candidates:
        source = candidate["source"]
        affected = candidate["affected_entry_ids"]
        if not affected or any(entry_id not in by_id for entry_id in affected):
            raise ValueError(f"Candidate has unknown entry: {source}")
        conflicts = [{"source": term.source, "target": term.target,
                      "kind": term.kind} for term in glossary.terms
                     if term.source.casefold() == source.casefold()]
        kind = candidate.get("type", "")
        official = lookup(localizer, source, "item") if kind == "item" else None
        rows.append({"source": source, "proposed_japanese": candidate["proposed_japanese"],
                     "affected_entry_ids": affected, "kind": kind,
                     "existing_glossary_conflict": conflicts,
                     "pokeapi_applicability": (official["status"] if official else "not_franchise_entity"),
                     "pokeapi_english": official["english_pokeapi"] if official else None,
                     "pokeapi_ja_hrkt": official["japanese_pokeapi"] if official else None,
                     "project_standard_candidate": kind in {"location", "feature", "person"},
                     "context_sensitive": kind not in {"location"},
                     "status": "proposal_only"})
    return {"metadata": {"count": len(rows), "rule": "No candidate auto-added to glossaries/ja.json"}, "entries": rows}


def pointer_owner_audit(batch, selection, rom):
    if hashlib.md5(rom).hexdigest() != "9cad8e771940e7f7094d13911552cef0":
        raise ValueError("Source ROM MD5 mismatch")
    by_id = {row["id"]: row for row in selection["entries"]}
    rows = []
    for row in batch["entries"]:
        address = int(row["id"].split("_")[-1], 16)
        needle = (0x08000000 + address).to_bytes(4, "little")
        found = []
        cursor = 0
        while (cursor := rom.find(needle, cursor)) >= 0:
            found.append(f"0x{cursor:X}")
            cursor += 1
        selected = {int(value, 16) for value in by_id[row["id"]].get("pointer_owners", [])}
        actual = {int(value, 16) for value in found}
        if actual != selected:
            rows.append({"id": row["id"], "rom_offset": f"0x{address:X}",
                         "metadata_owners": sorted(f"0x{x:X}" for x in selected),
                         "whole_rom_exact_pointer_hits": found,
                         "missing_owners": sorted(f"0x{x:X}" for x in actual - selected),
                         "stale_owners": sorted(f"0x{x:X}" for x in selected - actual)})
    return {"metadata": {"audited": len(batch["entries"]), "mismatch_count": len(rows)},
            "entries": rows}


def build_inputs(review, validation, name_audit, prepared, phase5, owner_audit):
    by_id = {row["id"]: row for row in prepared["entries"]}
    validation_by_id = {row["id"]: row for row in validation}
    name_by_id = {row["id"]: row for row in name_audit["entries"]}
    owner_incomplete = {row["id"] for row in owner_audit["entries"]}
    all_reviewed = []
    safe = []
    for row in review:
        entry_id = row["id"]
        validation_row = validation_by_id[entry_id]
        name_row = name_by_id.get(entry_id)
        name_status = ([term["verification_status"] for term in name_row["terms"]]
                       if name_row else [])
        if row["status"] != "confirmed":
            technical_status = row["status"]
        elif validation_row["issues"]:
            technical_status = "held_validation"
        elif entry_id in owner_incomplete:
            technical_status = "owner_incomplete"
        elif any(status not in {"verified_exact", "verified_but_difference"}
                 for status in name_status):
            technical_status = "provisional_official_name"
        else:
            technical_status = "validated_for_controlfix"
        annotated = {**row, "technical_status": technical_status,
                     "validation_issues": validation_row["issues"],
                     "official_name_statuses": name_status,
                     "translated": technical_target(row) if technical_status == "validated_for_controlfix" else None}
        all_reviewed.append(annotated)
        if technical_status == "validated_for_controlfix":
            source = dict(by_id[entry_id])
            source["translated"] = technical_target(row)
            safe.append(source)
    combined = list(phase5["entries"]) + safe
    if len({row["id"] for row in combined}) != len(combined):
        raise ValueError("Phase 5 / Batch 01 duplicate ID")
    return ({"metadata": {"phase": "6B-1", "entry_count": len(all_reviewed),
                          "technical_status_counts": dict(Counter(row["technical_status"] for row in all_reviewed))},
             "entries": all_reviewed},
            {"entries": safe}, {"entries": combined})


def main():
    review = read(REVIEW)
    batch = read(BATCH)
    selection = read(SELECTION)
    prepared = read(PREPARED)
    phase5 = read(PHASE5)
    validation = validate_review(review, batch, selection)
    write(PHASE6 / "ja_phase6_batch01_review_validation.json",
          {"metadata": {"entry_count": len(validation),
                        "issue_count": sum(bool(row["issues"]) for row in validation)},
           "entries": validation})
    localizer = PokeAPILocalizer("ja", ROOT / ".cache/pokeapi", timeout=8)
    names = audit_names(review, localizer)
    write(PHASE6 / "ja_phase6_batch01_unverified_names.json", names)
    owners = pointer_owner_audit(batch, selection, ROM.read_bytes())
    write(PHASE6 / "ja_phase6_batch01_owner_audit.json", owners)
    glossary = load_glossary(ROOT / "glossaries/ja.json", expected_language="ja")
    write(PHASE6 / "ja_phase6_glossary_match_audit.json", glossary_audit(selection, glossary))
    write(PHASE6 / "ja_phase6_batch01_glossary_candidates_audit.json",
          candidate_audit(read(CANDIDATES), glossary, selection, localizer))
    reviewed, safe, combined = build_inputs(review, validation, names, prepared, phase5, owners)
    write(PHASE6 / "ja_phase6_batch01_reviewed.json", reviewed)
    write(PHASE6 / "ja_phase6_batch01_safe_input.json", safe)
    write(PHASE6 / "ja_phase6_batch01_combined_input.json", combined)
    print({"reviewed": len(review), "validation_issues": sum(bool(row["issues"]) for row in validation),
           "name_statuses": names["metadata"]["status_counts"],
           "owner_mismatches": owners["metadata"]["mismatch_count"],
           "technical_statuses": reviewed["metadata"]["technical_status_counts"],
           "combined": len(combined["entries"])})


if __name__ == "__main__":
    main()
