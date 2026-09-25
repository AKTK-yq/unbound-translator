"""Phase 5E glossary, reviewed-entry, and ROM safety gates."""

from __future__ import annotations

import json
from pathlib import Path
import runpy

import pytest

from lib.pcs_text import Charmap
from lib.translation_glossary import load_glossary


ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_phase5d_review_and_patch_are_consistent():
    review = read("tests/fixtures/ja_phase5d_glossary_review.json")
    patch = read("tests/fixtures/ja_phase5d_glossary_patch.json")["terms"]
    approved = {row["source"]: row for row in review if row["status"] == "project_standard"}
    unresolved = {row["source"] for row in review if row["status"] == "unresolved"}
    assert len(review) == 122 and len(approved) == len(patch) == 114
    assert len(unresolved) == 8
    assert len({row["source"] for row in patch}) == 114
    assert unresolved.isdisjoint({row["source"] for row in patch})
    assert all(row["status"] == "project_standard" and
               row["target"] == approved[row["source"]]["japanese"]
               for row in patch)


def test_approved_glossary_retains_scopes_and_excludes_unresolved():
    glossary = load_glossary(ROOT / "glossaries/ja.json", expected_language="ja")
    terms = {term.source: term for term in glossary.terms}
    assert len(terms) == 139
    for source in ("Gruff", "Exp. Gain", "Capped Share", "High King",
                   "Unique Horn", "Sphere", "Djinn", "Dancing"):
        assert source not in terms
    assert terms["Difficult"].context_scope == "battle_difficulty"
    assert terms["Difficult"].global_replace is False
    assert terms["Hard"].context_scope == "safari_difficulty"
    assert terms["Hard"].global_replace is False
    assert sum(not term.global_replace for term in glossary.terms) == 31
    assert glossary.matches("Difficult", "scripts") == []
    assert glossary.matches("Hard", "scripts") == []
    assert glossary.matches("Difficult", "scripts", entry_id="scr_1F10621")
    assert glossary.matches("Hard", "scripts", entry_id="scr_1FACB9D") == []
    assert glossary.matches("Hard", "scripts", entry_id="scr_1F10621") == []


def test_templates_preserve_dynamic_tokens_and_scope():
    glossary = load_glossary(ROOT / "glossaries/ja.json", expected_language="ja")
    _protected, route = glossary.protect("Route 7", "map_names")
    assert len(route) == 1 and route[0]["target"] == "7ばんどうろ"
    assert glossary.protect("Route 7", "scripts")[1] == []
    _protected, gang = glossary.protect(
        "Black [player] is here", "scripts", entry_id="scr_1F9FBCD")
    assert len(gang) == 1 and gang[0]["target"] == "ブラック[player]"
    assert glossary.protect("Black [player] is here", "scripts")[1] == []
    _protected, game = glossary.protect(
        r"New Game \+", "scripts", entry_id="scr_1F103AA")
    assert len(game) == 1 and game[0]["target"] == r"ニューゲーム\+"
    assert glossary.missing_targets(
        "Black [player] is here", "[japanese]ブラック[latin][player][japanese]がいる[latin]",
        "scripts", entry_id="scr_1F9FBCD",
    ) == []
    assert glossary.missing_targets(
        r"New Game \+", r"[japanese]ニューゲーム\+[latin]",
        "scripts", entry_id="scr_1F103AA",
    ) == []


def test_options_are_settings_only_not_ordinary_prose():
    glossary = load_glossary(ROOT / "glossaries/ja.json", expected_language="ja")
    assert glossary.protect("Options", "menu_options")[1][0]["target"] == "せってい"
    assert glossary.protect("Option", "menu_pause")[1][0]["target"] == "せってい"
    assert glossary.protect("General Options", "setting_names")[1][0]["target"] == "せってい"
    assert glossary.protect("an option", "scripts")[1] == []
    assert glossary.protect("Option", "battle_messages")[1] == []


