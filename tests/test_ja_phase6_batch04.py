"""Batch 04 fail-closed technical integration regressions."""

import json
from pathlib import Path

import pytest

from lib.fa_control import join_segments
from scripts.build_ja_phase6_batch03_handoff import audit_rom
from scripts.build_ja_phase6_batch04 import BATTLE_HOLD, BATTLE_SAFE, apply_names, buffer_audit

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out/phase6"


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def test_review_validation_counts():
    meta = read(OUT / "ja_phase6_batch04_review_validation.json")["metadata"]
    assert meta["count"] == 408 and meta["issue_count"] == 0
    assert meta["review_source_counts"] == {"claude_cli": 408}
    assert meta["status_counts"] == {"confirmed": 362, "existing_glossary": 17,
                                     "needs_context": 28, "needs_technical_fit": 1}
    assert (meta["non_fa"], meta["fa"], meta["fa_controls"], meta["fa_segments"],
            meta["multiple_fa_entries"]) == (358, 50, 88, 505, 22)


def test_fifty_fa_entries_fully_accounted():
    audit = read(OUT / "ja_phase6_batch04_fa_audit.json")
    meta = audit["metadata"]
    assert (meta["fa_entries"], meta["fa_controls"], meta["segments"]) == (50, 88, 505)
    assert meta["classification_counts"] == {"semantic_confirmed_review": 48, "segment_conflict": 1,
                                             "context_hold_only": 1}
    assert sum(meta["layout_counts"].values()) == 50
    assert meta["layout_counts"]["NOT_SEMANTICALLY_APPROVED"] == 2
    assert meta["applied_count"] == meta["layout_counts"]["LAYOUT_PASS"]
    source = {r["id"]: r for r in read(OUT / "ja_phase6_batch04_fa_segmented_input.json")["entries"]}
    for row in audit["entries"]:
        assert row["segment_count"] == len(source[row["id"]]["control_segments"])
        assert row["source_controls"] == source[row["id"]]["source_boundary_sequence"]
        assert row["apply"] == (row["layout_status"] == "LAYOUT_PASS")
        if row["apply"]:
            assert join_segments(source[row["id"]]["control_segments"], row["japanese_segments"])


def test_long_segments_measured_in_pixels():
    audit = read(OUT / "ja_phase6_batch04_fa_audit.json")
    assert audit["metadata"]["long_segment_count"] == 60
    assert audit["metadata"]["long_segment_entries"] == 39
    applied = {r["id"] for r in audit["entries"] if r["apply"]}
    for segment in audit["long_segments"]:
        assert segment["visible_chars"] > 18
        if segment["class"] in {"WIDTH_OVERFLOW", "LAYOUT_AMBIGUOUS", "RENDERER_UNKNOWN"}:
            assert segment["id"] not in applied
        if segment["class"] == "WIDTH_OVERFLOW":
            assert segment["pixels"] > 240


def test_specific_holds():
    reviewed = {r["id"]: r for r in read(OUT / "ja_phase6_batch04_reviewed.json")["entries"]}
    conflict = reviewed["scr_1F48ED0"]
    assert not conflict["apply"] and conflict["fa_semantic_result"] == "segment_conflict"
    assert not reviewed["scr_1F4C2ED"]["apply"]
    assert reviewed["scr_1F4C2ED"]["fa_semantic_result"] == "context_hold_only"
    handoff = read(OUT / "ja_phase6_batch04_fa_retranslation.json")
    assert handoff["id"] == "scr_1F48ED0" and handoff["no_codex_translation"]
    assert all(not r["apply"] for r in reviewed.values() if r["review_status"] == "needs_context")


def test_official_names_and_fallback():
    names = read(OUT / "ja_phase6_batch04_official_name_audit.json")
    meta = names["metadata"]
    assert (meta["occurrence_count"], meta["unique_term_count"], meta["entry_count"]) == (112, 54, 81)
    assert meta["pokeapi_type_occurrences"] == 83
    reviewed = {r["id"]: r for r in read(OUT / "ja_phase6_batch04_reviewed.json")["entries"]}
    for row in names["entries"]:
        if row["verification_result"] not in {"verified_exact", "verified_difference"}:
            assert row["final_value"] is None
            assert not reviewed[row["entry_id"]]["apply"]
    row = {"id": "x"}
    text, _, reasons = apply_names(row, [{"English term": "Moomoo Milks", "verification_result": "not_found",
                                          "final_value": None, "proposed_japanese": "モーモーミルク"}],
                                   "モーモーミルク 5こ", None)
    assert reasons and text == "モーモーミルク 5こ"


