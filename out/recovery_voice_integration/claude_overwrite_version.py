#!/usr/bin/env python3
"""Phase 6C-3C: technical integration of the four NPC voice rewrite candidates.

Stages: prepare (verify + build controlfix input), finalize (after 004 controlfix),
audit (binary audit of the incremental ROM). No new translation: the four proposals
come verbatim from Phase 6C-3B and each is applied only if every gate passes.
"""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import runpy
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.pcs_text import Charmap
from lib.translation_glossary import load_glossary
from lib.translation_tokens import semantic_tokens
from scripts.audit_ja_phase6_batch01_fit import line_widths
from scripts.build_ja_phase6_batch02 import owner_audit
from scripts.build_ja_phase6_batch05 import control_sequence

OUT = ROOT / "out/phase6"
FIX = ROOT / "tests/fixtures"
BASE_ROM = ROOT / "out/unbound-ja-phase6-cleanup-glossary.gba"
NEW_ROM = ROOT / "out/unbound-ja-phase6-voice-pass1.gba"
SOURCE_ROM = ROOT / "rom/unbound.gba"
CANDIDATES = FIX / "ja_phase6_voice_rewrite_candidates.json"
PROFILES = FIX / "ja_phase6_voice_profiles_claude.json"
AUDIT = FIX / "ja_phase6_voice_integration_audit.json"
BASELINE = OUT / "ja_phase6_cleanup_glossary_combined_controlfix.json"
INPUT = OUT / "ja_phase6_voice_pass1_input.json"
CONTROLFIX = OUT / "ja_phase6_voice_pass1_controlfix.json"
SAFE = OUT / "ja_phase6_voice_pass1_safe_controlfix.json"
SOURCE_MD5 = "9cad8e771940e7f7094d13911552cef0"
BASE_SHA256 = "3cd6d07baa4c287e10dab9d0a04960455311d6ee829e189abc57940040af638a"
BASELINE_COUNT = 2261
BATTLE_WINDOW_PHYSICAL_PX = 222  # ROM-proven battle message window span (Phase 6B-4.6)
HAN = re.compile(r"[㐀-鿿]")
TARGET_IDS = ["scr_1F02029", "scr_1F02145", "scr_740753", "scr_1F06A82"]

# Reviewer's meaning decision for each entry (English checked against current and proposed Japanese).
MEANING = {
    "scr_1F02029": {
        "decision": "approved",
        "english": "My special [Fire]-types will burn you to a crisp!",
        "finding": "『special』は五つの定型文が並ぶ中の一つ（special / fast / tough / physical / mental defense）で、"
                   "能力値の系統を表す。とくせい(Ability)ではない。",
        "evidence": [
            {"entry": "scr_1F02029", "english": "special Fire-types"},
            {"entry": "scr_1F020C8", "english": "fast Water-types"},
            {"entry": "scr_1F02118", "english": "tough Grass-types"},
            {"entry": "scr_1F02164", "english": "physical dark fury"},
            {"entry": "scr_1F02197", "english": "mental defense (psychic powers)"}],
        "corroboration": "各トレーナーの先頭ポケモン（ROMの種族IDから復号）が、形容詞に対応する能力値の高い種族である。"
                         "ただし種族値は参考知識で、証明ではない。主根拠は定型文の並び。",
        "wording": "『とくこう』（能力値の略称）も検討したが、並びの『ぶつりこうげき』(scr_1F02164)に合わせて"
                   "『とくしゅこうげきの』を採用。Abilityの『とくせい』とは混同しない。",
    },
    "scr_1F02145": {
        "decision": "approved",
        "english": "My Grass-types didn’t help me.",
        "finding": "直前の台詞(scr_1F02118)の『help me win』に対応する敗北台詞。『helpしなかった』が原文。"
                   "現行の『やくに たたなかった』は『役に立たなかった』で原文より強い非難。",
        "evidence": [{"entry": "scr_1F02118", "english": "My tough Grass-types will help me win!"}],
    },
    "scr_740753": {
        "decision": "approved",
        "english": "Are you my mommy?",
        "finding": "人違いの問いかけ。後続の『You’re not my mommy』(scr_7459E1)と対。人称を省いても意味は同じ。",
        "evidence": [{"entry": "scr_7459E1", "english": "Oh no. You’re not my mommy."}],
    },
    "scr_1F06A82": {
        "decision": "approved",
        "english": "I’m going to rough you up!",
        "finding": "威嚇の宣言。『してあげる』は恩恵の言い方で威嚇に合わない。『してやる』は同型の挑発文で使用済み。",
        "evidence": [{"entry": "scr_1F02029", "english": "…will burn you to a crisp! (→してやる)"}],
    },
}


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def tokens(text):
    return re.findall(r"\\CC[0-9A-F]+|\\[A-Za-z.]|\[[a-z0-9_]+\]|\n", text)


