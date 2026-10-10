#!/usr/bin/env python3
"""Phase 6C-4A: split the 569-entry Claude translation/context queue into four batches.

Preparation only: no translation, no ROM, no change to any input file. Every output
carries ``metadata.phase == "6C-4A"``; the writer refuses to overwrite any existing
file that does not carry that marker, so a file from another phase can never be
replaced by accident. Re-running regenerates byte-identical outputs.
"""

from __future__ import annotations

from collections import Counter, defaultdict
import copy
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.fa_control import parse_raw_segments
from lib.pcs_text import Charmap, decode_pcs
from lib.translation_glossary import load_glossary
from scripts.build_ja_phase6_batch04 import BATTLE_HOLD, BATTLE_SAFE, FIELD_SAFE

OUT = ROOT / "out/phase6"
FIX = ROOT / "tests/fixtures"
PHASE = "6C-4A"
HANDOFF_V3 = OUT / "ja_phase6_cleanup_translation_handoff_v3.json"
GLOSSARY_HANDOFF = OUT / "ja_phase6_cleanup_translation_glossary_handoff.json"
ATTRIBUTION = OUT / "ja_phase6_speaker_attribution.json"
VOICE_REVIEW = OUT / "ja_phase6_voice_review_for_claude.json"
PROFILES = FIX / "ja_phase6_voice_profiles_claude.json"
INVENTORY = OUT / "ja_phase6_final_cleanup_inventory_v3.json"
COMBINED = OUT / "ja_phase6_cleanup_glossary_combined_controlfix.json"
SELECTION = FIX / "ja_phase6_selection.json"
PREPARED = ROOT / "out/ja-phase5e-prepared.json"
GLOSSARY = ROOT / "glossaries/ja.json"
SOURCE_ROM = ROOT / "rom/unbound.gba"
SOURCE_MD5 = "9cad8e771940e7f7094d13911552cef0"
PROTECTED = [ROOT / "scripts/build_ja_phase6_voice_integration.py",
             ROOT / "tests/test_ja_phase6_voice_integration.py",
             ROOT / "out/unbound-ja-phase6-voice-pass1.gba"]
