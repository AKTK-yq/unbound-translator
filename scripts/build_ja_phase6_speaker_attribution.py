#!/usr/bin/env python3
"""Evidence-limited Phase 6C-3A ROM speaker attribution; never edits text."""

from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.pcs_text import decode_pcs

OUT = ROOT / "out/phase6"
SOURCE_MD5 = "9cad8e771940e7f7094d13911552cef0"
TRAINER_COUNT = 743
MAP_SECTION_COUNT = 109
MAJOR_NAMES = {
    "Aklove", "Alice", "Benjamin", "Big Mo", "Galavan", "Ivory", "Jax",
    "Marlon", "Mel", "Mirskle", "Tessy", "Zeph",
}
UNBOUND_SPECIFIC_CLASSES = {"Light of Ruin Leader", "Light of Ruin Admin", "Shadow Admin"}
SPEAKER_CATEGORIES = {
    "CANON_CHARACTER", "UNBOUND_ORIGINAL", "GENERIC_NPC", "TRAINER_CLASS",
    "UNKNOWN_SPEAKER", "NON_DIALOGUE",
}


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def gba_pointer(rom: bytes, offset: int) -> int | None:
    if not 0 <= offset <= len(rom) - 4:
        return None
    value = int.from_bytes(rom[offset:offset + 4], "little")
    return value - 0x08000000 if 0x08000000 <= value < 0x08000000 + len(rom) else None


def valid_map_header(rom: bytes, offset: int) -> bool:
    if not 0 <= offset <= len(rom) - 28:
        return False
    layout, events = gba_pointer(rom, offset), gba_pointer(rom, offset + 4)
    if layout is None or events is None:
        return False
    scripts_word = rom[offset + 8:offset + 12]
    if scripts_word != bytes(4) and gba_pointer(rom, offset + 8) is None:
        return False
    connections_word = rom[offset + 12:offset + 16]
    if connections_word != bytes(4) and gba_pointer(rom, offset + 12) is None:
        return False
    if rom[offset + 20] >= MAP_SECTION_COUNT or rom[offset + 23] > 15:
        return False
    width = int.from_bytes(rom[layout:layout + 4], "little")
    height = int.from_bytes(rom[layout + 4:layout + 8], "little")
    if not 1 <= width <= 255 or not 1 <= height <= 255:
        return False
    if gba_pointer(rom, layout + 8) is None or gba_pointer(rom, layout + 12) is None:
        return False
    counts = rom[events:events + 4]
    if len(counts) != 4 or any(count > 60 for count in counts):
        return False
    return all(not count or gba_pointer(rom, events + 4 + 4 * index) is not None
               for index, count in enumerate(counts))


def scan_map_objects(rom: bytes):
    """Accept header only with structured fields and a literal table reference."""
    headers = set()
    for offset in range(0, len(rom) - 28, 4):
        if rom[offset + 3] not in (8, 9) or rom[offset + 7] not in (8, 9):
            continue
        if valid_map_header(rom, offset):
            headers.add(offset)
    references = defaultdict(list)
    for offset in range(0, len(rom) - 4, 4):
        if rom[offset + 3] not in (8, 9):
            continue
        target = gba_pointer(rom, offset)
        if target in headers:
            references[target].append(offset)
    accepted = {header for header in headers if references[header]}
    # Known independent Unbound map/event anchors are a structural regression.
    assert {0x34FB28, 0x3513A8} <= accepted
    objects = []
    for header in sorted(accepted):
        events = gba_pointer(rom, header + 4)
        count = rom[events]
        start = gba_pointer(rom, events + 4)
        if not count or start is None or start + count * 0x18 > len(rom):
            continue
        for index in range(count):
            record = start + index * 0x18
            script = gba_pointer(rom, record + 0x10)
            if script is None:
                continue
            objects.append({
                "map_header_offset": f"0x{header:08X}",
                "map_header_pointer_sources": [f"0x{x:08X}" for x in references[header]],
                "map_events_offset": f"0x{events:08X}",
                "object_record_offset": f"0x{record:08X}",
                "object_index": index,
                "local_object_id": rom[record],
                "graphics_id": rom[record + 1],
                "coordinates": [int.from_bytes(rom[record + 4:record + 6], "little", signed=True),
                                int.from_bytes(rom[record + 6:record + 8], "little", signed=True)],
                "script_offset": f"0x{script:08X}",
                "region_section_id": rom[header + 20],
                "map_id": None,  # Master group-index table is not proved here.
            })
    return objects, {"structured_header_candidates": len(headers),
                     "pointer_referenced_headers": len(accepted),
                     "object_script_bindings": len(objects)}