def test_new_packed_bufferstring_owners_are_explicit_and_real():
    extractor = runpy.run_path(str(ROOT / "001_extract_unbound_text.py"))
    expected = {
        0x1F2CB11: [0x1E6C66E],
        0x1F164B9: [0x1E54CFA, 0x1E54D66],
        0x1F187A9: [0x1E54381, 0x1E553CB, 0x1E55437],
        0x1F16D88: [0x1E53903, 0x1E54E57, 0x1E54EC3],
        0x1F17512: [0x1E53B9A],
        0x1FA3C48: [0x1E6C96A],
        0x1F15C64: [0x1E54C09],
        0x1F17ADA: [0x1E53E53, 0x1E55111, 0x1E5517D],
        0x1F18108: [0x1E540EA, 0x1E5526E, 0x1E552DA],
        0x1F9D3C7: [0x1E6C75B],
        0x1F80CA6: [0x1E6C929],
        0x1FACB78: [0x1E6C8A6],
        0x1F6A015: [0x1E6C9A2],
    }
    for target, sources in expected.items():
        assert set(sources) <= set(extractor["MANUAL_TEXT_POINTER_SOURCES"][target])
    rom_path = ROOT / "rom/unbound.gba"
    if not rom_path.exists():
        pytest.skip("private source ROM unavailable")
    rom = rom_path.read_bytes()
    for target, sources in expected.items():
        for source in sources:
            assert rom[source - 2:source] == b"\x85\x00"
            assert rom[source:source + 4] == (0x08000000 + target).to_bytes(4, "little")


def test_phase5e_applies_52_and_item_name_only_when_generated():
    path = ROOT / "out/ja-phase5e-controlfix.json"
    if not path.exists():
        pytest.skip("Phase 5E pipeline not generated locally")
    rows = {row["id"]: row for row in read("out/ja-phase5e-controlfix.json")["entries"]}
    recheck = read("out/ja-phase5d-needs-context-recheck.json")["entries"]
    ready = {row["id"] for row in recheck if row["ready_for_retranslation"]}
    held = {row["id"] for row in recheck if not row["ready_for_retranslation"]}
    assert len(ready) == 52 and ready <= rows.keys()
    assert held.isdisjoint(rows)
    item = rows["tbl_item_names_00363_EB92C0"]
    assert "ナゾノクサのはっぱ" in item["translated"]
    assert len(Charmap("ja").encode(item["translated"])) == 14
    assert "ナゾノクサの はっぱ" in rows["scr_746471"]["translated"]
    assert "ナゾノクサの はっぱ" in rows["scr_75318A"]["translated"]
    for row in recheck:
        if row["ready_for_retranslation"] and row["category"] == "mission_names":
            assert " " not in row["proposed_japanese"]


def test_phase5e_controlfix_and_binary_audit_when_generated():
    first = ROOT / "out/ja-phase5e-controlfix.json"
    second = ROOT / "out/ja-phase5e-controlfix-second.json"
    audit = ROOT / "out/ja-phase5e-binary-audit.json"
    if not (first.exists() and second.exists() and audit.exists()):
        pytest.skip("Phase 5E build not generated locally")
    assert first.read_bytes() == second.read_bytes()
    result = read("out/ja-phase5e-binary-audit.json")
    assert result["status"] == "PASS"
    assert result["input_entries"] >= 674


def test_phase5e_context_glossary_and_runtime_qa_when_generated():
    paths = [ROOT / path for path in (
        "out/ja-phase5e-remaining-context.json",
        "out/ja-phase5e-glossary-audit.json",
        "tests/fixtures/ja_phase5e_runtime_subset.json",
    )]
    if not all(path.exists() for path in paths):
        pytest.skip("Phase 5E context and audit not generated locally")
    context = read("out/ja-phase5e-remaining-context.json")
    assert context["total"] == len(context["entries"]) == 44
    assert context["classification_counts"] == {
        "A": 4, "B": 16, "C": 10, "D": 2, "E": 3, "F": 8, "H": 1,
    }
    assert all(row["evidence"] and row["resolution_status"] for row in context["entries"])
    forms = [row for row in context["entries"] if row["category"] == "pokedex_form_names"]
    assert len(forms) == 5
    assert all(row["evidence"][1]["records"] for row in forms)
    audit = read("out/ja-phase5e-glossary-audit.json")
    assert len(audit["terms"]) == 114 and audit["conflict_count"] == 0
    assert audit["actually_applied_term_count"] > 0
    assert audit["actually_applied_entry_count"] >= 52
    qa = read("tests/fixtures/ja_phase5e_runtime_subset.json")
    assert 20 <= len(qa["cases"]) <= 30
    ids = {row["id"] for row in read("out/ja-phase5e-controlfix.json")["entries"]}
    assert all(case["ids"] and set(case["ids"]) <= ids for case in qa["cases"])
