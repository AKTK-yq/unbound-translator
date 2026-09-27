#!/usr/bin/env python3
"""Audit every Batch 02 name proposal against exact-English PokeAPI ja-hrkt."""

from __future__ import annotations

from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.pcs_text import Charmap
from lib.pokeapi_localizer import PokeAPILocalizer, language_value, same_name, source_slug
from lib.translation_tokens import strip_hma_quotes

REVIEW_PATH = ROOT / "tests/fixtures/ja_phase6_batch02_claude_review.json"
TERMS_PATH = ROOT / "tests/fixtures/ja_phase6_batch02_official_name_review.json"
OUTPUT_PATH = ROOT / "out/phase6/ja_phase6_batch02_official_name_audit.json"

SUPPORTED = {
    "pokemon": ("pokemon-species", "pokemon_names"),
    "move": ("move", "move_names"),
    "item": ("item", "item_names"),
    "ability": ("ability", "ability_names"),
    "type": ("type", "type_names"),
}


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def lookup(localizer, source, kind):
    """Verify full source term, never a singularized/plural-stripped approximation."""
    if kind not in SUPPORTED or source.startswith("["):
        return {"result": "unsupported", "entity": None, "pokeapi_english": None,
                "pokeapi_japanese": None, "notes": "No exact entity endpoint for this term type"}
    endpoint, category = SUPPORTED[kind]
    slug = source_slug(source, category)
    payload = localizer._get(endpoint, slug)
    if not payload:
        return {"result": "not_found", "entity": f"{endpoint}/{slug}",
                "pokeapi_english": None, "pokeapi_japanese": None,
                "notes": "Entity slug not found; no name inferred"}
    english = language_value(payload.get("names"), "en", "name")
    japanese = language_value(payload.get("names"), "ja", "name")
    evidence = {"entity": f"{endpoint}/{slug}", "pokeapi_english": english,
                "pokeapi_japanese": japanese}
    if not english or not same_name(source, english, category):
        return {**evidence, "result": "ambiguous",
                "notes": "PokeAPI English name differs from full source term"}
    if not japanese:
        return {**evidence, "result": "unsupported", "notes": "ja-hrkt name unavailable"}
    try:
        Charmap("ja").encode(f"[japanese]{japanese}[latin]")
    except (UnicodeEncodeError, ValueError):
        return {**evidence, "result": "unsupported",
                "notes": "ja-hrkt cannot be encoded by Japanese PCS"}
    return {**evidence, "result": "verified_exact", "notes": "Exact English entity and PCS-safe ja-hrkt"}


def build(terms, review, localizer):
    if len(terms) != 153 or len({term["entry_id"] for term in terms}) != 120:
        raise ValueError("Expected 153 term observations across 120 Batch 02 entries")
    by_id = {row["id"]: row for row in review}
    keys = list(dict.fromkeys((row["English term"], row["term_type"]) for row in terms))
    with ThreadPoolExecutor(max_workers=8) as executor:
        evidence = dict(zip(keys, executor.map(lambda pair: lookup(localizer, *pair), keys)))
    rows = []
    for term in terms:
        entry_id, source, kind = term["entry_id"], term["English term"], term["term_type"]
        if entry_id not in by_id:
            raise ValueError(f"Unknown entry: {entry_id}")
        original = strip_hma_quotes(by_id[entry_id]["original"])
        proposed = term["Japanese candidate if used"]
        found_in_source = source in original
        result = evidence[(source, kind)]
        status = result["result"]
        note = result["notes"]
        if not found_in_source and status == "verified_exact":
            status = "ambiguous"
            note = "Term is not an exact substring of entry original; entity identity unproved"
        elif status == "verified_exact" and proposed and proposed.replace(" ", "") != result["pokeapi_japanese"].replace(" ", ""):
            status = "verified_difference"
            note = "Existing draft term differs; PokeAPI value is authoritative"
        if proposed and proposed.replace(" ", "") not in by_id[entry_id]["reviewed_japanese"].replace(" ", ""):
            status = "ambiguous"
            note = "Proposed Japanese term absent from reviewed draft"
        verified = status in {"verified_exact", "verified_difference"}
        rows.append({"entry_id": entry_id, "source_term": source, "term_type": kind,
                     "proposed_japanese": proposed, "pokeapi_japanese": result["pokeapi_japanese"],
                     "pokeapi_english": result["pokeapi_english"], "pokeapi_entity": result["entity"],
                     "verification_result": status, "final_value": result["pokeapi_japanese"] if verified else None,
                     "changed": status == "verified_difference", "source_occurs_exactly": found_in_source,
                     "notes": note})
    counts = Counter(row["verification_result"] for row in rows)
    return {"metadata": {"phase": "6B-2", "term_count": len(rows),
                         "entry_count": len({row["entry_id"] for row in rows}),
                         "result_counts": dict(counts),
                         "rule": "Only full English-source identity plus PCS-safe PokeAPI ja-hrkt is official."},
            "entries": rows}


def main():
    localizer = PokeAPILocalizer("ja", ROOT / ".cache/pokeapi", timeout=8)
    result = build(read(TERMS_PATH), read(REVIEW_PATH), localizer)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(result["metadata"])


if __name__ == "__main__":
    main()
