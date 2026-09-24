import contextlib
import hashlib
import io
import json
import sys
from pathlib import Path
from unittest import mock

import pytest

from lib.pcs_text import Charmap, decode_pcs
from lib.gen3_font import NORMAL_JAPANESE_GLYPH_WIDTHS, text_pixel_width
from scripts import audit_ja_phase4
from scripts import build_ja_phase4_selection
from tests.helpers import load_script_module

ROOT = Path(__file__).resolve().parents[1]
INJECTOR = load_script_module("005_hybrid_injector.py", "ja_phase4_injector")
CONTROLFIX = load_script_module("004_controlfix_translations.py", "ja_phase4_controlfix")
SELECTION = json.loads((ROOT / "tests/fixtures/ja_phase4_selection.json").read_text(encoding="utf-8"))
CLAUDE_REVIEW = json.loads((ROOT / "tests/fixtures/ja_phase4_claude_review.json").read_text(encoding="utf-8"))


def test_phase4_selection_applies_every_confirmed_review_without_expanding_scope():
    selected = {entry["id"]: entry["japanese"] for entry in SELECTION["entries"]}
    assert len(selected) == 59
    assert len(CLAUDE_REVIEW["entries"]) == 59
    confirmed = [entry for entry in CLAUDE_REVIEW["entries"] if entry["status"] == "confirmed"]
    pending = [entry for entry in CLAUDE_REVIEW["entries"] if entry["status"] == "needs_context"]
    assert len(confirmed) == 56
    assert {entry["id"] for entry in pending} == {
        "scr_1F0F842", "scr_1F10323", "tbl_mission_log_00017_1F560DA",
    }
    assert all(selected[entry["id"]] == entry["reviewed_japanese"] for entry in confirmed)


def test_japanese_page_transition_and_dynamic_buffer_roundtrip():
    text, changed = CONTROLFIX.ensure_japanese_page("[green]こ\nん\\lに\n\nち[player]は")
    encoded = Charmap("ja").encode(text)

    assert changed
    assert b"\xFC\x15" in encoded and b"\xFC\x16\xFD\x01\xFC\x15" in encoded
    assert all(byte in encoded for byte in (0xFE, 0xFA, 0xFB))
    assert decode_pcs(encoded).text == text
    expanded = encoded.replace(b"\xFD\x01", Charmap("ja").encode("ASH")[:-1], 1)
    assert "[latin]ASH[japanese]は" in decode_pcs(expanded).text


def test_japanese_normal_widths_and_quote_codes_match_rom():
    assert len(NORMAL_JAPANESE_GLYPH_WIDTHS) == 0x118
    rom_path = ROOT / "rom/unbound.gba"
    if rom_path.exists():
        with rom_path.open("rb") as stream:
            stream.seek(0x20F500)
            assert stream.read(0x118) == NORMAL_JAPANESE_GLYPH_WIDTHS
    cmap = Charmap("ja")
    assert cmap.encode(r"[japanese]\qoあ\qc[latin]") == bytes.fromhex(
        "FC 15 B1 01 B2 FC 16 FF"
    )
    assert text_pixel_width("[japanese]はなしのはやさ[latin]", cmap) == 70
    assert text_pixel_width(r"[japanese]\qoあ\qc[latin]", cmap) == 30


def test_phase4_selection_rejects_unknown_japanese_glyph():
    assert len(SELECTION["entries"]) == 59
    prepared_entries = [
        {"id": row["id"], "original": '"Hello"', "category": "scripts"}
        for row in SELECTION["entries"]
    ]
    # Invalid Unicode must be rejected before a translation is handed to injection.
    selection = json.loads(json.dumps(SELECTION, ensure_ascii=False))
    selection["entries"][0]["japanese"] = "漢"
    with pytest.raises(UnicodeEncodeError, match="Japanese PCS page"):
        build_ja_phase4_selection.build({"entries": prepared_entries}, selection, verify_pokeapi=False)
    with pytest.raises(UnicodeEncodeError, match="Japanese PCS page"):
        Charmap("ja").encode("[japanese]漢[latin]")


