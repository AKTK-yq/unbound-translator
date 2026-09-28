#!/usr/bin/env python3
"""Phase 6B-4.6 focused naming/menu audit; translation and ROM remain untouched."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.renderer_profiles import (battle_profiles, focused_menu_profiles,
                                   horizontal_layout_trace, maximum_table_width,
                                   normal_line_widths_with_placeholders,
                                   rom_naming_profiles, unknown_profile)
from lib.gen3_font import NORMAL_GLYPH_WIDTHS
from scripts.audit_ja_phase6_renderer_widths import prefix_bounds

OUT = ROOT / "out/phase6"
SOURCE_MD5 = "9cad8e771940e7f7094d13911552cef0"
BATCH04_SHA256 = "3cc314c7ceb3cd6057d8c6fb71194af0e4691f54a06b0174d9b06c41900dae0e"
BATTLE_COMMAND_IDS = {
    "tbl_menu_battle_00001_3FE747": 0x000DDCDC,  # Safari caller 0x000DDC90; window 2.
    "tbl_menu_battle_00004_A4C7DA": 0x0009FB008,
    "tbl_menu_battle_00005_A4C807": 0x0009FB004,
    "tbl_menu_battle_00006_A4C82B": 0x0009FAFD0,
}


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def battle_commands(rom: bytes, extracted: list[dict]) -> dict:
    by_id = {row["id"]: row for row in extracted}
    for entry_id, pointer_offset in BATTLE_COMMAND_IDS.items():
        row = by_id[entry_id]
        target = int(row["address"], 16)
        if int.from_bytes(rom[pointer_offset:pointer_offset + 4], "little") != 0x08000000 + target:
            raise ValueError(f"Battle command pointer changed: {entry_id}")
        if f"0x{pointer_offset:X}" not in row["pointer_sources"]:
            raise ValueError(f"Battle command extraction owner changed: {entry_id}")
    if int.from_bytes(rom[0x0009FAFBC:0x0009FAFC0], "little") != 0x080D87BD:
        raise ValueError("Unbound battle command print trampoline changed")
    # ROM font routines reference four independent Latin width-table copies.
    # All match byte-for-byte; font 1 can therefore use the normal Latin
    # advance model for these *Latin-only* source strings. This says nothing
    # about Japanese glyph advances in font 1.
    latin_width_copies = (0x001FB100, 0x00207300, 0x00217618, 0x00227930)
    if any(rom[offset:offset + 256] != bytes(NORMAL_GLYPH_WIDTHS)
           for offset in latin_width_copies):
        raise ValueError("Unbound battle command Latin font width differs")
    # All four strings have the same FC 13 38 second-column origin, 56px.
    for entry_id in BATTLE_COMMAND_IDS:
        target = int(by_id[entry_id]["address"], 16)
        raw = rom[target:target + by_id[entry_id]["byte_length"]]
        if bytes.fromhex("fc 13 38") not in raw:
            raise ValueError(f"Battle command column break changed: {entry_id}")
    traces = {entry_id: horizontal_layout_trace(by_id[entry_id]["original"].strip('"'))
              for entry_id in BATTLE_COMMAND_IDS}
    if any(trace["unsupported_controls"] or trace["max_rightmost_x"] > 96 or
           not any(event["control"] == "FC13" and event["cursor_x"] == 56
                   for event in trace["position_events"])
           for trace in traces.values()):
        raise ValueError("Battle command control/column model changed")
    return {"window_id": 2, "window_rom": "0x00248340",
            "printer_rom": "0x003FEB7C", "window_width_pixels": 96,
            "second_column_origin_pixels": 56,
            "physical_first_column_span": 56, "physical_second_column_span": 40,
            "cursor_and_right_padding_proved": False,
            "font_id": 1, "letter_spacing": 0,
            "source_font_width_table_copies": [f"0x{offset:08X}" for offset in latin_width_copies],
            "japanese_font1_width_proved": False,
            "confidence": "PARTIAL", "fit_approval": False,
            "ids": sorted(BATTLE_COMMAND_IDS),
            "source_layout_traces": traces,
            "evidence": "ROM pointer operands/calls above, FC 13 38 in each string; cell cursor margins unresolved"}


def battle35_recheck(previous: dict, names: dict, prefixes: dict, ability_max: int) -> dict:
    max_prefix = max(item["width_pixels"] for item in prefixes.values())
    name_codes = (0x0F, 0x10, 0x11, 0x13)
    local_max = names["pokemon_nickname"]["safe_local_keyboard_width"] + max_prefix
    general_latin_max = names["pokemon_nickname"]["safe_any_ordinary_latin_code_width"] + max_prefix
    japanese_max = names["pokemon_nickname"]["conditional_japanese_page_width"] + max_prefix
    # The generalized model includes all ordinary Latin code points, including
    # glyphs absent from the local keyboard; imported-name page still unproved.
    conservative = max(general_latin_max, japanese_max)
    local_rules = {code: local_max for code in name_codes} | {0x1A: ability_max}
    broad_rules = {code: conservative for code in name_codes} | {0x1A: ability_max}
    rows = []
    for entry in previous["entries"]:
        local = normal_line_widths_with_placeholders(entry["japanese"], local_rules)
        broad = normal_line_widths_with_placeholders(entry["japanese"], broad_rules)
        if local["unknown_placeholder_codes"] or broad["unknown_placeholder_codes"]:
            conditional_class = "UNKNOWN"
        elif broad["max_total"] < 222:
            conditional_class = "FIT_ALL_VALUES"
        elif local["max_total"] < 222:
            conditional_class = "DYNAMIC_OVERFLOW_POSSIBLE"
        else:
            conditional_class = "DYNAMIC_OVERFLOW_POSSIBLE"
        rows.append({"id": entry["id"], "japanese": entry["japanese"],
                     "rom_offset": entry["rom_offset"], "buffer_types": entry["placeholder_codes"],
                     "static_width_by_line": local["line_static"],
                     "local_keyboard_dynamic_by_line": local["line_dynamic_max"],
                     "local_keyboard_total_by_line": local["line_total_max"],
                     "broad_dynamic_by_line": broad["line_dynamic_max"],
                     "broad_total_by_line": broad["line_total_max"],
                     "physical_window_limit": 222, "wrap": "explicit_FE_FA_FB_only",
                     "known_local_input_fits": local["max_total"] < 222,
                     "conditional_width_class": conditional_class,
                     "classification": "UNKNOWN", "fit_approval": False,
                     "unproved": ["Unbound prefix consumer/length", "imported nickname encoding/page",
                                  "last-glyph right-edge margin"]})
    if len(rows) != 35:
        raise ValueError("Battle hold set changed")
    counts = Counter(row["conditional_width_class"] for row in rows)
    return {"metadata": {"count": 35, "newly_statically_safe": 0,
                         "conditional_width_counts": dict(counts),
                         "local_input_fits": sum(row["known_local_input_fits"] for row in rows),
                         "theoretical_overflow_only": sum(row["known_local_input_fits"]
                                                          and row["conditional_width_class"] == "DYNAMIC_OVERFLOW_POSSIBLE"
                                                          for row in rows),
                         "local_input_overflow_possible": sum(not row["known_local_input_fits"] for row in rows),
                         "final_counts": {"UNKNOWN": 35}}, "entries": rows}


def fa_name_recheck(previous: dict, names: dict) -> dict:
    local = {1: names["player_name"]["safe_local_keyboard_width"],
             6: names["rival_name"]["safe_local_keyboard_width"]}
    broad = {1: names["player_name"]["safe_any_ordinary_latin_code_width"],
             6: names["rival_name"]["safe_any_ordinary_latin_code_width"]}
    rows = []
    for row in previous["entries"]:
        segments = row["candidate_japanese_segments"]
        local_widths = [normal_line_widths_with_placeholders(
            "[japanese]" + segment + "[latin]", local)["max_total"] for segment in segments]
        broad_widths = [normal_line_widths_with_placeholders(
            "[japanese]" + segment + "[latin]", broad)["max_total"] for segment in segments]
        rows.append({"id": row["id"], "prior_status": row["prior_status"],
                     "local_input_width_by_segment": local_widths,
                     "ordinary_latin_bound_by_segment": broad_widths,
                     "normal_dialogue_usable_width": None,
                     "variable_name_profile": ["player_name", "rival_name"],
                     "layout_confidence": "UNKNOWN", "apply": False})
    return {"metadata": {"ambiguous": 30, "screen_overflow": 5,
                         "newly_safe": 0}, "entries": rows}


def classify_menu(row: dict) -> tuple[str, str]:
    category = row["category"]
    entry_id = row["id"]
    if category == "battle_messages":
        return "battle_message", "battle_message"
    if entry_id in BATTLE_COMMAND_IDS:
        return "battle_command_two_column", "battle_action_menu"
    if category == "menu_battle":
        return "battle_submenu", "battle_submenu_unknown"
    if category == "menu_options":
        return "options_value_label", "options_label_value_row"
    if category == "menu_game_settings":
        return "settings_label_or_help", "game_settings_unknown"
    if category == "menu_item_storage":
        original = row["original"]
        if "Deposit Item" in original or "Withdraw Item" in original:
            return "pc_item_action", "pc_item_action_short"
        if "Store items" in original or "Take out items" in original:
            return "pc_item_help", "pc_item_help_unknown"
        if "full" in original:
            return "pc_item_message", "pc_message_unknown"
        return "pc_item_context_action", "pc_item_context_unknown"
    if category == "menu_pc":
        if int(entry_id.rsplit("_", 1)[-1], 16) >= 0x41848F:
            return "pc_box_action_or_label", "pc_box_label_unknown"
        return "pc_box_message", "pc_message_unknown"
    if category == "menu_cube_system":
        return "bag_cube_sort_popup_or_tab", "bag_cube_unknown"
    if category == "menu_list_labels":
        return "generic_list", "generic_list_unknown"
    if category in ("setting_names", "start_menu_labels"):
        return "short_label", "short_label_unknown"
    if category.startswith("menu_"):
        return category, category + "_unknown"
    return "unknown", "unknown"


def menu_inventory(batch: dict, profiles: dict, names: dict) -> tuple[dict, dict]:
    result = {**batch, "metadata": dict(batch["metadata"]), "entries": []}
    groups = Counter()
    confidence = Counter()
    for original in batch["entries"]:
        row = dict(original)
        group, profile_id = classify_menu(row)
        profile = profiles.get(profile_id)
        if profile is None:
            profile = unknown_profile(profile_id, "No direct per-entry Unbound caller/window proof")
        if group == "battle_command_two_column":
            # Window is proven but 56/40px columns have unmeasured cursor margins.
            confidence_value = "PARTIAL"
            usable = None
            physical = 96
        else:
            confidence_value = profile.confidence
            usable = profile.usable_width if confidence_value == "PROVEN" else None
            physical = (profile.width_tiles * 8 - (profile.text_start_x or 0)
                        if profile.width_tiles is not None else None)
        row["renderer_group_final"] = group
        row["renderer_profile_id"] = profile_id
        row["renderer_confidence"] = confidence_value
        row["usable_width_pixels"] = usable
        row["physical_window_span_pixels"] = physical
        row["wrap_support"] = profile.wrap
        row["window_sizing"] = "fixed_template" if profile.width_tiles is not None else "unknown"
        row["dynamic_buffer_profile"] = [
            {"token": token, "profile": "player_name" if token == "[player]" else
             "rival_name" if token == "[rival]" else "battle_or_context_dependent"}
            for token in row.get("buffers", [])]
        row["variable_name_profile"] = {
            "player_name": names["player_name"]["safe_local_keyboard_width"],
            "rival_name": names["rival_name"]["safe_local_keyboard_width"],
        } if row.get("control_segments") else None
        row["layout_confidence"] = confidence_value
        row["technical_fit_risk"] = "NEEDS_TRANSLATED_PIXEL_FIT" if confidence_value == "PROVEN" else (
            "STRUCTURED_COLUMNS_OR_MARGIN" if confidence_value == "PARTIAL" else "UNKNOWN_RENDERER")
        row["final_fit_gate"] = "HOLD_UNTIL_TRANSLATED_AND_PROVED"
        result["entries"].append(row)
        groups[group] += 1
        confidence[confidence_value] += 1
    result["metadata"]["renderer_width_final_audit"] = {
        "groups": dict(sorted(groups.items())), "confidence_counts": dict(confidence),
        "fa_metadata_rows": sum(bool(row.get("control_segments")) for row in result["entries"]),
        "new_translations": 0, "fit_approval_count": 0, "gate": "HOLD"}
    return result, result["metadata"]["renderer_width_final_audit"]


def main() -> None:
    rom = (ROOT / "rom/unbound.gba").read_bytes()
    if hashlib.md5(rom).hexdigest() != SOURCE_MD5:
        raise ValueError("Source ROM MD5 mismatch")
    batch04 = (ROOT / "out/unbound-ja-phase6-batch04.gba").read_bytes()
    if hashlib.sha256(batch04).hexdigest() != BATCH04_SHA256:
        raise ValueError("Batch 04 ROM changed")
    extracted = read(ROOT / "out/unbound-texts.json")["entries"]
    species = maximum_table_width(extracted, rom, "pokemon_names")
    ability = maximum_table_width(extracted, rom, "ability_names")
    names = rom_naming_profiles(rom, species["max_width"])
    profiles = battle_profiles(rom) | focused_menu_profiles(rom)
    command = battle_commands(rom, extracted)
    previous = read(OUT / "ja_phase6_batch04_battle35_width_recheck.json")
    battle = battle35_recheck(previous, names, prefix_bounds(rom), ability["max_width"])
    fa = fa_name_recheck(read(OUT / "ja_phase6_batch04_fa_width_recheck.json"), names)
    batch05, inventory = menu_inventory(read(OUT / "ja_phase6_batch05_fa_segmented_input.json"),
                                        profiles, names)
    style = read(OUT / "ja_phase6_batch05_style_handoff.json")
    style["renderer_width_gate"] = "HOLD_MAJOR_MENUS_AND_IMPORTED_NAMES"
    style["natural_translation_first"] = True
    style["forbid_width_driven_abbreviation"] = True
    style["final_pixel_fit_owner"] = "Codex after reviewed translation"
    style["official_names_require_verification"] = True
    style["fa_segment_translation_only"] = True
    style["naming_profile_path"] = "out/phase6/ja_phase6_renderer_width_final_audit.json"
    style["battle_command_columns"] = command
    style["unknown_renderer_rule"] = "HOLD; do not substitute battle/dialogue width"
    write(OUT / "ja_phase6_batch05_fa_segmented_input.json", batch05)
    write(OUT / "ja_phase6_batch05_style_handoff.json", style)
    audit = {"metadata": {"phase": "6B-4.6", "source_md5": SOURCE_MD5,
                          "batch04_sha256": BATCH04_SHA256, "japanese_applied": 1549,
                          "new_rom_created": False, "go_hold": "HOLD"},
             "name_profiles": names, "species_actual_max": species,
             "battle_command": command,
             "renderer_profiles": {key: asdict(value) for key, value in profiles.items()},
             "batch04_battle35": battle["metadata"], "batch04_fa": fa["metadata"],
             "batch05_inventory": inventory}
    write(OUT / "ja_phase6_renderer_width_final_audit.json", audit)
    write(OUT / "ja_phase6_batch04_battle35_width_final.json", battle)
    write(OUT / "ja_phase6_batch04_fa_width_final.json", fa)
    print({"naming_max": {key: value["safe_local_keyboard_width"] for key, value in names.items()},
           "battle35": battle["metadata"], "batch05": inventory})


if __name__ == "__main__":
    main()
