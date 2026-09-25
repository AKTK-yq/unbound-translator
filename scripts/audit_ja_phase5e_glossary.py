#!/usr/bin/env python3
"""Fill the Phase 5E approved-term audit from final controlfixed entries."""

from __future__ import annotations

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.translation_glossary import _target_for_match, load_glossary


ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def main():
    audit_path = ROOT / "out/ja-phase5e-glossary-audit.json"
    audit = read("out/ja-phase5e-glossary-audit.json")
    glossary = load_glossary(ROOT / "glossaries/ja.json", expected_language="ja")
    approved = {term.source for term in glossary.terms[25:]}
    rows = {row["source"]: row for row in audit["terms"]}
    if set(rows) != approved or len(rows) != 114:
        raise ValueError("Approved audit/glossary mismatch")
    translations = read("out/ja-phase5e-controlfix.json")["entries"]
    applied = {source: set() for source in approved}
    conflicts = {source: [] for source in approved}
    for entry in translations:
        neutral = entry["translated"].replace("[japanese]", "").replace("[latin]", "")
        for start, end, term in glossary.matches(
            entry["original"], entry["category"], entry_id=entry["id"]
        ):
            if term.source not in approved:
                continue
            target = _target_for_match(term, entry["original"][start:end], entry["category"])
            if target in neutral:
                applied[term.source].add(entry["id"])
            else:
                conflicts[term.source].append({"id": entry["id"], "expected": target})
    for source, row in rows.items():
        row["actually_applied_ids"] = sorted(applied[source])
        row["conflict"] = conflicts[source] or None
    audit["actually_applied_term_count"] = sum(bool(ids) for ids in applied.values())
    audit["actually_applied_entry_count"] = len(set.union(*applied.values()))
    audit["conflict_count"] = sum(map(len, conflicts.values()))
    if audit["conflict_count"]:
        raise ValueError(f"Approved glossary conflicts: {audit['conflict_count']}")
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Glossary: {audit['actually_applied_term_count']} approved terms in "
          f"{audit['actually_applied_entry_count']} entries, no conflicts")


if __name__ == "__main__":
    main()
