"""Phase 6C-2B glossary integration, propagation, and ROM-safety regressions."""

from collections import Counter
import json

import pytest

from lib.translation_glossary import load_glossary
from scripts.build_ja_phase6_cleanup_glossary import (
    APPROVED_DECISIONS, BASE_ROM, GLOSSARY, GLOSSARY_BACKUP, NEW_ROM, OUT, ROOT, REVIEW,
    assert_strict_map, audit_rom, candidate_has_terms, glossary_consistency, is_term_reason,
    read, reroute, verify_official,
)

FIX = ROOT / "tests/fixtures"


@pytest.fixture(scope="module")
def review():
    return read(REVIEW)["terms"]


@pytest.fixture(scope="module")
def stage():
    return {x["id"]: x for x in read(OUT / "ja_phase6_cleanup_glossary_propagation.json")["entries"]}


def test_all_208_decisions_kept_and_counts(review):
    assert len(review) == 208 and len({r["index"] for r in review}) == 208
    assert Counter(r["decision"] for r in review) == {
        "APPROVED_PROJECT_STANDARD": 142, "UNRESOLVED_TERM": 25, "APPROVED_OFFICIAL": 16,
        "UNRESOLVED_CONTEXT": 10, "APPROVED_CONTEXT_SCOPED": 10, "REJECT_CANDIDATE": 3,
        "KEEP_EXISTING": 2}
    assert sum(r["decision"] in APPROVED_DECISIONS for r in review) == 170


def test_glossary_merge_preserves_existing_terms_and_scope(review):
    old = read(GLOSSARY_BACKUP)["terms"]
    new = read(GLOSSARY)["terms"]
    assert len(old) == 139 and len(new) == 292
    assert new[:139] == old, "existing approved terms must be unchanged and keep their order"
    added = new[139:]
    assert len(added) == 153
    assert all(t["global_replace"] is False and t["entry_ids"] for t in added)
    patch = read(OUT / "ja_phase6_cleanup_glossary_approved.json")["entries"]
    assert {(t["source"], t["target"]) for t in added} >= {(e["source"], e["target"]) for e in patch}
    assert len(load_glossary(GLOSSARY, expected_language="ja").terms) == 292


def test_rejected_and_unresolved_terms_are_not_merged(review):
    sources = {t["source"] for t in read(GLOSSARY)["terms"]}
    for row in review:
        if row["decision"] in {"REJECT_CANDIDATE"} or row["decision"].startswith("UNRESOLVED"):
            assert row["english"] not in sources, row["english"]
    assert not {"Cut", "Strength", "Fighting"} & sources
    psychic = [t for t in read(GLOSSARY)["terms"] if t["source"] == "Psychic"]
    assert len(psychic) == 1 and psychic[0]["entry_ids"] == ["scr_1F3394E"]


def test_no_global_leak_and_zero_conflicts_or_collisions():
    result = glossary_consistency(load_glossary(GLOSSARY, expected_language="ja"), None)
    assert result["conflicts"] == 0 and result["scope_collisions"] == 0
    assert result["collision_risk_sources_checked"] == 63


def test_matcher_examples_stay_scoped():
    glossary = load_glossary(GLOSSARY, expected_language="ja")
    assert glossary.matches("Aerial Ace", "scripts", entry_id="scr_75C267") == []
    assert glossary.matches("Let’s cut them off at the exit.", "scripts", entry_id="scr_1F3164B") == []
    assert glossary.matches("Lucky Egg", "scripts", entry_id="unrelated") == []
    assert glossary.matches("Egg", "menu_pokemon_summary", entry_id="unrelated") == []
    # Longest term wins over the nested existing global term.
    hits = glossary.matches("Antisis City", "scripts", entry_id="scr_1F13B6A")
    assert [t.target for _, _, t in hits] == ["アンティシスシティ"]
    hits = glossary.matches("Zeph Jr.", "scripts", entry_id="scr_1F0CA42")
    assert [t.target for _, _, t in hits] == ["ゼフジュニア"]


