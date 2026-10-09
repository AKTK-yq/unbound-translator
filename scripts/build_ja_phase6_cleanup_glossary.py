#!/usr/bin/env python3
"""Phase 6C-2B: merge the reviewed glossary and propagate it conservatively.

Stages (python scripts/build_ja_phase6_cleanup_glossary.py STAGE):
  merge     verify official evidence, merge approved terms into glossaries/ja.json
  propagate select held entries whose only blocker was a term decision
  finalize  gate the controlfixed candidates (after 004 controlfix)
  audit     binary audit of the incremental ROM
  handoff   translation handoff v2 with approved terms and speaker metadata

No new translation is produced. Candidate Japanese is never reworded.
"""

from __future__ import annotations

from collections import Counter, defaultdict
import glob
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
from scripts.audit_ja_phase6_batch01_fit import line_widths
from scripts.build_ja_phase6_batch02 import owner_audit
from scripts.build_ja_phase6_batch05 import control_sequence
from scripts.build_ja_phase6_batch06 import interior_pointer_hits
from scripts.build_ja_phase6_cleanup_stage1 import normalized_official

OUT = ROOT / "out/phase6"
FIX = ROOT / "tests/fixtures"
GLOSSARY = ROOT / "glossaries/ja.json"
GLOSSARY_BACKUP = OUT / "ja_glossary_pre_phase6c2b.json"
REVIEW = FIX / "ja_phase6_cleanup_glossary_claude_review.json"
APPROVED_PATCH = OUT / "ja_phase6_cleanup_glossary_approved.json"
UNRESOLVED_PATCH = OUT / "ja_phase6_cleanup_glossary_unresolved.json"
HANDOFF_V1 = OUT / "ja_phase6_cleanup_translation_glossary_handoff.json"
INVENTORY = OUT / "ja_phase6_final_cleanup_inventory_v2.json"
BASE_ROM = ROOT / "out/unbound-ja-phase6-cleanup-codex.gba"
NEW_ROM = ROOT / "out/unbound-ja-phase6-cleanup-glossary.gba"
SOURCE_MD5 = "9cad8e771940e7f7094d13911552cef0"
BASE_ROM_SHA256 = "9123192acb91428a88e72592bacf592e4415ed9bf4d16ef67965ec1986ebba79"
OLD_GLOSSARY_TERMS = 139
BASELINE_COUNT = 2218

APPROVED_DECISIONS = {"APPROVED_OFFICIAL", "APPROVED_PROJECT_STANDARD", "APPROVED_CONTEXT_SCOPED", "KEEP_EXISTING"}
HAN = re.compile(r"[㐀-鿿]")
STATUS_FOR = {"APPROVED_OFFICIAL": "official_verified", "APPROVED_PROJECT_STANDARD": "project_standard",
              "APPROVED_CONTEXT_SCOPED": "context_scoped", "KEEP_EXISTING": "existing_extended"}

# Hold reasons that a term decision alone can resolve (the entry text is otherwise complete).
TERM_REASON_PREFIXES = ("unverified_official_name", "unresolved_official_name")
TERM_REASONS = {"official_name_unresolved", "mission_title_glossary_proposal_not_approved",
                "glossary_candidate_unapproved"}
# Label-type scopes: the whole candidate must equal the approved term (no free text around it).
LABEL_SCOPES = {"mission_title_only", "pokedex_species_table_only", "trainer_class_table_only",
                "trainer_name_label_only", "person_name_only", "menu_label_only", "badge_name_only",
                "item_name_only", "setting_label_only"}


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def is_term_reason(reason: str) -> bool:
    return reason.startswith(TERM_REASON_PREFIXES) or reason in TERM_REASONS


# --------------------------------------------------------------------------- official evidence

def _entity_pairs():
    """English->Japanese pairs proved by earlier PokeAPI audits (exact English entity only)."""
    exact, loose, genus = set(), set(), set()
    for path in sorted(glob.glob(str(OUT / "*official*audit*.json")) + glob.glob(str(OUT / "*name_audit*.json"))):
        data = read(path)
        rows = data.get("entries") if isinstance(data, dict) else data
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            english = row.get("English term") or row.get("english_term") or row.get("source_term")
            status = row.get("verification_result") or row.get("verification class")
            japanese = row.get("pokeapi_japanese")
            pokeapi_english = row.get("pokeapi_english")
            for key in ("PokeAPI result", "official source/result"):
                nested = row.get(key)
                if isinstance(nested, dict):
                    japanese = japanese or nested.get("ja-hrkt")
                    pokeapi_english = pokeapi_english or nested.get("english")
                    status = status or nested.get("status")
                    if nested.get("english") and nested.get("ja-hrkt"):
                        genus.add((nested["english"], nested["ja-hrkt"]))
            if english and japanese:
                if status == "verified_exact":
                    exact.add((english.lower(), japanese))
                elif pokeapi_english and pokeapi_english.lower() == english.lower():
                    loose.add((english.lower(), japanese))
            for alt in (row.get("alternatives") or {}).values():
                if alt.get("result") == "verified_exact" and english:
                    exact.add((english.lower(), alt.get("pokeapi_japanese")))
            terms = row.get("official_terms")
            if isinstance(terms, dict) and row.get("provenance") == "pokeapi-ja-hrkt":
                for source, target in terms.items():
                    exact.add((source.lower(), target))
    return exact, loose, genus


