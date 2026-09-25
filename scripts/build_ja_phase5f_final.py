#!/usr/bin/env python3
"""Merge one reviewed bulb dialogue and its two local buffer literals."""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib.pcs_text import Charmap
from lib.translation_tokens import semantic_token_counts, strip_hma_quotes


ROOT = Path(__file__).resolve().parents[1]
BODY_ID = "scr_1F1A99A"
VALUES = {"scr_1F1A9C6": ("on", "オン", 3),
          "scr_1F1A9C9": ("off", "オフ", 4)}
EXPECTED_BODY = "なにかの でんきゅうの ようだ。 [green][buffer1][black]に しますか？"
KANJI = re.compile(r"[\u3400-\u9fff\uf900-\ufaff]")


def read(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def write(path, data):
    (ROOT / path).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def pointer_hits(rom: bytes, target: int) -> list[int]:
    pointer = (0x08000000 + target).to_bytes(4, "little")
    hits = []
    cursor = 0
    while (cursor := rom.find(pointer, cursor)) >= 0:
        hits.append(cursor)
        cursor += 1
    return hits


def build(review, phase5e, prepared, extracted, rom):
    if len(review) != 1 or review[0]["id"] != BODY_ID or review[0]["status"] != "needs_technical_fit":
        raise ValueError("Claude review must contain exactly the held bulb dialogue")
    reviewed = review[0]
    if reviewed["reviewed_japanese"] != EXPECTED_BODY or KANJI.search(EXPECTED_BODY):
        raise ValueError("Unapproved or non-kana bulb wording")
    baseline = list(phase5e["entries"])
    baseline_ids = {row["id"] for row in baseline}
    if len(baseline) != len(baseline_ids) or len(baseline) != 674:
        raise ValueError("Phase 5E baseline changed")
    target_ids = {BODY_ID, *VALUES}
    if baseline_ids & target_ids:
        raise ValueError("Bulb entries already translated in Phase 5E")
    prepared_by_id = {row["id"]: row for row in prepared["entries"]}
    extracted_by_id = {row["id"]: row for row in extracted["entries"]}
    source = prepared_by_id[BODY_ID]
    if source["original"] != reviewed["original"]:
        raise ValueError("Claude source text differs from prepared source")
    original = strip_hma_quotes(source["original"])
    if semantic_token_counts(original) != semantic_token_counts(EXPECTED_BODY):
        raise ValueError("Protected/control token mismatch")
    if [token for token in ("[green]", "[buffer1]", "[black]") if EXPECTED_BODY.count(token) != 1]:
        raise ValueError("Required bulb tokens changed")
    if not (EXPECTED_BODY.index("[green]") < EXPECTED_BODY.index("[buffer1]") < EXPECTED_BODY.index("[black]")):
        raise ValueError("Bulb token order changed")

    codec = Charmap("ja")
    additions = []
    fit = []
    owner_audit = []
    for identifier in (BODY_ID, *VALUES):
        prepared_row = prepared_by_id[identifier]
        extracted_row = extracted_by_id[identifier]
        if (prepared_row["original"] != extracted_row["original"] or
                prepared_row["address"] != extracted_row["address"] or
                prepared_row["byte_length"] != extracted_row["byte_length"]):
            raise ValueError(f"Fresh extraction changed source identity: {identifier}")
        text = EXPECTED_BODY if identifier == BODY_ID else VALUES[identifier][1]
        if KANJI.search(text):
            raise ValueError(f"Kanji in {identifier}")
        if identifier in VALUES:
            english, _, slot = VALUES[identifier]
            if strip_hma_quotes(prepared_row["original"]) != english or extracted_row["byte_length"] != slot:
                raise ValueError(f"Bulb value source/slot changed: {identifier}")
            if len(extracted_row["pointer_sources"]) != 5:
                raise ValueError(f"Incomplete bufferstring owners: {identifier}")
        elif len(extracted_row["pointer_sources"]) != 10:
            raise ValueError("Incomplete dialogue owners")
        target = int(extracted_row["address"], 16)
        owners = sorted(int(value, 16) for value in extracted_row["pointer_sources"])
        if pointer_hits(rom, target) != owners:
            raise ValueError(f"Whole-ROM exact pointer set incomplete: {identifier}")
        if identifier in VALUES:
            if any(rom[owner - 2:owner] != b"\x85\x00" or
                   rom[owner + 4:owner + 6] != b"\x0f\x00" or
                   int.from_bytes(rom[owner + 6:owner + 10], "little") != 0x08000000 + 0x1F1A99A
                   for owner in owners):
                raise ValueError(f"Buffer-to-dialogue command path changed: {identifier}")
            if any(pointer_hits(rom, target + interior) for interior in range(1, slot)):
                raise ValueError(f"Interior pointer found: {identifier}")
        elif any(rom[owner - 2:owner] != b"\x0f\x00" for owner in owners):
            raise ValueError("Dialogue owner no longer loadword opcode")
        owner_audit.append({"id": identifier, "exact_pointer_hits": [f"0x{x:X}" for x in owners],
                            "bufferstring_then_dialogue": identifier in VALUES,
                            "interior_pointer_hits": [] if identifier in VALUES else None})
        encoded = codec.encode("[japanese]" + text + "[latin]")
        slot = int(extracted_row["byte_length"])
        if extracted_row.get("no_relocation") or not extracted_row["pointer_sources"]:
            raise ValueError(f"Unsafe relocation ownership: {identifier}")
        entry = {**prepared_row, "pointer_sources": extracted_row["pointer_sources"],
                 "is_pointer_based": True, "translated": text}
        additions.append(entry)
        fit.append({"id": identifier, "rom_offset": extracted_row["address"],
                    "gba_address": f"0x{0x08000000 + int(extracted_row['address'], 16):08X}",
                    "original": strip_hma_quotes(extracted_row["original"]),
                    "reviewed_japanese": text, "slot_size": slot,
                    "minimum_page_encoded_bytes": len(encoded),
                    "minimum_page_encoded_hex": encoded.hex(" "),
                    "expected_relocation": len(encoded) > slot,
                    "pointer_sources": extracted_row["pointer_sources"],
                    "context_scope": "bulb_toggle_buffer" if identifier in VALUES else "bulb_toggle_dialogue"})
    output = {"entries": baseline + additions}
    if len(output["entries"]) != 677:
        raise ValueError("Unexpected focused input count")
    audit = {"phase": "5F-final", "phase5e_applied": 674,
             "new_dialogue_entries": 1, "new_buffer_value_entries": 2,
             "total_applied": 677, "global_on_off_replacement": False,
             "source_review_rows": len(review), "fit": fit,
             "owner_audit": owner_audit}
    return output, audit


def main():
    output, audit = build(read("tests/fixtures/ja_phase5f_claude_review.json"),
                          read("out/ja-phase5e-reviewed-input.json"),
                          read("out/ja-phase5e-prepared.json"),
                          read("out/ja-phase5f-extracted.json"),
                          (ROOT / "rom/unbound.gba").read_bytes())
    write("out/ja-phase5f-final-reviewed-input.json", output)
    write("out/ja-phase5f-final-fit-audit.json", audit)
    counts = Counter("buffer" if row["id"] in VALUES else "dialogue" for row in output["entries"][-3:])
    print(f"Phase 5F input: {len(output['entries'])}; new {dict(counts)}")


if __name__ == "__main__":
    main()
