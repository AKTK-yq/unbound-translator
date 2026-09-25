"""Phase 5F held-entry and Japanese text-progression safety checks."""

import json
from pathlib import Path
import runpy

import pytest

from lib.pcs_text import Charmap, decode_pcs
from scripts.audit_ja_phase5f_pacing import analyze


ROOT = Path(__file__).resolve().parents[1]


def load(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_visual_qa_fixture_has_all_held_visual_cases_and_pacing():
    cases = load("tests/fixtures/ja_phase5f_visual_qa.json")["cases"]
    assert len(cases) == 12
    assert len({case["id"] for case in cases}) == len(cases)
    assert sum(case["id"].startswith("tbl_pokedex_form_names_") for case in cases) == 5
    assert {"scr_1F0F842", "tbl_menu_list_labels_00005_4178FD", "scr_1FAE999",
            "options_text_pacing"} <= {case["id"] for case in cases}
    assert all(case["screen"] and case["how_to_reach"] and case["what_to_look_at"] and
               case["possible_interpretations"] and "screenshot_needed" in case
               for case in cases)


def test_pacing_static_glyphs_include_spaces_and_punctuation_but_not_waits():
    codec = Charmap("ja")
    metrics = analyze(codec.encode("[japanese]あ い。！[latin]"))
    assert metrics["ordinary_glyph"] == 5
    assert metrics["space_glyph"] == 1
    assert metrics["static_glyph_advance_steps"] == 5
    assert metrics["punctuation_or_symbol_glyph"] == 2
    assert not any(metrics.get(control, 0) for control in ("FC_08", "FC_09", "FC_0A"))


def test_japanese_latin_dynamic_restore_is_byte_stable():
    text = "[japanese]こ[latin][buffer1][japanese]ん。[latin]"
    codec = Charmap("ja")
    assert decode_pcs(codec.encode(text)).text == text
    assert codec.encode(text).count(bytes.fromhex("FC 15")) == 2
    assert codec.encode(text).count(bytes.fromhex("FC 16")) == 2


def test_held_entries_are_not_in_phase5e_controlfix_when_generated():
    controlfix = ROOT / "out/ja-phase5e-controlfix.json"
    audit = ROOT / "out/ja-phase5f-remaining-audit.json"
    if not (controlfix.exists() and audit.exists()):
        pytest.skip("local Phase 5E/5F generated audit unavailable")
    held = load("out/ja-phase5f-remaining-audit.json")
    assert held["classification_counts"] == {
        "A": 4, "B": 16, "C": 10, "D": 2, "E": 3, "F": 8, "H": 1,
    }
    assert held["total"] == len(held["entries"]) == 44
    assert held["new_japanese_translation_count"] == 0
    assert held["day_owner_metadata_resolved_count"] == 5
    applied = {row["id"] for row in load("out/ja-phase5e-controlfix.json")["entries"]}
    assert not (applied & {row["id"] for row in held["entries"]})
    assert "scr_1080302" not in applied
    credits = [row for row in held["entries"] if row["category"] == "credits_text"]
    assert {(row["evidence"][0]["source_byte_length"],
             row["evidence"][0]["roundtrip_byte_length"]) for row in credits} == {
                 (35, 33), (32, 30), (18, 16),
             }
    assert {row["id"] for row in held["entries"] if row["classification"] == "D"} == {
        "scr_7A95BA", "scr_750C28",
    }
    prefixes = {row["id"]: row["evidence"][0]["first_raw_byte"] for row in held["entries"]
                if row["classification"] == "D"}
    assert prefixes == {"scr_7A95BA": "0x14", "scr_750C28": "0x02"}
    bulb = next(row for row in held["entries"] if row["id"] == "scr_1F1A99A")
    assert bulb["evidence"][0]["actual_values_proven"] is True
    assert {source["value"] for source in bulb["evidence"][0]["source_data"]} == {"on", "off"}


def test_claude_handoff_is_bounded_and_not_an_approved_translation():
    handoff = load("out/ja-phase5f-for-claude.json") if (ROOT / "out/ja-phase5f-for-claude.json").exists() else None
    if handoff is None:
        pytest.skip("local Phase 5F handoff unavailable")
    assert [entry["id"] for entry in handoff["entries"]] == ["scr_1F1A99A"]
    row = handoff["entries"][0]
    assert "on/off" in row["buffer_meaning"]
    assert all(row[key] for key in ("original", "old_candidate", "newly_discovered_context",
                                   "speaker", "runtime_use", "technical_constraints"))
    assert "do not inject" in handoff["purpose"]


def test_held_page_controls_have_no_added_explicit_waits_when_generated():
    path = ROOT / "out/ja-phase5f-pacing-analysis.json"
    if not path.exists():
        pytest.skip("local Phase 5F pacing audit unavailable")
    audit = load("out/ja-phase5f-pacing-analysis.json")
    assert audit["translated_entry_count"] == 674
    assert audit["entries_with_added_explicit_wait_controls"] == []
    assert audit["controlfix_added_explicit_waits"] == []
    assert len(audit["cases"]) == 5
    for case in audit["cases"]:
        assert case["japanese"]["FC_15"] == case["japanese"]["FC_16"]
    options = [case for case in audit["cases"] if case["id"].startswith("tbl_menu_game_settings_")]
    assert len(options) == 2
    assert all(case["japanese"]["static_glyph_advance_steps"] <
               case["english"]["static_glyph_advance_steps"] for case in options)
    assert all(case["japanese"].get("scroll_FA", 0) == case["english"].get("scroll_FA", 0)
               and case["japanese"].get("clear_FB", 0) == case["english"].get("clear_FB", 0)
               for case in options)


def test_rom_renderer_static_bytes_when_available():
    path = ROOT / "rom/unbound.gba"
    if not path.exists():
        pytest.skip("private source ROM unavailable")
    rom = path.read_bytes()
    # `ldrb r1,[r6,#0x1E]` and `ldrb r0,[r6,#0x1D]`: delay and speed.
    assert rom[0x57E6:0x57F0].hex() == "b17f00291dd0707f0028"
    # FC15/FC16 both set printer Japanese-page flag at offset 0x21.
    assert rom[0x5B10:0x5B20].hex() == "311c2131012002e0311c213100200870"
