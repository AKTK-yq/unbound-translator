"""Phase 6C-1 accounting, queue completeness, and ROM-safety regressions."""

from collections import Counter
import pytest

from scripts.build_ja_phase6_cleanup_stage1 import (
    OUT, ROOT, CLASSES, assert_strict_map, audit_rom, buffer_class,
    read, validate_inventory, width_class,
)

FIX = ROOT / "tests/fixtures"


@pytest.fixture(scope="module")
def data():
    inventory = read(OUT / "ja_phase6_final_cleanup_inventory_v2.json")
    selected = read(FIX / "ja_phase6_selection.json")["entries"]
    baseline = read(OUT / "ja_phase6_batch06_combined_controlfix.json")["entries"]
    return inventory, selected, baseline


def test_inventory_1129_and_no_applied_overlap(data):
    inventory, selected, baseline = data
    original = read(OUT / "ja_phase6_final_cleanup_inventory.json")
    assert validate_inventory(original, selected, baseline)["validated"]
    assert {x["id"] for x in inventory["entries"]} == {x["id"] for x in original["entries"]}
    assert len(inventory["entries"]) == 1129
    assert len({x["id"] for x in baseline}) == 2048


def test_resolution_complete_and_deterministic_applied(data):
    rows = data[0]["entries"]
    assert {x["resolution_class"] for x in rows} <= CLASSES
    assert all(x["previous_primary_hold"] and isinstance(x["previous_secondary_holds"], list)
               and x["priority"] in {"P1", "P2", "P3"} for x in rows)
    assert sum(x["apply_status"] == "applied" for x in rows) == 170
    assert all(x["apply_status"] == "applied" for x in rows if x["deterministic"])
    assert Counter(x["resolution_class"] for x in rows) == data[0]["metadata"]["resolution_counts"]


def test_width_buffer_control_pointer_classifications(data):
    rows = data[0]["entries"]
    by = lambda category: [x for x in rows if x["previous_primary_hold"] == category]
    assert Counter(x["normalized_technical_facts"]["width_class"] for x in by("WIDTH_LAYOUT")) == {
        "A_RUNTIME_UNVERIFIED_ONLY": 137, "B_DYNAMIC_WORST_CASE": 32,
        "C_STATIC_OVERFLOW": 5, "D_STRUCTURED_OR_UNKNOWN": 17,
    }
    assert len(by("UNKNOWN_BUFFER")) == 280
    assert all(x["normalized_technical_facts"]["buffer_class"] in {
        "BUFFER_VALUE_PROVEN", "BUFFER_TYPE_PROVEN", "FINITE_SET_PROVEN",
        "CALLER_DEPENDENT", "DYNAMIC_UNKNOWN", "UNRESOLVED",
    } for x in by("UNKNOWN_BUFFER"))
    assert Counter(x["normalized_technical_facts"]["control_class"] for x in by("CONTROL_BOUNDARY")) == {
        "B_SOURCE_SEGMENTS_UNIQUE": 72, "C_SEMANTIC_OR_GRAMMAR_CONFLICT": 7,
        "D_UNPROVEN_SEGMENTS": 9,
    }
    assert len(by("POINTER_OWNER")) == 19
    assert all("pointer_reference_details" in x["normalized_technical_facts"] for x in by("POINTER_OWNER"))


def test_classifier_examples(data):
    rows = {x["id"]: x for x in data[0]["entries"]}
    original = {x["id"]: x for x in read(OUT / "ja_phase6_final_cleanup_inventory.json")["entries"]}
    assert width_class(original["scr_1F07615"]) == "A_RUNTIME_UNVERIFIED_ONLY"
    assert buffer_class({}, {"buffers": ["[buffer1]"]}) == "CALLER_DEPENDENT"
    assert buffer_class({}, {"buffers": ["[player]"]}) == "BUFFER_TYPE_PROVEN"
    assert rows["scr_1F07615"]["normalized_technical_facts"]["width_class"] == "A_RUNTIME_UNVERIFIED_ONLY"


def test_glossary_exact_dedup_and_coverage(data):
    terms = read(OUT / "ja_phase6_cleanup_for_claude_glossary.json")
    keys = [(x["english_term"].casefold(), x["term_type"]) for x in terms["terms"]]
    assert len(keys) == len(set(keys)) == terms["metadata"]["term_count"]
    covered = {id_ for term in terms["terms"] for id_ in term["affected_ids"]}
    covered |= {x["id"] for x in terms["entry_scope_reviews"]}
    glossary_class = {x["id"] for x in data[0]["entries"]
                      if x["resolution_class"] == "CLAUDE_GLOSSARY"}
    assert glossary_class <= covered
    assert terms["metadata"]["approved"] == 0


def test_handoff_queue_completeness_and_runtime_minimality(data):
    rows = data[0]["entries"]
    translation = read(OUT / "ja_phase6_cleanup_for_claude_translation.json")["entries"]
    investigation = read(OUT / "ja_phase6_cleanup_for_codex_investigation.json")["entries"]
    runtime = read(OUT / "ja_phase6_cleanup_runtime_review.json")["entries"]
    assert {x["id"] for x in translation} == {x["id"] for x in rows if x["resolution_class"] in {
        "CLAUDE_TRANSLATION", "CLAUDE_CONTEXT"}}
    assert {x["id"] for x in investigation} == {x["id"] for x in rows
                                               if x["resolution_class"] == "CODEX_INVESTIGATION"}
    assert {x["id"] for x in runtime} == {x["id"] for x in rows
                                         if x["resolution_class"] == "RUNTIME_REVIEW"}
    assert all(x["previous_primary_hold"] == "WIDTH_LAYOUT" and
               x["known_technical_constraints"]["normalized_facts"]["width_class"]
               == "B_DYNAMIC_WORST_CASE" for x in runtime)


def test_existing_2048_unchanged_and_strict_map(data):
    baseline = data[2]
    merged = read(OUT / "ja_phase6_cleanup_combined_controlfix.json")["entries"]
    assert merged[:2048] == baseline and len(merged) == 2218
    dry = read(OUT / "ja_phase6_cleanup_incremental_dry_run_map.json")
    built = read(OUT / "ja_phase6_cleanup_incremental_map.json")
    assert_strict_map(dry, built, 170)
    assert built["stats"]["in_place"] == 119
    assert built["stats"]["relocated"] == 51
    assert built["stats"]["pointer_writes"] == 153


def test_strict_map_rejects_pointer_mismatch():
    dry = read(OUT / "ja_phase6_cleanup_incremental_dry_run_map.json")
    built = read(OUT / "ja_phase6_cleanup_incremental_map.json")
    changed = dict(built)
    changed["stats"] = {**built["stats"], "skipped_pointer_mismatch": 1}
    with pytest.raises(AssertionError):
        assert_strict_map(dry, changed, 170)


def test_binary_audit_no_unexpected_bytes():
    result = audit_rom()
    assert result["status"] == "PASS"
    assert result["unexpected_bytes"] == 0
    assert result["changed_bytes"] == sum(result["classified_changed_bytes"].values())
    assert (ROOT / "out/unbound-ja-phase6-cleanup-codex.gba").stat().st_size == 0x2000000
