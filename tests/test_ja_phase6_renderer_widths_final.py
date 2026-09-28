"""Phase 6B-4.6: ROM-backed name limits and fail-closed menu width metadata."""

import json
from pathlib import Path

import pytest

from lib.gen3_font import NORMAL_GLYPH_WIDTHS
from lib.pcs_text import Charmap
from lib.renderer_profiles import (focused_menu_profiles, horizontal_layout_trace,
                                   maximum_table_width, rom_naming_profiles)
from scripts.audit_ja_phase6_renderer_widths_final import (battle_commands,
                                                            battle35_recheck, classify_menu,
                                                            menu_inventory)
from scripts.audit_ja_phase6_renderer_widths import prefix_bounds


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out/phase6"


def load(name):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def evidence():
    rom = (ROOT / "rom/unbound.gba").read_bytes()
    extracted = json.loads((ROOT / "out/unbound-texts.json").read_text(encoding="utf-8"))["entries"]
    species = maximum_table_width(extracted, rom, "pokemon_names")
    return rom, extracted, rom_naming_profiles(rom, species["max_width"])


def test_naming_char_count_keyboard_pages_and_terminator(evidence):
    rom, _, names = evidence
    assert {kind: row["max_chars_excluding_terminator"] for kind, row in names.items()} == {
        "pokemon_nickname": 10, "player_name": 7, "rival_name": 7}
    assert {kind: row["naming_output_bytes_with_terminator"] for kind, row in names.items()} == {
        "pokemon_nickname": 11, "player_name": 8, "rival_name": 8}
    keyboard = rom[0x003E22D0:0x003E2330]
    assert len(keyboard) == 96
    assert len(set(keyboard) - {0}) == 75
    assert max(keyboard) < 0xF7
    assert all(not row["local_keyboard_japanese"] and not row["local_keyboard_mixed"]
               for row in names.values())
    assert rom[0x003E2474 + 1] == 10
    assert rom[0x003E245C + 1] == rom[0x003E2480 + 1] == 7


def test_naming_safe_widths_and_actual_species(evidence):
    _, _, names = evidence
    assert names["pokemon_nickname"]["keyboard_max_advance"] == 6
    assert names["pokemon_nickname"]["safe_local_keyboard_width"] == 60
    assert names["player_name"]["safe_local_keyboard_width"] == 42
    assert names["rival_name"]["safe_local_keyboard_width"] == 42
    assert names["pokemon_nickname"]["safe_any_ordinary_latin_code_width"] == 120
    assert names["pokemon_nickname"]["conditional_japanese_page_width"] == 100
    assert names["pokemon_nickname"]["actual_known_species_max_width"] == 59
    assert all(row["letter_spacing"] == 0 for row in names.values())
    assert max(NORMAL_GLYPH_WIDTHS[:0xF7]) == 12


def test_naming_rom_anchor_changes_fail_closed(evidence):
    rom, _, names = evidence
    bad = bytearray(rom)
    bad[0x003E2475] = 11
    with pytest.raises(ValueError, match="limits changed"):
        rom_naming_profiles(bad, names["pokemon_nickname"]["actual_known_species_max_width"])
    bad = bytearray(rom)
    bad[0x003E22D0] = 0xFC
    with pytest.raises(ValueError, match="keyboard changed"):
        rom_naming_profiles(bad, 59)


def test_battle35_recheck_is_conditional_not_approval(evidence):
    rom, _, names = evidence
    prior = load("ja_phase6_batch04_battle35_width_recheck.json")
    result = battle35_recheck(prior, names, prefix_bounds(rom), 86)
    assert result["metadata"]["count"] == 35
    assert result["metadata"]["local_input_fits"] == 29
    assert result["metadata"]["theoretical_overflow_only"] == 28
    assert result["metadata"]["local_input_overflow_possible"] == 6
    assert result["metadata"]["newly_statically_safe"] == 0
    assert result["metadata"]["final_counts"] == {"UNKNOWN": 35}
    assert all(row["classification"] == "UNKNOWN" and not row["fit_approval"]
               for row in result["entries"])


