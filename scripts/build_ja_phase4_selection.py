#!/usr/bin/env python3
"""Seed a bounded Japanese runtime test from normal prepared extraction JSON."""

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib.pcs_text import Charmap
from lib.pokeapi_localizer import PokeAPILocalizer
from lib.translation_tokens import semantic_token_counts, strip_hma_quotes


def build(prepared, selection, *, verify_pokeapi=True, cache_dir=".cache/pokeapi"):
    rows = selection["entries"]
    ids = [row["id"] for row in rows]
    if not 50 <= len(ids) <= 100 or len(ids) != len(set(ids)):
        raise ValueError("Phase 4 needs 50–100 unique entry IDs")

    by_id = {entry["id"]: entry for entry in prepared["entries"]}
    if any(entry_id not in by_id for entry_id in ids):
        raise ValueError("Selection contains an ID absent from prepared extraction")

    localizer = PokeAPILocalizer("ja", cache_dir) if verify_pokeapi else None
    cmap = Charmap(target_lang="ja")
    selected = []
    for row in rows:
        entry = dict(by_id[row["id"]])
        japanese = row["japanese"]
        if row.get("origin") == "pokeapi-ja-hrkt" and localizer is not None:
            actual = localizer.translate_entry(entry)
            if actual != japanese:
                raise ValueError(
                    f"PokeAPI ja-hrkt differs for {row['id']}: {actual!r} != {japanese!r}"
                )
        original_controls = semantic_token_counts(strip_hma_quotes(entry["original"]))
        translated_controls = semantic_token_counts(japanese)
        if original_controls != translated_controls:
            raise ValueError(f"Control mismatch for {row['id']}: {original_controls} != {translated_controls}")
        cmap.encode(f"[japanese]{japanese}[latin]")
        entry["translated"] = japanese
        selected.append(entry)

    result = dict(prepared)
    result["entries"] = selected
    result.pop("tables", None)
    result.pop("free_texts", None)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prepared")
    parser.add_argument("selection")
    parser.add_argument("-o", "--output", required=True)
    parser.add_argument("--no-pokeapi-verify", action="store_true")
    args = parser.parse_args()
    prepared = json.loads(Path(args.prepared).read_text(encoding="utf-8"))
    selection = json.loads(Path(args.selection).read_text(encoding="utf-8"))
    result = build(prepared, selection, verify_pokeapi=not args.no_pokeapi_verify)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"selected: {len(result['entries'])}")
    print(f"PokeAPI ja-hrkt verified: {sum(row.get('origin') == 'pokeapi-ja-hrkt' for row in selection['entries'])}")
    print(f"output: {output}")


if __name__ == "__main__":
    main()
