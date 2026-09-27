#!/usr/bin/env python3
"""Build untranslated Phase 6A selection, Claude handoff, and QA candidates.

This tool reads the English ROM but never patches it or invokes an LLM.
"""

from __future__ import annotations

import hashlib
import argparse
import json
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.pcs_text import Charmap, decode_pcs
from lib.pokeapi_localizer import CATEGORY_SPECS, PokeAPILocalizer
from lib.translation_glossary import load_glossary
from lib.translation_tokens import semantic_tokens, strip_hma_quotes
from scripts.build_ja_phase5_dataset import (
    BUFFER_TOKEN, EARLY_INTRO_END, EARLY_INTRO_START, NPC_BANK_END,
    NPC_BANK_START, SOURCE_MD5, control_features, renderer_for,
    runtime_class, selection_score,
)

TARGET_SIZE = 2500
BATCH_COUNT = 6
BATCH_MIN = 400
BATCH_MAX = 500
QA_SIZE = 120
BASE = ROOT / "out"
PREPARED = BASE / "ja-phase5e-prepared.json"
APPLIED = BASE / "ja-phase5f-final-controlfix.json"
HELD = BASE / "ja-phase5f-remaining-audit.json"
PHASE5_MAP = BASE / "ja-phase5f-final-map.json"
ROM = ROOT / "rom" / "unbound.gba"
MANIFEST = ROOT / "tests" / "fixtures" / "ja_phase6_selection.json"
QA = ROOT / "tests" / "fixtures" / "ja_phase6_runtime_candidates.json"
PHASE6_OUT = BASE / "phase6"

# Balanced production scope, not a census of every extracted table row.
QUOTAS = {
    "scripts": 1440, "plain_scripts": 8, "battle_messages": 235,
    "mission_names": 32, "mission_descriptions": 36,
    "mission_objectives": 25, "mission_log": 10,
    "menu_common": 22, "menu_pc": 30, "menu_game_settings": 35,
    "menu_battle": 24, "menu_list_labels": 38, "menu_link_controls": 15,
    "menu_trainer_card": 14, "menu_cube_system": 14,
    "menu_pokemon_summary": 12, "menu_item_storage": 10,
    "menu_options": 5, "menu_pokemon": 7, "menu_pokedex": 3,
    "menu_save": 3, "menu_shop": 2, "menu_pause": 2,
    "setting_names": 8, "start_menu_labels": 3,
    "pokemon_names": 58, "move_names": 58, "item_names": 58,
    "ability_names": 32, "type_names": 6, "nature_names": 6,
    "trainer_names": 23, "trainer_classes": 12, "map_names": 22,
    "pokedex_species": 16, "pokedex_descriptions": 25,
    "move_descriptions": 46, "item_descriptions": 46,
    "ability_descriptions": 28, "habitat_names": 3,
    "move_learning": 3, "trade_messages": 3,
}
TABLE_LEGACY = re.compile(r"legacy|unused|old", re.IGNORECASE)
HAN = re.compile(r"[\u3400-\u9fff]")


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def offset(entry):
    value = entry["address"]
    return int(value, 16) if isinstance(value, str) else value


def eligible(entry, applied_ids, held_ids):
    if entry["id"] in applied_ids or entry["id"] in held_ids:
        return False
    if entry["category"] not in QUOTAS:
        return False
    if TABLE_LEGACY.search(entry.get("table_name") or ""):
        return False
    if not re.search(r"[A-Za-z]", strip_hma_quotes(entry["original"])):
        return False
    confidence, _ = runtime_class(entry, set())
    return confidence in "AB"


