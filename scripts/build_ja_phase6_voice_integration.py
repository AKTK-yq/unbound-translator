#!/usr/bin/env python3
"""Phase 6C-3C: stage three reviewed rewrites and audit an incremental ROM.

Run `prepare`, controlfix twice, injector dry-run/build, then `audit` as
documented in docs/ja-phase6-npc-voice-integration.md. Never writes source ROM.
"""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import runpy
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.pcs_text import Charmap, decode_pcs
from lib.translation_glossary import load_glossary
from lib.translation_tokens import semantic_tokens, strip_hma_quotes
from scripts.audit_ja_phase6_batch01_fit import line_widths
from scripts.build_ja_phase6_batch05 import control_sequence
from scripts.build_ja_phase6_voice_review import tokens

OUT = ROOT / "out/phase6"
FIX = ROOT / "tests/fixtures"
BASE_ROM = ROOT / "out/unbound-ja-phase6-cleanup-glossary.gba"
NEW_ROM = ROOT / "out/unbound-ja-phase6-voice-pass1.gba"
BASE_SHA256 = "3cd6d07baa4c287e10dab9d0a04960455311d6ee829e189abc57940040af638a"
SOURCE_MD5 = "9cad8e771940e7f7094d13911552cef0"
BASE_JSON = OUT / "ja_phase6_cleanup_glossary_combined_controlfix.json"
CANDIDATES = FIX / "ja_phase6_voice_rewrite_candidates.json"
PROFILES = FIX / "ja_phase6_voice_profiles_claude.json"
INPUT = OUT / "ja_phase6_voice_pass1_input.json"
CONTROLFIX = OUT / "ja_phase6_voice_pass1_controlfix.json"
CONTROLFIX_TWICE = OUT / "ja_phase6_voice_pass1_controlfix_twice.json"
DRY_MAP = OUT / "ja_phase6_voice_pass1_dry_run_map.json"
BUILD_MAP = OUT / "ja_phase6_voice_pass1_map.json"
AUDIT = FIX / "ja_phase6_voice_integration_audit.json"
APPROVED = ("scr_1F02145", "scr_740753", "scr_1F06A82")
HELD = "scr_1F02029"
HAN = re.compile(r"[㐀-鿿]")


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_inputs():
    baseline = read(BASE_JSON)["entries"]
    assert len(baseline) == len({x["id"] for x in baseline}) == 2261
    candidates = read(CANDIDATES)["candidates"]
    assert {x["entry_id"] for x in candidates} == set(APPROVED) | {HELD}
    profiles = read(PROFILES)
    assert profiles["metadata"]["input_entries"] == 120
    source = (ROOT / "rom/unbound.gba").read_bytes()
    assert hashlib.md5(source).hexdigest() == SOURCE_MD5
    base_rom = BASE_ROM.read_bytes()
    assert len(base_rom) == len(source) == 0x2000000
    assert sha256(base_rom) == BASE_SHA256
    return {x["id"]: x for x in baseline}, {x["entry_id"]: x for x in candidates}, source, base_rom


def encoded(injector, codec, row, value):
    changed = {**row, "translated": value}
    return injector["encode_text"](codec, injector["translation_for_injection"](changed),
                                   plain_script=row["category"] == "plain_scripts")


