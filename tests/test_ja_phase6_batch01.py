"""Technical gate for Claude-reviewed Japanese Batch 01 only."""

from collections import Counter
import json
from pathlib import Path

import pytest

from lib.pcs_text import Charmap
from lib.translation_glossary import load_glossary
from scripts.audit_ja_phase5b import classify_changed_bytes
from scripts.build_ja_phase6_batch01 import validate_review

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out/phase6"


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def test_407_review_exact_ids_original_status_and_tokens():
    review = read(ROOT / "tests/fixtures/ja_phase6_batch01_claude_review.json")
    batch = read(OUT / "ja_phase6_batch01_for_claude.json")
    selection = read(ROOT / "tests/fixtures/ja_phase6_selection.json")
    results = validate_review(review, batch, selection)
    assert len(review) == len(results) == 407
    assert Counter(row["status"] for row in review) == {"confirmed": 401, "needs_context": 6}
    assert all(not row["issues"] for row in results)
    assert {row["id"] for row in review} == {row["id"] for row in batch["entries"]}


def test_56_memory_rows_and_no_memory_only_official_acceptance():
    names = read(OUT / "ja_phase6_batch01_unverified_names.json")
    reviewed = read(OUT / "ja_phase6_batch01_reviewed.json")
    assert names["metadata"]["entry_count"] == 56
    assert names["metadata"]["term_count"] == 77
    assert names["metadata"]["status_counts"] == {
        "verified_exact": 64, "ambiguous": 12, "not_supported": 1,
    }
    by_id = {row["id"]: row for row in reviewed["entries"]}
    for row in names["entries"]:
        for term in row["terms"]:
            if term["verification_status"] == "verified_exact":
                assert term["english_source_term"] == term["english_pokeapi"]
                assert term["claude_japanese"] == term["japanese_pokeapi"]
                assert Charmap(target_lang="ja").encode(
                    f"[japanese]{term['japanese_pokeapi']}[latin]"
                )
        if not row["all_verified"]:
            assert by_id[row["id"]]["technical_status"] == "provisional_official_name"
            assert by_id[row["id"]]["translated"] is None


def test_ace_scope_and_selection_wide_glossary_audit():
    glossary = load_glossary(ROOT / "glossaries/ja.json", expected_language="ja")
    assert glossary.matches("Aerial Ace", "scripts", entry_id="scr_75C267") == []
    assert glossary.matches("Ace", "scripts", entry_id="scr_1F0EF1F")
    audit = read(OUT / "ja_phase6_glossary_match_audit.json")
    assert audit["metadata"]["selection_count"] == 2500
    assert audit["metadata"]["changed_entry_count"] == 4
    assert {row["id"] for row in audit["changed_matches"]} >= {"scr_75C267"}
    assert all(not any(match[2] == "Ace" for match in row["after"])
               for row in audit["changed_matches"])
    assert audit["metadata"]["potential_compound_match_count"] >= 0


def test_glossary_candidates_stay_proposals_only():
    audit = read(OUT / "ja_phase6_batch01_glossary_candidates_audit.json")
    assert audit["metadata"]["count"] == len(audit["entries"]) == 24
    assert Counter(row["kind"] for row in audit["entries"]) == {
        "location": 17, "item": 4, "feature": 1, "npc_label": 1, "other": 1,
    }
    assert all(row["status"] == "proposal_only" for row in audit["entries"])
    assert all(row["pokeapi_applicability"] == "not_found"
               for row in audit["entries"] if row["kind"] == "item")


def test_six_context_holds_and_four_incomplete_owners_stay_english():
    reviewed = read(OUT / "ja_phase6_batch01_reviewed.json")
    statuses = Counter(row["technical_status"] for row in reviewed["entries"])
    assert statuses == {"validated_for_controlfix": 385, "provisional_official_name": 12,
                        "needs_context": 6, "owner_incomplete": 4}
    owners = read(OUT / "ja_phase6_batch01_owner_audit.json")
    assert owners["metadata"] == {"audited": 407, "mismatch_count": 4}
    assert all(row["missing_owners"] and not row["stale_owners"] for row in owners["entries"])
    held_ids = {row["id"] for row in reviewed["entries"] if row["technical_status"] != "validated_for_controlfix"}
    injected = {row["id"] for row in read(OUT / "ja_phase6_batch01_controlfix.json")["entries"]}
    assert not held_ids & injected
    assert len(held_ids) == 22
    evidence = read(OUT / "ja_phase6_batch01_buffer_evidence.json")
    assert evidence["metadata"]["count"] == 6
    assert all(row["conclusion"].endswith("keep English") for row in evidence["entries"])


def test_controlfix_idempotency_and_zero_mismatch():
    first = (OUT / "ja_phase6_batch01_controlfix.json").read_bytes()
    second = (OUT / "ja_phase6_batch01_controlfix_second.json").read_bytes()
    assert first == second
    assert read(OUT / "ja_phase6_batch01_controlfix_report.json")["stats"]["remaining_control_mismatches"] == 0
    assert read(OUT / "ja_phase6_batch01_controlfix_second_report.json")["stats"]["changed"] == 0


def test_fit_detects_relocation_and_keeps_uncertain_width_explicit():
    fit = read(OUT / "ja_phase6_batch01_fit.json")
    assert fit["metadata"]["placement_counts"] == {
        "in_place": 362, "relocation": 23, "held_english": 22,
    }
    assert fit["metadata"]["fixed_count"] == 0
    assert all(row["japanese_bytes"] <= row["slot_size"]
               for row in fit["entries"] if row["placement"] == "in_place")
    assert all(row["japanese_bytes"] > row["slot_size"]
               for row in fit["entries"] if row["placement"] == "relocation")
    assert all(row["renderer_width_limit_pixels"] is None for row in fit["entries"])


def test_strict_binary_audit_and_helper_reject_unrelated_byte():
    report = read(OUT / "ja_phase6_batch01_binary_audit.json")
    assert report["status"] == "PASS"
    assert (report["in_place"], report["relocated"], report["pointer_writes"]) == (840, 222, 2033)
    assert report["vetted_ff_consumed"] == 3142
    assert not read(OUT / "ja_phase6_batch01_map.json")["missing_relocations"]
    with pytest.raises(ValueError, match="Unrelated ROM bytes"):
        classify_changed_bytes(b"abc", b"axc", {0: "in-place text"})


def test_qa_and_batch02_style_handoff_only():
    qa = read(ROOT / "tests/fixtures/ja_phase6_batch01_runtime_qa.json")
    assert 20 <= len(qa["entries"]) <= 30
    safe_ids = {row["id"] for row in read(OUT / "ja_phase6_batch01_safe_input.json")["entries"]}
    assert {row["id"] for row in qa["entries"]} <= safe_ids
    assert all(row["route_confidence"] == "unverified" for row in qa["entries"])
    style = read(OUT / "ja_phase6_batch02_style_handoff.json")
    assert style["status"] == "guidance_only_no_batch02_translation"
    assert "Never use Pokémon, Move, Item, or Ability names from memory" in " ".join(style["rejected_or_risky_notes"])