def test_official_claims_have_evidence(review):
    results = verify_official(review)
    assert len(results) == 28
    assert all(x["class"] != "no_evidence" for x in results)
    assert Counter(x["class"] for x in results) == {
        "verified_exact": 12, "verified_genus_pair": 10,
        "verified_singular_plural_inferred": 5, "entity_exact_but_audit_ambiguous": 1}
    qualot = [t for t in read(GLOSSARY)["terms"] if t["source"] == "Qualot Berry"][0]
    assert qualot["status"] == "context_scoped" and "needs_human_confirmation" in qualot["note"]


def test_propagation_accounting(stage):
    assert len(stage) == 282
    assert Counter(r["propagation"] for r in stage.values()) == {
        "safe_injectable": 43, "term_resolved_other_holds": 165,
        "term_resolved_technical_gate_failed": 26, "blocked_unresolved_term": 32,
        "already_applied": 12, "no_term_needed": 4}
    resolved = [r for r in stage.values() if r["glossary_status"] == "glossary_resolved"]
    assert len(resolved) == 245
    unresolved_ids = {i for x in read(OUT / "ja_phase6_cleanup_glossary_unresolved.json")["entries"]
                      for i in x["affected_ids"]}
    safe = [r for r in stage.values() if r["propagation"] == "safe_injectable"]
    assert not {r["id"] for r in safe} & unresolved_ids, "unresolved terms must never be auto-applied"


def test_safe_entries_use_existing_candidate_with_approved_terms(review, stage):
    inventory = {x["id"]: x for x in read(OUT / "ja_phase6_final_cleanup_inventory_v2.json")["entries"]}
    by_id = {}
    for row in review:
        if row["decision"] in APPROVED_DECISIONS:
            for entry_id in row["resolved_ids"]:
                by_id.setdefault(entry_id, []).append(row)
    safe_entries = read(OUT / "ja_phase6_cleanup_glossary_safe_controlfix.json")["entries"]
    assert len(safe_entries) == 43
    for entry in safe_entries:
        key = entry["id"]
        assert stage[key]["propagation"] == "safe_injectable"
        assert entry["translated"] == "[japanese]" + inventory[key]["candidate_japanese"] + "[latin]"
        assert not candidate_has_terms(inventory[key]["candidate_japanese"], by_id[key])
        assert all(is_term_reason(x) or x == "width_unproved:layout_ambiguous"
                   for x in inventory[key]["normalized_technical_facts"]["raw_hold_reasons"])
        assert stage[key]["gate"]["failures"] == []


def test_candidate_term_check_rejects_reworded_candidate(review):
    gem = [r for r in review if r["english"] == "Gem"][0]
    assert candidate_has_terms("ジェムを あつめよう", [gem]) == ["Gem"]
    assert candidate_has_terms("ジュエルを あつめよう", [gem]) == []


def test_reroute_is_deterministic():
    assert reroute(["needs_context"]) == "CLAUDE_CONTEXT"
    assert reroute(["no_candidate_translation"]) == "CLAUDE_TRANSLATION"
    assert reroute(["fa_layout:LAYOUT_AMBIGUOUS"]) == "CODEX_INVESTIGATION"
    assert reroute(["physical_screen_width_overflow", "source_control_sequence_changed"]) == "CLAUDE_TRANSLATION"


def test_existing_2218_unchanged_and_controlfix_idempotent():
    baseline = read(OUT / "ja_phase6_cleanup_combined_controlfix.json")["entries"]
    combined = read(OUT / "ja_phase6_cleanup_glossary_combined_controlfix.json")["entries"]
    candidates = read(OUT / "ja_phase6_cleanup_glossary_candidates_controlfix.json")["entries"]
    assert len(baseline) == 2218 and len(combined) == 2261
    assert combined[:2218] == baseline and candidates[:2218] == baseline
    assert combined[2218:] == read(OUT / "ja_phase6_cleanup_glossary_safe_controlfix.json")["entries"]
    assert (OUT / "ja_phase6_cleanup_glossary_candidates_controlfix.json").read_bytes() == (
        OUT / "ja_phase6_cleanup_glossary_candidates_controlfix_twice.json").read_bytes()
    report = read(OUT / "ja_phase6_cleanup_glossary_candidates_controlfix_report.json")["stats"]
    assert report["remaining_control_mismatches"] == 0