def singular(english: str) -> str:
    text = english
    if text.endswith("ies"):
        return text[:-3] + "y"
    return text[:-1] if text.endswith("s") else text


def verify_official(rows):
    """Re-check every row that claims a PokeAPI-verified Japanese form."""
    exact, loose, genus = _entity_pairs()
    results = []
    for row in rows:
        if row["official_state"] not in {"verified_exact_prior_audit", "singular_verified_plural_inferred"}:
            continue
        english, final = row["english"], row["final_japanese"]
        flags = row["flags"]
        evidence, cls = None, "no_evidence"
        if flags.get("suffix_note"):
            if (f"{english} Pokémon", final + "ポケモン") in genus:
                cls, evidence = "verified_genus_pair", f"{english} Pokémon = {final}ポケモン"
        elif row["official_state"] == "singular_verified_plural_inferred":
            if (singular(english).lower(), final) in exact:
                cls, evidence = "verified_singular_plural_inferred", singular(english)
        else:
            candidates = [row["english"]] + row["surface_forms_in_affected"]
            if any((c.lower(), final) in exact for c in candidates):
                cls, evidence = "verified_exact", english
            elif any((c.lower(), final) in loose for c in candidates):
                cls, evidence = "entity_exact_but_audit_ambiguous", english
        if cls == "no_evidence" and (english.lower(), final) in exact:
            cls, evidence = "verified_exact", english
        results.append({"index": row["index"], "english": english, "final": final,
                        "decision": row["decision"], "class": cls, "evidence": evidence})
    return results


# --------------------------------------------------------------------------- merge

def build_term_rows(patch_entries, official_by_index):
    rows = []
    for entry in patch_entries:
        scope = entry["scope"]
        match = scope["match"]
        status = STATUS_FOR[entry["decision"]]
        note_parts = [f"Phase 6C-2B {entry['decision']}", f"official_state={entry['official_state']}"]
        classes = {official_by_index[i]["class"] for i in entry["review_rows"] if i in official_by_index}
        if "entity_exact_but_audit_ambiguous" in classes:
            status = "context_scoped"
            note_parts.append("needs_human_confirmation: PokeAPI entity exact but earlier audit was ambiguous only because the source wraps a line")
        note_parts.extend(entry["notes"])
        base = {
            "kind": entry["kind"], "status": status, "context_scope": entry["context_scope"],
            "global_replace": False, "case_sensitive": match["case_sensitive"],
            "categories": entry["categories"], "entry_ids": entry["entry_ids"],
            "note": "; ".join(note_parts),
        }
        for source in [entry["source"], *entry["source_variants"]]:
            rows.append({"source": source, "target": entry["target"], **base})
    return rows


def stage_merge():
    review = read(REVIEW)
    patch = read(APPROVED_PATCH)
    rows = review["terms"]
    assert len(rows) == 208
    approved_rows = [r for r in rows if r["decision"] in APPROVED_DECISIONS]
    assert len(approved_rows) == 170, len(approved_rows)
    official = verify_official(rows)
    official_by_index = {x["index"]: x for x in official}
    bad = [x for x in official if x["class"] == "no_evidence"]
    if bad:
        raise ValueError(f"official claims without evidence: {bad}")

    if not GLOSSARY_BACKUP.exists():
        base = read(GLOSSARY)
        assert len(base["terms"]) == OLD_GLOSSARY_TERMS and base["status"] == "phase5e-reviewed-terms"
        write(GLOSSARY_BACKUP, base)
    base = read(GLOSSARY_BACKUP)
    old_terms = base["terms"]
    new_terms = build_term_rows(patch["entries"], official_by_index)

    # Rejected candidates must stay out; unresolved terms must never be merged.
    rejected = {r["english"] for r in rows if r["decision"] == "REJECT_CANDIDATE"}
    unresolved = {r["english"] for r in rows if r["decision"].startswith("UNRESOLVED")}
    merged_sources = {t["source"] for t in new_terms}
    assert not rejected & merged_sources and not unresolved & merged_sources, (rejected | unresolved) & merged_sources
    keys = Counter((t["source"], t.get("context_scope", "global")) for t in [*old_terms, *new_terms])
    duplicates = [k for k, v in keys.items() if v > 1]
    assert not duplicates, duplicates
    codec = Charmap("ja")
    for term in new_terms:
        assert not HAN.search(term["target"]) and term["global_replace"] is False
        assert term["entry_ids"], term["source"]
        codec.encode("[japanese]" + term["target"] + "[latin]")
    # Existing approved translations are never overwritten.
    old_targets = {(t["source"], t.get("context_scope", "global")): t["target"] for t in old_terms}
    for term in new_terms:
        same = [v for (s, _), v in old_targets.items() if s.lower() == term["source"].lower()]
        assert all(v == term["target"] for v in same), (term["source"], same)

    merged = {**base, "status": "phase6c2b-reviewed-terms",
              "note": "Kana-only approved terms. Phase 6C-2B terms are entry-scoped (global_replace=false); "
                      "unresolved and rejected terms are intentionally absent.",
              "terms": [*old_terms, *new_terms]}
    write(GLOSSARY, merged)
    loaded = load_glossary(GLOSSARY, expected_language="ja")
    assert len(loaded.terms) == len(old_terms) + len(new_terms)
    report = {"old_terms": len(old_terms), "added_terms": len(new_terms),
              "total_terms": len(loaded.terms), "review_rows_approved": len(approved_rows),
              "patch_entries": len(patch["entries"]),
              "decision_counts": dict(Counter(r["decision"] for r in approved_rows)),
              "official_verification": dict(Counter(x["class"] for x in official)),
              "official_rows": official,
              "needs_confirmation": [x for x in official if x["class"] == "entity_exact_but_audit_ambiguous"],
              "status_counts": dict(Counter(t["status"] for t in new_terms))}
    report.update(glossary_consistency(loaded, Charmap("ja")))
    write(OUT / "ja_phase6_cleanup_glossary_merge_report.json", report)
    return {k: report[k] for k in ("old_terms", "added_terms", "total_terms", "official_verification",
                                   "conflicts", "scope_collisions")}