def check_entries():
    rom = BASE_ROM.read_bytes()
    source = SOURCE_ROM.read_bytes()
    assert hashlib.sha256(rom).hexdigest() == BASE_SHA256
    assert hashlib.md5(source).hexdigest() == SOURCE_MD5
    baseline = read(BASELINE)["entries"]
    by_id = {x["id"]: x for x in baseline}
    candidates = {c["entry_id"]: c for c in read(CANDIDATES)["candidates"]}
    assert list(candidates) == TARGET_IDS and len(baseline) == BASELINE_COUNT
    prepared = {x["id"]: x for x in read(ROOT / "out/ja-phase5e-prepared.json")["entries"]}
    voice = {d["id"]: (g, evs) for g in read(OUT / "ja_phase6_voice_review_for_claude.json")["groups"]
             for d, evs in zip(g["dialogue"], g["speaker_evidence"])}
    glossary = load_glossary(ROOT / "glossaries/ja.json", expected_language="ja")
    codec = Charmap("ja")
    injector = runpy.run_path(str(ROOT / "005_hybrid_injector.py"))

    def payload(entry, text):
        item = dict(entry)
        item["translated"] = text
        return injector["encode_text"](codec, injector["translation_for_injection"](item), plain_script=False)

    results = []
    owner_rows = [{"id": k, "rom_offset": int(by_id[k]["address"], 16), "pointer_owners": by_id[k]["pointer_sources"]}
                  for k in TARGET_IDS]
    owners = {x["id"]: x for x in owner_audit(owner_rows, rom)["entries"]}
    for key in TARGET_IDS:
        entry, cand = by_id[key], candidates[key]
        current, proposed = cand["current_japanese"], cand["proposed_japanese"]
        address, slot = int(entry["address"], 16), entry["byte_length"]
        english_raw = source[address:address + slot]
        now, new = payload(entry, current), payload(entry, proposed)
        rom_slot = rom[address:address + slot]
        english_widths = line_widths(english_raw)
        proposed_widths, current_widths = line_widths(new), line_widths(now)
        evidence = voice[key][1][0]
        gloss_prepared = prepared[key]["translation_source"]
        missing_current = glossary.missing_targets(gloss_prepared, current, entry["category"], entry_id=key)
        missing_proposed = glossary.missing_targets(gloss_prepared, proposed, entry["category"], entry_id=key)
        gate = {
            "applied_text_matches_candidate_current": entry["translated"] == current,
            "rom_slot_matches_current_encoding": rom_slot == now.ljust(slot, b"\xff"),
            "storage": "in_place_original_slot",
            "meaning_review": MEANING[key]["decision"],
            "protected_tokens_equal": semantic_tokens(current) == semantic_tokens(proposed),
            "control_token_sequence_equal": tokens(current) == tokens(proposed),
            "source_english_control_sequence_equal": control_sequence(english_raw) == control_sequence(new),
            "pcs_encode_ok": True,
            "kanji_free": not HAN.search(proposed),
            "glossary_missing_targets_current": missing_current,
            "glossary_missing_targets_proposed": missing_proposed,
            "bytes_current": len(now), "bytes_proposed": len(new), "source_slot_bytes": slot,
            "fits_source_slot": len(new) <= slot,
            "pointer_owners_complete": not owners[key]["missing"] and not owners[key]["stale"],
            "pointer_owner_detail": owners[key],
            "width": {
                "english_source_line_px": english_widths, "current_japanese_line_px": current_widths,
                "proposed_line_px": proposed_widths,
                "proposed_max_not_wider_than_english_source_max": max(proposed_widths) <= max(english_widths),
                "proposed_lines_equal_current": len(proposed_widths) == len(current_widths),
                "within_proven_battle_window_222px": max(proposed_widths) <= BATTLE_WINDOW_PHYSICAL_PX,
                "also_below_240px_screen": max(proposed_widths) < 240,
                "renderer_evidence": {
                    "trainerbattle_text_operand_index": evidence["text_operand_index"],
                    "trainerbattle_mode": evidence["battle_mode"],
                    "text_operand_offset": evidence["text_operand_offset"],
                    "window_geometry": "Unbound field/battle display window for this operand is not proven. "
                                       "Fit is therefore judged against (1) the shipped English line widths of the same string "
                                       "in the same window and (2) the ROM-proven 222px battle message span, never against 240px alone."}},
        }
        mandatory = ("applied_text_matches_candidate_current", "rom_slot_matches_current_encoding", "protected_tokens_equal",
                     "control_token_sequence_equal", "source_english_control_sequence_equal", "pcs_encode_ok", "kanji_free",
                     "fits_source_slot", "pointer_owners_complete")
        width = gate["width"]
        passed = (all(gate[k] for k in mandatory) and gate["meaning_review"] == "approved"
                  and not missing_proposed and width["proposed_max_not_wider_than_english_source_max"]
                  and width["proposed_lines_equal_current"] and width["within_proven_battle_window_222px"])
        results.append({"entry_id": key, "speaker_id": cand["speaker_id"], "original_english": cand["original_english"],
                        "current_japanese": current, "proposed_japanese": proposed,
                        "meaning": MEANING[key], "gate": gate, "decision": "APPLY" if passed else "HOLD",
                        "hold_reasons": [] if passed else [k for k in mandatory if not gate[k]]})
    return results, baseline