def map_section_name(rom: bytes, section: int) -> str | None:
    source = 0x3F1CAC + section * 4
    target = gba_pointer(rom, source)
    return decode_pcs(rom, target, 64).text if target is not None else None


def trainer_record(rom: bytes, trainer_id: int) -> dict | None:
    if not 0 <= trainer_id < TRAINER_COUNT:
        return None
    record = 0x23EAC8 + trainer_id * 40
    name = decode_pcs(rom, record + 4, 12).text.strip()
    class_id = rom[record + 1]
    if class_id >= 107 or not name:
        return None
    class_slot = 0x23E558 + class_id * 13
    class_pointer = gba_pointer(rom, class_slot)
    class_text = decode_pcs(rom, class_pointer if class_pointer is not None else class_slot, 48).text
    if not class_text:
        return None
    return {"trainer_id": trainer_id, "trainer_name": name, "trainer_class_id": class_id,
            "trainer_class": class_text, "trainer_pic_id": rom[record + 3],
            "record_offset": f"0x{record:08X}",
            "party_pointer_offset": f"0x{record + 0x24:08X}",
            "party_pointer": f"0x{gba_pointer(rom, record + 0x24):08X}"
            if gba_pointer(rom, record + 0x24) is not None else None}


def trainerbattle_owners(rom: bytes, owner: int, target: int) -> list[dict]:
    found = []
    for delta in (6, 10):  # Only first/second text operands; later words may be scripts.
        start = owner - delta
        if start < 0 or rom[start] != 0x5C or rom[start + 1] >= 16:
            continue
        if gba_pointer(rom, owner) != target:
            continue
        record = trainer_record(rom, int.from_bytes(rom[start + 2:start + 4], "little"))
        if record is None:
            continue
        found.append({**record, "opcode_offset": f"0x{start:08X}",
                      "text_operand_offset": f"0x{owner:08X}",
                      "text_operand_index": 0 if delta == 6 else 1,
                      "battle_mode": rom[start + 1],
                      "opcode_bytes": rom[start:owner + 4].hex(" ")})
    return found


def object_bindings(rom: bytes, objects: list[dict], owner: int, target: int):
    if gba_pointer(rom, owner) != target:
        return [], []
    direct, nearby = [], []
    for obj in objects:
        start = int(obj["script_offset"], 16)
        distance = owner - start
        if not 0 <= distance <= 0x80:
            continue
        note = {**obj, "text_operand_offset": f"0x{owner:08X}",
                "distance_to_operand": distance,
                "map_section_name": map_section_name(rom, obj["region_section_id"])}
        prefix = rom[start:owner - 2] if owner >= start + 2 else b""
        if (rom[owner - 2:owner] == b"\x0F\x00"
                and prefix in {b"", b"\x5A", b"\x6A\x5A", b"\x69\x5A"}
                and rom[owner + 4:owner + 6] in {b"\x09\x02", b"\x09\x06"}):
            note["script_bytes"] = rom[start:owner + 6].hex(" ")
            note["binding_kind"] = "direct_object_faceplayer_loadword_callstd"
            direct.append(note)
        else:
            note["binding_kind"] = "same_object_script_neighborhood_unparsed"
            nearby.append(note)
    return direct, nearby


def pointer_sources(row: dict) -> list[str]:
    if "preserved_metadata" in row:
        return row["preserved_metadata"].get("pointer_owners") or []
    return row.get("pointer_sources") or []


def text_offset(row: dict) -> int:
    if "preserved_metadata" in row:
        return row["preserved_metadata"]["rom_offset"]
    return int(row["address"], 16)


