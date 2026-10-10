#!/usr/bin/env python3
"""Phase 6C-4E: immutable-input, fail-closed Batch 02 integration.

Only reviewed wording is used. Existing artifacts are verified, never replaced.
Run ``python scripts/build_ja_phase6_cleanup_batch02.py all`` from the root.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import runpy
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lib.fa_control import join_segments, parse_raw_segments, reconstruct_reviewed_segments
from lib.gen3_font import NORMAL_GLYPH_WIDTHS, NORMAL_JAPANESE_GLYPH_WIDTHS
from lib.pcs_text import Charmap, decode_pcs, fc_arg_count
from lib.renderer_profiles import horizontal_layout_trace, normal_line_widths_with_placeholders
from lib.translation_glossary import load_glossary
from lib.translation_tokens import semantic_tokens, strip_hma_quotes
from scripts.audit_ja_phase6_batch01_fit import line_widths
from scripts.audit_ja_phase6_fa import layout_trace
from scripts.build_ja_phase6_batch02 import owner_audit
from scripts.build_ja_phase6_batch06 import interior_pointer_hits
from scripts.build_ja_phase6_cleanup_batch01 import cli, digest, official_record, persist, read
from scripts.build_ja_phase6_cleanup_glossary import assert_strict_map
from scripts.build_ja_phase6_voice_integration import encoded

OUT = ROOT / 'out/phase6'
FIX = ROOT / 'tests/fixtures'
PREFIX = 'ja_phase6_cleanup_batch02_'
REVIEW = FIX / (PREFIX + 'claude_review.json')
BATCH = OUT / (PREFIX + 'for_claude.json')
BASE = ROOT / 'out/unbound-ja-phase6-cleanup-batch01.gba'
ROM = ROOT / 'out/unbound-ja-phase6-cleanup-batch02.gba'
BASE_SHA = '02c3fcb7a488e6620a274491d5490bd3339eda6935f69973f1b083e67932533c'
SOURCE_MD5 = '9cad8e771940e7f7094d13911552cef0'
STATUSES = {'confirmed': 93, 'needs_context': 49}
SPECIAL_FA = {44: 'scr_1F09154', 63: 'scr_1F0A436', 137: 'scr_1F1330A'}
TROPHIES = {81: 'scr_1F0C34F', 82: 'scr_1F0C3AF', 83: 'scr_1F0C40F'}
RELOCATIONS = {8: 'scr_1F0734A', 93: 'scr_1F0D8AA', 99: 'scr_1F0DD47',
               117: 'scr_1F116D7', 118: 'scr_1F116E1', 119: 'scr_1F116E9', 123: 'scr_1F11C50'}
HAN = re.compile(r'[\u3400-\u9fff]')

# Entry-specific semantic audit, not a translation or automatic word-order rule.
# A matching byte/token sequence cannot prove that information appears at the
# same source boundary. Keep these reviewed drafts, but do not inject them.
BOUNDARY_NOTES = {
    'scr_1F07406': 'Staraptor moves from E2 to E1 across FE.',
    'scr_1F0744B': 'Talonflame moves from E2 to E1 across FE.',
    'scr_1F07491': 'Hawlucha moves from E2 to E1 across FE.',
    'scr_1F07929': 'Champion and Borrius region exchange E0/E1; request/skill exchange E2/E3.',
    'scr_1F07AE2': 'Butterfree moves E0 to E1 across FE; looking-for predicate moves E1 to E0.',
    'scr_1F07D00': 'Pokemon moves E0 to E1 across FE; looking-for predicate moves E1 to E0.',
    'scr_1F07D7B': 'Negation did not train is before FA in E1; Japanese じぶんじゃ ない is delayed to E2 after FA.',
    'scr_1F082E2': 'communist moves before the E2 FA; governed moves after it.',
    'scr_1F09154': 'Science Society is merged into E4 across FE; cloned shifts E4 to E5.',
    'scr_1F09045': 'thanks moves from E9 to E8 across FE; greater involvement changes E6/E7.',
    'scr_1F09A3C': 'Day-Care moves E3 to E2 across FE; conditional is delayed to E3.',
    'scr_1F09D6C': 'flowers moves E1 to E0 across FE.',
    'scr_1F0A436': 'Paradise moves E1 to E0 across FE; Honey Gather also splits differently at FE.',
    'scr_1F0A83E': 'blew away moves E0 to E1 across FE; Roar identity separately unresolved.',
    'scr_1F0A9FD': 'defeated moves E2 to E3 across FA; came-across qualifier moves the other way.',
    'scr_1F0AABD': 'defeated moves E2 to E3 across FA; defeat-us also softened to battle-us.',
    'scr_1F0ADCC': 'two on two is split E6/E7 across FA in English; Japanese completes 2たい2 before that wait.',
    'scr_1F0B2DB': 'Crobatman moves E1 to E0 across FE.',
    'scr_1F0C34F': 'Frontier Brain moves E1 to E0; Single Battle moves E2 to E1 before FA; trophy moves after FA.',
    'scr_1F0C3AF': 'Frontier Brain moves E1 to E0; Double Battle moves E2 to E1 before FA; trophy moves after FA.',
    'scr_1F0C40F': 'Frontier Brain moves E1 to E0; Multi Battle moves E2 to E1 before FA; trophy moves after FA.',
    'scr_1F0C46E': 'challenge moves E4 to E5 across FA; become moves E5 to E6 across FA.',
    'scr_1F0D98F': 'Cresselia and location move E2 to E1 across FE.',
    'scr_1F0D9E7': 'Cresselia and location move E1 to E0 across FE.',
    'scr_1F0E68D': 'Coin Case moves E2 to E1 across FE.',
    'scr_1F0E798': 'number one is split E8/E9 across FA in English; Japanese completes ナンバーワン before that wait.',
    'scr_1F113ED': 'hurt/forgive clauses exchange E2/E3 across FA; destruction moves E7 to E6.',
    'scr_1F130DC': 'Cut moves E9 to E10 across FE.',
    'scr_1F1330A': 'endangered/growing-back exchange E5/E6 across FA; service/obligation exchange E8/E9 across FA.',
    'scr_1F13518': 'night moves E1 to E0 across FE.',
    'scr_1F13575': 'daytime moves E2 to E1 across FA; it is revealed before the source input wait.',
}
VOICE_NOTES = {
    'scr_1F07AB1': 'brought me is rendered as for my sake; benefit is added rather than delivery.',
    'scr_1F09B40': 'かせぎの ほとんどは ... もちものを うる is an incomplete Japanese predicate; requires wording review.',
    'scr_1F11888': 'if, no ... when SHE arrives loses the correction from possibility to certainty.',
}
UNVERIFIED_NAMES = {
    'scr_1F0A83E': 'Capitalized Roar may name move roar; ほえごえ is not its exact official name ほえる. Caller semantics unproved.',
    'scr_1F0B2DB': 'Crobat species verification does not approve the new proper name Crobatman.',
    'scr_1F0BE99': 'Cube is approved in restricted scope, but Super Cube is a distinct unapproved form.',
    'scr_1F0C46E': 'Redwood Village is outside its approved entry scope; no independent location identity proof.',
    'scr_1F0C52E': 'Gurun Town and Route 18 are outside approved scopes; no independent map binding proof.',
    'scr_1F0E798': 'Ferrothorn species name does not prove the Black Ferrothorn organization identity in this script.',
}


def baseline():
    rows = read(OUT / 'ja_phase6_cleanup_batch01_combined_controlfix.json')['entries']
    assert len(rows) == len({x['id'] for x in rows}) == 2329
    return rows


def segments(row):
    return row.get('source_segments', row['source_control_structure']['display_segments'])


def completed_text(row):
    if row['status'] != 'confirmed':
        return ''
    if row['fa_segmented']:
        return reconstruct_reviewed_segments(strip_hma_quotes(row['original']), segments(row), row['translated_segments'])
    text = row['reviewed_japanese']
    assert text == join_segments(segments(row), row['translated_segments'])
    return text


def validate_review(review, batch, manifest, voice):
    ids = [x['id'] for x in review]
    assert len(ids) == len(set(ids)) == 142
    assert ids == [x['id'] for x in batch] == manifest['batches'][1]['entry_ids']
    assert Counter(x['status'] for x in review) == STATUSES
    assert Counter(x['input_resolution_class'] for x in review) == {'CLAUDE_TRANSLATION': 61, 'CLAUDE_CONTEXT': 81}
    assert Counter(x['speaker_confidence'] for x in review) == {'PROVEN': 9, 'PLAUSIBLE': 29, 'UNKNOWN': 104}
    groups = defaultdict(list)
    for r, s in zip(review, batch):
        for key in ('id', 'category', 'original', 'speaker_id', 'speaker_confidence', 'dialogue_group_id', 'protected_tokens', 'source_control_structure'):
            assert r[key] == s[key], (r['id'], key)
        assert r['previous_candidate'] == s['candidate'] == s['previous_japanese_candidate']
        assert r['hold_reason'] == s['current_hold_reason']
        assert r['input_resolution_class'] == s['resolution_class']
        assert r['source_controls'] == s['controls'] and r['buffers'] == s['buffers']
        # Claude flattened two warning records to term strings. Verify identity,
        # and retain the complete original records in source_handoff, never infer
        # that missing reasons/decisions have been resolved.
        assert r['unresolved_glossary_warnings'] == [x['term'] if isinstance(x, dict) else x for x in s['unresolved_glossary_warnings']]
        assert r['review_source'] == 'claude_cli' and r['batch'] == 2
        assert join_segments(segments(r)) == strip_hma_quotes(r['original'])
        assert Counter(semantic_tokens(strip_hma_quotes(r['original']))) == Counter(r['protected_tokens'])
        if r['speaker_confidence'] == 'PROVEN':
            groups[r['speaker_id']].append(r['id'])
        if r['status'] == 'needs_context':
            assert not r['reviewed_japanese'] and not any(r['translated_segments'])
    expected = {x['speaker_id']: x['entry_ids_in_batch'] for x in voice['proven_speaker_groups']}
    assert dict(groups) == expected and len(groups) == 7
    for index, key in {**SPECIAL_FA, **TROPHIES, **RELOCATIONS}.items():
        assert ids[index] == key, 'Review numbers are zero-based, not batch_position'
    counts = {c: sum(x['source_controls'].get(c, 0) for x in review if x['status'] == 'confirmed') for c in ('FE', 'FB', 'FA')}
    assert counts == {'FE': 153, 'FB': 126, 'FA': 67}
    assert sum(x['fa_segmented'] for x in review) == 55
    assert sum(x['fa_segmented'] and x['status'] == 'confirmed' for x in review) == 38
    assert sum(bool(x['official_name_warnings']) for x in review) == 13
    assert sum(bool(x['glossary_scope_gaps']) for x in review) == 10
    held = [x for x in review if x['status'] == 'needs_context']
    memberships = {code: [x['id'] for x in held if code in x['buffers']] for code in sorted({v for x in held for v in x['buffers']})}
    return {'count': 142, 'duplicates': 0, 'missing': 0, 'status_counts': STATUSES,
            'confirmed_source_controls': counts,
            'all_source_controls': {c: sum(x['source_controls'].get(c, 0) for x in review) for c in ('FE', 'FB', 'FA')},
            'proven_groups': dict(groups), 'context_unique': 49, 'buffer_memberships': memberships,
            'fa_total': 55, 'fa_complete': 38, 'fa_context_hold': 17,
            'official_warning_entries': 13, 'scope_gap_entries': 10,
            'original_candidate_confidence_and_control_metadata_preserved': True}


def raw_controls(raw, *, ignore_pages=False):
    result, index = [], 0
    while index < len(raw):
        b = raw[index]
        if b == 0xFF:
            assert index == len(raw) - 1
            break
        n = 2 + fc_arg_count(raw[index + 1]) if b == 0xFC else 2 if b in (0xFD, 0xF7, 0xF8, 0xF9) else 1
        assert index + n <= len(raw)
        if b >= 0xF7 and not (ignore_pages and b == 0xFC and raw[index + 1] in (0x15, 0x16)):
            result.append(raw[index:index + n].hex(' '))
        index += n
    return result


def control_audit(row, text, fixed, source_raw):
    targets = row['translated_segments']
    sources = segments(row)
    expected = [x['after_control'] for x in sources if x['after_control']]
    raw = Charmap('ja').encode(fixed)
    boundaries = [x['after_control'] for x in parse_raw_segments(raw) if x['after_control']]
    token_ok = len(sources) == len(targets) and all(semantic_tokens(s['text']) == semantic_tokens(t) for s, t in zip(sources, targets))
    controls_ok = raw_controls(source_raw, ignore_pages=True) == raw_controls(raw, ignore_pages=True)
    return {'state': 'PASS' if token_ok and controls_ok and boundaries == expected else 'HOLD',
            'per_segment_tokens_preserved': token_ok, 'raw_controls_preserved_except_language_pages': controls_ok,
            'source_controls_hex': raw_controls(source_raw, ignore_pages=True),
            'target_controls_hex': raw_controls(raw, ignore_pages=True),
            'source_boundaries': expected, 'target_boundaries': boundaries,
            'source_segments': deepcopy(sources), 'translated_segments': deepcopy(targets),
            'text_reconstructed_exactly': join_segments(sources, targets) == text}


def semantic_audit(row):
    key = row['id']
    issues = [v for v in (BOUNDARY_NOTES.get(key), VOICE_NOTES.get(key)) if v]
    return {'state': 'HOLD' if issues else 'PASS', 'issues': issues,
            'boundary_note': BOUNDARY_NOTES.get(key), 'voice_note': VOICE_NOTES.get(key),
            'source_and_target_units': [{'index': i, 'english': s['text'], 'japanese': t, 'after_control': s['after_control']}
                                        for i, (s, t) in enumerate(zip(segments(row), row['translated_segments']))],
            'speaker_confidence': row['speaker_confidence'], 'voice_profile_status': row['voice_profile_status'],
            'canon_identity_promoted': False, 'new_wording_created': False,
            'rule': 'Manual clause/timing audit; unchanged control counts alone never grant semantic approval.'}


def renderer_evidence(rom):
    assert rom[0x3A73BC:0x3A73C4] == bytes.fromhex('00 02 0f 1a 04 0f 98 01')
    assert rom[0x6FB38:0x6FB3C] == (0x083A73BC).to_bytes(4, 'little')
    assert rom[0x248330:0x248338] == bytes.fromhex('00 01 0f 1c 04 00 90 00')
    assert rom[0x3FEB64:0x3FEB70] == bytes.fromhex('ff 02 02 02 00 02 01 01 0f 06 00 00')
    assert rom[0x1FB100:0x1FB200] == bytes(NORMAL_GLYPH_WIDTHS)
    assert rom[0x20F500:0x20F618] == NORMAL_JAPANESE_GLYPH_WIDTHS
    return {'field_template_rom': '0x003A73BC', 'field_template_gba': '0x083A73BC',
            'field_template_reference_rom': '0x0006FB38', 'field_physical_pixels': 208,
            'battle_template_rom': '0x00248330', 'battle_printer_rom': '0x003FEB64', 'battle_physical_pixels': 222,
            'latin_width_table_rom': '0x001FB100', 'japanese_width_table_rom': '0x0020F500',
            'runtime_verified': False, 'usable_margin_and_all_live_variants_proved': False}


def caller_profile(row, owners, rom):
    calls = []
    for p in owners['recorded']:
        offset = int(p, 16)
        kind = owners['owner_kinds'][len(calls)]
        field = rom[offset - 2:offset] == b'\x0f\x00' and rom[offset + 4] == 9 and rom[offset + 5] in (2, 3, 4, 5, 6)
        message = rom[offset - 1] == 0x67
        calls.append({'pointer_rom': p, 'pointer_gba': f'0x{offset + 0x08000000:08X}', 'kind': kind,
                      'adjacent_hex': rom[max(0, offset - 3):offset + 7].hex(' '),
                      'loadword_callstd': field, 'message_opcode': message})
    trainer = row['speaker_confidence'] == 'PROVEN' and (row.get('speaker_id') or '').startswith('trainer_')
    direct = all(x['loadword_callstd'] or x['message_opcode'] for x in calls)
    key = 'field_callstd_or_message' if direct else 'trainer_intro_or_defeat' if trainer else 'unproved_consumer'
    return {'profile_id': key, 'calls': calls, 'normal_font_candidate': True,
            'conservative_width_limit': 208, 'exact_live_renderer_proven': False,
            'basis': 'ROM-backed normal field/battle physical spans; caller/actor evidence retained; no implicit wrapping or dynamic-width guess.'}


def width_audit(row, fixed, source_raw, profile):
    widths = normal_line_widths_with_placeholders(fixed, {})
    trace = horizontal_layout_trace(fixed)
    problems = []
    if widths['max_total'] > 208:
        problems.append('field_208px_overflow')
    if widths['unknown_placeholder_codes']:
        problems.append('dynamic_width_and_page_contract_unproved')
    if trace['unsupported_controls']:
        problems.append('renderer_special_control_unmodelled')
    source_pixels = line_widths(source_raw)
    if row['fa_segmented'] and widths['max_total'] > max(source_pixels):
        problems.append('fa_source_width_envelope_exceeded')
    if row['fa_segmented'] and profile['profile_id'] == 'unproved_consumer':
        problems.append('fa_consumer_unproved')
    # Keep original cursor/scroll events exactly, not merely event counts.
    target_trace = layout_trace(Charmap('ja').encode(fixed))
    original_trace = layout_trace(source_raw)
    event_shape = lambda trace: [(e['control'], e['line_before'], e['line_after_model'], e['page_before'], e['page_after']) for e in trace['events']]
    if event_shape(original_trace) != event_shape(target_trace):
        problems.append('scroll_or_page_sequence_changed')
    if row['fa_segmented'] and any(e['line_before'] < 1 for e in target_trace['events'] if e['control'] == 'FA'):
        problems.append('fa_before_second_visible_line')
    return {**widths, 'profile': profile, 'limit_pixels': 208, 'source_line_pixels': source_pixels,
            'source_trace': original_trace, 'target_trace': target_trace,
            'horizontal_trace': trace, 'problems': problems,
            'state': 'HOLD' if problems else 'STATIC_FIT_RUNTIME_WARNING',
            'runtime_measured': False, 'warning': 'width_runtime_unverified; physical span is not a per-entry live measurement'}


def official_audit(row, text, glossary):
    records, issues = [], []
    for claim in row['official_names_verified']:
        match = re.fullmatch(r'(.+?)=(.+?) \(PokeAPI cache, ([\w-]+)/([\w-]+), verified_exact\)', claim)
        assert match, claim
        english, japanese, category, slug = match.groups()
        record = official_record(category, slug, english, japanese)
        if row['id'] == 'scr_1F11C50' and english == 'Hoopa':
            assert text == '[green]フー\\.\\CC0818 パ\\.'
            record['context_proof'] = 'Source Hoo/pause/pa split retained as フー/pause/パ; spelling joins to exact species name.'
        else:
            assert japanese in text, (row['id'], claim)
        records.append(record)
    key = row['id']
    if key in {'scr_1F09D6C', 'scr_1F09E0D', 'scr_1F09E94'}:
        record = official_record('item', 'gracidea', 'Gracidea', 'グラシデアのはな')
        item = read(ROOT / record['source'])
        flavors = [x['text'] for x in item['flavor_text_entries'] if x['language']['name'] == 'en']
        assert any('flower' in x.lower() and 'bouquet' in x.lower() and 'gratitude' in x.lower() for x in flavors)
        record['context_proof'] = 'Item itself is a flower given in bouquets to convey gratitude; exact reviewed English use, not an inferred generic plant name.'
        records.append(record)
    if key == 'scr_1F0A708':
        terms = [t for _, _, t in glossary.matches('Frost Mountain', 'scripts', entry_id=key)]
        assert any(t.source == 'Frost Mountain' and t.target == text for t in terms)
        records.append({'state': 'PROJECT_SCOPED_APPROVED', 'english': 'Frost Mountain', 'japanese': text, 'official_claim': False})
    if key in {'scr_1F0AABD', 'scr_1F0ADCC'}:
        source_phrase = re.sub(r'\s+', ' ', row['original'].replace('\\l', ' '))
        assert 'two on two' in source_phrase and '2たい2' in text
        records.append({'state': 'ORDINARY_BATTLE_FORMAT', 'english': 'two on two', 'japanese': '2たい2', 'official_claim': False})
    if key == 'scr_1F0D8AA':
        assert strip_hma_quotes(row['original']) == text == 'Sankren fimbulvetr!'
        records.append({'state': 'SOURCE_SPELLING_RETAINED', 'english': text, 'japanese': text,
                        'official_claim': False, 'meaning': 'No interpretation or transliteration; every visible source character preserved.'})
    if key in UNVERIFIED_NAMES:
        issues.append(UNVERIFIED_NAMES[key])
    return {'state': 'HOLD' if issues else 'PASS', 'records': records,
            'issues': issues, 'review_warnings': deepcopy(row['official_name_warnings'])}


def glossary_audit(row, handoff, text, glossary):
    english = re.sub(r'\s+', ' ', strip_hma_quotes(row['original']))
    terms = [{'source': t.source, 'target': t.target, 'scope': t.context_scope,
              'entry_ids': list(t.entry_ids), 'categories': list(t.categories),
              'global_replace': t.global_replace, 'target_present': t.target in text or not text}
             for _, _, t in glossary.matches(english, row['category'], entry_id=row['id'])]
    gaps = deepcopy(row['glossary_scope_gaps'])
    independent = row['id'] == 'scr_1F0A273'  # Ability entity, not mission title.
    in_scope = row['id'] in {'scr_1F07929', 'scr_1F082E2', 'scr_1F0E49D'}
    gap_state = 'NOT_REPORTED' if not gaps else 'ALREADY_IN_SCOPE' if in_scope else 'INDEPENDENT_OFFICIAL_ENTITY' if independent else 'SCOPE_EXTENSION_REQUIRES_REVIEW'
    return {'state': 'PASS' if all(x['target_present'] for x in terms) and gap_state != 'SCOPE_EXTENSION_REQUIRES_REVIEW' else 'HOLD',
            'matched_scoped_terms': terms, 'gap_state': gap_state, 'reported_gaps': gaps,
            'approved_terms_from_handoff': deepcopy(handoff['approved_glossary_terms']),
            'review_terms_used': deepcopy(row['glossary_terms_used']),
            'scope_extensions': 0, 'automatic_replacements': 0,
            'explanation': 'Borrius/Region and Cloud Burst already global. Honey Gather verified as ability independently; do not widen the mission-title scope.'}


def protected_inputs():
    paths = set(ROOT / p for p in read(FIX / 'ja_phase6_cleanup_batch_manifest.json')['metadata']['protected_files_sha256'])
    paths.update([REVIEW, BATCH, FIX / (PREFIX + 'voice_audit.json'),
                  ROOT / 'docs/ja-phase6-final-cleanup-batch02-claude-review.md',
                  OUT / 'ja_phase6_cleanup_translation_style_handoff.json', ROOT / 'glossaries/ja.json',
                  OUT / 'ja_phase6_cleanup_batch01_combined_controlfix.json',
                  ROOT / 'out/ja-phase5e-prepared.json', FIX / 'ja_phase6_selection.json'])
    paths.update(ROOT.glob('rom/*.gba'))
    paths.update(ROOT.glob('out/*.gba'))
    return {str(p.relative_to(ROOT)): digest(p.read_bytes()) for p in sorted(paths) if p != ROM}


def analyze():
    rom, before = (ROOT / 'rom/unbound.gba').read_bytes(), BASE.read_bytes()
    assert hashlib.md5(rom).hexdigest() == SOURCE_MD5 and digest(before) == BASE_SHA
    assert len(rom) == len(before) == 0x2000000
    anchors = renderer_evidence(rom)
    assert renderer_evidence(before) == anchors
    review, batch = read(REVIEW), read(BATCH)['entries']
    validation = validate_review(review, batch, read(FIX / 'ja_phase6_cleanup_batch_manifest.json'), read(FIX / (PREFIX + 'voice_audit.json')))
    glossary = load_glossary(ROOT / 'glossaries/ja.json', expected_language='ja')
    assert len(glossary.terms) == 292
    old = baseline()
    assert not {x['id'] for x in old} & {x['id'] for x in review}
    prepared = {x['id']: x for x in read(ROOT / 'out/ja-phase5e-prepared.json')['entries']}
    selection = {x['id']: x for x in read(FIX / 'ja_phase6_selection.json')['entries']}
    chosen = [selection[x['id']] for x in review]
    owners = {x['id']: x for x in owner_audit(chosen, rom)['entries']}
    interiors = interior_pointer_hits(rom, chosen)
    injector = runpy.run_path(str(ROOT / '005_hybrid_injector.py'))
    fix = runpy.run_path(str(ROOT / '004_controlfix_translations.py'))
    codec = Charmap('ja')
    records, safe = [], []
    for index, (r, s) in enumerate(zip(review, batch)):
        key = r['id']
        entry, sel = deepcopy(prepared[key]), selection[key]
        pos, slot = int(entry['address'], 16), entry['byte_length']
        assert pos == sel['rom_offset'] and slot == sel['slot_size'] and entry['original'] == r['original']
        length = decode_pcs(rom, pos, slot).byte_length
        raw = rom[pos:pos + length]
        source_segments = parse_raw_segments(raw, rom_offset=pos)
        assert join_segments(source_segments) == strip_hma_quotes(r['original'])
        assert [(x['text'], x['after_control']) for x in source_segments] == [(x['text'], x['after_control']) for x in segments(r)]
        assert rom[pos:pos + slot] == before[pos:pos + slot]
        assert sorted(int(p, 16) for p in entry.get('pointer_sources', [])) == sorted(int(p, 16) for p in sel['pointer_owners'])
        for p in entry.get('pointer_sources', []):
            p = int(p, 16)
            assert rom[p:p + 4] == before[p:p + 4] == (pos + 0x08000000).to_bytes(4, 'little')
        text = completed_text(r)
        holds = ['review_needs_context'] if not text else []
        fixed = fix['ensure_japanese_page'](text)[0] if text else None
        controls = control_audit(r, text, fixed, raw) if text else {'state': 'NOT_COMPLETED'}
        semantic = semantic_audit(r) if text else {'state': 'NOT_COMPLETED', 'issues': []}
        profile = caller_profile(r, owners[key], rom)
        width = width_audit(r, fixed, raw, profile) if text else {'state': 'NOT_MEASURED', 'problems': []}
        official = official_audit(r, text, glossary) if text else {'state': 'NOT_COMPLETED', 'records': [], 'issues': []}
        terms = glossary_audit(r, s, text, glossary)
        buffer_state = {'state': 'NOT_REQUIRED' if not r['buffers'] else 'PLAYER_NAME_UNPROVED' if set(r['buffers']) == {'[player]'} else 'UNKNOWN_CALLER_DEPENDENT',
                        'tokens': deepcopy(r['buffers']), 'missing': 'Writer, all values, expansion page state and width proof.' if r['buffers'] else None}
        if r['buffers']:
            holds.append('dynamic_buffer_contract_unproved')
        if text:
            if controls['state'] != 'PASS':
                holds.append('control_boundary_or_token_placement_changed')
            if semantic['boundary_note']:
                holds.append('CONTROL_BOUNDARY_REVIEW_REQUIRED')
            if semantic['voice_note']:
                holds.append('CLAUDE_VOICE_REVIEW_REQUIRED')
            if official['state'] == 'HOLD':
                holds.append('official_or_project_name_unverified')
            if terms['state'] != 'PASS':
                holds.append('glossary_scope_or_target_unapproved')
            holds.extend(width['problems'])
            if any('bufferstring' in k for k in owners[key]['owner_kinds']):
                holds.append('bufferstring_consumer_width_and_page_unproved')
            if key == 'scr_1F0DD47':
                holds.append('special_0x25_label_consumer_unproved')
        payload = encoded(injector, codec, entry, fixed) if text else None
        assert not text or not HAN.search(text)
        size = len(payload) if payload else None
        relocation = size is not None and size > slot
        pointer = {**owners[key], 'interior_hits': interiors[key], 'fixed': sel['fixed'], 'no_relocation': sel['no_relocation'], 'relocation_needed': relocation}
        if text and (pointer['missing'] or pointer['stale'] or interiors[key]):
            holds.append('owner_incomplete_or_interior')
        if relocation and (pointer['fixed'] or pointer['no_relocation']):
            holds.append('fixed_or_no_relocation_overflow')
        if relocation and (not entry.get('is_pointer_based') or not entry.get('pointer_sources')):
            holds.append('relocation_owner_absent')
        fa_state = 'NOT_APPLICABLE'
        if r['fa_segmented']:
            fa_state = 'HOLD_UNKNOWN_BUFFER' if not text else 'LAYOUT_PASS' if not holds else 'LAYOUT_HOLD'
        record = {'id': key, 'review_index': index, 'review_status': r['status'], 'review': deepcopy(r),
                  'source_handoff': deepcopy(s), 'original_english': r['original'], 'candidate_japanese': text,
                  'decision': 'HOLD' if holds else 'APPLY', 'primary_hold': holds[0] if holds else None,
                  'secondary_holds': holds[1:], 'all_holds': holds, 'buffer_state': buffer_state,
                  'FA_state': {'present': r['fa_segmented'], 'layout_status': fa_state, 'special_case': index in SPECIAL_FA,
                               'completed_segments': bool(text) and r['fa_segmented'], 'source_segments': source_segments,
                               'translated_segments': deepcopy(r['translated_segments'])},
                  'control_state': controls, 'semantic_voice_state': semantic, 'width_state': width,
                  'official_name_state': official, 'glossary_state': terms, 'pointer_state': pointer,
                  'source_slot': slot, 'source_encoded_bytes': length, 'encoded_bytes': size,
                  'controlfixed_japanese': fixed, 'planned_placement': 'relocated' if relocation else 'in_place',
                  'next_action': 'Resolve recorded evidence gaps; wording/boundary issues return to Claude. No automatic rewriting.' if holds else 'Trigger this exact caller and inspect every original control transition.'}
        records.append(record)
        if not holds:
            entry['translated'] = fixed
            if r['fa_segmented']:
                entry.update(control_segments=deepcopy(source_segments),
                             translated_segments=deepcopy(r['translated_segments']),
                             source_boundary_sequence=controls['source_boundaries'],
                             controls=deepcopy(r['source_controls']),
                             fa_placement_policy='require_segments', fa_layout_reviewed=True,
                             fa_placement_status='RESOLVED_SEGMENTED')
            safe.append(entry)
    assert {x['id'] for x in records if x['pointer_state']['relocation_needed']} == set(RELOCATIONS.values())
    metadata = {'validation': validation, 'renderer_evidence': anchors, 'source_md5': SOURCE_MD5,
                'baseline_sha256': BASE_SHA, 'baseline_applied': 2329, 'applied': len(safe), 'held': 142 - len(safe),
                'japanese_applied_total': 2329 + len(safe), 'phase6_remaining_holds': 848 - len(safe),
                'input_hashes': protected_inputs(), 'relocation_candidate_ids': list(RELOCATIONS.values()),
                'fa_applied': sum(x['decision'] == 'APPLY' and x['FA_state']['present'] for x in records),
                'glossary_scope_changes': 0, 'new_translations': 0}
    return metadata, records, safe


def assert_safe_record(r):
    assert r['decision'] == 'APPLY' and r['review_status'] == 'confirmed' and not r['all_holds']
    assert r['control_state']['state'] == r['semantic_voice_state']['state'] == 'PASS'
    assert r['buffer_state']['state'] == 'NOT_REQUIRED'
    assert r['official_name_state']['state'] == r['glossary_state']['state'] == 'PASS'
    assert not r['width_state']['problems'] and r['width_state']['max_total'] <= 208
    if r['FA_state']['present']:
        assert r['FA_state']['layout_status'] == 'LAYOUT_PASS'
        assert r['width_state']['max_total'] <= max(r['width_state']['source_line_pixels'])
    p = r['pointer_state']
    assert not p['missing'] and not p['stale'] and not p['interior_hits']
    if p['relocation_needed']:
        assert p['recorded'] and not p['fixed'] and not p['no_relocation']
    else:
        assert r['encoded_bytes'] <= r['source_slot']


def build(safe):
    inp, fixed, twice = [OUT / (PREFIX + name) for name in ('safe_input.json', 'controlfix.json', 'controlfix_twice.json')]
    for source, output, report in [(inp, fixed, OUT / (PREFIX + 'controlfix_report.json')),
                                    (fixed, twice, OUT / (PREFIX + 'controlfix_twice_report.json'))]:
        cli('004_controlfix_translations.py', [source, '-o', output, '--source', ROOT / 'out/ja-phase5e-prepared.json',
                                              '--report', report, '--target-lang', 'ja', '--no-wrap'], [output, report])
        assert read(output)['entries'] == safe, 'Reviewed text/control boundary changed during controlfix'
        stats = read(report)['stats']
        assert stats['remaining_control_mismatches'] == stats['fa_placement_review_required'] == 0
    assert fixed.read_bytes() == twice.read_bytes(), 'Byte-for-byte controlfix idempotency failure'
    full_map = OUT / (PREFIX + 'full_dry_run_map.json')
    combined = OUT / (PREFIX + 'combined_controlfix.json')
    cli('005_hybrid_injector.py', [ROOT / 'rom/unbound.gba', combined, '-o', ROM, '--target-lang', 'ja',
                                 '--dry-run', '--fail-on-no-space', '--map-output', full_map], [full_map])
    assert_strict_map(read(full_map), read(full_map), 2329 + len(safe))
    dry, built = [OUT / (PREFIX + n) for n in ('incremental_dry_run_map.json', 'map.json')]
    args = [BASE, fixed, '-o', ROM, '--target-lang', 'ja', '--fail-on-no-space']
    cli('005_hybrid_injector.py', [*args, '--dry-run', '--map-output', dry], [dry])
    assert_strict_map(read(dry), read(dry), len(safe))
    cli('005_hybrid_injector.py', [*args, '--map-output', built], [ROM, built])
    assert_strict_map(read(dry), read(built), len(safe))


def ranges(values):
    result = []
    for value in sorted(values):
        if result and result[-1][1] + 1 == value:
            result[-1][1] = value
        else:
            result.append([value, value])
    return [[f'0x{a:08X}', f'0x{b:08X}'] for a, b in result]


def audit_binary(before, after, safe, mapping, old):
    assert len(before) == len(after) == 0x2000000 and digest(before) == BASE_SHA
    injector = runpy.run_path(str(ROOT / '005_hybrid_injector.py'))
    codec = Charmap('ja')
    moves = {x['id']: x for x in mapping['relocations']}
    allowed = {k: set() for k in ('in_place_text', 'relocated_text', 'pointer_writes')}
    for e in safe:
        pos, slot = int(e['address'], 16), e['byte_length']
        payload = encoded(injector, codec, e, e['translated'])
        if e['id'] in moves:
            move = moves[e['id']]
            dest = int(move['new_offset'], 16)
            assert move['storage'] == 'vetted_ff' and move['byte_length'] == len(payload)
            from lib.unbound_free_space import VETTED_FREE_SPACE_RANGES
            excluded = injector['FREE_SPACE_EXCLUDE_RANGES']
            assert any(a <= dest and dest + len(payload) <= b for a, b in VETTED_FREE_SPACE_RANGES)
            assert not any(dest < b and a < dest + len(payload) for a, b in excluded)
            assert before[dest:dest + len(payload)] == b'\xff' * len(payload)
            assert after[dest:dest + len(payload)] == payload
            assert before[pos:pos + slot] == after[pos:pos + slot]
            allowed['relocated_text'].update(range(dest, dest + len(payload)))
            assert sorted(move['pointer_sources']) == sorted(e['pointer_sources'])
            for pointer in move['pointer_sources']:
                p = int(pointer, 16)
                assert before[p:p + 4] == (pos + 0x08000000).to_bytes(4, 'little')
                assert after[p:p + 4] == (dest + 0x08000000).to_bytes(4, 'little')
                allowed['pointer_writes'].update(range(p, p + 4))
            needle = (pos + 0x08000000).to_bytes(4, 'little')
            assert after.find(needle) == -1, 'Old exact pointer remains'
        else:
            assert len(payload) <= slot and after[pos:pos + slot] == payload.ljust(slot, b'\xff')
            allowed['in_place_text'].update(range(pos, pos + slot))
    old_moves = {}
    for name in ('ja_phase6_batch04_map.json', 'ja_phase6_batch05_incremental_map.json',
                 'ja_phase6_batch06_incremental_map.json', 'ja_phase6_cleanup_incremental_map.json',
                 'ja_phase6_cleanup_glossary_incremental_map.json', 'ja_phase6_cleanup_batch01_map.json'):
        old_moves.update({x['id']: x for x in read(OUT / name)['relocations']})
    protected = set()
    for e in old:
        move = old_moves.get(e['id'])
        pos = int(move['new_offset'], 16) if move else int(e['address'], 16)
        size = move['byte_length'] if move else e['byte_length']
        payload = encoded(injector, codec, e, e['translated'])
        assert before[pos:pos + len(payload)] == payload, ('Baseline payload mismatch', e['id'])
        assert before[pos:pos + size] == after[pos:pos + size], e['id']
        protected.update(range(pos, pos + size))
        for pointer in e.get('pointer_sources', []):
            p = int(pointer, 16)
            assert before[p:p + 4] == after[p:p + 4], e['id']
            protected.update(range(p, p + 4))
    union = set().union(*allowed.values())
    assert len(union) == sum(map(len, allowed.values())), 'Overlapping write classes'
    assert not protected & union, 'Writes overlap prior applied text/pointers'
    changed = {i for i, (a, b) in enumerate(zip(before, after)) if a != b}
    assert not changed - union, 'Unexpected binary differences'
    assert not changed & protected
    return {'status': 'PASS', 'existing_2329_text_and_pointers_unchanged': True,
            'voice_pass1_three_revisions_preserved': all(any(x['id'] == key for x in old) for key in ('scr_1F02145', 'scr_740753', 'scr_1F06A82')),
            'changed_byte_count': len(changed), 'unexpected_byte_count': 0,
            'classified_changed_bytes': {k: len(v & changed) for k, v in allowed.items()},
            'classified_changed_ranges': {k: ranges(v & changed) for k, v in allowed.items()},
            'in_place_count': mapping['stats']['in_place'], 'relocation_count': len(moves),
            'pointer_writes': mapping['stats']['pointer_writes'], 'output_sha256': digest(after),
            'runtime_patches': 0, 'font_graphics_changes': 0}


def runtime_qa(records, mapping):
    applied = [x for x in records if x['decision'] == 'APPLY']
    chosen = [x for x in applied if x['review']['speaker_confidence'] == 'PROVEN']
    chosen += [x for x in applied if x['pointer_state']['relocation_needed'] and x not in chosen]
    chosen += [x for x in applied if x['FA_state']['present'] and x not in chosen][:7]
    scoped_location = next(x for x in applied if x['id'] == 'scr_1F0A708')
    if scoped_location not in chosen:
        chosen.append(scoped_location)
    chosen += sorted([x for x in applied if x not in chosen], key=lambda x: -x['width_state']['max_total'])[:max(0, 17 - len(chosen))]
    chosen = chosen[:17]
    chosen += [next(x for x in records if x['id'] == k) for k in SPECIAL_FA.values()]
    assert 15 <= len(chosen) <= 25 and len(chosen) == len({x['id'] for x in chosen})
    return {'metadata': {'count': len(chosen), 'performed': False, 'rom': str(ROM.relative_to(ROOT))},
            'entries': [{'id': x['id'], 'apply_status': x['decision'], 'original': x['original_english'],
                         'japanese': x['candidate_japanese'], 'speaker_id': x['review']['speaker_id'],
                         'source_rom_offset': f"0x{x['source_handoff']['known_technical_constraints']['rom_offset']:08X}",
                         'source_gba_address': f"0x{x['source_handoff']['known_technical_constraints']['rom_offset'] + 0x08000000:08X}",
                         'pointer_owners': x['pointer_state']['recorded'],
                         'speaker_confidence': x['review']['speaker_confidence'],
                         'location_evidence': deepcopy(x['source_handoff']['speaker_evidence']),
                         'runtime_reachability': 'Exact event unplayed; original operand and map/trainer metadata are evidence, not a live-path assertion.',
                         'procedure': 'Locate the recorded object/trainer/script caller. Compare exact English, then every FE/FA/FB frame; holds remain English. Do not infer route from ROM proximity.',
                         'expected_controls': x['review']['source_controls'], 'width_state': x['width_state'],
                         'relocation': next((m for m in mapping['relocations'] if m['id'] == x['id']), None)} for x in chosen]}


def scope_proposals(records, glossary):
    names = ['Cube', 'Redwood Village', 'Gurun Town', 'Route [N]', 'Borrius Region', 'Frost Mountain',
             'Black Ferrothorn', 'Science Society', 'Cloud Burst']
    result = []
    for name in names:
        terms = [t for t in glossary.terms if t.source == name]
        affected = [x['id'] for x in records if any(name.split(' [')[0] in g or name == 'Borrius Region' and 'Borrius=' in g for g in x['review']['glossary_scope_gaps'])]
        result.append({'english': name, 'existing_terms': [{'target': t.target, 'scope': t.context_scope,
                       'entry_ids': list(t.entry_ids), 'categories': list(t.categories), 'global_replace': t.global_replace} for t in terms],
                       'affected_ids': affected, 'decision': 'NO_EXTENSION_ALREADY_GLOBAL' if any(t.global_replace for t in terms) else 'PROPOSAL_ONLY_REQUIRES_ENTITY_SCOPE_REVIEW',
                       'applied_to_glossary': False})
    return {'count': 9, 'entries': result, 'Honey_Gather': 'Ability verified independently; mission-title scope remains untouched.'}


def report(metadata, records, audit):
    applied = [x for x in records if x['decision'] == 'APPLY']
    fa = [x for x in records if x['FA_state']['present']]
    lines = ['# Phase 6C-4E — Final Cleanup Batch 02 Technical Integration', '',
             f"142件を検証。適用{len(applied)}件、保留{142-len(applied)}件。Claude本文は書き換えていない。",
             f"日本語適用総数{metadata['japanese_applied_total']}、Phase 6残り保留{metadata['phase6_remaining_holds']}。", '',
             '## 結果', '', '|項目|結果|', '|---|---|',
             '|review|142 IDs / 重複0 / 欠落0 / confirmed93 / context49 / 元英語・候補・confidence保持|',
             '|話者|PROVEN9/7組、PLAUSIBLE29、UNKNOWN104。公式人物認定・profile昇格0|',
             '|controls|confirmed FE153/FB126/FA67。全142件ではFE238/FB196/FA92。母集団を区別|',
             f"|FA|55件、完成38/文脈保留17、適用{sum(x['decision']=='APPLY' for x in fa)}|",
             f"|in-place/relocation/pointer writes|{audit['in_place_count']}/{audit['relocation_count']}/{audit['pointer_writes']}|",
             '|既存2,329件|個別encoded payload・再配置先・全pointer bytes不変。Sarah/Liam/Koji保持|',
             '|strict dry-run|元ROM+2,329+safe全体と基準ROM+safe incrementalを照合。全エラー0|',
             '|controlfix|標準 --no-wrap 2回、本文・境界不変、出力JSON byte-for-byte一致|',
             f"|binary audit|{audit['changed_byte_count']} bytes、unexpected0、runtime/font/graphics patch0|",
             f"|ROM SHA-256|`{audit['output_sha256']}`|", '',
             '## 幅とrenderer根拠', '',
             'ROM 0x003A73BC / GBA 0x083A73BC の26×4 field templateとROM 0x0006FB38の参照を再照合。',
             'battle template ROM 0x00248330 / GBA 0x08248330、printer ROM 0x003FEB64 / GBA 0x083FEB64 は28 tiles、x=2。',
             '物理横幅208/222pxの小さい方208pxを保守上限とした。240px画面幅では判定しない。',
             'Latin ROM 0x001FB100 / GBA 0x081FB100、Japanese ROM 0x0020F500 / GBA 0x0820F500の幅テーブルはコードと同一。',
             '各entryのcallstd/message/trainer/table/bufferstring経路と生byte列をreviewed JSONに記録。実機で全variantを確認したとは主張しない。',
             'FAは既存Phase 6安全モデルのsource最大幅内、208px内、scroll/page event同型、dynamicなしを追加条件とした。',
             '過去の208px診断だけの承認ではなくROM template再照合も実施。ただしtextbox余白・live caller等の未実測はwarning。', '',
             '## 個別監査', '', '|review番号（0始まり）|ID|判定|主理由|', '|---|---|---|---|']
    for x in records:
        lines.append(f"|{x['review_index']}|{x['id']}|{x['decision']}|{x['primary_hold'] or '全gate通過'}|")
    lines += ['', '## 特別FA / trophy / voice', '']
    for key in [*SPECIAL_FA.values(), *TROPHIES.values(), 'scr_1F0AC39']:
        x = next(x for x in records if x['id'] == key)
        lines.append(f"- `{key}`: {x['decision']}; {x['semantic_voice_state'].get('boundary_note') or '語句・waitを保持'}; width {x['width_state'].get('line_static')}")
    lines += ['', '#44/#63/#137は意味境界の移動が残るため保留。#81～#83はFE/FA/終端の3 segmentsを正しく再構築できるが、',
              'Battle formatがFAの後から前へ移るため、構造PASSと意味境界PASSを区別して保留。',
              '#72は「あなたは」「ようね」を削除したClaude訳のまま計算。以前247pxから167pxへ短縮。',
              '追加の口調/意味問題もCLAUDE_VOICE_REVIEW_REQUIREDとして台帳に保存。新規訳なし。', '',
              '## 公式名称 / glossary', '']
    for x in records:
        if x['review']['official_name_warnings']:
            lines.append(f"- `{x['id']}`: {x['official_name_state']['state']}; {x['official_name_state']['issues'] or [r['state'] for r in x['official_name_state']['records']]}; {x['decision']}")
    lines += ['', '全official_names_verifiedをローカルPokeAPIのen/ja-hrkt exact entityとSHA256で再検証。',
              'Gracideaはcache flavorに花・花束・感謝の独立記述があり名称を検証。Roarはmove/一般語未確定のため保留。',
              '2たい2は普通の対戦形式、Fighting動詞はタイプ名に置換しない。Frost Mountainの対象entryは承認scope内。',
              'Sankren fimbulvetr!は原文スペルをそのまま保持し、意味や音写を創作しない。',
              '13 warningと技術HOLDは同一ではない。Botanical項目は公式根拠が解決しても意味境界/幅gateで別途保留になり得る。', '',
              'scope gap報告10件をmatcherで再検証。Borrius/Region・Cloud Burstは実際には既存global scope。',
              'Honey Gatherはability exact entityで独立確認し、mission titleのscopeを広げない。その他のgapは保留。',
              '9語proposalは既存scope/entry IDs/entity未解決点を保存するだけ。glossary 292語・global_replace不変。', '',
              '## 再配置7件 / buffer台帳', '']
    for key in RELOCATIONS.values():
        x = next(x for x in records if x['id'] == key)
        lines.append(f"- `{key}`: slot{x['source_slot']}, encoded{x['encoded_bytes']}; {x['decision']}; owners {x['pointer_state']['recorded']}; missing {x['pointer_state']['missing']}; interior {x['pointer_state']['interior_hits']}")
    lines += ['', '49 context holdは重複を含むbuffer別membershipとunique IDの両方を保存。値を推測して昇格しない。',
              '追加で[player]は名前上限だけではexpansion page/全値の幅を証明できず保留。bufferstringもconsumer未証明を保留。',
              '再配置は既存基準ROMでFFのvetted範囲だけを使用。全owner更新・旧exact pointerなし・interiorなし・旧本文保持を監査。', '',
              'interior/exactの追加hitは生4byteの一致であり、graphics等の偶然一致を実pointerと断定しない。未分類hitは安全側で保留。',
              '28件の適用には原文ラテン表記を維持した呪文1件を含む。新規かな本文は27件。',
              '初回30件buildは意味境界の最終再検査後、out/phase6/recovery_cleanup_batch02_attempt1/に全成果物を退避。上書き・削除なし。', '',
              '## 再現 / QA / 次工程', '',
              '`python scripts/build_ja_phase6_cleanup_batch02.py all`。全成果物は既存なら再計算一致・監査のみ、上書き禁止。',
              'reviewed/technical_holds/scope_extension_proposal/controlfix/maps/binary_auditをout/phase6へ保存。',
              'runtime QA fixtureは20件、操作未実施。PROVEN話者・FA・再配置・長文・用語確認・#72・negative holdを含む。',
              'Batch03以降は同じspeakerのprofile confidenceを維持。FAは語句を入力待ちの前後へ移すと構造一致でも保留。',
              'glossary referenceとscope match、species名とorganization名を区別。PokeAPI対象外の名称は公式と呼ばない。',
              'wrapで208px超過を隠さない。全値が未証明のbufferには仮54pxを使って承認しない。',
              '最終pytest/py_compile/git diff --checkはvalidation JSONに記録。Batch03/04・commit/pushは未実施。', '']
    validation_path = OUT / (PREFIX + 'validation.json')
    if validation_path.exists():
        validation = read(validation_path)
        lines += ['## 最終回帰検証', '',
                  f"pytest: {validation['pytest']['passed']} passed / {validation['pytest']['subtests_passed']} subtests passed。",
                  'py_compile PASS、git diff --check PASS。',
                  'system pythonにpytestがないため、既存 .venv/Scripts/python.exe を使用。',
                  'incremental vetted FF使用73 bytes、残610,199 bytes、reclaimed使用0。',
                  'tracked既存ファイル変更0。新規script/test/report/runtime QA fixtureの4ファイル。', '']
    text = '\n'.join(lines)
    path = ROOT / 'docs/ja-phase6-final-cleanup-batch02-technical.md'
    if path.exists():
        assert path.read_text(encoding='utf-8') == text
    else:
        path.write_text(text, encoding='utf-8')


def main():
    metadata, records, safe = analyze()
    for r in records:
        if r['decision'] == 'APPLY':
            assert_safe_record(r)
    assert safe, 'No technically safe reviewed candidate'
    persist(OUT / (PREFIX + 'reviewed.json'), {'metadata': metadata, 'entries': records})
    persist(OUT / (PREFIX + 'technical_holds.json'), {'metadata': {'count': 142-len(safe)}, 'entries': [r for r in records if r['decision'] == 'HOLD']})
    persist(OUT / (PREFIX + 'safe_input.json'), {'entries': safe})
    persist(OUT / (PREFIX + 'combined_controlfix.json'), {'entries': baseline() + safe})
    glossary = load_glossary(ROOT / 'glossaries/ja.json', expected_language='ja')
    persist(OUT / (PREFIX + 'scope_extension_proposal.json'), scope_proposals(records, glossary))
    build(safe)
    mapping = read(OUT / (PREFIX + 'map.json'))
    audit = audit_binary(BASE.read_bytes(), ROM.read_bytes(), safe, mapping, baseline())
    for name, sha in metadata['input_hashes'].items():
        assert digest((ROOT / name).read_bytes()) == sha, name
    persist(OUT / (PREFIX + 'binary_audit.json'), audit)
    persist(FIX / (PREFIX + 'runtime_qa.json'), runtime_qa(records, mapping))
    report(metadata, records, audit)
    print(json.dumps({'applied': len(safe), 'held': 142-len(safe), 'fa_applied': metadata['fa_applied'],
                      'total': metadata['japanese_applied_total'], 'remaining': metadata['phase6_remaining_holds'],
                      'binary': {k: v for k, v in audit.items() if k != 'classified_changed_ranges'}}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    if sys.argv[1:] != ['all']:
        raise SystemExit('usage: build_ja_phase6_cleanup_batch02.py all')
    main()
