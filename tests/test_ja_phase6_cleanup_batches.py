"""Phase 6C-4A: the 569-entry queue is split into four unmodified, deterministic batches."""

import json

import pytest

from lib.translation_glossary import load_glossary
from scripts.build_ja_phase6_cleanup_batches import (
    BATCH_FILES, BATCH_SIZE_RANGE, EXPECTED, GLOSSARY, HANDOFF_V3, MANIFEST, PHASE, PROFILES, PROTECTED,
    ROOT, SELECTION, STYLE_HANDOFF, build, guarded_write, read, sha256, split_batches, validate_input,
    validate_outputs,
)


@pytest.fixture(scope="module")
def data():
    source = read(HANDOFF_V3)["entries"]
    return {"source": {e["id"]: e for e in source}, "entries": source,
            "batches": [read(p) for p in BATCH_FILES], "manifest": read(MANIFEST),
            "style": read(STYLE_HANDOFF), "profiles": {p["speaker_id"]: p for p in read(PROFILES)["profiles"]}}


def test_input_569_is_clean_and_not_contaminated(data):
    report = validate_input(data["entries"])
    assert report["ok"] and report["entries"] == report["unique"] == 569 and report["duplicates"] == 0
    assert report["classes"] == {"CLAUDE_TRANSLATION": 302, "CLAUDE_CONTEXT": 267}
    assert not report["already_in_applied_json"] and not report["inventory_not_held"]
    assert not any(report["slot_differs_from_source_rom"].values()), "held slots must still equal the source ROM"


def test_each_id_assigned_exactly_once_with_sane_sizes(data):
    ids = [e["id"] for b in data["batches"] for e in b["entries"]]
    assert sorted(ids) == sorted(data["source"]) and len(ids) == len(set(ids)) == 569
    sizes = [len(b["entries"]) for b in data["batches"]]
    assert sizes == [147, 142, 140, 140]
    assert all(BATCH_SIZE_RANGE[0] <= n <= BATCH_SIZE_RANGE[1] for n in sizes)
    assert [b["metadata"]["entries"] for b in data["batches"]] == sizes
    assert validate_outputs()["problems"] == []


def test_batch1_is_exactly_the_non_dialogue_rows_and_dialogue_follows(data):
    first, rest = data["batches"][0]["entries"], [e for b in data["batches"][1:] for e in b["entries"]]
    assert all(e["speaker_category"] == "NON_DIALOGUE" for e in first) and len(first) == 147
    assert all(e["speaker_category"] != "NON_DIALOGUE" and e["category"] == "scripts" for e in rest)


def test_proven_speaker_groups_and_conversations_are_not_split(data):
    placement = {}
    for b in data["batches"]:
        for e in b["entries"]:
            if e["dialogue_group_id"]:
                placement.setdefault(e["dialogue_group_id"], set()).add(b["metadata"]["batch"])
    assert len(placement) == 9 and all(len(v) == 1 for v in placement.values())
    conv = {}
    for b in data["batches"][1:]:
        for e in b["entries"]:
            conv.setdefault(e["preserved_metadata"]["conversation_id"], set()).add(b["metadata"]["batch"])
    assert all(len(v) == 1 for v in conv.values())
    assert data["manifest"]["metadata"]["proven_group_batches"] == {k: sorted(v) for k, v in placement.items()}


def test_original_fields_unchanged_and_no_translation_added(data):
    for b in data["batches"]:
        for e in b["entries"]:
            original = data["source"][e["id"]]
            assert all(e[k] == v for k, v in original.items()), e["id"]
            assert e["previous_japanese_candidate"] == original["candidate"]
            assert e["original"] == original["original"] == e["original_english"]
            assert "reviewed_japanese" not in e and e["resolution_class"] == original["resolution_class"]
        assert b["metadata"]["no_new_translation_generated"] is True


def test_controls_tokens_and_fa_units_match_the_source(data):
    selection = {x["id"]: x for x in read(SELECTION)["entries"]}
    fa_total = 0
    for b in data["batches"]:
        for e in b["entries"]:
            structure = e["source_control_structure"]
            assert structure["controls"] == e["controls"] and structure["parse_error"] is None
            assert e["protected_tokens"] == selection[e["id"]]["protected_tokens"]
            boundaries = structure["boundary_sequence"]
            assert boundaries.count("FA") == e["controls"].get("FA", 0)
            if e["controls"].get("FA"):
                fa_total += 1
                units = e["translation_units"]
                assert len(units) == len(structure["display_segments"]) == len(boundaries) + 1
                assert e["fa_placement_policy"] == "require_segments"
            else:
                assert "translation_units" not in e
            assert [s["after_control"] for s in structure["display_segments"] if s["after_control"]] == boundaries
    assert fa_total == 206 == sum(b["metadata"]["fa_entries"] for b in data["batches"])


