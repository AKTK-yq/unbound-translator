"""Phase 5A selection stays lossless, bounded, and translation-safe."""

from collections import Counter
import json
from pathlib import Path
import subprocess

import pytest

from lib.pcs_text import Charmap
from lib.translation_glossary import load_glossary
from lib.translation_tokens import semantic_tokens, strip_hma_quotes
from scripts.build_ja_phase5_dataset import glossary_candidates, make_handoff, validate_manifest


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = json.loads((ROOT / "tests/fixtures/ja_phase5_selection.json").read_text(encoding="utf-8"))
SUBSET = json.loads((ROOT / "tests/fixtures/ja_phase5_runtime_subset.json").read_text(encoding="utf-8"))
HANDOFF_PATH = ROOT / "out/ja_phase5_for_claude.json"
CAPACITY_PATH = ROOT / "out/ja_phase5_capacity.json"
COVERAGE_PATH = ROOT / "out/ja_phase5_coverage.json"


def test_manifest_parse_count_unique_ids_addresses_and_confidence():
    rows = MANIFEST["entries"]
    assert 500 <= len(rows) <= 1000
    assert MANIFEST["metadata"]["entry_count"] == len(rows)
    assert len({row["id"] for row in rows}) == len(rows)
    assert len({row["rom_offset"] for row in rows}) == len(rows)
    assert len({row["category"] for row in rows}) == 55
    assert {row["runtime_confidence"] for row in rows} <= set("ABCD")
    assert all(row["runtime_reason"] and row["pointer_owners"] is not None for row in rows)
    validate_manifest(rows)


def test_duplicate_address_and_invalid_confidence_rejected():
    row = dict(MANIFEST["entries"][0])
    other = dict(MANIFEST["entries"][1])
    other["rom_offset"] = row["rom_offset"]
    other["gba_address"] = row["gba_address"]
    with pytest.raises(ValueError, match="Duplicate Phase 5A ROM offsets"):
        validate_manifest([row, other])
    row["runtime_confidence"] = "Z"
    with pytest.raises(ValueError, match="Invalid runtime confidence"):
        validate_manifest([row])


def test_handoff_preserves_protected_tokens_and_does_not_invent_speakers():
    manifest = {row["id"]: row for row in MANIFEST["entries"]}
    generated = json.loads(json.dumps(make_handoff(MANIFEST["entries"]), ensure_ascii=False))
    if HANDOFF_PATH.exists():
        saved = json.loads(HANDOFF_PATH.read_text(encoding="utf-8"))
        assert generated == saved["entries"]
    handoff = {row["id"]: row for row in generated}
    assert manifest.keys() == handoff.keys()
    for entry_id, row in handoff.items():
        source = manifest[entry_id]
        assert row["original"] == source["original"]
        assert row["translation_source"] == source["translation_source"]
        assert Counter(row["protected_tokens"]) == Counter(semantic_tokens(strip_hma_quotes(row["original"])))
        assert row["semantic_token_placeholders"] == source["placeholders"]
        assert row["speaker"] == "unknown"
        assert row["speaker_confidence"] == "unknown"
        assert row["context_basis"].endswith("unproven")


def test_pokeapi_metadata_is_verified_kana_only_and_unverified_has_no_value():
    codec = Charmap(target_lang="ja")
    rows = MANIFEST["entries"]
    verified = [row for row in rows if row["official_status"] == "verified"]
    assert len(verified) > 0
    for row in verified:
        assert row["official_source"].startswith("PokeAPI v2 ja-hrkt")
        assert row["approved_origin"] == "pokeapi-ja-hrkt"
        assert row["approved_translation"] == row["official_translation"]
        assert codec.encode(f"[japanese]{row['official_translation']}[latin]")
    for row in rows:
        if row["official_status"] == "unverified":
            assert row["official_translation"] is None


def test_no_new_prose_translation_and_glossary_candidates_are_unapproved():
    approved = {"phase4-reviewed", "phase4-glossary", "pokeapi-ja-hrkt", None}
    codec = Charmap(target_lang="ja")
    assert {row["approved_origin"] for row in MANIFEST["entries"]} <= approved
    for row in MANIFEST["entries"]:
        if row["approved_origin"] is None:
            assert row["approved_translation"] is None
        else:
            assert codec.encode(f"[japanese]{row['approved_translation']}[latin]")
    glossary = load_glossary(ROOT / "glossaries/ja.json", expected_language="ja")
    candidates = glossary_candidates(MANIFEST["entries"], glossary)
    assert candidates
    assert all(row["status"] == "glossary_candidate" and row["target"] is None for row in candidates)
    assert any(row["source"] == "Bellin Town" for row in candidates)


def test_runtime_subset_is_main_set_subset_with_broad_coverage():
    ids = {row["id"] for row in MANIFEST["entries"]}
    subset = SUBSET["entries"]
    assert 50 <= len(subset) <= 100
    assert SUBSET["metadata"]["entry_count"] == len(subset)
    assert {row["id"] for row in subset} <= ids
    assert len({row["id"] for row in subset}) == len(subset)
    assert {row["category"] for row in subset} >= {"scripts", "battle_messages", "mission_log", "menu_options"}


def test_capacity_and_coverage_reports_reconcile_to_manifest():
    rows = MANIFEST["entries"]
    if not CAPACITY_PATH.exists() or not COVERAGE_PATH.exists():
        pytest.skip("Ignored local analysis reports are not present")
    coverage = json.loads(COVERAGE_PATH.read_text(encoding="utf-8"))
    capacity = json.loads(CAPACITY_PATH.read_text(encoding="utf-8"))
    assert sum(coverage["category_counts"].values()) == len(rows)
    assert sum(coverage["runtime_confidence"].values()) == len(rows)
    assert capacity["available_vetted_ff_shared_bytes"] > 0
    assert sum(category["total_entries"] for category in capacity["category_counts"].values()) == len(rows)
    assert all(value["phase4_size_factor"] > 0 for value in capacity["scenarios"].values())


def test_private_rom_and_save_paths_are_git_ignored():
    result = subprocess.run(
        ["git", "check-ignore", "--no-index", "rom/unbound.gba", "out/ja-phase5-test.gba", "out/ja-phase5-test.sav"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    )
    assert set(result.stdout.splitlines()) == {
        "rom/unbound.gba", "out/ja-phase5-test.gba", "out/ja-phase5-test.sav",
    }
