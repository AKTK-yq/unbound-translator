#!/usr/bin/env python3
"""Strict byte-ownership and relocation audit for the Phase 5B ROM."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import runpy
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib.pcs_text import Charmap
from lib.unbound_free_space import VETTED_FREE_SPACE_RANGES


SOURCE_MD5 = "9cad8e771940e7f7094d13911552cef0"


def offset(value):
    return int(value, 16) if isinstance(value, str) else int(value)


def compact_ranges(offsets):
    ordered = sorted(set(offsets))
    if not ordered:
        return []
    result = []
    start = end = ordered[0]
    for current in ordered[1:]:
        if current == end + 1:
            end = current
        else:
            result.append(f"0x{start:08X}-0x{end:08X}")
            start = end = current
    result.append(f"0x{start:08X}-0x{end:08X}")
    return result


def classify_changed_bytes(source, output, ownership):
    if len(source) != len(output):
        raise ValueError("ROM size changed")
    changed = {i for i, (before, after) in enumerate(zip(source, output)) if before != after}
    unexpected = changed - ownership.keys()
    if unexpected:
        raise ValueError(f"Unrelated ROM bytes changed: {compact_ranges(unexpected)}")
    return {kind: {"count": len(addresses), "ranges": compact_ranges(addresses)}
            for kind, addresses in ((kind, [i for i in changed if ownership[i] == kind])
                                    for kind in ("in-place text", "relocated text", "pointer writes"))}


def remaining_spans(blocks, allocations):
    spans = []
    for block in blocks:
        cursor = block.start
        for start, end in allocations:
            if end <= block.start or start >= block.end:
                continue
            if start < cursor:
                if end > cursor:
                    raise ValueError("Overlapping relocation allocations")
                continue
            if start > cursor:
                spans.append((cursor, start))
            cursor = end
        if cursor < block.end:
            spans.append((cursor, block.end))
    return spans


def audit(source, output, entries, injection_map, injector=None):
    if hashlib.md5(source).hexdigest() != SOURCE_MD5:
        raise ValueError("Source ROM MD5 differs from required baseline")
    injector = injector or runpy.run_path(str(Path(__file__).resolve().parents[1] / "005_hybrid_injector.py"))
    stats = injection_map["stats"]
    bad = ("encode_errors", "skipped_pointer_mismatch", "skipped_implausible_pointer",
           "skipped_no_space", "fixed_truncated", "no_relocation_truncated",
           "ability_descriptions_compacted", "runtime_patches", "graphics_patches",
           "skipped_bounds", "skipped_unsafe", "skipped_duplicate_fixed")
    failures = {key: stats[key] for key in bad if stats[key]}
    if failures or injection_map["missing_relocations"] or injection_map["missing_fixed_slots"]:
        raise ValueError(f"Unsafe injector result: {failures}; missing allocation/fit")
    if injection_map["runtime_patches"] or injection_map["graphics_patches"]:
        raise ValueError("Unexpected runtime or graphics patch")
    if stats["input_entries"] != len(entries) or stats["in_place"] + stats["relocated"] != len(entries):
        raise ValueError("Not every resolved entry was injected")
    if stats["free_bytes"] != stats["vetted_free_bytes"] or injection_map["used_reclaimed_text_bytes"]:
        raise ValueError("Non-vetted relocation storage used")

    cmap = Charmap("ja")
    relocated = {item["id"]: item for item in injection_map["relocations"]}
    if len(relocated) != stats["relocated"]:
        raise ValueError("Relocation map duplicate/count mismatch")
    destination_groups = defaultdict(list)
    for item in injection_map["relocations"]:
        destination_groups[(offset(item["new_offset"]), item["byte_length"])].append(item)
    for group in destination_groups.values():
        if len(group) > 1 and sum(not item.get("shared_payload") for item in group) != 1:
            raise ValueError("Shared relocation has no unique primary payload")
    ownership = {}
    allocations = {}
    pointer_sources = set()
    rows = []
    for entry in entries:
        entry_id = entry["id"]
        old = offset(entry["address"])
        slot = int(entry["byte_length"])
        payload = injector["encode_text"](cmap, injector["translation_for_injection"](entry),
                                           plain_script=entry.get("category") == "plain_scripts")
        owners = [offset(item) for item in entry.get("pointer_sources", [])]
        reloc = relocated.get(entry_id)
        if (len(payload) > slot) != bool(reloc):
            raise ValueError(f"Wrong in-place/relocation choice: {entry_id}")
        row = {"id": entry_id, "category": entry["category"], "source": f"0x{old:08X}",
               "slot_size": slot, "destination_size": len(payload), "pointer_owners": len(owners),
               "placement": "relocated" if reloc else "in-place"}
        if reloc:
            dest = offset(reloc["new_offset"])
            end = dest + len(payload)
            row["destination"] = f"0x{dest:08X}"
            if reloc["storage"] != "vetted_ff" or reloc["byte_length"] != len(payload):
                raise ValueError(f"Unvetted/inaccurate destination: {entry_id}")
            if not any(start <= dest and end <= stop for start, stop in VETTED_FREE_SPACE_RANGES):
                raise ValueError(f"Relocation outside vetted FF: {entry_id}")
            if any(start <= dest < stop or start < end <= stop or dest <= start and stop <= end
                   for start, stop in injector["FREE_SPACE_EXCLUDE_RANGES"]):
                raise ValueError(f"Relocation in reserved code/font region: {entry_id}")
            if source[dest:end] != b"\xff" * len(payload) or output[dest:end] != payload:
                raise ValueError(f"Relocated bytes differ: {entry_id}")
            if output[old:old + slot] != source[old:old + slot]:
                raise ValueError(f"Old slot changed after relocation: {entry_id}")
            key = (dest, end)
            if key in allocations:
                if allocations[key] != payload:
                    raise ValueError(f"Unexpected shared destination: {entry_id}")
            else:
                if any(dest < existing_end and existing_start < end for existing_start, existing_end in allocations):
                    raise ValueError(f"Overlapping destinations: {entry_id}")
                allocations[key] = payload
                for i in range(dest, end):
                    if i in ownership:
                        raise ValueError(f"Overlapping relocation byte: {i:X}")
                    ownership[i] = "relocated text"
            if set(owners) != {offset(value) for value in reloc["pointer_sources"]}:
                raise ValueError(f"Pointer owner list mismatch: {entry_id}")
            old_ptr = (0x08000000 + old).to_bytes(4, "little")
            new_ptr = (0x08000000 + dest).to_bytes(4, "little")
            for owner in owners:
                if owner in pointer_sources:
                    raise ValueError(f"Duplicate pointer owner: {owner:X}")
                pointer_sources.add(owner)
                if source[owner:owner + 4] != old_ptr or output[owner:owner + 4] != new_ptr:
                    raise ValueError(f"Pointer write mismatch: {entry_id} owner {owner:X}")
                for i in range(owner, owner + 4):
                    if i in ownership:
                        raise ValueError(f"Overlapping pointer byte: {i:X}")
                    ownership[i] = "pointer writes"
            # An old pointer may indicate an unowned live reference; reject
            # it rather than silently accepting an incomplete relocation.
            if output.find(old_ptr) != -1:
                raise ValueError(f"Old pointer remains: {entry_id}")
        else:
            expected = injector["fit_to_slot"](payload, slot, 0xFF)
            if output[old:old + slot] != expected:
                raise ValueError(f"In-place bytes differ: {entry_id}")
            for i in range(old, old + slot):
                if i in ownership:
                    raise ValueError(f"Overlapping in-place byte: {i:X}")
                ownership[i] = "in-place text"
            for owner in owners:
                if source[owner:owner + 4] != output[owner:owner + 4]:
                    raise ValueError(f"In-place pointer changed: {entry_id}")
        rows.append(row)

    if len(pointer_sources) != stats["pointer_writes"]:
        raise ValueError("Pointer-write count mismatch")
    unique_bytes = sum(end - start for start, end in allocations)
    if unique_bytes != injection_map["used_vetted_bytes"]:
        raise ValueError("Vetted FF consumption does not equal unique allocations")
    free_blocks = injector["build_free_blocks"](
        source, entries, injector["DEFAULT_MIN_FREE_RUN"], injector["DEFAULT_MIN_ADDRESS"],
        allowed_ranges=VETTED_FREE_SPACE_RANGES)
    if sum(block.end - block.start for block in free_blocks) != stats["vetted_free_bytes"]:
        raise ValueError("Vetted free-block capacity differs from injector")
    spans = remaining_spans(free_blocks, sorted(allocations))
    if sum(end - start for start, end in spans) != injection_map["remaining_free_bytes"]:
        raise ValueError("Remaining vetted FF differs from injector")
    changes = classify_changed_bytes(source, output, ownership)
    by_category = defaultdict(Counter)
    for row in rows:
        by_category[row["category"]][row["placement"]] += 1
    return {"status": "PASS", "source_md5": hashlib.md5(source).hexdigest(),
            "output_md5": hashlib.md5(output).hexdigest(),
            "output_sha256": hashlib.sha256(output).hexdigest(),
            "input_entries": len(entries), "in_place": stats["in_place"],
            "relocated": stats["relocated"], "pointer_writes": stats["pointer_writes"],
            "relocated_bytes": stats["relocated_bytes"],
            "unique_relocated_bytes": unique_bytes,
            "vetted_ff_total": stats["vetted_free_bytes"],
            "vetted_ff_consumed": injection_map["used_vetted_bytes"],
            "vetted_ff_remaining": injection_map["remaining_free_bytes"],
            "largest_remaining_span": max((end - start for start, end in spans), default=0),
            "changed_bytes": changes,
            "category_placements": {key: dict(value) for key, value in by_category.items()},
            "entries": rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_rom")
    parser.add_argument("output_rom")
    parser.add_argument("resolved_json")
    parser.add_argument("injector_map")
    parser.add_argument("--report", default="out/ja-phase5b-binary-audit.json")
    args = parser.parse_args()
    entries = json.loads(Path(args.resolved_json).read_text(encoding="utf-8"))["entries"]
    injection_map = json.loads(Path(args.injector_map).read_text(encoding="utf-8"))
    report = audit(Path(args.source_rom).read_bytes(), Path(args.output_rom).read_bytes(),
                   entries, injection_map)
    Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{report['status']}: {report['in_place']} in-place, {report['relocated']} relocated, "
          f"{report['pointer_writes']} pointers; {report['vetted_ff_consumed']} vetted FF bytes")


if __name__ == "__main__":
    main()
