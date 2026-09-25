#!/usr/bin/env python3
"""Promote Phase 5D approved terms without losing contextual scope."""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib.pcs_text import Charmap
from lib.translation_glossary import load_glossary


ROOT = Path(__file__).resolve().parents[1]
KANJI = re.compile(r"[\u3400-\u9fff\uf900-\ufaff]")
STALE_WARNING_ID = "tbl_menu_game_settings_00000_1F4E274"
COMPLETE_WARNING_ID = "tbl_menu_game_settings_00000_1F4E26F"

SCOPE_CATEGORIES = {
    "trainer_class": ["trainer_classes"],
    "organization_and_trainer_class": ["trainer_classes"],
    "organization_and_mission_title": ["mission_names"],
    "options_setting_label": ["setting_names"],
    "route_number_template": ["map_names"],
    "start_menu_label": ["start_menu_labels"],
    "ui_choice_label": ["menu_game_settings"],
}
EXACT_ENTRY_IDS = {
    "Difficult": ["scr_1F10621"],
    "Vanilla": ["scr_1F10630"],
    "Expert": ["scr_1F1063D"],
    "Insane": ["scr_1F10644"],
    "Easy": ["scr_1F1062B"],
    "Challenging": ["scr_1F1064B"],
    "Nerd": ["scr_1FACB9D"],
    "Black [player]": ["scr_1F9FBCD", "scr_1F9EAF1", "scr_1F9F08F"],
    "New Game \\+": ["scr_1F103AA"],
}
SETTINGS_CATEGORIES = ["menu_pause", "menu_options", "menu_game_settings",
                       "setting_names", "start_menu_labels"]


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def validate_review(review, patch, extracted):
    approved = {row["source"]: row for row in review if row["status"] == "project_standard"}
    unresolved = {row["source"] for row in review if row["status"] == "unresolved"}
    patch_terms = patch["terms"]
    sources = [row["source"] for row in patch_terms]
    if (len(review), len(approved), len(unresolved), len(patch_terms)) != (122, 114, 8, 114):
        raise ValueError("Phase 5D review counts changed")
    if len(sources) != len(set(sources)) or set(sources) != set(approved):
        raise ValueError("Patch source coverage differs from approved review")
    if set(sources) & unresolved:
        raise ValueError("Unresolved term in approved patch")
    by_id = {row["id"]: row for row in extracted["entries"]}
    if len(by_id) != len(extracted["entries"]):
        raise ValueError("Duplicate extraction ID")
    codec = Charmap("ja")
    migrations = []
    for row in patch_terms:
        source = row["source"]
        reviewed = approved[source]
        if (row["status"] != "project_standard" or row["target"] != reviewed["japanese"]
                or row["context_scope"] != reviewed["context_scope"]):
            raise ValueError(f"Patch/review conflict: {source}")
        if KANJI.search(row["target"]):
            raise ValueError(f"Kanji in glossary target: {source}")
        sample = row["target"].replace("[N]", "7")
        codec.encode("[japanese]" + sample + "[latin]")
        for entry_id in reviewed.get("affected_entry_ids", []):
            actual = COMPLETE_WARNING_ID if entry_id == STALE_WARNING_ID else entry_id
            if actual != entry_id:
                migrations.append({"from": entry_id, "to": actual, "term": source})
            if actual not in by_id:
                raise ValueError(f"Affected ID missing: {source} {entry_id}")
    if len(migrations) != 1:
        raise ValueError("Expected exactly one known clipped-warning ID migration")
    return approved, unresolved, migrations


def merge_glossary(existing, patch):
    terms = [dict(row) for row in existing["terms"]]
    sources = {row["source"] for row in terms}
    for row in terms:
        if row["source"] in {"Option", "Options"}:
            row["context_scope"] = "settings_ui"
            row["global_replace"] = False
            row["categories"] = SETTINGS_CATEGORIES
    for proposed in patch["terms"]:
        source = proposed["source"]
        if source in sources:
            raise ValueError(f"Approved source already exists: {source}")
        row = dict(proposed)
        scope = row["context_scope"]
        if row["kind"] == "mission_title":
            row["categories"] = ["mission_names"]
        elif scope in SCOPE_CATEGORIES:
            row["categories"] = SCOPE_CATEGORIES[scope]
        if source == "Oddish Leaves":
            # This term is an item name. The two approved Phase 5C prose
            # sentences intentionally keep word spacing unchanged.
            row["categories"] = ["item_names"]
        if source in EXACT_ENTRY_IDS:
            row["entry_ids"] = EXACT_ENTRY_IDS[source]
        if scope.endswith("_template"):
            row["template"] = True
        terms.append(row)
        sources.add(source)
    output = dict(existing)
    output["status"] = "phase5e-reviewed-terms"
    output["note"] = "Kana-only approved Phase 5D terms; scoped terms require their category or exact entry IDs."
    output["terms"] = terms
    if len(terms) != 139:
        raise ValueError("Expected 25 old + 114 approved terms")
    return output


def main():
    review = read(ROOT / "tests/fixtures/ja_phase5d_glossary_review.json")
    patch = read(ROOT / "tests/fixtures/ja_phase5d_glossary_patch.json")
    extracted = read(ROOT / "out/ja-phase5c-extracted.json")
    _approved, unresolved, migrations = validate_review(review, patch, extracted)
    path = ROOT / "glossaries/ja.json"
    existing = read(path)
    if existing.get("status") == "phase5e-reviewed-terms":
        # Regeneration must start from a 25-term predecessor, not append twice.
        existing = dict(existing)
        existing["terms"] = existing["terms"][:25]
    if len(existing["terms"]) != 25:
        raise ValueError("Unexpected predecessor glossary size")
    output = merge_glossary(existing, patch)
    path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    loaded = load_glossary(path, expected_language="ja")
    if len(loaded.terms) != 139:
        raise ValueError("Merged glossary failed to load")
    audit = {
        "reviewed": len(review), "approved": len(patch["terms"]),
        "unresolved": sorted(unresolved),
        "context_sensitive_reviewed": sum(row["context_scope"] != "global" for row in review),
        "context_sensitive_adopted": sum(not row["global_replace"] for row in patch["terms"]),
        "affected_id_migrations": migrations,
        "terms": [{
            "source": row["source"], "japanese": row["target"],
            "status": row["status"], "scope": row["context_scope"],
            "affected_ids": next((reviewed.get("affected_entry_ids", []) for reviewed in review
                                  if reviewed["source"] == row["source"]), []),
            "actually_applied_ids": [],
            "global_replace": row["global_replace"],
            "template": row.get("template", False), "conflict": None,
        } for row in output["terms"][25:]],
    }
    audit_path = ROOT / "out/ja-phase5e-glossary-audit.json"
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Glossary: {len(loaded.terms)} terms (114 promoted; {len(unresolved)} held)")


if __name__ == "__main__":
    main()
