#!/usr/bin/env python3
"""Fail-closed exact-English PokeAPI audit for Batch 05 review flags."""

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


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def audit(flags, review, localizer):
    if len(flags) != 67 or len({x["entry_id"] for x in flags}) != 67:
        raise ValueError("Expected 67 distinct official-name review entries")
    by_id = {x["id"]: x for x in review}
    terms = list(dict.fromkeys((t["english_term"], t["kind"])
                               for row in flags for t in row["english_terms"]))
    with ThreadPoolExecutor(max_workers=8) as pool:
        evidence = dict(zip(terms, pool.map(
            lambda pair: lookup(localizer, *pair) if pair[1] in SUPPORTED else
            {"result": "not_applicable", "entity": None, "pokeapi_english": None,
             "pokeapi_japanese": None, "notes": "Not a supported PokeAPI entity"}, terms)))
    rows = []
    for flag in flags:
        entry_id = flag["entry_id"]
        if entry_id not in by_id or flag["original"] != by_id[entry_id]["original"]:
            raise ValueError(f"Official-name source mismatch: {entry_id}")
        draft = by_id[entry_id].get("reviewed_japanese") or by_id[entry_id].get("candidate_japanese") or ""
        observations = []
        for term in flag["english_terms"]:
            english, kind = term["english_term"], term["kind"]
            proof = evidence[(english, kind)]
            status, note = proof["result"], proof["notes"]
            if status == "verified_exact" and english not in strip_hma_quotes(flag["original"]):
                status, note = "ambiguous", "English name does not occur contiguously in source"
            japanese = proof.get("pokeapi_japanese")
            if status == "verified_exact" and japanese.replace(" ", "") not in draft.replace(" ", ""):
                status, note = "ambiguous", (
                    "Official name is absent from draft; inflected/common-noun use or the exact "
                    "Japanese term span cannot be proved, so automatic replacement is unsafe")
            observations.append({
                "entry_id": entry_id, "English term": english, "type": kind,
                "provisional Japanese": flag["japanese_candidate"],
                "PokeAPI result": {"entity": proof.get("entity"), "english": proof.get("pokeapi_english"),
                                    "ja-hrkt": japanese, "status": status},
                "final Japanese": japanese if status in {"verified_exact", "verified_difference"} else None,
                "changed": status == "verified_difference", "apply impact": "pending_entry_fit",
                "notes": note,
            })
        if not observations:
            observations.append({
                "entry_id": entry_id, "English term": None, "type": None,
                "provisional Japanese": flag["japanese_candidate"],
                "PokeAPI result": {"entity": None, "english": None, "ja-hrkt": None,
                                    "status": "ambiguous"},
                "final Japanese": None, "changed": False, "apply impact": "held_no_exact_entity",
                "notes": "Review flagged an official-looking term, but no exact ROM English entity was identified",
            })
        rows.extend(observations)
    return {"metadata": {"entry_count": 67, "observation_count": len(rows),
                          "result_counts": dict(Counter(x["PokeAPI result"]["status"] for x in rows)),
                          "rule": "Exact English identity plus PCS-safe ja-hrkt; no inferred singular/plural or memory-only names"},
            "entries": rows}


def main():
    flags = read(ROOT / "tests/fixtures/ja_phase6_batch05_official_name_review.json")
    review = read(ROOT / "tests/fixtures/ja_phase6_batch05_claude_review.json")
    output = audit(flags, review, PokeAPILocalizer("ja", ROOT / ".cache/pokeapi", timeout=12))
    path = ROOT / "out/phase6/ja_phase6_batch05_official_name_audit.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(output["metadata"])


if __name__ == "__main__":
    main()