def validate_entry(entry, candidate, source_rom, base_rom, injector, codec):
    assert entry["id"] == candidate["entry_id"]
    assert entry["original"] == candidate["original_english"]
    assert entry["translated"] == candidate["current_japanese"]
    assert entry["category"] == "scripts" and entry["is_pointer_based"]
    glossary = load_glossary(ROOT / "glossaries/ja.json", expected_language="ja")
    glossary_hits = glossary.matches(strip_hma_quotes(entry["original"]), entry["category"],
                                     entry_id=entry["id"])
    assert not glossary_hits, "a newly scoped glossary match requires separate wording review"
    old, proposed = entry["translated"], candidate["proposed_japanese"]
    assert not HAN.search(old + proposed)
    assert tokens(old) == tokens(proposed)
    assert semantic_tokens(old) == semantic_tokens(proposed)
    assert old.count("\n") == proposed.count("\n")
    assert old.startswith("[japanese]") and old.endswith("[latin]")
    assert proposed.startswith("[japanese]") and proposed.endswith("[latin]")
    old_bytes = encoded(injector, codec, entry, old)
    new_bytes = encoded(injector, codec, entry, proposed)
    assert control_sequence(old_bytes) == control_sequence(new_bytes)
    assert codec.encode(proposed) == new_bytes
    offset, slot = int(entry["address"], 16), entry["byte_length"]
    assert decode_pcs(source_rom, offset, slot).text == strip_hma_quotes(entry["original"])
    assert base_rom[offset:offset + slot] == old_bytes.ljust(slot, b"\xff")
    assert len(new_bytes) <= slot
    for owner in entry["pointer_sources"]:
        pos = int(owner, 16)
        expected = (0x08000000 + offset).to_bytes(4, "little")
        assert source_rom[pos:pos + 4] == base_rom[pos:pos + 4] == expected
    source_widths = line_widths(source_rom[offset:offset + slot])
    current_widths, proposed_widths = line_widths(old_bytes), line_widths(new_bytes)
    # Unbound field textbox: ROM 0x3A73BC, 26 tiles; battle message box:
    # ROM 0x248330, 28 tiles / printer x=2. Both bounds are checked because
    # trainerbattle intro/defeat use different paths and mode 13 is extended.
    assert source_rom[0x3A73BC:0x3A73C4] == base_rom[0x3A73BC:0x3A73C4] == bytes.fromhex(
        "00 02 0f 1a 04 0f 98 01")
    assert source_rom[0x6FB38:0x6FB3C] == (0x083A73BC).to_bytes(4, "little")
    assert source_rom[0x248330:0x248338] == base_rom[0x248330:0x248338] == bytes.fromhex(
        "00 01 0f 1c 04 00 90 00")
    assert source_rom[0x3FEB64:0x3FEB70] == base_rom[0x3FEB64:0x3FEB70] == bytes.fromhex(
        "ff 02 02 02 00 02 01 01 0f 06 00 00")
    assert max(proposed_widths) <= min(208, 222)
    assert max(proposed_widths) <= max(source_widths)
    return {
        "entry_id": entry["id"], "original_english": entry["original"],
        "current_japanese": old, "proposed_japanese": proposed,
        "rom_offset": f"0x{offset:08X}", "gba_address": f"0x{offset + 0x08000000:08X}",
        "slot_size": slot, "pointer_owners": entry["pointer_sources"],
        "current_encoded_bytes": len(old_bytes), "proposed_encoded_bytes": len(new_bytes),
        "source_line_pixels": source_widths, "current_line_pixels": current_widths,
        "proposed_line_pixels": proposed_widths, "field_window_physical_pixels": 208,
        "battle_window_physical_pixels": 222,
        "renderer_fit_rule": "below both ROM-backed physical spans and the original English maximum; no dynamic buffer",
        "control_tokens": tokens(proposed), "pcs_controls_current": control_sequence(old_bytes),
        "pcs_controls_proposed": control_sequence(new_bytes),
        "protected_tokens_preserved": True, "kanji_count": 0,
        "baseline_slot_matches": True, "pointer_owners_match": True,
        "glossary_matches": [],
    }


def glossary_observations(baseline):
    glossary = load_glossary(ROOT / "glossaries/ja.json", expected_language="ja")
    frost = next(t for t in glossary.terms if t.source == "Frost Mountain")
    route = next(t for t in glossary.terms if t.source == "Route [N]")
    row_a, row_b = baseline["scr_1F0AECE"], baseline["scr_1F0B076"]
    assert "Frost Mountain" in row_a["original"] and "フロストマウンテン" in row_a["translated"]
    assert "Route 8" in row_b["original"] and "ルート8" in row_b["translated"]
    assert frost.target == "フロストやま" and route.target == "[N]ばんどうろ"
    def hits(term, row):
        return [x.source for _, _, x in glossary.matches(term, row["category"], entry_id=row["id"])]
    assert hits("Frost Mountain", row_a) == []
    assert hits("Frost Mountain", {"id": "scr_1F0A708", "category": "scripts"}) == ["Frost Mountain"]
    assert hits("Route 8", row_b) == []
    assert [x.source for _, _, x in glossary.matches("Route 8", "map_names", entry_id="probe")] == ["Route [N]"]
    return [
        {"entry_id": row_a["id"], "current_japanese": row_a["translated"],
         "approved_form": frost.target, "glossary_entry_ids": list(frost.entry_ids),
         "same_english_place_name": True, "current_entry_scoped_match": False,
         "decision": "AUDIT_ONLY", "note": "Exact English Frost Mountain; approved form applies only to scr_1F0A708. Do not widen scope in voice pass."},
        {"entry_id": row_b["id"], "current_japanese": row_b["translated"],
         "approved_template": route.target, "glossary_categories": list(route.categories),
         "current_entry_scoped_match": False, "decision": "AUDIT_ONLY",
         "note": "Route [N] template matches map_names, not scripts; extension requires a separate policy review."},
    ]