def attribute(rom: bytes, objects: list[dict], row: dict) -> dict:
    category = row["category"]
    result = {"id": row["id"], "speaker_id": None,
              "speaker_category": "NON_DIALOGUE" if category not in {"scripts", "plain_scripts"}
                                  else "UNKNOWN_SPEAKER",
              "speaker_confidence": "UNKNOWN", "speaker_name": None,
              "speaker_evidence": [], "canon_character_candidate": None,
              "source_game_candidate": None, "dialogue_group_id": None,
              "voice_review_required": False, "trainer_candidates": [],
              "object_candidates": [], "name_mentions_are_identity_evidence": False}
    if result["speaker_category"] == "NON_DIALOGUE":
        result["speaker_evidence"].append({"kind": "structured_category",
                                           "category": category,
                                           "limitation": "No individual NPC speaker asserted."})
        return result
    target = text_offset(row)
    trainers, direct, near = [], [], []
    for text_owner in pointer_sources(row):
        owner = int(text_owner, 16)
        trainers.extend(trainerbattle_owners(rom, owner, target))
        d, n = object_bindings(rom, objects, owner, target)
        direct.extend(d)
        near.extend(n)
    trainers = list({(x["opcode_offset"], x["text_operand_offset"]): x for x in trainers}.values())
    direct = list({(x["object_record_offset"], x["text_operand_offset"]): x for x in direct}.values())
    near = list({(x["object_record_offset"], x["text_operand_offset"]): x for x in near}.values())
    trainer_ids = {x["trainer_id"] for x in trainers}
    object_ids = {(x["map_header_offset"], x["local_object_id"]) for x in direct}
    result["trainer_candidates"] = trainers
    result["object_candidates"] = direct + near
    if len(trainer_ids) == 1 and trainers:
        trainer = trainers[0]
        result.update(speaker_id=f"trainer_{trainer['trainer_id']:04d}",
                      speaker_category=("UNBOUND_ORIGINAL" if trainer["trainer_class"]
                                        in UNBOUND_SPECIFIC_CLASSES and trainer["trainer_name"]
                                        in MAJOR_NAMES else "TRAINER_CLASS"),
                      speaker_confidence="PROVEN", speaker_name=trainer["trainer_name"],
                      dialogue_group_id=f"trainer_{trainer['trainer_id']:04d}",
                      voice_review_required=True)
        if result["speaker_category"] == "UNBOUND_ORIGINAL":
            result["source_game_candidate"] = {"game": "Pokémon Unbound",
                                               "confidence": "PLAUSIBLE",
                                               "basis": "Unbound-specific trainer class and exact trainer record; cross-game identity not proved."}
        result["speaker_evidence"] = [{"kind": "trainerbattle_text_operand", **x} for x in trainers]
    elif len(object_ids) == 1 and direct and not trainers:
        obj = direct[0]
        speaker_id = f"object_{int(obj['map_header_offset'], 16):08X}_{obj['local_object_id']:03d}"
        result.update(speaker_id=speaker_id, speaker_category="GENERIC_NPC",
                      speaker_confidence="PROVEN", speaker_name=None,
                      dialogue_group_id=speaker_id, voice_review_required=True)
        result["speaker_evidence"] = [{"kind": "direct_object_message", **x} for x in direct]
    else:
        if trainers:
            result["speaker_evidence"].append({"kind": "multiple_or_conflicting_trainer_ids",
                                               "ids": sorted(trainer_ids),
                                               "limitation": "Shared text cannot be assigned to one trainer."})
        if direct:
            result["speaker_evidence"].append({"kind": "multiple_or_conflicting_object_bindings",
                                               "bindings": direct,
                                               "limitation": "Not a unique object speaker."})
        if near:
            result["speaker_confidence"] = "PLAUSIBLE"
            result["speaker_evidence"].append({"kind": "object_script_proximity",
                                               "bindings": near,
                                               "limitation": "Branch/call path and actual speaker not proved."})
    assert result["speaker_category"] in SPEAKER_CATEGORIES
    assert result["speaker_confidence"] != "PROVEN" or result["speaker_id"]
    return result


