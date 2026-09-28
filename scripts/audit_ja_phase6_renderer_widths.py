#!/usr/bin/env python3
"""Phase 6B-4.5: ROM-anchored renderer geometry, conservative width holds."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.gen3_font import NORMAL_GLYPH_WIDTHS
from lib.pcs_text import Charmap
from lib.renderer_profiles import (battle_profiles, conservative_variable_bounds,
                                   maximum_table_width, normal_line_widths_with_placeholders,
                                   unknown_profile)

OUT = ROOT / "out/phase6"
SOURCE_MD5 = "9cad8e771940e7f7094d13911552cef0"
BATCH04_SHA256 = "3cc314c7ceb3cd6057d8c6fb71194af0e4691f54a06b0174d9b06c41900dae0e"


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def prefix_bounds(rom):
    prefixes = {}
    for label, offset, expected in (("wild", 0x003FD555, "Wild "),
                                    ("trainer_foe", 0x003FD55B, "Foe ")):
        raw = Charmap("it").encode(expected)
        if rom[offset:offset + len(raw)] != raw:
            raise ValueError(f"Battle prefix bytes changed: {label}")
        prefixes[label] = {"text": expected, "rom_offset": f"0x{offset:08X}",
                           "gba_address": f"0x{0x08000000 + offset:08X}",
                           "width_pixels": sum(NORMAL_GLYPH_WIDTHS[b] for b in raw[:-1]),
                           "consumer_proof": "adjacent battle prefix literals; Unbound expansion branch not yet traced"}
    return prefixes


def placeholder_profiles(tables, variable, prefixes):
    prefixed_name = variable["nickname"]["latin_upper_pixels"] + max(
        item["width_pixels"] for item in prefixes.values())
    return {
        "0F": {"name": "ATK_NAME_WITH_PREFIX", "class": "PLAYER_VARIABLE_MAX_WIDTH",
               "max_pixels": prefixed_name, "typical_pixels": None,
               "source": "10-byte FireRed nickname reference plus max ROM foe/wild prefix",
               "bound_proven_for_unbound": False},
        "10": {"name": "DEF_NAME_WITH_PREFIX", "class": "PLAYER_VARIABLE_MAX_WIDTH",
               "max_pixels": prefixed_name, "typical_pixels": None,
               "source": "10-byte FireRed nickname reference plus max ROM foe/wild prefix",
               "bound_proven_for_unbound": False},
        "11": {"name": "EFF_NAME_WITH_PREFIX", "class": "PLAYER_VARIABLE_MAX_WIDTH",
               "max_pixels": prefixed_name, "typical_pixels": None,
               "source": "10-byte FireRed nickname reference plus max ROM foe/wild prefix",
               "bound_proven_for_unbound": False},
        "13": {"name": "SCR_ACTIVE_NAME_WITH_PREFIX", "class": "PLAYER_VARIABLE_MAX_WIDTH",
               "max_pixels": prefixed_name, "typical_pixels": None,
               "source": "10-byte FireRed nickname reference plus max ROM foe/wild prefix",
               "bound_proven_for_unbound": False},
        "14": {"name": "CURRENT_MOVE", "class": "CONTEXT_DEPENDENT",
               "max_pixels": tables["move_names"]["max_width"], "typical_pixels": None,
               "source": "Current source-ROM move table; out-of-range type-move fallback not enumerated",
               "bound_proven_for_unbound": False},
        "1A": {"name": "SCR_ACTIVE_ABILITY", "class": "FINITE_SET_MAX_WIDTH",
               "max_pixels": tables["ability_names"]["max_width"], "typical_pixels": None,
               "source": "All source-ROM ability-name records; translated names require recomputation",
               "bound_proven_for_unbound": True},
        "00": {"name": "BUFF1", "class": "CONTEXT_DEPENDENT", "max_pixels": None,
               "typical_pixels": None, "source": "Battle script writer dependent",
               "bound_proven_for_unbound": False},
        "01": {"name": "BUFF2", "class": "CONTEXT_DEPENDENT", "max_pixels": None,
               "typical_pixels": None, "source": "Battle script writer dependent",
               "bound_proven_for_unbound": False},
        "2A": {"name": "ATK_PREFIX2", "class": "CONTEXT_DEPENDENT", "max_pixels": None,
               "typical_pixels": None, "source": "English side prefix, battle state dependent",
               "bound_proven_for_unbound": False},
        "36": {"name": "CFRU_EXTENSION_36", "class": "UNKNOWN", "max_pixels": None,
               "typical_pixels": None, "source": "Unbound/CFRU expansion branch unproved",
               "bound_proven_for_unbound": False},
        "38": {"name": "CFRU_EXTENSION_38", "class": "UNKNOWN", "max_pixels": None,
               "typical_pixels": None, "source": "Unbound/CFRU expansion branch unproved",
               "bound_proven_for_unbound": False},
    }


def battle_35(reviewed, candidates, profiles, placeholders):
    by_id = {row["id"]: row for row in candidates}
    selected = [row for row in reviewed if row["category"] == "battle_messages"
                and not row["apply"] and row["hold_reason"] in
                (["width_unproved:layout_ambiguous"], ["width_unproved:width_overflow"])]
    if len(selected) != 35:
        raise ValueError(f"Expected 35 width-only battle holds, found {len(selected)}")
    usable = profiles["battle_message"].usable_width
    rules = {int(code, 16): value["max_pixels"] for code, value in placeholders.items()}
    result = []
    for row in selected:
        text = by_id[row["id"]]["translated"]
        widths = normal_line_widths_with_placeholders(text, rules)
        codes = row["buffer_result"]["battle_codes"]
        unproved = any(not placeholders[code]["bound_proven_for_unbound"] for code in codes)
        if any(value > usable for value in widths["line_static"]):
            classification = "WIDTH_OVERFLOW"  # Even a zero-width dynamic value cannot fit.
        elif widths["unknown_placeholder_codes"] or unproved:
            classification = "DYNAMIC_WIDTH_AMBIGUOUS"
        elif widths["max_total"] > usable:
            classification = "WIDTH_OVERFLOW"
        else:
            classification = "FIT"
        conditional = "FIT" if widths["max_total"] <= usable and not widths["unknown_placeholder_codes"] else "NOT_GUARANTEED"
        result.append({"id": row["id"], "japanese": text,
                       "rom_offset": by_id[row["id"]]["address"],
                       "static_text_width_by_line": widths["line_static"],
                       "dynamic_buffer_max_by_line": widths["line_dynamic_max"],
                       "total_worst_case_by_line": widths["line_total_max"],
                       "renderer_usable_width": usable, "wrap": profiles["battle_message"].wrap,
                       "placeholder_codes": codes, "unproved_name_bound": unproved,
                       "conditional_if_firered_lengths_unchanged": conditional,
                       "result": classification, "apply": False,
                       "reason": "Nickname capacity in Unbound not independently proved; no auto-wrap" if unproved
                       else "ROM-derived geometry and finite placeholder widths"})
    return {"metadata": {"count": len(result),
                         "result_counts": dict(Counter(row["result"] for row in result)),
                         "newly_safe": sum(row["result"] in ("FIT", "WRAP_SAFE") for row in result)},
            "entries": result}


def fa_held(fa_audit, variable):
    ambiguous = [row for row in fa_audit if row["layout_status"] == "LAYOUT_AMBIGUOUS"]
    overflow = [row for row in fa_audit if row["layout_status"] == "LAYOUT_OVERFLOW"]
    if len(ambiguous) != 30 or len(overflow) != 5:
        raise ValueError("Batch 04 FA hold counts changed")
    bounds = {1: variable["player"]["latin_upper_pixels"],
              6: variable["rival"]["latin_upper_pixels"]}
    rows = []
    for row in ambiguous + overflow:
        entry_id = row["id"]
        # The FA handoff is segmented, not one controlfixed string. Measure each
        # Japanese segment without changing its FE/FA/FB boundaries.
        segment_widths = [normal_line_widths_with_placeholders(
            "[japanese]" + segment + "[latin]", bounds)
            for segment in row["japanese_segments"]]
        static_widths = [width["max_total"] - max(width["line_dynamic_max"])
                         for width in segment_widths]
        reference_worst = [width["max_total"] for width in segment_widths]
        screen_overflow = any(value > 240 for value in static_widths)
        rows.append({"id": entry_id, "prior_status": row["layout_status"],
                     "buffer_tokens": row.get("source_controls"),
                     "candidate_japanese_segments": row["japanese_segments"],
                     "reference_name_bound_pixels": bounds,
                     "prior_japanese_line_pixels": row["japanese_line_pixels"],
                     "static_width_by_segment": static_widths,
                     "reference_worst_width_by_segment": reference_worst,
                     "unknown_placeholder_codes": sorted({code for width in segment_widths
                                                          for code in width["unknown_placeholder_codes"]}),
                     "static_exceeds_screen": bool(screen_overflow),
                     "result": "LAYOUT_OVERFLOW" if row["layout_status"] == "LAYOUT_OVERFLOW"
                     else "LAYOUT_AMBIGUOUS",
                     "reason": "Normal dialogue window not ROM-proved; player/rival length is FireRed reference only",
                     "apply": False})
    return {"metadata": {"ambiguous_reviewed": 30, "screen_overflow_reviewed": 5,
                         "newly_safe": 0}, "entries": rows}


def seaport_audit(rom):
    target = 0x01F69284
    pointer = (0x08000000 + target).to_bytes(4, "little")
    hits = [index for index in range(len(rom) - 3) if rom[index:index + 4] == pointer]
    expected = [0x01E60934, 0x01E7E0A3, 0x01E7FBF8, 0x01E7FC2E,
                0x01EAF564, 0x01EAFD84]
    if hits != expected or rom[0x01E7E0A1:0x01E7E0A3] != b"\x85\x00":
        raise ValueError("Seaport exact pointer hits or bufferstring operand changed")
    return {"id": "scr_1F69284", "target_rom_offset": f"0x{target:08X}",
            "target_gba_address": f"0x{0x08000000 + target:08X}",
            "whole_rom_exact_hits": [f"0x{x:08X}" for x in hits],
            "new_owner": {"pointer_rom_offset": "0x01E7E0A3",
                          "opcode_rom_offset": "0x01E7E0A1", "opcode_bytes": "85 00",
                          "kind": "bufferstring 0 operand"},
            "other_owner_caveat": "Two aligned fields at 0x01EAF564/0x01EAFD84 have unproved consumer; keep relocation held",
            "status": "DIRECT_OWNER_PROVED_OTHER_CONSUMERS_UNPROVED"}


def batch05_metadata(batch, profiles, placeholders):
    result = {**batch, "metadata": dict(batch["metadata"]), "entries": []}
    counts = Counter()
    groups = Counter()
    for source in batch["entries"]:
        row = dict(source)
        category = row["category"]
        if category == "battle_messages":
            group = "battle_message"
            codes = sorted({token[1:].upper() for token in row["buffers"]
                            if token.startswith("\\") and len(token) == 3})
            if any(code not in placeholders or placeholders[code]["max_pixels"] is None for code in codes):
                status = "UNKNOWN_DYNAMIC"
            elif codes:
                status = "DYNAMIC_BOUNDED" if all(placeholders[code]["bound_proven_for_unbound"]
                                                    for code in codes) else "DYNAMIC_BOUND_REFERENCE_ONLY"
            else:
                status = "WIDTH_NEEDS_TRANSLATION"
            profile = profiles[group]
        elif category == "menu_battle":
            # This extractor category includes Safari and other widgets; it is
            # not evidence of B_WIN_ACTION_MENU ownership.
            group = "menu_battle_unmapped"
            codes = []
            status = "STRUCTURED_UI"
            profile = unknown_profile(group, "No per-entry battle window or print caller proven")
        elif category in {"setting_names", "start_menu_labels"}:
            group = "short_fixed_label"
            codes = []
            status = "STRUCTURED_UI"
            profile = unknown_profile(group, "Source category does not prove actual Unbound label widget")
        else:
            group = category
            codes = []
            status = "UNKNOWN_RENDERER"
            profile = unknown_profile(group, "No ROM-proved category-to-window caller/template/print origin")
        row["renderer_width_profile"] = group
        row["width_status"] = status
        row["usable_width_pixels"] = profile.usable_width if profile.status == "ROM_WINDOW_AND_PRINTER_PROVED" else None
        row["placeholder_width_classes"] = {code: placeholders[code]["class"] for code in codes
                                            if code in placeholders}
        row["final_fit_gate"] = "HOLD_UNTIL_TRANSLATED_AND_PROVED"
        row["width_evidence"] = profile.evidence
        result["entries"].append(row)
        counts[status] += 1
        groups[group] += 1
    result["metadata"]["renderer_width_audit"] = {
        "status_counts": dict(counts), "renderer_counts": dict(groups),
        "translation_created": False, "all_final_fit_held": True}
    return result


def visual_qa(battle, fa, batch05, seaport):
    picks = []
    for row in battle["entries"][:3]:
        picks.append({"renderer": "battle_message", "screen": "battle message window",
                      "entry_id": row["id"], "how_to_reach": "Use battle with relevant status/ability; exact trigger requires battle-script trace",
                      "what_measurement_is_needed": "window left/right, first glyph x, clipping at right edge, nickname expansion",
                      "expected_text": row["japanese"], "screenshot_needed": True,
                      "what_would_resolve_ambiguity": "Compare longest legal nickname and wild/trainer prefixes against right edge"})
    for row in fa["entries"][:3]:
        picks.append({"renderer": "normal_dialogue_FA", "screen": "field dialogue",
                      "entry_id": row["id"], "how_to_reach": "Locate script operand/event with progressed save; route unverified",
                      "what_measurement_is_needed": "dialogue box left/right, first glyph x, player/rival longest-name state",
                      "expected_text": row["candidate_japanese_segments"], "screenshot_needed": True,
                      "what_would_resolve_ambiguity": "Show FE/FA transition with maximum-length name and no clipped glyph"})
    for group, screen, reach in (
            ("menu_battle_unmapped", "Safari/battle menu", "Enter the relevant battle mode"),
            ("menu_options", "Options", "Open pause menu then Options"),
            ("menu_pc", "PC", "Interact with a Pokémon Center PC"),
            ("menu_item_storage", "Item Storage", "Open PC item storage"),
            ("menu_pokemon_summary", "Pokémon Summary", "Open party then Summary"),
            ("menu_game_settings", "Game Settings", "Open pause menu then Game Settings"),
    ):
        item = next((row for row in batch05["entries"] if row["renderer_width_profile"] == group), None)
        if item:
            picks.append({"renderer": group, "screen": screen, "entry_id": item["id"],
                          "how_to_reach": reach,
                          "what_measurement_is_needed": "window/list cell left and right, glyph origin, cursor and right-value columns",
                          "expected_text": item["original"], "screenshot_needed": True,
                          "what_would_resolve_ambiguity": "Pixel-bound each rendered column and identify its font and alignment"})
    picks.append({"renderer": "battle_action_menu", "screen": "Fight/Pokémon/Bag/Run",
                  "entry_id": None, "how_to_reach": "Enter any ordinary battle",
                  "what_measurement_is_needed": "Each action cell's text origin and width, cursor space",
                  "expected_text": "FIGHT / POKéMON / BAG / RUN", "screenshot_needed": True,
                  "what_would_resolve_ambiguity": "Tie four rendered labels to the B_WIN_ACTION_MENU print calls"})
    picks.append({"renderer": "route_or_city_label", "screen": "Seaport City/location label",
                  "entry_id": seaport["id"], "how_to_reach": "Visit Seaport City; exact caller for each owner unverified",
                  "what_measurement_is_needed": "sign/window left-right bounds, glyph origin, whether bufferstring or script message",
                  "expected_text": "Seaport City", "screenshot_needed": True,
                  "what_would_resolve_ambiguity": "Trace each owner to displayed widget and measure its usable width"})
    return {"metadata": {"count": len(picks), "human_tested": False,
                         "measurement_steps": [
                             "Use mGBA's screenshot command at native 240x160 resolution; disable scaling for pixel counts.",
                             "Record outer window left/right, glyph first x and last visible pixel on same row.",
                             "Repeat with maximum-length nickname/player name and both wild/trainer prefixes.",
                             "Check FE newline and FA button-scroll as separate frames; note clipping, cursor and right-aligned values.",
                             "Enter measured coordinates and save/screenshots with entry ID; do not infer width from English text alone."]},
            "cases": picks}


def main():
    rom = (ROOT / "rom/unbound.gba").read_bytes()
    if hashlib.md5(rom).hexdigest() != SOURCE_MD5:
        raise ValueError("Source ROM MD5 mismatch")
    batch04_rom = (ROOT / "out/unbound-ja-phase6-batch04.gba").read_bytes()
    if hashlib.sha256(batch04_rom).hexdigest() != BATCH04_SHA256:
        raise ValueError("Batch 04 baseline ROM changed")
    profiles = battle_profiles(rom)
    extracted = read(ROOT / "out/unbound-texts.json")["entries"]
    tables = {category: maximum_table_width(extracted, rom, category)
              for category in ("pokemon_names", "move_names", "ability_names", "trainer_names", "trainer_classes")}
    variable = conservative_variable_bounds()
    prefixes = prefix_bounds(rom)
    placeholders = placeholder_profiles(tables, variable, prefixes)
    reviewed = read(OUT / "ja_phase6_batch04_reviewed.json")["entries"]
    candidates = read(OUT / "ja_phase6_batch04_candidates_controlfix.json")["entries"]
    battle = battle_35(reviewed, candidates, profiles, placeholders)
    fa = fa_held(read(OUT / "ja_phase6_batch04_fa_audit.json")["entries"], variable)
    seaport = seaport_audit(rom)
    batch05 = batch05_metadata(read(OUT / "ja_phase6_batch05_fa_segmented_input.json"), profiles, placeholders)
    style = read(OUT / "ja_phase6_batch05_style_handoff.json")
    style["renderer_width_gate"] = "HOLD_BATTLE_DYNAMIC_AND_MAJOR_MENUS"
    style["battle_renderer_width_result"] = {
        "window_tiles": profiles["battle_message"].width_tiles,
        "physical_usable_pixels": profiles["battle_message"].usable_width,
        "wrap": profiles["battle_message"].wrap,
        "caveat": "NAME_WITH_PREFIX nickname length is FireRed reference only; no automatic approval"}
    style["battle_placeholder_width_profiles"] = placeholders
    style["width_approved_battle_placeholders"] = []
    style["dynamic_width_handling"] = (
        "Treat name-with-prefix codes as conditional FireRed-reference bounds only; "
        "do not approve without Unbound name-cap/page proof. Recompute finite-set "
        "maximums after translated name tables are selected.")
    style["menu_label_width_rule"] = "Use each ROM-proved widget only; otherwise UNKNOWN_RENDERER and hold. Never substitute dialogue width."
    style["claude_width_instruction"] = "Translate naturally without forced abbreviation; Codex decides final pixel fit after review."
    style["batch05_width_metadata"] = "out/phase6/ja_phase6_batch05_fa_segmented_input.json"
    style["translation_created"] = False
    visual = visual_qa(battle, fa, batch05, seaport)
    audit = {"metadata": {"phase": "6B-4.5", "source_md5": SOURCE_MD5,
                          "batch04_md5": hashlib.md5(batch04_rom).hexdigest(),
                          "batch04_sha256": BATCH04_SHA256,
                          "japanese_applied": 1549, "new_rom_created": False},
             "renderer_profiles": {key: asdict(value) for key, value in profiles.items()},
             "unknown_groups": ["normal_dialogue", "pause_menu", "options", "bag", "pc",
                                "generic_list", "short_selector", "signpost", "town_city_sign",
                                "route_label", "mission_ui", "short_label", "trainer_pokemon_fixed_label"],
             "name_table_maxima": tables, "variable_name_bounds": variable,
             "battle_prefixes": prefixes, "battle_placeholder_profiles": placeholders,
             "battle_35_result_counts": battle["metadata"]["result_counts"],
             "batch05_renderer_counts": batch05["metadata"]["renderer_width_audit"]["renderer_counts"],
             "batch05_width_status_counts": batch05["metadata"]["renderer_width_audit"]["status_counts"],
             "go_hold": "HOLD", "go_hold_reason": "Nickname length and major menu/label renderers remain unproved"}
    write(OUT / "ja_phase6_renderer_width_audit.json", audit)
    write(OUT / "ja_phase6_batch04_battle35_width_recheck.json", battle)
    write(OUT / "ja_phase6_batch04_fa_width_recheck.json", fa)
    write(OUT / "ja_phase6_seaport_owner_audit.json", seaport)
    write(OUT / "ja_phase6_batch05_fa_segmented_input.json", batch05)
    write(OUT / "ja_phase6_batch05_style_handoff.json", style)
    write(ROOT / "tests/fixtures/ja_phase6_renderer_visual_qa.json", visual)
    print({"battle_message_usable": profiles["battle_message"].usable_width,
           "battle35": battle["metadata"], "batch05": batch05["metadata"]["renderer_width_audit"],
           "visual_cases": len(visual["cases"]), "gate": "HOLD"})


if __name__ == "__main__":
    main()
