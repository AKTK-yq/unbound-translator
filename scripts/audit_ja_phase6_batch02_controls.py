#!/usr/bin/env python3
"""ROM-backed FA scroll and dynamic-buffer evidence for Batch 02."""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.pcs_text import decode_pcs
from lib.translation_tokens import strip_hma_quotes
from scripts.build_ja_phase5c_handoff import operand_kind

ROM = ROOT / "rom/unbound.gba"
REVIEW = ROOT / "tests/fixtures/ja_phase6_batch02_claude_review.json"
SELECTION = ROOT / "tests/fixtures/ja_phase6_selection.json"
OUT = ROOT / "out/phase6"
RAW_SUFFIX = re.compile(r"\\\\(?:07|08|0C)")


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def scroll_semantics(rom):
    # RenderText subtracts F8 for its F8..FF dispatch. FA is jump-table index 2.
    if rom[0x584A:0x5850] != bytes.fromhex("f8 38 07 28 00 d9"):
        raise ValueError("RenderText special-byte dispatch anchor changed")
    targets = {f"0x{code:02X}": f"0x{int.from_bytes(rom[0x5860 + 4 * (code - 0xF8):0x5864 + 4 * (code - 0xF8)], 'little'):08X}"
               for code in (0xFA, 0xFB, 0xFE)}
    if targets != {"0xFA": "0x08005B26", "0xFB": "0x08005B22", "0xFE": "0x08005880"}:
        raise ValueError(f"Unexpected RenderText dispatch: {targets}")
    if rom[0x5B22:0x5B2A] != bytes.fromhex("02 20 00 e0 03 20 30 77"):
        raise ValueError("Scroll/clear state-store anchor changed")
    return {"rom_render_text": "0x00005790", "gba_render_text": "0x08005790",
            "dispatch_rom": "0x00005848", "jump_table_rom": "0x00005860",
            "targets": targets, "handler_bytes_rom_0x5B22": rom[0x5B22:0x5B2A].hex(" "),
            "semantics": "FA waits for button press, then scrolls dialogue by one line; FB waits and clears, FE newline",
            "basis": "Unbound ROM dispatch/state bytes plus pret/pokefirered src/text.c CHAR_PROMPT_SCROLL reference"}


def scroll_rows(review, selection, rom):
    rows = []
    for row in review:
        if "control_placement_review_required" not in row["review_warning"]:
            continue
        source = selection[row["id"]]
        offset = source["rom_offset"]
        raw = rom[offset:offset + source["slot_size"]]
        decoded = decode_pcs(rom, offset, source["slot_size"])
        original = row["original"]
        target = row["reviewed_japanese"]
        source_positions = [i for i in range(len(original)) if original.startswith("\\l", i)]
        target_positions = [i for i in range(len(target)) if target.startswith("\\l", i)]
        if (decoded.text != strip_hma_quotes(original) or raw.count(0xFA) != len(source_positions)
                or (target and len(source_positions) != len(target_positions))):
            raise ValueError(f"FA/source/review count mismatch: {row['id']}")
        if not source_positions or source_positions[-1] >= len(original) - 3:
            raise ValueError(f"Expected mid-text FA in {row['id']}")
        rows.append({"id": row["id"], "rom_offset": f"0x{offset:08X}",
                     "gba_address": source["gba_address"], "pointer_owners": source["pointer_owners"],
                     "raw_source_bytes": raw.hex(" "), "decoded_original": decoded.text,
                     "source_fa_byte_positions": [i for i, b in enumerate(raw) if b == 0xFA],
                     "source_text_positions": source_positions, "target_text_positions": target_positions,
                     "source_neighbors": [original[max(0, i - 36):i + 38] for i in source_positions],
                     "target_neighbors": [target[max(0, i - 36):i + 38] for i in target_positions],
                     "renderer_group": source["renderer_group"],
                     "renderer_evidence": source["runtime_evidence"],
                     "source_owner_kinds": [operand_kind(rom, int(x, 16)) for x in source["pointer_owners"]],
                     "placement_class": "C", "safe_to_move_in_controlfix": False,
                     "reason": "The review appends source FA controls after translated prose; no reviewed semantic page boundary establishes the replacement position. Keep English."})
    if len(rows) != 30:
        raise ValueError(f"Expected 30 provisional FA entries, got {len(rows)}")
    return {"metadata": {"count": 30, "class_counts": {"C": 30},
                         "rule": "FA (\\l) is an interactive one-line scroll. Preserve placement at a reviewed semantic/page boundary; never append missing FA at end or move it automatically."},
            "rom_semantics": scroll_semantics(rom), "entries": rows}


def direct_literal(rom, owner):
    """Recognize only immediately adjacent bufferstring -> message/loadpointer."""
    if owner >= 7 and rom[owner - 1] == 0x67 and rom[owner - 7] == 0x85 and rom[owner - 6] <= 2:
        at = owner - 7
    elif owner >= 8 and rom[owner - 2] == 0x0F and rom[owner - 8] == 0x85 and rom[owner - 7] <= 2:
        at = owner - 8
    else:
        return None
    index = rom[at + 1]
    address = int.from_bytes(rom[at + 2:at + 6], "little") - 0x08000000
    if not 0 <= address < len(rom):
        return None
    decoded = decode_pcs(rom, address, 96)
    if not decoded.terminated or decoded.raw_count:
        return None
    return {"writer_opcode_rom": f"0x{at:08X}", "command": f"bufferstring {index}",
            "buffer": f"[buffer{index + 1}]", "source_rom": f"0x{address:08X}",
            "source_table": "script literal", "value": decoded.text,
            "evidence": "immediately adjacent bufferstring and message/loadpointer operand"}


