"""Phase 5C evidence handoff stays conservative about runtime ownership."""

import importlib.util
import json
from pathlib import Path
import sys

import pytest

from scripts.build_ja_phase5c_handoff import (
    DIFFICULTY_BUDGET_EXAMPLES,
    DIFFICULTY_ROLES,
    buffer_evidence,
    exact_pointer_references,
    operand_kind,
    pointer_evidence,
)
from lib.gen3_font import text_pixel_width
from lib.pcs_text import Charmap, decode_pcs


ROOT = Path(__file__).resolve().parents[1]


def test_exact_pointer_references_and_bufferstring_owner():
    rom = bytearray(64)
    target = 0x20
    pointer = (0x08000000 + target).to_bytes(4, "little")
    rom[4:10] = b"\x85\x00" + pointer
    rom[24:28] = pointer
    assert exact_pointer_references(rom, target) == [6, 24]
    evidence = pointer_evidence(rom, {"id": "sample", "rom_offset": target,
                                    "pointer_owners": ["0x18"]})
    assert evidence["recorded_owner_count"] == 1
    assert evidence["additional_exact_pointer_offsets"] == ["0x00000006"]
    assert operand_kind(rom, 6) == "bufferstring 0 operand"
    assert rom[4:6] == b"\x85\x00"  # Separate structural proof.


def test_new_game_difficulty_review_holds_are_not_silently_approved():
    selected = {row["id"]: row for row in json.loads(
        (ROOT / "tests/fixtures/ja_phase5_selection.json").read_text(encoding="utf-8"))["entries"]}
    reviewed = {row["id"]: row for row in json.loads(
        (ROOT / "tests/fixtures/ja_phase5_claude_review.json").read_text(encoding="utf-8"))}
    new_game_ids = {entry_id for entry_id in DIFFICULTY_ROLES
                    if entry_id.startswith("scr_") and entry_id != "scr_1F4E26F"}
    assert new_game_ids.issubset(selected)
    assert all(entry_id not in selected for entry_id in (
        "tbl_setting_names_00013_1F4DB23", "tbl_menu_game_settings_00035_1F4E037",
        "tbl_setting_names_00014_1F4DC09", "tbl_menu_game_settings_00018_1F4DE12"))
    for entry_id in ("scr_1F10621", "scr_1F10630", "scr_1F1063D", "scr_1F10644",
                     "scr_1F0FFA4", "scr_1F100B9", "scr_1F101AC", "scr_1F10323"):
        assert reviewed[entry_id]["status"] == "needs_context"
    assert reviewed["scr_1F0FE27"]["status"] == "confirmed"
    assert reviewed["scr_1F0FF35"]["status"] == "confirmed"


def test_buffer_handoff_marks_proven_and_unknown_producers_differently():
    known = buffer_evidence("The difficulty is [buffer1].", "scr_1F10323")
    assert known[0]["runtime_producer"]["source"].startswith("variable 0x50DF")
    unknown = buffer_evidence("Hello [buffer1].", "scr_7527C2")
    assert unknown[0]["runtime_producer"] is None
    assert buffer_evidence("\\CC is a control, not a buffer.", "unused") == []


def test_options_warning_and_mode_buffers_are_explicit_extraction_owners():
    path = ROOT / "001_extract_unbound_text.py"
    spec = importlib.util.spec_from_file_location("phase5c_extractor", path)
    extractor = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = extractor
    spec.loader.exec_module(extractor)
    ranges = [row for row in extractor.POST_POINTER_MANUAL_TEXT_RANGES
              if row.table_name == "data.menus.text.gameSettings.extraPrompts"]
    assert [(row.start, row.end) for row in ranges] == [(0x1F4E26F, 0x1F4E515)]
    assert extractor.MANUAL_TEXT_POINTER_SOURCES[0x1F4E26F] == [0x1EBD7FC]
    assert 0x1E6FCEB in extractor.MANUAL_TEXT_POINTER_SOURCES[0x1F10621]
    assert 0x1E6FD0E in extractor.MANUAL_TEXT_POINTER_SOURCES[0x1F10630]
    assert extractor.MANUAL_TEXT_POINTER_SOURCES[0x1F1062B] == [0x1E6FC43, 0x1E6FDED]
    assert extractor.MANUAL_TEXT_POINTER_SOURCES[0x1F1064B] == [0x1E6FC32]


def test_difficulty_budget_examples_are_kana_only_and_exact():
    cmap = Charmap("ja")
    expected = {
        "scr_1F10621": (10, 50),
        "scr_1F10630": (8, 30),
        "scr_1F1063D": (11, 60),
        "scr_1F10644": (10, 50),
    }
    for entry_id, example in DIFFICULTY_BUDGET_EXAMPLES.items():
        wrapped = f"[japanese]{example}[latin]"
        assert (len(cmap.encode(wrapped)), text_pixel_width(wrapped, cmap)) == expected[entry_id]
        assert decode_pcs(cmap.encode(wrapped)).text == wrapped


def test_source_rom_difficulty_anchors_when_available():
    rom_path = ROOT / "rom/unbound.gba"
    if not rom_path.exists():
        pytest.skip("private source ROM is not available")
    rom = rom_path.read_bytes()
    assert rom[0x01E6FCE9:0x01E6FCEF] == bytes.fromhex("85 00 21 06 f1 09")
    assert rom[0x01E6FD0C:0x01E6FD12] == bytes.fromhex("85 00 30 06 f1 09")
    for source, target in ((0x01E6FC43, 0x01F1062B),
                           (0x01E6FDED, 0x01F1062B),
                           (0x01E6FC32, 0x01F1064B)):
        assert rom[source - 2:source] == bytes.fromhex("85 00")
        assert rom[source:source + 4] == (0x08000000 + target).to_bytes(4, "little")
    assert rom[0x01E6FE3F:0x01E6FE44] == bytes.fromhex("6f 13 05 22 01")
    assert rom[0x01FB3948:0x01FB3954] == bytes.fromhex(
        "23 db f4 09 18 3a fb 09 37 e0 f4 09")
    assert rom[0x01FB37B8:0x01FB37C4] == bytes.fromhex(
        "09 dc f4 09 4c 3a fb 09 12 de f4 09")
    assert rom[0x01FB3A18:0x01FB3A28] == bytes.fromhex(
        "30 06 f1 09 21 06 f1 09 3d 06 f1 09 44 06 f1 09")
    assert rom[0x01FB54CC:0x01FB54D8] == bytes.fromhex(
        "21 06 f1 09 30 06 f1 09 3d 06 f1 09")
    warning = decode_pcs(rom, 0x01F4E26F)
    assert warning.byte_length == 185
    assert warning.text.startswith("[red]WARNING![black]")
    assert rom[0x01EBD7FC:0x01EBD800] == bytes.fromhex("6f e2 f4 09")
