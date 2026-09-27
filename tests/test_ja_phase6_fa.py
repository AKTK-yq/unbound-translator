"""Fail-closed FA placement and ROM-derived display-segment tests."""

import json
from pathlib import Path
import subprocess
import sys

import pytest

from lib.fa_control import join_segments, parse_raw_segments, reconstruct_reviewed_segments
from lib.pcs_text import Charmap
from scripts.audit_ja_phase6_fa import phase6_counts, source_raw
from scripts.audit_ja_phase6_batch02_controls import scroll_semantics

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out/phase6"


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


@pytest.mark.parametrize("original,expected", [
    ("A\nB\\lC", ["FE", "FA"]),
    ("A\\lB\n\nC", ["FA", "FB"]),
    ("A\\lB\\lC", ["FA", "FA"]),
    ("A[buffer1]\\lB", ["FA"]),
])
def test_raw_source_segment_parser(original, expected):
    raw = Charmap("ja").encode(original)
    segments = parse_raw_segments(raw, rom_offset=0x100)
    assert join_segments(segments) == original
    assert [s["after_control"] for s in segments if s["after_control"]] == expected
    assert all(s["control_offset"] >= 0x100 for s in segments if s["after_control"])


def test_parser_skips_control_argument_equal_to_fa():
    segments = parse_raw_segments(bytes.fromhex("FC 01 FA C2 FA FF"))
    assert [s["after_control"] for s in segments if s["after_control"]] == ["FA"]
    assert segments[0]["control_offset"] == 4


def test_reconstruction_preserves_source_boundaries_not_character_index():
    segments = parse_raw_segments(Charmap("ja").encode("A\nB\\lC\n\nD"))
    translated = reconstruct_reviewed_segments(
        "A\nB\\lC\n\nD", segments, ["あ", "い", "う", "え"]
    )
    assert translated == "あ\nい\\lう\n\nえ"
    with pytest.raises(ValueError, match="layout boundary"):
        reconstruct_reviewed_segments("A\nB\\lC\n\nD", segments,
                                      ["あい\\l", "う", "え", "お"])
    with pytest.raises(ValueError, match="structure differs"):
        reconstruct_reviewed_segments("A\nB\\lC", segments, ["あ", "い", "う", "え"])


def run_controlfix(tmp_path, entry, source_original):
    input_path = tmp_path / "input.json"
    source_path = tmp_path / "source.json"
    output_path = tmp_path / "fixed.json"
    report_path = tmp_path / "report.json"
    input_path.write_text(json.dumps({"entries": [entry]}, ensure_ascii=False), encoding="utf-8")
    source_path.write_text(json.dumps({"entries": [{"id": entry["id"],
                                                     "original": source_original}]}, ensure_ascii=False),
                           encoding="utf-8")
    subprocess.run([sys.executable, str(ROOT / "004_controlfix_translations.py"),
                    str(input_path), "-o", str(output_path), "--source", str(source_path),
                    "--target-lang", "ja", "--report", str(report_path)],
                   cwd=ROOT, check=True, capture_output=True, text=True)
    return read(output_path)["entries"][0], read(report_path)


def test_controlfix_segmented_fa_preserved_and_idempotent(tmp_path):
    original = "A\nB\\lC[buffer1]\n\nD"
    segments = parse_raw_segments(Charmap("ja").encode(original))
    entry = {"id": "fa_fixture", "category": "scripts", "original": original,
             "translated": "あいうえお\\l", "fa_placement_policy": "require_segments",
             "control_segments": [{"text": s["text"], "after_control": s["after_control"]}
                                  for s in segments],
             "source_boundary_sequence": ["FE", "FA", "FB"],
             "controls": {"FE": 1, "FA": 1, "FB": 1},
             "translated_segments": ["あ", "い", "う[buffer1]", "え"],
             "fa_layout_reviewed": True}
    fixed, report = run_controlfix(tmp_path, entry, original)
    assert fixed["translated"] == "[japanese]あ\nい\\lう[latin][buffer1][japanese]\n\nえ[latin]"
    assert fixed["fa_placement_status"] == "RESOLVED_SEGMENTED"
    assert report["stats"]["fa_segmented_rebuilt"] == 1
    fixed_again, _ = run_controlfix(tmp_path, fixed, original)
    assert fixed_again["translated"] == fixed["translated"]


