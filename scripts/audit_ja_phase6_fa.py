#!/usr/bin/env python3
"""ROM-backed Phase 6 FA boundary audit; does not translate or patch a ROM."""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.fa_control import join_segments, parse_raw_segments
from lib.gen3_font import NORMAL_GLYPH_WIDTHS, NORMAL_JAPANESE_GLYPH_WIDTHS, RUNTIME_BUFFER_WIDTH
from lib.pcs_text import Charmap, decode_pcs, fc_arg_count

OUT = ROOT / "out/phase6"
SELECTION = ROOT / "tests/fixtures/ja_phase6_selection.json"
QA = ROOT / "tests/fixtures/ja_phase6_fa_runtime_qa.json"
ROM = ROOT / "rom/unbound.gba"
MODEL_BOX_WIDTH = 208  # 26 tiles, diagnostic assumption; not a proven Unbound template.
MODEL_VISIBLE_LINES = 2  # Dialogue-window assumption, not an assertion about every renderer.


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def source_raw(rom, row):
    offset = row["rom_offset"]
    decoded = decode_pcs(rom, offset, row["slot_size"])
    if not decoded.terminated or decoded.byte_length != row["source_encoded_size"]:
        raise ValueError(f"Source slot changed: {row['id']}")
    raw = rom[offset:offset + decoded.byte_length]
    expected = row["original"].strip('"')
    if decoded.text != expected:
        raise ValueError(f"Source text differs from selection: {row['id']}")
    return raw


def layout_trace(raw):
    """Normal-font approximation with real ROM width tables, no implicit wrap."""
    index = 0
    japanese = False
    line = 0
    x = 0
    page = 0
    max_x = 0
    events = []
    while index < len(raw):
        byte = raw[index]
        offset = index
        index += 1
        if byte == 0xFF:
            break
        if byte == 0xFC:
            command = raw[index]
            index += 1 + fc_arg_count(command)
            if command == 0x15:
                japanese = True
            elif command == 0x16:
                japanese = False
            continue
        if byte in (0xFD, 0xF7, 0xF8, 0xF9):
            index += 1
            if byte == 0xFD:
                x += RUNTIME_BUFFER_WIDTH
            max_x = max(max_x, x)
            continue
        if byte in (0xFE, 0xFA, 0xFB):
            events.append({"byte_offset": offset, "control": f"{byte:02X}",
                           "line_before": line, "x_before": x, "page_before": page})
            x = 0
            if byte == 0xFE:
                line += 1
            elif byte == 0xFB:
                line = 0
                page += 1
            # FA moves window pixels but does not change printer currentY.
            events[-1].update({"line_after_model": line, "page_after": page})
            continue
        x += ((10 if byte == 0 else NORMAL_JAPANESE_GLYPH_WIDTHS[byte])
              if japanese else NORMAL_GLYPH_WIDTHS[byte])
        max_x = max(max_x, x)
    return {"box_width_pixels_assumed": MODEL_BOX_WIDTH,
            "visible_lines_assumed": MODEL_VISIBLE_LINES,
            "normal_font": True, "buffer_width_estimate": RUNTIME_BUFFER_WIDTH,
            "max_line_pixels": max_x, "overflow_under_assumption": max_x > MODEL_BOX_WIDTH,
            "events": events, "pixel_perfect": False}


def boundary_evidence(segments):
    results = []
    current_line = 0
    for index, segment in enumerate(segments):
        control = segment["after_control"]
        if control == "FE":
            current_line += 1
        elif control == "FB":
            current_line = 0
        elif control == "FA":
            previous = segment["text"].rstrip()
            next_text = segments[index + 1]["text"] if index + 1 < len(segments) else ""
            results.append({"control_offset": segment["control_offset"],
                            "after_segment_index": index,
                            "input_boundary": True,
                            "rendered_line_boundary": True,
                            "sentence_boundary": previous.endswith((".", "!", "?", "。", "！", "？")),
                            "clause_boundary": previous.endswith((",", ";", ":")),
                            "full_textbox_boundary_under_2_line_model": current_line >= 1,
                            "next_segment_starts": next_text[:40],
                            "semantic_classification": "sentence" if previous.endswith((".", "!", "?")) else
                            "clause" if previous.endswith((",", ";", ":")) else "mid_sentence_or_undetermined"})
            # FA moves window pixels, not the printer's currentY coordinate.
    return results