def priority(entry, codec):
    address = offset(entry)
    category = entry["category"]
    # Proven NEW GAME operands first; owner-proven NPC bank next. Other script
    # branches are only B, regardless of text locality or apparent dialogue.
    if category in {"scripts", "plain_scripts"}:
        region = (0 if EARLY_INTRO_START <= address < EARLY_INTRO_END
                  else 1 if NPC_BANK_START <= address < NPC_BANK_END
                  else 2 if 0x1F00000 <= address < 0x1F80000 else 3)
        owner = min(int(p, 16) for p in entry["pointer_sources"])
        return (region, owner // 0x1000, owner, address)
    if category == "battle_messages":
        table = entry.get("table_name") or ""
        return (0 if table == "data.battle.text.messages" else 1,
                0 if entry.get("pointer_sources") else 1,
                entry.get("table_index") or 0, address)
    return (0 if entry.get("pointer_sources") else 1,
            entry.get("table_index") or 0, address,
            selection_score(entry, codec))


def select(prepared, applied_ids, held_ids, size=TARGET_SIZE):
    codec = Charmap()
    pools = defaultdict(list)
    for entry in prepared:
        if eligible(entry, applied_ids, held_ids):
            pools[entry["category"]].append(entry)
    for category in pools:
        pools[category].sort(key=lambda entry: priority(entry, codec))
    selected = []
    used_offsets = set()
    for category, quota in QUOTAS.items():
        for entry in pools[category]:
            if sum(row["category"] == category for row in selected) >= quota:
                break
            address = offset(entry)
            if address not in used_offsets:
                selected.append(entry)
                used_offsets.add(address)
    if len(selected) < size:
        # Fill only from same A/B, owner-proven pools; do not lower confidence
        # merely to reach the requested round number.
        remainder = sorted(
            (entry for pool in pools.values() for entry in pool
             if offset(entry) not in used_offsets),
            key=lambda entry: (entry["category"] not in {"scripts", "plain_scripts"},
                               priority(entry, codec)),
        )
        for entry in remainder[:size - len(selected)]:
            selected.append(entry)
    selected = selected[:size]
    if len(selected) != size:
        raise ValueError(f"Only {len(selected)} eligible A/B entries; need {size}")
    return selected


def cached_localizer(*, live=False):
    if live:
        return PokeAPILocalizer("ja", ROOT / ".cache" / "pokeapi", timeout=8)

    def offline(_request, timeout):
        raise OSError("Phase 6A uses verified cached PokeAPI only")

    return PokeAPILocalizer("ja", ROOT / ".cache" / "pokeapi", opener=offline)


def approved_value(entry, glossary, localizer, codec):
    source = strip_hma_quotes(entry["original"]).strip()
    category = entry["category"]
    matches = glossary.matches(source, category, entry_id=entry["id"])
    terms = []
    for start, end, term in matches:
        protected, replacement = glossary.protect(
            source[start:end], category, entry_id=entry["id"]
        )
        if replacement:
            terms.append({"source": source[start:end], "target": replacement[0]["target"],
                          "kind": term.kind, "scope": term.context_scope,
                          "global_replace": term.global_replace})
    glossary_terms = {term["source"]: term["target"] for term in terms}
    deterministic = None
    origin = None
    if len(matches) == 1 and matches[0][0] == 0 and matches[0][1] == len(source):
        _, replacements = glossary.protect(source, category, entry_id=entry["id"])
        deterministic = replacements[0]["target"]
        origin = "glossary-exact"
    official = {}
    official_status = "not_applicable"
    if category in CATEGORY_SPECS:
        value = localizer.translate_entry(entry)
        official_status = "unverified"
        if value:
            if HAN.search(value):
                official_status = "contains_kanji"
            else:
                try:
                    codec.encode(f"[japanese]{value}[latin]")
                except (UnicodeEncodeError, ValueError):
                    official_status = "unsupported_glyph"
                else:
                    official = {source: value}
                    official_status = "verified_cached_ja-hrkt"
                    deterministic = value
                    origin = "pokeapi-ja-hrkt"
    if deterministic is not None:
        try:
            codec.encode(f"[japanese]{deterministic}[latin]")
        except (UnicodeEncodeError, ValueError):
            deterministic = None
            origin = None
    return glossary_terms, terms, official, official_status, deterministic, origin


def script_groups(rows):
    scripts = [row for row in rows if row["category"] in {"scripts", "plain_scripts"}]
    scripts.sort(key=lambda row: (int(row["pointer_owners"][0], 16), row["rom_offset"]))
    groups = []
    current = []
    for row in scripts:
        owner = int(row["pointer_owners"][0], 16)
        previous = current[-1] if current else None
        if previous:
            prior_owner = int(previous["pointer_owners"][0], 16)
            if (owner - prior_owner > 0x30 or owner // 0x1000 != prior_owner // 0x1000
                    or abs(row["rom_offset"] - previous["rom_offset"]) > 0x400
                    or len(current) >= 12):
                groups.append(current)
                current = []
        current.append(row)
    if current:
        groups.append(current)
    for group in groups:
        first = group[0]
        owner = first["pointer_owners"][0]
        group_id = f"script_operand_neighborhood_{owner[2:]}"
        for index, row in enumerate(group):
            row["conversation_id"] = group_id
            row["scene_id"] = None
            row["sequence_index"] = index
            row["group_evidence"] = (
                "Near event-script pointer operands plus nearby text; dialogue order, "
                "scene, speaker, and event reachability unproven"
            )
    for row in rows:
        if row["category"] not in {"scripts", "plain_scripts"}:
            row["conversation_id"] = None
            row["scene_id"] = row.get("table_name")
            row["sequence_index"] = row.get("table_index")
            row["group_evidence"] = "Structured table membership; not a spoken conversation"
    return groups


def make_rows(selected, rom, glossary, localizer):
    codec = Charmap(target_lang="ja")
    rows = []
    for entry in selected:
        address = offset(entry)
        decoded = decode_pcs(rom, address, entry["byte_length"])
        if not decoded.terminated or decoded.byte_length > entry["byte_length"]:
            raise ValueError(f"Invalid ROM text slot: {entry['id']}")
        controls = control_features(rom[address:address + decoded.byte_length])
        source = strip_hma_quotes(entry["original"])
        protected = semantic_tokens(source)
        placeholders = entry.get("semantic_token_placeholders") or []
        buffers = [token for token in protected if BUFFER_TOKEN.fullmatch(token)]
        owners = entry.get("pointer_sources") or []
        no_relocation = bool(entry.get("no_relocation"))
        relocatable = bool(owners and entry.get("is_pointer_based") and not no_relocation)
        fixed = not relocatable
        renderer = renderer_for(entry["category"])
        confidence, evidence = runtime_class(entry, set())
        reasons = []
        if fixed:
            reasons.append("fixed_or_no_relocation")
        if entry["category"].startswith("menu_") or entry["category"] in {"setting_names", "start_menu_labels"}:
            reasons.append("narrow_ui_unmeasured")
        if len(buffers) > 1:
            reasons.append("multiple_dynamic_buffers")
        if len(owners) > 1:
            reasons.append("multiple_pointer_owners")
        if controls.get("FB") or controls.get("FA") or controls.get("FC"):
            reasons.append("special_or_page_controls")
        if renderer == "unknown":
            reasons.append("unknown_renderer")
        risk = "high" if reasons else "medium" if protected or entry["category"] in {"scripts", "battle_messages"} else "low"
        glossary_terms, glossary_details, official_terms, official_status, deterministic, origin = approved_value(
            entry, glossary, localizer, codec
        )
        encoded_deterministic = len(codec.encode(f"[japanese]{deterministic}[latin]")) if deterministic else None
        row = {
            "id": entry["id"], "category": entry["category"], "original": entry["original"],
            "translation_source": entry.get("translation_source", source),
            "rom_offset": address, "gba_address": f"0x{0x08000000 + address:08X}",
            "slot_size": entry["byte_length"], "source_encoded_size": decoded.byte_length,
            "pointer_owners": owners, "controls": controls, "buffers": buffers,
            "placeholders": placeholders, "protected_tokens": protected,
            "renderer_group": renderer, "runtime_confidence": confidence,
            "runtime_evidence": evidence, "speaker": "unknown", "speaker_confidence": "unknown",
            "technical_risk": risk, "risk_reasons": reasons,
            "relocation_possible": relocatable, "fixed": fixed,
            "no_relocation": no_relocation, "already_translated": False,
            "phase5_unresolved": False, "glossary_terms": glossary_terms,
            "glossary_term_details": glossary_details, "official_terms": official_terms,
            "official_status": official_status, "deterministic_translation": deterministic,
            "deterministic_origin": origin, "deterministic_encoded_size": encoded_deterministic,
            "requires_fit_review": bool(fixed and encoded_deterministic and encoded_deterministic > entry["byte_length"]),
            "table_name": entry.get("table_name"), "table_index": entry.get("table_index"),
            "notes": "Runtime usage of this exact row unobserved; scene and speaker require play/trace.",
        }
        rows.append(row)
    script_groups(rows)
    return rows


def contexts(rows, prepared, applied, held_ids):
    applied_by_id = {row["id"]: row.get("translated") for row in applied}
    # Exact script-owner proximity only; no broad ROM-neighbor context is
    # claimed as the same conversation.
    all_scripts = sorted((entry for entry in prepared if entry["category"] in {"scripts", "plain_scripts"}
                          and entry.get("pointer_sources") and entry["id"] not in held_ids),
                         key=lambda entry: int(entry["pointer_sources"][0], 16))
    owner_index = {entry["id"]: i for i, entry in enumerate(all_scripts)}

    def context_item(entry, basis):
        item = {"id": entry["id"], "original": entry["original"], "basis": basis,
                "confidence": "medium" if basis == "same_operand_neighborhood" else "low"}
        if entry["id"] in applied_by_id:
            item["phase5_japanese"] = applied_by_id[entry["id"]]
            item["already_translated"] = True
        return item

    for row in rows:
        if row["conversation_id"]:
            index = owner_index[row["id"]]
            neighbors = []
            for step in range(-4, 5):
                if not step or not 0 <= index + step < len(all_scripts):
                    continue
                entry = all_scripts[index + step]
                if abs(int(entry["pointer_sources"][0], 16) - int(row["pointer_owners"][0], 16)) > 0x50:
                    continue
                if abs(offset(entry) - row["rom_offset"]) > 0x800:
                    continue
                neighbors.append((step, entry))
            before = [context_item(entry, "same_operand_neighborhood") for step, entry in neighbors if step < 0][-3:]
            after = [context_item(entry, "same_operand_neighborhood") for step, entry in neighbors if step > 0][:3]
        else:
            before = after = []
        row["context_before"] = before
        row["context_after"] = after
        row["context_confidence"] = "medium" if before or after else "none"
def partition(rows):
    groups = defaultdict(list)
    for row in rows:
        key = row["conversation_id"] or f"single:{row['id']}"
        groups[key].append(row)
    ordered = sorted(groups.values(), key=lambda group: (
        0 if group[0]["category"] in {"scripts", "plain_scripts"} else
        1 if group[0]["category"].startswith("mission_") else
        2 if group[0]["category"] == "battle_messages" else
        3 if group[0]["category"].startswith("menu_") or group[0]["category"] in {"setting_names", "start_menu_labels"} else 4,
        min(row["rom_offset"] for row in group),
    ))
    batches = [[] for _ in range(BATCH_COUNT)]
    target = len(rows) // BATCH_COUNT
    index = 0
    for group in ordered:
        if index < BATCH_COUNT - 1 and len(batches[index]) + len(group) > target - 8:
            index += 1
        batches[index].extend(group)
    if any(not BATCH_MIN <= len(batch) <= BATCH_MAX for batch in batches):
        raise ValueError(f"Batch sizes outside {BATCH_MIN}-{BATCH_MAX}: {[len(x) for x in batches]}")
    for number, batch in enumerate(batches, start=1):
        for row in batch:
            row["batch_number"] = number
    return batches


def make_handoff(batch, number):
    result = []
    for row in batch:
        result.append({
            "id": row["id"], "category": row["category"], "original": row["original"],
            "translation_source": row["translation_source"],
            "context_before": row["context_before"], "context_after": row["context_after"],
            "context_confidence": row["context_confidence"],
            "conversation_id": row["conversation_id"], "scene_id": row["scene_id"],
            "speaker": row["speaker"], "speaker_confidence": row["speaker_confidence"],
            "sequence_index": row["sequence_index"],
            "runtime_context": row["runtime_evidence"], "protected_tokens": row["protected_tokens"],
            "placeholders": row["placeholders"], "controls": row["controls"],
            "buffers": row["buffers"], "official_terms": row["official_terms"],
            "official_status": row["official_status"], "glossary_terms": row["glossary_terms"],
            "glossary_term_details": row["glossary_term_details"],
            "deterministic_translation": row["deterministic_translation"],
            "deterministic_origin": row["deterministic_origin"],
            "slot_size": row["slot_size"], "technical_risk": row["technical_risk"],
            "fixed": row["fixed"], "no_relocation": row["no_relocation"],
            "notes": row["notes"],
        })
    return {"metadata": {"phase": "6A", "batch": number, "entry_count": len(result),
                         "translation_policy": "kana-only; prose untranslated; preserve protected tokens"},
            "entries": result}


def qa_candidates(rows, size=QA_SIZE):
    chosen = []
    used = set()

    def take(candidates, count):
        for row in candidates:
            if count <= 0 or len(chosen) >= size:
                break
            if row["id"] not in used:
                chosen.append(row)
                used.add(row["id"])
                count -= 1

    ordered = sorted(rows, key=lambda row: row["rom_offset"])
    take((r for r in ordered if EARLY_INTRO_START <= r["rom_offset"] < EARLY_INTRO_END), 4)
    take((r for r in ordered if r["category"] in {"scripts", "plain_scripts"}
          and EARLY_INTRO_START <= r["rom_offset"] < EARLY_INTRO_END), 18)
    take((r for r in ordered if r["category"] == "scripts"
          and NPC_BANK_START <= r["rom_offset"] < NPC_BANK_END), 16)
    for category, count in (("scripts", 15), ("battle_messages", 12),
                            ("mission_names", 3), ("mission_descriptions", 5),
                            ("mission_objectives", 4), ("mission_log", 3)):
        take((r for r in ordered if r["category"] == category), count)
    take((r for r in ordered if r["category"].startswith("menu_")
          or r["category"] in {"setting_names", "start_menu_labels"}), 18)
    for feature, count in (("buffers", 4), ("FB", 4), ("FA", 3), ("FD", 3),
                           ("fixed", 4), ("no_relocation", 3)):
        take((r for r in ordered if (
            r.get(feature) if feature in {"buffers", "fixed", "no_relocation"}
            else r["controls"].get(feature)
        )), count)
    take((r for r in ordered if r["renderer_group"] in {"description_ui", "pokedex_ui", "name_table_ui"}), 8)
    take((r for r in ordered if r["technical_risk"] == "high"), size - len(chosen))
    take(ordered, size - len(chosen))
    return {"metadata": {"phase": "6A", "entry_count": len(chosen),
                         "note": "Candidates only. Exact runtime reachability and ROM fit require Phase 6B verification."},
            "entries": [{"id": r["id"], "category": r["category"],
                         "runtime_confidence": r["runtime_confidence"],
                         "runtime_evidence": r["runtime_evidence"],
                         "qa_route": ("NEW GAME settings; branch conditional" if EARLY_INTRO_START <= r["rom_offset"] < EARLY_INTRO_END
                                      else "NPC/event; exact map unproven" if r["category"] in {"scripts", "plain_scripts"}
                                      else "battle condition" if r["category"] == "battle_messages"
                                      else "Mission Log" if r["category"].startswith("mission_")
                                      else "menu/data lookup"),
                         "technical_risk": r["technical_risk"],
                         "renderer_group": r["renderer_group"]} for r in chosen]}


def capacity(rows, applied, phase5_map):
    codec = Charmap(target_lang="ja")
    prepared_by_id = {row["id"]: row for row in read_json(PREPARED)["entries"]}
    sample = []
    for row in applied:
        if not row.get("translated") or row["id"] not in prepared_by_id:
            continue
        try:
            source_size = prepared_by_id[row["id"]]["byte_length"]
            sample.append(len(codec.encode(row["translated"])) / source_size)
        except (ValueError, UnicodeEncodeError):
            continue
    sample.sort()
    factors = {"low": sample[int((len(sample) - 1) * 0.25)],
               "central": sample[int((len(sample) - 1) * 0.5)],
               "high": sample[int((len(sample) - 1) * 0.9)]}
    scenarios = {}
    for name, factor in factors.items():
        counts = Counter()
        for row in rows:
            estimate = row["deterministic_encoded_size"] or max(1, round(row["source_encoded_size"] * factor))
            counts["estimated_japanese_bytes"] += estimate
            if estimate > row["slot_size"]:
                if row["relocation_possible"]:
                    counts["relocation"] += 1
                    counts["relocation_bytes"] += estimate
                else:
                    counts["fixed_overflow"] += 1
            else:
                counts["in_place"] += 1
        scenarios[name] = {"phase5_size_factor": round(factor, 3), **counts,
                           "expected_vetted_ff_consumption_upper_bound": counts["relocation_bytes"],
                           "projected_vetted_ff_remaining_lower_bound": phase5_map["remaining_free_bytes"] - counts["relocation_bytes"]}
    return {"source_slot_bytes": sum(r["slot_size"] for r in rows),
            "source_encoded_bytes": sum(r["source_encoded_size"] for r in rows),
            "phase5_ratio_sample_count": len(sample),
            "phase5_vetted_ff_remaining": phase5_map["remaining_free_bytes"],
            "model": "Phase 5F translated PCS/source-slot ratios applied to unreviewed entries; known deterministic size exact. No controlfix/inject; dedup and allocator fragmentation omitted.",
            "scenarios": scenarios}


def coverage(rows, batches, qa, capacity_report, applied, prepared):
    feature_counts = Counter()
    combinations = Counter()
    for row in rows:
        for code in ("FE", "FA", "FB", "FC", "FD"):
            feature_counts[code] += bool(row["controls"].get(code))
        feature_counts["dynamic_buffer"] += bool(row["buffers"])
        feature_counts["placeholder"] += bool(row["placeholders"])
        feature_counts["multiple_page"] += row["controls"].get("FB", 0) >= 2
        feature_counts["language_switch"] += bool(row["controls"].get("FC_15") or row["controls"].get("FC_16"))
        combinations["+".join(code for code in ("FE", "FA", "FB", "FC", "FD") if row["controls"].get(code)) or "none"] += 1
    prepared_by_id = {row["id"]: row for row in prepared}
    phase5_renderers = {renderer_for(prepared_by_id[row["id"]]["category"])
                        for row in applied if row["id"] in prepared_by_id}
    current_renderers = {row["renderer_group"] for row in rows}
    return {
        "selected_total": len(rows), "new_translation_targets": len(rows),
        "deterministic_resolved": sum(bool(r["deterministic_translation"]) for r in rows),
        "claude_translation_needed": sum(not r["deterministic_translation"] for r in rows),
        "categories": dict(sorted(Counter(r["category"] for r in rows).items())),
        "runtime_confidence": dict(sorted(Counter(r["runtime_confidence"] for r in rows).items())),
        "story_npc_count": sum(r["category"] in {"scripts", "plain_scripts"} for r in rows),
        "conversation_groups": len({r["conversation_id"] for r in rows if r["conversation_id"]}),
        "speaker": dict(Counter(r["speaker_confidence"] for r in rows)),
        "renderer_groups": dict(sorted(Counter(r["renderer_group"] for r in rows).items())),
        "phase5_renderer_groups": sorted(phase5_renderers),
        "new_renderer_groups": sorted(current_renderers - phase5_renderers),
        "unknown_renderer_count": sum(r["renderer_group"] == "unknown" for r in rows),
        "control_coverage": dict(feature_counts), "control_combinations": dict(combinations.most_common()),
        "fixed": sum(r["fixed"] for r in rows), "no_relocation": sum(r["no_relocation"] for r in rows),
        "technical_risk": dict(Counter(r["technical_risk"] for r in rows)),
        "pokeapi_deterministic": sum(r["deterministic_origin"] == "pokeapi-ja-hrkt" for r in rows),
        "glossary_deterministic": sum(r["deterministic_origin"] == "glossary-exact" for r in rows),
        "batch_sizes": [len(batch) for batch in batches], "qa_candidates": len(qa["entries"]),
        "capacity": capacity_report,
    }


def validate(rows, batches, applied_ids, held_ids, qa):
    ids = [r["id"] for r in rows]
    if len(ids) != len(set(ids)) or len({r["rom_offset"] for r in rows}) != len(rows):
        raise ValueError("Duplicate ID or ROM offset")
    if set(ids) & (applied_ids | held_ids):
        raise ValueError("Phase 5 applied/held ID selected")
    if any(r["runtime_confidence"] not in "AB" for r in rows):
        raise ValueError("C/D confidence selected")
    batch_ids = [r["id"] for batch in batches for r in batch]
    if len(batch_ids) != len(set(batch_ids)) or set(batch_ids) != set(ids):
        raise ValueError("Batch partition incomplete/duplicate")
    group_batches = defaultdict(set)
    for index, batch in enumerate(batches):
        for row in batch:
            if row["conversation_id"]:
                group_batches[row["conversation_id"]].add(index)
    if any(len(locations) > 1 for locations in group_batches.values()):
        raise ValueError("Conversation group split")
    if not {r["id"] for r in qa["entries"]} <= set(ids):
        raise ValueError("QA candidate outside selection")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live-pokeapi", action="store_true",
                        help="Fetch uncached official ja-hrkt records; writes only ignored cache")
    args = parser.parse_args()
    prepared = read_json(PREPARED)["entries"]
    applied = read_json(APPLIED)["entries"]
    held = read_json(HELD)["entries"]
    phase5_map = read_json(PHASE5_MAP)
    rom = ROM.read_bytes()
    if hashlib.md5(rom).hexdigest() != SOURCE_MD5:
        raise ValueError("Source ROM MD5 mismatch")
    applied_ids = {row["id"] for row in applied}
    held_ids = {row["id"] for row in held} - applied_ids
    selected = select(prepared, applied_ids, held_ids)
    localizer = cached_localizer(live=args.live_pokeapi)
    if args.live_pokeapi:
        with ThreadPoolExecutor(max_workers=8) as executor:
            list(executor.map(localizer.translate_entry,
                              (entry for entry in selected if entry["category"] in CATEGORY_SPECS)))
    rows = make_rows(selected, rom, load_glossary(ROOT / "glossaries" / "ja.json"), localizer)
    contexts(rows, prepared, applied, held_ids)
    batches = partition(rows)
    qa = qa_candidates(rows)
    validate(rows, batches, applied_ids, held_ids, qa)
    report = coverage(rows, batches, qa, capacity(rows, applied, phase5_map), applied, prepared)
    report["phase5_applied_excluded"] = len(applied_ids)
    report["phase5_unresolved_excluded"] = len(held_ids)
    report["phase5_original_held"] = len(held)
    manifest = {"metadata": {"phase": "6A", "source_rom_md5": SOURCE_MD5,
                             "source_prepared": str(PREPARED.relative_to(ROOT)),
                             "phase5_applied_source": str(APPLIED.relative_to(ROOT)),
                             "entry_count": len(rows),
                             "selection_policy": "A/B only, owner or structured table, no legacy; exact row runtime usually unobserved"},
                "excluded_phase5_unresolved": [
                    {"id": row["id"], "phase5_unresolved": True,
                     "classification": row.get("classification"), "reason": row.get("current_reason")}
                    for row in held if row["id"] in held_ids],
                "entries": rows}
    write_json(MANIFEST, manifest)
    write_json(QA, qa)
    for index, batch in enumerate(batches, start=1):
        write_json(PHASE6_OUT / f"ja_phase6_batch{index:02d}_for_claude.json", make_handoff(batch, index))
    write_json(PHASE6_OUT / "ja_phase6a_coverage.json", report)
    write_json(PHASE6_OUT / "ja_phase6a_fixed_audit.json", {
        "entries": [{"id": r["id"], "category": r["category"], "slot_size": r["slot_size"],
                     "source_encoded_size": r["source_encoded_size"],
                     "deterministic_encoded_size": r["deterministic_encoded_size"],
                     "requires_fit_review": r["requires_fit_review"],
                     "fixed": r["fixed"], "no_relocation": r["no_relocation"],
                     "pointer_owners": r["pointer_owners"]} for r in rows if r["fixed"] or r["no_relocation"]]})
    print(json.dumps({k: report[k] for k in (
        "selected_total", "runtime_confidence", "deterministic_resolved", "claude_translation_needed",
        "batch_sizes", "qa_candidates", "fixed", "no_relocation")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
