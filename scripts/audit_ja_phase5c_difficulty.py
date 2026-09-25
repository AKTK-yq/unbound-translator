#!/usr/bin/env python3
"""Cross-check focused difficulty placements against the strict full-ROM audit."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib.gen3_font import text_pixel_width
from lib.pcs_text import Charmap
from lib.translation_tokens import strip_hma_quotes


CLIPPED_ID = "tbl_menu_game_settings_00000_1F4E274"
COMPLETE_ID = "tbl_menu_game_settings_00000_1F4E26F"
BATTLE_CHOICES = (
    "scr_1F10630", "scr_1F10621", "scr_1F1063D", "scr_1F10644"
)


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def max_line_width(text):
    """Measure each line without forgetting the renderer's persistent page."""
    japanese = False
    widths = []
    for line in re.split(r"\n|\\l|\\p", text):
        prefix = "[japanese]" if japanese else ""
        widths.append(text_pixel_width(prefix + line, Charmap("ja")))
        for token in re.findall(r"\[(?:japanese|latin)\]", line):
            japanese = token == "[japanese]"
    return max(widths, default=0)


def build_report(source_audit, entries, binary_audit):
    if binary_audit["status"] != "PASS":
        raise ValueError("Full binary audit has not passed")
    by_id = {row["id"]: row for row in entries}
    binary_by_id = {row["id"]: row for row in binary_audit["entries"]}
    if len(by_id) != len(entries) or CLIPPED_ID in by_id or COMPLETE_ID not in by_id:
        raise ValueError("Duplicate input or incorrect difficulty warning")
    source_rows = source_audit["entries"]
    if len(source_rows) != 26:
        raise ValueError("Difficulty audit coverage changed")
    rows = []
    for source in source_rows:
        # This read-only audit predates the extractor fix. Its complete script
        # row is the same ROM string now owned by the menu_game_settings ID.
        entry_id = COMPLETE_ID if source["id"] == "scr_1F4E26F" else source["id"]
        entry = by_id.get(entry_id)
        binary = binary_by_id.get(entry_id)
        if entry is None or binary is None:
            raise ValueError(f"Difficulty text is not injected: {entry_id}")
        if (entry["original"] != source["original"] or
                int(entry["address"], 16) != int(source["rom_offset"], 16) or
                int(entry["byte_length"]) != source["slot_size"]):
            raise ValueError(f"Difficulty source metadata changed: {entry_id}")
        owners = entry.get("pointer_sources", [])
        if len(owners) != binary["pointer_owners"]:
            raise ValueError(f"Difficulty pointer ownership differs: {entry_id}")
        if binary["placement"] == "relocated" and not owners:
            raise ValueError(f"Unowned difficulty relocation: {entry_id}")
        translated = strip_hma_quotes(entry["translated"])
        row = {
            "id": entry_id,
            "runtime_role": source["runtime_role"],
            "category": entry["category"],
            "original": source["original"],
            "japanese": translated,
            "rom_offset": source["rom_offset"],
            "gba_address": source["gba_address"],
            "slot_size": source["slot_size"],
            "encoded_bytes": binary["destination_size"],
            "pixel_width_max_line": max_line_width(translated),
            "pointer_owners": owners,
            "placement": binary["placement"],
            "destination_rom_offset": binary.get("destination", source["rom_offset"]),
            "destination_gba_address": f"0x{0x08000000 + int(binary.get('destination', source['rom_offset']), 16):08X}",
            "runtime_visual_status": "mGBA confirmation pending",
        }
        rows.append(row)
    choices = [row for row in rows if row["id"] in BATTLE_CHOICES]
    if len(choices) != 4 or {row["id"] for row in choices} != set(BATTLE_CHOICES):
        raise ValueError("Incomplete Options battle choice set")
    return {
        "status": "PASS",
        "scope": "26 difficulty-related entries; full-ROM byte audit passed separately",
        "full_audit_output_sha256": binary_audit["output_sha256"],
        "entry_count": len(rows),
        "battle_choice_count": len(choices),
        "clipped_warning_excluded": True,
        "runtime_anchors": source_audit["runtime_anchors"],
        "entries": rows,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-audit", default="out/ja-phase5c-difficulty-audit.json")
    parser.add_argument("--controlfix", default="out/ja-phase5c-controlfix.json")
    parser.add_argument("--binary-audit", default="out/ja-phase5c-binary-audit.json")
    parser.add_argument("--output", default="out/ja-phase5c-difficulty-binary-audit.json")
    args = parser.parse_args()
    report = build_report(read(args.source_audit), read(args.controlfix)["entries"],
                          read(args.binary_audit))
    Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                                 encoding="utf-8")
    print(f"{report['status']}: {report['entry_count']} difficulty entries")


if __name__ == "__main__":
    main()
