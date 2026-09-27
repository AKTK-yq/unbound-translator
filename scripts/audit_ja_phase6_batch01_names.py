#!/usr/bin/env python3
"""Verify Batch 01's memory-based franchise names against PokeAPI ja-hrkt."""

from __future__ import annotations

from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.pcs_text import Charmap
from lib.pokeapi_localizer import PokeAPILocalizer, language_value, same_name, source_slug
from lib.translation_tokens import strip_hma_quotes

REVIEW = ROOT / "tests/fixtures/ja_phase6_batch01_claude_review.json"
OUTPUT = ROOT / "out/phase6/ja_phase6_batch01_unverified_names.json"

# Explicit source-span and Claude-word pairing. PokeAPI supplies only the
# authoritative value; this table is never an official-name authority.
# Kind: pokemon, move, item, ability, or trainer_class (unsupported by PokeAPI).
TERMS = {
    "scr_74037F": [("Cacnea", "pokemon", "サボネア"), ("Cut", "move", "いあいぎり")],
    "scr_74572A": [("Abra", "pokemon", "ケーシィ"), ("Kadabra", "pokemon", "ユンゲラー"), ("Reuniclus", "pokemon", "ランクルス")],
    "scr_74BC3B": [("Swinub", "pokemon", "ウリムー")],
    "scr_74BBE2": [("Zubat", "pokemon", "ズバット")],
    "scr_74F85C": [("Bird Keepeer", "trainer_class", "とりつかい")],
    "scr_74FB23": [("Hoopa", "pokemon", "フーパ")],
    "scr_750327": [("Duskull", "pokemon", "ヨマワル"), ("Shadow Sneak", "move", "かげうち")],
    "scr_75B6F5": [("Clefairy", "pokemon", "ピッピ")],
    "scr_75BA2B": [("Snover", "pokemon", "ユキカブリ")],
    "scr_75C112": [("Gliscor", "pokemon", "グライオン"), ("Rock Smash", "move", "いわくだき")],
    "scr_75C12E": [("Gliscor", "pokemon", "グライオン")],
    "scr_75C267": [("Staraptor", "pokemon", "ムクホーク"), ("Aerial Ace", "move", "つばめがえし")],
    "scr_75DC8D": [("Sandslash", "pokemon", "サンドパン")],
    "scr_1F00A8E": [("Poké Ball", "item", "モンスターボール"), ("TM Case", "item", "わざマシンケース")],
    "scr_1F00C0A": [("TM Case", "item", "わざマシンケース")],
    "scr_1F00D23": [("Incinerate", "move", "やきつくす")],
    "scr_1F01BEF": [("Defog", "move", "きりばらい")],
    "scr_1F02B2B": [("Heart Scales", "item", "ハートのウロコ")],
    "scr_1F02C3C": [("Tiny Mushrooms", "item", "ちいさなキノコ")],
    "scr_1F02C4B": [("Big Mushrooms", "item", "おおきなキノコ")],
    "scr_1F02C59": [("Balm Mushrooms", "item", "かおるキノコ")],
    "scr_1F02C68": [("Tiny Mushrooms", "item", "ちいさなキノコ")],
    "scr_1F02C79": [("Tiny Mushrooms", "item", "ちいさなキノコ")],
    "scr_1F02DD8": [("Keen Eye", "ability", "するどいめ"), ("Infiltrator", "ability", "すりぬけ"),
                     ("Pikipek", "pokemon", "ツツケラ"), ("Hoothoot", "pokemon", "ホーホー")],
    "scr_1F02F4F": [("Keen Eye", "ability", "するどいめ"), ("Infiltrator", "ability", "すりぬけ")],
    "scr_1F02FFA": [("Cutiefly", "pokemon", "アブリー"), ("Sweet Scent", "move", "あまいかおり")],
    "scr_1F030EE": [("Stench", "ability", "あくしゅう")],
    "scr_1F02C8C": [("Big Mushroom", "item", "おおきなキノコ")],
    "scr_1F02C9B": [("Big Mushrooms", "item", "おおきなキノコ")],
    "scr_1F02CAD": [("Balm Mushroom", "item", "かおるキノコ")],
    "scr_1F02CBD": [("Balm Mushrooms", "item", "かおるキノコ")],
    "scr_1F03531": [("Revives", "item", "げんきのかけら"), ("Paralyze Heals", "item", "まひなおし")],
    "scr_1F03A3C": [("Strength", "move", "かいりき")],
    "scr_1F03CBD": [("Master Ball", "item", "マスターボール"), ("Hoopa", "pokemon", "フーパ")],
    "scr_1F03E86": [("Hoopa", "pokemon", "フーパ")],
    "scr_1F03EC8": [("Hoopa", "pokemon", "フーパ"), ("Master Ball", "item", "マスターボール")],
    "scr_1F03F47": [("Hoopa", "pokemon", "フーパ")],
    "scr_1F04188": [("Old Rod", "item", "ボロのつりざお"), ("Magikarp", "pokemon", "コイキング"),
                     ("Good Rod", "item", "いいつりざお")],
    "scr_1F042EA": [("Max Repels", "item", "ゴールドスプレー")],
    "scr_1F045DD": [("Dusk Ball", "item", "ダークボール"), ("Ultra Ball", "item", "ハイパーボール")],
    "scr_1F046E2": [("Hyper Potions", "item", "すごいキズぐすり")],
    "scr_1F047E3": [("Moomoo Milk", "item", "モーモーミルク")],
    "scr_1F04E4C": [("Moomoo Milk", "item", "モーモーミルク")],
    "scr_1F0516C": [("Hidden Power", "move", "めざめるパワー")],
    "scr_1F051C7": [("Hidden Power", "move", "めざめるパワー")],
    "scr_1F0521F": [("Hidden Power", "move", "めざめるパワー")],
    "scr_1F052AA": [("Hidden Power", "move", "めざめるパワー")],
    "scr_1F0572F": [("Magmar", "pokemon", "ブーバー"), ("Magmarizer", "item", "マグマブースター")],
    "scr_1F05779": [("Electabuzz", "pokemon", "エレブー"), ("Electirizer", "item", "エレキブースター")],
    "scr_1F0591E": [("Everstone", "item", "かわらずのいし")],
    "scr_1F05B12": [("Everstone", "item", "かわらずのいし")],
    "scr_1F05B72": [("Everstone", "item", "かわらずのいし")],
    "scr_1F05DD1": [("Thunder Stone", "item", "かみなりのいし"), ("Pikachu", "pokemon", "ピカチュウ")],
    "scr_1F05EB5": [("Oval Stone", "item", "まんまるいし")],
    "scr_1F05F04": [("Oval Stone", "item", "まんまるいし")],
    "scr_1F07376": [("Latiosite", "item", "ラティオスナイト")],
}