# --------------------------------------------------------------------------- consistency

def corpus():
    prepared = read(ROOT / "out/ja-phase5e-prepared.json")["entries"]
    return [(x["id"], x["category"], x["translation_source"]) for x in prepared]


def glossary_consistency(new_glossary, _codec):
    old_glossary = load_glossary(GLOSSARY_BACKUP, expected_language="ja") if GLOSSARY_BACKUP.exists() else new_glossary
    old_sources = {(t.source, t.context_scope) for t in old_glossary.terms}
    review = read(REVIEW)["terms"]
    high_risk = {r["english"] for r in review if r["decision"] in APPROVED_DECISIONS
                 and r["collision_risk"]["level"] in {"high", "medium"}}
    risk_sources = {t.source for t in new_glossary.terms if (t.source, t.context_scope) not in old_sources
                    and any(t.source.lower() == e.lower() for e in high_risk)}
    added, overridden, conflicts, collisions = 0, 0, [], []
    new_by_source = {(t.source, t.context_scope): t for t in new_glossary.terms}
    for entry_id, category, text in corpus():
        old = {(s, e, t.source, t.target) for s, e, t in old_glossary.matches(text, category, entry_id=entry_id)}
        new = {(s, e, t.source, t.target) for s, e, t in new_glossary.matches(text, category, entry_id=entry_id)}
        for s, e, source, target in new - old:
            owners = [t for t in new_glossary.terms if t.source == source and t.target == target
                      and (t.source, t.context_scope) not in old_sources]
            if not any(entry_id in t.entry_ids for t in owners):
                collisions.append({"id": entry_id, "source": source, "reason": "match_outside_entry_ids"})
            added += 1
        for s, e, source, target in old - new:
            cover = [x for x in new if x[0] <= s and x[1] >= e]
            overridden += 1
            if not cover or not any(target in c[3] for c in cover):
                conflicts.append({"id": entry_id, "old": [source, target],
                                  "new": [list(c[2:]) for c in cover]})
    return {"new_matches": added, "overridden_old_matches": overridden,
            "conflicts": len(conflicts), "conflict_details": conflicts[:20],
            "scope_collisions": len(collisions), "collision_details": collisions[:20],
            "collision_risk_sources_checked": len(risk_sources)}


# --------------------------------------------------------------------------- propagation

def resolved_terms_by_id(review_rows):
    result = defaultdict(list)
    for row in review_rows:
        if row["decision"] not in APPROVED_DECISIONS:
            continue
        for entry_id in row["resolved_ids"]:
            result[entry_id].append(row)
    return result


def candidate_has_terms(candidate: str, terms) -> list[str]:
    """Return the English terms whose approved Japanese is absent from the existing candidate."""
    flat = candidate.replace(" ", "")
    missing = []
    for row in terms:
        final = row["final_japanese"].replace(" ", "")
        if row["scope"]["scope"] in LABEL_SCOPES:
            body = re.sub(r"\\CC[0-9A-F]+|\[[a-z0-9_]+\]", "", flat)
            if body != final:
                missing.append(row["english"])
        elif final not in flat:
            missing.append(row["english"])
    return missing


def official_evidence_blockers(item, terms) -> list[str]:
    """Every audited name in the entry must be covered by a resolved term or be verified in the candidate."""
    blockers = []
    names = set()
    for row in terms:
        names.add(row["english"].lower())
        names.update(s.lower() for s in row["surface_forms_in_affected"])
    candidate = (item["candidate_japanese"] or "").replace(" ", "")
    for evidence in item["normalized_technical_facts"].get("official_evidence", []):
        english = evidence.get("source_term") or evidence.get("English term")
        if not english:
            continue
        state = normalized_official([evidence])
        if state == "VERIFIED_EXACT":
            final = evidence.get("final_value") or evidence.get("final Japanese") or evidence.get("pokeapi_japanese")
            if final and final.replace(" ", "") not in candidate:
                blockers.append("verified_official_name_absent_in_candidate:" + english)
        elif english.lower() not in names and singular(english).lower() not in names:
            blockers.append("audited_name_not_resolved:" + english)
    for reason in item["normalized_technical_facts"]["raw_hold_reasons"]:
        if reason.startswith("unverified_official_name:"):
            name = reason.split(":")[1].lower()
            if name not in names and singular(name).lower() not in names:
                blockers.append("hold_reason_name_not_resolved:" + name)
    return blockers


