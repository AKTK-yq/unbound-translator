#!/usr/bin/env python3
"""Verify Batch 04's provisional franchise names against exact-English PokeAPI ja-hrkt."""

from __future__ import annotations

from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.pokeapi_localizer import PokeAPILocalizer
from lib.translation_tokens import strip_hma_quotes
from scripts.audit_ja_phase6_batch02_names import SUPPORTED, lookup

TERMS = ROOT / "tests/fixtures/ja_phase6_batch04_official_name_review.json"
REVIEW = ROOT / "tests/fixtures/ja_phase6_batch04_claude_review.json"
OUTPUT = ROOT / "out/phase6/ja_phase6_batch04_official_name_audit.json"
EXPECTED_OCCURRENCES = 112
EXPECTED_TERMS = 54
EXPECTED_ENTRIES = 81


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def draft_text(review_row):
    if review_row.get("segments"):
        return "".join(piece["reviewed_japanese"] or "" for piece in review_row["segments"])
    return review_row.get("reviewed_japanese") or review_row.get("candidate_japanese") or ""


def verify(localizer, source, kind):
    if kind not in SUPPORTED:
        return {"result": "not_applicable", "entity": None, "pokeapi_english": None,
                "pokeapi_japanese": None,
                "notes": "Not a PokeAPI entity type; memory-only franchise wording is not treated as official"}
    return lookup(localizer, source, kind)


def build(terms, review, localizer):
    unique = {row["english_term"] for row in terms}
    entries = {row["entry_id"] for row in terms}
    if (len(terms), len(unique), len(entries)) != (EXPECTED_OCCURRENCES, EXPECTED_TERMS, EXPECTED_ENTRIES):
        raise ValueError(f"Unexpected term accounting: {len(terms)}/{len(unique)}/{len(entries)}")
    by_id = {row["id"]: row for row in review}
    if len(by_id) != 408:
        raise ValueError("Expected 408 reviewed Batch 04 entries")
    keys = list(dict.fromkeys((row["english_term"], row["type"]) for row in terms))
    with ThreadPoolExecutor(max_workers=8) as executor:
        evidence = dict(zip(keys, executor.map(lambda pair: verify(localizer, *pair), keys)))
    rows = []
    for term in terms:
        entry_id = term["entry_id"]
        if entry_id not in by_id:
            raise ValueError(f"Unknown entry: {entry_id}")
        source, kind, proposal = term["english_term"], term["type"], term["japanese_candidate"]
        result = evidence[(source, kind)]
        status, note = result["result"], result["notes"]
        exact_in_source = source in strip_hma_quotes(by_id[entry_id]["original"])
        if status == "verified_exact" and not exact_in_source:
            status, note = "ambiguous", "Full English term does not occur contiguously in the source entry"
        if status == "verified_exact" and proposal.replace(" ", "") != result["pokeapi_japanese"].replace(" ", ""):
            status, note = "verified_difference", "Provisional kana differs; exact PokeAPI ja-hrkt is authoritative"
        verified = status in {"verified_exact", "verified_difference"}
        rows.append({
            "entry_id": entry_id, "English term": source, "term_type": kind,
            "provisional_japanese": proposal, "proposed_japanese": proposal,
            "pokeapi_japanese": result.get("pokeapi_japanese"),
            "pokeapi_english": result.get("pokeapi_english"), "pokeapi_entity": result.get("entity"),
            "claude_marked_pokeapi_target": term["needs_pokeapi_verification"],
            "verification_result": status,
            "final_value": result.get("pokeapi_japanese") if verified else None,
            "changed": status == "verified_difference",
            "source_occurs_exactly": exact_in_source,
            "proposed_in_reviewed_draft": proposal.replace(" ", "") in draft_text(by_id[entry_id]).replace(" ", ""),
            "apply_impact": ("name_applied" if verified else
                             "entry_held_unverified_name"),
            "notes": note})
    per_term = {}
    for row in rows:
        per_term.setdefault(row["English term"], row["verification_result"])
    return {"metadata": {
        "phase": "6B-4", "occurrence_count": len(rows), "unique_term_count": len(unique),
        "entry_count": len(entries),
        "claude_pokeapi_target_occurrences": sum(term["needs_pokeapi_verification"] for term in terms),
        "pokeapi_type_occurrences": sum(row["term_type"] in SUPPORTED for row in rows),
        "result_counts": dict(Counter(row["verification_result"] for row in rows)),
        "unique_term_result_counts": dict(Counter(per_term.values())),
        "rule": "Only exact English entity identity and PCS-safe ja-hrkt count as verified; "
                "not_applicable, ambiguous, not_found and unsupported terms hold their entry."},
        "entries": rows}


def main():
    localizer = PokeAPILocalizer("ja", ROOT / ".cache/pokeapi", timeout=12)
    result = build(read(TERMS), read(REVIEW), localizer)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(result["metadata"])


if __name__ == "__main__":
    main()
