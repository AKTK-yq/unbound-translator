#!/usr/bin/env python3
"""Validate Claude's Phase 5 review, merge it, and classify controlfixed fit.

The reviewed wording is input data, not a glossary approval. Unresolved rows
remain English; this script never shortens or rewrites Japanese translations.
"""

from __future__ import annotations

import argparse
from collections import Counter
import copy
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib.gen3_font import text_pixel_width
from lib.pcs_text import Charmap
from lib.translation_tokens import semantic_token_counts, semantic_tokens, strip_hma_quotes


STATUSES = {"confirmed", "existing_official", "needs_context", "needs_technical_fit"}
KANJI = re.compile(r"[\u3400-\u9fff\uf900-\ufaff]")
LATIN_UNCHANGED_ID = "tbl_menu_options_00017_419E4B"
POINTER_OWNERSHIP_UNRESOLVED = {
    "tbl_battle_messages_00000_800880",
    "tbl_battle_messages_00002_965C16",
    "tbl_ability_descriptions_00000_24F3C4",
    "scr_1A6211",
}
RENDERER_WIDTHS = {
    "ability_descriptions": 191,
    "move_descriptions": 122,
    "mission_descriptions": 172,
}
SUPPLEMENTAL_RUNTIME_ROUTES = {
    "scr_1A56A7": ("Pokémon naming", "入手・捕獲後のニックネーム確認を開き、[buffer1] のポケモン名を確認する。"),
    "tbl_menu_item_storage_00005_4177C5": ("PC item storage", "PCのどうぐ預かりから個数を指定して引き出し、どうぐ名と個数bufferを確認する。"),
    "tbl_move_learning_00002_416DF7": ("move learning", "ポケモンをレベルアップさせ、技を覚える確認画面でポケモン名・技名bufferを確認する。"),
}


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, data):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def validate_review(selection, review, glossary_review):
    selected = selection["entries"]
    if len(selected) != 750 or len(review) != 750:
        raise ValueError("Phase 5 review and selection must contain exactly 750 rows")
    selection_ids = [row["id"] for row in selected]
    review_ids = [row["id"] for row in review]
    if len(set(selection_ids)) != 750 or len(set(review_ids)) != 750:
        raise ValueError("Duplicate review or selection ID")
    if set(selection_ids) != set(review_ids):
        raise ValueError("Review ID coverage differs from selection")
    selected_by_id = {row["id"]: row for row in selected}
    codec = Charmap("ja")
    for row in review:
        source = selected_by_id[row["id"]]
        entry_id = row["id"]
        if row["status"] not in STATUSES:
            raise ValueError(f"Invalid status: {entry_id}")
        if row["original"] != source["original"] or row["category"] != source["category"]:
            raise ValueError(f"Original/category mismatch: {entry_id}")
        if Counter(source["protected_tokens"]) != Counter(semantic_tokens(strip_hma_quotes(source["original"]))):
            raise ValueError(f"Selection protected tokens differ from original: {entry_id}")
        if row["status"] == "existing_official":
            if row.get("reviewed_japanese") != source.get("official_translation"):
                raise ValueError(f"PokeAPI official translation changed: {entry_id}")
            if source.get("official_source") is None:
                raise ValueError(f"Official source absent: {entry_id}")
        if row["status"] != "needs_context" and not row.get("reviewed_japanese"):
            raise ValueError(f"Applied Japanese is empty: {entry_id}")
        for field in ("reviewed_japanese", "candidate_japanese"):
            value = row.get(field)
            if value is None:
                continue
            if KANJI.search(value):
                raise ValueError(f"Kanji in {field}: {entry_id}")
            if semantic_token_counts(value) != semantic_token_counts(strip_hma_quotes(source["original"])):
                raise ValueError(f"Protected/control token mismatch in {field}: {entry_id}")
            if field == "reviewed_japanese" and row["status"] != "needs_context":
                if entry_id == LATIN_UNCHANGED_ID:
                    if value != strip_hma_quotes(source["original"]):
                        raise ValueError("L=A exception changed")
                else:
                    # Controlfix inserts the page switches. The raw candidate is
                    # checked in the same page for early unsupported-glyph errors.
                    codec.encode(f"[japanese]{value}[latin]")
    if len(glossary_review) != 78 or any(item.get("official_confirmed") for item in glossary_review):
        raise ValueError("78 glossary candidates must remain unapproved")
    return {"total": 750, "statuses": dict(Counter(row["status"] for row in review)),
            "warnings": sum(bool(row.get("review_warning")) for row in review),
            "provisional_glossary_candidates": 78}


