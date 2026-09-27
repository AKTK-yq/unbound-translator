#!/usr/bin/env python3
"""Bounded ROM evidence for six unproved Batch 01 substitutions."""

from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.pcs_text import decode_pcs
from scripts.build_ja_phase5c_handoff import operand_kind

IDS = ("scr_1F01267", "scr_1F012BD", "scr_1F016AD",
       "scr_1F02458", "scr_1F01914", "scr_1F0618A")


def build():
    rom = (ROOT / "rom/unbound.gba").read_bytes()
    extracted = {row["id"]: row for row in json.loads(
        (ROOT / "out/ja-phase5f-extracted.json").read_text(encoding="utf-8"))["entries"]}
    rows = []
    for entry_id in IDS:
        entry = extracted[entry_id]
        address = int(entry["address"], 16)
        raw = rom[address:address + entry["byte_length"]]
        owners = []
        for source in entry["pointer_sources"]:
            owner = int(source, 16)
            nearby = []
            for location in range(max(0, owner - 0x100), min(len(rom) - 6, owner + 0x100)):
                if rom[location] != 0x85 or rom[location + 1] > 2:
                    continue
                pointer = int.from_bytes(rom[location + 2:location + 6], "little")
                target = pointer - 0x08000000
                if not 0 <= target < len(rom):
                    continue
                decoded = decode_pcs(rom, target, 96)
                if not decoded.terminated or decoded.raw_count > 3:
                    continue
                nearby.append({"opcode_rom": f"0x{location:X}",
                               "buffer_index": rom[location + 1],
                               "literal_rom": f"0x{target:X}",
                               "literal": decoded.text[:90],
                               "distance_from_dialogue_owner": location - owner,
                               "confidence": "candidate opcode pattern; event control flow unproved"})
            owners.append({"rom_offset": source, "kind": operand_kind(rom, owner),
                           "surrounding_hex": rom[owner - 16:owner + 16].hex(" "),
                           "nearby_bufferstring_candidates": nearby})
        rows.append({"id": entry_id, "original": entry["original"],
                     "text_rom_offset": entry["address"],
                     "text_gba_address": f"0x{0x08000000 + address:08X}",
                     "source_bytes_hex": raw.hex(" "),
                     "owners": owners,
                     "conclusion": "Not proven: writer, all possible values, and Japanese grammar; keep English"})
    return {"metadata": {"count": len(rows),
                         "note": "Pattern candidates do not prove execution. FD 07/08/0C have no named PCS macro in lib/pcs_text.py."},
            "entries": rows}


def main():
    result = build()
    path = ROOT / "out/phase6/ja_phase6_batch01_buffer_evidence.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print({row["id"]: sum(len(owner["nearby_bufferstring_candidates"]) for owner in row["owners"])
           for row in result["entries"]})


if __name__ == "__main__":
    main()
