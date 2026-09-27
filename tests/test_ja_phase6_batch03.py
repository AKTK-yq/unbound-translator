"""Batch 03 fail-closed technical integration regressions."""

import json
from pathlib import Path

import pytest

from lib.fa_control import join_segments
from scripts.build_ja_phase6_batch03_handoff import audit_rom

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out/phase6"


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def test_review_counts_and_provenance():
    validation = read(OUT / "ja_phase6_batch03_review_validation.json")
    assert validation["metadata"]["count"] == 408
    assert validation["metadata"]["issue_count"] == 0
    assert validation["metadata"]["review_source_counts"] == {
        "Claude CLI": 160, "Codex (user-approved fallback)": 248}
    reviewed = read(OUT / "ja_phase6_batch03_reviewed.json")
    assert reviewed["metadata"]["safe_application_count"] == 125
    assert reviewed["metadata"]["hold_count"] == 283
    assert sum(row["apply"] for row in reviewed["entries"]) == 125


def test_official_names_fit_and_glossary_are_gated():
    names = read(OUT / "ja_phase6_batch03_official_name_audit.json")
    assert names["metadata"]["term_count"] == 108
    assert names["metadata"]["result_counts"] == {
        "verified_exact": 90, "ambiguous": 6, "not_found": 12}
    fit = read(OUT / "ja_phase6_batch03_fit.json")
    assert fit["metadata"]["count"] == 80
    assert fit["metadata"]["result_counts"] == {
        "layout_ambiguous": 65, "width_overflow": 4,
        "owner_incomplete": 2, "in_place": 9}
    glossary = read(OUT / "ja_phase6_batch03_glossary_audit.json")
    assert glossary["metadata"]["candidate_count"] == 30
    assert glossary["metadata"]["scope_collision_count"] == 0
    assert all(row["status"] == "proposal_only_not_approved"
               for row in glossary["candidate_entries"])


def test_fa_accounting_and_segmented_layout_only():
    audit = read(OUT / "ja_phase6_batch03_fa_audit.json")
    metadata = audit["metadata"]
    assert metadata["segmented_handoff_required"] == 122
    assert metadata["classification_counts"] == {
        "semantic_confirmed_review": 51, "segment_conflict": 41,
        "context_hold_only": 21, "technical_nonconflict_hold": 9}
    assert metadata["layout_counts"] == {
        "LAYOUT_PASS": 16, "LAYOUT_AMBIGUOUS": 32,
        "LAYOUT_OVERFLOW": 3, "NOT_SEMANTICALLY_APPROVED": 71}
    reviewed = read(OUT / "ja_phase6_batch03_reviewed.json")
    approved = [row for row in reviewed["entries"] if row["apply"] and row.get("fa_segmented")]
    assert len(approved) == 16
    source = {row["id"]: row for row in
              read(OUT / "ja_phase6_batch03_fa_segmented_input.json")["entries"]}
    for row in approved:
        assert row["layout_result"] == "LAYOUT_PASS"
        assert row["source_boundary_sequence"] == source[row["id"]]["source_boundary_sequence"]
        assert join_segments(source[row["id"]]["control_segments"])


def test_combination_preserves_every_batch02_entry_and_controlfix_is_clean():
    baseline = read(OUT / "ja_phase6_batch02_controlfix.json")["entries"]
    merged = read(OUT / "ja_phase6_batch03_controlfix.json")["entries"]
    assert len(baseline) == 1226 and len(merged) == 1351
    assert merged[:1226] == baseline
    report = read(OUT / "ja_phase6_batch03_controlfix_report.json")["stats"]
    assert report["remaining_control_mismatches"] == 0
    assert report["fa_placement_review_required"] == 0
    assert report["fa_segmented_rebuilt"] == 16
    assert (OUT / "ja_phase6_batch03_controlfix.json").read_bytes() == (
        OUT / "ja_phase6_batch03_controlfix_twice.json").read_bytes()
    invariant = read(OUT / "ja_phase6_batch03_fa_invariant.json")
    assert invariant["status"] == "PASS"
    assert invariant["applied_count"] == 16
    assert all(row["source_controls"] == row["output_controls"] for row in invariant["entries"])


def test_strict_map_and_rom_diff():
    injection_map = read(OUT / "ja_phase6_batch03_map.json")
    stats = injection_map["stats"]
    for field in ("encode_errors", "skipped_pointer_mismatch", "skipped_implausible_pointer",
                  "fixed_truncated", "no_relocation_truncated", "skipped_no_space",
                  "runtime_patches", "graphics_patches"):
        assert stats[field] == 0
    assert not injection_map["missing_relocations"]
    assert not injection_map["missing_fixed_slots"]
    assert read(OUT / "ja_phase6_batch03_rom_audit.json")["unexpected_byte_count"] == 0
    assert read(OUT / "ja_phase6_batch03_incremental_audit.json")["unexpected_byte_count"] == 0


def test_binary_auditor_rejects_unrelated_byte(tmp_path):
    output = bytearray((ROOT / "out/unbound-ja-phase6-batch03.gba").read_bytes())
    output[0x1234] ^= 1
    bad = tmp_path / "bad.gba"
    bad.write_bytes(output)
    with pytest.raises(ValueError, match="Unexpected ROM differences"):
        audit_rom(ROOT / "rom/unbound.gba", bad,
                  read(OUT / "ja_phase6_batch03_controlfix.json"),
                  read(OUT / "ja_phase6_batch03_map.json"))


def test_qa_and_batch04_are_bounded_source_only():
    qa = read(ROOT / "tests/fixtures/ja_phase6_batch03_runtime_qa.json")
    assert len(qa["entries"]) == 36
    assert all(row["runtime_result"] == "not_human_tested" for row in qa["entries"])
    batch04 = read(OUT / "ja_phase6_batch04_fa_segmented_input.json")
    assert len(batch04["entries"]) == 408
    assert batch04["metadata"]["fa_annotated_entries"] == 50
    assert batch04["metadata"]["status"] == "source_only_not_translated"
    assert sum("control_segments" in row for row in batch04["entries"]) == 50
    style = read(OUT / "ja_phase6_batch04_style_handoff.json")
    assert style["batch04_gate"] == "STATIC_GO_SEGMENTED_INPUT_ONLY"
    assert "Translate segment text only" in style["fa_claude_instruction"]
