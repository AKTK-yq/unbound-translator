"""Phase 6B-2 technical gate; Batch 03 translation is intentionally absent."""

from collections import Counter
import json
from pathlib import Path

import pytest

from lib.translation_glossary import load_glossary
from scripts.audit_ja_phase5b import classify_changed_bytes
from scripts.audit_ja_phase6_batch02_controls import scroll_semantics
from scripts.audit_ja_phase6_batch02_names import lookup
from scripts.build_ja_phase6_batch02 import review_validation

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out/phase6"


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def test_review_408_identity_provenance_tokens_and_charmap():
    review = read(ROOT / "tests/fixtures/ja_phase6_batch02_claude_review.json")
    batch = read(OUT / "ja_phase6_batch02_for_claude.json")
    selection = read(ROOT / "tests/fixtures/ja_phase6_selection.json")
    result = review_validation(review, batch, selection)
    assert result["metadata"]["issue_count"] == 0
    assert result["metadata"]["count"] == 408
    assert result["metadata"]["provenance_counts"] == {
        "Claude CLI": 200, "Codex (user-approved fallback)": 208}
    assert result["metadata"]["status_counts"] == {
        "confirmed": 195, "existing_glossary": 7,
        "needs_context": 156, "needs_technical_fit": 50}


def test_all_153_name_observations_and_no_memory_only_acceptance():
    audit = read(OUT / "ja_phase6_batch02_official_name_audit.json")
    assert audit["metadata"]["term_count"] == 153
    assert audit["metadata"]["entry_count"] == 120
    assert Counter(row["verification_result"] for row in audit["entries"]) == {
        "verified_exact": 89, "not_found": 21, "unsupported": 40, "ambiguous": 3}
    for row in audit["entries"]:
        verified = row["verification_result"] in {"verified_exact", "verified_difference"}
        assert bool(row["final_value"]) == verified
        if verified:
            assert row["source_occurs_exactly"]
            assert row["pokeapi_english"] == row["source_term"]
            assert row["final_value"] == row["pokeapi_japanese"]
    reviewed = read(OUT / "ja_phase6_batch02_reviewed.json")
    unresolved_ids = {row["entry_id"] for row in audit["entries"] if row["final_value"] is None}
    assert not unresolved_ids & {row["id"] for row in reviewed["entries"] if row["apply"]}


def test_pokeapi_lookup_requires_exact_english_entity_and_supported_type():
    class FakeLocalizer:
        def _get(self, endpoint, identifier):
            if endpoint == "item" and identifier in {"nugget", "nuggets"}:
                return {"names": [
                    {"language": {"name": "en"}, "name": "Nugget"},
                    {"language": {"name": "ja-hrkt"}, "name": "きんのたま"}]}
            return None

    localizer = FakeLocalizer()
    assert lookup(localizer, "Nugget", "item")["result"] == "verified_exact"
    assert lookup(localizer, "Nuggets", "item")["result"] == "ambiguous"
    assert lookup(localizer, "Nugget", "trainer_title")["result"] == "unsupported"


def test_fa_scroll_rom_semantics_and_30_placement_holds():
    rom = (ROOT / "rom/unbound.gba").read_bytes()
    semantics = scroll_semantics(rom)
    assert semantics["targets"]["0xFA"] == "0x08005B26"
    assert semantics["targets"]["0xFB"] == "0x08005B22"
    audit = read(OUT / "ja_phase6_batch02_scroll_audit.json")
    reviewed = {row["id"]: row for row in read(OUT / "ja_phase6_batch02_reviewed.json")["entries"]}
    assert len(audit["entries"]) == 30
    assert all(row["placement_class"] == "C" and not row["safe_to_move_in_controlfix"]
               for row in audit["entries"])
    assert all(len(row["source_fa_byte_positions"]) == len(row["source_text_positions"])
               for row in audit["entries"])
    assert all(not reviewed[row["id"]]["apply"] for row in audit["entries"])


def test_49_buffers_and_dynamic_suffixes_not_guessed():
    audit = read(OUT / "ja_phase6_batch02_buffer_audit.json")
    rows = audit["entries"]
    assert len(rows) == 49
    assert audit["metadata"]["status_counts"] == {"unknown": 48, "runtime-dependent": 1}
    reviewed = {row["id"]: row for row in read(OUT / "ja_phase6_batch02_reviewed.json")["entries"]}
    assert all(not reviewed[row["id"]]["apply"] for row in rows)
    variable = next(row for row in rows if row["id"] == "scr_1F0DBDC")
    assert set(variable["possible_values_proved"]) == {"item", "Pokémon", "TM"}
    assert len(variable["writer_evidence"]) == 3
    assert any(row["raw_suffix_tokens"] for row in rows)


