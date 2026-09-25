"""Phase 5C review gate, difficulty ownership, and strict ROM regressions."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import runpy

import pytest

from lib.pcs_text import Charmap, decode_pcs


ROOT = Path(__file__).resolve().parents[1]
MERGE = runpy.run_path(str(ROOT / "scripts/build_ja_phase5c.py"))
FOCUSED = runpy.run_path(str(ROOT / "scripts/audit_ja_phase5c_difficulty.py"))
BINARY = runpy.run_path(str(ROOT / "scripts/audit_ja_phase5b.py"))


def read(name):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def test_review_merge_applies_only_confirmed_20_and_five_focused_rows():
    required = (
        "out/ja-phase5c-prepared.json", "out/ja-phase5b-resolved.json",
        "out/ja-phase5c-needs-context-for-claude.json",
        "tests/fixtures/ja_phase5c_claude_review.json",
        "tests/fixtures/ja_phase5c_difficulty_review.json",
    )
    if any(not (ROOT / path).exists() for path in required):
        pytest.skip("local Phase 5C pipeline artifacts unavailable")
    merged, audit = MERGE["merge"](*(read(path) for path in required))
    ids = {entry["id"] for entry in merged["entries"]}
    review = read("tests/fixtures/ja_phase5c_claude_review.json")
    confirmed = {entry["id"] for entry in review if entry["status"] == "confirmed"}
    held = {entry["id"] for entry in review if entry["status"] == "needs_context"}
    assert (audit["baseline_applied"], audit["context_confirmed"],
            audit["context_held"], audit["difficulty_focused_additions"],
            audit["total_input"]) == (596, 20, 96, 5, 621)
    assert confirmed <= ids and held.isdisjoint(ids)
    assert "scr_74AE91" not in ids
    assert "tbl_menu_game_settings_00000_1F4E274" not in ids
    assert "tbl_menu_game_settings_00000_1F4E26F" in ids


def test_complete_warning_extraction_and_duplicate_exclusion():
    path = ROOT / "out/ja-phase5c-extracted.json"
    if not path.exists():
        pytest.skip("fresh extraction unavailable")
    rows = read("out/ja-phase5c-extracted.json")["entries"]
    assert len(rows) == 25044
    same_address = [row for row in rows if int(row["address"], 16) == 0x1F4E26F]
    assert len(same_address) == 1
    assert same_address[0]["id"] == "tbl_menu_game_settings_00000_1F4E26F"
    assert int(same_address[0]["byte_length"]) == 185
    assert any(int(pointer, 16) == 0x1EBD7FC
               for pointer in same_address[0]["pointer_sources"])
    assert not any(row["id"] == "tbl_menu_game_settings_00000_1F4E274" for row in rows)
    by_id = {row["id"]: row for row in rows}
    assert {0x1E6FCEB} <= {int(x, 16) for x in by_id["scr_1F10621"]["pointer_sources"]}
    assert {0x1E6FD0E} <= {int(x, 16) for x in by_id["scr_1F10630"]["pointer_sources"]}
    assert {0x1E6FC43, 0x1E6FDED} <= {
        int(x, 16) for x in by_id["scr_1F1062B"]["pointer_sources"]}


def test_battle_difficulty_labels_and_relocations():
    path = ROOT / "out/ja-phase5c-difficulty-binary-audit.json"
    if not path.exists():
        pytest.skip("focused binary audit unavailable")
    report = read("out/ja-phase5c-difficulty-binary-audit.json")
    assert report["status"] == "PASS" and report["entry_count"] == 26
    rows = {row["id"]: row for row in report["entries"]}
    expected = {
        "scr_1F10630": ("バニラ", 8, 8, 30, "in-place", 5),
        "scr_1F10621": ("ハード", 8, 10, 30, "in-place", 5),
        "scr_1F1063D": ("エキスパート", 11, 7, 60, "relocated", 4),
        "scr_1F10644": ("インセイン", 10, 7, 50, "relocated", 5),
    }
    for entry_id, (word, size, slot, width, placement, owners) in expected.items():
        row = rows[entry_id]
        assert word in row["japanese"]
        assert (row["encoded_bytes"], row["slot_size"],
                row["pixel_width_max_line"], row["placement"],
                len(row["pointer_owners"])) == (size, slot, width, placement, owners)
    assert "バトルのむずかしさ" in rows["tbl_setting_names_00013_1F4DB23"]["japanese"]
    assert rows["tbl_menu_game_settings_00000_1F4E26F"]["slot_size"] == 185
    assert "ほんとうに" in rows["tbl_menu_game_settings_00000_1F4E26F"]["japanese"]
    warning = rows["tbl_menu_game_settings_00000_1F4E26F"]["japanese"]
    assert "[red]" in warning and "[black]" in warning
    assert "\n" in warning and "\\l" in warning and "\n\n" in warning
    encoded = Charmap("ja").encode(warning)
    assert all(code in encoded for code in (0xFE, 0xFA, 0xFB, 0xFC))


def test_difficulty_buffer_and_player_page_state():
    path = ROOT / "out/ja-phase5c-controlfix.json"
    if not path.exists():
        pytest.skip("Phase 5C controlfix unavailable")
    rows = {row["id"]: row for row in read("out/ja-phase5c-controlfix.json")["entries"]}
    mode_text = rows["scr_1F1063D"]["translated"]
    result_text = rows["scr_1F10323"]["translated"]
    player_text = rows["scr_1F9FBCD"]["translated"]
    assert "[latin][buffer1][japanese]" in result_text
    assert "[latin][player][japanese]" in player_text
    cmap = Charmap("ja")
    mode_bytes = cmap.encode(mode_text)[:-1]
    result_bytes = cmap.encode(result_text)
    expanded = result_bytes.replace(b"\xfd\x02", mode_bytes)
    assert "エキスパート" in decode_pcs(expanded).text
    player_bytes = cmap.encode(player_text).replace(b"\xfd\x01", cmap.encode("RED")[:-1])
    assert "ブラック[latin]RED[japanese]" in decode_pcs(player_bytes).text
    assert "[buffer1]" in rows["tbl_mission_log_00017_1F560DA"]["translated"]


def test_controlfix_is_byte_identical_on_second_pass():
    first = ROOT / "out/ja-phase5c-controlfix.json"
    second = ROOT / "out/ja-phase5c-controlfix-second.json"
    if not first.exists() or not second.exists():
        pytest.skip("Phase 5C idempotency artifacts unavailable")
    assert first.read_bytes() == second.read_bytes()
    assert read("out/ja-phase5c-controlfix-second-report.json")["stats"]["changed"] == 0


def test_strict_binary_audit_and_focused_audit():
    required = ("rom/unbound.gba", "out/unbound-ja-phase5c.gba",
                "out/ja-phase5c-controlfix.json", "out/ja-phase5c-map.json",
                "out/ja-phase5c-difficulty-audit.json")
    if any(not (ROOT / name).exists() for name in required):
        pytest.skip("private Phase 5C ROM artifacts unavailable")
    entries = read(required[2])["entries"]
    report = BINARY["audit"]((ROOT / required[0]).read_bytes(),
                              (ROOT / required[1]).read_bytes(), entries, read(required[3]))
    assert report["status"] == "PASS"
    assert (report["input_entries"], report["in_place"], report["relocated"],
            report["pointer_writes"], report["vetted_ff_consumed"]) == (621, 452, 169, 876, 2383)
    focused = FOCUSED["build_report"](read(required[4]), entries, report)
    assert focused["status"] == "PASS" and focused["entry_count"] == 26
    assert hashlib.sha256((ROOT / required[1]).read_bytes()).hexdigest() == focused[
        "full_audit_output_sha256"]
