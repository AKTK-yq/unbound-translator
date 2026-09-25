#!/usr/bin/env python3
"""Regenerate Phase 5C input from Phase 5B plus strictly reviewed kana.

This is a data merge, not a translator. Only 20 newly confirmed context rows
and focused confirmed difficulty rows are added. Existing Phase 5B files stay
untouched; unresolved candidates remain absent from injection input.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib.pcs_text import Charmap
from lib.translation_tokens import remove_layout_tokens, semantic_token_counts, strip_hma_quotes


KANJI = re.compile(r"[\u3400-\u9fff\uf900-\ufaff]")
CLIPPED_WARNING = "tbl_menu_game_settings_00000_1F4E274"
COMPLETE_WARNING = "tbl_menu_game_settings_00000_1F4E26F"
EXISTING_WARNING = "tbl_menu_game_settings_00001_1F4E328"
BASELINE_COUNT = 596
EXPECTED_CONTEXT = {"confirmed": 20, "needs_context": 96}


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, data):
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def unique_index(rows, label):
    ids = [row["id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError(f"Duplicate {label} ID")
    return {row["id"]: row for row in rows}


def validate_reviewed_text(entry_id, original, text, codec):
    if not isinstance(text, str) or not text:
        raise ValueError(f"Empty reviewed Japanese: {entry_id}")
    if KANJI.search(text):
        raise ValueError(f"Kanji in reviewed Japanese: {entry_id}")
    if semantic_token_counts(text) != semantic_token_counts(strip_hma_quotes(original)):
        raise ValueError(f"Protected/control token mismatch: {entry_id}")
    codec.encode(f"[japanese]{text}[latin]")


def validate_context_review(handoff, review, prepared):
    handoff_by_id = unique_index(handoff["entries"], "handoff")
    review_by_id = unique_index(review, "Phase 5C context review")
    prepared_by_id = unique_index(prepared["entries"], "prepared")
    if len(handoff_by_id) != 116 or set(handoff_by_id) != set(review_by_id):
        raise ValueError("Phase 5C review ID coverage differs from 116-row handoff")
    statuses = Counter(row["status"] for row in review)
    if dict(statuses) != EXPECTED_CONTEXT:
        raise ValueError(f"Phase 5C status counts changed: {dict(statuses)}")
    codec = Charmap("ja")
    for row in review:
        entry_id = row["id"]
        source = handoff_by_id[entry_id]
        if row["original"] != source["original"] or row["category"] != source["category"]:
            raise ValueError(f"Phase 5C original/category mismatch: {entry_id}")
        for field in ("reviewed_japanese", "candidate_japanese"):
            value = row.get(field)
            if value is not None:
                if KANJI.search(value) or semantic_token_counts(value) != semantic_token_counts(
                        strip_hma_quotes(row["original"])):
                    raise ValueError(f"Unsafe {field}: {entry_id}")
        if row["status"] == "confirmed":
            current = prepared_by_id.get(entry_id)
            if current is None or current["original"] != row["original"]:
                raise ValueError(f"Confirmed source not in fresh extraction: {entry_id}")
            validate_reviewed_text(entry_id, row["original"], row.get("reviewed_japanese"), codec)
        elif row.get("reviewed_japanese") is not None:
            raise ValueError(f"Unresolved row contains applied wording: {entry_id}")
    if review_by_id["scr_74AE91"]["status"] != "needs_context":
        raise ValueError("Zeph buffer remains unknown")
    if review_by_id[CLIPPED_WARNING]["status"] != "needs_context":
        raise ValueError("Clipped warning must remain held")
    return review_by_id, prepared_by_id


def validate_difficulty_review(rows, context_by_id, prepared_by_id, baseline_by_id):
    confirmed = {}
    reflow_existing = {}
    for row in rows:
        status = row["status"]
        entry_id = row.get("id")
        if status == "confirmed":
            if not entry_id or entry_id in confirmed:
                raise ValueError("Duplicate/missing confirmed difficulty ID")
            source = prepared_by_id.get(entry_id)
            if source is None:
                raise ValueError(f"Difficulty ID absent from fresh extraction: {entry_id}")
            if row["source"] not in (strip_hma_quotes(source["original"]), source["original"]):
                # Some review rows use a descriptive 'source' label. Those
                # overlap the 116-row review, whose original is authoritative.
                if entry_id not in context_by_id:
                    raise ValueError(f"Difficulty source mismatch: {entry_id}")
            validate_reviewed_text(entry_id, source["original"], row.get("reviewed_japanese"), Charmap("ja"))
            if entry_id in context_by_id:
                other = context_by_id[entry_id]
                if other["status"] != "confirmed" or other["reviewed_japanese"] != row["reviewed_japanese"]:
                    raise ValueError(f"Difficulty/context review conflict: {entry_id}")
            confirmed[entry_id] = row
        elif status == "confirmed_phase5b":
            if entry_id not in baseline_by_id:
                raise ValueError(f"Claimed Phase 5B row absent: {entry_id}")
            if entry_id == EXISTING_WARNING:
                source = prepared_by_id[entry_id]
                reviewed = row["reviewed_japanese"]
                validate_reviewed_text(entry_id, source["original"], reviewed, Charmap("ja"))
                prior = baseline_by_id[entry_id]["translated"].replace("[japanese]", "").replace("[latin]", "")
                prior = remove_layout_tokens(prior)[0]
                if re.sub(r"\s+", "", prior) != re.sub(r"\s+", "", reviewed):
                    raise ValueError("Existing Options warning wording changed during layout reflow")
                reflow_existing[entry_id] = reviewed
        elif status in {"not_in_scope", "not_found", "do_not_translate"}:
            if entry_id == COMPLETE_WARNING:
                raise ValueError("Complete warning cannot be held by clipped-row status")
        else:
            raise ValueError(f"Unknown difficulty review status: {status}")
    if len(confirmed) != 19 or CLIPPED_WARNING in confirmed or COMPLETE_WARNING not in confirmed:
        raise ValueError("Focused difficulty review coverage changed")
    return confirmed, reflow_existing


def merge(prepared, baseline, handoff, context_review, difficulty_review):
    context_by_id, prepared_by_id = validate_context_review(handoff, context_review, prepared)
    baseline_by_id = unique_index(baseline["entries"], "Phase 5B baseline")
    if len(baseline_by_id) != BASELINE_COUNT or CLIPPED_WARNING in baseline_by_id:
        raise ValueError("Phase 5B baseline count/clipped warning changed")
    if CLIPPED_WARNING in prepared_by_id or COMPLETE_WARNING not in prepared_by_id:
        raise ValueError("Fresh extractor did not remove clipped warning")
    for entry_id, old in baseline_by_id.items():
        current = prepared_by_id.get(entry_id)
        if current is None or (current["original"], current["category"]) != (
                old["original"], old["category"]):
            raise ValueError(f"Phase 5B source changed: {entry_id}")
    difficulty_by_id, reflow_existing = validate_difficulty_review(
        difficulty_review, context_by_id, prepared_by_id, baseline_by_id)
    context_confirmed = {entry_id: row for entry_id, row in context_by_id.items()
                         if row["status"] == "confirmed"}
    if set(context_confirmed) & set(baseline_by_id):
        raise ValueError("Newly confirmed context overlaps Phase 5B baseline")
    if set(difficulty_by_id) & set(baseline_by_id):
        raise ValueError("Focused difficulty translation would overwrite Phase 5B")
    added = {entry_id: row["reviewed_japanese"] for entry_id, row in context_confirmed.items()}
    for entry_id, row in difficulty_by_id.items():
        if entry_id in added and added[entry_id] != row["reviewed_japanese"]:
            raise ValueError(f"Difficulty wording conflict: {entry_id}")
        added[entry_id] = row["reviewed_japanese"]
    if len(added) != 25 or len(set(difficulty_by_id) - set(context_confirmed)) != 5:
        raise ValueError("Phase 5C focused addition count changed")
    output_entries = []
    for entry_id, row in baseline_by_id.items():
        current = dict(prepared_by_id[entry_id])
        current["translated"] = reflow_existing.get(entry_id, row["translated"])
        output_entries.append(current)
    for entry_id, value in added.items():
        current = dict(prepared_by_id[entry_id])
        current["translated"] = value
        output_entries.append(current)
    output = {"entries": output_entries}
    if len(output_entries) != 621 or any(row["id"] == CLIPPED_WARNING for row in output_entries):
        raise ValueError("Phase 5C output count/clipped exclusion failed")
    audit = {"phase": "5C", "baseline_applied": len(baseline_by_id),
             "context_reviewed": len(context_review), "context_confirmed": len(context_confirmed),
             "context_held": len(context_review) - len(context_confirmed),
             "difficulty_confirmed": len(difficulty_by_id),
             "difficulty_overlap_with_context": len(set(difficulty_by_id) & set(context_confirmed)),
             "difficulty_focused_additions": len(set(difficulty_by_id) - set(context_confirmed)),
             "total_input": len(output_entries),
             "context_confirmed_ids": sorted(context_confirmed),
             "focused_addition_ids": sorted(set(difficulty_by_id) - set(context_confirmed)),
             "clipped_warning_excluded": True, "complete_warning_included": COMPLETE_WARNING in added,
             "existing_warning_reflowed": list(reflow_existing),
             "glossary_mutated": False}
    return output, audit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared", default="out/ja-phase5c-prepared.json")
    parser.add_argument("--baseline", default="out/ja-phase5b-resolved.json")
    parser.add_argument("--handoff", default="out/ja-phase5c-needs-context-for-claude.json")
    parser.add_argument("--context-review", default="tests/fixtures/ja_phase5c_claude_review.json")
    parser.add_argument("--difficulty-review", default="tests/fixtures/ja_phase5c_difficulty_review.json")
    parser.add_argument("--output", default="out/ja-phase5c-reviewed-input.json")
    parser.add_argument("--audit", default="out/ja-phase5c-merge-audit.json")
    args = parser.parse_args()
    output, audit = merge(read_json(args.prepared), read_json(args.baseline), read_json(args.handoff),
                          read_json(args.context_review), read_json(args.difficulty_review))
    write_json(args.output, output)
    write_json(args.audit, audit)
    print(f"Phase 5C input: {audit['total_input']} = {audit['baseline_applied']} + "
          f"{audit['context_confirmed']} + {audit['difficulty_focused_additions']}")


if __name__ == "__main__":
    main()