def nearby_writers(rom, owner, radius=96):
    result = []
    for at in range(max(0, owner - radius), owner):
        if rom[at] != 0x85 or rom[at + 1] > 2:
            continue
        address = int.from_bytes(rom[at + 2:at + 6], "little") - 0x08000000
        if not 0 <= address < len(rom):
            continue
        decoded = decode_pcs(rom, address, 96)
        if decoded.terminated and decoded.raw_count <= 2:
            result.append({"writer_opcode_rom": f"0x{at:08X}",
                           "buffer": f"[buffer{rom[at + 1] + 1}]", "source_rom": f"0x{address:08X}",
                           "value": decoded.text[:90], "distance": owner - at,
                           "confidence": "pattern candidate only; branch/control-flow unproved"})
    return result


def grammar_hints(original):
    hints = []
    lower = original.casefold()
    if RAW_SUFFIX.search(original):
        hints.append("raw FD suffix/modifier; expansion and plural grammar unproved")
    if any(x in lower for x in (" time\\\\07", " purchase\\\\07", " item\\\\07", " point\\\\07")):
        hints.append("English plural-s candidate adjacent to raw suffix")
    if any(x in lower for x in (" son", " daughter", " his ", " her ", " a ", " an ")):
        hints.append("English gender/article grammar may be context-sensitive")
    if any(x in lower for x in ("[buffer1]%", "[buffer2]%", " coins", " minutes", " times", " purchases")):
        hints.append("numeric role suggested by source prose; writer not proved")
    return hints


def buffer_rows(review, selection, rom):
    rows = []
    for row in review:
        if "unknown_buffer" not in row["review_warning"]:
            continue
        source = selection[row["id"]]
        tokens = sorted(set(source["buffers"]))
        owners = []
        for value in source["pointer_owners"]:
            owner = int(value, 16)
            owners.append({"rom_offset": value, "kind": operand_kind(rom, owner),
                           "nearby_hex": rom[max(0, owner - 12):owner + 8].hex(" "),
                           "direct_writer": direct_literal(rom, owner),
                           "nearby_writer_candidates": nearby_writers(rom, owner)})
        direct = [item["direct_writer"] for item in owners]
        raw_suffix = RAW_SUFFIX.findall(row["original"])
        # A single direct writer does not prove global value when other owners
        # exist, another buffer is present, or an FD suffix can alter grammar.
        if (tokens and not raw_suffix and owners and all(direct)
                and all(item["buffer"] == tokens[0] for item in direct)
                and len(tokens) == 1 and len({item["value"] for item in direct}) == 1):
            status = "resolved_value"
            values = [direct[0]["value"]]
            note = "All recorded call sites have same immediately adjacent literal writer; verify script reachability in runtime QA"
        elif any(direct):
            status = "runtime-dependent"
            values = sorted({item["value"] for item in direct if item})
            note = "Some adjacent literal writers seen, but all paths/buffers or suffix behavior are not proven"
        else:
            status = "unknown"
            values = []
            note = "No immediately adjacent literal writer proven; nearby byte patterns are not execution proof"
        rows.append({"id": row["id"], "original": row["original"],
                     "rom_offset": f"0x{source['rom_offset']:08X}", "gba_address": source["gba_address"],
                     "slot_size": source["slot_size"], "buffer_tokens": tokens,
                     "raw_suffix_tokens": raw_suffix, "grammar_hints": grammar_hints(row["original"]),
                     "writer_evidence": owners, "possible_values_proved": values,
                     "value_type": "script literal text" if status == "resolved_value" else "unproved",
                     "text_page": "producer-dependent; Japanese/Latin output page unproved",
                     "grammatical_role": "source prose only; Japanese form not approved",
                     "buffer_status": status, "notes": note})
    if len(rows) != 49:
        raise ValueError(f"Expected 49 unknown-buffer warnings, got {len(rows)}")
    return {"metadata": {"count": len(rows),
                         "status_counts": dict(Counter(row["buffer_status"] for row in rows)),
                         "rule": "Do not translate unresolved buffers or remove FD raw suffix tokens."},
            "entries": rows}


def main():
    rom = ROM.read_bytes()
    review = read(REVIEW)
    selection = {row["id"]: row for row in read(SELECTION)["entries"]}
    scroll = scroll_rows(review, selection, rom)
    buffers = buffer_rows(review, selection, rom)
    write(OUT / "ja_phase6_batch02_scroll_audit.json", scroll)
    write(OUT / "ja_phase6_batch02_buffer_audit.json", buffers)
    print({"scroll": scroll["metadata"], "buffers": buffers["metadata"]})


if __name__ == "__main__":
    main()