def glossary_mismatch_audit():
    glossary = load_glossary(ROOT / "glossaries/ja.json", expected_language="ja")
    texts = {r["id"]: r for r in read(ROOT / "out/unbound-texts.json")["entries"]}
    prepared = {x["id"]: x for x in read(ROOT / "out/ja-phase5e-prepared.json")["entries"]}
    applied = {x["id"]: x for x in read(BASELINE)["entries"]}
    frost = [t for t in glossary.terms if t.source == "Frost Mountain"]
    frost_entries = [{"id": k, "category": v["category"], "english": v["original"].strip('"').replace("\n", " ")[:80]}
                     for k, v in texts.items() if "Frost Mountain" in re.sub(r"\\l|\s+", " ", v["original"])]
    frost_forms = Counter()
    for k in (x["id"] for x in frost_entries if x["id"] in applied):
        for form in ("フロストマウンテン", "フロストやま"):
            if form in applied[k]["translated"]:
                frost_forms[form] += 1
    text_f = prepared["scr_1F0AECE"]["translation_source"]
    route = [t for t in glossary.terms if t.source == "Route [N]"]
    route_hits = {"scripts": [t.target for _, _, t in glossary.matches("Route 8", "scripts", entry_id="scr_1F0B076")],
                  "map_names": [t.target for _, _, t in glossary.matches("Route 8", "map_names")]}
    route_usage = Counter()
    for k, entry in applied.items():
        english = texts.get(k, {}).get("original", "")
        if re.search(r"(?<!\w)Route \d+", english):
            form = ("[N]ばんどうろ" if re.search(r"\d+ばんどうろ", entry["translated"]) else
                    "ルート[N]" if "ルート" in entry["translated"] else "other")
            route_usage[(entry["category"], form)] += 1
    return {
        "scr_1F0AECE": {
            "current_japanese_form": "フロストマウンテン", "approved_glossary_form": "フロストやま",
            "english_in_entry": "Frost Mountain",
            "glossary_term_scope": [{"entry_ids": list(t.entry_ids), "categories": list(t.categories),
                                     "global_replace": t.global_replace, "context_scope": t.context_scope} for t in frost],
            "glossary_applies_to_this_entry": bool(glossary.matches(text_f, "scripts", entry_id="scr_1F0AECE")),
            "english_occurrences": frost_entries,
            "applied_japanese_form_counts": dict(frost_forms),
            "same_place": "SAME_NAME_ONLY: identical English proper name and one map-name record; a separate location is not "
                          "indicated, but same-location identity beyond the name is not independently proven",
            "finding": "glossary mismatch confirmed; the approved term is entry-scoped and does not cover this entry",
            "action": "none (not modified in this phase)"},
        "scr_1F0B076": {
            "current_japanese_form": "ルート8", "approved_glossary_form": "[N]ばんどうろ (Route [N] template)",
            "glossary_term_scope": [{"categories": list(t.categories), "context_scope": t.context_scope,
                                     "global_replace": t.global_replace, "template": t.template} for t in route],
            "template_match_in_scripts_entry": route_hits["scripts"], "template_match_in_map_names": route_hits["map_names"],
            "entry_category": applied["scr_1F0B076"]["category"],
            "applied_route_usage_by_category_and_form": {f"{c}|{f}": n for (c, f), n in sorted(route_usage.items())},
            "finding": "the map_names-only scope does not apply to this scripts entry; the template yields no match",
            "action": "none (not modified in this phase)"},
    }


