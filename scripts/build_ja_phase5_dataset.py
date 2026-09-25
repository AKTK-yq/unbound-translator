#!/usr/bin/env python3
"""Build a bounded, untranslated Japanese Phase 5A review dataset."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.pcs_text import Charmap, decode_pcs, fc_arg_count
from lib.pokeapi_localizer import CATEGORY_SPECS, PokeAPILocalizer
from lib.translation_glossary import load_glossary
from lib.translation_tokens import semantic_tokens, strip_hma_quotes


TARGET_SIZE = 750
SOURCE_MD5 = "9cad8e771940e7f7094d13911552cef0"
CONFIDENCE = frozenset("ABCD")
TARGETS = {
    "scripts": 275, "plain_scripts": 8, "pointer_texts": 8,
    "battle_messages": 65,
    "pokemon_names": 25, "move_names": 25, "item_names": 25,
    "ability_names": 20, "type_names": 18, "nature_names": 20,
    "pokedex_species": 8, "pokedex_descriptions": 8,
    "move_descriptions": 8, "item_descriptions": 8,
    "ability_descriptions": 8, "habitat_names": 3, "map_names": 12,
    "mission_names": 20, "mission_descriptions": 18,
    "mission_objectives": 12, "mission_log": 18,
    "menu_pause": 11, "menu_common": 20, "menu_options": 18,
    "menu_pokemon": 15, "menu_pc": 18, "menu_shop": 5,
    "menu_save": 10, "menu_saving_messages": 6,
    "menu_save_prompts": 1, "menu_pcoptions": 3,
    "menu_item_storage": 10, "menu_game_settings": 12,
    "menu_pokemon_summary": 10, "menu_battle": 10,
    "menu_list_labels": 12, "setting_names": 10,
    "start_menu_labels": 8, "menu_trainer_card": 5,
    "menu_cube_system": 5, "menu_cube": 5, "menu_pokedex": 1,
    "menu_mining": 1, "move_learning": 5,
    "trade_messages": 5, "day_names": 5,
    "gendered_dialogue_fragments": 5,
    "trainer_names": 5, "trainer_classes": 5,
    "pokedex_form_names": 5, "menu_multiplayer": 4,
    "menu_link_controls": 5, "menu_pokemon_options": 5,
    "menu_standalone_labels": 1, "credits_text": 3,
}
TABLE_RENDERERS = {
    "pokemon_names": "pokemon_name_table", "move_names": "move_name_table",
    "item_names": "item_name_table", "ability_names": "ability_name_table",
    "type_names": "type_name_table", "nature_names": "nature_name_table",
    "battle_messages": "battle_text_printer",
    "mission_names": "mission_ui", "mission_descriptions": "mission_ui",
    "mission_objectives": "mission_ui", "mission_log": "mission_log",
    "scripts": "event_dialogue", "plain_scripts": "event_dialogue",
}
PHASE4_RUNTIME_CONFIRMED = {
    "scr_1F0F7EC", "scr_1F0F800", "scr_1F0F814",
}
EARLY_INTRO_START = 0x1F0EF00
EARLY_INTRO_END = 0x1F11000
NPC_BANK_START = 0x740000
NPC_BANK_END = 0x760000
HAN = re.compile(r"[\u3400-\u9fff]")
BUFFER_TOKEN = re.compile(r"\[(?:player|rival|kun|buffer[123])\]|\\\\[0-9A-Fa-f]{2}")


def address(entry):
    value = entry["address"]
    return int(value, 16) if isinstance(value, str) else value


def save_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def source_bytes(entry, cmap):
    return cmap.encode(strip_hma_quotes(entry["original"]))


def control_features(encoded):
    """Read PCS command boundaries; do not count command arguments as glyphs."""
    counts = Counter()
    index = 0
    while index < len(encoded):
        byte = encoded[index]
        index += 1
        if byte == 0xFF:
            break
        if byte in (0xFE, 0xFA, 0xFB):
            counts[{0xFE: "FE", 0xFA: "FA", 0xFB: "FB"}[byte]] += 1
        elif byte == 0xFC and index < len(encoded):
            command = encoded[index]
            counts["FC"] += 1
            counts[f"FC_{command:02X}"] += 1
            index += 1 + fc_arg_count(command)
        elif byte == 0xFD and index < len(encoded):
            counts["FD"] += 1
            index += 1
        elif byte in (0xF7, 0xF8, 0xF9) and index < len(encoded):
            counts[f"{byte:02X}"] += 1
            index += 1
    return dict(sorted(counts.items()))


def renderer_for(category):
    if category in TABLE_RENDERERS:
        return TABLE_RENDERERS[category]
    if category.startswith("menu_"):
        return category
    if category in {"setting_names", "start_menu_labels"}:
        return "settings_or_menu_ui"
    if category in {"pokedex_species", "pokedex_descriptions", "pokedex_form_names"}:
        return "pokedex_ui"
    if category in {"move_descriptions", "item_descriptions", "ability_descriptions"}:
        return "description_ui"
    if category in {"map_names", "trainer_names", "trainer_classes"}:
        return "name_table_ui"
    return "unknown"


def runtime_class(entry, phase4_ids):
    category = entry["category"]
    offset = address(entry)
    owners = entry.get("pointer_sources") or []
    if entry["id"] in PHASE4_RUNTIME_CONFIRMED:
        return "A", "Phase 3 mGBA observation plus current NEW GAME script operand"
    if entry["id"] in phase4_ids and EARLY_INTRO_START <= offset < EARLY_INTRO_END:
        return "A", "Phase 4 runtime-tested NEW GAME flow; exact branch may vary"
    if category in {"scripts", "plain_scripts"}:
        if owners:
            return "B", "Extractor-owned event-script pointer; event reachability not individually played"
        return "C", "Extracted script text without proven live event operand"
    if category == "pointer_texts":
        return "C", "Pointer ownership exists but calling renderer/runtime path is unproven"
    if entry.get("table_name"):
        return "B", f"Extractor-owned structured table {entry['table_name']}; row reachability varies"
    if owners:
        return "B", "Extractor-owned pointer; exact runtime branch untested"
    return "C", "Extracted ROM text; runtime consumer unproven"


def selection_score(entry, cmap):
    offset = address(entry)
    source = strip_hma_quotes(entry["original"])
    controls = control_features(source_bytes(entry, cmap))
    score = 0
    if entry["category"] == "scripts":
        if EARLY_INTRO_START <= offset < EARLY_INTRO_END:
            score += 100
        elif NPC_BANK_START <= offset < NPC_BANK_END:
            score += 55
    score += 7 * len(entry.get("pointer_sources") or [])
    score += 12 * int("FD" in controls)
    score += 8 * sum(int(key in controls) for key in ("FE", "FA", "FB", "FC"))
    score += 8 if len(source) > 100 else 3 if len(source) > 35 else 0
    index = entry.get("table_index")
    if isinstance(index, int):
        score += max(0, 25 - index // 4)
    return (-score, offset, entry["id"])


def select_entries(prepared, phase4, *, target_size=TARGET_SIZE):
    by_id = {entry["id"]: entry for entry in prepared["entries"]}
    phase4_ids = {row["id"] for row in phase4["entries"]}
    missing = phase4_ids - by_id.keys()
    if missing:
        raise ValueError(f"Phase 4 IDs absent from extraction: {sorted(missing)}")
    cmap = Charmap()
    selected = []
    ids = set()
    addresses = set()

    def add(entry):
        offset = address(entry)
        if entry["id"] in ids or offset in addresses:
            return False
        selected.append(entry)
        ids.add(entry["id"])
        addresses.add(offset)
        return True

    for row in phase4["entries"]:
        if not add(by_id[row["id"]]):
            raise ValueError(f"Duplicate Phase 4 ID/address: {row['id']}")

    pools = {}
    for category in TARGETS:
        candidates = [
            entry for entry in prepared["entries"]
            if entry["category"] == category
            and entry["id"] not in ids
            and re.search(r"[A-Za-z]", strip_hma_quotes(entry["original"]))
        ]
        pools[category] = sorted(candidates, key=lambda entry: selection_score(entry, cmap))

    counts = Counter(entry["category"] for entry in selected)
    while len(selected) < target_size:
        available = [category for category in TARGETS if counts[category] < TARGETS[category] and pools[category]]
        if not available:
            break
        category = min(available, key=lambda item: (counts[item] / TARGETS[item], list(TARGETS).index(item)))
        while pools[category]:
            candidate = pools[category].pop(0)
            if add(candidate):
                counts[category] += 1
                break
        else:
            continue
    if not 500 <= len(selected) <= 1000:
        raise ValueError(f"Phase 5A selection outside requested range: {len(selected)}")
    return selected


def validate_manifest(rows):
    ids = [row["id"] for row in rows]
    offsets = [row["rom_offset"] for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate Phase 5A IDs")
    if len(offsets) != len(set(offsets)):
        raise ValueError("Duplicate Phase 5A ROM offsets")
    for row in rows:
        if row["runtime_confidence"] not in CONFIDENCE:
            raise ValueError(f"Invalid runtime confidence: {row['id']}")
        if row["gba_address"] != f"0x{0x08000000 + row['rom_offset']:08X}":
            raise ValueError(f"Incorrect GBA address: {row['id']}")
        if row["slot_size"] < row["source_encoded_size"]:
            raise ValueError(f"Source exceeds ROM slot: {row['id']}")


def context_neighbors(prepared):
    by_category = defaultdict(list)
    for entry in prepared["entries"]:
        by_category[entry["category"]].append(entry)
    neighbors = {}
    for entries in by_category.values():
        entries.sort(key=address)
        for index, entry in enumerate(entries):
            before = entries[index - 1] if index else None
            after = entries[index + 1] if index + 1 < len(entries) else None
            neighbors[entry["id"]] = (
                strip_hma_quotes(before["original"]) if before and address(entry) - address(before) <= 0x200 else "",
                strip_hma_quotes(after["original"]) if after and address(after) - address(entry) <= 0x200 else "",
            )
    return neighbors


def glossary_candidates(rows, glossary):
    result = []
    seen = set()
    for row in rows:
        if row["category"] not in {"map_names", "mission_names"}:
            continue
        term = strip_hma_quotes(row["original"]).strip()
        if not term or term in seen or glossary.matches(term, row["category"]):
            continue
        if term.upper() == "INDIGO PLATEAU" or re.fullmatch(r"Route [0-9]+", term, re.IGNORECASE):
            continue
        if not re.search(r"[A-Za-z]", term):
            continue
        seen.add(term)
        result.append({"source": term, "category": row["category"], "evidence_id": row["id"], "target": None, "status": "glossary_candidate", "note": "Place label or mission title; Unbound-specificity and Japanese wording require human review"})
    return result


def make_handoff(rows):
    result = []
    for row in rows:
        result.append({
            "id": row["id"], "category": row["category"],
            "original": row["original"], "translation_source": row["translation_source"],
            "context_before": row["context_before"], "context_after": row["context_after"],
            "context_basis": "same-category nearby ROM text only; scene/speaker continuity unproven",
            "speaker": row["speaker"], "speaker_confidence": row["speaker_confidence"],
            "runtime_context": row["runtime_reason"],
            "protected_tokens": row["protected_tokens"],
            "semantic_token_placeholders": row["placeholders"],
            "controls": row["controls"],
            "official_terms": {strip_hma_quotes(row["original"]): row["official_translation"]} if row["official_translation"] else {},
            "glossary_terms": row["glossary_terms"],
            "approved_translation": row["approved_translation"],
            "approved_origin": row["approved_origin"],
            "max_or_expected_width": None,
            "slot_size": row["slot_size"],
            "notes": row["notes"],
        })
    return result


def choose_runtime_subset(rows, phase4, *, size=80):
    phase4_by_id = {item["id"]: item for item in phase4["entries"]}
    chosen = []
    chosen_ids = set()

    def take(candidates, limit):
        count = 0
        for row in candidates:
            if count >= limit or len(chosen) >= size:
                break
            if row["id"] not in chosen_ids:
                chosen.append(row)
                chosen_ids.add(row["id"])
                count += 1

    def ordered(items):
        return sorted(items, key=lambda row: row["rom_offset"])

    take(ordered(row for row in rows if phase4_by_id.get(row["id"], {}).get("route") == "intro"), 20)
    take(ordered(row for row in rows if row["id"] not in phase4_by_id and EARLY_INTRO_START <= row["rom_offset"] < EARLY_INTRO_END), 10)
    take(ordered(row for row in rows if row["id"] not in phase4_by_id and row["category"] == "scripts" and NPC_BANK_START <= row["rom_offset"] < NPC_BANK_END and row["slot_size"] >= 60), 6)
    take(ordered(row for row in rows if phase4_by_id.get(row["id"], {}).get("route") == "npc"), 2)
    take(ordered(row for row in rows if row["category"] == "battle_messages" and row["id"] in phase4_by_id), 5)
    take(ordered(row for row in rows if row["category"] == "battle_messages" and row["id"] not in phase4_by_id), 3)
    for category, limit in (("mission_log", 4), ("mission_names", 2), ("mission_descriptions", 2), ("mission_objectives", 2)):
        take(ordered(row for row in rows if row["category"] == category), limit)
    menus = ordered(row for row in rows if row["category"].startswith("menu_") or row["category"] in {"setting_names", "start_menu_labels"})
    priority_menus = ("menu_pause", "menu_options", "menu_pc", "menu_shop", "menu_save", "menu_pokemon", "menu_common", "menu_item_storage", "menu_game_settings", "menu_battle")
    for category in priority_menus:
        take((row for row in menus if row["category"] == category), 1)
    menu_first = []
    seen_categories = set()
    for row in menus:
        if row["category"] not in seen_categories and row["category"] not in priority_menus:
            menu_first.append(row)
            seen_categories.add(row["category"])
    take(menu_first, 6)
    for category in ("pokemon_names", "move_names", "item_names", "ability_names", "type_names", "nature_names"):
        take(ordered(row for row in rows if row["category"] == category and row["official_status"] == "verified"), 1)
    if len(chosen) < size:
        take(sorted(rows, key=lambda row: (
            row["runtime_confidence"] not in {"A", "B"},
            row["predicted_japanese_risk"] != "high",
            not bool(row["controls"].get("FD") or row["controls"].get("FB")),
            row["rom_offset"],
        )), size - len(chosen))
    return chosen


def _injector_module():
    path = ROOT / "005_hybrid_injector.py"
    spec = importlib.util.spec_from_file_location("phase5_capacity_injector", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def capacity_report(rows, original_entries, rom, phase4_controlfix):
    injector = _injector_module()
    from lib.unbound_free_space import VETTED_FREE_SPACE_RANGES

    blocks = injector.build_free_blocks(
        rom, original_entries, injector.DEFAULT_MIN_FREE_RUN,
        injector.DEFAULT_MIN_ADDRESS, VETTED_FREE_SPACE_RANGES,
    )
    vetted_free = sum(block.end - block.start for block in blocks)
    phase4_by_id = {entry["id"]: entry for entry in phase4_controlfix.get("entries", [])}
    japanese_codec = Charmap(target_lang="ja")
    ratios = []
    for row in rows:
        prior = phase4_by_id.get(row["id"])
        if prior and prior.get("translated") and row["source_encoded_size"]:
            size = len(japanese_codec.encode(prior["translated"]))
            ratios.append(size / row["source_encoded_size"])
    ratios.sort()
    def quantile(fraction, fallback):
        return ratios[round((len(ratios) - 1) * fraction)] if ratios else fallback
    factors = {"low": quantile(0.25, 0.9), "base": quantile(0.5, 1.2), "high": quantile(0.9, 1.5)}

    category_counts = defaultdict(lambda: Counter())
    for row in rows:
        counts = category_counts[row["category"]]
        counts["total_entries"] += 1
        counts["fixed_slots"] += int(row["fixed_slot"])
        counts["pointer_owned"] += int(bool(row["pointer_owners"]))
        counts["relocation_possible"] += int(row["relocatable"])
        counts["no_relocation"] += int(row["no_relocation"])
        counts["total_current_bytes"] += row["slot_size"]
    by_category = {}
    for category, counts in sorted(category_counts.items()):
        result = dict(counts)
        result["average_slot"] = round(counts["total_current_bytes"] / counts["total_entries"], 2)
        result["available_vetted_ff_shared_bytes"] = vetted_free
        by_category[category] = result

    scenarios = {}
    for name, factor in factors.items():
        relocated = fixed_overflow = relocated_bytes = 0
        for row in rows:
            prior = phase4_by_id.get(row["id"])
            if prior and prior.get("translated"):
                estimate = len(japanese_codec.encode(prior["translated"]))
            elif row.get("official_translation"):
                estimate = len(japanese_codec.encode(f"[japanese]{row['official_translation']}[latin]"))
            elif row.get("approved_translation"):
                estimate = len(japanese_codec.encode(f"[japanese]{row['approved_translation']}[latin]"))
            else:
                estimate = max(1, round(row["source_encoded_size"] * factor))
            if estimate > row["slot_size"]:
                if row["relocatable"]:
                    relocated += 1
                    relocated_bytes += estimate
                else:
                    fixed_overflow += 1
        scenarios[name] = {
            "phase4_size_factor": round(factor, 3),
            "predicted_relocations": relocated,
            "predicted_relocation_bytes": relocated_bytes,
            "predicted_fixed_overflows": fixed_overflow,
            "fraction_of_shared_vetted_ff": round(relocated_bytes / vetted_free, 4) if vetted_free else None,
        }
    return {
        "scope": "Selected Phase 5A entries only; unreviewed prose sizes are rough Phase 4 extrapolations, not injection results",
        "available_vetted_ff_shared_bytes": vetted_free,
        "vetted_block_count": len(blocks),
        "phase4_ratio_sample_count": len(ratios),
        "category_counts": by_category,
        "scenarios": scenarios,
    }


def build(prepared, extracted, phase4, rom, glossary, *, phase4_controlfix=None, localizer=None, workers=6, target_size=TARGET_SIZE):
    if hashlib.md5(rom).hexdigest() != SOURCE_MD5:
        raise ValueError("Source ROM MD5 mismatch")
    selected = select_entries(prepared, phase4, target_size=target_size)
    phase4_translation = {row["id"]: row["japanese"] for row in phase4["entries"]}
    neighbors = context_neighbors(prepared)
    latin_codec = Charmap()
    japanese_codec = Charmap(target_lang="ja")
    rows = []
    for entry in selected:
        offset = address(entry)
        slot = int(entry["byte_length"])
        decoded = decode_pcs(rom, offset, slot)
        if not decoded.terminated or decoded.byte_length > slot:
            raise ValueError(f"Unterminated selected ROM text: {entry['id']}")
        encoded = rom[offset:offset + decoded.byte_length]
        features = control_features(encoded)
        source = strip_hma_quotes(entry["original"])
        tokens = semantic_tokens(source)
        confidence, reason = runtime_class(entry, phase4_translation)
        owners = entry.get("pointer_sources") or []
        no_relocation = bool(entry.get("no_relocation"))
        relocatable = bool(owners) and bool(entry.get("is_pointer_based")) and not no_relocation
        fixed_slot = not relocatable
        renderer = renderer_for(entry["category"])
        buffers = [token for token in tokens if BUFFER_TOKEN.fullmatch(token)]
        placeholders = entry.get("semantic_token_placeholders") or []
        glossary_matches = glossary.matches(entry.get("translation_source", ""), entry["category"])
        glossary_terms = {term.source: term.target_for(entry["category"]) for _, _, term in glossary_matches}
        approved = phase4_translation.get(entry["id"])
        approved_origin = "phase4-reviewed" if approved else None
        if not approved and strip_hma_quotes(entry["original"]) in glossary_terms:
            approved = glossary_terms[source]
            approved_origin = "phase4-glossary"
        if approved:
            japanese_codec.encode(f"[japanese]{approved}[latin]")
        risk_reasons = []
        if fixed_slot:
            risk_reasons.append("fixed_or_no_relocation")
        if len(source) > 110 or features.get("FB", 0) > 0:
            risk_reasons.append("long_or_multipage")
        if len(buffers) > 1:
            risk_reasons.append("multiple_dynamic_tokens")
        if renderer == "unknown":
            risk_reasons.append("unknown_renderer")
        if entry["category"].startswith("menu_") or entry["category"] in {"setting_names", "start_menu_labels"}:
            risk_reasons.append("narrow_ui_unknown_bound")
        risk = "high" if risk_reasons else "medium" if features or entry["category"] in {"scripts", "battle_messages"} else "low"
        before, after = neighbors[entry["id"]]
        row = {
            "id": entry["id"], "category": entry["category"],
            "original": entry["original"],
            "translation_source": entry.get("translation_source"),
            "rom_offset": offset, "gba_address": f"0x{0x08000000 + offset:08X}",
            "slot_size": slot,
            "pointer_owners": owners,
            "controls": features,
            "buffers": buffers,
            "placeholders": placeholders,
            "protected_tokens": tokens,
            "renderer": renderer,
            "runtime_confidence": confidence,
            "runtime_reason": reason,
            "source_encoded_size": len(encoded),
            "predicted_japanese_risk": risk,
            "risk_reasons": risk_reasons,
            "fixed_slot": fixed_slot,
            "relocatable": relocatable,
            "no_relocation": no_relocation,
            "table_name": entry.get("table_name"),
            "table_index": entry.get("table_index"),
            "official_translation": None,
            "official_source": None,
            "official_status": "not_applicable" if entry["category"] not in CATEGORY_SPECS else "unverified",
            "glossary_terms": glossary_terms,
            "approved_translation": approved,
            "approved_origin": approved_origin,
            "context_before": before,
            "context_after": after,
            "speaker": "unknown",
            "speaker_confidence": "unknown",
            "notes": "Adjacent text is ROM-neighbor context, not proven same speaker or sequence." if before or after else "No close ROM-neighbor context; speaker unknown.",
        }
        if len(source_bytes(entry, latin_codec)) != row["source_encoded_size"]:
            row["notes"] += " PCS re-encode differs from original bytes; inspect before translation."
        rows.append(row)
    validate_manifest(rows)

    if localizer is not None:
        by_id = {entry["id"]: entry for entry in selected}
        target_rows = [row for row in rows if row["category"] in CATEGORY_SPECS and not row["approved_translation"]]
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="phase5-pokeapi") as executor:
            futures = {executor.submit(localizer.translate_entry, by_id[row["id"]]): row for row in target_rows}
            for future in as_completed(futures):
                row = futures[future]
                value = future.result()
                if value and not HAN.search(value):
                    try:
                        japanese_codec.encode(f"[japanese]{value}[latin]")
                    except UnicodeEncodeError:
                        row["official_status"] = "unsupported_glyph"
                    else:
                        row["official_translation"] = value
                        row["official_source"] = "PokeAPI v2 ja-hrkt; English source validated"
                        row["official_status"] = "verified"
                        row["approved_translation"] = value
                        row["approved_origin"] = "pokeapi-ja-hrkt"
                elif value:
                    row["official_status"] = "contains_kanji"
                else:
                    row["official_status"] = "unverified"

    by_id = {row["id"]: row for row in rows}
    subset = choose_runtime_subset(rows, phase4)
    handoff = make_handoff(rows)
    candidates = glossary_candidates(rows, glossary)
    candidate_sources = {item["source"] for item in candidates}
    for row in rows:
        source = strip_hma_quotes(row["original"]).strip()
        if source in candidate_sources and row["category"] in {"map_names", "mission_names"}:
            row["glossary_candidate"] = source
    counts = Counter(row["category"] for row in rows)
    confidence_counts = Counter(row["runtime_confidence"] for row in rows)
    control_counts = Counter()
    combinations = Counter()
    renderers = defaultdict(lambda: {"count": 0, "categories": set(), "example_ids": []})
    for row in rows:
        features = row["controls"]
        for name in ("FE", "FA", "FB", "FC", "FD"):
            if features.get(name):
                control_counts[name] += 1
        control_counts["dynamic"] += int(bool(row["buffers"]))
        control_counts["placeholder"] += int(bool(row["placeholders"]))
        if features.get("FB", 0) >= 2:
            control_counts["multiple_page"] += 1
        combo = "+".join(name for name in ("FE", "FA", "FB", "FC", "FD") if features.get(name)) or "none"
        combinations[combo] += 1
        current = renderers[row["renderer"]]
        current["count"] += 1
        current["categories"].add(row["category"])
        if len(current["example_ids"]) < 5:
            current["example_ids"].append(row["id"])
    phase4_renderers = {renderer_for(by_id[entry_id]["category"]) for entry_id in phase4_translation if entry_id in by_id}
    coverage = {
        "selected_entries": len(rows),
        "category_counts": dict(sorted(counts.items())),
        "runtime_confidence": {key: confidence_counts[key] for key in "ABCD"},
        "renderers": {name: {"count": value["count"], "categories": sorted(value["categories"]), "example_ids": value["example_ids"], "phase4_status": "previously_selected" if name in phase4_renderers else "new_phase5a"} for name, value in sorted(renderers.items())},
        "control_counts": dict(sorted(control_counts.items())),
        "control_combinations": dict(sorted(combinations.items())),
        "official_verified": sum(row["official_status"] == "verified" for row in rows),
        "official_unverified": sum(row["official_status"] == "unverified" for row in rows),
        "glossary_entry_count": sum(bool(row["glossary_terms"]) for row in rows),
        "glossary_occurrence_count": sum(len(glossary.matches(row["translation_source"] or "", row["category"])) for row in rows),
        "glossary_candidates": candidates,
        "renderer_unknown_ids": [row["id"] for row in rows if row["renderer"] == "unknown"],
    }
    capacity = capacity_report(rows, extracted["entries"], rom, phase4_controlfix or {})
    manifest = {
        "metadata": {
            "phase": "5A", "target_language": "ja", "source_rom_md5": SOURCE_MD5,
            "selection_method": "Phase 4 seed plus scored category quotas; pointer/table ownership required for B",
            "entry_count": len(rows), "translation_policy": "Only PokeAPI ja-hrkt, existing glossary, or Phase 4 reviewed wording is approved; prose remains untranslated",
        },
        "entries": rows,
    }
    runtime_subset = {
        "metadata": {"phase": "5A", "entry_count": len(subset), "source_manifest": "tests/fixtures/ja_phase5_selection.json", "note": "Priority order for human QA after Phase 5B translations; inclusion does not assert current runtime observation"},
        "entries": [{"id": row["id"], "category": row["category"], "renderer": row["renderer"], "runtime_confidence": row["runtime_confidence"], "reason": row["runtime_reason"], "qa_route": "NEW GAME" if EARLY_INTRO_START <= row["rom_offset"] < EARLY_INTRO_END else "NPC/event; map unproven" if row["category"] == "scripts" else "conditional battle" if row["category"] == "battle_messages" else "Mission Log" if row["category"].startswith("mission_") or row["category"] == "mission_log" else "menu/data lookup"} for row in subset],
    }
    return manifest, {"metadata": {"phase": "5A", "entry_count": len(handoff)}, "entries": handoff}, runtime_subset, capacity, coverage


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prepared")
    parser.add_argument("extracted")
    parser.add_argument("rom")
    parser.add_argument("--phase4-selection", default="tests/fixtures/ja_phase4_selection.json")
    parser.add_argument("--phase4-controlfix", default="out/unbound-ja-phase4-reviewed-controlfix.json")
    parser.add_argument("--glossary", default="glossaries/ja.json")
    parser.add_argument("--manifest", default="tests/fixtures/ja_phase5_selection.json")
    parser.add_argument("--handoff", default="out/ja_phase5_for_claude.json")
    parser.add_argument("--subset", default="tests/fixtures/ja_phase5_runtime_subset.json")
    parser.add_argument("--capacity", default="out/ja_phase5_capacity.json")
    parser.add_argument("--coverage", default="out/ja_phase5_coverage.json")
    parser.add_argument("--pokeapi-cache", default=".cache/pokeapi")
    parser.add_argument("--pokeapi-workers", type=int, default=6)
    parser.add_argument("--offline", action="store_true", help="Do not fetch PokeAPI; official statuses remain unverified")
    args = parser.parse_args()
    prepared = json.loads(Path(args.prepared).read_text(encoding="utf-8"))
    extracted = json.loads(Path(args.extracted).read_text(encoding="utf-8"))
    phase4 = json.loads(Path(args.phase4_selection).read_text(encoding="utf-8"))
    phase4_path = Path(args.phase4_controlfix)
    if not phase4_path.exists():
        parser.error(f"Phase 4 controlfixed baseline is required for capacity estimates: {phase4_path}")
    phase4_controlfix = json.loads(phase4_path.read_text(encoding="utf-8"))
    glossary = load_glossary(args.glossary, expected_language="ja")
    localizer = None if args.offline else PokeAPILocalizer("ja", args.pokeapi_cache)
    result = build(prepared, extracted, phase4, Path(args.rom).read_bytes(), glossary,
                   phase4_controlfix=phase4_controlfix, localizer=localizer,
                   workers=args.pokeapi_workers)
    for path, data in zip((args.manifest, args.handoff, args.subset, args.capacity, args.coverage), result):
        save_json(path, data)
    manifest, _handoff, subset, capacity, coverage = result
    print(f"selected: {len(manifest['entries'])}")
    print(f"runtime QA subset: {len(subset['entries'])}")
    print(f"PokeAPI ja-hrkt verified: {coverage['official_verified']}")
    print(f"glossary entries: {coverage['glossary_entry_count']}")
    print(f"vetted FF shared bytes: {capacity['available_vetted_ff_shared_bytes']}")


if __name__ == "__main__":
    main()
