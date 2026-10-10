#!/usr/bin/env python3
"""Phase 6C-4C: fail-closed Batch 01 integration. Never replace an artifact.

Run ``python scripts/build_ja_phase6_cleanup_batch01.py all``. Existing JSON
must equal the recomputed result; existing ROM/maps are audited rather than
rebuilt. This script neither changes the glossary nor translates other batches.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import runpy
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lib.fa_control import join_segments, parse_raw_segments, reconstruct_reviewed_segments
from lib.pcs_text import Charmap, decode_pcs
from lib.renderer_profiles import battle_profiles, horizontal_layout_trace, normal_line_widths_with_placeholders
from lib.translation_glossary import load_glossary
from lib.translation_tokens import semantic_tokens, strip_hma_quotes
from scripts.audit_ja_phase6_batch01_fit import line_widths
from scripts.build_ja_phase6_batch02 import owner_audit
from scripts.build_ja_phase6_batch06 import interior_pointer_hits
from scripts.build_ja_phase6_cleanup_glossary import assert_strict_map
from scripts.build_ja_phase6_voice_integration import encoded

OUT = ROOT / 'out/phase6'
FIX = ROOT / 'tests/fixtures'
PREFIX = 'ja_phase6_cleanup_batch01_'
BASE = ROOT / 'out/unbound-ja-phase6-voice-pass1.gba'
ROM = ROOT / 'out/unbound-ja-phase6-cleanup-batch01.gba'
BASE_SHA = '68a6fecdbcf48a70d2e17cebc4c747a4095cfa242b8fc963e17a82722a68bc55'
SOURCE_MD5 = '9cad8e771940e7f7094d13911552cef0'
REVIEW = FIX / (PREFIX + 'claude_review.json')
BATCH = OUT / (PREFIX + 'for_claude.json')
SPECIAL = {'12', '16', '18', '19', '1B', '20', '21'}
CUBE = 'tbl_start_menu_labels_00001_A4E4E4'
WIDE = 'tbl_battle_messages_00158_3FC421'
CODE = re.compile(r'\\\\([0-9A-F]{2})')
EXPECTED_STATUSES = {'confirmed': 114, 'needs_context': 32, 'needs_technical_fit': 1}


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def digest(data):
    return hashlib.sha256(data).hexdigest()


def persist(path, value):
    """Check existence immediately before writing; existing content is immutable."""
    path = Path(path)
    if path.exists():
        assert read(path) == value, f'Existing artifact differs: {path}'
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as handle:
        handle.write(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def baseline():
    rows = read(OUT / 'ja_phase6_cleanup_glossary_combined_controlfix.json')['entries']
    by_id = {x['id']: deepcopy(x) for x in rows}
    assert len(rows) == len(by_id) == 2261
    for row in read(OUT / 'ja_phase6_voice_pass1_controlfix.json')['entries']:
        assert row['id'] in by_id
        by_id[row['id']] = deepcopy(row)
    return list(by_id.values())


def source_segments(row):
    return row.get('source_segments', row['source_control_structure']['display_segments'])


def source_boundaries(row):
    return row.get('source_boundary_sequence', row['source_control_structure']['boundary_sequence'])


def validate_review(review, batch, manifest):
    ids = [x['id'] for x in review]
    assert len(ids) == len(set(ids)) == 147
    assert ids == [x['id'] for x in batch]
    assert ids == manifest['batches'][0]['entry_ids']
    assert Counter(x['status'] for x in review) == EXPECTED_STATUSES
    for r, s in zip(review, batch):
        assert r['review_source'] == 'claude_cli' and r['batch'] == 1
        for key in ('id', 'category', 'original', 'protected_tokens', 'source_control_structure'):
            assert r[key] == s[key], (r['id'], key)
        assert r['input_resolution_class'] == s['resolution_class']
        assert r['source_controls'] == s['controls']
        assert r['buffers'] == s['buffers']
        assert r['hold_reason'] == s['current_hold_reason']
        assert Counter(semantic_tokens(strip_hma_quotes(r['original']))) == Counter(r['protected_tokens'])
        assert join_segments(source_segments(r)) == strip_hma_quotes(r['original'])
        assert [x['after_control'] for x in source_segments(r) if x['after_control']] == source_boundaries(r)
    counts = {c: sum(x['source_controls'].get(c, 0) for x in review) for c in ('FE', 'FB', 'FA')}
    assert counts == {'FE': 124, 'FB': 15, 'FA': 4}
    return {'count': 147, 'duplicates': 0, 'missing': 0, 'identity_errors': 0,
            'status_counts': EXPECTED_STATUSES, 'source_boundary_counts': counts,
            'provenance': 'claude_cli', 'glossary_metadata_retained': True}


def context_accounting(review):
    held = [x for x in review if x['status'] == 'needs_context']
    groups = {code: [x['id'] for x in held if code in x['buffers']]
              for code in ('\\\\00', '\\\\2A', '\\\\28', '[buffer1]')}
    assert [len(v) for v in groups.values()] == [28, 1, 1, 3]
    memberships = Counter(key for values in groups.values() for key in values)
    assert len(memberships) == len(held) == 32
    resolved = [x for x in review if x['context_resolution']['resolved']]
    assert len(resolved) == 56
    occurrences = Counter(e['kind'] for x in resolved for e in x['context_resolution']['evidence'])
    unique = {kind: sum(any(e['kind'] == kind for e in x['context_resolution']['evidence'])
                       for x in resolved) for kind in occurrences}
    return {'held_unique_ids': [x['id'] for x in held], 'groups': groups,
            'membership_count': sum(memberships.values()),
            'overlaps': {k: [g for g, values in groups.items() if k in values]
                         for k, n in memberships.items() if n > 1},
            'resolved_unique': 56, 'evidence_occurrences': dict(occurrences),
            'evidence_unique_entries': unique}


def buffer_evidence(rom):
    """Pin the real hook and FD dispatch, without guessing the high-bank ABI.

    Discovery is meaningful but NOT complete writer/caller proof. Case handlers
    can change names based on species, side, Frontier or link state. A current
    upstream CFRU source is not a build identity for this private Unbound ROM.
    """
    assert rom[0xD77F4:0xD7800] == bytes.fromhex('00b5024900f036f802bc0847')
    assert rom[0xD7868:0xD7870] == bytes.fromhex('004a104751d09b08')
    target = int.from_bytes(rom[0xD786C:0xD7870], 'little') & ~1
    assert target == 0x089BD050
    assert rom[0x9BD0BA:0x9BD0CC] == bytes.fromhex('fd2b01d000f09cfc049b58783d2800d99fe3')
    from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB
    disassembler = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
    meanings = {'12': 'active battler name with conditional prefix', '16': 'last-used item name',
                '18': 'attacker ability (species-sensitive helper)',
                '19': 'defender ability (species-sensitive helper)',
                '1B': 'effect battler ability (species-sensitive helper)',
                '20': 'opponent-one link record name', '21': 'opponent-two link record name'}
    records = {}
    for code in sorted(SPECIAL):
        table = 0x9BD0D0 + int(code, 16) * 2
        relative = int.from_bytes(rom[table:table + 2], 'little')
        address = 0x089BD0D0 + relative * 2
        offset = address - 0x08000000
        raw = rom[offset:offset + 38]
        records[code] = {'classification': 'UNVERIFIED', 'candidate_semantics': meanings[code],
                         'dispatch_table_offset': f'0x{table:08X}',
                         'relative_halfword': relative, 'handler_address': f'0x{address:08X}',
                         'handler_prefix_hex': raw.hex(),
                         'instructions': [f'0x{i.address:08X}: {i.mnemonic} {i.op_str}'
                                          for i in disassembler.disasm(raw, address)],
                         'verified': ['Unbound hook target', 'FD dispatch and code-specific handler'],
                         'missing': ['per-entry writer/caller and active/species/link-state contract',
                                     'full transitive helper/table and output-language/bounds proof'],
                         'next_action': 'Trace the complete handler, helper and each message writer in this ROM; do not infer compatibility from code number.'}
    return {'source_md5': SOURCE_MD5, 'hook_offset': '0x000D7868',
            'hook_target': f'0x{target:08X}', 'dispatch': 'FD, unsigned code <= 0x3D, 62 halfword cases at ROM 0x009BD0D0',
            'gnu_thumb_case_helper': '0x08964ABE', 'codes': records,
            'reference_urls': ['https://github.com/Skeli789/Complete-Fire-Red-Upgrade/blob/master/hooks',
                               'https://github.com/Skeli789/Complete-Fire-Red-Upgrade/blob/master/src/battle_strings.c'],
            'upstream_not_rom_identity': True}


def official_record(category, key, english, japanese):
    path = ROOT / '.cache/pokeapi' / category / (key + '.json')
    data = read(path)
    names = {x['language']['name']: x['name'] for x in data['names']}
    assert names['en'] == english
    assert names['ja-hrkt'] == japanese
    return {'state': 'VERIFIED_EXACT_ENTITY', 'entity_type': category, 'entity_id': data['id'],
            'english': english, 'japanese': japanese, 'source': str(path.relative_to(ROOT)),
            'sha256': digest(path.read_bytes()), 'language': 'ja-hrkt',
            'scope': 'this entry wording only; no glossary extension'}


def official_audit(row, text):
    key = row['id']
    records = []
    if key == 'tbl_battle_messages_00122_3FC048':
        records.append(official_record('move', 'curse', 'Curse', 'のろい'))
        records[-1]['context'] = 'HP sacrifice and curse applied to target; wording names the curse effect, not a global Curse replacement.'
    if key == 'scr_1EEA8A9':
        for slug, en, ja in [('qualot-berry', 'Qualot Berry', 'タポルのみ'),
                             ('pecha-berry', 'Pecha Berry', 'モモンのみ'),
                             ('fresh-water', 'Fresh Water', 'おいしいみず')]:
            records.append(official_record('item', slug, en, ja))
    if key == 'tbl_mission_objectives_00033_1F56736':
        records.append(official_record('item', 'go-goggles', 'Go-Goggles', 'ゴーゴーゴーグル'))
    if key == 'tbl_pokedex_descriptions_00013_166896A':
        records.append(official_record('pokemon-species', '75', 'Graveler', 'ゴローン'))
        records[-1]['context'] = 'Alolan electric Graveler description; species name is shared.'
    if key == 'tbl_menu_pokemon_summary_00014_419A3D':
        records.append({'state': 'INDEPENDENT_PROJECT_WORDING', 'english': 'Day-Care', 'japanese': 'そだてや',
                        'context': 'Egg found by the Day-Care couple identifies the breeding facility independently.',
                        'glossary_matching_this_entry': False, 'global_replace': False,
                        'scope': 'wording review of this entry only; existing scr_1F09A3C scope unchanged',
                        'official_claim': False})
    if key == 'tbl_battle_messages_00239_3FCC39':
        records.append({'state': 'UNVERIFIED_OFFICIAL_NAME', 'english': 'HM', 'japanese': 'ひでんマシン',
                        'reason': 'Existing applied usage is consistency evidence, not exact official entity proof; prior HM audit is ambiguous.',
                        'scope': 'HM moves; cannot borrow a guessed item/machine name'})
    for record in records:
        assert record['japanese'] in text
    return {'state': 'HOLD' if any(x['state'] == 'UNVERIFIED_OFFICIAL_NAME' for x in records)
            else 'VERIFIED' if records else 'NOT_REQUIRED', 'records': records,
            'review_warnings': deepcopy(row['official_name_warnings'])}


def notation_audit(row, text):
    original = strip_hma_quotes(row['original'])
    if '(' in original or ')' in original:
        expected = {'Low (Faster)': 'ひくい/はやい', 'Medium (Default)': 'ふつう/デフォルト',
                    'High (Slower)': 'たかい/おそい'}
        approved = expected.get(original) == text
        return {'required': True, 'approved': approved, 'replacement': 'parentheses -> slash',
                'meaning': 'one option: quality/value followed by its speed/default annotation; not two selectable options',
                'original': original, 'candidate': text}
    if '&' in original:
        approved = original == 'Bike&Surf Music' and text == 'じてんしゃと なみのりの おんがく'
        return {'required': True, 'approved': approved, 'replacement': '& -> と',
                'meaning': 'music for both bike and Surf contexts; conjunction preserved',
                'original': original, 'candidate': text}
    return {'required': False, 'approved': True}


def segment_check(row, text):
    targets = parse_raw_segments(Charmap('ja').encode(text))
    sources = source_segments(row)
    boundaries = [x['after_control'] for x in targets if x['after_control']]
    original_boundaries = source_boundaries(row)
    # Compare non-layout controls separately per source display segment. This
    # catches a buffer crossing FE even when global token counts are unchanged.
    invariant = (boundaries == original_boundaries and len(targets) == len(sources)
                 and all(semantic_tokens(s['text']) == semantic_tokens(t['text'])
                         for s, t in zip(sources, targets)))
    return {'state': 'PASS' if invariant else 'HOLD_BOUNDARY_OR_TOKEN_PLACEMENT',
            'source_boundaries': original_boundaries, 'target_boundaries': boundaries,
            'source_segments': deepcopy(sources), 'target_segments': targets,
            'counts_order_segments_and_protected_tokens_preserved': invariant}


def width_check(row, text):
    fixed = '[japanese]' + text + '[latin]'
    widths = normal_line_widths_with_placeholders(fixed, {})
    limits = {'battle_messages': 222, 'ability_descriptions': 191,
              'move_descriptions': 122, 'mission_descriptions': 172, 'setting_names': 93}
    limit = limits.get(row['category'])
    problems = []
    if max(widths['line_static']) > (limit if limit is not None else 240):
        problems.append('known_width_overflow')
    cat = row['category']
    lines = len(widths['line_static'])
    cap = {'ability_descriptions': 1, 'move_descriptions': 6, 'item_descriptions': 3,
           'mission_descriptions': 3, 'mission_objectives': 2, 'pokedex_descriptions': 3}.get(cat)
    if cap and lines > cap:
        problems.append('known_line_count_overflow')
    if row['id'] == WIDE:
        problems.append('223px_estimate_dynamic_bounds_unproved')
    if widths['unknown_placeholder_codes']:
        problems.append('dynamic_output_bounds_unproved')
    trace = horizontal_layout_trace(fixed)
    # Explicit minimum-X column FC13 57: labels must finish by x=87. FC0600
    # switches the following price to font 0, so its normal-font width is not
    # claimed as exact. The unchanged original price/column remains intact.
    if trace['position_events']:
        prefix = text.split('\\CC13', 1)[0]
        label_width = normal_line_widths_with_placeholders('[japanese]' + prefix + '[latin]', {})['max_total']
        column = trace['position_events'][0]['cursor_x']
        if label_width > column:
            problems.append('structured_column_collision')
        trace['label_pixels'] = label_width
        trace['source_column_x'] = column
        trace['price_font_exact_width_claimed'] = False
    return {**widths, 'state': 'HOLD' if problems else 'STATIC_FIT_RUNTIME_WARNING',
            'physical_or_project_limit': limit, 'line_cap': cap, 'horizontal_trace': trace,
            'problems': problems, 'runtime_measured': False,
            'warnings': ['width_runtime_unverified'],
            'legacy_54px_estimate': line_widths(Charmap('ja').encode(fixed)),
            'dynamic_bound': 'none required' if not row['buffers'] else 'unproved; 54px is not a safe bound'}


def glossary_audit(row, source, text, glossary):
    english = re.sub(r'\s+', ' ', strip_hma_quotes(row['original']))
    hits = glossary.matches(english, row['category'], entry_id=row['id'])
    applied = [{'source': term.source, 'target': term.target, 'kind': term.kind,
                'context_scope': term.context_scope, 'entry_ids': list(term.entry_ids),
                'categories': list(term.categories), 'global_replace': term.global_replace,
                'target_present': term.target in text} for _, _, term in hits]
    # No broad replacement is made: exact scoped matcher results are only
    # checked against reviewed wording. Reference-only terms remain references.
    return {'state': 'PASS' if all(x['target_present'] for x in applied) or not text else 'HOLD_TARGET_ABSENT',
            'matched_scoped_terms': applied, 'approved_terms_from_handoff': deepcopy(source['approved_glossary_terms']),
            'review_terms_used': deepcopy(row['glossary_terms_used']),
            'review_terms_not_used': deepcopy(row['glossary_terms_not_used']),
            'automatic_replacements': 0, 'scope_extensions': 0,
            'Day-Care_Fresh_Water_policy': 'independent entry semantics and exact item cache; never extend another entry scope'}


def context_check(row, baseline_rows):
    evidence = deepcopy(row['context_resolution'])
    refs = set()
    for e in evidence.get('evidence', []):
        # Include existing applied siblings named by the reviewer. Preserve
        # generic narrative evidence separately instead of inventing IDs.
        for prefix in re.findall(r'(?:menu_[a-z_]+_\d{5})', e.get('detail', '') if isinstance(e.get('detail'), str) else ''):
            refs.update(x['id'] for x in baseline_rows if x['id'].startswith('tbl_' + prefix))
    evidence['existing_applied_comparisons'] = [
        {'id': x['id'], 'original_english': x['original'], 'existing_japanese': x['translated']}
        for x in baseline_rows if x['id'] in refs]
    evidence['original_english'] = row['original']
    evidence['candidate_japanese'] = row['reviewed_japanese'] or row.get('reviewed_text_joined', '')
    evidence['semantic_confirmation_is_technical_approval'] = False
    return evidence


def prepare():
    source_rom = (ROOT / 'rom/unbound.gba').read_bytes()
    before = BASE.read_bytes()
    assert hashlib.md5(source_rom).hexdigest() == SOURCE_MD5
    assert digest(before) == BASE_SHA and len(before) == len(source_rom) == 0x2000000
    manifest = read(FIX / 'ja_phase6_cleanup_batch_manifest.json')
    review, batch = read(REVIEW), read(BATCH)['entries']
    validation = validate_review(review, batch, manifest)
    accounting = context_accounting(review)
    buffers = buffer_evidence(source_rom)
    assert battle_profiles(source_rom)['battle_message'].usable_width == 222
    glossary = load_glossary(ROOT / 'glossaries/ja.json', expected_language='ja')
    assert len(glossary.terms) == 292
    base_rows = baseline()
    prepared = {x['id']: x for x in read(ROOT / 'out/ja-phase5e-prepared.json')['entries']}
    selected = {x['id']: x for x in read(FIX / 'ja_phase6_selection.json')['entries']}
    selection = [selected[x['id']] for x in review]
    owners = {x['id']: x for x in owner_audit(selection, source_rom)['entries']}
    interiors = interior_pointer_hits(source_rom, selection)
    injector = runpy.run_path(str(ROOT / '005_hybrid_injector.py'))
    fix = runpy.run_path(str(ROOT / '004_controlfix_translations.py'))
    codec = Charmap('ja')
    records, safe = [], []
    assert not {x['id'] for x in base_rows} & {x['id'] for x in review}
    for row, handoff in zip(review, batch):
        key = row['id']
        entry, sel = deepcopy(prepared[key]), selected[key]
        pos, slot = int(entry['address'], 16), entry['byte_length']
        assert pos == sel['rom_offset'] and slot == sel['slot_size']
        assert entry['original'] == row['original']
        source_length = decode_pcs(source_rom, pos, slot).byte_length
        parsed = parse_raw_segments(source_rom[pos:pos + source_length])
        assert join_segments(parsed) == strip_hma_quotes(row['original'])
        assert source_rom[pos:pos + slot] == before[pos:pos + slot], key
        holds = []
        text = row['reviewed_japanese']
        fa = {'present': row['fa_segmented'], 'semantic_status': row['status'],
              'layout_status': 'NOT_APPLICABLE', 'source_segments': deepcopy(source_segments(row)),
              'translated_segments': deepcopy(row.get('translated_segments', []))}
        if row['status'] != 'confirmed':
            holds.append('review_' + row['status'])
        if row['fa_segmented']:
            if row['status'] == 'confirmed':
                text = reconstruct_reviewed_segments(strip_hma_quotes(row['original']), row['source_segments'], row['translated_segments'])
                fa['semantic_status'] = 'COMPLETED_SEGMENTS'
                fa['reconstructed_text'] = text
                fa['layout_status'] = 'HOLD_DYNAMIC_BUFFER_AND_LAYOUT_UNPROVED'
            else:
                fa['layout_status'] = 'HOLD_UNKNOWN_00'
            holds.append('fa_layout_not_approved')
        controls = segment_check(row, text) if text else {'state': 'NO_COMPLETED_TRANSLATION'}
        if text and controls['state'] != 'PASS':
            holds.append('source_boundary_or_token_placement_changed')
        codes = CODE.findall(strip_hma_quotes(row['original']))
        buffer_state = {'state': 'NOT_REQUIRED', 'codes': codes, 'review_metadata': deepcopy(row['buffers'])}
        if row['buffers']:
            buffer_state['state'] = 'CALLER_DEPENDENT' if any(x in row['buffers'] for x in ('\\\\00', '[buffer1]', '\\\\28', '\\\\2A')) else 'UNVERIFIED'
            buffer_state['code_evidence'] = {c: buffers['codes'].get(c, {'classification': 'UNVERIFIED',
                    'reason': 'Prior FireRed meaning does not prove the Unbound high-bank handler/caller contract.'}) for c in codes}
            holds.append('unbound_buffer_contract_unproved')
        official = official_audit(row, text) if text else {'state': 'NOT_REVIEWABLE', 'records': []}
        if official['state'] == 'HOLD':
            holds.append('official_entity_unverified')
        notation = notation_audit(row, text)
        if not notation['approved']:
            holds.append('notation_semantics_unproved')
        width = width_check(row, text) if text else {'state': 'NOT_MEASURED', 'problems': []}
        holds.extend(width['problems'])
        terms = glossary_audit(row, handoff, text, glossary)
        if terms['state'] != 'PASS':
            holds.append('glossary_scoped_target_absent')
        encoded_length, fixed_text, payload = None, None, None
        if text:
            fixed_text = fix['ensure_japanese_page'](text)[0]
            try:
                payload = encoded(injector, codec, entry, fixed_text)
                encoded_length = len(payload)
            except (ValueError, UnicodeEncodeError) as exc:
                holds.append('encode_error:' + str(exc))
        relocation = encoded_length is not None and encoded_length > slot
        pointer = {**owners[key], 'interior_hits': interiors[key], 'relocation_needed': relocation,
                   'fixed': sel['fixed'], 'no_relocation': sel['no_relocation']}
        if relocation and (sel['fixed'] or sel['no_relocation']):
            holds.append('fixed_or_no_relocation_overflow')
        if relocation and (not entry.get('is_pointer_based') or not entry.get('pointer_sources')):
            holds.append('relocation_owner_absent')
        if relocation and (pointer['missing'] or pointer['stale'] or interiors[key]):
            holds.append('relocation_owner_incomplete_or_interior')
        for owner in entry.get('pointer_sources', []):
            p = int(owner, 16)
            assert before[p:p + 4] == source_rom[p:p + 4], key
        if key == CUBE:
            assert slot == 8 and encoded_length == 11 and sel['fixed'] and sel['no_relocation']
        holds = list(dict.fromkeys(holds))
        record = {'id': key, 'review_status': row['status'], 'original_english': row['original'],
                  'candidate_japanese': text, 'review': deepcopy(row), 'source_handoff': deepcopy(handoff),
                  'decision': 'HOLD' if holds else 'APPLY',
                  'primary_hold': holds[0] if holds else None, 'secondary_holds': holds[1:],
                  'all_holds': holds, 'official_name_state': official, 'buffer_state': buffer_state,
                  'FA_state': fa, 'control_state': controls, 'width_state': width,
                  'pointer_state': pointer, 'glossary_state': terms, 'notation_audit': notation,
                  'context_verification': context_check(row, base_rows),
                  'source_slot': slot, 'encoded_bytes': encoded_length, 'controlfixed_japanese': fixed_text,
                  'planned_placement': 'relocated' if relocation else 'in_place',
                  'next_action': 'Resolve each recorded hold with entry-specific ROM evidence; preserve reviewed segments and wording.' if holds
                                 else 'Runtime QA: trigger original caller and compare every segment; no further translation work.'}
        records.append(record)
        if not holds:
            entry['translated'] = fixed_text
            safe.append(entry)
    confirmed_special = [x['id'] for x in review if x['status'] == 'confirmed' and set(CODE.findall(x['original'])) & SPECIAL]
    all_special = [x['id'] for x in review if set(CODE.findall(x['original'])) & SPECIAL]
    assert len(confirmed_special) == 33 and len(all_special) == 37
    inputs = [REVIEW, BATCH, FIX / 'ja_phase6_cleanup_batch_manifest.json',
              OUT / 'ja_phase6_cleanup_translation_style_handoff.json', ROOT / 'glossaries/ja.json',
              ROOT / 'scripts/build_ja_phase6_voice_integration.py', ROOT / 'tests/test_ja_phase6_voice_integration.py']
    preflight = {'validation': validation, 'context_accounting': accounting, 'battle_buffer_evidence': buffers,
                 'special_33_confirmed_ids': confirmed_special, 'special_all_37_ids': all_special,
                 'extra_special_context_ids': sorted(set(all_special) - set(confirmed_special)),
                 'input_hashes': {str(p.relative_to(ROOT)): digest(p.read_bytes()) for p in inputs},
                 'baseline_sha256': BASE_SHA, 'source_md5': SOURCE_MD5,
                 'applied': len(safe), 'held': len(records) - len(safe),
                 'baseline_applied': 2261, 'japanese_applied_total': 2261 + len(safe),
                 'phase6_remaining_holds': 916 - len(safe)}
    persist(OUT / (PREFIX + 'preflight.json'), preflight)
    persist(OUT / (PREFIX + 'reviewed.json'), {'metadata': preflight, 'entries': records})
    persist(OUT / (PREFIX + 'technical_holds.json'), {'metadata': {'count': len(records) - len(safe)},
                                                  'entries': [x for x in records if x['decision'] == 'HOLD']})
    persist(OUT / (PREFIX + 'safe_input.json'), {'entries': safe})
    persist(OUT / (PREFIX + 'combined_controlfix.json'), {'entries': base_rows + safe})
    return preflight, records, safe


def cli(script, arguments, outputs):
    if any(p.exists() for p in outputs):
        assert all(p.exists() for p in outputs), f'Partial stage exists: {outputs}; inspect it, never overwrite.'
        return
    for path in outputs:
        assert not path.exists(), path
    result = subprocess.run([sys.executable, '-X', 'utf8', str(ROOT / script), *map(str, arguments)],
                            cwd=ROOT, text=True, encoding='utf-8', capture_output=True)
    assert result.returncode == 0, result.stdout + result.stderr


def assert_safe_record(record):
    """Independent fail-closed release gate, also used when reusing artifacts."""
    assert record['decision'] == 'APPLY' and record['review_status'] == 'confirmed'
    assert not record['all_holds'] and record['primary_hold'] is None
    assert record['control_state']['state'] == 'PASS'
    assert record['buffer_state']['state'] == 'NOT_REQUIRED'
    assert not record['width_state']['problems']
    assert record['official_name_state']['state'] not in {'HOLD', 'NOT_REVIEWABLE'}
    assert record['glossary_state']['state'] == 'PASS'
    assert record['notation_audit']['approved']
    assert not record['FA_state']['present'], 'No FA layout was approved in this pass'
    pointer = record['pointer_state']
    if pointer['relocation_needed']:
        assert not pointer['fixed'] and not pointer['no_relocation']
        assert pointer['recorded'] and not pointer['missing'] and not pointer['stale'] and not pointer['interior_hits']
    else:
        assert record['encoded_bytes'] <= record['source_slot']


def supplemental_context(records):
    """Exact sibling comparisons; compressed review IDs can name several tables.

    Resolve both English identity and full stable ID, not a numeric suffix alone.
    Keep this supplemental audit distinct from the immutable reviewed artifact.
    """
    old = baseline()
    siblings = {
        'cube_sort': ['tbl_menu_cube_system_00001_A4E065', 'tbl_menu_cube_system_00002_A4E06A',
                      'tbl_menu_cube_system_00011_A4E09D', 'tbl_menu_cube_system_00012_A4E0AF',
                      'tbl_menu_game_settings_00002_1F4DC2A', 'tbl_menu_game_settings_00003_1F4DC32',
                      'tbl_menu_game_settings_00004_1F4DC3A'],
        'battle_entry': ['tbl_menu_cube_system_00013_A4E0C3', 'tbl_menu_cube_system_00014_A4E0E9',
                         'tbl_menu_cube_system_00015_A4E110'],
        'copper_rank': ['tbl_menu_link_controls_00003_41DF8B', 'tbl_menu_link_controls_00005_41DF99',
                        'tbl_menu_link_controls_00006_41DFA0'],
    }
    by_id = {x['id']: x for x in old}
    corpus = read(ROOT / 'out/ja-phase5e-prepared.json')['entries']
    result = []
    for record in records:
        review = record['review']
        if not review['context_resolution']['resolved']:
            continue
        key = record['id']
        group = ('cube_sort' if key.startswith('tbl_menu_cube_system_') else
                 'battle_entry' if any(key.startswith(f'tbl_menu_battle_{n:05d}_') for n in (2, 3)) else
                 'copper_rank' if key == 'tbl_menu_link_controls_00004_41DF92' else None)
        refs = siblings.get(group, [])
        assert all(x in by_id for x in refs)
        candidate = record['candidate_japanese']
        if group == 'cube_sort':
            assert all(any(word in by_id[x]['translated'] for word in ('しゅるい', 'なまえ', 'どうぐ', 'ならべかえ', 'じゅん')) for x in refs)
            assert candidate in {'おおいじゅん', 'すくないじゅん', 'こすう', 'しゅるい'}
        if group == 'battle_entry':
            assert all('さんか できる ポケモンは' in by_id[x]['translated'] for x in refs)
            assert candidate in {'さんかする', 'さんかしない'}
        if group == 'copper_rank':
            assert [strip_hma_quotes(by_id[x]['original']) for x in refs] == ['BRONZE', 'SILVER', 'GOLD']
            assert candidate == 'カッパー'
        # This is consistency evidence, not a new translation or an automatic
        # substitution. It also records when no prior applied analogue exists.
        plain_original = strip_hma_quotes(review['original'])
        comparables = [x for x in old if strip_hma_quotes(x['original']) == plain_original]
        result.append({'id': key, 'original_english': review['original'], 'candidate_japanese': candidate,
                       'review_evidence': deepcopy(review['context_resolution']['evidence']),
                       'buffer_semantics': record['buffer_state'], 'glossary_scope': record['glossary_state'],
                       'technical_decision': record['decision'],
                       'exact_existing_siblings': [{'id': x, 'original_english': by_id[x]['original'],
                                                    'japanese': by_id[x]['translated']} for x in refs],
                       'identical_english_applied_entries': [{'id': x['id'], 'japanese': x['translated']} for x in comparables],
                       'no_prior_identical_english': not comparables,
                       'source_category_consistent': any(x['id'] == key and x['category'] == review['category'] for x in corpus)})
    assert len(result) == 56 and all(x['source_category_consistent'] for x in result)
    return {'count': 56, 'entries': result,
            'compressed_ID_warning': 'The same category/index prefix can identify multiple ROM tables. Match the complete stable ID and English meaning.'}


def build(safe):
    inp = OUT / (PREFIX + 'safe_input.json')
    fixed = OUT / (PREFIX + 'controlfix.json')
    twice = OUT / (PREFIX + 'controlfix_twice.json')
    for source, output, report in [(inp, fixed, OUT / (PREFIX + 'controlfix_report.json')),
                                    (fixed, twice, OUT / (PREFIX + 'controlfix_twice_report.json'))]:
        cli('004_controlfix_translations.py', [source, '-o', output, '--source', ROOT / 'out/ja-phase5e-prepared.json',
                                              '--report', report, '--target-lang', 'ja', '--no-wrap'], [output, report])
        assert read(output)['entries'] == safe, 'Controlfix must not change reviewed wording or boundaries'
        stats = read(report)['stats']
        assert stats['remaining_control_mismatches'] == stats['fa_placement_review_required'] == 0
    combined = OUT / (PREFIX + 'combined_controlfix.json')
    full_map = OUT / (PREFIX + 'full_dry_run_map.json')
    cli('005_hybrid_injector.py', [ROOT / 'rom/unbound.gba', combined, '-o', ROM, '--target-lang', 'ja',
                                 '--dry-run', '--fail-on-no-space', '--map-output', full_map], [full_map])
    full = read(full_map)
    assert_strict_map(full, full, 2261 + len(safe))
    assert full['stats']['in_place'] + full['stats']['relocated'] + full['stats']['unchanged'] == 2261 + len(safe)
    dry_map = OUT / (PREFIX + 'incremental_dry_run_map.json')
    build_map = OUT / (PREFIX + 'map.json')
    cli('005_hybrid_injector.py', [BASE, fixed, '-o', ROM, '--target-lang', 'ja', '--dry-run',
                                 '--fail-on-no-space', '--map-output', dry_map], [dry_map])
    plan = read(dry_map)
    assert_strict_map(plan, plan, len(safe))
    cli('005_hybrid_injector.py', [BASE, fixed, '-o', ROM, '--target-lang', 'ja',
                                 '--fail-on-no-space', '--map-output', build_map], [ROM, build_map])
    assert_strict_map(plan, read(build_map), len(safe))


def audit_binary(before, after, safe, mapping, old_rows):
    assert len(before) == len(after) == 0x2000000
    injector = runpy.run_path(str(ROOT / '005_hybrid_injector.py'))
    codec = Charmap('ja')
    relocations = {x['id']: x for x in mapping['relocations']}
    allowed = {k: set() for k in ('in_place_text', 'relocated_text', 'pointer_writes')}
    for row in safe:
        payload = encoded(injector, codec, row, row['translated'])
        offset, slot = int(row['address'], 16), row['byte_length']
        move = relocations.get(row['id'])
        if move:
            dest = int(move['new_offset'], 16)
            assert move['storage'] == 'vetted_ff' and move['byte_length'] == len(payload)
            assert before[dest:dest + len(payload)] == b'\xff' * len(payload)
            assert after[dest:dest + len(payload)] == payload
            assert after[offset:offset + slot] == before[offset:offset + slot]
            allowed['relocated_text'].update(range(dest, dest + len(payload)))
            for pointer in move['pointer_sources']:
                p = int(pointer, 16)
                assert before[p:p + 4] == (0x08000000 + offset).to_bytes(4, 'little')
                assert after[p:p + 4] == (0x08000000 + dest).to_bytes(4, 'little')
                allowed['pointer_writes'].update(range(p, p + 4))
        else:
            assert len(payload) <= slot and after[offset:offset + slot] == payload.ljust(slot, b'\xff')
            allowed['in_place_text'].update(range(offset, offset + slot))
    old_moves = {}
    for name in ('ja_phase6_batch04_map.json', 'ja_phase6_batch05_incremental_map.json',
                 'ja_phase6_batch06_incremental_map.json', 'ja_phase6_cleanup_incremental_map.json',
                 'ja_phase6_cleanup_glossary_incremental_map.json'):
        old_moves.update({x['id']: x for x in read(OUT / name)['relocations']})
    protected = set()
    for row in old_rows:
        move = old_moves.get(row['id'])
        pos = int(move['new_offset'], 16) if move else int(row['address'], 16)
        length = move['byte_length'] if move else row['byte_length']
        assert before[pos:pos + length] == after[pos:pos + length], row['id']
        payload = encoded(injector, codec, row, row['translated'])
        assert before[pos:pos + len(payload)] == payload, ('Baseline payload mismatch', row['id'])
        protected.update(range(pos, pos + length))
        for pointer in row.get('pointer_sources', []):
            p = int(pointer, 16)
            assert before[p:p + 4] == after[p:p + 4], row['id']
            protected.update(range(p, p + 4))
    union = set().union(*allowed.values())
    assert sum(map(len, allowed.values())) == len(union), 'Overlapping write classes'
    assert not protected & union, 'New writes overlap existing text/pointers'
    changed = {i for i, (a, b) in enumerate(zip(before, after)) if a != b}
    assert not changed - union, 'Unexpected binary differences'
    assert not changed & protected
    return {'status': 'PASS', 'existing_2261_text_and_pointers_unchanged': True,
            'changed_byte_count': len(changed), 'unexpected_byte_count': 0,
            'classified_changed_bytes': {k: len(v & changed) for k, v in allowed.items()},
            'in_place_count': mapping['stats']['in_place'], 'relocation_count': len(relocations),
            'pointer_writes': mapping['stats']['pointer_writes'], 'output_sha256': digest(after),
            'runtime_patches': 0, 'font_graphics_changes': 0}


def runtime_qa(records, mapping):
    applied = [x for x in records if x['decision'] == 'APPLY']
    ranked = sorted(applied, key=lambda x: (-bool(x['official_name_state']['records']),
                    -bool(x['control_state'].get('source_boundaries')), -bool(x['pointer_state']['relocation_needed']),
                    -max(x['width_state']['line_static'])))
    chosen = ranked[:16]
    # Include buffer/FA holds as negative QA cases, explicitly absent from ROM.
    for key in ('tbl_battle_messages_00122_3FC048', WIDE, 'tbl_battle_messages_00185_3FC75D', CUBE):
        chosen.append(next(x for x in records if x['id'] == key))
    assert len({x['id'] for x in chosen}) == len(chosen) == 20
    return {'metadata': {'count': 20, 'performed': False, 'emulator_operation_required_now': False},
            'entries': [{'id': x['id'], 'category': x['review']['category'], 'apply_status': x['decision'],
                         'original': x['original_english'], 'japanese': x['candidate_japanese'],
                         'source_offset': x['source_handoff']['known_technical_constraints']['rom_offset'],
                         'pointer_owners': x['pointer_state']['recorded'],
                         'relocation': next((m for m in mapping['relocations'] if m['id'] == x['id']), None),
                         'procedure': 'Trigger this exact original caller; advance FE/FB/FA normally, inspect glyphs, width, name expansion and adjacent fields. Holds must retain the original English.',
                         'expected_controls': x['review']['source_controls'],
                         'priority_reasons': ['official terms' if x['official_name_state']['records'] else 'width/layout',
                                              'relocated' if x['pointer_state']['relocation_needed'] else 'in-place',
                                              'positive apply' if x['decision'] == 'APPLY' else 'negative hold']}
                        for x in chosen]}


def report(preflight, records, audit):
    applied = [x for x in records if x['decision'] == 'APPLY']
    official = [x for x in records if x['review']['official_name_warnings']]
    fa = [x for x in records if x['FA_state']['present']]
    text = f'''# Phase 6C-4C — Final Cleanup Batch 01 Technical Integration

147件を監査し、{len(applied)}件を適用、{147 - len(applied)}件を保留。今回の範囲はBatch 01のみ。
既存2,261件の本文・pointer、Sarah/Liam/Koji修正、Daniel既存訳は全て保持。

## 検証結果

|項目|結果|
|---|---|
|review validation|147 IDs / duplicate 0 / missing 0 / source・provenance・controls・metadata一致|
|status|confirmed 114 / needs_context 32 / needs_technical_fit 1|
|source boundary|FE 124 / FB 15 / FA 4|
|context unique accounting|32 unique / 33 memberships; 00と28の重複はtbl_battle_messages_00081_3FBC62|
|semantic context resolved|56 unique; 根拠39 battle / 10 glossary / 24 siblingは重複と複数根拠を含む|
|special battle buffers|confirmed 33件、contextを含め37件。7コードを実ROMでdispatchまで追跡。全経路・writer/caller未証明のためUNVERIFIEDとして保留|
|safe / holds|{len(applied)} / {147 - len(applied)}|
|in-place / relocation|{audit['in_place_count']} / {audit['relocation_count']}|
|pointer writes|{audit['pointer_writes']}|
|Japanese applied total|{preflight['japanese_applied_total']}|
|Phase 6 remaining holds|{preflight['phase6_remaining_holds']}|
|existing 2,261|個別payload照合・storage・全pointer bytes保持 PASS|
|strict dry-run|2,261 + safe全体と基準ROMへのincremental両方PASS|
|controlfix|safe subsetを標準controlfix --no-wrapで2回実行、完全一致・idempotent|
|binary audit|{audit['changed_byte_count']} changed bytes / unexpected 0 / runtime patch 0 / font・graphics change 0|
|ROM SHA256|`{audit['output_sha256']}`|
|runtime QA|20 cases; mGBA操作は未実施、実行用fixtureあり|

## Battle buffers — proof boundary

ROM `0x000D77F4`のwrapperは`0x080D7868`を呼び、そこは`ldr r2; bx r2`で
`0x089BD050`へ飛ぶ。ROM `0x009BD0BA`でFDを判別し、code<=0x3Dを検査し、
`0x08964ABE`経由でROM `0x009BD0D0`の62 halfword dispatch tableを使う。
FireRed vanilla番号一致だけの互換判定は無効。

|code|実ROM handler|追跡した情報|分類|
|---|---|---|---|
|12|0x089BD36C|active selector RAM 0x02023BC4、条件付き接頭辞とname helper|UNVERIFIED|
|16|0x089BD434|RAM 0x02023D68 halfword -> helper 0x08099E91|UNVERIFIED|
|18|0x089BD45C|selector 0x02023D6B、shared ability/species helper path|UNVERIFIED|
|19|0x089BD462|selector 0x02023D6C、同shared path|UNVERIFIED|
|1B|0x089BD480|selector 0x02023D6E、同shared path|UNVERIFIED|
|20|0x089BD5A0|0x0202273C link records、28-byte stride、side xor 1|UNVERIFIED|
|21|0x089BD5B2|同link records、side xor 3|UNVERIFIED|

上記はpartial evidence。helperの全呼出し、species-sensitive table、message writer、
active/link/Frontier状態、出力言語と最大幅まで同一ROMでつながっていない。
既存の0F/10/11/13/14/1Aについても以前のpret-only承認を新規適用へ流用しない。
00/28/2A/[buffer1]はCALLER_DEPENDENT。詳細machine-code prefixesと33/37 ID一覧はreviewed JSONに保存。
[CFRU hooks](https://github.com/Skeli789/Complete-Fire-Red-Upgrade/blob/master/hooks) と
[battle_strings.c](https://github.com/Skeli789/Complete-Fire-Red-Upgrade/blob/master/src/battle_strings.c)
は探索用の一次資料であり、このROMのbuild identityや互換証明ではない。

## Official / glossary scope

'''
    for x in official:
        text += f"- `{x['id']}`: {x['official_name_state']['state']}; " + '; '.join(
            r['english'] + '=' + r['japanese'] + ' (' + r['state'] + ')' for r in x['official_name_state']['records']) + f"; {x['decision']}\n"
    text += '''
PokeAPI cacheはen exact entityとja-hrktを照合し、entity ID・cache SHA256を保存。
CurseはHP犠牲による呪いの効果、Gravelerは電気を帯びたアローラ個体の種名として確認。
HMは既存使用例だけでは公式entityを証明できず保留。Day-Careは夫婦が見つけたタマゴという
独立した文脈から育成施設「そだてや」を採用し、公式検証済みとは主張しない。
Fresh Water/Pecha Berryは独立したitem cache照合。292 termsのscope・global_replaceを変更しない。
全147件にscoped matcher結果、review used/not-used、元handoff metadataを保持。

## FA / controls / width

'''
    for x in fa:
        text += f"- `{x['id']}`: {x['FA_state']['semantic_status']}; {x['FA_state']['layout_status']}; {x['decision']}\n"
    text += '''
完成segments3件は元のFE/FA順・segment数・segment別protected controlsを確認して再構築。
全体reviewed_japanese空欄を未完訳とは扱わない。ただしbufferとdynamic幅未証明のため
layout approvalを付与せず全FA保留。00を含む1件は意味上も未解決。
通常entryも元のsegment境界に対してtokensを比較し、移動したものは保留。

Cube V3 (`tbl_start_menu_labels_00001_A4E4E4`) は8-byte fixed/no-relocation枠に
キューブV3の11 bytesが必要で保留。切詰め・制御削除・隣接上書きなし。

223px case (`tbl_battle_messages_00158_3FC421`) は旧診断の「静的幅」というラベルが誤り。
静的幅は[10,115]pxで、223pxは2つのFDを54pxずつ加えた仮の幅。
222px battle spanを満たす証明にはならず、意味・実dynamic bounds未証明で保留。
この差異を推測で修正して採用しない。

Low/Medium/High括弧→slashの3件は同一選択肢の値/速度注記で意味を保持。
Bike&Surf Musicの&→とは両方の移動状態の音楽という論理ANDを保持。
ただし169px setting labelは既存93px制約で保留。charmap対応だけで採用しない。

文面をwrapし直してsource FE/FB/FAを動かさず、既存controlfixの言語ページのみ付与。
確立済み能力191px/1行、技122px/6行、mission172px/3行、setting93px制約を使用。
vendor FC13 column x=87の手前にitem nameが収まるか個別比較。後続FC0600の価格のfont0は
元controlと価格を維持し、normal-fontで価格幅を証明したとは主張しない。
renderer実機未測定だけならwarning。全保留理由をprimary/secondaryとして残した。

## Reproduction / preservation / handoff

`.venv\\Scripts\\python.exe -X utf8 scripts/build_ja_phase6_cleanup_batch01.py all`

全出力は存在確認し、JSON再計算一致またはROM/map監査のみ。既存成果物を上書きしない。
strict full dry-runは元ROMから容量/owner/pointer/encodeを検証する診断であり、
実ROM生成はvoice-pass1基準へのincremental適用。全差分をin-place/relocation/pointerに分類。
旧relocation mapと既存2261個別encoded payload・本文範囲・全pointerを照合し保持。
他工程スクリプト、glossary、旧ROM、6件の既存未追跡ファイルは変更なし。

Batch 02準備に進むためのtechnical gate/reportは揃ったが、buffer検証の課題は残る。
今回Batch 02〜04の翻訳を開始しない。次回はROM固有helper/writerとdynamic幅を証明し、
FAではsegment translationとlayout approvalを分離、official exact entityとentry scopeを独立検証する。
unknown rendererを一律保留へ戻さず、確実なoverflow/column collision/固定枠だけを別のgateで止める。

作成: 新script/test、technical report、runtime QA fixture、out/phase6のBatch01専用JSON/maps、
`out/unbound-ja-phase6-cleanup-batch01.gba`。tracked既存ファイル変更なし。commit/pushなし。
最終pytest/py_compile/git diff --check結果はvalidation JSONに保存。
'''
    path = ROOT / 'docs/ja-phase6-final-cleanup-batch01-technical.md'
    if path.exists():
        assert path.read_text(encoding='utf-8') == text
    else:
        with path.open('x', encoding='utf-8') as handle:
            handle.write(text)


def main():
    preflight, records, safe = prepare()
    for record in records:
        if record['decision'] == 'APPLY':
            assert_safe_record(record)
    build(safe)
    mapping = read(OUT / (PREFIX + 'map.json'))
    audit = audit_binary(BASE.read_bytes(), ROM.read_bytes(), safe, mapping, baseline())
    assert digest(BASE.read_bytes()) == BASE_SHA
    for name, expected in preflight['input_hashes'].items():
        assert digest((ROOT / name).read_bytes()) == expected, name
    persist(OUT / (PREFIX + 'binary_audit.json'), audit)
    persist(FIX / (PREFIX + 'runtime_qa.json'), runtime_qa(records, mapping))
    persist(OUT / (PREFIX + 'context_verification.json'), supplemental_context(records))
    report(preflight, records, audit)
    print(json.dumps({**preflight['validation'], 'applied': len(safe), 'held': 147 - len(safe),
                      'binary_audit': audit}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    if sys.argv[1:] != ['all']:
        raise SystemExit('usage: build_ja_phase6_cleanup_batch01.py all')
    main()