def stage_prepare():
    results, baseline = check_entries()
    applied = {r["entry_id"]: r["proposed_japanese"] for r in results if r["decision"] == "APPLY"}
    entries = [dict(x) for x in baseline]
    for entry in entries:
        if entry["id"] in applied:
            entry["translated"] = applied[entry["id"]]
    write(INPUT, {"entries": entries})
    write(AUDIT, {"metadata": {"phase": "6C-3C", "stage": "prepared", "targets": TARGET_IDS},
                  "entries": results, "glossary_mismatch_audit": glossary_mismatch_audit()})
    return {r["entry_id"]: r["decision"] for r in results}


def stage_finalize():
    audit = read(AUDIT)
    baseline = read(BASELINE)["entries"]
    pre = read(INPUT)["entries"]
    controlfixed = read(CONTROLFIX)["entries"]
    twice = read(OUT / "ja_phase6_voice_pass1_controlfix_twice.json")["entries"]
    applied = [r["entry_id"] for r in audit["entries"] if r["decision"] == "APPLY"]
    assert controlfixed == pre, "controlfix changed the already controlfixed input"
    assert twice == controlfixed, "controlfix is not idempotent"
    assert len(controlfixed) == BASELINE_COUNT
    changed = [a["id"] for a, b in zip(baseline, controlfixed) if a != b]
    assert changed == [k for k in TARGET_IDS if k in applied], changed
    safe = [x for x in controlfixed if x["id"] in applied]
    write(SAFE, {"entries": safe})
    audit["metadata"].update({"stage": "finalized", "controlfix_idempotent": True,
                              "entries_changed_vs_baseline": changed, "other_entries_changed": 0})
    write(AUDIT, audit)
    return {"applied": applied, "changed": changed}


def ranges(positions):
    data = sorted(positions)
    if not data:
        return []
    result, start, last = [], data[0], data[0]
    for pos in data[1:]:
        if pos != last + 1:
            result.append(f"0x{start:08X}-0x{last:08X}")
            start = pos
        last = pos
    result.append(f"0x{start:08X}-0x{last:08X}")
    return result


