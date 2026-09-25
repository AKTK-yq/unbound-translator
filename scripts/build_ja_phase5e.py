#!/usr/bin/env python3
"""Rebuild Phase 5C plus 52 glossary-approved labels and one item name."""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib.gen3_font import text_pixel_width
from lib.pcs_text import Charmap
from lib.translation_glossary import load_glossary
from lib.translation_tokens import semantic_token_counts, strip_hma_quotes
from scripts.build_ja_phase5c import merge as merge_phase5c


ROOT = Path(__file__).resolve().parents[1]
KANJI = re.compile(r"[\u3400-\u9fff\uf900-\ufaff]")
ITEM_ID = "tbl_item_names_00363_EB92C0"
ITEM_TARGET = "ナゾノクサのはっぱ"


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write(path, data):
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build(prepared, baseline, handoff, context_review, difficulty_review,
          recheck, glossary):
    phase5c, phase5c_audit = merge_phase5c(
        prepared, baseline, handoff, context_review, difficulty_review)
    prepared_by_id = {row["id"]: row for row in prepared["entries"]}
    if len(prepared_by_id) != len(prepared["entries"]):
        raise ValueError("Duplicate fresh extraction ID")
    held = {row["id"] for row in context_review if row["status"] == "needs_context"}
    recheck_by_id = {row["id"]: row for row in recheck["entries"]}
    if len(recheck_by_id) != 96 or set(recheck_by_id) != held:
        raise ValueError("Phase 5D recheck does not match Phase 5C held 96")
    ready = [row for row in recheck["entries"] if row["ready_for_retranslation"]]
    if len(ready) != 52 or Counter(row["category"] for row in ready) != {
        "scripts": 25, "map_names": 9, "mission_names": 14, "trainer_classes": 4
    }:
        raise ValueError("Phase 5D ready-52 coverage changed")
    if sum(row["codex_technical_investigation"] for row in recheck["entries"] if not row["ready_for_retranslation"]) != 36:
        raise ValueError("Phase 5D technical-36 coverage changed")
    terms = {term.source: term for term in glossary.terms}
    applied = list(phase5c["entries"])
    applied_ids = {row["id"] for row in applied}
    codec = Charmap("ja")
    fit_rows = []
    for row in ready:
        entry_id = row["id"]
        if entry_id in applied_ids:
            raise ValueError(f"Ready row already applied: {entry_id}")
        source = prepared_by_id.get(entry_id)
        if source is None or source["category"] != row["category"]:
            raise ValueError(f"Ready row missing/category changed: {entry_id}")
        if len(row["resolved_terms"]) != 1 or row["unresolved_terms"]:
            raise ValueError(f"Ready row has ambiguous terms: {entry_id}")
        term_source, approved_target = row["resolved_terms"][0].split("=", 1)
        term = terms.get(term_source)
        japanese = row["proposed_japanese"]
        if term is None or approved_target != term.target or japanese != term.target:
            raise ValueError(f"Ready row is not approved glossary wording: {entry_id}")
        if KANJI.search(japanese) or semantic_token_counts(japanese) != semantic_token_counts(
                strip_hma_quotes(source["original"])):
            raise ValueError(f"Unsafe kana or control tokens: {entry_id}")
        payload = codec.encode("[japanese]" + japanese + "[latin]")
        slot = int(source["byte_length"])
        owners = source.get("pointer_sources", [])
        if not owners or (source.get("no_relocation") and len(payload) > slot):
            raise ValueError(f"Unsafe pointer/fixed fit: {entry_id}")
        entry = dict(source)
        entry["translated"] = japanese
        applied.append(entry)
        applied_ids.add(entry_id)
        fit_rows.append({
            "id": entry_id, "category": source["category"],
            "source": strip_hma_quotes(source["original"]),
            "glossary_term": term_source, "japanese": japanese,
            "scope": term.context_scope, "rom_offset": source["address"],
            "encoded_bytes": len(payload), "slot_size": slot,
            "pixel_width": text_pixel_width("[japanese]" + japanese + "[latin]", codec),
            "expected_placement": "in-place" if len(payload) <= slot else "relocation",
            "pointer_owners": owners,
        })
    item = prepared_by_id[ITEM_ID]
    if (item["category"] != "item_names" or strip_hma_quotes(item["original"]) != "Oddish Leaves"
            or ITEM_ID in applied_ids or terms["Oddish Leaves"].target != ITEM_TARGET):
        raise ValueError("Oddish Leaves item-name source or glossary changed")
    payload = codec.encode("[japanese]" + ITEM_TARGET + "[latin]")
    if len(payload) != int(item["byte_length"]) or not item.get("pointer_sources"):
        raise ValueError("Oddish Leaves item name does not fit its own slot")
    item_entry = dict(item)
    item_entry["translated"] = ITEM_TARGET
    applied.append(item_entry)
    applied_ids.add(ITEM_ID)
    if len(applied) != 674 or any(row["id"] in applied_ids for row in recheck["entries"]
                                  if not row["ready_for_retranslation"]):
        raise ValueError("Phase 5E applied/held count changed")
    audit = {
        "phase": "5E", "phase5c_applied": phase5c_audit["total_input"],
        "glossary_resolved_applied": len(ready), "item_name_added": 1,
        "japanese_applied": len(applied),
        "english_untouched": len(prepared["entries"]) - len(applied),
        "remaining_context": 44, "ready_by_category": dict(Counter(row["category"] for row in ready)),
        "ready_fit": fit_rows,
        "item_name": {"id": ITEM_ID, "source": "Oddish Leaves", "japanese": ITEM_TARGET,
                      "rom_offset": item["address"], "encoded_bytes": len(payload),
                      "slot_size": item["byte_length"], "expected_placement": "in-place"},
        "prose_spacing_preserved_ids": ["scr_746471", "scr_75318A"],
    }
    return {"entries": applied}, audit


def main():
    prepared = read(ROOT / "out/ja-phase5e-prepared.json")
    glossary = load_glossary(ROOT / "glossaries/ja.json", expected_language="ja")
    output, audit = build(
        prepared,
        read(ROOT / "out/ja-phase5b-resolved.json"),
        read(ROOT / "out/ja-phase5c-needs-context-for-claude.json"),
        read(ROOT / "tests/fixtures/ja_phase5c_claude_review.json"),
        read(ROOT / "tests/fixtures/ja_phase5c_difficulty_review.json"),
        read(ROOT / "out/ja-phase5d-needs-context-recheck.json"),
        glossary,
    )
    write(ROOT / "out/ja-phase5e-reviewed-input.json", output)
    write(ROOT / "out/ja-phase5e-merge-audit.json", audit)
    print(f"Phase 5E input: {audit['japanese_applied']} = "
          f"{audit['phase5c_applied']} + {audit['glossary_resolved_applied']} + 1 item")


if __name__ == "__main__":
    main()