def test_battle_buffer_rule():
    assert set(BATTLE_SAFE) == {"0F", "10", "11", "13", "14", "1A"}
    assert {"00", "01", "2A", "36", "38"} <= set(BATTLE_HOLD)
    safe = buffer_audit({"buffers": ["\\\\0F"]}, "\\\\0F fell asleep!")
    assert safe["result"] == "resolved_type"
    held = buffer_audit({"buffers": ["\\\\2A", "\\\\14"]}, "\\\\2A’s \\\\14 raised Defense!")
    assert held["result"] == "unknown"
    assert buffer_audit({"buffers": ["[buffer1]"]}, "[buffer1]")["result"] == "unknown"
    assert buffer_audit({"buffers": ["[player]"]}, "[player]!")["result"] == "resolved_type"


def test_existing_glossary_and_route_template():
    existing = read(OUT / "ja_phase6_batch04_existing_glossary_audit.json")
    assert existing["metadata"]["count"] == 17
    assert existing["metadata"]["kinds"] == {"deterministic_location": 3, "route_template": 14}
    assert existing["metadata"]["route_template_misapplied_to_prose"] == []
    for row in existing["entries"]:
        assert row["valid"]
        if row["kind"] == "route_template":
            assert row["number_preserved"] and row["reviewed"].endswith("ばんどうろ")


def test_glossary_candidates_not_approved():
    glossary = read(OUT / "ja_phase6_batch04_glossary_audit.json")
    assert glossary["metadata"]["candidate_count"] == 55
    assert glossary["metadata"]["scope_collision_count"] == 0
    assert all(r["status"] == "proposal_only_not_approved" for r in glossary["candidate_entries"])
    reviewed = read(OUT / "ja_phase6_batch04_reviewed.json")["entries"]
    assert not any(r["apply"] for r in reviewed if r["category"] == "mission_names")


def test_controlfix_idempotent_and_baseline_preserved():
    baseline = read(OUT / "ja_phase6_batch03_controlfix.json")["entries"]
    merged = read(OUT / "ja_phase6_batch04_controlfix.json")["entries"]
    safe = read(OUT / "ja_phase6_batch04_reviewed.json")["metadata"]["safe_application_count"]
    assert len(baseline) == 1351 and len(merged) == 1351 + safe
    assert merged[:1351] == baseline
    report = read(OUT / "ja_phase6_batch04_controlfix_report.json")["stats"]
    assert report["remaining_control_mismatches"] == 0
    assert report["fa_placement_review_required"] == 0
    assert (OUT / "ja_phase6_batch04_controlfix.json").read_bytes() == (
        OUT / "ja_phase6_batch04_controlfix_twice.json").read_bytes()
    invariant = read(OUT / "ja_phase6_batch04_fa_invariant.json")
    assert invariant["status"] == "PASS" and invariant["error_count"] == 0
    assert all(r["source_controls"] == r["output_controls"] for r in invariant["entries"])


def test_strict_map_and_rom_diff():
    for name in ("ja_phase6_batch04_map.json", "ja_phase6_batch04_dry_run_map.json"):
        injection_map = read(OUT / name)
        stats = injection_map["stats"]
        for field in ("encode_errors", "skipped_pointer_mismatch", "skipped_implausible_pointer",
                      "fixed_truncated", "no_relocation_truncated", "skipped_no_space",
                      "runtime_patches", "graphics_patches"):
            assert stats[field] == 0
        assert not injection_map["missing_relocations"] and not injection_map["missing_fixed_slots"]
    assert read(OUT / "ja_phase6_batch04_rom_audit.json")["unexpected_byte_count"] == 0
    assert read(OUT / "ja_phase6_batch04_incremental_audit.json")["unexpected_byte_count"] == 0


def test_binary_auditor_rejects_unrelated_byte(tmp_path):
    output = bytearray((ROOT / "out/unbound-ja-phase6-batch04.gba").read_bytes())
    output[0x1234] ^= 1
    bad = tmp_path / "bad.gba"
    bad.write_bytes(output)
    with pytest.raises(ValueError, match="Unexpected ROM differences"):
        audit_rom(ROOT / "rom/unbound.gba", bad, read(OUT / "ja_phase6_batch04_controlfix.json"),
                  read(OUT / "ja_phase6_batch04_map.json"))


def test_runtime_qa_and_batch05_inputs():
    qa = read(ROOT / "tests/fixtures/ja_phase6_batch04_runtime_qa.json")
    assert 30 <= len(qa["entries"]) <= 40
    focus = qa["metadata"]["focus_counts"]
    assert 8 <= sum(v for k, v in focus.items() if k.startswith("FA_")) <= 10
    assert all(r["runtime_result"] == "not_human_tested" for r in qa["entries"])
    batch05 = read(OUT / "ja_phase6_batch05_fa_segmented_input.json")
    assert len(batch05["entries"]) == 408
    assert batch05["metadata"]["status"] == "source_only_not_translated"
    assert sum("control_segments" in r for r in batch05["entries"]) == batch05["metadata"]["fa_annotated_entries"]
    style = read(OUT / "ja_phase6_batch05_style_handoff.json")
    assert style["batch05_gate"] == "STATIC_GO_SEGMENTED_INPUT_ONLY"
    assert set(style["battle_buffer_rule"]["engine_defined_types"]) == set(BATTLE_SAFE)