def test_50_technical_fit_measured_without_shortening_or_auto_approval():
    fit = read(OUT / "ja_phase6_batch02_fit.json")
    assert fit["metadata"]["count"] == 50
    assert fit["metadata"]["result_counts"] == {
        "in_place": 45, "relocatable": 2, "structured_constraint": 3}
    assert fit["metadata"]["confirmed_width_overflow"] == 0
    for row in fit["entries"]:
        assert not row["apply"]
        assert row["source_bytes"] == row["slot_size"]
        if row["fit_result"] == "relocatable":
            assert row["japanese_encoded_bytes"] > row["slot_size"]
            assert row["relocation_possible"]
        assert row["renderer_width_limit_pixels"] is None


def test_glossary_boundary_and_18_proposals_remain_unapproved():
    glossary = load_glossary(ROOT / "glossaries/ja.json", expected_language="ja")
    assert glossary.matches("Aerial Ace", "scripts", entry_id="scr_75C267") == []
    audit = read(OUT / "ja_phase6_batch02_glossary_audit.json")
    assert audit["metadata"]["candidate_count"] == 18
    assert audit["metadata"]["scope_mismatch_count"] == 0
    assert all(row["status"] == "proposal_only" for row in audit["candidate_entries"])
    assert all(row["claim_scope_valid"] for row in audit["review_matches"])


def test_reviewed_safe_set_and_pointer_owner_holds():
    reviewed = read(OUT / "ja_phase6_batch02_reviewed.json")
    assert reviewed["metadata"]["safe_application_count"] == 164
    assert reviewed["metadata"]["hold_count"] == 244
    safe = read(OUT / "ja_phase6_batch02_safe_input.json")["entries"]
    assert len(safe) == 164
    assert {row["id"] for row in safe} == {row["id"] for row in reviewed["entries"] if row["apply"]}
    assert sum("compact_width_unproven" in row["hold_reason"] and row["status"] == "confirmed"
               for row in reviewed["entries"]) == 35
    assert all(row["fit_result"] == "in_place" and row["final_encoded_bytes"] <= row["source_slot_bytes"]
               for row in reviewed["entries"] if row["apply"])
    owners = read(OUT / "ja_phase6_batch02_owner_audit.json")
    assert owners["metadata"]["mismatch_count"] == 2
    assert {row["id"] for row in owners["entries"] if row["missing"]} == {
        "scr_1F0DAD3", "scr_1F0DD3F"}
    assert next(row for row in owners["entries"] if row["id"] == "scr_1F0DD3F")["missing_kinds"] == [
        "bufferstring 0 operand"]
    assert len(read(OUT / "ja_phase6_batch02_combined_input.json")["entries"]) == 1226


def test_controlfix_idempotent_and_strict_binary_audit():
    assert (OUT / "ja_phase6_batch02_controlfix.json").read_bytes() == (
        OUT / "ja_phase6_batch02_controlfix_second.json").read_bytes()
    assert read(OUT / "ja_phase6_batch02_controlfix_report.json")["stats"]["remaining_control_mismatches"] == 0
    assert read(OUT / "ja_phase6_batch02_controlfix_second_report.json")["stats"]["changed"] == 0
    dry = read(OUT / "ja_phase6_batch02_dry_run_map.json")
    real = read(OUT / "ja_phase6_batch02_map.json")
    assert dry["stats"] == real["stats"]
    assert all(real["stats"][key] == 0 for key in (
        "encode_errors", "skipped_pointer_mismatch", "skipped_implausible_pointer",
        "skipped_no_space", "fixed_truncated", "no_relocation_truncated",
        "runtime_patches", "graphics_patches"))
    audit = read(OUT / "ja_phase6_batch02_binary_audit.json")
    assert audit["status"] == "PASS"
    assert (audit["in_place"], audit["relocated"], audit["pointer_writes"]) == (1004, 222, 2033)
    incremental = read(OUT / "ja_phase6_batch02_incremental_audit.json")
    assert incremental["status"] == "PASS"
    assert (incremental["applied_entries"], incremental["changed_byte_count"],
            incremental["unexpected_byte_count"], incremental["pointer_writes"],
            incremental["relocations"]) == (164, 12872, 0, 0, 0)
    with pytest.raises(ValueError, match="Unrelated ROM bytes"):
        classify_changed_bytes(b"abc", b"axc", {0: "in-place text"})


def test_runtime_qa_and_batch03_segmented_gate():
    qa = read(ROOT / "tests/fixtures/ja_phase6_batch02_runtime_qa.json")
    assert len(qa["entries"]) == 30
    safe_ids = {row["id"] for row in read(OUT / "ja_phase6_batch02_safe_input.json")["entries"]}
    assert {row["id"] for row in qa["entries"]} <= safe_ids
    assert all(row["route_confidence"] == "unverified" for row in qa["entries"])
    assert all(row["placement"] == "in_place" for row in qa["entries"])
    handoff = read(OUT / "ja_phase6_batch03_style_handoff.json")
    assert handoff["batch03_gate"] == "STATIC_GO_SEGMENTED_INPUT_ONLY"
    assert "scroll" in handoff["fa_scroll_rule"]
