"""Focused Phase 5F final bulb/buffer integration safety gates."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lib.pcs_text import Charmap, decode_pcs
from lib.translation_tokens import semantic_token_counts, strip_hma_quotes
from scripts.build_ja_phase5f_final import BODY_ID, EXPECTED_BODY, VALUES, pointer_hits


ROOT = Path(__file__).resolve().parents[1]
ON_OWNERS = {0x1E74C91, 0x1E74CEE, 0x1E74D4B, 0x1E74DA8, 0x1E74E05}
OFF_OWNERS = {0x1E74CBB, 0x1E74D18, 0x1E74D75, 0x1E74DD2, 0x1E74E2F}
BODY_OWNERS = {0x1E74C97, 0x1E74CC1, 0x1E74CF4, 0x1E74D1E, 0x1E74D51,
               0x1E74D7B, 0x1E74DAE, 0x1E74DD8, 0x1E74E0B, 0x1E74E35}


def read(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_claude_single_review_preserves_exact_tokens_and_kana():
    review = read("tests/fixtures/ja_phase5f_claude_review.json")
    assert len(review) == 1
    row = review[0]
    assert row["id"] == BODY_ID and row["status"] == "needs_technical_fit"
    assert row["reviewed_japanese"] == EXPECTED_BODY
    assert semantic_token_counts(strip_hma_quotes(row["original"])) == semantic_token_counts(EXPECTED_BODY)
    assert EXPECTED_BODY.count("[green]") == EXPECTED_BODY.count("[buffer1]") == EXPECTED_BODY.count("[black]") == 1
    assert EXPECTED_BODY.index("[green]") < EXPECTED_BODY.index("[buffer1]") < EXPECTED_BODY.index("[black]")
    assert not any("\u3400" <= character <= "\u9fff" for character in EXPECTED_BODY)
    assert Charmap("ja").encode("[japanese]" + EXPECTED_BODY + "[latin]").endswith(b"\xff")


def test_on_off_values_are_local_not_global_glossary_terms():
    glossary = read("glossaries/ja.json")
    sources = {term["source"].lower() for term in glossary["terms"]}
    assert not {"on", "off"} & sources
    assert set(VALUES) == {"scr_1F1A9C6", "scr_1F1A9C9"}
    assert VALUES["scr_1F1A9C6"] == ("on", "オン", 3)
    assert VALUES["scr_1F1A9C9"] == ("off", "オフ", 4)
    codec = Charmap("ja")
    assert codec.encode("[japanese]オン[latin]") == bytes.fromhex("FC 15 55 7E FC 16 FF")
    assert codec.encode("[japanese]オフ[latin]") == bytes.fromhex("FC 15 55 6C FC 16 FF")


def test_whole_rom_buffer_owners_and_direct_flow_when_available():
    path = ROOT / "rom/unbound.gba"
    if not path.exists():
        pytest.skip("private ROM unavailable")
    rom = path.read_bytes()
    for target, owners in ((0x1F1A9C6, ON_OWNERS), (0x1F1A9C9, OFF_OWNERS)):
        assert set(pointer_hits(rom, target)) == owners
        assert all(pointer_hits(rom, target + interior) == []
                   for interior in range(1, 3 if target == 0x1F1A9C6 else 4))
        for owner in owners:
            assert rom[owner - 2:owner] == b"\x85\x00"
            assert rom[owner + 4:owner + 6] == b"\x0f\x00"
            assert rom[owner + 6:owner + 10] == (0x08000000 + 0x1F1A99A).to_bytes(4, "little")
    assert set(pointer_hits(rom, 0x1F1A99A)) == BODY_OWNERS


def test_controlfix_repeat_and_dynamic_page_restoration_when_generated():
    first = ROOT / "out/ja-phase5f-final-controlfix.json"
    second = ROOT / "out/ja-phase5f-final-controlfix-second.json"
    if not (first.exists() and second.exists()):
        pytest.skip("local controlfix outputs unavailable")
    assert first.read_bytes() == second.read_bytes()
    entries = {row["id"]: row for row in read("out/ja-phase5f-final-controlfix.json")["entries"]}
    assert len(entries) == 677
    body = entries[BODY_ID]["translated"]
    assert "[green][latin][buffer1][japanese][black]" in body
    codec = Charmap("ja")
    body_bytes = codec.encode(body)
    assert len(body_bytes) == 41 <= entries[BODY_ID]["byte_length"]
    assert body_bytes.count(b"\xfd\x02") == 1
    for identifier, (_, japanese, slot) in VALUES.items():
        value_bytes = codec.encode(entries[identifier]["translated"])
        assert len(value_bytes) == 7 > slot
        expanded = body_bytes.replace(b"\xfd\x02", value_bytes[:-1])
        decoded = decode_pcs(expanded).text
        assert japanese in decoded and "[japanese][black]に" in decoded
        assert decoded.index(japanese) < decoded.index("[japanese][black]に")
    previous = read("out/ja-phase5e-controlfix.json")["entries"]
    assert previous == read("out/ja-phase5f-final-controlfix.json")["entries"][:674]
    assert read("out/ja-phase5f-final-controlfix-report.json")["stats"]["remaining_control_mismatches"] == 0


def test_strict_map_and_binary_audit_when_generated():
    paths = [ROOT / name for name in ("out/ja-phase5f-final-dry-run-map.json",
                                      "out/ja-phase5f-final-map.json",
                                      "out/ja-phase5f-final-binary-audit.json")]
    if not all(path.exists() for path in paths):
        pytest.skip("local injector/audit outputs unavailable")
    dry = read("out/ja-phase5f-final-dry-run-map.json")
    built = read("out/ja-phase5f-final-map.json")
    assert dry["stats"] == built["stats"]
    stats = built["stats"]
    assert stats["input_entries"] == 677
    assert stats["in_place"] == 478 and stats["relocated"] == 199
    assert stats["pointer_writes"] == 2009
    for key in ("encode_errors", "skipped_pointer_mismatch", "skipped_implausible_pointer",
                "skipped_no_space", "fixed_truncated", "no_relocation_truncated",
                "runtime_patches", "graphics_patches"):
        assert stats[key] == 0
    assert not built["missing_relocations"] and not built["missing_fixed_slots"]
    assert built["used_reclaimed_text_bytes"] == 0
    reloc = {row["id"]: row for row in built["relocations"]}
    assert BODY_ID not in reloc
    for identifier, owners in (("scr_1F1A9C6", ON_OWNERS), ("scr_1F1A9C9", OFF_OWNERS)):
        assert reloc[identifier]["storage"] == "vetted_ff"
        assert reloc[identifier]["byte_length"] == 7
        assert {int(x, 16) for x in reloc[identifier]["pointer_sources"]} == owners
    audit = read("out/ja-phase5f-final-binary-audit.json")
    assert audit["status"] == "PASS" and audit["input_entries"] == 677


def test_only_bulb_delta_from_phase5e_when_generated():
    previous = ROOT / "out/unbound-ja-phase5e.gba"
    current = ROOT / "out/unbound-ja-phase5f-final.gba"
    if not (previous.exists() and current.exists()):
        pytest.skip("private local ROMs unavailable")
    before, after = previous.read_bytes(), current.read_bytes()
    pointer_offsets = {index for owner in ON_OWNERS | OFF_OWNERS for index in range(owner, owner + 4)}
    body_offsets = set(range(0x1F1A99A, 0x1F1A99A + 44))
    changed = {index for index, (left, right) in enumerate(zip(before, after)) if left != right}
    assert len(before) == len(after) == 32 * 1024 * 1024
    assert changed <= pointer_offsets | body_offsets
    assert len(changed & pointer_offsets) == 40
    assert len(changed & body_offsets) == 41


def test_runtime_qa_fixture_contains_both_states():
    fixture = read("tests/fixtures/ja_phase5f_final_runtime_qa.json")
    assert fixture["status"] == "human_runtime_pending"
    assert {case["buffer_value"] for case in fixture["cases"]} == {"オン", "オフ"}
    assert all(case["buffer_value"] in case["expected_text"] and
               case["how_to_trigger"] and case["what_to_visually_verify"]
               for case in fixture["cases"])
