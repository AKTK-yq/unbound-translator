"""Phase 6 Batch 06 fail-closed technical-integration regression checks."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from lib.pcs_text import Charmap
from scripts.build_ja_phase6_batch05 import control_sequence
from scripts.build_ja_phase6_batch06 import inputs, validate, glossary_audit
from scripts.build_ja_phase6_batch06_handoff import audit_incremental, HOLD_CLASSES

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out/phase6"
FIX = ROOT / "tests/fixtures"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_review_ids_provenance_status_official_and_fe():
    rom, review, source, selected, baseline = inputs()
    result = validate(rom, review, source, selected)
    assert result["reviewed"] == result["unique_ids"] == 461
    assert result["duplicate"] == result["extra"] == 0
    assert result["FE"] == 254
    assert result["FA"] == 0
    assert result["nonempty"] == 455
    assert len(baseline) == 1717
    assert result["status_counts"] == {
        "confirmed": 214, "existing_official": 212,
        "existing_glossary": 29, "needs_context": 6,
    }
    assert all(row["review_source"] == "claude_cli" for row in review)
    assert len({row["id"] for row in review}) == 461
    assert all(not row["reviewed_japanese"] for row in review
               if row["status"] == "needs_context")
    assert read(FIX / "ja_phase6_batch06_fa_claude_review.json") == []


def test_official_pending_and_glossary_scope():
    existing = read(OUT / "ja_phase6_batch06_existing_official_audit.json")
    assert existing["metadata"] == {"count": 212, "mismatch": 0, "memory_only": 0}
    assert all(row["provenance"] == "pokeapi-ja-hrkt" and row["official_terms"]
               and row["whitespace_normalized_equal"] for row in existing["entries"])
    flags = read(FIX / "ja_phase6_batch06_official_name_review.json")
    names = read(OUT / "ja_phase6_batch06_official_name_audit.json")
    assert len(flags) == len(names["entries"]) == 39
    assert len({row["entry_id"] for row in flags}) == 39
    assert names["metadata"]["result_counts"] == {
        "not_applicable": 19, "not_found": 6, "unsupported": 1,
        "verified_exact": 1, "ambiguous": 12,
    }
    catch = next(x for x in names["entries"] if x["English term"] == "Catching Charm")
    assert catch["verification class"] == "verified_exact"
    reviewed = read(OUT / "ja_phase6_batch06_reviewed.json")["entries"]
    assert not next(x for x in reviewed if x["id"] == catch["entry_id"])["final_apply"]
    _, review, _, selected, _ = inputs()
    glossary = glossary_audit(review, selected)
    assert glossary["metadata"]["existing_glossary"] == 29
    assert glossary["metadata"]["scope_mismatch"] == 0
    assert glossary["metadata"]["candidate_count"] == 25
    assert glossary["metadata"]["candidate_approved"] == 0
    assert all(not row["approved"] for row in glossary["candidates"])


def test_safe_set_menu_width_controls_and_idempotency():
    reviewed = read(OUT / "ja_phase6_batch06_reviewed.json")
    rows = reviewed["entries"]
    safe = [row for row in rows if row["final_apply"]]
    assert len(rows) == 461
    assert len(safe) == 331
    assert len(rows) - len(safe) == 130
    assert sum(row["category"].startswith("menu_") for row in rows) == 17
    assert sum(row["category"].startswith("menu_") for row in safe) == 12
    menu = read(OUT / "ja_phase6_batch06_menu_audit.json")
    assert menu["metadata"]["count"] == 17
    assert menu["metadata"]["applied"] == 12
    assert all("pointer_owners" in row and "slot_size" in row for row in menu["entries"])
    assert all(row["known_usable_width_pixels"] is None for row in menu["entries"])
    assert all(row["width_result"]["warning"] for row in rows)
    assert all("width_runtime_unverified" not in row["hold_reason"] for row in rows)
    assert sum("CONTROL_BOUNDARY" in row["hold_reason"] for row in rows) == 72
    assert all(row["control_result"] == "unmodified" for row in safe)
    combined = (OUT / "ja_phase6_batch06_combined_controlfix.json").read_bytes()
    assert combined == (OUT / "ja_phase6_batch06_safe_controlfix_rebuilt.json").read_bytes()
    assert combined == (OUT / "ja_phase6_batch06_controlfix_twice.json").read_bytes()
    old = read(OUT / "ja_phase6_batch05_combined_controlfix.json")["entries"]
    fixed = read(OUT / "ja_phase6_batch06_combined_controlfix.json")["entries"]
    assert fixed[:1717] == old
    assert len(fixed) == 2048
    assert read(OUT / "ja_phase6_batch06_controlfix_twice_report.json")[
        "stats"]["changed"] == 0
    selection = {row["id"]: row for row in
                 read(FIX / "ja_phase6_selection.json")["entries"]}
    rom = (ROOT / "rom/unbound.gba").read_bytes()
    injector = __import__("runpy").run_path(str(ROOT / "005_hybrid_injector.py"))
    codec = Charmap("ja")
    for entry in fixed[1717:]:
        source = selection[entry["id"]]
        raw = rom[source["rom_offset"]:source["rom_offset"] + source["source_encoded_size"]]
        payload = injector["encode_text"](
            codec, injector["translation_for_injection"](entry),
            plain_script=entry["category"] == "plain_scripts")
        assert control_sequence(raw) == control_sequence(payload)


def test_strict_maps_binary_audit_and_existing_1717():
    dry = read(OUT / "ja_phase6_batch06_incremental_dry_run_map.json")
    built = read(OUT / "ja_phase6_batch06_incremental_map.json")
    full = read(OUT / "ja_phase6_batch06_full_dry_run_map.json")
    for result, count in ((dry, 331), (built, 331), (full, 2048)):
        stats = result["stats"]
        assert stats["input_entries"] == count
        assert not result["missing_relocations"]
        assert not result["missing_fixed_slots"]
        assert not result["runtime_patches"]
        assert not result["graphics_patches"]
        for field in ("encode_errors", "skipped_pointer_mismatch",
                      "skipped_implausible_pointer", "skipped_no_space",
                      "fixed_truncated", "no_relocation_truncated",
                      "ability_descriptions_compacted"):
            assert stats[field] == 0
    assert dry["stats"] == built["stats"]
    assert dry["relocations"] == built["relocations"]
    assert built["stats"]["in_place"] == 297
    assert built["stats"]["relocated"] == 34
    assert built["stats"]["pointer_writes"] == 45
    assert all(x["storage"] == "vetted_ff" for x in built["relocations"])
    incremental = read(OUT / "ja_phase6_batch06_incremental_audit.json")
    source = read(OUT / "ja_phase6_batch06_rom_audit.json")
    assert incremental["status"] == source["status"] == "PASS"
    assert incremental["existing_1717_unchanged"]
    assert incremental["unexpected_byte_count"] == source["unexpected_byte_count"] == 0
    assert incremental["classified_changed_bytes"] == {
        "in_place_text": 6409, "relocated_text": 325, "pointer_writes": 145,
    }
    after = (ROOT / "out/unbound-ja-phase6-batch06.gba").read_bytes()
    assert hashlib.sha256(after).hexdigest() == incremental["after_sha256"]
    assert hashlib.sha256(after).hexdigest() == source["output_sha256"]


def test_binary_auditor_rejects_unrelated_byte(tmp_path):
    previous = ROOT / "out/unbound-ja-phase6-batch05.gba"
    candidate = bytearray((ROOT / "out/unbound-ja-phase6-batch06.gba").read_bytes())
    candidate[0x100] ^= 1
    bad = tmp_path / "unexpected.gba"
    bad.write_bytes(candidate)
    safe = read(OUT / "ja_phase6_batch06_safe_controlfix.json")["entries"]
    built = read(OUT / "ja_phase6_batch06_incremental_map.json")
    existing = read(OUT / "ja_phase6_batch05_combined_controlfix.json")["entries"]
    earlier = (read(OUT / "ja_phase6_batch04_map.json")["relocations"]
               + read(OUT / "ja_phase6_batch05_incremental_map.json")["relocations"])
    with pytest.raises(ValueError, match="Unexpected ROM changes"):
        audit_incremental(previous, bad, safe, built, existing, earlier)


def test_runtime_qa_and_phase6_cleanup_accounting():
    qa = read(FIX / "ja_phase6_batch06_runtime_qa.json")
    assert len(qa["entries"]) == 36
    assert len({x["id"] for x in qa["entries"]}) == 36
    assert all(x["runtime_result"] == "not_human_tested" for x in qa["entries"])
    inventory = read(OUT / "ja_phase6_final_cleanup_inventory.json")
    meta = inventory["metadata"]
    assert meta["selected"] == 2500
    assert meta["phase6_applied"] == 1371
    assert meta["phase6_held"] == len(inventory["entries"]) == 1129
    assert meta["pre_phase6_applied"] == 677
    assert meta["current_japanese_applied"] == 2048
    assert meta["batch_counts"] == {
        "1": {"selected": 407, "applied": 385, "held": 22},
        "2": {"selected": 408, "applied": 164, "held": 244},
        "3": {"selected": 408, "applied": 125, "held": 283},
        "4": {"selected": 408, "applied": 198, "held": 210},
        "5": {"selected": 408, "applied": 168, "held": 240},
        "6": {"selected": 461, "applied": 331, "held": 130},
    }
    assert len({x["id"] for x in inventory["entries"]}) == 1129
    assert set(meta["primary_category_counts"]) <= set(HOLD_CLASSES)
    assert sum(meta["primary_category_counts"].values()) == 1129
    assert sum(meta["priority_counts"].values()) == 1129
    assert all(x["primary_hold"] not in x["secondary_holds"] for x in inventory["entries"])
    assert all(x["suggested_next_action"] for x in inventory["entries"])
