"""Phase 6C-3B voice-profile review: accounting, identity, control and kana safety."""

import json
import re

import pytest

from lib.pcs_text import Charmap
from lib.translation_glossary import load_glossary
from lib.translation_tokens import semantic_tokens
from scripts.build_ja_phase6_voice_review import (
    COMBINED, HAN, PROFILES, REWRITES, STATUSES, VOICE_INPUT, clean, read, tokens,
)


@pytest.fixture(scope="module")
def data():
    return {"input": read(VOICE_INPUT)["groups"], "profiles": read(PROFILES),
            "rewrites": read(REWRITES), "combined": {x["id"]: x for x in read(COMBINED)["entries"]}}


def test_group_and_entry_accounting(data):
    groups, profiles = data["input"], data["profiles"]["profiles"]
    assert len(groups) == len(profiles) == 56
    assert [g["speaker_id"] for g in groups] == [p["speaker_id"] for p in profiles]
    expected = [d["id"] for g in groups for d in g["dialogue"]]
    assert len(expected) == len(set(expected)) == 120
    rewrites = data["rewrites"]
    reviewed = ([c["entry_id"] for c in rewrites["candidates"]] + [u["entry_id"] for u in rewrites["unchanged"]]
                + [h["entry_id"] for h in rewrites["held_untranslated"]])
    assert sorted(reviewed) == sorted(expected)
    assert rewrites["metadata"]["reviewed_entries"] == 120
    for group, profile in zip(groups, profiles):
        assert profile["evidence_entry_ids"] == group["dialogue_ids"]
        assert len(profile["trainer_ids"]) == 1, "one profile must never merge two trainer IDs"


def test_identity_is_never_promoted(data):
    for group, profile in zip(data["input"], data["profiles"]["profiles"]):
        assert profile["identity_confidence"] == group["confidence"] == "PROVEN"
        assert profile["canon_identity"] == {"status": "NOT_ESTABLISHED", "official_character_proven": False}
        assert profile["source_game"] == (group["source_game"] or {"game": None, "confidence": "UNKNOWN"})
        assert profile["original_japanese_voice_reference"] == {"status": "not_collected", "applied": False}
    meta = data["profiles"]["metadata"]
    assert meta["official_character_voice_applied"] == 0 and meta["proven_canon_characters"] == 0
    assert meta["official_voice_reference"] == "not_collected"


def test_voice_status_rules(data):
    profiles = data["profiles"]["profiles"]
    assert {p["voice_status"] for p in profiles} <= STATUSES
    counts = data["profiles"]["metadata"]["voice_status_counts"]
    assert sum(counts.values()) == 56
    for p in profiles:
        if p["voice_status"] == "CONFIRMED_VOICE":
            assert len(p["evidence_entry_ids"]) >= 3 and not p["untranslated_entry_ids"]
        # No first/second person or gender is ever hard-assigned without evidence.
        assert p["first_person"]["value"] is None and p["second_person"]["value"] is None
        assert p["prohibited_assumptions"] and p["personality_traits"] is not None
        assert not HAN.search(json.dumps(p["speech_examples_short"], ensure_ascii=False))
    named = {p["character_name"]: p for p in profiles}
    assert named["Marlon"]["source_game"]["confidence"] == "PLAUSIBLE"
    assert named["Ivory"]["voice_status"] == "PROVISIONAL_VOICE"
    assert any("同名" in x or "名前一致" in x for x in named["Lucas"]["prohibited_assumptions"])


def test_plausible_and_unknown_pools_are_not_promoted(data):
    pool = data["profiles"]["plausible_pool"]["entries"]
    assert len(pool) == 38
    assert all(x["identity_confidence"] == "PLAUSIBLE" and x["applies_to_other_entries"] is False for x in pool)
    assert all(x["voice_status"] in {"PROVISIONAL_VOICE", "NEUTRAL_ONLY"} for x in pool)
    unknown = data["profiles"]["unknown_pool"]
    assert unknown["dialogue_candidates"] == 372 and unknown["non_dialogue"] == 147


def test_rewrite_candidates_preserve_controls_meaning_and_kana(data):
    codec = Charmap("ja")
    glossary = load_glossary(__import__("pathlib").Path(__file__).resolve().parents[1] / "glossaries/ja.json",
                             expected_language="ja")
    targets = [t.target for t in glossary.terms if len(t.target) >= 3]
    originals = {d["id"]: d for g in data["input"] for d in g["dialogue"]}
    assert len(data["rewrites"]["candidates"]) == 4
    for item in data["rewrites"]["candidates"]:
        key = item["entry_id"]
        current, proposed = item["current_japanese"], item["proposed_japanese"]
        assert current == data["combined"][key]["translated"], "current translation must be the applied text"
        assert item["original_english"] == originals[key]["original"]
        assert current != proposed
        assert tokens(current) == tokens(proposed)
        assert semantic_tokens(current) == semantic_tokens(proposed)
        assert current.count("\n") == proposed.count("\n")
        assert not HAN.search(proposed)
        codec.encode(proposed)
        cv = item["control_validation"]
        assert cv["control_token_sequence_equal"] and cv["protected_tokens_equal"] and cv["within_240px"]
        assert item["charmap_validation"] == {"encodes_in_japanese_charmap": True, "kanji_free": True}
        assert item["requires_technical_review"] == (not cv["fits_source_slot"])
        assert item["speaker_confidence"] == "PROVEN" and item["reason"] and item["change_risk"]
        # Approved glossary terms present in the current text must survive unchanged.
        for target in targets:
            if target in clean(current):
                assert target in clean(proposed), (key, target)


def test_unchanged_and_held_entries_have_no_rewrite(data):
    rewrites = data["rewrites"]
    changed = {c["entry_id"] for c in rewrites["candidates"]}
    assert not changed & {u["entry_id"] for u in rewrites["unchanged"]}
    assert len(rewrites["held_untranslated"]) == 8
    for held in rewrites["held_untranslated"]:
        assert held["entry_id"] not in data["combined"], "held entries have no applied Japanese"
    assert rewrites["metadata"]["applied_to_translation_json"] is False


def test_phase_does_not_touch_translation_inputs(data):
    # The applied text for every reviewed entry is still present and unmodified in the combined JSON.
    for g in data["input"]:
        for d in g["dialogue"]:
            if d["current_japanese"]:
                assert data["combined"][d["id"]]["translated"] == d["current_japanese"]
