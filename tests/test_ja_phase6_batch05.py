"""Batch 05 review, control, incremental injection and handoff invariants."""

import json
from pathlib import Path

import pytest

from lib.renderer_profiles import battle_profiles, maximum_table_width, rom_naming_profiles
from scripts.build_ja_phase6_batch05 import control_sequence, validate
from scripts.build_ja_phase6_batch05_handoff import incremental_audit, strict_map

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out/phase6"
FIX = ROOT / "tests/fixtures"


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def inputs():
    review = read(FIX / "ja_phase6_batch05_claude_review.json")
    source = read(OUT / "ja_phase6_batch05_fa_segmented_input.json")["entries"]
    selected = [x for x in read(FIX / "ja_phase6_selection.json")["entries"] if x.get("batch_number") == 5]
    return review, source, selected


def test_review_408_exact_ids_status_tokens_and_metadata():
    review, source, selected = inputs()
    result = validate(review, source, selected)
    assert result == read(OUT / "ja_phase6_batch05_review_validation.json")["metadata"]
    assert result["count"] == 408 and result["issue_count"] == 0
    assert result["reviewed_nonempty"] == 331
    assert result["status_counts"] == {"confirmed": 317, "existing_glossary": 1,
                                       "needs_context": 71, "needs_technical_fit": 19}


def test_official_name_67_exact_or_held():
    names = read(OUT / "ja_phase6_batch05_official_name_audit.json")
    reviewed = {x["id"]: x for x in read(OUT / "ja_phase6_batch05_reviewed.json")["entries"]}
    assert names["metadata"]["entry_count"] == names["metadata"]["observation_count"] == 67
    assert names["metadata"]["result_counts"] == {"verified_exact": 32, "ambiguous": 33, "not_found": 2}
    assert names["metadata"]["apply_impact_counts"] == {"applied": 10, "entry_held": 57}
    for row in names["entries"]:
        status = row["PokeAPI result"]["status"]
        if status not in {"verified_exact", "verified_difference"}:
            assert row["final Japanese"] is None
            assert not reviewed[row["entry_id"]]["final_apply"]
        if status in {"verified_exact", "verified_difference"}:
            assert row["final Japanese"] == row["PokeAPI result"]["ja-hrkt"]


def test_unknown_buffers_and_context_held():
    review, source, _ = inputs()
    result = {x["id"]: x for x in read(OUT / "ja_phase6_batch05_reviewed.json")["entries"]}
    unknown = [x for x in review if "unknown_buffer" in x["review_warning"]]
    assert len(unknown) == 68
    assert all(not result[x["id"]]["final_apply"] for x in unknown)
    context = [x for x in review if x["status"] == "needs_context"]
    assert len(context) == 71 and all(not result[x["id"]]["final_apply"] for x in context)


def test_technical_19_and_incomplete_six():
    reviewed = read(OUT / "ja_phase6_batch05_reviewed.json")
    assert reviewed["metadata"]["technical_fit_classes"] == {
        "FA_SEMANTIC_CONFLICT": 1, "STRUCTURED_CONSTRAINT": 12, "TRANSLATION_INCOMPLETE": 6}
    handoff = read(FIX / "ja_phase6_batch05_retranslation.json")
    assert handoff["metadata"]["count"] == 6
    assert all(x["no_codex_translation"] and x["failed_or_provisional_Japanese"] is None
               for x in handoff["entries"])
    ids = {x["id"] for x in handoff["entries"]}
    assert ids == {x["id"] for x in reviewed["entries"] if x["technical_class"] == "TRANSLATION_INCOMPLETE"}


def test_fa_four_control_order_twelve_segments_all_held():
    fa = read(OUT / "ja_phase6_batch05_fa_audit.json")
    assert fa["metadata"] == {"entries": 4, "controls": 4, "segments": 12, "applied": 0}
    assert sum(len(x["source_segments"]) for x in fa["entries"]) == 12
    assert all(x["source_boundary_sequence"].count("FA") == 1 and not x["apply"] for x in fa["entries"])


def test_width_warning_alone_does_not_hold_and_battle_geometry():
    reviewed = read(OUT / "ja_phase6_batch05_reviewed.json")
    assert reviewed["metadata"]["safe_application_count"] == 168
    assert reviewed["metadata"]["hold_count"] == 240
    assert sum(x["final_apply"] and x["category"] == "battle_messages" for x in reviewed["entries"]) == 21
    assert sum(x["final_apply"] and x["category"] != "battle_messages" for x in reviewed["entries"]) == 147
    assert all(x["width_result"]["runtime_unverified"] for x in reviewed["entries"])
    assert not any("width_runtime_unverified" in x["hold_reason"] for x in reviewed["entries"])
    rom = (ROOT / "rom/unbound.gba").read_bytes()
    assert battle_profiles(rom)["battle_message"].usable_width == 222
    extracted = read(ROOT / "out/unbound-texts.json")["entries"]
    species = maximum_table_width(extracted, rom, "pokemon_names")
    bounds = rom_naming_profiles(rom, species["max_width"])
    assert {key: row["safe_local_keyboard_width"] for key, row in bounds.items()} == {
        "pokemon_nickname": 60, "player_name": 42, "rival_name": 42}


