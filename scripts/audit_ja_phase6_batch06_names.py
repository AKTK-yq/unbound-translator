#!/usr/bin/env python3
"""Exact-entity PokeAPI ja-hrkt audit for Phase 6 Batch 06."""

from __future__ import annotations

from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.pcs_text import Charmap
from lib.pokeapi_localizer import (PokeAPILocalizer, language_value,
                                   same_genus, same_name, source_slug)

FIX = ROOT / "tests/fixtures"
OUT = ROOT / "out/phase6"
SUPPORTED = {"item", "species_classification"}


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def lookup(localizer: PokeAPILocalizer, flag: dict, source: dict) -> dict:
    """Only a fully matched English item or indexed species genus is verified."""
    kind = flag["type"]
    english = flag["English term"]
    if kind not in SUPPORTED:
        return {"class": "not_applicable", "entity": None, "english": None,
                "japanese": None, "notes": "No exact PokeAPI field for this source type"}
    if kind == "item":
        endpoint, identifier = "item", source_slug(english, "item_names")
        field = "names"
    else:
        endpoint, identifier = "pokemon-species", int(source["table_index"]) + 1
        field = "genera"
    payload = localizer._get(endpoint, identifier)
    entity = f"{endpoint}/{identifier}"
    if not payload:
        return {"class": "not_found", "entity": entity, "english": None,
                "japanese": None, "notes": "Exact entity not returned; no name inferred"}
    source_english = language_value(payload.get(field), "en", "name" if kind == "item" else "genus")
    source_japanese = language_value(payload.get(field), "ja", "name" if kind == "item" else "genus")
    exact_english = (same_name(english, source_english, "item_names") if kind == "item"
                     else same_genus(english, source_english))
    if not source_english or not exact_english:
        return {"class": "ambiguous", "entity": entity, "english": source_english,
                "japanese": source_japanese, "notes": "Indexed/slug entity English does not match exact ROM term"}
    if not source_japanese:
        return {"class": "unsupported", "entity": entity, "english": source_english,
                "japanese": None, "notes": "ja-hrkt value absent"}
    japanese = source_japanese
    if kind == "species_classification":
        # The ROM genus field omits its separately rendered 'Pokémon' suffix.
        # Require the paired PokeAPI genera to prove both suffixes first.
        if not source_english.casefold().endswith(" pokémon") or not japanese.endswith("ポケモン"):
            return {"class": "ambiguous", "entity": entity, "english": source_english,
                    "japanese": japanese, "notes": "Genus suffix relationship unproved"}
        japanese = japanese[:-4]
    try:
        Charmap("ja").encode(f"[japanese]{japanese}[latin]")
    except (UnicodeEncodeError, ValueError):
        return {"class": "unsupported", "entity": entity, "english": source_english,
                "japanese": japanese, "notes": "Official Japanese cannot be encoded in current PCS"}
    return {"class": "verified", "entity": entity, "english": source_english,
            "japanese": japanese, "notes": "Exact English identity, ja-hrkt and PCS encoding verified"}


def audit(flags: list[dict], review: list[dict], selection: list[dict],
          localizer: PokeAPILocalizer) -> dict:
    if len(flags) != 39 or len({x["entry_id"] for x in flags}) != 39:
        raise ValueError("Expected 39 unique pending-name entries")
    by_review = {x["id"]: x for x in review}
    by_source = {x["id"]: x for x in selection}
    if len(by_review) != 461 or len(by_source) != 461:
        raise ValueError("Batch 06 source/review incomplete")
    for flag in flags:
        key = flag["entry_id"]
        if key not in by_review or key not in by_source:
            raise ValueError(f"Unknown pending name {key}")
        source_term = flag["English term"]
        if source_term not in by_review[key]["original"] and not (
                flag["type"] == "pokemon" and source_term.split("[", 1)[0]
                in by_review[key]["original"]):
            raise ValueError(f"English term absent from source {key}")
    with ThreadPoolExecutor(max_workers=8) as pool:
        evidence = list(pool.map(
            lambda x: lookup(localizer, x, by_source[x["entry_id"]]), flags))
    rows = []
    for flag, proof in zip(flags, evidence):
        key = flag["entry_id"]
        draft = by_review[key]["reviewed_japanese"] or by_review[key].get("candidate_japanese") or ""
        official = proof["japanese"]
        result = proof["class"]
        final = None
        changed = False
        notes = proof["notes"]
        if result == "verified":
            proposed = flag["provisional Japanese"]
            if proposed not in draft and by_review[key]["reviewed_japanese"]:
                result = "ambiguous"
                notes = "Provisional term span absent from reviewed Japanese; replacement unsafe"
            else:
                result = "verified_exact" if proposed == official else "verified_difference"
                final = official
                changed = proposed != official
        rows.append({
            "entry_id": key, "English term": flag["English term"], "type": flag["type"],
            "proposed Japanese": flag["provisional Japanese"],
            "official source/result": {"entity": proof["entity"], "english": proof["english"],
                                       "ja-hrkt": proof["japanese"]},
            "final Japanese": final, "verification class": result, "changed": changed,
            "apply impact": "pending_fit" if result.startswith("verified_") else "hold_pending_context_or_approval",
            "notes": notes,
        })
    return {"metadata": {"entry_count": len(rows),
                         "result_counts": dict(Counter(x["verification class"] for x in rows)),
                         "policy": "Exact English entity plus PCS-safe ja-hrkt only; unsupported types never become official"},
            "entries": rows}


def main():
    flags = read(FIX / "ja_phase6_batch06_official_name_review.json")
    review = read(FIX / "ja_phase6_batch06_claude_review.json")
    selected = [x for x in read(FIX / "ja_phase6_selection.json")["entries"]
                if x["batch_number"] == 6]
    result = audit(flags, review, selected,
                   PokeAPILocalizer("ja", ROOT / ".cache/pokeapi", timeout=12))
    write(OUT / "ja_phase6_batch06_official_name_audit.json", result)
    print(result["metadata"])


if __name__ == "__main__":
    main()
