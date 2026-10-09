"""Phase 6C-3C: only three approved voice rewrites reach the new ROM."""

from collections import Counter
import hashlib

from lib.pcs_text import Charmap
from scripts.build_ja_phase6_voice_integration import (
    APPROVED, AUDIT, BASE_JSON, BASE_ROM, BASE_SHA256, BUILD_MAP, CANDIDATES,
    CONTROLFIX, CONTROLFIX_TWICE, DRY_MAP, HELD, INPUT, NEW_ROM, ROOT,
    SOURCE_MD5, glossary_observations, read, require_controlfix, strict_map,
)


def test_four_judgements_and_2261_count():
    rows = read(CANDIDATES)["candidates"]
    audit = read(AUDIT)
    assert len(rows) == 4
    assert {x["entry_id"] for x in rows} == set(APPROVED) | {HELD}
    assert audit["applied_count"] == 3 and audit["held_count"] == 1
    assert all(x["glossary_matches"] == [] for x in audit["entries"])
    assert {x["entry_id"] for x in audit["entries"] if x["decision"] == "APPLY"} == set(APPROVED)
    assert {x["entry_id"] for x in audit["entries"] if x["decision"] == "HOLD"} == {HELD}
    baseline = read(BASE_JSON)["entries"]
    assert len(baseline) == len({x["id"] for x in baseline}) == 2261
    assert all(x["translated"] == next(y["current_japanese"] for y in rows if y["entry_id"] == x["id"])
               for x in baseline if x["id"] in set(APPROVED) | {HELD})


def test_controlfix_twice_is_identity_and_does_not_touch_tokens():
    assert read(INPUT) == read(CONTROLFIX) == read(CONTROLFIX_TWICE)
    assert [x["id"] for x in require_controlfix()] == list(APPROVED)
    audit = read(AUDIT)
    for row in audit["entries"]:
        assert row["pcs_controls_current"] == row["pcs_controls_proposed"]
        assert row["protected_tokens_preserved"] and row["kanji_count"] == 0
        assert row["control_tokens"][0] == "[japanese]"
        assert row["control_tokens"][-1] == "[latin]"
        assert row["proposed_encoded_bytes"] <= row["slot_size"]
        assert row["baseline_slot_matches"] and row["pointer_owners_match"]
        Charmap("ja").encode(row["proposed_japanese"])


def test_real_rom_window_profiles_and_conservative_widths():
    rom = (ROOT / "rom/unbound.gba").read_bytes()
    assert rom[0x3A73BC:0x3A73C4] == bytes.fromhex("00 02 0f 1a 04 0f 98 01")
    assert rom[0x6FB38:0x6FB3C] == (0x083A73BC).to_bytes(4, "little")
    assert rom[0x248330:0x248338] == bytes.fromhex("00 01 0f 1c 04 00 90 00")
    assert rom[0x3FEB64:0x3FEB70] == bytes.fromhex("ff 02 02 02 00 02 01 01 0f 06 00 00")
    for row in read(AUDIT)["entries"]:
        assert row["field_window_physical_pixels"] == 208
        assert row["battle_window_physical_pixels"] == 222
        assert max(row["proposed_line_pixels"]) <= 208
        assert max(row["proposed_line_pixels"]) <= max(row["source_line_pixels"])


def test_strict_maps_and_binary_diff_are_three_slots_only():
    dry, built = read(DRY_MAP), read(BUILD_MAP)
    strict_map(dry)
    strict_map(built)
    assert dry["stats"] == built["stats"]
    before, after = BASE_ROM.read_bytes(), NEW_ROM.read_bytes()
    assert len(before) == len(after) == 0x2000000
    assert hashlib.sha256(before).hexdigest() == BASE_SHA256
    changed = {i for i, (a, b) in enumerate(zip(before, after)) if a != b}
    audit = read(AUDIT)
    assert len(changed) == audit["binary_diff"]["changed_byte_count"] == 24
    assert [f"0x{x:08X}" for x in sorted(changed)] == audit["binary_diff"]["changed_offsets"]
    allowed = set()
    for row in audit["entries"]:
        pos = int(row["rom_offset"], 16)
        if row["decision"] == "APPLY":
            allowed.update(range(pos, pos + row["slot_size"]))
        else:
            assert before[pos:pos + row["slot_size"]] == after[pos:pos + row["slot_size"]]
        for owner in row["pointer_owners"]:
            off = int(owner, 16)
            assert before[off:off + 4] == after[off:off + 4]
    assert changed <= allowed
    assert audit["binary_diff"]["unexpected_byte_count"] == 0
    assert audit["binary_diff"]["pointer_write_bytes"] == 0
    assert audit["binary_diff"]["relocated_text_bytes"] == 0
    assert hashlib.md5((ROOT / "rom/unbound.gba").read_bytes()).hexdigest() == SOURCE_MD5
    assert hashlib.sha256(after).hexdigest() == audit["rom_hashes"]["output_sha256"]


def test_glossary_discrepancies_are_audit_only():
    baseline = {x["id"]: x for x in read(BASE_JSON)["entries"]}
    observations = glossary_observations(baseline)
    assert observations == read(AUDIT)["glossary_observations"]
    assert [x["entry_id"] for x in observations] == ["scr_1F0AECE", "scr_1F0B076"]
    assert all(x["decision"] == "AUDIT_ONLY" and not x["current_entry_scoped_match"]
               for x in observations)
    decisions = Counter(x["decision"] for x in read(AUDIT)["entries"])
    assert decisions == {"APPLY": 3, "HOLD": 1}
    assert not {x["entry_id"] for x in observations} & set(APPROVED)
