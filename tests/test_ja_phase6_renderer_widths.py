"""ROM-anchored renderer bounds must fail closed where runtime is unproved."""

import json
from pathlib import Path

import pytest

from lib.renderer_profiles import (battle_profiles, conservative_variable_bounds,
                                   maximum_table_width, normal_line_widths_with_placeholders,
                                   unknown_profile)
from scripts.audit_ja_phase6_renderer_widths import (battle_35, fa_held,
                                                     placeholder_profiles, prefix_bounds,
                                                     seaport_audit)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out/phase6"


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def rom():
    return (ROOT / "rom/unbound.gba").read_bytes()


def test_battle_profile_parse_and_usable_width(rom):
    profiles = battle_profiles(rom)
    message = profiles["battle_message"]
    assert (message.window_id, message.window_rom_offset, message.printer_rom_offset) == (
        0, 0x00248330, 0x003FEB64)
    assert (message.width_tiles, message.height_tiles, message.text_start_x) == (28, 4, 2)
    assert (message.font_id, message.letter_spacing, message.line_spacing) == (2, 0, 2)
    assert message.usable_width == 222
    assert message.wrap == "explicit_FE_FA_FB_only"
    assert (profiles["battle_action_menu"].width_tiles,
            profiles["battle_action_menu"].font_id) == (12, 1)
    bad = bytearray(rom)
    bad[0x0000F348] ^= 1
    with pytest.raises(ValueError, match="xref changed"):
        battle_profiles(bad)


def test_explicit_battle_line_controls_and_pages():
    widths = normal_line_widths_with_placeholders(
        "[japanese]こんにちは\\nあいう\\lえお\\pかき[latin]", {})
    assert len(widths["line_static"]) == 4
    assert widths["line_static"][0] > 0
    assert widths["unknown_placeholder_codes"] == []


def test_dynamic_pokemon_move_ability_table_widths(rom):
    entries = read(ROOT / "out/unbound-texts.json")["entries"]
    tables = {category: maximum_table_width(entries, rom, category) for category in (
        "pokemon_names", "move_names", "ability_names")}
    assert (tables["pokemon_names"]["record_count"],
            tables["pokemon_names"]["max_width"]) == (1294, 59)
    assert (tables["move_names"]["record_count"],
            tables["move_names"]["max_width"]) == (923, 71)
    assert (tables["ability_names"]["record_count"],
            tables["ability_names"]["max_width"]) == (293, 86)
    placeholders = placeholder_profiles(tables, conservative_variable_bounds(),
                                        prefix_bounds(rom))
    assert placeholders["0F"]["class"] == "PLAYER_VARIABLE_MAX_WIDTH"
    assert placeholders["14"]["max_pixels"] == 71
    assert placeholders["1A"]["max_pixels"] == 86
    assert not placeholders["14"]["bound_proven_for_unbound"]


def test_player_name_upper_bound_is_reference_only():
    bounds = conservative_variable_bounds()
    assert bounds["player"]["max_chars_reference"] == 7
    assert bounds["player"]["latin_upper_pixels"] == 84
    assert bounds["nickname"]["latin_upper_pixels"] == 120
    assert not bounds["player"]["approved_for_automatic_fit"]


def test_unknown_route_sign_and_generic_menus_hold():
    for key in ("route_label", "signpost", "options", "bag", "pc", "generic_list"):
        profile = unknown_profile(key, "runtime window caller not proved")
        assert profile.status == "UNKNOWN_RENDERER"
        assert profile.usable_width is None


def test_batch04_battle35_remain_unapproved():
    audit = read(OUT / "ja_phase6_batch04_battle35_width_recheck.json")
    assert audit["metadata"]["count"] == 35
    assert audit["metadata"]["newly_safe"] == 0
    assert audit["metadata"]["result_counts"] == {"DYNAMIC_WIDTH_AMBIGUOUS": 35}
    assert all(not row["apply"] and row["renderer_usable_width"] == 222
               for row in audit["entries"])


def test_fa_dynamic_name_and_screen_overflow_hold():
    audit = read(OUT / "ja_phase6_batch04_fa_width_recheck.json")
    assert audit["metadata"] == {"ambiguous_reviewed": 30,
                                  "screen_overflow_reviewed": 5, "newly_safe": 0}
    assert all(not row["apply"] for row in audit["entries"])
    overflow = [row for row in audit["entries"] if row["prior_status"] == "LAYOUT_OVERFLOW"]
    assert len(overflow) == 5
    assert all(row["static_exceeds_screen"] for row in overflow)
    assert all(max(row["static_width_by_segment"]) > 240 for row in overflow)


def test_batch05_width_metadata_and_visual_qa():
    batch = read(OUT / "ja_phase6_batch05_fa_segmented_input.json")
    assert len(batch["entries"]) == 408
    counts = batch["metadata"]["renderer_width_audit"]["status_counts"]
    assert counts == {"WIDTH_NEEDS_TRANSLATION": 189,
                      "UNKNOWN_RENDERER": 196, "STRUCTURED_UI": 23}
    assert all(row["final_fit_gate"] == "HOLD_UNTIL_TRANSLATED_AND_PROVED"
               for row in batch["entries"])
    assert all("renderer_width_profile" in row for row in batch["entries"])
    qa = read(ROOT / "tests/fixtures/ja_phase6_renderer_visual_qa.json")
    assert qa["metadata"]["human_tested"] is False
    assert len(qa["cases"]) >= 10
    assert all(row["screenshot_needed"] and row["what_would_resolve_ambiguity"]
               for row in qa["cases"])


def test_seaport_exact_pointer_hits_and_opcode(rom):
    audit = seaport_audit(rom)
    assert audit["new_owner"]["pointer_rom_offset"] == "0x01E7E0A3"
    assert len(audit["whole_rom_exact_hits"]) == 6
    assert audit["status"] == "DIRECT_OWNER_PROVED_OTHER_CONSUMERS_UNPROVED"