ENDPOINT = {"pokemon": "pokemon-species", "move": "move", "item": "item", "ability": "ability"}


def lookup(localizer, source, kind):
    if kind not in ENDPOINT:
        return {"status": "not_supported", "english_pokeapi": None,
                "japanese_pokeapi": None, "entity": None}
    endpoint = ENDPOINT[kind]
    # A pluralized story phrase is not an exact official item name. A
    # singular candidate is context only, never promoted to verified.
    candidate = source
    if kind == "item" and source.endswith("s"):
        candidate = source[:-1]
    identifier = source_slug(candidate, "item_names" if kind == "item" else "move_names" if kind == "move" else "pokemon_names" if kind == "pokemon" else "ability_names")
    payload = localizer._get(endpoint, identifier)
    if not payload:
        return {"status": "not_found", "english_pokeapi": None,
                "japanese_pokeapi": None, "entity": f"{endpoint}/{identifier}"}
    english = language_value(payload.get("names"), "en", "name")
    japanese = language_value(payload.get("names"), "ja", "name")
    if not english or not japanese:
        return {"status": "not_supported", "english_pokeapi": english,
                "japanese_pokeapi": japanese, "entity": f"{endpoint}/{identifier}"}
    if not same_name(source, english, "item_names" if kind == "item" else "move_names" if kind == "move" else "pokemon_names" if kind == "pokemon" else "ability_names"):
        return {"status": "ambiguous", "english_pokeapi": english,
                "japanese_pokeapi": japanese, "entity": f"{endpoint}/{identifier}"}
    try:
        Charmap(target_lang="ja").encode(f"[japanese]{japanese}[latin]")
    except (UnicodeEncodeError, ValueError):
        return {"status": "not_supported", "english_pokeapi": english,
                "japanese_pokeapi": japanese, "entity": f"{endpoint}/{identifier}"}
    return {"status": "verified", "english_pokeapi": english,
            "japanese_pokeapi": japanese, "entity": f"{endpoint}/{identifier}"}


def build(review, localizer):
    remembered = {row["id"] for row in review if "公式名を記憶" in row.get("reason", "")}
    if remembered != TERMS.keys() or len(remembered) != 56:
        raise ValueError(f"Memory-name mapping mismatch: missing={remembered - TERMS.keys()}, extra={TERMS.keys() - remembered}")
    by_id = {row["id"]: row for row in review}
    unique = {(source, kind) for terms in TERMS.values() for source, kind, _japanese in terms}
    with ThreadPoolExecutor(max_workers=8) as executor:
        checked = dict(zip(unique, executor.map(lambda key: lookup(localizer, *key), unique)))
    rows = []
    for entry_id, terms in TERMS.items():
        review_row = by_id[entry_id]
        source = strip_hma_quotes(review_row["original"])
        source_flat = " ".join(source.replace("\\l", " ").replace("\\n", " ").split())
        full_japanese = review_row["reviewed_japanese"]
        results = []
        for english, kind, claude in terms:
            if english not in source_flat:
                raise ValueError(f"English source term absent: {entry_id}: {english}")
            if claude.replace(" ", "") not in full_japanese.replace(" ", ""):
                raise ValueError(f"Claude term absent: {entry_id}: {claude}")
            evidence = checked[(english, kind)]
            if evidence["status"] == "verified":
                status = ("verified_exact" if claude == evidence["japanese_pokeapi"]
                          else "verified_but_difference")
            else:
                status = evidence["status"]
            results.append({"english_source_term": english, "term_type": kind,
                            "claude_japanese": claude, "verification_status": status,
                            "memory_matches_pokeapi": (claude == evidence["japanese_pokeapi"]
                                                       if evidence["japanese_pokeapi"] else None),
                            **evidence})
        rows.append({"id": entry_id, "category": review_row["category"],
                     "original": review_row["original"], "claude_japanese": full_japanese,
                     "context": review_row.get("reason", ""), "terms": results,
                     "all_verified": all(term["verification_status"] in {"verified_exact", "verified_but_difference"}
                                         for term in results)})
    counts = Counter(term["verification_status"] for row in rows for term in row["terms"])
    return {"metadata": {"phase": "6B-1", "entry_count": len(rows),
                         "term_count": sum(len(row["terms"]) for row in rows),
                         "status_counts": dict(counts),
                         "rule": "Only exact English PokeAPI names and kana-encodable ja-hrkt are verified."},
            "entries": rows}


def main():
    review = json.loads(REVIEW.read_text(encoding="utf-8"))
    localizer = PokeAPILocalizer("ja", ROOT / ".cache/pokeapi", timeout=8)
    output = build(review, localizer)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(output["metadata"])


if __name__ == "__main__":
    main()