def style_signals(originals: list[str]) -> list[dict]:
    """Observable English markers only; no Japanese voice or pronoun decisions."""
    corpus = "\n".join(originals)
    rules = [
        ("polite", r"\b(?:please|thank you|would you|sir|ma'am)\b"),
        ("formal", r"\b(?:indeed|therefore|shall|hence)\b"),
        ("casual", r"\b(?:gonna|wanna|gotta|hey)\b"),
        ("rough", r"\b(?:punk|damn|shut up)\b"),
        ("playful", r"\b(?:haha|hehe|heeey)\b"),
    ]
    found = []
    for label, pattern in rules:
        match = re.search(pattern, corpus, flags=re.IGNORECASE)
        if match:
            found.append({"signal": label, "english_evidence": match.group(0),
                          "status": "lexical_clue_not_voice_decision"})
    if corpus.count("!") >= 2:
        found.append({"signal": "emotional", "english_evidence": f"{corpus.count('!')} exclamation marks",
                      "status": "punctuation_clue_not_voice_decision"})
    return found or [{"signal": "neutral", "english_evidence": "No selected lexical marker",
                      "status": "absence_of_marker_not_character_trait"}]


def build():
    source = read(OUT / "ja_phase6_cleanup_translation_handoff_v2.json")
    queue = source["entries"]
    assert len(queue) == len({x["id"] for x in queue}) == 569
    assert Counter(x["resolution_class"] for x in queue) == {
        "CLAUDE_CONTEXT": 267, "CLAUDE_TRANSLATION": 302}
    inventory = read(OUT / "ja_phase6_final_cleanup_inventory_v3.json")
    assert inventory["metadata"]["held_after_glossary"] == 916
    applied = read(OUT / "ja_phase6_cleanup_glossary_combined_controlfix.json")["entries"]
    assert len(applied) == 2261
    rom = (ROOT / "rom/unbound.gba").read_bytes()
    assert hashlib.md5(rom).hexdigest() == SOURCE_MD5
    objects, map_audit = scan_map_objects(rom)
    attributed = [attribute(rom, objects, row) for row in queue]
    by_id = {x["id"]: x for x in attributed}
    v3 = deepcopy(source)
    for row in v3["entries"]:
        evidence = by_id[row["id"]]
        for field in ("speaker_id", "speaker_category", "speaker_confidence", "speaker_evidence",
                      "canon_character_candidate", "source_game_candidate", "dialogue_group_id",
                      "voice_review_required"):
            assert field not in row
            row[field] = evidence[field]
    assert all({k: v for k, v in updated.items() if k in original} == original
               for original, updated in zip(queue, v3["entries"]))
    v3["metadata"] = {**source["metadata"], "speaker_attribution_phase": "6C-3A",
                      "speaker_counts": dict(Counter(x["speaker_confidence"] for x in attributed)),
                      "speaker_category_counts": dict(Counter(x["speaker_category"] for x in attributed)),
                      "original_entries_preserved": 569, "translation_changes": 0,
                      "name_mentions_identity_promotions": 0}

    applied_candidates = []
    for row in applied:
        if row["category"] not in {"scripts", "plain_scripts"}:
            continue
        evidence = attribute(rom, objects, row)
        if evidence["speaker_confidence"] != "PROVEN":
            continue
        applied_candidates.append({"id": row["id"], "category": row["category"],
                                   "original": row["original"], "current_japanese": row["translated"],
                                   "rom_offset": f"0x{text_offset(row):08X}",
                                   "pointer_sources": pointer_sources(row),
                                   **evidence})

    group_rows = defaultdict(list)
    queue_by_id = {x["id"]: x for x in queue}
    for row in attributed:
        if row["speaker_confidence"] == "PROVEN":
            source_row = queue_by_id[row["id"]]
            group_rows[row["speaker_id"]].append({"id": row["id"], "original": source_row["original"],
                                                    "current_japanese": source_row["current_japanese"],
                                                    "source": "held_translation_queue",
                                                    "scene_context": source_row["context"],
                                                    "speaker_evidence": row["speaker_evidence"]})
    for row in applied_candidates:
        group_rows[row["speaker_id"]].append({"id": row["id"], "original": row["original"],
                                                "current_japanese": row["current_japanese"],
                                                "source": "already_applied",
                                                "scene_context": None,
                                                "speaker_evidence": row["speaker_evidence"]})
    speaker_groups = []
    all_attributed = {x["id"]: x for x in attributed + applied_candidates}
    for speaker_id, texts in sorted(group_rows.items()):
        identity = all_attributed[texts[0]["id"]]
        if any(all_attributed[x["id"]]["speaker_category"] != identity["speaker_category"] for x in texts):
            raise ValueError(f"Inconsistent speaker category: {speaker_id}")
        speaker_groups.append({"speaker_id": speaker_id, "speaker_name": identity["speaker_name"],
                               "english_name": identity["speaker_name"],
                               "character_category": identity["speaker_category"],
                               "source_game": identity["source_game_candidate"],
                               "dialogue_ids": [x["id"] for x in texts],
                               "dialogue": texts,
                               "speaker_evidence": [x["speaker_evidence"] for x in texts],
                               "confidence": "PROVEN",
                               "style_evidence": style_signals([x["original"] for x in texts]),
                               "original_japanese_voice_reference_status": "not_collected"})
    voice_groups = [x for x in speaker_groups
                    if x["character_category"] == "UNBOUND_ORIGINAL"
                    or len(x["dialogue_ids"]) >= 2]
    voice_groups.sort(key=lambda x: (x["character_category"] != "UNBOUND_ORIGINAL",
                                     -len(x["dialogue_ids"]), x["speaker_id"]))

    name_only = []
    for trainer_id in range(TRAINER_COUNT):
        record = trainer_record(rom, trainer_id)
        if record and record["trainer_name"] in {"Lucas", "Barry"}:
            name_only.append({**record, "status": "rejected_name_only_match",
                              "reason": "Trainer class does not establish historical character identity; no linked appearance/team/event proof."})
    canon = {"metadata": {"proven_canon": 0, "candidate_count": 0,
                          "rule": "Name mention or shared trainer name alone is never an identity claim."},
             "candidates": [], "rejected_name_only_matches": name_only,
             "source_game_counts": {}, "external_japanese_voice_reference_status": "not_collected"}
    speaker_report = {"metadata": {"queue_entries": 569, "applied_total": 2261,
                                    "applied_proven_candidates": len(applied_candidates),
                                    "queue_confidence_counts": dict(Counter(x["speaker_confidence"] for x in attributed)),
                                    "queue_category_counts": dict(Counter(x["speaker_category"] for x in attributed)),
                                    "distinct_proven_speaker_groups": len(speaker_groups),
                                    "map_scan": map_audit,
                                    "source_rom_md5": SOURCE_MD5,
                                    "not_runtime_playtested": True},
                      "entries": attributed, "applied_candidates": applied_candidates,
                      "speaker_groups": speaker_groups}
    voice = {"metadata": {"speaker_groups": len(voice_groups),
                          "entry_occurrences": sum(len(x["dialogue_ids"]) for x in voice_groups),
                          "unique_entry_ids": len({key for x in voice_groups for key in x["dialogue_ids"]}),
                          "new_translation_generated": False,
                          "no_voice_edits": True,
                          "rule": "Only proved trainer ID or direct object message groups; no cross-map/name-only merge."},
             "groups": voice_groups}
    write(OUT / "ja_phase6_speaker_attribution.json", speaker_report)
    write(OUT / "ja_phase6_canon_character_candidates.json", canon)
    write(OUT / "ja_phase6_cleanup_translation_handoff_v3.json", v3)
    write(OUT / "ja_phase6_voice_review_for_claude.json", voice)
    return {"queue": len(queue), "queue_confidence": speaker_report["metadata"]["queue_confidence_counts"],
            "applied_candidates": len(applied_candidates), "speaker_groups": len(speaker_groups),
            "voice_groups": len(voice_groups), "canon_candidates": 0}


if __name__ == "__main__":
    print(build())
