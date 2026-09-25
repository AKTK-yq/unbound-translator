"""Phase 5B reviewed-data and ROM-audit safety regression tests."""

from collections import Counter
import copy
import json
from pathlib import Path

import pytest

from lib.pcs_text import Charmap
from scripts.audit_ja_phase5b import classify_changed_bytes
from scripts.build_ja_phase5_reviewed import (
    LATIN_UNCHANGED_ID, classify_fits, merge, runtime_subset, validate_review,
)


ROOT = Path(__file__).resolve().parents[1]


def load(relative):
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


SELECTION = load("tests/fixtures/ja_phase5_selection.json")
REVIEW = load("tests/fixtures/ja_phase5_claude_review.json")
GLOSSARY_REVIEW = load("tests/fixtures/ja_phase5_glossary_review.json")
RUNTIME_SOURCE = load("tests/fixtures/ja_phase5_runtime_subset.json")
RUNTIME_5B = load("tests/fixtures/ja_phase5b_runtime_subset.json")
FIT_REVIEW = load("tests/fixtures/ja_phase5_fit_review.json")


def prepared_stub():
    return {"entries": [{"id": row["id"], "category": row["category"],
                         "original": row["original"], "address": f"0x{row['rom_offset']:X}",
                         "byte_length": row["slot_size"], "pointer_sources": row["pointer_owners"],
                         "is_pointer_based": bool(row["pointer_owners"]),
                         "no_relocation": row["no_relocation"]}
                        for row in SELECTION["entries"]]}


def test_review_validation_and_status_counts():
    result = validate_review(SELECTION, REVIEW, GLOSSARY_REVIEW)
    assert result["total"] == 750
    assert result["statuses"] == {"confirmed": 512, "existing_official": 106,
                                  "needs_context": 116, "needs_technical_fit": 16}
    assert result["warnings"] == 15
    assert result["provisional_glossary_candidates"] == 78


def test_merge_status_rules_preserve_review_fields_and_official_wording():
    output, audit = merge(prepared_stub(), SELECTION, REVIEW, GLOSSARY_REVIEW)
    applied = {row["id"]: row for row in output["entries"]}
    selection = {row["id"]: row for row in SELECTION["entries"]}
    review = {row["id"]: row for row in REVIEW}
    assert len(applied) == 633  # 634 eligible, one unchanged-Latin expression
    assert LATIN_UNCHANGED_ID not in applied
    assert len(audit["rows"]) == 750
    for entry_id, row in review.items():
        if row["status"] == "needs_context":
            assert entry_id not in applied
        elif row["status"] == "existing_official":
            assert applied[entry_id]["translated"] == selection[entry_id]["official_translation"]
        elif entry_id != LATIN_UNCHANGED_ID:
            assert applied[entry_id]["translated"] == row["reviewed_japanese"]
    assert Counter(item["review"]["status"] for item in audit["rows"])["needs_context"] == 116
    assert next(item for item in audit["rows"] if item["id"] == "scr_1F0F842")["review"].get("review_warning")
    assert all(not item["official_confirmed"] for item in GLOSSARY_REVIEW)
    assert "glossary" not in output
    assert Charmap("ja").encode("[japanese]こんにちは[latin]")


@pytest.mark.parametrize("mutation,match", [
    ("duplicate", "Duplicate"),
    ("original", "Original/category"),
    ("official", "official translation"),
    ("kanji", "Kanji"),
    ("token", "Protected/control token"),
    ("status", "Invalid status"),
])
def test_review_validation_rejects_corruption(mutation, match):
    rows = copy.deepcopy(REVIEW)
    if mutation == "duplicate":
        rows[1]["id"] = rows[0]["id"]
    elif mutation == "original":
        rows[0]["original"] += "X"
    elif mutation == "official":
        next(row for row in rows if row["status"] == "existing_official")["reviewed_japanese"] = "あ"
    elif mutation == "kanji":
        next(row for row in rows if row["status"] == "confirmed")["reviewed_japanese"] = "漢"
    elif mutation == "token":
        next(row for row in rows if row["id"] == "scr_1F0F89C")["reviewed_japanese"] = "なまえ"
    else:
        rows[0]["status"] = "approved"
    with pytest.raises(ValueError, match=match):
        validate_review(SELECTION, rows, GLOSSARY_REVIEW)