def candidate_layout(candidate):
    if not candidate:
        return None
    try:
        payload = Charmap("ja").encode("[japanese]" + candidate + "[latin]")
        if isinstance(payload, tuple):
            payload = payload[0]
        return layout_trace(payload)
    except (ValueError, UnicodeError) as exc:
        return {"error": str(exc), "pixel_perfect": False}


def audit_30(selection, audit, reviewed, rom):
    rows = []
    for prior in audit["entries"]:
        row = selection[prior["id"]]
        raw = source_raw(rom, row)
        segments = parse_raw_segments(raw, rom_offset=row["rom_offset"])
        if join_segments(segments) != prior["decoded_original"]:
            raise ValueError(f"Segment loss: {row['id']}")
        fa_offsets = [segment["control_offset"] for segment in segments
                      if segment["after_control"] == "FA"]
        if fa_offsets != [row["rom_offset"] + n for n in prior["source_fa_byte_positions"]]:
            raise ValueError(f"FA offset mismatch: {row['id']}")
        candidate = reviewed[row["id"]]["reviewed_japanese"]
        rows.append({"id": row["id"], "rom_offset": f"0x{row['rom_offset']:08X}",
                     "gba_address": row["gba_address"],
                     "pointer_owners": row["pointer_owners"],
                     "raw_bytes": raw.hex(" "), "decoded_source": prior["decoded_original"],
                     "control_sequence": [s["after_control"] for s in segments if s["after_control"]],
                     "control_offsets": [f"0x{s['control_offset']:08X}" for s in segments if s["after_control"]],
                     "source_text_segments": segments,
                     "fa_boundary_evidence": boundary_evidence(segments),
                     "japanese_candidate": candidate,
                     "provisional_fa_text_positions": prior["target_text_positions"],
                     "source_layout": layout_trace(raw),
                     "candidate_layout": candidate_layout(candidate),
                     "classification": "STILL_AMBIGUOUS",
                     "chosen_fa_location": None,
                     "reason": "Draft FA was appended provisionally; target prose was not translated per source display segment. No reviewed Japanese segment boundary or exact window proof.",
                     "confidence": "low"})
    if len(rows) != 30:
        raise ValueError(f"Expected 30 provisional rows, got {len(rows)}")
    return rows


def classify_batch03(row):
    controls = row["controls"]
    if not controls.get("FA"):
        return "no_FA"
    if (controls["FA"] == 1 and not controls.get("FB")
            and not row.get("buffers") and not controls.get("FC")):
        return "FA_simple_structure"
    return "FA_complex_structure"


def phase6_counts(selection):
    fa = [row for row in selection if row["controls"].get("FA")]
    return {"selected_entries": len(selection), "fa_entries": len(fa),
            "fa_controls": sum(row["controls"]["FA"] for row in fa),
            "multiple_fa_entries": sum(row["controls"]["FA"] > 1 for row in fa),
            "fa_plus_fe": sum(bool(row["controls"].get("FE")) for row in fa),
            "fa_plus_fb": sum(bool(row["controls"].get("FB")) for row in fa),
            "fa_plus_buffer": sum(bool(row.get("buffers")) for row in fa),
            "fa_plus_fc08_timed_pause": sum(bool(row["controls"].get("FC_08")) for row in fa),
            "fa_plus_other_wait_or_control": sum(any(row["controls"].get(code)
                for code in ("FC", "F7", "F8", "F9")) for row in fa)}