def test_existing_glossary_scoped_and_candidates_not_merged():
    audit = read(OUT / "ja_phase6_batch05_glossary_audit.json")
    existing = audit["existing_glossary"]
    assert len(existing) == 1 and existing[0]["id"] == "tbl_setting_names_00004_1F4DB88"
    assert existing[0]["final_apply"]
    plan = {x["id"]: x for x in read(OUT / "ja_phase6_batch05_preliminary_plan.json")["entries"]}
    assert plan[existing[0]["id"]]["glossary"]["scope_valid"]
    assert len(audit["entries"]) == 4
    assert all(x["status"] == "proposal_only_not_approved" for x in audit["entries"])


def test_source_controls_exact_for_every_applied_entry():
    rom = (ROOT / "rom/unbound.gba").read_bytes()
    selected = {x["id"]: x for x in inputs()[2]}
    safe = read(OUT / "ja_phase6_batch05_safe_controlfix.json")["entries"]
    from lib.pcs_text import Charmap
    import runpy
    injector = runpy.run_path(str(ROOT / "005_hybrid_injector.py"))
    codec = Charmap("ja")
    for row in safe:
        source = selected[row["id"]]
        raw = rom[source["rom_offset"]:source["rom_offset"] + source["source_encoded_size"]]
        encoded = injector["encode_text"](codec, injector["translation_for_injection"](row), plain_script=False)
        assert control_sequence(raw) == control_sequence(encoded), row["id"]


def test_controlfix_idempotent_baseline_1549_preserved():
    baseline = read(OUT / "ja_phase6_batch04_controlfix.json")["entries"]
    combined = read(OUT / "ja_phase6_batch05_combined_controlfix.json")["entries"]
    assert len(baseline) == 1549 and len(combined) == 1717
    assert combined[:1549] == baseline
    assert (OUT / "ja_phase6_batch05_combined_controlfix.json").read_bytes() == (
        OUT / "ja_phase6_batch05_safe_controlfix_rebuilt.json").read_bytes()
    assert (OUT / "ja_phase6_batch05_combined_controlfix.json").read_bytes() == (
        OUT / "ja_phase6_batch05_controlfix_twice.json").read_bytes()
    report = read(OUT / "ja_phase6_batch05_controlfix_twice_report.json")["stats"]
    assert report["remaining_control_mismatches"] == report["fa_placement_review_required"] == 0


def test_incremental_strict_map_and_binary_audits():
    dry = read(OUT / "ja_phase6_batch05_incremental_dry_run_map.json")
    built = read(OUT / "ja_phase6_batch05_incremental_map.json")
    strict_map(dry, built, 168)
    assert (built["stats"]["in_place"], built["stats"]["relocated"],
            built["stats"]["pointer_writes"]) == (85, 83, 108)
    audit = read(OUT / "ja_phase6_batch05_incremental_audit.json")
    source = read(OUT / "ja_phase6_batch05_rom_audit.json")
    assert audit["existing_1549_unchanged"] and audit["unexpected_byte_count"] == 0
    assert audit["classified_changed_bytes"] == {"in_place_text": 1715, "relocated_text": 796,
                                                 "pointer_writes": 347}
    assert source["unexpected_byte_count"] == 0
    assert audit["candidate_sha256"] == source["output_sha256"]
    assert audit["candidate_sha256"] == __import__("hashlib").sha256(
        (ROOT / "out/unbound-ja-phase6-batch05.gba").read_bytes()).hexdigest()


def test_binary_auditor_rejects_unrelated_change(tmp_path):
    output = bytearray((ROOT / "out/unbound-ja-phase6-batch05.gba").read_bytes())
    output[0x1234] ^= 1
    bad = tmp_path / "bad.gba"
    bad.write_bytes(output)
    with pytest.raises(ValueError, match="Unexpected incremental ROM bytes"):
        incremental_audit(ROOT / "out/unbound-ja-phase6-batch04.gba", bad,
                          read(OUT / "ja_phase6_batch05_safe_controlfix.json")["entries"],
                          read(OUT / "ja_phase6_batch05_incremental_map.json"),
                          read(OUT / "ja_phase6_batch04_controlfix.json")["entries"],
                          read(OUT / "ja_phase6_batch04_map.json"))


def test_runtime_qa_and_batch06_source_only_handoff():
    qa = read(FIX / "ja_phase6_batch05_runtime_qa.json")
    assert qa["metadata"]["count"] == len(qa["entries"]) == 36
    assert all(x["runtime_result"] == "not_human_tested" for x in qa["entries"])
    style = read(OUT / "ja_phase6_batch06_style_handoff.json")
    assert style["applied_total"] == 1717 and style["batch06_source_count"] == 461
    assert style["batch06_fa_count"] == 0
    assert style["translation_status"] == "source_only_no_batch06_translation"
