# Japanese Phase 4 runtime validation

This is the original, provisional Phase 4 build recipe. For the Claude-reviewed 56-entry update, use
[`ja-phase4-reviewed.md`](ja-phase4-reviewed.md) instead. Do not run the `003_llm_translate.py --resume` step below
against reviewed manual wording: glossary validation can invalidate reviewed inflections and invoke an LLM.

This is a 59-entry kana-only test build. The selected IDs, manual wording, and nine PokeAPI `ja-hrkt` values are in
[`tests/fixtures/ja_phase4_selection.json`](../tests/fixtures/ja_phase4_selection.json). The current English ROM must
have MD5 `9cad8e771940e7f7094d13911552cef0`.

From the repository root, with the development dependencies installed:

```bash
python 001_extract_unbound_text.py rom/unbound.gba -o out/unbound-ja-phase4-extracted.json
python 002_prepare_translation_text.py out/unbound-ja-phase4-extracted.json -o out/unbound-ja-phase4-prepared.json
python scripts/build_ja_phase4_selection.py out/unbound-ja-phase4-prepared.json tests/fixtures/ja_phase4_selection.json -o out/unbound-ja-phase4-translated.json
python 003_llm_translate.py out/unbound-ja-phase4-translated.json --target ja --auth chatgpt --resume -o out/unbound-ja-phase4-translated.json
python 004_controlfix_translations.py out/unbound-ja-phase4-translated.json -o out/unbound-ja-phase4-controlfix.json --source out/unbound-ja-phase4-prepared.json --report out/unbound-ja-phase4-controlfix-report.json --target-lang ja
python 005_hybrid_injector.py rom/unbound.gba out/unbound-ja-phase4-controlfix.json -o out/unbound-ja-phase4.gba --target-lang ja --map-output out/unbound-ja-phase4-dry-run-map.json --dry-run --fail-on-no-space
python 005_hybrid_injector.py rom/unbound.gba out/unbound-ja-phase4-controlfix.json -o out/unbound-ja-phase4.gba --target-lang ja --map-output out/unbound-ja-phase4-map.json --fail-on-no-space
python scripts/audit_ja_phase4.py rom/unbound.gba out/unbound-ja-phase4.gba out/unbound-ja-phase4-controlfix.json tests/fixtures/ja_phase4_selection.json out/unbound-ja-phase4-map.json --report out/unbound-ja-phase4-audit.json --markdown out/unbound-ja-phase4-report.md
python -m pytest
```

The selection builder checks source controls and PCS encoding; it fetches and verifies the nine PokeAPI values. The
translation CLI resumes the already curated 59 entries, so this build makes no LLM requests. The injector must show
zero encode errors, pointer mismatches, implausible pointers, truncations, missing relocations, runtime patches, and
graphics patches. The audit fails if any ROM byte falls outside the selected in-place slots, vetted destinations, and
pointer operands. It also checks every listed pointer owner, the old slots, and the source ROM MD5.

The generated `out/unbound-ja-phase4-report.md` lists all entries and their pointer evidence, and gives the mGBA
check order. Earlier character, skin, and hair prompts were runtime confirmed; other branches, NPC locations,
conditional battle messages, and mission states still need human confirmation. Keep the ROM and save files private.