def merge(prepared, selection, review, glossary_review):
    validation = validate_review(selection, review, glossary_review)
    prepared_by_id = {row["id"]: row for row in prepared["entries"]}
    selected_by_id = {row["id"]: row for row in selection["entries"]}
    input_entries = []
    audit_rows = []
    for row in review:
        entry_id = row["id"]
        source = selected_by_id[entry_id]
        base = prepared_by_id.get(entry_id)
        if base is None or base["original"] != source["original"] or base["category"] != source["category"]:
            raise ValueError(f"Prepared extraction mismatch: {entry_id}")
        status = row["status"]
        applied = status != "needs_context" and entry_id != LATIN_UNCHANGED_ID
        audit_rows.append({"id": entry_id, "status": status, "applied_candidate": applied,
                           "review": copy.deepcopy(row), "selection": copy.deepcopy(source)})
        if not applied:
            continue
        entry = dict(base)
        entry["translated"] = (source["official_translation"] if status == "existing_official"
                               else row["reviewed_japanese"])
        input_entries.append(entry)
    result = dict(prepared)
    result["entries"] = input_entries
    result.pop("tables", None)
    result.pop("free_texts", None)
    return result, {"validation": validation, "rows": audit_rows,
                    "latin_unchanged_exception": LATIN_UNCHANGED_ID}


def classify_fits(controlfixed, audit, *, strict_counts=True):
    translated = {row["id"]: row for row in controlfixed["entries"]}
    cmap = Charmap("ja")
    fit_rows = []
    fixed_rows = []
    unresolved_rows = []
    resolved_ids = set()
    for record in audit["rows"]:
        source = record["selection"]
        review = record["review"]
        entry_id = source["id"]
        entry = translated.get(entry_id)
        if entry is None and record["applied_candidate"]:
            raise ValueError(f"Missing controlfixed candidate: {entry_id}")
        encoded_size = None
        pixel_width = None
        if entry is not None:
            text = entry["translated"]
            encoded_size = len(cmap.encode(text))
            # The renderer advances to a new line/page at these layout
            # controls. Measuring the whole string would incorrectly reject
            # already-wrapped descriptions as one giant line.
            line_fragments = re.split(r"(?:\\n|\\l|\\p|\n)", text)
            pixel_width = max((text_pixel_width(f"[japanese]{fragment}[latin]", cmap)
                               for fragment in line_fragments), default=0)
            without_page = text.replace("[japanese]", "").replace("[latin]", "")
            if semantic_token_counts(without_page) != semantic_token_counts(strip_hma_quotes(source["original"])):
                raise ValueError(f"Controlfix changed protected controls: {entry_id}")
        slot = int(source["slot_size"])
        overflow = max(0, (encoded_size or 0) - slot)
        relocatable = bool(source["relocatable"]) and not source.get("no_relocation")
        renderer_width = RENDERER_WIDTHS.get(source["category"])
        pixel_risk = (renderer_width is not None and pixel_width is not None
                      and pixel_width > renderer_width)
        unresolved = entry is not None and (
            (overflow > 0 and not relocatable) or pixel_risk
            # FireRed's Pokédex appends a separate suffix, but the current
            # Unbound renderer has not been proven equivalent. Keep every
            # species-category candidate English until runtime is checked.
            or source["category"] == "pokedex_species"
            or entry_id in POINTER_OWNERSHIP_UNRESOLVED
        )
        if entry is not None and not unresolved:
            resolved_ids.add(entry_id)
        elif entry is not None:
            reason = ("fixed/no-relocation slot overflow" if overflow > 0 and not relocatable
                      else "known renderer-width budget exceeded" if pixel_risk
                      else "Pokédex category suffix behavior unverified" if source["category"] == "pokedex_species"
                      else "unowned source-ROM pointers remain after relocation")
            unresolved_rows.append({"id": entry_id, "category": source["category"],
                                    "status": review["status"], "reason": reason,
                                    "encoded_size": encoded_size, "slot_size": slot,
                                    "pixel_width": pixel_width, "renderer_width": renderer_width})
        if review["status"] == "needs_technical_fit":
            if unresolved and pixel_risk and not overflow:
                fit_class = "D"
            elif unresolved:
                fit_class = "C"
            elif overflow:
                fit_class = "B"
            else:
                fit_class = "A"
            fit_rows.append({"id": entry_id, "category": source["category"],
                             "original": source["original"],
                             "reviewed_japanese": review["reviewed_japanese"],
                             "controlfixed_japanese": entry["translated"],
                             "slot_size": slot, "encoded_size": encoded_size,
                             "overflow_bytes": overflow, "pixel_width": pixel_width,
                             "renderer_width": renderer_width, "relocatable": relocatable,
                             "no_relocation": bool(source.get("no_relocation")),
                             "classification": fit_class,
                             "proposed_shorter_japanese": None,
                             "reason": ("Natural wording retained; fixed/no-relocation overflow" if fit_class == "C"
                                        else "Measured width exceeds known renderer budget" if fit_class == "D"
                                        else "Pointer-owned relocation required" if fit_class == "B"
                                        else "Fits without technical rewrite"),
                             "review_warning": review.get("review_warning")})
        if source["fixed_slot"]:
            fixed_rows.append({"id": entry_id, "category": source["category"],
                               "status": review["status"], "applied_candidate": entry is not None,
                               "encoded_size": encoded_size, "slot_size": slot,
                               "overflow_bytes": overflow if entry is not None else None,
                               "fit": None if entry is None else overflow == 0,
                               "pixel_width": pixel_width, "renderer_width": renderer_width,
                               "relocatable": relocatable,
                               "no_relocation": bool(source.get("no_relocation"))})
    if strict_counts and (len(fit_rows) != 16 or len(fixed_rows) != 135):
        raise ValueError("Technical fit or fixed-slot count changed")
    resolved = dict(controlfixed)
    resolved["entries"] = [entry for entry in controlfixed["entries"] if entry["id"] in resolved_ids]
    return resolved, fit_rows, fixed_rows, unresolved_rows