def classify_entries():
    inventory = read(INVENTORY)["entries"]
    by = {x["id"]: x for x in inventory}
    review = read(REVIEW)["terms"]
    handoff = read(HANDOFF_V1)
    index = handoff["entry_index"]
    terms_by_id = resolved_terms_by_id(review)
    rows = []
    for entry_id, info in sorted(index.items()):
        item = by[entry_id]
        facts = item["normalized_technical_facts"]
        reasons = facts["raw_hold_reasons"]
        other = [x for x in reasons if not is_term_reason(x)]
        secondary = [x for x in item["previous_secondary_holds"] if x != "GLOSSARY_APPROVAL"]
        row = {"id": entry_id, "category": item["category"], "batch": item["batch"],
               "glossary_status": info["status"], "apply_status_before": item["apply_status"],
               "resolution_class_before": item["resolution_class"],
               "previous_primary_hold": item["previous_primary_hold"],
               "raw_hold_reasons": reasons, "non_term_reasons": other,
               "approved_terms": [t["english"] for t in terms_by_id[entry_id]],
               "unresolved_terms": [x["term"] for x in info["unresolved"]]}
        if item["apply_status"] == "applied":
            row.update(propagation="already_applied", blockers=[])
        elif info["status"] == "blocked_unresolved_term":
            row.update(propagation="blocked_unresolved_term", blockers=["unresolved_term"])
        elif info["status"] == "no_glossary_term_needed":
            row.update(propagation="no_term_needed", blockers=[])
        else:
            blockers = []
            if not item["candidate_japanese"]:
                blockers.append("no_candidate_translation")
            blockers.extend(x for x in other if x != "width_unproved:layout_ambiguous")
            if "width_unproved:layout_ambiguous" in other:
                if item["category"] not in {"scripts", "plain_scripts"}:
                    blockers.append("width_unproved_structured_ui")
            blockers.extend(f"secondary:{x}" for x in secondary if x != "WIDTH_LAYOUT")
            if item["candidate_japanese"]:
                missing = candidate_has_terms(item["candidate_japanese"], terms_by_id[entry_id])
                if missing:
                    blockers.append("candidate_lacks_approved_term:" + "|".join(missing))
            if item["candidate_japanese"]:
                blockers.extend(official_evidence_blockers(item, terms_by_id[entry_id]))
            row["blockers"] = blockers
            row["propagation"] = "term_resolved_pending_technical_gate" if not blockers else "term_resolved_other_holds"
        rows.append(row)
    return rows, by


def stage_propagate():
    rows, by = classify_entries()
    selection = {x["id"]: x for x in read(FIX / "ja_phase6_selection.json")["entries"]}
    prepared = {x["id"]: x for x in read(ROOT / "out/ja-phase5e-prepared.json")["entries"]}
    baseline = read(OUT / "ja_phase6_cleanup_combined_controlfix.json")["entries"]
    assert len(baseline) == BASELINE_COUNT
    candidates = []
    for row in rows:
        if row["propagation"] == "term_resolved_pending_technical_gate":
            entry = dict(prepared[row["id"]])
            entry["translated"] = "[japanese]" + by[row["id"]]["candidate_japanese"] + "[latin]"
            candidates.append(entry)
    write(OUT / "ja_phase6_cleanup_glossary_candidates_input.json", {"entries": baseline + candidates})
    write(OUT / "ja_phase6_cleanup_glossary_propagation_stage.json", {"entries": rows})
    return {"entries": len(rows), "candidates": len(candidates),
            "propagation": dict(Counter(r["propagation"] for r in rows))}