@pytest.mark.parametrize("mutation", ["no_segments", "no_layout", "moved_buffer", "index_restore",
                                      "wrong_sequence", "unknown_glyph"])
def test_unreviewed_or_ambiguous_fa_is_held(tmp_path, mutation):
    original = "A[buffer1]\\lB"
    segments = parse_raw_segments(Charmap("ja").encode(original))
    entry = {"id": "fa_fixture", "category": "scripts", "original": original,
             "translated": "あ[buffer1]い\\l", "fa_placement_policy": "require_segments",
             "control_segments": [{"text": s["text"], "after_control": s["after_control"]}
                                  for s in segments],
             "source_boundary_sequence": ["FA"],
             "controls": {"FA": 1},
             "translated_segments": ["あ[buffer1]", "い"],
             "fa_layout_reviewed": True}
    if mutation == "no_segments":
        entry.pop("translated_segments")
    elif mutation == "no_layout":
        entry["fa_layout_reviewed"] = False
    elif mutation == "moved_buffer":
        entry["translated_segments"] = ["あ", "い[buffer1]"]
    elif mutation == "wrong_sequence":
        entry["source_boundary_sequence"] = ["FE"]
    elif mutation == "unknown_glyph":
        entry["translated_segments"] = ["漢[buffer1]", "い"]
    else:
        entry.pop("translated_segments")
        entry["translated"] = "あ[buffer1]い\\l"  # matching count, wrong display boundary
    fixed, report = run_controlfix(tmp_path, entry, original)
    assert fixed["translated"] is None
    assert fixed["fa_placement_status"] == "FA_PLACEMENT_REVIEW_REQUIRED"
    assert report["stats"]["fa_placement_review_required"] == 1


def test_rom_semantics_and_30_source_segments():
    rom = (ROOT / "rom/unbound.gba").read_bytes()
    fixture = read(ROOT / "tests/fixtures/ja_phase6_fa_semantics.json")
    assert scroll_semantics(rom)["targets"] == fixture["targets_gba"]
    assert rom[0x5B22:0x5B2A] == bytes.fromhex(fixture["state_store_bytes_rom_0x5B22"])
    rows = read(OUT / "ja_phase6_fa_30_audit.json")["entries"]
    selection = {row["id"]: row for row in read(ROOT / "tests/fixtures/ja_phase6_selection.json")["entries"]}
    assert len(rows) == 30
    for row in rows:
        raw = source_raw(rom, selection[row["id"]])
        assert row["raw_bytes"] == raw.hex(" ")
        segments = parse_raw_segments(raw, rom_offset=selection[row["id"]]["rom_offset"])
        assert join_segments(segments) == row["decoded_source"]
        assert row["source_text_segments"] == segments
        assert row["classification"] == "STILL_AMBIGUOUS"
        assert row["chosen_fa_location"] is None


def test_batch03_handoff_is_segmented_and_phase6_counts():
    selection = read(ROOT / "tests/fixtures/ja_phase6_selection.json")["entries"]
    assert phase6_counts(selection) == read(OUT / "ja_phase6_fa_selection_counts.json")
    batch = read(OUT / "ja_phase6_batch03_fa_segmented_input.json")
    audit = read(OUT / "ja_phase6_batch03_fa_audit.json")
    assert len(batch["entries"]) == 408
    assert audit["metadata"]["counts"] == {
        "no_FA": 286, "FA_simple_structure": 2, "FA_complex_structure": 120}
    assert audit["metadata"]["segmented_handoff_required"] == 122
    for row in batch["entries"]:
        if "\\l" in row["original"]:
            assert row["fa_placement_policy"] == "require_segments"
            assert row["translation_units"]
            assert "\\l" in join_segments(row["control_segments"])
    handoff = read(OUT / "ja_phase6_batch03_style_handoff.json")
    assert handoff["batch03_gate"] == "STATIC_GO_SEGMENTED_INPUT_ONLY"
    assert handoff["fa_translation_input"] == "out/phase6/ja_phase6_batch03_fa_segmented_input.json"
    assert "Do not choose any FA" in handoff["fa_claude_instruction"]
    assert "fa_placement_review_required" in handoff["fa_ambiguous_warning"]
    qa = read(ROOT / "tests/fixtures/ja_phase6_fa_runtime_qa.json")
    assert len(qa["cases"]) == 4
    assert qa["metadata"]["runtime_status"] == "unverified"