def runtime_qa(rows):
    ids = ("scr_1F0BB4B", "scr_1F0BC67", "scr_1F0BD67", "scr_1F0C11C")
    descriptions = {
        "scr_1F0BB4B": ("Mom / departure dialogue (text-inferred)", "NEW GAME序盤、家を出る前後に母親へ話す。イベント分岐・マップは未確認。"),
        "scr_1F0BC67": ("Mom / Mission Log explanation (text-inferred)", "NEW GAME序盤、Super CubeとMission Logの説明イベントを進める。実到達は未確認。"),
        "scr_1F0BD67": ("Mom / Super Cube component (text-inferred)", "NEW GAME序盤、自室のSuper Cube部品に関する母親の説明を進める。実到達は未確認。"),
        "scr_1F0C11C": ("Costume Box tutorial (text-inferred)", "NEW GAME序盤、Costume Box受領・説明イベントを進める。実到達は未確認。"),
    }
    by_id = {row["id"]: row for row in rows}
    cases = []
    for entry_id in ids:
        row = by_id[entry_id]
        place, reach = descriptions[entry_id]
        sequence = []
        for index, segment in enumerate(row["source_text_segments"]):
            sequence.append(f"JP_SEGMENT_{index}_UNREVIEWED")
            if segment["after_control"]:
                sequence.append(segment["after_control"])
        cases.append({"entry_id": entry_id, "location_event": place, "how_to_reach": reach,
                      "runtime_reachability": "candidate_only_not_played",
                      "source_english_behavior": row["decoded_source"],
                      "expected_japanese_display_sequence": sequence,
                      "japanese_sequence_status": "unreviewed_template_not_in_ROM; current_Batch02_ROM_displays_English",
                      "input_required_at": [f"0x{e['control_offset']:08X}" for e in row["source_text_segments"]
                                            if e["after_control"] in ("FA", "FB")],
                      "line_scroll_at": [f"0x{e['control_offset']:08X}" for e in row["source_text_segments"]
                                         if e["after_control"] == "FA"],
                      "failure_signs": "押下前に次の区間が表示される、空行だけをスクロールする、文字が重なる／欠ける、FA後の文が消える。"})
    return {"metadata": {"count": len(cases), "rom_status": "not_built", "runtime_status": "unverified"},
            "cases": cases}


def build():
    rom = ROM.read_bytes()
    selection = read(SELECTION)["entries"]
    by_id = {row["id"]: row for row in selection}
    prior = read(OUT / "ja_phase6_batch02_scroll_audit.json")
    reviewed = {row["id"]: row for row in read(OUT / "ja_phase6_batch02_reviewed.json")["entries"]}
    rows = audit_30(by_id, prior, reviewed, rom)
    batch03 = read(OUT / "ja_phase6_batch03_for_claude.json")
    batch03_rows = []
    annotated = json.loads(json.dumps(batch03))
    for source, target in zip(batch03["entries"], annotated["entries"]):
        classification = classify_batch03(source)
        audit_row = {"id": source["id"], "classification": classification,
                     "fa_count": source["controls"].get("FA", 0),
                     "segmented_handoff_required": classification != "no_FA"}
        if classification != "no_FA":
            selected = by_id[source["id"]]
            segments = parse_raw_segments(source_raw(rom, selected), rom_offset=selected["rom_offset"])
            target["control_segments"] = [{"text": s["text"], "after_control": s["after_control"]}
                                          for s in segments]
            target["source_boundary_sequence"] = [s["after_control"] for s in segments
                                                  if s["after_control"]]
            target["fa_placement_policy"] = "require_segments"
            target["translation_units"] = [{"segment_index": index, "english": s["text"]}
                                           for index, s in enumerate(segments)]
            audit_row["control_segments"] = target["control_segments"]
        batch03_rows.append(audit_row)
    counts = Counter(row["classification"] for row in batch03_rows)
    annotated["metadata"]["fa_policy"] = "Translate translation_units independently. Never place FA; output translated_segments. Codex/controlfix reconstructs only after layout review."
    annotated["metadata"]["fa_annotated_entries"] = len(batch03_rows) - counts["no_FA"]
    write(OUT / "ja_phase6_fa_30_audit.json", {"metadata": {"count": len(rows), "status_counts": {"STILL_AMBIGUOUS": len(rows)},
                                                "rom_source": str(ROM), "runtime_unverified": True}, "entries": rows})
    write(OUT / "ja_phase6_batch03_fa_audit.json", {"metadata": {"counts": dict(counts),
                                                      "segmented_handoff_required": len(batch03_rows) - counts["no_FA"]},
                                                  "entries": batch03_rows})
    write(OUT / "ja_phase6_batch03_fa_segmented_input.json", annotated)
    write(OUT / "ja_phase6_fa_selection_counts.json", phase6_counts(selection))
    write(QA, runtime_qa(rows))
    print({"thirty": len(rows), "batch03": dict(counts), "phase6": phase6_counts(selection),
           "runtime_qa": 4})


if __name__ == "__main__":
    build()