def stage_finalize():
    rows = read(OUT / "ja_phase6_cleanup_glossary_propagation_stage.json")["entries"]
    inventory = {x["id"]: x for x in read(INVENTORY)["entries"]}
    selection = {x["id"]: x for x in read(FIX / "ja_phase6_selection.json")["entries"]}
    baseline = read(OUT / "ja_phase6_cleanup_combined_controlfix.json")["entries"]
    controlfixed = read(OUT / "ja_phase6_cleanup_glossary_candidates_controlfix.json")["entries"]
    assert controlfixed[:BASELINE_COUNT] == baseline, "controlfix changed existing entries"
    candidates = {x["id"]: x for x in controlfixed[BASELINE_COUNT:]}
    pending = [r for r in rows if r["propagation"] == "term_resolved_pending_technical_gate"]
    assert set(candidates) == {r["id"] for r in pending}
    chosen = [selection[k] for k in candidates]
    rom = (ROOT / "rom/unbound.gba").read_bytes()
    owners = {x["id"]: x for x in owner_audit(chosen, rom)["entries"]}
    interiors = interior_pointer_hits(rom, chosen)
    codec = Charmap("ja")
    injector = runpy.run_path(str(ROOT / "005_hybrid_injector.py"))
    safe = []
    for row in rows:
        key = row["id"]
        if key not in candidates:
            continue
        entry, source = candidates[key], selection[key]
        failures = []
        try:
            payload = injector["encode_text"](codec, injector["translation_for_injection"](entry),
                                              plain_script=source["category"] == "plain_scripts")
        except (UnicodeEncodeError, ValueError) as exc:
            payload = b""
            failures.append(f"encode:{exc}")
        raw = rom[source["rom_offset"]:source["rom_offset"] + source["source_encoded_size"]]
        if payload and control_sequence(raw) != control_sequence(payload):
            failures.append("source_control_sequence_changed")
        if payload and max(line_widths(payload), default=0) >= 240:
            failures.append("physical_screen_width_overflow")
        if payload and len(payload) > source["slot_size"]:
            if source["fixed"] or source["no_relocation"] or not source["relocation_possible"]:
                failures.append("fixed_or_no_relocation_overflow")
            if owners[key]["missing"] or owners[key]["stale"]:
                failures.append("pointer_owner_unproved")
            if interiors[key]:
                failures.append("interior_pointer_unproved")
            if not source["pointer_owners"]:
                failures.append("no_pointer_owner")
        if source["buffers"]:
            failures.append("buffer_in_text_unproved")
        if entry.get("translated") != "[japanese]" + inventory[key]["candidate_japanese"] + "[latin]":
            failures.append("candidate_changed_by_controlfix")
        row["gate"] = {"encoded_bytes": len(payload), "line_pixels": line_widths(payload) if payload else [],
                       "fit": "in_place" if payload and len(payload) <= source["slot_size"] else "relocation",
                       "failures": failures}
        if failures:
            row["propagation"] = "term_resolved_technical_gate_failed"
            row["blockers"] = failures
        else:
            row["propagation"] = "safe_injectable"
            safe.append(entry)
    write(OUT / "ja_phase6_cleanup_glossary_propagation_stage.json", {"entries": rows})
    write(OUT / "ja_phase6_cleanup_glossary_safe_controlfix.json", {"entries": safe})
    write(OUT / "ja_phase6_cleanup_glossary_combined_controlfix.json", {"entries": baseline + safe})
    return {"safe": len(safe), "failed": sum(r["propagation"] == "term_resolved_technical_gate_failed" for r in rows)}


# --------------------------------------------------------------------------- binary audit

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


def assert_strict_map(plan, built, input_count):
    assert plan["stats"] == built["stats"]
    assert plan["relocations"] == built["relocations"]
    assert built["stats"]["input_entries"] == input_count
    for key in ("skipped_pointer_mismatch", "skipped_implausible_pointer", "skipped_no_space",
                "encode_errors", "fixed_truncated", "no_relocation_truncated",
                "ability_descriptions_compacted", "runtime_patches", "graphics_patches",
                "skipped_unsafe", "skipped_bounds"):
        assert built["stats"][key] == 0, (key, built["stats"][key])
    assert not built["missing_relocations"] and not built["missing_fixed_slots"]
    assert not built["runtime_patches"] and not built["graphics_patches"]


def audit_rom(before_path=BASE_ROM, after_path=NEW_ROM):
    before, after = Path(before_path).read_bytes(), Path(after_path).read_bytes()
    assert len(before) == len(after) == 0x2000000
    assert hashlib.sha256(before).hexdigest() == BASE_ROM_SHA256
    safe = read(OUT / "ja_phase6_cleanup_glossary_safe_controlfix.json")["entries"]
    baseline = read(OUT / "ja_phase6_cleanup_combined_controlfix.json")["entries"]
    assert len(baseline) == BASELINE_COUNT
    plan = read(OUT / "ja_phase6_cleanup_glossary_incremental_dry_run_map.json")
    built = read(OUT / "ja_phase6_cleanup_glossary_incremental_map.json")
    assert_strict_map(plan, built, len(safe))
    relocated = {x["id"]: x for x in built["relocations"]}
    codec = Charmap("ja")
    injector = runpy.run_path(str(ROOT / "005_hybrid_injector.py"))
    allowed = {"in_place_text": set(), "relocated_text": set(), "pointer_writes": set()}
    for entry in safe:
        key = entry["id"]
        raw = injector["encode_text"](codec, injector["translation_for_injection"](entry),
                                      plain_script=entry["category"] == "plain_scripts")
        old, size = int(entry["address"], 16), entry["byte_length"]
        move = relocated.get(key)
        if move:
            new = int(move["new_offset"], 16)
            assert move["storage"] == "vetted_ff" and move["byte_length"] == len(raw)
            assert after[new:new + len(raw)] == raw and before[new:new + len(raw)] == b"\xff" * len(raw)
            allowed["relocated_text"].update(range(new, new + len(raw)))
            for pointer in move["pointer_sources"]:
                pos = int(pointer, 16)
                assert before[pos:pos + 4] == (0x08000000 + old).to_bytes(4, "little")
                assert after[pos:pos + 4] == (0x08000000 + new).to_bytes(4, "little")
                allowed["pointer_writes"].update(range(pos, pos + 4))
        else:
            assert len(raw) <= size and after[old:old + size] == raw.ljust(size, b"\xff")
            allowed["in_place_text"].update(range(old, old + size))
    old_relocations = {}
    for name in ("ja_phase6_batch04_map.json", "ja_phase6_batch05_incremental_map.json",
                 "ja_phase6_batch06_incremental_map.json", "ja_phase6_cleanup_incremental_map.json"):
        old_relocations.update({x["id"]: x for x in read(OUT / name)["relocations"]})
    protected = set()
    for entry in baseline:
        key = entry["id"]
        old = old_relocations.get(key)
        if old:
            pos = int(old["new_offset"], 16)
            protected.update(range(pos, pos + old["byte_length"]))
            for pointer in old["pointer_sources"]:
                p = int(pointer, 16)
                protected.update(range(p, p + 4))
        else:
            pos = int(entry["address"], 16)
            protected.update(range(pos, pos + entry["byte_length"]))
    allowed_all = set().union(*allowed.values())
    assert not protected & allowed_all, "glossary propagation overlaps existing translation storage"
    for a, b in (("in_place_text", "relocated_text"), ("in_place_text", "pointer_writes"),
                 ("relocated_text", "pointer_writes")):
        assert not allowed[a] & allowed[b], (a, b)
    changed = {i for i, (x, y) in enumerate(zip(before, after)) if x != y}
    unexpected = changed - allowed_all
    assert not changed & protected, f"existing translations changed: {ranges(changed & protected)[:5]}"
    assert not unexpected, f"unexpected bytes: {ranges(unexpected)[:5]}"
    result = {"status": "PASS", "base_sha256": hashlib.sha256(before).hexdigest(),
              "new_md5": hashlib.md5(after).hexdigest(), "new_sha256": hashlib.sha256(after).hexdigest(),
              "existing_2218_unchanged": True, "changed_bytes": len(changed),
              "changed_ranges": ranges(changed),
              "classified_changed_bytes": {name: len(changed & area) for name, area in allowed.items()},
              "unexpected_bytes": 0, "relocated": len(relocated),
              "pointer_writes": built["stats"]["pointer_writes"],
              "strict_incremental_dry_run": "PASS", "entries": len(safe)}
    write(OUT / "ja_phase6_cleanup_glossary_binary_audit.json", result)
    return {k: result[k] for k in ("status", "changed_bytes", "classified_changed_bytes", "unexpected_bytes",
                                     "new_sha256", "entries")}