def test_menu_templates_and_battle_column_controls(evidence):
    rom, extracted, _ = evidence
    profiles = focused_menu_profiles(rom)
    assert profiles["options_label_value_row"].width_tiles == 26
    assert profiles["options_label_value_row"].text_start_x == 8
    assert profiles["options_label_value_row"].usable_width is None
    assert profiles["pc_item_action_short"].width_tiles == 13
    assert profiles["pc_item_action_short"].usable_width is None
    command = battle_commands(rom, extracted)
    assert command["second_column_origin_pixels"] == 56
    assert command["physical_second_column_span"] == 40
    assert not command["fit_approval"]
    assert len(command["source_font_width_table_copies"]) == 4
    assert all(trace["unsupported_controls"] == [] and trace["max_rightmost_x"] <= 96
               for trace in command["source_layout_traces"].values())


def test_horizontal_control_not_arrow_alignment():
    base = horizontal_layout_trace("AB")
    with_column = horizontal_layout_trace("A\\CC1338B")
    assert with_column["position_events"] == [
        {"line": 0, "control": "FC13", "cursor_x": 56}]
    assert with_column["max_rightmost_x"] > base["max_rightmost_x"]
    # The backslash aliases are single-byte arrow glyphs, not layout commands.
    arrows = horizontal_layout_trace("\\al\\ar")
    assert arrows["position_events"] == []
    assert arrows["max_rightmost_x"] == sum(
        NORMAL_GLYPH_WIDTHS[byte] for byte in Charmap("ja").encode("\\al\\ar")[:-1])


def test_unknown_renderer_stays_held(evidence):
    rom, _, names = evidence
    batch = load("ja_phase6_batch05_fa_segmented_input.json")
    profiles = focused_menu_profiles(rom)
    annotated, counts = menu_inventory(batch, profiles, names)
    assert len(annotated["entries"]) == 408
    assert counts["confidence_counts"]["UNKNOWN"] >= 200
    assert counts["fit_approval_count"] == 0
    assert all(row["usable_width_pixels"] is None and row["final_fit_gate"] ==
               "HOLD_UNTIL_TRANSLATED_AND_PROVED" for row in annotated["entries"]
               if row["renderer_confidence"] == "UNKNOWN")
    assert classify_menu({"id": "tbl_menu_battle_00001_3FE747", "category": "menu_battle"}) == (
        "battle_command_two_column", "battle_action_menu")


def test_batch05_and_fa_metadata_complete():
    batch = load("ja_phase6_batch05_fa_segmented_input.json")
    summary = batch["metadata"]["renderer_width_final_audit"]
    assert len(batch["entries"]) == 408
    assert sum(summary["confidence_counts"].values()) == 408
    assert summary["confidence_counts"] == {"PROVEN": 189, "UNKNOWN": 208, "PARTIAL": 11}
    assert summary["fa_metadata_rows"] == 4
    assert all({"renderer_profile_id", "renderer_confidence", "usable_width_pixels",
                "dynamic_buffer_profile", "wrap_support", "window_sizing",
                "technical_fit_risk", "layout_confidence"} <= row.keys()
               for row in batch["entries"])
    segmented = [row for row in batch["entries"] if row.get("control_segments")]
    assert len(segmented) == 4
    assert all(row["variable_name_profile"] == {"player_name": 42, "rival_name": 42}
               for row in segmented)
    assert load("ja_phase6_batch04_fa_width_final.json")["metadata"]["newly_safe"] == 0


def test_visual_qa_is_minimal_and_has_measurable_fields():
    qa = json.loads((ROOT / "tests/fixtures/ja_phase6_renderer_visual_qa.json").read_text(
        encoding="utf-8"))
    assert qa["metadata"]["count"] == len(qa["cases"]) == 10
    assert not qa["metadata"]["human_tested"]
    required = {"renderer", "profile", "screen", "how_to_reach", "english_baseline_text",
                "window_left_edge_px", "print_start_px", "expected_right_edge_px",
                "screenshot_measurement_needed", "what_would_resolve_ambiguity"}
    assert all(required <= case.keys() and case["screenshot_needed"]
               for case in qa["cases"])