def stage_prepare():
    baseline, candidates, source_rom, base_rom = load_inputs()
    injector = runpy.run_path(str(ROOT / "005_hybrid_injector.py"))
    codec = Charmap("ja")
    checks = {key: validate_entry(baseline[key], candidates[key], source_rom, base_rom, injector, codec)
              for key in (*APPROVED, HELD)}
    # Semantic decision: "special Fire-types" does not establish the Special
    # Attack stat.  Existing "とくせい" is questionable, but the candidate is
    # a different unsupported gameplay claim, so keep it out of the ROM.
    assert "My special [green]Fire[blue]-types" in baseline[HELD]["original"]
    assert "とくしゅこうげきの" in candidates[HELD]["proposed_japanese"]
    # Use the repository decontrolfix operation before editing the existing
    # controlfixed translation. The Claude proposal supplies the deliberate
    # final line breaks; 004 must then reproduce them exactly.
    decontrolfix = runpy.run_path(str(ROOT / "006_decontrolfix_translations.py"))["clean_translation"]
    editable, staged = [], []
    for key in APPROVED:
        item = deepcopy(baseline[key])
        clean, removed = decontrolfix(item["translated"])
        assert clean, key
        item["translated"] = clean
        editable.append(deepcopy(item))
        item["translated"] = candidates[key]["proposed_japanese"]
        staged.append(item)
    assert len(staged) == 3 and all(x["id"] != HELD for x in staged)
    write(OUT / "ja_phase6_voice_pass1_decontrolfixed.json", {"entries": editable})
    write(INPUT, {"entries": staged})
    write(OUT / "ja_phase6_voice_pass1_preflight.json", {
        "approved_ids": list(APPROVED), "held_ids": [HELD],
        "checks": list(checks.values()), "glossary_observations": glossary_observations(baseline),
        "baseline_sha256": sha256(base_rom), "source_md5": SOURCE_MD5,
    })
    return {"approved": list(APPROVED), "held": [HELD], "staged_input": str(INPUT)}


def require_controlfix():
    original = read(INPUT)["entries"]
    once = read(CONTROLFIX)["entries"]
    twice = read(CONTROLFIX_TWICE)["entries"]
    assert original == once == twice, "controlfix must preserve the reviewed lines and be idempotent"
    assert len(once) == 3 and [x["id"] for x in once] == list(APPROVED)
    report = read(OUT / "ja_phase6_voice_pass1_controlfix_report.json")
    report2 = read(OUT / "ja_phase6_voice_pass1_controlfix_twice_report.json")
    assert report["stats"]["remaining_control_mismatches"] == 0 and not report["remaining"]
    assert report2["stats"]["remaining_control_mismatches"] == 0 and not report2["remaining"]
    return once


def strict_map(mapping):
    s = mapping["stats"]
    assert s["input_entries"] == s["in_place"] == 3
    assert s["relocated"] == s["pointer_writes"] == 0
    for key in ("skipped_pointer_mismatch", "skipped_implausible_pointer", "skipped_no_space",
                "skipped_unsafe", "skipped_bounds", "skipped_empty", "skipped_duplicate_fixed",
                "encode_errors", "fixed_truncated",
                "no_relocation_truncated", "ability_descriptions_compacted", "runtime_patches",
                "graphics_patches"):
        assert s[key] == 0, (key, s[key])
    assert mapping["used_free_bytes"] == mapping["used_vetted_bytes"] == 0
    assert mapping["used_reclaimed_text_bytes"] == 0
    assert not mapping["relocations"] and not mapping["missing_relocations"]
    assert not mapping["missing_fixed_slots"]
    assert not mapping["runtime_patches"] and not mapping["graphics_patches"]


