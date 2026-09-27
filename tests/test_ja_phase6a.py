"""Phase 6A selection is reproducible, bounded, and safe for Claude handoff."""

import json
from collections import Counter, defaultdict
from pathlib import Path

import pytest

from lib.pcs_text import Charmap
from lib.translation_glossary import load_glossary
from lib.translation_tokens import semantic_tokens, strip_hma_quotes
from scripts.build_ja_phase6a import (
    BATCH_COUNT, BATCH_MAX, BATCH_MIN, QA_SIZE, approved_value,
    cached_localizer, make_handoff, partition, validate,
)

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = json.loads((ROOT / "tests/fixtures/ja_phase6_selection.json").read_text(encoding="utf-8"))
QA = json.loads((ROOT / "tests/fixtures/ja_phase6_runtime_candidates.json").read_text(encoding="utf-8"))
ROWS = MANIFEST["entries"]
BY_ID = {row["id"]: row for row in ROWS}


def test_selection_unique_and_phase5_exclusions():
    assert len(ROWS) == MANIFEST["metadata"]["entry_count"] == 2500
    assert len(BY_ID) == len(ROWS)
    assert len({row["rom_offset"] for row in ROWS}) == len(ROWS)
    applied = json.loads((ROOT / "out/ja-phase5f-final-controlfix.json").read_text(encoding="utf-8"))
    applied_ids = {row["id"] for row in applied["entries"]}
    held_ids = {row["id"] for row in MANIFEST["excluded_phase5_unresolved"]}
    assert len(applied_ids) == 677
    assert len(held_ids) == 43
    assert not BY_ID.keys() & applied_ids
    assert not BY_ID.keys() & held_ids
    assert all(row["phase5_unresolved"] for row in MANIFEST["excluded_phase5_unresolved"])
    assert all(not row["already_translated"] and not row["phase5_unresolved"] for row in ROWS)
    assert not held_ids & {item["id"] for row in ROWS
                           for item in row["context_before"] + row["context_after"]}


def test_runtime_confidence_owner_and_legacy_filter():
    assert {row["runtime_confidence"] for row in ROWS} <= {"A", "B"}
    assert all(row["runtime_evidence"] for row in ROWS)
    assert sum(row["renderer_group"] == "unknown" for row in ROWS) <= 10
    assert all("legacy" not in (row["table_name"] or "").casefold() for row in ROWS)
    for row in ROWS:
        assert row["gba_address"] == f"0x{0x08000000 + row['rom_offset']:08X}"
        assert row["slot_size"] >= row["source_encoded_size"] > 0
        assert row["pointer_owners"] or row["table_name"]
        assert row["speaker"] == row["speaker_confidence"] == "unknown"


def test_batch_partition_complete_unique_and_groups_preserved():
    batches = [[row for row in ROWS if row["batch_number"] == index]
               for index in range(1, BATCH_COUNT + 1)]
    assert all(BATCH_MIN <= len(batch) <= BATCH_MAX for batch in batches)
    all_ids = [row["id"] for batch in batches for row in batch]
    assert len(all_ids) == len(set(all_ids)) == len(ROWS)
    assert set(all_ids) == BY_ID.keys()
    group_batches = defaultdict(set)
    for number, batch in enumerate(batches, 1):
        for row in batch:
            if row["conversation_id"]:
                group_batches[row["conversation_id"]].add(number)
    assert all(len(numbers) == 1 for numbers in group_batches.values())
    validate(ROWS, batches, set(), set(), QA)


def test_handoff_files_match_manifest_and_preserve_metadata():
    partitioned = partition(ROWS)
    for number in range(1, BATCH_COUNT + 1):
        batch = partitioned[number - 1]
        expected = make_handoff(batch, number)
        path = ROOT / f"out/phase6/ja_phase6_batch{number:02d}_for_claude.json"
        if path.exists():
            assert json.loads(path.read_text(encoding="utf-8")) == expected
        for item in expected["entries"]:
            source = BY_ID[item["id"]]
            assert item["original"] == source["original"]
            assert item["controls"] == source["controls"]
            assert item["buffers"] == source["buffers"]
            assert Counter(item["protected_tokens"]) == Counter(source["protected_tokens"])
            assert item["placeholders"] == source["placeholders"]