BATCH_FILES = [OUT / f"ja_phase6_cleanup_batch{n:02d}_for_claude.json" for n in range(1, 5)]
STYLE_HANDOFF = OUT / "ja_phase6_cleanup_translation_style_handoff.json"
MANIFEST = FIX / "ja_phase6_cleanup_batch_manifest.json"
EXPECTED = {"total": 569, "CLAUDE_TRANSLATION": 302, "CLAUDE_CONTEXT": 267}
BATCH_SIZE_RANGE = (120, 160)
CUES = (("exclamation", r"!"), ("question", r"\?"), ("pause_token", r"\\\."), ("please", r"(?i)\bplease\b"),
        ("slang_or_contraction", r"(?i)\b(ya|yer|gonna|wanna|kinda|ain't|'em|’em)\b"),
        ("player_address", r"\[player\]"), ("rival_address", r"\[rival\]"))


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def dumps(value):
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def guarded_write(path, value):
    """Write only a new file, or a file that this phase produced earlier."""
    path = Path(path)
    if path.exists():
        try:
            marker = read(path).get("metadata", {}).get("phase")
        except (ValueError, AttributeError):
            marker = None
        if marker != PHASE:
            raise FileExistsError(f"refusing to overwrite existing file from another phase: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dumps(value), encoding="utf-8")


# --------------------------------------------------------------------------- input validation

def validate_input(entries):
    ids = [e["id"] for e in entries]
    inventory = {x["id"]: x for x in read(INVENTORY)["entries"]}
    combined = {x["id"] for x in read(COMBINED)["entries"]}
    selection = {x["id"]: x for x in read(SELECTION)["entries"]}
    rom = SOURCE_ROM.read_bytes()
    report = {"entries": len(ids), "unique": len(set(ids)), "duplicates": len(ids) - len(set(ids)),
              "classes": dict(Counter(e["resolution_class"] for e in entries))}
    report["already_in_applied_json"] = sorted(set(ids) & combined)
    report["inventory_not_held"] = sorted(i for i in ids if inventory[i]["apply_status"] == "applied")
    report["inventory_class_mismatch"] = sorted(i for e in entries for i in [e["id"]]
                                                if inventory[i]["resolution_class"] != e["resolution_class"])
    report["missing_from_inventory"] = sorted(i for i in ids if i not in inventory)
    report["missing_from_selection"] = sorted(i for i in ids if i not in selection)
    base = ROOT / "out/unbound-ja-phase6-cleanup-glossary.gba"
    voice = ROOT / "out/unbound-ja-phase6-voice-pass1.gba"
    changed = {}
    for label, path in (("cleanup_glossary_rom", base), ("voice_pass1_rom", voice)):
        if not path.exists():
            continue
        other = path.read_bytes()
        changed[label] = sorted(i for i in ids
                                if other[selection[i]["rom_offset"]:selection[i]["rom_offset"] + selection[i]["slot_size"]]
                                != rom[selection[i]["rom_offset"]:selection[i]["rom_offset"] + selection[i]["slot_size"]])
    report["slot_differs_from_source_rom"] = changed
    report["contamination"] = bool(report["already_in_applied_json"] or report["inventory_not_held"]
                                   or report["inventory_class_mismatch"] or any(changed.values()))
    report["ok"] = (report["entries"] == EXPECTED["total"] and report["unique"] == EXPECTED["total"]
                    and report["classes"] == {k: EXPECTED[k] for k in ("CLAUDE_TRANSLATION", "CLAUDE_CONTEXT")}
                    and not report["missing_from_inventory"] and not report["missing_from_selection"]
                    and not report["contamination"])
    return report


# --------------------------------------------------------------------------- deterministic split

class UnionFind:
    def __init__(self, items):
        self.parent = {i: i for i in items}

    def find(self, item):
        while self.parent[item] != item:
            self.parent[item] = self.parent[self.parent[item]]
            item = self.parent[item]
        return item

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[max(ra, rb)] = min(ra, rb)


def split_batches(entries):
    """Batch 1 = every NON_DIALOGUE row; batches 2-4 = dialogue units cut into three runs.

    A unit is a connected set of rows that share a conversation_id or a proven
    dialogue_group_id. Units are never cut, so a proven speaker group is never split.
    """
    nondialogue = [e for e in entries if e["speaker_category"] == "NON_DIALOGUE"]
    dialogue = [e for e in entries if e["speaker_category"] != "NON_DIALOGUE"]
    offset = lambda e: (e["known_technical_constraints"]["rom_offset"], e["id"])
    batch1 = sorted(nondialogue, key=lambda e: (e["category"], *offset(e)))
    uf = UnionFind([e["id"] for e in dialogue])
    seen = {}
    for e in dialogue:
        for key in (("conv", e["preserved_metadata"]["conversation_id"]), ("grp", e["dialogue_group_id"])):
            if key[1] is None:
                continue
            if key in seen:
                uf.union(seen[key], e["id"])
            else:
                seen[key] = e["id"]
    units = defaultdict(list)
    for e in dialogue:
        units[uf.find(e["id"])].append(e)
    ordered = sorted(units.values(), key=lambda rows: min(offset(r) for r in rows))
    for rows in ordered:
        rows.sort(key=offset)
    total = len(dialogue)
    cumulative = [0]
    for rows in ordered:
        cumulative.append(cumulative[-1] + len(rows))
    first = min(range(1, len(ordered)), key=lambda i: (abs(cumulative[i] - total / 3), i))
    second = min(range(first + 1, len(ordered)), key=lambda i: (abs(cumulative[i] - 2 * total / 3), i))
    bounds = [0, first, second, len(ordered)]
    groups = [[r for rows in ordered[bounds[i]:bounds[i + 1]] for r in rows] for i in range(3)]
    batches = [batch1, *groups]
    return batches, ordered


# --------------------------------------------------------------------------- per-entry enrichment

def english_cues(text):
    return {name: len(re.findall(pattern, text)) for name, pattern in CUES if re.search(pattern, text)}


def buffer_metadata(entry, facts):
    items = []
    for token in entry["buffers"]:
        code = token[2:] if token.startswith("\\\\") else None
        if code in BATTLE_SAFE:
            status = "battle_type_defined_by_engine"
        elif code in BATTLE_HOLD:
            status = "battle_type_not_proven_hold"
        elif token in FIELD_SAFE:
            status = "field_placeholder_known"
        else:
            status = "unknown_writer_and_value_set_hold"
        items.append({"token": token, "status": status,
                      "meaning": BATTLE_SAFE.get(code) or BATTLE_HOLD.get(code) or FIELD_SAFE.get(token)})
    return {"buffers": items, "buffer_class": facts.get("buffer_class"),
            "rule": "Keep every buffer token in source order. Never guess the value type, grammar, or writer; "
                    "hold with needs_context if the sentence cannot be written without it."}


def translation_risk(entry, fa, unresolved):
    reasons = []
    controls = entry["controls"]
    if fa:
        reasons.append("fa_segmented_required")
    if entry["buffers"]:
        reasons.append("dynamic_buffers")
    if any(b in {"[buffer1]", "[buffer2]", "[buffer3]"} or (b.startswith("\\\\") and b[2:] in BATTLE_HOLD)
           for b in entry["buffers"]):
        reasons.append("unknown_buffer_type")
    if unresolved:
        reasons.append("unresolved_glossary_term")
    if controls.get("FC") or controls.get("FD"):
        reasons.append("page_or_substitution_controls")
    if entry["resolution_class"] == "CLAUDE_CONTEXT":
        reasons.append("context_required")
    if any("dynamic_buffer" in r or "unresolved" in r for r in entry["remaining_holds"]):
        reasons.append("hold_reason_mentions_unresolved_dependency")
    high = {"unknown_buffer_type", "unresolved_glossary_term"}
    if high & set(reasons) or ("fa_segmented_required" in reasons and "dynamic_buffers" in reasons):
        level = "high"
    elif reasons:
        level = "medium"
    else:
        level = "low"
    return {"level": level, "reasons": reasons}


def voice_attachment(entry, profiles, plausible, groups, queue_by_group):
    confidence, category = entry["speaker_confidence"], entry["speaker_category"]
    base = {"speaker_id": entry["speaker_id"], "speaker_confidence": confidence, "speaker_category": category,
            "canon_character_candidate": entry["canon_character_candidate"],
            "official_character_proven": False,
            "official_character_rule": "Name matches are not identity. Official Japanese voice needs proven identity, "
                                       "source game and a Japanese-version voice reference; none is available."}
    if category == "NON_DIALOGUE":
        return {**base, "voice_application": "not_applicable_non_dialogue", "voice_profile": None}
    if confidence == "PROVEN":
        profile = profiles.get(entry["speaker_id"])
        group = groups.get(entry["speaker_id"])
        context = []
        if group:
            for d in group["dialogue"]:
                context.append({"id": d["id"], "original": d["original"], "current_japanese": d["current_japanese"],
                                "source": d["source"], "in_this_queue": d["id"] in queue_by_group})
        if profile:
            status = profile["voice_status"]
            mode = {"CONFIRMED_VOICE": "enforce_approved_profile",
                    "PROVISIONAL_VOICE": "reference_only_do_not_force",
                    "NEUTRAL_ONLY": "neutral_only", "INSUFFICIENT_EVIDENCE": "neutral_only_insufficient_evidence"}[status]
            slim = {k: profile[k] for k in ("character_name", "voice_status", "identity_confidence", "character_category",
                                            "trainer_class", "politeness", "first_person", "second_person",
                                            "sentence_endings", "personality_traits", "speech_examples_short",
                                            "evidence_entry_ids", "untranslated_entry_ids", "prohibited_assumptions",
                                            "notes")}
            return {**base, "voice_application": mode, "voice_profile": slim, "speaker_group_context": context}
        return {**base, "voice_application": "neutral_no_profile",
                "voice_profile": None, "speaker_group_context": context,
                "note": "Proven by object/trainer binding but not part of the 56 reviewed voice groups."}
    if confidence == "PLAUSIBLE":
        return {**base, "voice_application": "plausible_tendency_reference_only", "voice_profile": None,
                "plausible_tendency": plausible.get(entry["id"]),
                "note": "Only an object-script proximity candidate. Do not assume the same person as any other entry "
                        "and do not harden the tendency into a personal voice."}
    return {**base, "voice_application": "unknown_speaker_neutral_with_register",
            "voice_profile": None, "english_register_cues": english_cues(entry["original"]),
            "note": "Reflect the attitude in the English (cheerful, angry, formal, sarcastic, surprised). "
                    "Do not add a first person, gendered ending, dialect or age voice without evidence."}


CLAUDE_TASK_DETAIL = {
    "CLAUDE_TRANSLATION": "Write complete kana-only Japanese for this entry (new wording, or a reviewed replacement of the previous "
                          "candidate). If the previous candidate is already acceptable say so. No wording is pre-approved.",
    "CLAUDE_CONTEXT": "Decide whether the available context is enough. If yes, write the Japanese; if the buffer, speaker "
                      "or event context is unresolved, return status needs_context with the exact missing fact. Never guess.",
}
ALLOWED_OUTCOMES = ["confirmed", "needs_context", "needs_technical_fit"]


def glossary_terms(entry, glossary):
    approved = []
    for item in entry["glossary"]["approved_terms"]:
        scoped = [t for t in glossary.terms if t.target.replace(" ", "") == item["japanese"].replace(" ", "")
                  and (entry["id"] in t.entry_ids or (not t.entry_ids and t.global_replace))
                  and t.source.lower() in {x.lower() for x in (item["term"],)} | {item["term"]}]
        approved.append({**item, "glossary_scope": [
            {"source": t.source, "context_scope": t.context_scope, "global_replace": t.global_replace,
             "case_sensitive": t.case_sensitive, "categories": list(t.categories), "entry_ids": list(t.entry_ids)}
            for t in scoped] or [{"note": "term decided in Phase 6C-2A; see glossary entry for this exact entry_id"}]})
    return approved


def build():
    handoff = read(HANDOFF_V3)
    entries = handoff["entries"]
    report = validate_input(entries)
    if not report["ok"]:
        raise ValueError(f"input validation failed: {json.dumps(report, ensure_ascii=False)[:600]}")
    assert hashlib.md5(SOURCE_ROM.read_bytes()).hexdigest() == SOURCE_MD5
    batches, units = split_batches(entries)

    selection = {x["id"]: x for x in read(SELECTION)["entries"]}
    prepared = {x["id"]: x for x in read(PREPARED)["entries"]}
    inventory = {x["id"]: x for x in read(INVENTORY)["entries"]}
    profile_doc = read(PROFILES)
    profiles = {p["speaker_id"]: p for p in profile_doc["profiles"]}
    plausible = {x["entry_id"]: {"tendency_suggestion": x["tendency_suggestion"], "voice_status": x["voice_status"],
                                 "map_section_names": x["map_section_names"], "graphics_ids": x["graphics_ids"]}
                 for x in profile_doc["plausible_pool"]["entries"]}
    groups = {g["speaker_id"]: g for g in read(VOICE_REVIEW)["groups"]}
    queue_ids = {e["id"] for e in entries}
    glossary = load_glossary(GLOSSARY, expected_language="ja")
    rom = SOURCE_ROM.read_bytes()
    unresolved_terms = handoff["unresolved_terms"]
    charmap = Charmap("ja")
    probe = {}
    for ch in "ヴ「」、：〜()%=+＋・&;":
        try:
            charmap.encode("[japanese]" + ch + "[latin]")
            probe[ch] = True
        except (UnicodeEncodeError, ValueError, KeyError):
            probe[ch] = False

    out_batches, manifest_batches = [], []
    for number, rows in enumerate(batches, start=1):
        out_entries = []
        for position, entry in enumerate(rows, start=1):
            key = entry["id"]
            sel = selection[key]
            decoded = decode_pcs(rom, sel["rom_offset"], sel["slot_size"])
            raw = rom[sel["rom_offset"]:sel["rom_offset"] + decoded.byte_length]
            try:
                segments = parse_raw_segments(raw, rom_offset=sel["rom_offset"])
                structure_error = None
            except ValueError as exc:
                segments, structure_error = [], str(exc)
            fa = bool(entry["controls"].get("FA"))
            facts = inventory[key]["normalized_technical_facts"]
            matches = [{"source": t.source, "target": t.target, "kind": t.kind, "context_scope": t.context_scope,
                        "global_replace": t.global_replace}
                       for _, _, t in glossary.matches(prepared[key]["translation_source"], entry["category"], entry_id=key)]
            unresolved = entry["glossary"]["unresolved_warnings"]
            new = copy.deepcopy(entry)  # every original field stays byte-for-byte equal
            new.update({
                "cleanup_batch": number, "batch_position": position,
                "previous_japanese_candidate": entry["candidate"],
                "current_hold_reason": {"exact_reason": entry["exact_reason"], "remaining_holds": entry["remaining_holds"],
                                        "previous_primary_hold": entry["previous_primary_hold"],
                                        "secondary_holds": entry["secondary_holds"]},
                "claude_task": {"class": entry["resolution_class"], "summary": entry["requested_claude_task"],
                                "detail": CLAUDE_TASK_DETAIL[entry["resolution_class"]],
                                "allowed_outcomes": ALLOWED_OUTCOMES,
                                "technical_hold_note": "If natural Japanese needs a word order or boundary change across a source "
                                                       "control, return needs_technical_fit instead of moving a control."},
                "translation_source": prepared[key]["translation_source"],
                "protected_tokens": sel["protected_tokens"], "placeholders": sel["placeholders"],
                "source_control_structure": {
                    "controls": entry["controls"], "slot_size": sel["slot_size"], "fixed": sel["fixed"],
                    "no_relocation": sel["no_relocation"],
                    "boundary_sequence": [s["after_control"] for s in segments if s["after_control"]],
                    "display_segments": [{"segment_index": i, "text": s["text"], "after_control": s["after_control"]}
                                         for i, s in enumerate(segments)],
                    "parse_error": structure_error,
                    "rule": "FE/FA/FB, colors, waits, FC/FD pages and alignment are owned by the ROM structure; "
                            "do not add, remove, move or merge them."},
                "buffer_metadata": buffer_metadata(entry, facts),
                "approved_glossary_terms": glossary_terms(entry, glossary),
                "glossary_matcher_hits": matches,
                "unresolved_glossary_warnings": unresolved,
                "translation_risk": translation_risk(entry, fa, unresolved),
            })
            new.update(voice_attachment(entry, profiles, plausible, groups,
                                        {d for g in groups.values() for d in g["dialogue_ids"] if d in queue_ids}))
            if fa:
                new["fa_placement_policy"] = "require_segments"
                new["translation_units"] = [{"segment_index": i, "english": s["text"], "after_control": s["after_control"]}
                                            for i, s in enumerate(segments)]
                new["fa_output_contract"] = ("Return one reviewed_japanese string per translation_unit, in order. "
                                             "Never place, remove or move FA/FE/FB; the free-form combined string stays empty.")
            out_entries.append(new)
        out_batches.append(out_entries)

    batch_meta = []
    for number, (rows, out_entries) in enumerate(zip(batches, out_batches), start=1):
        meta = {
            "phase": PHASE, "batch": number, "file": BATCH_FILES[number - 1].name, "entries": len(out_entries),
            "status": "source_only_not_translated", "no_new_translation_generated": True,
            "resolution_classes": dict(Counter(e["resolution_class"] for e in out_entries)),
            "speaker_confidence": dict(Counter(e["speaker_confidence"] for e in out_entries)),
            "speaker_categories": dict(Counter(e["speaker_category"] for e in out_entries)),
            "voice_application": dict(Counter(e["voice_application"] for e in out_entries)),
            "categories": dict(sorted(Counter(e["category"] for e in out_entries).items())),
            "fa_entries": sum("translation_units" in e for e in out_entries),
            "buffer_entries": sum(bool(e["buffers"]) for e in out_entries),
            "glossary_states": dict(Counter(e["glossary"]["state"] for e in out_entries)),
            "translation_risk": dict(Counter(e["translation_risk"]["level"] for e in out_entries)),
            "style_handoff": STYLE_HANDOFF.name}
        batch_meta.append(meta)
        guarded_write(BATCH_FILES[number - 1], {"metadata": meta, "entries": out_entries})

    proven = sorted({e["dialogue_group_id"] for e in entries if e["dialogue_group_id"]})
    proven_placement = {g: sorted({n for n, rows in enumerate(batches, 1) for e in rows if e["dialogue_group_id"] == g})
                        for g in proven}
    style = style_handoff(batch_meta, probe, profile_doc, unresolved_terms)
    guarded_write(STYLE_HANDOFF, style)
    manifest = {
        "metadata": {"phase": PHASE, "purpose": "Deterministic split of the 569-entry Claude queue into four batches",
                     "total_entries": len(entries), "batches": len(batches), "batch_sizes": [len(r) for r in batches],
                     "size_range_required": list(BATCH_SIZE_RANGE),
                     "split_rule": ["Batch 1 holds every NON_DIALOGUE row, ordered by (category, ROM offset, id).",
                                    "Dialogue rows form units: rows sharing a conversation_id or a proven dialogue_group_id are one unit.",
                                    "Units are ordered by their lowest ROM offset and cut into three runs near thirds; a unit is never split.",
                                    "No random choice, clock or hash seed is used; the same inputs give the same files."],
                     "units_total": len(units), "proven_groups": proven, "proven_group_batches": proven_placement,
                     "input_validation": validate_input(entries),
                     "inputs_sha256": {p.name: sha256(p) for p in (HANDOFF_V3, GLOSSARY_HANDOFF, ATTRIBUTION, VOICE_REVIEW,
                                                                    PROFILES, INVENTORY, GLOSSARY)},
                     "protected_files_sha256": {str(p.relative_to(ROOT)).replace("\\", "/"): sha256(p) for p in PROTECTED}},
        "batches": [{**m, "entry_ids": [e["id"] for e in rows]} for m, rows in zip(batch_meta, batches)]}
    guarded_write(MANIFEST, manifest)
    return {"batch_sizes": [len(r) for r in batches], "units": len(units),
            "classes": [m["resolution_classes"] for m in batch_meta], "proven": proven_placement}


def style_handoff(batch_meta, probe, profile_doc, unresolved_terms):
    status_counts = profile_doc["metadata"]["voice_status_counts"]
    return {
        "metadata": {"phase": PHASE, "status": "guidance_only_not_translated", "batches": [m["file"] for m in batch_meta],
                     "batch_sizes": [m["entries"] for m in batch_meta]},
        "scope": "Final Cleanup translation/context queue (569 entries). The previous Japanese candidate is a starting point only; "
                 "nothing is pre-approved. Return the contract below. Do not run ROM tools.",
        "language_rules": [
            "Kana only: hiragana, katakana, and the Japanese-charmap symbols below. No kanji.",
            "Natural game Japanese in the manner of the main Pokémon series; keep the existing wakachigaki baseline "
            "for prose, but do not put spaces inside proper names, place names, mission titles or short UI labels.",
            "Keep the meaning, event conditions, numbers, item/mission/battle conditions and foreshadowing unchanged. "
            "Never add or remove information to make a line sound nicer.",
            "Do not state an official Japanese name from memory. Use an approved glossary term, or mark the entry needs_context "
            "when a name is not approved.",
            "Runtime width that is merely unverified must not stop the translation. Write natural, compact Japanese; "
            "Codex checks technical fit afterwards. Never cut meaning to save width."],
        "charmap_probe": {"supported": [c for c, ok in probe.items() if ok], "unsupported": [c for c, ok in probe.items() if not ok],
                          "note": "Probed against the Japanese PCS codec. ASCII letters and digits are allowed; Latin text inside a "
                                  "Japanese string is handled by the controlfix page switch, not by you."},
        "speaker_rules": {
            "PROVEN": "A trainer ID or object binding only. Keep the same speaker's lines consistent and in the same batch. "
                      "It is not a canon identity, a name reading, a gender or an age.",
            "CONFIRMED_VOICE": f"An approved profile is attached ({status_counts.get('CONFIRMED_VOICE', 0)} profile overall). Follow it.",
            "PROVISIONAL_VOICE": "Reference only. Do not force it as the person's own voice.",
            "NEUTRAL_ONLY_or_INSUFFICIENT_EVIDENCE": "Use a natural neutral tone that follows the English attitude.",
            "PLAUSIBLE": "A candidate from object-script proximity. State it as a candidate; never treat entries as the same person.",
            "UNKNOWN": "Reflect the English attitude (cheerful, angry, formal, sarcastic, surprised, disappointed). "
                       "No invented first person, gendered ending, dialect or old-age speech.",
            "NON_DIALOGUE": "No NPC voice profile. Use the register of the interface or message type.",
            "first_and_second_person": "Omit pronouns unless the English or a proven profile requires one. 'きみ' for the player "
                                       "is a convention, not a speaker trait."},
        "official_character_rule": "No official canon character is proven (0). A shared name is not identity. Do not claim to "
                                   "reproduce an original Japanese voice: the identity, the source game and a Japanese-version "
                                   "voice reference are all missing.",
        "glossary_rules": [
            "Use `approved_glossary_terms` only for the exact entry (scope and entry_ids are given; global_replace is false for every Phase 6C term).",
            "Never substitute by substring. Ace is not Aerial Ace; Cut, Strength and Fighting rejected as terms stay ordinary words.",
            "`unresolved_glossary_warnings` are warnings: do not translate that term by guess; choose needs_context if the line depends on it.",
            "`glossary_matcher_hits` lists matches of the merged 292-term glossary and is informational."],
        "control_rules": {
            "preserve": ["FE", "FA", "FB", "FC", "FD", "waits", "colors", "alignment", "buffers", "placeholders", "source control boundaries"],
            "dangerous_controls": ["FE newline", "FA wait-and-scroll", "FB wait-and-clear", "FC page/style", "FD substitution",
                                   "colors, quote, button, alignment and pause tokens"],
            "technical_hold": "If natural Japanese needs a word order that crosses a source control, do not move the control: "
                              "return status needs_technical_fit and explain."},
        "buffer_rule": "Keep buffer tokens in source order. Unknown or caller-dependent buffers (buffer1-3, battle codes 00/01/2A/36/38) are "
                       "never guessed: return needs_context. Engine-defined name/move/ability battle codes and [player]/[rival] are typed.",
        "fa_contract": {
            "applies_to": "entries that contain `translation_units`",
            "claude_returns": "one reviewed_japanese per unit in source order; reviewed_japanese at entry level stays empty",
            "never": "place, remove, move, merge or split FA/FE/FB; invent a segment boundary",
            "hold": "needs_technical_fit when the meaning cannot be carried inside the segments"},
        "output_contract": {
            "status_values": ALLOWED_OUTCOMES,
            "per_entry": {"id": "same as input", "status": "confirmed | needs_context | needs_technical_fit",
                          "reviewed_japanese": "non-FA entries; '' for hold or FA",
                          "segments": "FA entries: [{segment_index, source, reviewed_japanese, protected_tokens, after_control}]",
                          "protected_tokens": "tokens kept, in source order", "glossary_terms_used": [],
                          "new_glossary_candidates": "proposals only; never approved here",
                          "speaker_notes": "what evidence was used; 'unknown' stays unknown",
                          "voice_applied": "none | confirmed_profile | provisional_reference | register_only",
                          "reason": "short Japanese or English explanation",
                          "review_source": "claude_cli", "translation_risk": "low | medium | high"}},
        "known_bad_patterns": [
            "Ace matched inside Aerial Ace", "memory-only official name", "speaker invented from a name or pointer proximity",
            "first person or gendered ending added without evidence", "FA appended or moved by character index",
            "buffer guessed from the English sentence", "meaning changed to sound more natural",
            "unsupported glyph (ヴ 「 」 ： 〜 ( ) % = +) used", "proper noun changed without a glossary decision"],
        "counters": {"pokemon": "ひき", "items": "こ", "times": "かい", "options": "とおり"},
        "unresolved_glossary_terms": [{"term": u["term"], "decision": u["decision"], "affected_ids": u["affected_ids"]}
                                      for u in unresolved_terms],
    }


def validate_outputs(report_only=False):
    """Mechanical checks used by the tests and the final report."""
    handoff = read(HANDOFF_V3)
    source = {e["id"]: e for e in handoff["entries"]}
    manifest = read(MANIFEST)
    batches = [read(p) for p in BATCH_FILES]
    ids = [e["id"] for b in batches for e in b["entries"]]
    problems = []
    if sorted(ids) != sorted(source) or len(ids) != len(set(ids)) or len(ids) != EXPECTED["total"]:
        problems.append("id_accounting")
    for batch in batches:
        n = len(batch["entries"])
        if not BATCH_SIZE_RANGE[0] <= n <= BATCH_SIZE_RANGE[1]:
            problems.append(f"batch_size:{batch['metadata']['batch']}:{n}")
    for batch in batches:
        for entry in batch["entries"]:
            original = source[entry["id"]]
            if any(entry.get(k) != v for k, v in original.items()):
                problems.append(f"original_field_changed:{entry['id']}")
            if "reviewed_japanese" in entry:
                problems.append(f"translation_present:{entry['id']}")
    placement = defaultdict(set)
    for batch in batches:
        for entry in batch["entries"]:
            if entry["dialogue_group_id"]:
                placement[entry["dialogue_group_id"]].add(batch["metadata"]["batch"])
    if any(len(v) != 1 for v in placement.values()):
        problems.append("proven_group_split")
    if [b["entry_ids"] for b in manifest["batches"]] != [[e["id"] for e in b["entries"]] for b in batches]:
        problems.append("manifest_mismatch")
    return {"problems": problems, "batch_sizes": [len(b["entries"]) for b in batches], "ids": len(ids)}


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) == 2 else "build"
    if command == "build":
        print(build())
    elif command == "validate":
        print(validate_outputs())
    else:
        sys.exit(__doc__)
