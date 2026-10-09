"""Phase 6C-3A: evidence-limited speaker metadata, never wording changes."""

from collections import Counter
import hashlib

import pytest

from scripts.build_ja_phase6_speaker_attribution import (
    OUT, ROOT, attribute, gba_pointer, read, scan_map_objects, trainer_record,
)


@pytest.fixture(scope="module")
def records():
    names = (
        "ja_phase6_cleanup_translation_handoff_v2.json",
        "ja_phase6_cleanup_translation_handoff_v3.json",
        "ja_phase6_speaker_attribution.json",
        "ja_phase6_canon_character_candidates.json",
        "ja_phase6_voice_review_for_claude.json",
        "ja_phase6_cleanup_glossary_combined_controlfix.json",
    )
    return {name: read(OUT / name) for name in names}


def test_handoff_keeps_all_569_entries_and_all_original_fields(records):
    old = records["ja_phase6_cleanup_translation_handoff_v2.json"]["entries"]
    new = records["ja_phase6_cleanup_translation_handoff_v3.json"]["entries"]
    assert len(old) == len(new) == 569
    assert len({row["id"] for row in new}) == 569
    assert [row["id"] for row in old] == [row["id"] for row in new]
    assert Counter(row["resolution_class"] for row in new) == {
        "CLAUDE_CONTEXT": 267, "CLAUDE_TRANSLATION": 302}
    for before, after in zip(old, new):
        assert {key: after[key] for key in before} == before
        assert set(after) - set(before) == {
            "speaker_id", "speaker_category", "speaker_confidence", "speaker_evidence",
            "canon_character_candidate", "source_game_candidate", "dialogue_group_id",
            "voice_review_required"}


def test_attribution_count_and_non_dialogue_boundary(records):
    rows = records["ja_phase6_speaker_attribution.json"]["entries"]
    assert len(rows) == 569
    assert Counter(row["speaker_confidence"] for row in rows) == {
        "PROVEN": 12, "PLAUSIBLE": 38, "UNKNOWN": 519}
    assert Counter(row["speaker_category"] for row in rows) == {
        "GENERIC_NPC": 2, "TRAINER_CLASS": 10,
        "UNKNOWN_SPEAKER": 410, "NON_DIALOGUE": 147}
    assert all(not row["voice_review_required"] and row["speaker_id"] is None
               for row in rows if row["speaker_category"] == "NON_DIALOGUE")
    assert all(row["speaker_id"] and row["speaker_evidence"]
               for row in rows if row["speaker_confidence"] == "PROVEN")
    assert all(row["speaker_id"] is None and row["dialogue_group_id"] is None
               for row in rows if row["speaker_confidence"] != "PROVEN")


def test_proven_owners_really_point_to_text_and_have_structural_evidence(records):
    rom = (ROOT / "rom/unbound.gba").read_bytes()
    assert hashlib.md5(rom).hexdigest() == "9cad8e771940e7f7094d13911552cef0"
    old = {row["id"]: row for row in
           records["ja_phase6_cleanup_translation_handoff_v2.json"]["entries"]}
    proven = [row for row in records["ja_phase6_speaker_attribution.json"]["entries"]
              if row["speaker_confidence"] == "PROVEN"]
    for row in proven:
        target = old[row["id"]]["preserved_metadata"]["rom_offset"]
        for evidence in row["speaker_evidence"]:
            owner = int(evidence["text_operand_offset"], 16)
            assert gba_pointer(rom, owner) == target
            if evidence["kind"] == "trainerbattle_text_operand":
                assert rom[int(evidence["opcode_offset"], 16)] == 0x5C
                assert trainer_record(rom, evidence["trainer_id"])["trainer_name"] == evidence["trainer_name"]
            elif evidence["kind"] == "direct_object_message":
                assert rom[owner - 2:owner] == b"\x0f\x00"
                assert rom[owner + 4:owner + 6] in {b"\x09\x02", b"\x09\x06"}
            else:
                pytest.fail(f"Unrecognized proof: {evidence['kind']}")


def test_proximity_and_name_only_never_become_identity(records):
    rows = records["ja_phase6_speaker_attribution.json"]["entries"]
    assert all(row["speaker_id"] is None for row in rows
               if row["speaker_confidence"] == "PLAUSIBLE")
    assert all(not row["name_mentions_are_identity_evidence"] for row in rows)
    canon = records["ja_phase6_canon_character_candidates.json"]
    assert canon["metadata"]["proven_canon"] == 0
    assert canon["candidates"] == []
    assert {row["trainer_name"] for row in canon["rejected_name_only_matches"]} == {"Lucas", "Barry"}
    assert all(row["status"] == "rejected_name_only_match"
               for row in canon["rejected_name_only_matches"])
    assert canon["source_game_counts"] == {}


def test_speaker_groups_use_exact_trainer_or_map_object_id(records):
    report = records["ja_phase6_speaker_attribution.json"]
    groups = report["speaker_groups"]
    assert len(groups) == 91
    assert len({g["speaker_id"] for g in groups}) == len(groups)
    assert len(report["applied_candidates"]) == 143
    assert len(records["ja_phase6_cleanup_glossary_combined_controlfix.json"]["entries"]) == 2261
    for group in groups:
        assert group["confidence"] == "PROVEN"
        assert group["speaker_id"].startswith(("trainer_", "object_"))
        assert len(group["dialogue_ids"]) == len(set(group["dialogue_ids"]))
        assert {e["id"] for e in group["dialogue"]} == set(group["dialogue_ids"])
        for entry in group["dialogue"]:
            for proof in entry["speaker_evidence"]:
                if group["speaker_id"].startswith("trainer_"):
                    assert proof["trainer_id"] == int(group["speaker_id"].split("_")[1])
                else:
                    assert (proof["map_header_offset"], proof["local_object_id"]) == (
                        f"0x{group['speaker_id'].split('_')[1]}",
                        int(group["speaker_id"].split("_")[2]))


def test_voice_review_is_subset_without_new_wording(records):
    groups = {g["speaker_id"]: g for g in
              records["ja_phase6_speaker_attribution.json"]["speaker_groups"]}
    voice = records["ja_phase6_voice_review_for_claude.json"]
    assert voice["metadata"]["speaker_groups"] == len(voice["groups"]) == 56
    assert voice["metadata"]["unique_entry_ids"] == 120
    assert voice["metadata"]["new_translation_generated"] is False
    for group in voice["groups"]:
        assert group == groups[group["speaker_id"]]
        assert (group["character_category"] == "UNBOUND_ORIGINAL"
                or len(group["dialogue_ids"]) >= 2)
        assert group["original_japanese_voice_reference_status"] == "not_collected"
        assert all("not_voice_decision" in item["status"] or item["status"] ==
                   "absence_of_marker_not_character_trait" for item in group["style_evidence"])


def test_known_direct_object_binding_and_shared_trainer_text_not_merged(records):
    rom = (ROOT / "rom/unbound.gba").read_bytes()
    objects, counts = scan_map_objects(rom)
    assert counts["object_script_bindings"] >= 790
    by_id = {row["id"]: row for row in
             records["ja_phase6_cleanup_translation_handoff_v2.json"]["entries"]}
    npc = attribute(rom, objects, by_id["scr_1F09A3C"])
    assert npc["speaker_id"] == "object_003516F0_003"
    shared = attribute(rom, objects, by_id["scr_1F33CAE"])
    assert shared["speaker_confidence"] != "PROVEN"
    assert shared["speaker_id"] is None
    assert {332, 333, 334} <= set(shared["speaker_evidence"][0]["ids"])
