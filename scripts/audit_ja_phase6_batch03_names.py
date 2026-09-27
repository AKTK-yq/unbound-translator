#!/usr/bin/env python3
"""Verify Batch 03's exact English franchise terms against PokeAPI ja-hrkt."""

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
from scripts.audit_ja_phase6_batch02_names import lookup

TERMS = ROOT / "tests/fixtures/ja_phase6_batch03_official_name_review.json"
REVIEW = ROOT / "tests/fixtures/ja_phase6_batch03_claude_review.json"
OUTPUT = ROOT / "out/phase6/ja_phase6_batch03_official_name_audit.json"


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def verify(localizer, source, kind):
    if kind != "move_or_type":
        return lookup(localizer, source, kind)
    move = lookup(localizer, source, "move")
    type_ = lookup(localizer, source, "type")
    if move["result"] == "verified_exact" and type_["result"] == "verified_exact":
        return {"result": "ambiguous", "entity": None, "pokeapi_english": source,
                "pokeapi_japanese": None,
                "notes": "Exact move and type entities both exist; source context must choose one",
                "alternatives": {"move": move, "type": type_}}
    matches = [row for row in (move, type_) if row["result"] == "verified_exact"]
    if len(matches) == 1:
        return matches[0]
    return {"result": "ambiguous", "entity": None, "pokeapi_english": None,
            "pokeapi_japanese": None,
            "notes": "Move/type identity unresolved by exact matching",
            "alternatives": {"move": move, "type": type_}}


def build(terms, review, localizer):
    if len(terms) != 108 or len({row["entry_id"] for row in terms}) != 84:
        raise ValueError("Expected 108 term observations across 84 Batch 03 entries")
    by_id = {row["id"]: row for row in review}
    if len(by_id) != 408:
        raise ValueError("Expected 408 reviewed Batch 03 entries")
    keys = list(dict.fromkeys((row["English term"], row["term_type"]) for row in terms))
    with ThreadPoolExecutor(max_workers=8) as executor:
        evidence = dict(zip(keys, executor.map(lambda pair: verify(localizer, *pair), keys)))
    rows = []
    for term in terms:
        entry_id = term["entry_id"]
        if entry_id not in by_id:
            raise ValueError(f"Unknown entry: {entry_id}")
        source, kind = term["English term"], term["term_type"]
        proposal = term["Japanese candidate if used"]
        result = evidence[(source, kind)]
        status, note = result["result"], result["notes"]
        exact_in_source = source in strip_hma_quotes(by_id[entry_id]["original"])
        if not exact_in_source and status == "verified_exact":
            status = "ambiguous"
            note = "Full English term does not occur contiguously in source entry"
        if status == "verified_exact" and proposal and proposal.replace(" ", "") != result["pokeapi_japanese"].replace(" ", ""):
            status = "verified_difference"
            note = "Proposed kana differs; exact PokeAPI ja-hrkt is authoritative"
        draft = by_id[entry_id]["reviewed_japanese"] or "".join(
            segment["reviewed_japanese"] for segment in by_id[entry_id].get("segments", []))
        proposal_in_draft = bool(proposal and proposal.replace(" ", "") in draft.replace(" ", ""))
        verified = status in {"verified_exact", "verified_difference"}
        rows.append({"entry_id": entry_id, "English term": source, "type": kind,
                     "proposed_japanese": proposal,
                     "pokeapi_japanese": result.get("pokeapi_japanese"),
                     "pokeapi_english": result.get("pokeapi_english"),
                     "pokeapi_entity": result.get("entity"),
                     "verification_result": status,
                     "final_value": result.get("pokeapi_japanese") if verified else None,
                     "changed": status == "verified_difference",
                     "source_occurs_exactly": exact_in_source,
                     "proposed_in_reviewed_draft": proposal_in_draft,
                     "alternatives": result.get("alternatives"), "notes": note})
    counts = Counter(row["verification_result"] for row in rows)
    return {"metadata": {"phase": "6B-3", "term_count": len(rows),
                         "entry_count": len({row["entry_id"] for row in rows}),
                         "result_counts": dict(counts),
                         "rule": "Only full English entity identity and PCS-safe ja-hrkt count as verified."},
            "entries": rows}


def main():
    localizer = PokeAPILocalizer("ja", ROOT / ".cache/pokeapi", timeout=12)
    result = build(read(TERMS), read(REVIEW), localizer)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(result["metadata"])


if __name__ == "__main__":
    main()