def test_technical_fit_fixture_and_fixed_slot_overflow():
    rows = FIT_REVIEW["entries"]
    assert len(rows) == 16
    assert Counter(row["classification"] for row in rows) == {"C": 11, "B": 2, "A": 3}
    assert all(row["proposed_shorter_japanese"] is None for row in rows)
    assert all(row["encoded_size"] > row["slot_size"] for row in rows if row["classification"] in {"B", "C"})
    assert all(row["relocatable"] for row in rows if row["classification"] == "B")
    assert all(not row["relocatable"] for row in rows if row["classification"] == "C")


def test_fit_classifier_never_forces_fixed_overflow_or_pokedex_suffix():
    source = copy.deepcopy(next(row for row in SELECTION["entries"]
                                if row["id"] == "tbl_menu_cube_00000_4162CD"))
    candidate = {"id": source["id"], "category": source["category"],
                 "translated": "[japanese]どうぐ[latin]"}
    audit = {"rows": [{"id": source["id"], "selection": source,
                       "review": {"status": "needs_technical_fit", "reviewed_japanese": "どうぐ"},
                       "applied_candidate": True}]}
    resolved, fit, fixed, unresolved = classify_fits({"entries": [candidate]}, audit, strict_counts=False)
    assert fit[0]["classification"] == "C"
    assert fixed[0]["fit"] is False
    assert not resolved["entries"]
    assert unresolved[0]["reason"] == "fixed/no-relocation slot overflow"

    source["category"] = "pokedex_species"
    source["slot_size"] = 32
    source["fixed_slot"] = True
    audit["rows"][0]["selection"] = source
    candidate["category"] = "pokedex_species"
    resolved, _, _, unresolved = classify_fits({"entries": [candidate]}, audit, strict_counts=False)
    assert not resolved["entries"]
    assert unresolved[0]["reason"] == "Pokédex category suffix behavior unverified"


def test_runtime_subset_is_applied_selection_subset_with_qa_fields():
    source_ids = {row["id"] for row in RUNTIME_SOURCE["entries"]}
    selected_ids = {row["id"] for row in SELECTION["entries"]}
    rows = RUNTIME_5B["entries"]
    assert len(rows) == 72
    assert RUNTIME_5B["metadata"]["source_80_applied"] == 69
    assert RUNTIME_5B["metadata"]["supplemental_applied"] == 3
    assert {row["id"] for row in rows} <= selected_ids
    assert {row["id"] for row in rows if not row.get("supplemental")} <= source_ids
    assert {row["id"] for row in rows if row.get("supplemental")} == {
        "scr_1A56A7", "tbl_menu_item_storage_00005_4177C5",
        "tbl_move_learning_00002_416DF7",
    }
    assert all(row["reach_steps"] and row["check"] and row["renderer"] for row in rows)
    assert any(row["relocation"] for row in rows)
    assert any(row["controls"].get("FA") for row in rows)
    assert any(row["controls"].get("FB") for row in rows)
    assert any(row["controls"].get("FD") for row in rows)
    assert any(row["category"] == "battle_messages" for row in rows)


def test_runtime_subset_builder_filters_unapplied_ids():
    source = {"entries": [{"id": "a", "qa_route": "NEW GAME", "category": "scripts",
                           "renderer": "event_dialogue"},
                          {"id": "b", "qa_route": "NEW GAME", "category": "scripts",
                           "renderer": "event_dialogue"}]}
    resolved = {"entries": [{"id": "a", "translated": "[japanese]あ[latin]"}]}
    audit = {"rows": [{"id": "a", "selection": {"category": "scripts", "controls": {},
                       "rom_offset": 1, "slot_size": 5, "original": "A", "fixed_slot": False}}]}
    result = runtime_subset(source, resolved, audit, {"relocations": []})
    assert [row["id"] for row in result["entries"]] == ["a"]


def test_binary_audit_rejects_unrelated_byte_and_classifies_owned_byte():
    assert classify_changed_bytes(b"\x00\x00", b"\x01\x00", {0: "in-place text"})["in-place text"]["count"] == 1
    with pytest.raises(ValueError, match="Unrelated ROM bytes"):
        classify_changed_bytes(b"\x00\x00", b"\x00\x01", {0: "in-place text"})