def test_voice_attachment_never_promotes_identity(data):
    for b in data["batches"]:
        for e in b["entries"]:
            original = data["source"][e["id"]]
            assert e["speaker_confidence"] == original["speaker_confidence"]
            assert e["official_character_proven"] is False and e["canon_character_candidate"] is None
            mode = e["voice_application"]
            if e["speaker_category"] == "NON_DIALOGUE":
                assert mode == "not_applicable_non_dialogue" and e["voice_profile"] is None
            elif e["speaker_confidence"] == "PLAUSIBLE":
                assert mode == "plausible_tendency_reference_only" and e["speaker_id"] is None
                assert e["plausible_tendency"]
            elif e["speaker_confidence"] == "UNKNOWN":
                assert mode == "unknown_speaker_neutral_with_register" and e["voice_profile"] is None
                assert e["speaker_id"] is None
            else:
                profile = data["profiles"].get(e["speaker_id"])
                if profile:
                    assert e["voice_profile"]["voice_status"] == profile["voice_status"]
                    assert e["voice_profile"]["identity_confidence"] == "PROVEN"
                    assert profile["voice_status"] != "CONFIRMED_VOICE" or mode == "enforce_approved_profile"
                    if profile["voice_status"] == "PROVISIONAL_VOICE":
                        assert mode == "reference_only_do_not_force"
                else:
                    assert mode == "neutral_no_profile"


def test_glossary_scope_and_unresolved_warnings_are_preserved(data):
    glossary = load_glossary(GLOSSARY, expected_language="ja")
    phase_terms = glossary.terms[139:]
    assert len(glossary.terms) == 292 and all(t.global_replace is False for t in phase_terms)
    for b in data["batches"]:
        for e in b["entries"]:
            original = data["source"][e["id"]]["glossary"]
            assert [x["term"] for x in e["approved_glossary_terms"]] == [x["term"] for x in original["approved_terms"]]
            assert e["unresolved_glossary_warnings"] == original["unresolved_warnings"]
            for term in e["approved_glossary_terms"]:
                for scope in term["glossary_scope"]:
                    if "global_replace" in scope and scope["entry_ids"]:
                        assert scope["global_replace"] is False and e["id"] in scope["entry_ids"]
            for hit in e["glossary_matcher_hits"]:
                assert any(t.source == hit["source"] and t.target == hit["target"] for t in glossary.terms)
    assert data["style"]["glossary_rules"] and data["style"]["official_character_rule"]


def test_unresolved_context_is_not_auto_resolved(data):
    held = [e for b in data["batches"] for e in b["entries"] if e["resolution_class"] == "CLAUDE_CONTEXT"]
    assert len(held) == 267
    assert all(e["claude_task"]["allowed_outcomes"] == ["confirmed", "needs_context", "needs_technical_fit"] for e in held)
    assert all(e["current_hold_reason"]["exact_reason"] == data["source"][e["id"]]["exact_reason"] for e in held)


def test_style_handoff_contract(data):
    style = data["style"]
    assert style["metadata"]["batch_sizes"] == [147, 142, 140, 140]
    assert "ヴ" in style["charmap_probe"]["unsupported"] and "、" in style["charmap_probe"]["supported"]
    assert style["output_contract"]["status_values"] == ["confirmed", "needs_context", "needs_technical_fit"]
    assert "Codex" in " ".join(style["language_rules"])


def test_deterministic_rebuild_and_overwrite_guard(data, tmp_path):
    targets = [*BATCH_FILES, STYLE_HANDOFF, MANIFEST]
    before = {p.name: sha256(p) for p in targets}
    protected_before = {p.name: sha256(p) for p in PROTECTED}
    build()
    assert {p.name: sha256(p) for p in targets} == before, "a rebuild must be byte-identical"
    assert {p.name: sha256(p) for p in PROTECTED} == protected_before
    first, _ = split_batches(data["entries"])
    second, _ = split_batches(list(reversed(data["entries"])))
    assert [[e["id"] for e in b] for b in first] == [[e["id"] for e in b] for b in second]
    foreign = tmp_path / "foreign.json"
    foreign.write_text(json.dumps({"metadata": {"phase": "6C-3C"}}), encoding="utf-8")
    with pytest.raises(FileExistsError):
        guarded_write(foreign, {"metadata": {"phase": PHASE}})
    plain = tmp_path / "plain.txt"
    plain.write_text("not json", encoding="utf-8")
    with pytest.raises(FileExistsError):
        guarded_write(plain, {"metadata": {"phase": PHASE}})
    mine = tmp_path / "mine.json"
    guarded_write(mine, {"metadata": {"phase": PHASE}})
    guarded_write(mine, {"metadata": {"phase": PHASE, "again": True}})


def test_manifest_records_inputs_and_protected_files(data):
    meta = data["manifest"]["metadata"]
    assert meta["total_entries"] == 569 and meta["batch_sizes"] == [147, 142, 140, 140]
    assert meta["input_validation"]["ok"] is True
    for path in PROTECTED:
        assert path.exists()
        assert meta["protected_files_sha256"][str(path.relative_to(ROOT)).replace("\\", "/")] == sha256(path)
    assert [b["entries"] for b in data["manifest"]["batches"]] == [147, 142, 140, 140]