# --------------------------------------------------------------------------- handoff v2

CONTEXT_MARKERS = {"needs_context", "unresolved_dynamic_buffer", "dynamic_buffer_or_suffix_unproved",
                   "dynamic_buffer_width_or_page_unproved", "review_status:needs_context",
                   "glossary_scope_unproved", "possible_glossary_collision", "review_context_or_incomplete",
                   "secondary:UNKNOWN_BUFFER", "secondary:CONTEXT_REQUIRED", "secondary:SPEAKER_REQUIRED"}
TECHNICAL_MARKERS = ("fa_layout", "terminal_fa", "unresolved_fa_placement", "fixed_or_no_relocation_overflow",
                     "no_pointer_owner", "pointer_owner_unproved", "interior_pointer_unproved",
                     "width_unproved_structured_ui", "source_control_sequence_changed", "secondary:FA_",
                     "secondary:STRUCTURED_UI", "secondary:POINTER_OWNER", "known_structured_constraint")
TRANSLATION_MARKERS = ("no_candidate_translation", "candidate_lacks_approved_term", "no_reviewed_japanese",
                       "no_complete", "review_status:needs_technical_fit", "needs_technical_fit",
                       "technical_fit_unapproved", "translation_incomplete", "physical_screen_width_overflow",
                       "approved_glossary_target_absent", "secondary:INCOMPLETE_TRANSLATION", "script_width_unproved",
                       "candidate_changed_by_controlfix", "buffer_in_text_unproved")


def reroute(blockers):
    """Deterministic queue routing for a formerly glossary-class entry. No wording is judged."""
    flat = list(blockers)
    if any(b in CONTEXT_MARKERS or b.split(":")[0] in CONTEXT_MARKERS for b in flat):
        return "CLAUDE_CONTEXT"
    if any(b.startswith(TRANSLATION_MARKERS) for b in flat):
        return "CLAUDE_TRANSLATION"
    if any(b.startswith(TECHNICAL_MARKERS) for b in flat):
        return "CODEX_INVESTIGATION"
    return "CLAUDE_TRANSLATION"


def name_mentions(original, glossary):
    flat = re.sub(r"\\[lp]|\s+", " ", original)
    found = []
    for term in glossary.terms:
        if term.kind == "person" and re.search(r"(?<![A-Za-z])" + re.escape(term.source) + r"(?![A-Za-z])", flat):
            found.append({"name": term.source, "japanese": term.target,
                          "identity_claim": "none: name match only; not asserted to be the same character"})
    return found