def stage_audit():
    baseline, candidates, source_rom, before = load_inputs()
    chosen = require_controlfix()
    planned, built = read(DRY_MAP), read(BUILD_MAP)
    strict_map(planned)
    strict_map(built)
    assert planned["stats"] == built["stats"]
    after = NEW_ROM.read_bytes()
    assert len(after) == len(before) == 0x2000000
    injector = runpy.run_path(str(ROOT / "005_hybrid_injector.py"))
    codec = Charmap("ja")
    allowed = set()
    per_entry = []
    for row in chosen:
        key = row["id"]
        check = validate_entry(baseline[key], candidates[key], source_rom, before, injector, codec)
        offset, slot = int(row["address"], 16), row["byte_length"]
        payload = encoded(injector, codec, row, row["translated"])
        assert after[offset:offset + slot] == payload.ljust(slot, b"\xff")
        assert after[offset:offset + slot] != before[offset:offset + slot]
        allowed.update(range(offset, offset + slot))
        for owner in row["pointer_sources"]:
            pos = int(owner, 16)
            assert before[pos:pos + 4] == after[pos:pos + 4]
        per_entry.append({**check, "decision": "APPLY", "placement": "in_place",
                          "changed_offsets": [f"0x{i:08X}" for i in range(offset, offset + slot)
                                              if before[i] != after[i]]})
    # Include the held entry in the audit, but never give it an allowed byte.
    held_row = baseline[HELD]
    pos, slot = int(held_row["address"], 16), held_row["byte_length"]
    assert before[pos:pos + slot] == after[pos:pos + slot]
    held_check = validate_entry(held_row, candidates[HELD], source_rom, before, injector, codec)
    per_entry.append({**held_check, "decision": "HOLD",
                      "reason": "special Fire-types does not prove the Special Attack stat; proposed wording adds an unsupported gameplay claim",
                      "changed_offsets": []})
    changed = {i for i, (a, b) in enumerate(zip(before, after)) if a != b}
    unexpected = changed - allowed
    assert changed and not unexpected, f"Unexpected ROM bytes: {[hex(x) for x in sorted(unexpected)[:20]]}"
    assert len(changed) == sum(len(x["changed_offsets"]) for x in per_entry)
    assert hashlib.md5((ROOT / "rom/unbound.gba").read_bytes()).hexdigest() == SOURCE_MD5
    assert sha256(BASE_ROM.read_bytes()) == BASE_SHA256
    report = {
        "phase": "6C-3C", "status": "PASS", "applied_count": 3, "held_count": 1,
        "baseline_applied_entries": 2261, "approved_only_text_changes": True,
        "other_2258_translations_unchanged": True, "other_pointer_changes": 0,
        "entries": per_entry, "glossary_observations": glossary_observations(baseline),
        "controlfix_idempotent": True,
        "strict_dry_run": {"status": "PASS", "stats": planned["stats"]},
        "strict_build": {"status": "PASS", "stats": built["stats"]},
        "binary_diff": {"changed_byte_count": len(changed),
                        "changed_offsets": [f"0x{x:08X}" for x in sorted(changed)],
                        "allowed_slot_count": 3, "unexpected_byte_count": 0,
                        "relocated_text_bytes": 0, "pointer_write_bytes": 0},
        "rom_hashes": {"source_md5": SOURCE_MD5,
                       "baseline_sha256": sha256(before), "output_md5": hashlib.md5(after).hexdigest(),
                       "output_sha256": sha256(after)},
    }
    write(AUDIT, report)
    return {"status": "PASS", "applied": 3, "held": 1,
            "changed_bytes": len(changed), "output_sha256": sha256(after)}


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in {"prepare", "audit"}:
        raise SystemExit("usage: python scripts/build_ja_phase6_voice_integration.py prepare|audit")
    print(stage_prepare() if sys.argv[1] == "prepare" else stage_audit())