def audit_rom(before_path=BASE_ROM, after_path=NEW_ROM):
    before, after = Path(before_path).read_bytes(), Path(after_path).read_bytes()
    assert len(before) == len(after) == 0x2000000
    assert hashlib.sha256(before).hexdigest() == BASE_SHA256
    safe = read(SAFE)["entries"]
    baseline = read(BASELINE)["entries"]
    plan = read(OUT / "ja_phase6_voice_pass1_dry_run_map.json")
    built = read(OUT / "ja_phase6_voice_pass1_map.json")
    assert plan["stats"] == built["stats"] and plan["relocations"] == built["relocations"] == []
    assert built["stats"]["input_entries"] == len(safe)
    for key in ("skipped_pointer_mismatch", "skipped_implausible_pointer", "skipped_no_space", "encode_errors",
                "fixed_truncated", "no_relocation_truncated", "ability_descriptions_compacted", "runtime_patches",
                "graphics_patches", "skipped_unsafe", "skipped_bounds", "relocated", "pointer_writes"):
        assert built["stats"][key] == 0, (key, built["stats"][key])
    assert built["stats"]["in_place"] == len(safe)
    codec = Charmap("ja")
    injector = runpy.run_path(str(ROOT / "005_hybrid_injector.py"))
    allowed = set()
    for entry in safe:
        raw = injector["encode_text"](codec, injector["translation_for_injection"](entry), plain_script=False)
        old, size = int(entry["address"], 16), entry["byte_length"]
        assert len(raw) <= size and after[old:old + size] == raw.ljust(size, b"\xff")
        allowed.update(range(old, old + size))
    old_relocations = {}
    for name in ("ja_phase6_batch04_map.json", "ja_phase6_batch05_incremental_map.json",
                 "ja_phase6_batch06_incremental_map.json", "ja_phase6_cleanup_incremental_map.json",
                 "ja_phase6_cleanup_glossary_incremental_map.json"):
        old_relocations.update({x["id"]: x for x in read(OUT / name)["relocations"]})
    protected = set()
    safe_ids = {x["id"] for x in safe}
    for entry in baseline:
        if entry["id"] in safe_ids:
            continue
        old = old_relocations.get(entry["id"])
        if old:
            pos = int(old["new_offset"], 16)
            protected.update(range(pos, pos + old["byte_length"]))
            for pointer in old["pointer_sources"]:
                p = int(pointer, 16)
                protected.update(range(p, p + 4))
        else:
            pos = int(entry["address"], 16)
            protected.update(range(pos, pos + entry["byte_length"]))
    assert not protected & allowed, "voice pass overlaps other translated entries"
    changed = {i for i, (x, y) in enumerate(zip(before, after)) if x != y}
    unexpected = changed - allowed
    assert not changed & protected, f"other translations changed: {ranges(changed & protected)[:5]}"
    assert not unexpected, f"unexpected bytes: {ranges(unexpected)[:5]}"
    result = {"status": "PASS", "base_sha256": hashlib.sha256(before).hexdigest(),
              "new_md5": hashlib.md5(after).hexdigest(), "new_sha256": hashlib.sha256(after).hexdigest(),
              "entries": sorted(safe_ids), "changed_bytes": len(changed), "changed_ranges": ranges(changed),
              "allowed_ranges": ranges(allowed), "unexpected_bytes": 0, "other_translated_entries_changed": 0,
              "relocated": 0, "pointer_writes": 0, "strict_incremental_dry_run": "PASS"}
    audit = read(AUDIT)
    audit["binary_audit"] = result
    audit["metadata"].update({"stage": "complete", "rom": "out/unbound-ja-phase6-voice-pass1.gba",
                              "applied": sorted(safe_ids), "applied_count": len(safe_ids)})
    write(AUDIT, audit)
    return {k: result[k] for k in ("status", "changed_bytes", "unexpected_bytes", "new_md5", "new_sha256")}


if __name__ == "__main__":
    stage = sys.argv[1] if len(sys.argv) == 2 else ""
    runner = {"prepare": stage_prepare, "finalize": stage_finalize, "audit": audit_rom}.get(stage)
    if runner is None:
        sys.exit(__doc__)
    print(runner())