def stage_handoff():
    inventory = read(INVENTORY)
    v2 = {x["id"]: x for x in inventory["entries"]}
    stage = {x["id"]: x for x in read(OUT / "ja_phase6_cleanup_glossary_propagation_stage.json")["entries"]}
    review = read(REVIEW)["terms"]
    v1 = read(HANDOFF_V1)
    v1_queue = {x["id"]: x for x in read(OUT / "ja_phase6_cleanup_for_claude_translation.json")["entries"]}
    unresolved_patch = read(UNRESOLVED_PATCH)["entries"]
    selection = {x["id"]: x for x in read(FIX / "ja_phase6_selection.json")["entries"]}
    glossary = load_glossary(GLOSSARY, expected_language="ja")
    scope_ids = set(v1["entry_scope_guidance_47"])
    terms_by_id = resolved_terms_by_id(review)
    unresolved_by_id = defaultdict(list)
    for item in unresolved_patch:
        for entry_id in item["affected_ids"]:
            unresolved_by_id[entry_id].append(item)

    routing = []
    for row in inventory["entries"]:
        key = row["id"]
        info = stage.get(key)
        before = row["resolution_class"]
        row["glossary_propagation"] = {"status": info["propagation"] if info else
                                       ("term_identification_needed" if key in scope_ids else "not_in_glossary_scope")}
        if info and info["propagation"] == "safe_injectable":
            row["apply_status"] = "applied"
            row["resolution_class"] = "GLOSSARY_PROPAGATED"
            row["next_queue"] = None
            row["final_current_status"] = "applied_glossary_propagation"
        elif row["apply_status"] == "applied":
            pass
        elif key in scope_ids:
            row["next_queue"] = "claude_glossary"
        elif before == "CLAUDE_GLOSSARY":
            if info["propagation"] == "blocked_unresolved_term":
                row["next_queue"] = "claude_glossary"
            else:
                blockers = list(info["blockers"]) or [f"non_term:{x}" for x in info["non_term_reasons"]]
                if info["propagation"] == "no_term_needed":
                    blockers = ["candidate_lacks_approved_term:false_positive_term_candidate_unchecked"]
                row["resolution_class"] = reroute(blockers)
                row["next_queue"] = {"CLAUDE_TRANSLATION": "claude_translation", "CLAUDE_CONTEXT": "claude_translation",
                                     "CODEX_INVESTIGATION": "codex_investigation"}[row["resolution_class"]]
        if row["resolution_class"] != before:
            routing.append({"id": key, "before": before, "after": row["resolution_class"]})
        row["glossary_propagation"]["approved_terms"] = [t["english"] for t in terms_by_id.get(key, [])]
        row["glossary_propagation"]["unresolved_terms"] = [u["term"] for u in unresolved_by_id.get(key, [])]
        row["glossary_propagation"]["blockers"] = info["blockers"] if info else []

    inventory["metadata"]["resolution_counts"] = dict(Counter(x["resolution_class"] for x in inventory["entries"]))
    inventory["metadata"]["glossary_propagated"] = sum(x["resolution_class"] == "GLOSSARY_PROPAGATED"
                                                       for x in inventory["entries"])
    inventory["metadata"]["held_after_glossary"] = sum(x["apply_status"] != "applied" for x in inventory["entries"])
    write(OUT / "ja_phase6_final_cleanup_inventory_v3.json", inventory)

    # translation handoff v2: every held entry routed to Claude, no duplicates, metadata preserved.
    queue, class_of = [], {}
    for row in inventory["entries"]:
        if row["apply_status"] == "applied" or row["resolution_class"] not in {"CLAUDE_TRANSLATION", "CLAUDE_CONTEXT"}:
            continue
        key = row["id"]
        source = selection[key]
        facts = row["normalized_technical_facts"]
        base = v1_queue.get(key)
        if base is None:
            base = {"id": key, "batch": row["batch"], "category": row["category"], "original": row["original"],
                    "candidate": row["candidate_japanese"], "exact_reason": facts["raw_hold_reasons"],
                    "previous_primary_hold": row["previous_primary_hold"],
                    "secondary_holds": row["previous_secondary_holds"],
                    "context": {"speaker": source["speaker"], "speaker_confidence": source["speaker_confidence"],
                                "scene_id": source["scene_id"], "conversation_id": source["conversation_id"],
                                "context_before": source["context_before"], "context_after": source["context_after"],
                                "runtime_evidence": source["runtime_evidence"]},
                    "controls": source["controls"], "buffers": source["buffers"],
                    "known_technical_constraints": {"rom_offset": source["rom_offset"], "slot_size": source["slot_size"],
                                                    "fixed": source["fixed"], "no_relocation": source["no_relocation"],
                                                    "pointer_owners": source["pointer_owners"],
                                                    "normalized_facts": facts},
                    "requested_claude_task": (
                        "Review context and wording; preserve source controls and named buffers. No approval inferred."
                        if row["resolution_class"] == "CLAUDE_CONTEXT" else
                        "Provide complete kana-only wording satisfying documented controls, terms, and fit.")}
        approved = [{"term": t["english"], "japanese": t["final_japanese"], "scope": t["scope"]["scope"],
                     "official_state": t["official_state"], "decision": t["decision"],
                     "manual_use_only": bool(t["flags"].get("infl") or t["flags"].get("spelled_out"))}
                    for t in terms_by_id.get(key, [])]
        unresolved = [{"term": u["term"], "decision": u["decision"], "reason": u["reason"],
                       "needed": u.get("additional_context_needed")} for u in unresolved_by_id.get(key, [])]
        rejected = [r["english"] for r in review if r["decision"] == "REJECT_CANDIDATE" and key in r["false_positive_ids"]]
        state = ("term_unresolved" if unresolved else "term_resolved" if approved else
                 "false_positive_only" if rejected else "no_glossary_term")
        class_of[key] = row["resolution_class"]
        queue.append({
            **base,
            "resolution_class": row["resolution_class"],
            "original_english": row["original"], "current_japanese": row["candidate_japanese"],
            "glossary": {"state": state, "approved_terms": approved, "unresolved_warnings": unresolved,
                         "false_positive_terms": rejected,
                         "rule": "Use approved terms only inside their scope; do not translate unresolved terms by guess."},
            "remaining_holds": [x for x in facts["raw_hold_reasons"] if not is_term_reason(x)],
            "queue_origin": "v1_translation_queue" if key in v1_queue else "glossary_class_rerouted",
            "preserved_metadata": {
                "speaker": source["speaker"], "speaker_confidence": source["speaker_confidence"],
                "scene_id": source["scene_id"], "conversation_id": source["conversation_id"],
                "sequence_index": source["sequence_index"], "group_evidence": source["group_evidence"],
                "context_confidence": source["context_confidence"], "runtime_evidence": source["runtime_evidence"],
                "runtime_confidence": source["runtime_confidence"], "notes": source["notes"],
                "table_name": source["table_name"], "table_index": source["table_index"],
                "rom_offset": source["rom_offset"], "gba_address": source["gba_address"],
                "pointer_owners": source["pointer_owners"], "renderer_group": source["renderer_group"],
                "script_location": {"category": source["category"], "rom_offset": source["rom_offset"],
                                    "gba_address": source["gba_address"], "conversation_id": source["conversation_id"]},
                "character_name": ({"value": source["speaker"], "confidence": source["speaker_confidence"]}
                                   if source["speaker"] != "unknown" else {"value": None, "status": "speaker_unproved"}),
                "trainer_class_or_label": ({"value": row["original"].strip('"'), "table": source["table_name"]}
                                           if source["category"] in {"trainer_classes", "trainer_names"} else None),
                "source_game": {"value": None, "status": "not_proven_in_inventory"},
                "name_mentions": name_mentions(row["original"], glossary)}})
    ids = [x["id"] for x in queue]
    assert len(ids) == len(set(ids))
    for key in v1_queue:
        if v2[key]["apply_status"] != "applied":
            assert key in ids, key
    handoff = {"metadata": {
        "phase": "6C-2B", "entries": len(queue), "no_new_translation_generated": True,
        "from_v1_queue": sum(x["queue_origin"] == "v1_translation_queue" for x in queue),
        "glossary_class_rerouted": sum(x["queue_origin"] == "glossary_class_rerouted" for x in queue),
        "glossary_state": dict(Counter(x["glossary"]["state"] for x in queue)),
        "class_counts": dict(Counter(class_of.values())),
        "speaker_policy": "Speakers are copied exactly from the selection fixture; unknown speakers are never merged "
                          "or assigned. A name mention is not an identity claim. Character voice is not edited here."},
        "approved_terms_source": "glossaries/ja.json (Phase 6C-2B terms are entry-scoped; see each entry's glossary block)",
        "unresolved_terms": [{"term": u["term"], "decision": u["decision"], "affected_ids": u["affected_ids"],
                              "reason": u["reason"], "needed": u.get("additional_context_needed"),
                              "suggested_candidate_unverified": u.get("suggested_candidate_unverified")}
                             for u in unresolved_patch],
        "term_identification_needed": [
            {"id": k, "category": g["category"], "batch": g["batch"],
             "original_english": v2[k]["original"], "current_japanese": v2[k]["candidate_japanese"],
             "note": g["note"], "queue_review_reason": g["queue_review_reason"]}
            for k, g in v1["entry_scope_guidance_47"].items()],
        "entries": queue}
    write(OUT / "ja_phase6_cleanup_translation_handoff_v2.json", handoff)

    stage_rows = list(stage.values())
    resolved_all = [r for r in stage_rows if r["glossary_status"] == "glossary_resolved"]
    summary = {
        "glossary": read(OUT / "ja_phase6_cleanup_glossary_merge_report.json"),
        "entries_in_term_scope": len(stage_rows),
        "term_resolved_entries": len(resolved_all),
        "term_resolved_by_propagation": dict(Counter(r["propagation"] for r in resolved_all)),
        "safe_injectable": sum(r["propagation"] == "safe_injectable" for r in stage_rows),
        "gate_failed": sum(r["propagation"] == "term_resolved_technical_gate_failed" for r in stage_rows),
        "blocked_unresolved_term": sum(r["propagation"] == "blocked_unresolved_term" for r in stage_rows),
        "no_term_needed": sum(r["propagation"] == "no_term_needed" for r in stage_rows),
        "term_identification_needed_entries": len(scope_ids),
        "rerouted_classes": dict(Counter(f"{x['before']}->{x['after']}" for x in routing)),
    }
    write(OUT / "ja_phase6_cleanup_glossary_propagation.json",
          {"metadata": summary, "entries": stage_rows, "routing": routing})
    return {"queue": len(queue), "held_after": inventory["metadata"]["held_after_glossary"],
            "classes": handoff["metadata"]["class_counts"], "from_v1": handoff["metadata"]["from_v1_queue"],
            "rerouted": handoff["metadata"]["glossary_class_rerouted"]}


if __name__ == "__main__":
    stage = sys.argv[1] if len(sys.argv) == 2 else ""
    runner = {"merge": stage_merge, "propagate": stage_propagate, "finalize": stage_finalize,
              "audit": audit_rom, "handoff": stage_handoff}.get(stage)
    if runner is None:
        sys.exit(__doc__)
    print(runner())