def _run_injector(tmp_path, rom, entry, *, fail_on_no_space=False):
    source_path = tmp_path / "source.gba"
    text_path = tmp_path / "texts.json"
    output_path = tmp_path / "patched.gba"
    map_path = tmp_path / "map.json"
    source_path.write_bytes(rom)
    text_path.write_text(json.dumps({"entries": [entry]}, ensure_ascii=False), encoding="utf-8")
    argv = [str(ROOT / "005_hybrid_injector.py"), str(source_path), str(text_path),
            "-o", str(output_path), "--target-lang", "ja", "--map-output", str(map_path)]
    if fail_on_no_space:
        argv.append("--fail-on-no-space")
    with (
        mock.patch.object(sys, "argv", argv),
        mock.patch.object(INJECTOR, "build_free_blocks", return_value=[
            INJECTOR.FreeBlock(0x300, 0x380, 0x300)
        ]),
        mock.patch.object(INJECTOR, "apply_language_patches", return_value=[]),
        mock.patch.object(INJECTOR, "patch_graphics", return_value=[]),
        contextlib.redirect_stdout(io.StringIO()),
    ):
        INJECTOR.main()
    return source_path, output_path, map_path


def test_japanese_relocation_updates_every_owner_only(tmp_path, monkeypatch):
    rom = bytearray(0x500)
    rom[0x100:0x10A] = Charmap("ja").encode("Hello").ljust(10, b"\xFF")
    rom[0x300:0x380] = b"\xFF" * 0x80
    for source in (0x20, 0x40):
        rom[source:source + 4] = (0x08000100).to_bytes(4, "little")
    entry = {
        "id": "script-ja", "category": "scripts", "address": "0x100",
        "byte_length": 10, "pointer_sources": ["0x20", "0x40"],
        "original": '"Hello"', "translated": "[japanese]あいうえおかきくけこ[latin]",
    }
    original_path, output_path, map_path = _run_injector(tmp_path, rom, entry, fail_on_no_space=True)
    output = output_path.read_bytes()
    injection_map = json.loads(map_path.read_text(encoding="utf-8"))
    relocation = injection_map["relocations"][0]
    dest = int(relocation["new_offset"], 16)

    assert injection_map["stats"]["relocated"] == 1
    assert injection_map["stats"]["pointer_writes"] == 2
    assert original_path.read_bytes() == rom
    assert output[0x100:0x10A] == rom[0x100:0x10A]
    assert output[dest:dest + relocation["byte_length"]] == Charmap("ja").encode(entry["translated"])
    assert all(output[source:source + 4] == (0x08000000 + dest).to_bytes(4, "little")
               for source in (0x20, 0x40))
    changed = {i for i, pair in enumerate(zip(rom, output)) if pair[0] != pair[1]}
    assert changed <= set(range(dest, dest + relocation["byte_length"])) | set(range(0x20, 0x24)) | set(range(0x40, 0x44))

    monkeypatch.setattr(audit_ja_phase4, "EXPECTED_MD5", hashlib.md5(rom).hexdigest())
    monkeypatch.setattr(audit_ja_phase4, "VETTED_FREE_SPACE_RANGES", ((0x300, 0x380),))
    audit = audit_ja_phase4.audit(bytes(rom), output, [entry],
                                  {"entries": [{"id": "script-ja", "route": "intro"}]}, injection_map)
    assert audit["status"] == "PASS"
    monkeypatch.setattr(audit_ja_phase4, "RESERVED_ROM_RANGES", ((0x300, 0x380),))
    with pytest.raises(ValueError, match="reserved ROM"):
        audit_ja_phase4.audit(bytes(rom), output, [entry],
                              {"entries": [{"id": "script-ja", "route": "intro"}]}, injection_map)


def test_japanese_fixed_slot_fails_without_truncation(tmp_path):
    rom = bytearray(0x500)
    rom[0x100:0x108] = Charmap("ja").encode("Pikachu").ljust(8, b"\xFF")
    rom[0x300:0x380] = b"\xFF" * 0x80
    entry = {
        "id": "fixed-ja", "category": "pokemon_names", "address": "0x100",
        "byte_length": 8, "original": '"Pikachu"',
        "translated": "[japanese]モンスターボール[latin]",
    }
    with pytest.raises(RuntimeError, match="Lossy fixed-slot truncation refused"):
        _run_injector(tmp_path, rom, entry, fail_on_no_space=True)
    assert (tmp_path / "source.gba").read_bytes() == rom
    assert not (tmp_path / "patched.gba").exists()
