#!/usr/bin/env python3
"""PCS slot and measured glyph-width preflight for Batch 01."""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.gen3_font import NORMAL_GLYPH_WIDTHS, NORMAL_JAPANESE_GLYPH_WIDTHS, RUNTIME_BUFFER_WIDTH
from lib.pcs_text import Charmap, fc_arg_count, decode_pcs
from lib.translation_tokens import strip_hma_quotes

OUT = ROOT / "out/phase6"


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def line_widths(encoded):
    widths = []
    width = 0
    japanese = False
    index = 0
    while index < len(encoded):
        byte = encoded[index]
        index += 1
        if byte == 0xFF:
            break
        if byte == 0xFC:
            command = encoded[index]
            index += 1 + fc_arg_count(command)
            if command == 0x15:
                japanese = True
            elif command == 0x16:
                japanese = False
            continue
        if byte == 0xFD:
            index += 1
            width += RUNTIME_BUFFER_WIDTH
            continue
        if byte in (0xFE, 0xFA, 0xFB):
            widths.append(width)
            width = 0
            continue
        if byte in (0xF7, 0xF8, 0xF9):
            index += 1
            continue
        width += (10 if byte == 0 else NORMAL_JAPANESE_GLYPH_WIDTHS[byte]) if japanese else NORMAL_GLYPH_WIDTHS[byte]
    widths.append(width)
    return widths


def build():
    selection = {row["id"]: row for row in read(ROOT / "tests/fixtures/ja_phase6_selection.json")["entries"]}
    reviewed = read(OUT / "ja_phase6_batch01_reviewed.json")["entries"]
    controlfixed = {row["id"]: row for row in read(OUT / "ja_phase6_batch01_controlfix.json")["entries"]}
    relocations = {row["id"]: row for row in read(OUT / "ja_phase6_batch01_map.json")["relocations"]}
    rom = (ROOT / "rom/unbound.gba").read_bytes()
    injector = runpy.run_path(str(ROOT / "005_hybrid_injector.py"))
    codec = Charmap("ja")
    rows = []
    for review in reviewed:
        entry_id = review["id"]
        source = selection[entry_id]
        address = source["rom_offset"]
        original = rom[address:address + decode_pcs(rom, address, source["slot_size"]).byte_length]
        source_widths = line_widths(original)
        status = review["technical_status"]
        row = {"id": entry_id, "category": source["category"], "technical_status": status,
               "source_bytes": source["source_encoded_size"], "slot_size": source["slot_size"],
               "fixed": source["fixed"], "no_relocation": source["no_relocation"],
               "relocation_allowed": source["relocation_possible"],
               "pointer_owners": source["pointer_owners"],
               "source_max_line_pixels": max(source_widths),
               "source_line_count": len(source_widths),
               "renderer_width_limit_pixels": None,
               "renderer_width_evidence": "No exact choice/sign window bound proved for this script operand"}
        if status == "validated_for_controlfix":
            translated = controlfixed[entry_id]
            payload = injector["encode_text"](codec, injector["translation_for_injection"](translated),
                                               plain_script=source["category"] == "plain_scripts")
            widths = line_widths(payload)
            source_text = strip_hma_quotes(source["original"])
            positional = any(token in source_text for token in ("\\al", "\\ar", "\\au", "\\ad"))
            compact = source["slot_size"] <= 32 and "\n" not in source_text and "\\l" not in source_text
            row.update({"japanese_bytes": len(payload), "japanese_max_line_pixels": max(widths),
                        "japanese_line_count": len(widths),
                        "placement": "relocation" if entry_id in relocations else "in_place",
                        "width_status": ("positional_sign_unverified" if positional else
                                         "compact_label_growth_unverified" if compact and max(widths) > max(source_widths) else
                                         "within_source_max_line_pixels" if max(widths) <= max(source_widths) else
                                         "dialogue_window_unverified"),
                        "pixel_widths": widths})
            if len(payload) > source["slot_size"] and entry_id not in relocations:
                raise ValueError(f"Missing relocation: {entry_id}")
            if source["fixed"] and len(payload) > source["slot_size"]:
                raise ValueError(f"Fixed overflow applied: {entry_id}")
        else:
            row.update({"japanese_bytes": None, "japanese_max_line_pixels": None,
                        "japanese_line_count": None, "placement": "held_english",
                        "width_status": "not_measured_untranslated"})
        rows.append(row)
    counts = Counter(row["placement"] for row in rows)
    widths = Counter(row["width_status"] for row in rows)
    return {"metadata": {"reviewed": len(rows), "placement_counts": dict(counts),
                         "width_status_counts": dict(widths), "fixed_count": sum(row["fixed"] for row in rows),
                         "note": "Normal-font glyph advances are measured. Exact script choice/sign renderer width is not proven; growth is a QA risk, not a confirmed overflow."},
            "entries": rows}


def main():
    result = build()
    path = OUT / "ja_phase6_batch01_fit.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(result["metadata"])


if __name__ == "__main__":
    main()
