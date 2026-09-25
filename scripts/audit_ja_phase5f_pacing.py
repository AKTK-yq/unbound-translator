#!/usr/bin/env python3
"""Static PCS progression audit; no ROM or translation writes."""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib.pcs_text import Charmap, fc_arg_count
from lib.translation_tokens import strip_hma_quotes


ROOT = Path(__file__).resolve().parents[1]
SAMPLE_IDS = (
    "tbl_menu_game_settings_00035_1F4E037",  # Options battle help
    "tbl_menu_game_settings_00018_1F4DE12",  # Options puzzle help
    "tbl_menu_options_00001_419DD3",         # Text Speed label
    "scr_1F10323",                           # dynamic difficulty text
    "scr_1F9FBCD",                           # dynamic player name
)


def analyze(encoded: bytes) -> dict:
    """Count renderer-relevant PCS units, excluding terminator."""
    counts = Counter()
    index = 0
    while index < len(encoded):
        value = encoded[index]
        index += 1
        if value == 0xFF:
            counts["terminator"] += 1
            break
        if value == 0x00:
            counts["space_glyph"] += 1
            counts["ordinary_glyph"] += 1
        elif value == 0xFE:
            counts["newline_FE"] += 1
        elif value == 0xFA:
            counts["scroll_FA"] += 1
        elif value == 0xFB:
            counts["clear_FB"] += 1
        elif value == 0xFC:
            command = encoded[index]
            index += 1
            args = encoded[index:index + fc_arg_count(command)]
            index += len(args)
            counts["FC_controls"] += 1
            counts[f"FC_{command:02X}"] += 1
            if command == 0x08:
                counts["timed_pause_frames"] += args[0] if args else 0
            elif command == 0x09:
                counts["press_wait"] += 1
            elif command == 0x0A:
                counts["sound_wait"] += 1
        elif value in (0xFD, 0xF7, 0xF8, 0xF9):
            index += 1
            counts[{0xFD: "FD_dynamic", 0xF7: "F7_special",
                    0xF8: "F8_button", 0xF9: "F9_special"}[value]] += 1
        else:
            counts["ordinary_glyph"] += 1
            if value in (0xAB, 0xAC, 0xAD, 0xB0, 0x2E):
                counts["punctuation_or_symbol_glyph"] += 1
    counts["nonspace_glyph"] = counts["ordinary_glyph"] - counts["space_glyph"]
    # RenderText reads spaces through the ordinary-glyph path. This is a
    # static glyph-advance count, not measured display frames; FC/FE can also
    # reset the same delay counter and Options may use speed zero.
    counts["static_glyph_advance_steps"] = counts["ordinary_glyph"]
    return dict(sorted(counts.items()))


def main():
    entries = json.loads((ROOT / "out/ja-phase5e-controlfix.json").read_text(encoding="utf-8"))["entries"]
    reviewed = json.loads((ROOT / "out/ja-phase5e-reviewed-input.json").read_text(encoding="utf-8"))["entries"]
    reviewed_by_id = {row["id"]: row for row in reviewed}
    codec = Charmap("ja")
    cases = []
    explicit_wait_increases = []
    page_transition_increases = []
    controlfix_wait_increases = []
    controlfix_page_increases = []
    explicit_wait_keys = ("FC_08", "FC_09", "FC_0A")
    page_keys = ("scroll_FA", "clear_FB")
    for row in entries:
        english = strip_hma_quotes(row["original"])
        original_bytes = codec.encode(english)
        japanese_bytes = codec.encode(row["translated"])
        original_metrics = analyze(original_bytes)
        translated_metrics = analyze(japanese_bytes)
        wait_increases = {key: translated_metrics.get(key, 0) - original_metrics.get(key, 0)
                          for key in explicit_wait_keys
                          if translated_metrics.get(key, 0) > original_metrics.get(key, 0)}
        page_increases = {key: translated_metrics.get(key, 0) - original_metrics.get(key, 0)
                          for key in page_keys
                          if translated_metrics.get(key, 0) > original_metrics.get(key, 0)}
        if wait_increases:
            explicit_wait_increases.append({"id": row["id"], "increases": wait_increases})
        if page_increases:
            page_transition_increases.append({"id": row["id"], "increases": page_increases})
        before_controlfix = analyze(codec.encode(reviewed_by_id[row["id"]]["translated"]))
        fixed_waits = {key: translated_metrics.get(key, 0) - before_controlfix.get(key, 0)
                       for key in explicit_wait_keys
                       if translated_metrics.get(key, 0) > before_controlfix.get(key, 0)}
        fixed_pages = {key: translated_metrics.get(key, 0) - before_controlfix.get(key, 0)
                       for key in page_keys
                       if translated_metrics.get(key, 0) > before_controlfix.get(key, 0)}
        if fixed_waits:
            controlfix_wait_increases.append({"id": row["id"], "increases": fixed_waits})
        if fixed_pages:
            controlfix_page_increases.append({"id": row["id"], "increases": fixed_pages})
        if row["id"] in SAMPLE_IDS:
            cases.append({
                "id": row["id"], "category": row["category"],
                "rom_offset": row["address"], "source_english": english,
                "translated_japanese": row["translated"],
                "english_encoded_hex": original_bytes.hex(" "),
                "japanese_encoded_hex": japanese_bytes.hex(" "),
                "english": original_metrics, "japanese": translated_metrics,
                "dynamic_buffer_values_excluded": bool(original_metrics.get("FD_dynamic")),
            })
    if {case["id"] for case in cases} != set(SAMPLE_IDS):
        raise ValueError("Pacing sample ID missing from Phase 5E")
    result = {
        "phase": "5F", "kind": "static PCS audit, not timed emulator measurement",
        "renderer_rom_offset": "0x00005790", "renderer_gba_address": "0x08005790",
        "glyph_decompress_rom_offset": "0x000065B8",
        "space_and_width_rom_offset": "0x000065C2",
        "sample_ids": list(SAMPLE_IDS), "cases": cases,
        "translated_entry_count": len(entries),
        "entries_with_added_explicit_wait_controls": explicit_wait_increases,
        "entries_with_added_page_transitions": page_transition_increases,
        "controlfix_added_explicit_waits": controlfix_wait_increases,
        "controlfix_added_page_transitions": controlfix_page_increases,
    }
    path = ROOT / "out/ja-phase5f-pacing-analysis.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Pacing: {len(cases)} samples; {len(explicit_wait_increases)} explicit-wait increases; "
          f"{len(page_transition_increases)} page-transition increases")


if __name__ == "__main__":
    main()
