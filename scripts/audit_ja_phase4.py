#!/usr/bin/env python3
"""Audit every byte changed by the bounded Japanese runtime ROM build."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib.pcs_text import Charmap
from lib.unbound_free_space import VETTED_FREE_SPACE_RANGES

EXPECTED_MD5 = "9cad8e771940e7f7094d13911552cef0"
# Keep in sync with the injector's FREE_SPACE_EXCLUDE_RANGES. These spans
# include legacy engine text/code and CFRU/high-bank runtime assets.
RESERVED_ROM_RANGES = (
    (0x160000, 0x200000),
    (0x230000, 0x500000),
    (0x1000000, 0x2000000),
)
ROUTE_EVIDENCE = {
    "intro": "NEW GAME intro script operand; branch still needs playthrough",
    "npc": "Owned NPC/event script operand; exact map/event reachability not independently confirmed",
    "battle": "Battle-message pointer in active message bank; trigger the matching battle event",
    "menu": "Menu pointer field; open the corresponding current UI screen",
    "mission": "Mission Log or mission-table pointer; requires the corresponding mission state",
    "pokemon": "Fixed species-name table row; encounter or view this species",
    "moves": "Fixed move-name table row; use or inspect this move",
    "items": "Fixed item-name table row; obtain or inspect this item",
}


def addr(value):
    return int(value, 16)


def compact_ranges(offsets):
    if not offsets:
        return []
    offsets = sorted(offsets)
    ranges = []
    start = end = offsets[0]
    for offset in offsets[1:]:
        if offset == end + 1:
            end = offset
        else:
            ranges.append(f"{start:08X}-{end:08X}")
            start = offset
        end = offset
    ranges.append(f"{start:08X}-{end:08X}")
    return ranges


def audit(original, output, entries, selection, injection_map):
    if len(original) != len(output) or hashlib.md5(original).hexdigest() != EXPECTED_MD5:
        raise ValueError("Source ROM size or MD5 differs from the verified baseline")
    rows = selection["entries"]
    selected = {entry["id"]: entry for entry in entries}
    relocated = {row["id"]: row for row in injection_map["relocations"]}
    if len(selected) != len(rows) or len(relocated) != injection_map["stats"]["relocated"]:
        raise ValueError("Entry or relocation count mismatch")

    stats = injection_map["stats"]
    must_be_zero = (
        "encode_errors", "skipped_pointer_mismatch", "skipped_implausible_pointer",
        "skipped_no_space", "fixed_truncated", "no_relocation_truncated",
        "ability_descriptions_compacted", "runtime_patches", "graphics_patches",
    )
    if any(stats[key] for key in must_be_zero):
        raise ValueError({key: stats[key] for key in must_be_zero if stats[key]})
    if injection_map["missing_relocations"] or injection_map["missing_fixed_slots"]:
        raise ValueError("Unplaced relocation or fixed-slot failure")
    if stats["input_entries"] != len(rows) or stats["in_place"] + stats["relocated"] != len(rows):
        raise ValueError("Not every selected entry was applied")
    if injection_map["used_free_bytes"] != stats["relocated_bytes"]:
        raise ValueError("Free-space accounting differs from relocated payload bytes")

    ownership = {}
    cmap = Charmap("ja")
    report_rows = []
    all_pointer_sources = set()
    for row in rows:
        entry = selected[row["id"]]
        old = addr(entry["address"])
        slot = int(entry["byte_length"])
        payload = cmap.encode(entry["translated"])
        relocation = relocated.get(row["id"])
        expected = "relocation" if len(payload) > slot else "in-place"
        if row.get("expected") and row["expected"] != expected:
            raise ValueError(f"Expected placement changed: {row['id']}")
        if (relocation is not None) != (expected == "relocation"):
            raise ValueError(f"Actual placement differs: {row['id']}")
        pointer_sources = [addr(pointer) for pointer in entry.get("pointer_sources", [])]

        if relocation:
            if relocation["storage"] != "vetted_ff":
                raise ValueError(f"Unvetted destination: {row['id']}")
            dest = addr(relocation["new_offset"])
            if not any(start <= dest and dest + len(payload) <= end for start, end in VETTED_FREE_SPACE_RANGES):
                raise ValueError(f"Destination outside vetted FF: {row['id']}")
            if any(dest < end and start < dest + len(payload) for start, end in RESERVED_ROM_RANGES):
                raise ValueError(f"Destination overlaps reserved ROM: {row['id']}")
            if original[dest:dest + len(payload)] != bytes([0xFF]) * len(payload):
                raise ValueError(f"Destination was not FF: {row['id']}")
            if output[dest:dest + len(payload)] != payload or output[old:old + slot] != original[old:old + slot]:
                raise ValueError(f"Relocated payload or old slot differs: {row['id']}")
            if {addr(p) for p in relocation["pointer_sources"]} != set(pointer_sources):
                raise ValueError(f"Pointer-owner list differs: {row['id']}")
            for offset in range(dest, dest + len(payload)):
                if offset in ownership:
                    raise ValueError(f"Overlapping relocated byte ownership: {offset:X}")
                ownership[offset] = "relocated text"
            old_pointer = (0x08000000 + old).to_bytes(4, "little")
            new_pointer = (0x08000000 + dest).to_bytes(4, "little")
            for source in pointer_sources:
                if source in all_pointer_sources:
                    raise ValueError(f"Overlapping pointer owners: {row['id']}")
                all_pointer_sources.add(source)
                if original[source:source + 4] != old_pointer or output[source:source + 4] != new_pointer:
                    raise ValueError(f"Pointer content differs: {row['id']} at {source:X}")
                for offset in range(source, source + 4):
                    if offset in ownership:
                        raise ValueError(f"Overlapping byte ownership: {offset:X}")
                    ownership[offset] = "pointer writes"
            if output.find(old_pointer) != -1:
                raise ValueError(f"Old pointer remains in output: {row['id']}")
        else:
            if len(payload) > slot or output[old:old + slot] != payload + bytes([0xFF]) * (slot - len(payload)):
                raise ValueError(f"In-place slot content differs: {row['id']}")
            for offset in range(old, old + slot):
                if offset in ownership:
                    raise ValueError(f"Overlapping byte ownership: {offset:X}")
                ownership[offset] = "in-place text"
            for source in pointer_sources:
                if original[source:source + 4] != output[source:source + 4]:
                    raise ValueError(f"In-place pointer changed: {row['id']}")

        report_rows.append({
            "id": row["id"], "category": entry["category"],
            "original": entry["original"], "japanese": entry["translated"],
            "rom_offset": f"0x{old:08X}", "gba_address": f"0x{0x08000000 + old:08X}",
            "slot_size": slot, "encoded_size": len(payload),
            "pointer_owners": [f"0x{source:08X}" for source in pointer_sources],
            "owner_context": (
                f"{entry['table_name']}[{entry['table_index']}]"
                if "table_name" in entry and "table_index" in entry else "script operand"
            ),
            "runtime_evidence": (
                "Phase 3 mGBA confirmed this NEW GAME selection prompt"
                if row["id"] in {"scr_1F0F7EC", "scr_1F0F800", "scr_1F0F814"}
                else ROUTE_EVIDENCE[row["route"]]
            ),
            "expected": expected, "actual": "relocation" if relocation else "in-place",
            "destination": relocation["new_offset"] if relocation else None,
            "origin": row.get("origin", "manual kana"),
        })

    changed = {offset for offset, pair in enumerate(zip(original, output)) if pair[0] != pair[1]}
    unowned = changed - ownership.keys()
    if unowned:
        raise ValueError(f"Unrelated ROM bytes changed: {compact_ranges(unowned)}")
    classified = {kind: sorted(offset for offset in changed if ownership[offset] == kind)
                  for kind in ("in-place text", "relocated text", "pointer writes")}
    return {
        "status": "PASS",
        "source_md5": hashlib.md5(original).hexdigest(),
        "output_md5": hashlib.md5(output).hexdigest(),
        "category_counts": dict(Counter(row["category"] for row in report_rows)),
        "entry_counts": {"in_place": stats["in_place"], "relocated": stats["relocated"],
                         "pointer_writes": stats["pointer_writes"]},
        "changed_bytes": {kind: {"count": len(offsets), "ranges": compact_ranges(offsets),
                                 "offsets": [f"0x{offset:08X}" for offset in offsets]}
                          for kind, offsets in classified.items()},
        "entries": report_rows,
    }


def markdown(report, rom_path="out/unbound-ja-phase4.gba"):
    lines = ["# Japanese Phase 4 runtime validation", "", "ROM byte audit: **PASS**. Runtime screens still need human confirmation.", "",
             "| ID | Category | Original | Japanese controlfixed | ROM / GBA | Slot / encoded | Pointer owners | Runtime evidence | Expected / actual |",
             "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for row in report["entries"]:
        safe = lambda value: str(value).replace("|", "\\|").replace("\n", "\\n")
        lines.append("| " + " | ".join((
            row["id"], row["category"], safe(row["original"]), safe(row["japanese"]),
            f"{row['rom_offset']} / {row['gba_address']}",
            f"{row['slot_size']} / {row['encoded_size']}",
            (", ".join(row["pointer_owners"]) or "fixed slot") +
            f" ({row['owner_context']})",
            safe(row["runtime_evidence"]),
            row["expected"] + " / " + row["actual"] +
            (f" → {row['destination']}" if row["destination"] else ""),
        )) + " |")
    lines.extend(("", "## ROM differences", ""))
    for kind, detail in report["changed_bytes"].items():
        lines.append(f"- {kind}: {detail['count']} changed bytes, {', '.join(detail['ranges'])}")
    lines.extend((
        "", "## mGBA check order", "",
        f"1. Boot `{rom_path}` with a fresh NEW GAME. Check the Borrius introduction, character/skin/hair/jacket/trim choices, name confirmation, and difficulty questions. Read through every line and page transition; retry the relevant answer branch for conditional questions.",
        "2. Finish the introduction. Open the pause menu and inspect Bag, Pokémon, Save, and Option. In Option, inspect Text Speed, Slow, and Fast. Open a Yes/No confirmation and the party screen.",
        "3. Inspect a Potion, Antidote, and Poké Ball in the Bag; inspect or encounter Bulbasaur, Pikachu, and Cacnea when available. Inspect Tackle, Cut, and Thunderbolt where learned or shown.",
        "4. Enter a normal battle. Check the next-Pokémon prompt on fainting and the poisoned/fainted/move-used messages when their conditions occur. Some messages need deliberately prepared battle states.",
        "5. Open the Mission Log after it becomes available. Check tabs, button icon, location buffer, reward instruction, and A Hero's/A Heroine's Journey when those missions are active.",
        "6. Talk to NPCs in the early towns and gyms. The selected NPC script operands are owned, but their exact map/event locations were not independently mapped; record any unreachable ID rather than treating its presence in the ROM as runtime proof.",
        "", "Check kana glyphs, English dynamic names, colors, scroll/page advance, selection transitions, and save/load. No runtime result is implied by the binary audit.",
    ))
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_rom")
    parser.add_argument("output_rom")
    parser.add_argument("controlfixed_json")
    parser.add_argument("selection_json")
    parser.add_argument("injector_map")
    parser.add_argument("--report", required=True)
    parser.add_argument("--markdown", required=True)
    args = parser.parse_args()
    entries = json.loads(Path(args.controlfixed_json).read_text(encoding="utf-8"))["entries"]
    selection = json.loads(Path(args.selection_json).read_text(encoding="utf-8"))
    injection_map = json.loads(Path(args.injector_map).read_text(encoding="utf-8"))
    report = audit(Path(args.source_rom).read_bytes(), Path(args.output_rom).read_bytes(),
                   entries, selection, injection_map)
    Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    Path(args.markdown).write_text(markdown(report, args.output_rom), encoding="utf-8")
    print(f"{report['status']}: {len(report['entries'])} entries; "
          f"{report['entry_counts']['in_place']} in-place, "
          f"{report['entry_counts']['relocated']} relocated, "
          f"{report['entry_counts']['pointer_writes']} pointer writes")
    for kind, detail in report["changed_bytes"].items():
        print(f"{kind}: {detail['count']} changed bytes")


if __name__ == "__main__":
    main()