def runtime_subset(source_subset, resolved, audit, relocation_map):
    resolved_ids = {row["id"] for row in resolved["entries"]}
    translated = {row["id"]: row["translated"] for row in resolved["entries"]}
    manifest = {row["id"]: row["selection"] for row in audit["rows"]}
    relocated = {row["id"] for row in relocation_map["relocations"]}
    rows = []
    source_ids = {item["id"] for item in source_subset["entries"]}
    items = list(source_subset["entries"])
    for entry_id, (route, _steps) in SUPPLEMENTAL_RUNTIME_ROUTES.items():
        if entry_id in resolved_ids and entry_id not in source_ids:
            source = manifest[entry_id]
            items.append({"id": entry_id, "category": source["category"],
                          "renderer": source["renderer"],
                          "runtime_confidence": source["runtime_confidence"],
                          "reason": source["runtime_reason"], "qa_route": route,
                          "supplemental": True})
    for item in items:
        entry_id = item["id"]
        if entry_id not in resolved_ids:
            continue
        source = manifest[entry_id]
        row = dict(item)
        route = item.get("qa_route", "")
        if entry_id in SUPPLEMENTAL_RUNTIME_ROUTES:
            steps = SUPPLEMENTAL_RUNTIME_ROUTES[entry_id][1]
        elif route == "NEW GAME":
            steps = "新規ゲームを開始し、導入会話・選択肢を順に進める。分岐は両方確認する。"
        elif route == "conditional battle":
            steps = "通常戦闘を開始し、原文に対応する戦闘状態を作る。条件を再現できない場合は未確認と記録。"
        elif route == "Mission Log":
            steps = "Mission Logを開き、該当ミッションを受注・進行して表示する。解放条件は別途確認。"
        elif route == "menu/data lookup":
            steps = f"{source['category']} に対応する画面を開く。原文表示位置と照合する。"
        else:
            steps = "該当NPC・イベントのマップを特定して会話する。所有script operandのみ確認済みで到達経路は未証明。"
        checks = ["かな文字と英語表示の共存"]
        for control in ("FE", "FA", "FB", "FC", "FD"):
            if source["controls"].get(control):
                checks.append(f"{control} control")
        if entry_id in relocated:
            checks.append("再配置先テキストと全pointer owner")
        if source["fixed_slot"]:
            checks.append("固定slot表示幅")
        row.update({"reach_steps": steps,
                    "controls": source["controls"],
                    "relocation": entry_id in relocated,
                    "rom_offset": f"0x{source['rom_offset']:08X}",
                    "slot_size": source["slot_size"],
                    "original": source["original"],
                    "japanese": translated[entry_id],
                    "check": "; ".join(checks),
                    "runtime_caveat": item.get("reason", "ROM ownership is not a runtime observation")})
        rows.append(row)
    return {"metadata": {"phase": "5B", "entry_count": len(rows),
                          "source_80_applied": sum(item["id"] in resolved_ids for item in source_subset["entries"]),
                          "supplemental_applied": sum(bool(item.get("supplemental")) for item in rows),
                          "note": "Human mGBA QA checklist; ROM ownership alone does not establish runtime reachability"},
            "entries": rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    merge_cmd = sub.add_parser("merge")
    merge_cmd.add_argument("--prepared", default="out/ja-phase5a-prepared.json")
    merge_cmd.add_argument("--selection", default="tests/fixtures/ja_phase5_selection.json")
    merge_cmd.add_argument("--review", default="tests/fixtures/ja_phase5_claude_review.json")
    merge_cmd.add_argument("--glossary-review", default="tests/fixtures/ja_phase5_glossary_review.json")
    merge_cmd.add_argument("--output", default="out/ja-phase5-reviewed-input.json")
    merge_cmd.add_argument("--audit", default="out/ja-phase5-review-audit.json")
    evaluate = sub.add_parser("evaluate")
    evaluate.add_argument("--controlfixed", required=True)
    evaluate.add_argument("--audit", default="out/ja-phase5-review-audit.json")
    evaluate.add_argument("--output", default="out/ja-phase5b-resolved.json")
    evaluate.add_argument("--fit-review", default="tests/fixtures/ja_phase5_fit_review.json")
    evaluate.add_argument("--fixed-audit", default="out/ja-phase5b-fixed-audit.json")
    evaluate.add_argument("--unresolved", default="out/ja-phase5b-unresolved.json")
    subset = sub.add_parser("subset")
    subset.add_argument("--source", default="tests/fixtures/ja_phase5_runtime_subset.json")
    subset.add_argument("--resolved", default="out/ja-phase5b-resolved.json")
    subset.add_argument("--audit", default="out/ja-phase5-review-audit.json")
    subset.add_argument("--map", required=True)
    subset.add_argument("--output", default="tests/fixtures/ja_phase5b_runtime_subset.json")
    args = parser.parse_args()
    if args.command == "merge":
        result, audit = merge(read_json(args.prepared), read_json(args.selection),
                              read_json(args.review), read_json(args.glossary_review))
        write_json(args.output, result)
        write_json(args.audit, audit)
        print(f"Validated {audit['validation']['total']}; candidates {len(result['entries'])}")
    elif args.command == "evaluate":
        resolved, fit, fixed, unresolved = classify_fits(read_json(args.controlfixed), read_json(args.audit))
        write_json(args.output, resolved)
        write_json(args.fit_review, {"metadata": {"phase": "5B", "entry_count": len(fit)}, "entries": fit})
        write_json(args.fixed_audit, {"metadata": {"phase": "5B", "entry_count": len(fixed)}, "entries": fixed})
        write_json(args.unresolved, {"metadata": {"phase": "5B", "entry_count": len(unresolved)}, "entries": unresolved})
        print(f"Resolved {len(resolved['entries'])}; unresolved {len(unresolved)}; technical classes {dict(Counter(row['classification'] for row in fit))}; fixed overflows {sum(row['fit'] is False for row in fixed)}")
    else:
        result = runtime_subset(read_json(args.source), read_json(args.resolved),
                                read_json(args.audit), read_json(args.map))
        write_json(args.output, result)
        print(f"Runtime subset {len(result['entries'])}")


if __name__ == "__main__":
    main()