def test_strict_maps_and_binary_audit():
    plan = read(OUT / "ja_phase6_cleanup_glossary_incremental_dry_run_map.json")
    built = read(OUT / "ja_phase6_cleanup_glossary_incremental_map.json")
    assert_strict_map(plan, built, 43)
    assert built["stats"]["in_place"] == 43 and built["stats"]["relocated"] == 0
    full = read(OUT / "ja_phase6_cleanup_glossary_full_dry_run_map.json")
    for key in ("skipped_pointer_mismatch", "skipped_implausible_pointer", "skipped_no_space", "encode_errors",
                "fixed_truncated", "no_relocation_truncated", "ability_descriptions_compacted",
                "runtime_patches", "graphics_patches"):
        assert full["stats"][key] == 0
    result = audit_rom()
    assert result["status"] == "PASS" and result["unexpected_bytes"] == 0
    assert result["changed_bytes"] == sum(result["classified_changed_bytes"].values())
    assert NEW_ROM.stat().st_size == 0x2000000


def test_binary_audit_rejects_unrelated_byte(tmp_path):
    data = bytearray(NEW_ROM.read_bytes())
    data[0x1234] ^= 1
    bad = tmp_path / "bad.gba"
    bad.write_bytes(data)
    with pytest.raises(AssertionError):
        audit_rom(BASE_ROM, bad)


def test_inventory_v3_accounting_and_queue_completeness():
    v2 = read(OUT / "ja_phase6_final_cleanup_inventory_v2.json")["entries"]
    v3 = read(OUT / "ja_phase6_final_cleanup_inventory_v3.json")["entries"]
    assert [x["id"] for x in v2] == [x["id"] for x in v3] and len(v3) == 1129
    assert sum(x["apply_status"] == "applied" for x in v3) == 213
    assert sum(x["apply_status"] != "applied" for x in v3) == 916
    for old, new in zip(v2, v3):
        if old["apply_status"] == "applied":
            assert new["apply_status"] == "applied" and new["resolution_class"] == old["resolution_class"]
    handoff = read(OUT / "ja_phase6_cleanup_translation_handoff_v2.json")
    ids = [x["id"] for x in handoff["entries"]]
    assert len(ids) == len(set(ids)) == 569
    assert set(ids) == {x["id"] for x in v3 if x["apply_status"] != "applied"
                        and x["resolution_class"] in {"CLAUDE_TRANSLATION", "CLAUDE_CONTEXT"}}


def test_handoff_v2_keeps_v1_fields_and_speaker_metadata():
    v1 = {x["id"]: x for x in read(OUT / "ja_phase6_cleanup_for_claude_translation.json")["entries"]}
    handoff = read(OUT / "ja_phase6_cleanup_translation_handoff_v2.json")["entries"]
    selection = {x["id"]: x for x in read(FIX / "ja_phase6_selection.json")["entries"]}
    for entry in handoff:
        old = v1.get(entry["id"])
        if old:
            for key, value in old.items():
                if key != "requested_claude_task":
                    assert entry[key] == value, (entry["id"], key)
        meta = entry["preserved_metadata"]
        source = selection[entry["id"]]
        for key in ("speaker", "speaker_confidence", "scene_id", "conversation_id", "context_confidence"):
            assert meta[key] == source[key]
        assert entry["original_english"] == source["original"]
        assert meta["source_game"]["value"] is None
        if source["speaker"] == "unknown":
            assert meta["character_name"]["value"] is None
        assert all("name match only" in m["identity_claim"] for m in meta["name_mentions"])


def test_affected_ids_not_lost(review, stage):
    queue = read(OUT / "ja_phase6_cleanup_for_claude_glossary.json")
    expected = {i for t in queue["terms"] for i in t["affected_ids"]}
    assert expected == {i for r in review for i in r["affected_ids"]} == set(stage)
    for row in review:
        assert set(row["resolved_ids"]) | set(row["unresolved_ids"]) | set(row["false_positive_ids"]) == set(row["affected_ids"])
    scope_47 = {x["id"] for x in queue["entry_scope_reviews"]}
    assert len(expected) + len(scope_47) == 329 and not expected & scope_47
    handoff = read(OUT / "ja_phase6_cleanup_translation_handoff_v2.json")
    assert {x["id"] for x in handoff["term_identification_needed"]} == scope_47
    assert len(handoff["unresolved_terms"]) == 39