def test_protected_tokens_and_page_controls_are_lossless():
    assert any(row["controls"].get("FE") for row in ROWS)
    assert any(row["controls"].get("FA") for row in ROWS)
    assert any(row["controls"].get("FB") for row in ROWS)
    assert any(row["controls"].get("FC") for row in ROWS)
    assert any(row["controls"].get("FD") for row in ROWS)
    for row in ROWS:
        assert Counter(row["protected_tokens"]) == Counter(semantic_tokens(strip_hma_quotes(row["original"])))
        assert all(p["token"] in row["protected_tokens"] for p in row["placeholders"])
        assert row["context_confidence"] in {"medium", "none"}
        assert all(item["confidence"] == "medium" for item in row["context_before"] + row["context_after"])


def test_glossary_scope_and_deterministic_values():
    glossary = load_glossary(ROOT / "glossaries/ja.json", expected_language="ja")
    codec = Charmap(target_lang="ja")
    localizer = cached_localizer()
    prepared = json.loads((ROOT / "out/ja-phase5e-prepared.json").read_text(encoding="utf-8"))
    source_by_id = {row["id"]: row for row in prepared["entries"]}
    for row in ROWS:
        _, details, official, status, deterministic, origin = approved_value(
            source_by_id[row["id"]], glossary, localizer, codec
        )
        # Phase 6B-1 narrowed Ace to its actual person-name entry. Keep the
        # historical selection fixture intact, but reject its four stale
        # Aerial Ace substring matches when comparing live glossary results.
        historical = row["glossary_term_details"]
        if row["id"] in {"scr_75C267", "scr_1F317D8", "scr_1F341A9", "scr_1F172DD"}:
            historical = [item for item in historical if item["source"] != "Ace"]
        assert details == historical
        assert official == row["official_terms"]
        assert status == row["official_status"]
        assert deterministic == row["deterministic_translation"]
        assert origin == row["deterministic_origin"]
        if deterministic:
            assert len(codec.encode(f"[japanese]{deterministic}[latin]")) == row["deterministic_encoded_size"]
    assert any(row["glossary_terms"] for row in ROWS)
    assert any(row["deterministic_origin"] == "glossary-exact" for row in ROWS)


def test_sensitive_glossary_terms_not_globalized():
    glossary = load_glossary(ROOT / "glossaries/ja.json", expected_language="ja")
    for term in ("Difficult", "Hard", "Log", "Cube", "The Shadows"):
        assert not glossary.matches(f"The {term} appears here", "scripts", entry_id="unrelated")
    assert not glossary.matches("Route 7", "scripts", entry_id="unrelated")
    assert glossary.matches("Route 7", "map_names", entry_id="unrelated")
    assert not glossary.matches("New Game \\+", "scripts", entry_id="unrelated")


def test_pokeapi_metadata_verified_kana_only():
    codec = Charmap(target_lang="ja")
    verified = [row for row in ROWS if row["official_status"] == "verified_cached_ja-hrkt"]
    assert verified
    for row in verified:
        assert row["official_terms"]
        assert row["deterministic_origin"] == "pokeapi-ja-hrkt"
        assert all(codec.encode(f"[japanese]{value}[latin]")
                   for value in row["official_terms"].values())
    assert all(not row["official_terms"] for row in ROWS if row["official_status"] == "unverified")


def test_fixed_no_relocation_and_qa_subset():
    assert len(QA["entries"]) == QA["metadata"]["entry_count"] == QA_SIZE
    assert {row["id"] for row in QA["entries"]} <= BY_ID.keys()
    assert all(row["fixed"] == (not row["relocation_possible"]) for row in ROWS)
    assert all(row["fixed"] for row in ROWS if row["no_relocation"])
    assert any(row["requires_fit_review"] for row in ROWS)
    assert all(row["deterministic_encoded_size"] > row["slot_size"]
               for row in ROWS if row["requires_fit_review"])


def test_validation_rejects_duplicates_and_phase5_leak():
    with pytest.raises(ValueError, match="Duplicate"):
        validate(ROWS + [ROWS[0]], [ROWS + [ROWS[0]]], set(), set(), QA)
    with pytest.raises(ValueError, match="Phase 5"):
        validate(ROWS, [ROWS], {ROWS[0]["id"]}, set(), QA)
