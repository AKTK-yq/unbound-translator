#!/usr/bin/env python3
"""Create human QA candidates and Batch 02 style guidance, without translating it."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out/phase6"
QA = ROOT / "tests/fixtures/ja_phase6_batch01_runtime_qa.json"


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def make_qa(selection, reviewed, fit, names, candidates, size=26):
    by_id = {row["id"]: row for row in selection["entries"]}
    review = {row["id"]: row for row in reviewed["entries"]}
    fit_by_id = {row["id"]: row for row in fit["entries"]}
    safe = [row for row in reviewed["entries"] if row["technical_status"] == "validated_for_controlfix"]
    chosen = []
    used = set()

    def add(rows, count):
        for row in rows:
            if count <= 0 or len(chosen) >= size:
                return
            if row["id"] not in used:
                chosen.append(row["id"])
                used.add(row["id"])
                count -= 1

    add((r for r in safe if fit_by_id[r["id"]]["width_status"] == "positional_sign_unverified"), 4)
    add((r for r in safe if "Choose from Party" in r["original"] or "All in Party" in r["original"]), 2)
    add((r for r in safe if fit_by_id[r["id"]]["placement"] == "relocation"), 5)
    add((r for r in safe if by_id[r["id"]]["buffers"]), 5)
    add((r for r in safe if by_id[r["id"]]["controls"].get("FB", 0) >= 2), 4)
    verified_ids = {row["id"] for row in names["entries"] if row["all_verified"]}
    add((r for r in safe if r["id"] in verified_ids), 3)
    candidate_ids = {entry_id for row in candidates["entries"] for entry_id in row["affected_entry_ids"]}
    add((r for r in safe if r["id"] in candidate_ids), 3)
    add((r for r in safe if by_id[r["id"]]["slot_size"] >= 300), size - len(chosen))
    add(safe, size - len(chosen))
    result = []
    for index, entry_id in enumerate(chosen, 1):
        row = by_id[entry_id]
        original = row["original"]
        route = ("標識を探す。該当地図・座標は未確認" if fit_by_id[entry_id]["width_status"] == "positional_sign_unverified"
                 else "選択肢を開く。会話NPCと地図は未確認" if "Choose from Party" in original or "All in Party" in original
                 else "Marlon/Jaxのストーリーイベント。正確なsceneは未確認" if "Marlon" in original or "Jax" in original
                 else "Mission HQ関連NPCを探す。座標未確認" if "Mission HQ" in original
                 else "NPC/eventを進行済みsaveで探す。場所・branchは未確認")
        result.append({"priority": index, "id": entry_id, "category": row["category"],
                       "rom_offset": f"0x{row['rom_offset']:08X}",
                       "pointer_owners": row["pointer_owners"],
                       "original": original, "expected_japanese": review[entry_id]["translated"],
                       "route": route, "route_confidence": "unverified",
                       "placement": fit_by_id[entry_id]["placement"],
                       "width_status": fit_by_id[entry_id]["width_status"],
                       "controls": row["controls"], "buffers": row["buffers"],
                       "has_glossary_candidate": entry_id in candidate_ids,
                       "has_pokeapi_verified_name": entry_id in verified_ids})
    return {"metadata": {"phase": "6B-1", "entry_count": len(result),
                         "note": "Human QA candidates only. No per-entry runtime reachability has been proved."},
            "entries": result}


def make_style(candidates):
    return {
        "phase": "6B-1-to-6B-2", "status": "guidance_only_no_batch02_translation",
        "approved_style_notes": [
            "Kana-only; prose retains current wakachigaki and P7 pacing baseline.",
            "Use neutral voice when speaker unknown; no invented first-person or gendered endings.",
            "ナゾノクサのはっぱ and わざマシン / わざマシンケース are wording candidates, not global glossary additions.",
            "レポートを かく for Save where meaning and UI context match.",
            "Keep $ in money amounts.",
            "Count Pokémon as ひき, items as こ, repetitions as かい, options as とおり when semantically correct.",
            "Sign arrows retain exact protected tokens; verify glyph width and position in runtime.",
            "Mission-like NPC prose is still scripts; preserve event context and token counts.",
        ],
        "rejected_or_risky_notes": [
            "Never infer speaker, scene, or chronology solely from nearby ROM addresses or pointer operands.",
            "Never use Pokémon, Move, Item, or Ability names from memory as official. Missing official_terms requires PokeAPI exact-English ja-hrkt verification or needs_context/provisional.",
            "Plural English phrases are not exact PokeAPI entity names; do not auto-verify singular lookups as exact.",
            "Do not approve 24 glossary proposals or globally replace context-sensitive terms.",
            "Do not translate FD 07/08/0C by guessing English suffix/evolution grammar.",
            "Choice and sign widths remain unproven even when PCS slot fit passes.",
        ],
        "glossary_candidates": [{"source": row["source"],
                                 "proposed_japanese": row["proposed_japanese"],
                                 "status": "proposal_only"} for row in candidates["entries"]],
        "pokeapi_naming_rule": "English source entity must exactly match PokeAPI English name; use kana-encodable ja-hrkt only. If not found/ambiguous/unsupported, mark provisional or needs_context.",
        "speaker_rule": "speaker unknown unless event/script evidence proves identity",
        "counters": {"pokemon": "ひき", "items": "こ", "times": "かい", "options": "とおり"},
        "sign_formatting": "Preserve \\al/\\ar/\\au/\\ad and original destination order; pixel/position QA required",
        "item_spacing": "Keep established item names whole; do not insert spaces inside a verified official name",
        "mission_formatting": "Do not apply mission title glossary to ordinary NPC prose; keep protected colors/buffers",
        "known_bad_patterns": ["Ace matched inside Aerial Ace", "memory-only official name",
                               "ASCII parentheses inside Japanese PCS page",
                               "relocation with incomplete pointer owners"],
    }


def main():
    selection = read(ROOT / "tests/fixtures/ja_phase6_selection.json")
    reviewed = read(OUT / "ja_phase6_batch01_reviewed.json")
    fit = read(OUT / "ja_phase6_batch01_fit.json")
    names = read(OUT / "ja_phase6_batch01_unverified_names.json")
    candidates = read(OUT / "ja_phase6_batch01_glossary_candidates_audit.json")
    qa = make_qa(selection, reviewed, fit, names, candidates)
    write(QA, qa)
    write(OUT / "ja_phase6_batch02_style_handoff.json", make_style(candidates))
    print({"qa_candidates": len(qa["entries"]),
           "batch02_style": "guidance_only"})


if __name__ == "__main__":
    main()
