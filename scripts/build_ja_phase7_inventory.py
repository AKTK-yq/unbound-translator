#!/usr/bin/env python3
"""Read-only Phase 7A census. Creates four exact-path JSON files, never a ROM.

Run from the repository root: python scripts/build_ja_phase7_inventory.py
Existing outputs must be byte-identical; conflicting or partial outputs stop.
This is evidence aggregation, not translation, controlfix, or an injector gate.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
from math import ceil
from pathlib import Path
import re
import runpy
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lib.pcs_text import Charmap, decode_pcs
from lib.translation_tokens import semantic_tokens, strip_hma_quotes
from scripts.build_ja_phase5_dataset import control_features, renderer_for
from scripts.build_ja_phase6_cleanup_batch03 import PHASE7A_PATHS, protected_snapshot
from scripts.build_ja_phase6_voice_integration import encoded

BASE_ROM = 'out/unbound-ja-phase6-cleanup-batch04.gba'
BASE_SHA = '0d1d00e7b0f4f113514abbcf1907e6d8949fd12b9193bf2cb0ad764ace5559d8'
CANONICAL = 'out/ja-phase5e-prepared.json'
RAW = 'out/unbound-texts.json'
APPLIED = 'out/phase6/ja_phase6_cleanup_batch04_combined_controlfix.json'
SELECTION = 'tests/fixtures/ja_phase6_selection.json'
OLD_WARNING = 'scr_1F4E26F'
WARNING = 'tbl_menu_game_settings_00000_1F4E26F'
SUFFIX = 'tbl_menu_game_settings_00000_1F4E274'
OUTPUTS = tuple('out/phase7/ja_full_localization_' + name + '.json' for name in
                ('inventory', 'category_stats', 'priority_queue', 'technical_blockers'))
MAPS = tuple('out/phase6/' + name + '.json' for name in (
    'ja_phase6_batch04_map', 'ja_phase6_batch05_incremental_map',
    'ja_phase6_batch06_incremental_map', 'ja_phase6_cleanup_incremental_map',
    'ja_phase6_cleanup_glossary_incremental_map', 'ja_phase6_cleanup_batch01_map',
    'ja_phase6_cleanup_batch02_map', 'ja_phase6_cleanup_batch03_map',
    'ja_phase6_cleanup_batch04_map'))
RUNTIME_OBSERVED = frozenset(('scr_1F0F7EC', 'scr_1F0F800', 'scr_1F0F814'))
HOLD_FAMILIES = (
    'unknown buffer', 'FA semantic boundary', 'dynamic name width',
    'renderer consumer', 'width overflow', 'incomplete pointer ownership',
    'official name', 'glossary scope', 'text slot capacity', 'glyph/font', 'other')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def index_unique(rows, label):
    result = {r['id']: r for r in rows}
    if len(result) != len(rows):
        raise ValueError('Duplicate IDs: ' + label)
    return result


def offset(row):
    value = row['address']
    return int(value, 16) if isinstance(value, str) else value


def pointer_hits(rom, target):
    needle = (0x08000000 + target).to_bytes(4, 'little')
    hits, cursor = [], 0
    while (cursor := rom.find(needle, cursor)) >= 0:
        hits.append(f'0x{cursor:08X}')
        cursor += 1
    return hits


def reconcile(canonical, raw, rom):
    """Prove a full-string alias; preserve the interior suffix as unresolved."""
    c, r = index_unique(canonical, 'canonical'), index_unique(raw, 'raw')
    common = set(c) & set(r)
    assert len(c) == 25044 and len(r) == 25045 and len(common) == 25043
    assert set(c) - set(r) == {WARNING}
    assert set(r) - set(c) == {OLD_WARNING, SUFFIX}
    metadata_deltas = []
    for key in sorted(common):
        for field in ('original', 'address', 'byte_length'):
            assert c[key].get(field) == r[key].get(field), (key, field)
        if c[key].get('pointer_sources') != r[key].get('pointer_sources'):
            # Historical owner discoveries are evidence, not source-text edits.
            for p in c[key].get('pointer_sources', []) + r[key].get('pointer_sources', []):
                owner = int(p, 16)
                assert int.from_bytes(rom[owner:owner + 4], 'little') == 0x08000000 + offset(c[key])
            metadata_deltas.append({'id': key, 'canonical_pointer_sources': c[key].get('pointer_sources', []),
                'raw_pointer_sources': r[key].get('pointer_sources', []), 'source_rom_words_verified': True})
    full, alias, suffix = c[WARNING], r[OLD_WARNING], r[SUFFIX]
    for field in ('original', 'address', 'byte_length', 'pointer_sources'):
        assert full[field] == alias[field], field
    start, inner = offset(full), offset(suffix)
    assert (start, inner, full['byte_length'], suffix['byte_length']) == (
        0x1F4E26F, 0x1F4E274, 185, 180)
    a, b = decode_pcs(rom, start, 185), decode_pcs(rom, inner, 180)
    assert a.text == strip_hma_quotes(full['original']) and a.terminated
    assert b.text == strip_hma_quotes(suffix['original']) and b.terminated
    assert start + a.byte_length == inner + b.byte_length == 0x1F4E328
    assert rom[start:start + 5] == bytes.fromhex('FC 01 04 D1 BB')
    owners = pointer_hits(rom, start)
    assert owners == ['0x01EBD7FC']
    extractor = runpy.run_path(str(ROOT / '001_extract_unbound_text.py'))
    current_range = [x for x in extractor['POST_POINTER_MANUAL_TEXT_RANGES']
                     if x.table_name == 'data.menus.text.gameSettings.extraPrompts']
    focused, _ = extractor['extract_manual_tables'](
        rom, 0, set(), set(), manual_ranges=current_range, include_tables=False)
    assert focused[0]['id'] == WARNING and focused[0]['original'] == full['original']
    return {
        'raw_extracted_count': 25045, 'canonical_translation_target_count': 25044,
        'common_ids': 25043, 'union_ids': 25046, 'missing_id_count': 0,
        'duplicate_id_count': 0, 'common_original_changes': 0,
        'common_pointer_metadata_deltas': metadata_deltas,
        'full_string_alias': {'raw_id': OLD_WARNING, 'canonical_id': WARNING,
            'status': 'PROVEN_SAME_STRING', 'rom_offset': '0x01F4E26F',
            'gba_address': '0x09F4E26F', 'pointer_sources': owners, 'slot_size': 185,
            'text_last_byte': '0x01F4E327', 'terminator': '0xFF',
            'reason': 'Identical address, original, slot and owner; different category/ID.'},
        'interior_candidate': {'raw_id': SUFFIX, 'parent_id': WARNING,
            'mapping_status': 'UNRESOLVED_MAPPING', 'offset_into_parent': 5,
            'rom_offset': '0x01F4E274', 'gba_address': '0x09F4E274', 'slot_size': 180,
            'relationship': 'STRICT_BYTE_SUFFIX_NOT_IDENTICAL_STRING',
            'omitted_prefix_hex': 'fc 01 04 d1 bb', 'omitted_prefix_text': '[red]WA',
            'whole_rom_direct_pointer_hits': pointer_hits(rom, inner),
            'shared_terminator_offset': '0x01F4E327',
            'computed_or_interior_consumer': 'NOT_PROVEN_OR_DISPROVED',
            'independent_runtime_display': 'UNPROVEN', 'unused_proven': False,
            'next_action': 'Trace computed/interior consumers; do not translate/write overlapping slots independently.'},
        'history': {'commit': '22a425f6850308383ae1bee746a3c4ebdb47cf0d',
            'file': '001_extract_unbound_text.py', 'change':
            'POST_POINTER extraPrompts start 0x1F4E274 -> 0x1F4E26F; added packed owner 0x1EBD7FC.',
            'current_focused_extraction': 'PROVEN_FULL_BOUNDARY',
            'raw_file_provenance': 'Old-boundary content; no embedded version/timestamp. Exact generation command unrecorded.'},
        'accounting': 'Canonical 25044 is the existing work ledger, not proof that raw suffix is unused. Keep +1 unresolved coverage obligation; unique physical display units provisionally 25044..25045.'}


def hold_family(reason):
    x = reason.lower()
    if 'dynamic' in x and ('width' in x or 'bound' in x):
        return 'dynamic name width'
    if 'buffer' in x:
        return 'unknown buffer'
    if 'pointer' in x or 'owner' in x or 'interior' in x:
        return 'incomplete pointer ownership'
    if 'glyph' in x or 'font' in x or 'raw_prefix' in x:
        return 'glyph/font'
    if 'slot' in x or 'capacity' in x or 'fixed' in x or 'fit' in x:
        return 'text slot capacity'
    if 'renderer' in x or 'consumer' in x or 'structured_ui' in x:
        return 'renderer consumer'
    if 'width' in x or 'overflow' in x:
        return 'width overflow'
    if 'fa' in x or 'control_boundary' in x:
        return 'FA semantic boundary'
    if 'glossary' in x:
        return 'glossary scope'
    if 'official' in x or 'entity' in x or 'name_unverified' in x:
        return 'official name'
    return 'other'


def classify(row, speaker):
    c = row['category']
    if c.startswith('pokedex_'):
        return 'POKEDEX'
    if c in {'pokemon_names', 'move_names', 'ability_names', 'type_names', 'nature_names'}:
        return 'POKEMON_MOVE_ABILITY_NAMES'
    if c in {'item_names', 'item_descriptions'}:
        return 'ITEMS'
    if c.startswith('mission_'):
        return 'MISSIONS'
    if c.startswith('menu_') or c in {'setting_names', 'start_menu_labels', 'day_names'}:
        return 'MENUS_SETTINGS'
    if c in {'battle_messages', 'move_learning'}:
        return 'BATTLE_MESSAGES'
    if c == 'map_names':
        return 'MAP_NAMES'
    if c in {'trainer_names', 'trainer_classes'}:
        return 'TRAINER_NAMES_CLASSES'
    if c in {'move_descriptions', 'ability_descriptions', 'habitat_names'}:
        return 'REFERENCE_DESCRIPTIONS'
    if row['id'] in RUNTIME_OBSERVED:
        return 'NEW_GAME_REQUIRED_UI'
    if speaker and speaker.get('speaker_confidence') == 'PROVEN':
        return 'TRAINER_DIALOGUE' if speaker.get('speaker_category') == 'TRAINER_CLASS' else 'NPC_DIALOGUE'
    return 'UNKNOWN'


def priority(row, family, runtime):
    c = row['category']
    if row['id'] in RUNTIME_OBSERVED or c in {
            'menu_save', 'menu_save_prompts', 'menu_pause', 'start_menu_labels', 'menu_options'}:
        p, why = 'P0', 'Required new-game/menu/save workflow; category policy, not individual play proof.'
    elif c == 'pointer_texts' or re.search(r'legacy|unused|debug', row.get('table_name', ''), re.I):
        p, why = 'P3', 'Consumer/reachability investigation first; never exclude automatically.'
    elif family in {'MISSIONS', 'BATTLE_MESSAGES', 'MENUS_SETTINGS', 'NPC_DIALOGUE', 'TRAINER_DIALOGUE', 'MAP_NAMES'}:
        p, why = 'P1', 'Family policy: interactions/progression support; mandatory scene unproved.'
    elif c in {'scripts', 'plain_scripts'}:
        p, why = 'P1', 'Provisional dialogue discovery queue; story/NPC/sidequest/postgame attribution UNKNOWN.'
    else:
        p, why = 'P2', 'Reference/names/remaining used-text policy; inspect reachability, do not exclude.'
    return {'level': p, 'reason': why, 'verification':
            'VERIFIED_REQUIRED_NEW_GAME' if runtime == 'HUMAN_OBSERVED_CURRENT' else 'PRIORITY_UNVERIFIED'}


def normalized_reuse_key(text):
    """Layout-only candidate key. Keeps all non-layout tokens; no semantic claim."""
    return re.sub(r'\s+', ' ', strip_hma_quotes(text).replace('\\l', ' ').replace('\\p', ' ')).strip()


def duplicate_groups(rows, key):
    groups = defaultdict(list)
    for r in rows:
        groups[key(r['original'])].append(r['id'])
    duplicate = [ids for ids in groups.values() if len(ids) > 1]
    return {'distinct_keys': len(groups), 'duplicate_groups': len(duplicate),
            'members': sum(map(len, duplicate)),
            'redundant_members': sum(len(g) - 1 for g in duplicate), 'groups': duplicate,
            'merge_authorized': False}


def persist_new(payloads, root=ROOT):
    """Preflight all four outputs. Never overwrite even one existing artifact."""
    assert set(payloads) == set(OUTPUTS) and set(payloads) <= PHASE7A_PATHS
    rendered = {p: (json.dumps(d, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
                for p, d in payloads.items()}
    exists = {p: (root / p).exists() for p in rendered}
    if any(exists.values()):
        if not all(exists.values()):
            raise FileExistsError('Partial Phase 7A output set; stop without writes.')
        for p, data in rendered.items():
            if (root / p).read_bytes() != data:
                raise FileExistsError('Conflicting existing artifact: ' + p)
        return 'VERIFIED_EXISTING_IDENTICAL'
    for p, data in rendered.items():
        path = root / p
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream:
            stream.write(data)
    return 'CREATED_NEW'


def build_inventory():
    protection_before = protected_snapshot()
    inputs = {}

    def read(path):
        data = (ROOT / path).read_bytes()
        inputs[path] = sha(data)
        return json.loads(data)

    canonical = read(CANONICAL)['entries']
    raw = read(RAW)['entries']
    current = index_unique(read(APPLIED)['entries'], 'applied')
    selection_data = read(SELECTION)
    selection = index_unique(selection_data['entries'], 'selection')
    phase5 = index_unique(read('out/ja-phase5f-final-controlfix.json')['entries'], 'Phase 5 base')
    historical = index_unique(read('out/phase6/ja_phase6_final_cleanup_inventory_v3.json')['entries'], 'historical holds')
    phase5_audit = index_unique(read('out/ja-phase5f-remaining-audit.json')['entries'], 'Phase 5 audit')
    speakers_data = read('out/phase6/ja_phase6_speaker_attribution.json')
    speakers = {r['id']: r for r in speakers_data['entries'] + speakers_data['applied_candidates']}
    phase5_context = index_unique(read('tests/fixtures/ja_phase5_selection.json')['entries'], 'Phase 5 selection')
    scope = set(selection) | set(phase5)
    canonical_ids = {r['id'] for r in canonical}
    assert len(current) == 2403 and len(scope) == 3177
    assert not set(selection) & set(phase5) and set(current) <= scope <= canonical_ids
    phase6_remaining = scope - set(current)
    assert len(phase6_remaining) == 774 and phase6_remaining <= set(historical)
    reviews, review_files = {}, {}
    for n in range(1, 5):
        path = f'out/phase6/ja_phase6_cleanup_batch0{n}_reviewed.json'
        for r in read(path)['entries']:
            assert r['id'] not in reviews
            reviews[r['id']], review_files[r['id']] = r, path
    assert len(reviews) == 569 and len(set(reviews) & set(current)) == 142
    assert len(set(reviews) & phase6_remaining) == 427
    assert len(phase6_remaining - set(reviews)) == 347
    source = (ROOT / 'rom/unbound.gba').read_bytes()
    base = (ROOT / BASE_ROM).read_bytes()
    assert hashlib.md5(source).hexdigest() == '9cad8e771940e7f7094d13911552cef0'
    assert sha(base) == BASE_SHA and len(base) == len(source) == 0x2000000
    mapping = reconcile(canonical, raw, source)
    relocations = {}
    for path in MAPS:
        relocations.update({r['id']: r for r in read(path)['relocations']})
    injector, codec = runpy.run_path(str(ROOT / '005_hybrid_injector.py')), Charmap('ja')
    verified, placements = {}, Counter()
    for key, r in current.items():
        dest = int(relocations[key]['new_offset'], 16) if key in relocations else offset(r)
        payload = encoded(injector, codec, r, r['translated'])
        assert base[dest:dest + len(payload)] == payload, ('Applied payload mismatch', key)
        for pointer in r.get('pointer_sources', []):
            owner = int(pointer, 16)
            assert int.from_bytes(base[owner:owner + 4], 'little') == 0x08000000 + dest, key
        placement = 'RELOCATED' if key in relocations else 'IN_PLACE'
        placements[placement] += 1
        verified[key] = {'placement': placement, 'destination_offset': f'0x{dest:08X}',
            'destination_gba_address': f'0x{dest + 0x08000000:08X}', 'payload_bytes': len(payload),
            'payload_sha256': sha(payload), 'payload_and_recorded_owners_match': True}
    entries = []
    for source_row in canonical:
        key = source_row['id']
        a, h, review = current.get(key), historical.get(key), reviews.get(key)
        old5 = phase5_audit.get(key) if key not in current else None
        active_review = review if key not in current else None
        reasons, candidate, candidate_source, complete_review = [], None, None, False
        if a:
            assert a['original'] == source_row['original'] and offset(a) == offset(source_row)
            candidate, candidate_source, complete_review = a['translated'], APPLIED, True
        elif active_review:
            assert active_review['original_english'] == source_row['original']
            reasons = [active_review['primary_hold']] + active_review['secondary_holds']
            reasons = [x for x in reasons if x]
            candidate = active_review.get('candidate_japanese') or active_review.get('controlfixed_japanese')
            candidate_source = review_files[key]
            complete_review = active_review['review_status'] == 'confirmed' and bool(candidate)
        elif key in phase6_remaining:
            assert h['original'] == source_row['original']
            reasons = [h['previous_primary_hold']] + h['previous_secondary_holds']
            facts = h['normalized_technical_facts']
            reasons += facts.get('raw_hold_reasons', [])
            if h['resolution_class'] == 'KEEP_ENGLISH':
                reasons = ['english_retention_proposed_not_approved_for_full_localization']
            candidate, candidate_source = h.get('candidate_japanese'), 'out/phase6/ja_phase6_final_cleanup_inventory_v3.json'
        elif old5:
            assert old5['original'] == source_row['original']
            classes = {'B': 'UNKNOWN_BUFFER', 'C': 'text_slot_capacity_and_renderer_consumer',
                       'D': 'raw_prefix_or_control_boundary', 'E': 'renderer_consumer',
                       'F': 'CONTEXT_REQUIRED', 'H': 'renderer_consumer_non_text_unproved'}
            reasons = [classes.get(old5['classification'], 'other')]
        # Do not promote absent or incomplete historic candidates to reviewed wording.
        if not candidate and not a and h and h.get('candidate_japanese'):
            candidate, candidate_source = h['candidate_japanese'], 'out/phase6/ja_phase6_final_cleanup_inventory_v3.json'
        kept = bool(old5 and old5['disposition'] == 'resolved_keep_latin_staff_name')
        context_hold = bool(not a and not kept and (
            (active_review and active_review['review_status'] == 'needs_context') or
            (not active_review and h and h['resolution_class'] in {'CLAUDE_CONTEXT', 'CLAUDE_GLOSSARY'}) or
            (old5 and old5['classification'] in {'B', 'F'})))
        technical_hold = bool(not a and not kept and any(x not in {
            'review_needs_context', 'CONTEXT_REQUIRED', 'INCOMPLETE_TRANSLATION'} for x in reasons))
        if a:
            status = 'APPLIED_JAPANESE'
        elif kept:
            status = 'KEEP_ENGLISH_APPROVED'
        elif context_hold:
            status = 'CONTEXT_HOLD'
        elif technical_hold:
            status = 'TECHNICAL_HOLD'
        elif candidate:
            status = 'TRANSLATED_NOT_APPLIED'
        else:
            status = 'UNTRANSLATED'
        translation_state = ('APPLIED_REVIEWED' if a else 'REVIEWED_NOT_APPLIED' if complete_review
                             else 'DRAFT_UNAPPROVED' if candidate else 'NONE')
        ctx = selection.get(key) or phase5_context.get(key) or {}
        runtime = ('HUMAN_OBSERVED_CURRENT' if key in RUNTIME_OBSERVED else
                   'SOURCE_RUNTIME_REPORTED_BRANCH_UNVERIFIED' if ctx.get('runtime_confidence') == 'A' else
                   'OWNER_ONLY_RUNTIME_UNVERIFIED' if source_row.get('pointer_sources') or source_row.get('table_name') else 'UNKNOWN')
        speaker = speakers.get(key)
        family = classify(source_row, speaker)
        address, size = offset(source_row), source_row['byte_length']
        data = source[address:address + size]
        decoded = decode_pcs(source, address, size)
        assert decoded.text == strip_hma_quotes(source_row['original']), ('Source boundary mismatch', key)
        controls = control_features(data)
        body = strip_hma_quotes(source_row['original'])
        clean = re.sub(r'\[[^\]]+\]|\\\\[0-9A-Fa-f]{2}|\\CC[0-9A-Fa-f]+|\\[a-z?.+>]', '', body)
        potential = []
        if controls.get('FD') or '\\\\' in body:
            potential += ['unknown buffer', 'dynamic name width']
        if controls.get('FA'):
            potential.append('FA semantic boundary')
        if not source_row.get('pointer_sources') and not source_row.get('table_name'):
            potential.append('incomplete pointer ownership')
        if source_row.get('no_relocation') or not source_row.get('is_pointer_based'):
            potential.append('text slot capacity')
        if decoded.raw_count:
            potential.append('glyph/font')
        reasons = list(dict.fromkeys(reasons))
        hold_record = {'primary_reason': reasons[0] if reasons else None,
            'secondary_reasons': reasons[1:], 'primary_family': hold_family(reasons[0]) if reasons else None,
            'all_families': sorted({hold_family(x) for x in reasons}),
            'context_hold': context_hold, 'technical_hold': technical_hold,
            'provenance': review_files.get(key) if active_review else candidate_source if h else
                          'out/ja-phase5f-remaining-audit.json' if old5 else None,
            'potential_unassessed_gates': sorted(set(potential))}
        entry = {'id': key, 'source': dict(source_row), 'category': source_row['category'],
            'content_family': family, 'content_family_evidence':
                'Extractor category/table ownership or PROVEN direct speaker binding; UNKNOWN otherwise.',
            'original': source_row['original'], 'rom_offset': f'0x{address:08X}',
            'gba_address': f'0x{address + 0x08000000:08X}', 'slot_size': size,
            'source_bytes_sha256': sha(data), 'source_terminated': decoded.terminated,
            'source_raw_count': decoded.raw_count,
            'pointer_ownership': {'recorded_sources': source_row.get('pointer_sources', []),
                'table_name': source_row.get('table_name'), 'table_index': source_row.get('table_index'),
                'no_relocation': source_row.get('no_relocation', False),
                'completeness': 'NOT_GLOBALLY_REPROVEN',
                'no_pointer_does_not_prove_unused': True},
            'status': status, 'translation_state': translation_state,
            'injection_state': 'APPLIED_BYTE_VERIFIED' if a else 'NOT_APPLIED',
            'candidate_japanese': candidate, 'candidate_source': candidate_source,
            'candidate_is_approved_for_injection': bool(a),
            'english_retention_reason': old5['disposition'] if kept else None,
            'phase6_scope': key in scope, 'phase6_remaining': key in phase6_remaining,
            'cleanup_569_member': key in reviews, 'holds': hold_record,
            'runtime': {'state': runtime, 'evidence': ctx.get('runtime_evidence') or ctx.get('runtime_reason'),
                'speaker_confidence': speaker.get('speaker_confidence') if speaker else 'UNKNOWN',
                'speaker_id': speaker.get('speaker_id') if speaker and speaker.get('speaker_confidence') == 'PROVEN' else None,
                'unused_proven': False},
            'priority': priority(source_row, family, runtime),
            'source_controls': controls, 'protected_tokens': semantic_tokens(body),
            'source_visible_characters': len(clean.replace('\n', '')),
            'control_complexity': 'HIGH' if controls.get('FD') or controls.get('FA') or controls.get('FC')
                                  else 'MEDIUM' if controls else 'LOW',
            'renderer_group': ctx.get('renderer_group') or ctx.get('renderer') or renderer_for(source_row['category']),
            'renderer_runtime_verification': 'NOT_CLAIMED_BY_CENSUS',
            'applied_rom_verification': verified.get(key),
            'unreferenced_candidate': not bool(source_row.get('pointer_sources')),
            'legacy_debug_candidate': bool(re.search(r'legacy|unused|debug', source_row.get('table_name', ''), re.I))}
        entries.append(entry)
    by_id = index_unique(entries, 'inventory')
    raw_rows = []
    for r in raw:
        target = WARNING if r['id'] == OLD_WARNING else r['id'] if r['id'] in by_id else None
        raw_rows.append({'id': r['id'], 'source': dict(r), 'canonical_id': target,
                         'mapping_status': 'UNRESOLVED_MAPPING' if target is None else
                                           'PROVEN_SAME_STRING' if r['id'] == OLD_WARNING else 'IDENTICAL_ID',
                         'status': by_id[target]['status'] if target else 'UNKNOWN'})
    status_counts = dict(sorted(Counter(r['status'] for r in entries).items()))
    translation_counts = dict(sorted(Counter(r['translation_state'] for r in entries).items()))
    exact, layout = duplicate_groups(canonical, lambda x: x), duplicate_groups(canonical, normalized_reuse_key)
    stats = []
    for category in sorted({r['category'] for r in entries}):
        rows = [r for r in entries if r['category'] == category]
        remaining = [r for r in rows if r['status'] not in {'APPLIED_JAPANESE', 'KEEP_ENGLISH_APPROVED'}]
        stats.append({'category': category, 'target_count': len(rows),
            'applied': sum(r['injection_state'] == 'APPLIED_BYTE_VERIFIED' for r in rows),
            'approved_english': sum(r['status'] == 'KEEP_ENGLISH_APPROVED' for r in rows),
            'with_existing_draft_or_review': sum(r['translation_state'] != 'NONE' for r in rows),
            'untranslated_no_draft': sum(r['translation_state'] == 'NONE' and r['status'] != 'KEEP_ENGLISH_APPROVED' for r in rows),
            'reviewed_not_applied': sum(r['translation_state'] == 'REVIEWED_NOT_APPLIED' for r in rows),
            'draft_not_applied': sum(r['translation_state'] == 'DRAFT_UNAPPROVED' for r in rows),
            'technical_hold': sum(r['holds']['technical_hold'] for r in rows),
            'context_hold': sum(r['holds']['context_hold'] for r in rows),
            'average_visible_characters': round(sum(r['source_visible_characters'] for r in rows) / len(rows), 2),
            'total_visible_characters': sum(r['source_visible_characters'] for r in rows),
            'control_complexity': dict(sorted(Counter(r['control_complexity'] for r in rows).items())),
            'priorities': dict(sorted(Counter(r['priority']['level'] for r in rows).items())),
            'remaining': len(remaining), 'claude_batch_size': 120 if category in {'scripts', 'plain_scripts', 'battle_messages', 'gendered_dialogue_fragments'} else 200,
            'batches_upper_bound': ceil(len(remaining) / (120 if category in {'scripts', 'plain_scripts', 'battle_messages', 'gendered_dialogue_fragments'} else 200)),
            'context_proof_required_before_scene_grouping': category in {'scripts', 'plain_scripts'}})
    blockers = {family: {'primary_ids': [], 'affected_ids': [], 'potential_unassessed_ids': []}
                for family in HOLD_FAMILIES}
    hold_rows = []
    for r in entries:
        h = r['holds']
        if h['context_hold'] or h['technical_hold']:
            hold_rows.append({'id': r['id'], 'status': r['status'], **h})
            blockers[h['primary_family']]['primary_ids'].append(r['id'])
            for family in h['all_families']:
                blockers[family]['affected_ids'].append(r['id'])
        if r['status'] not in {'APPLIED_JAPANESE', 'KEEP_ENGLISH_APPROVED'}:
            for family in h['potential_unassessed_gates']:
                blockers[family]['potential_unassessed_ids'].append(r['id'])
    for value in blockers.values():
        value.update({name.replace('_ids', '_count'): len(value[name]) for name in tuple(value)})
    graphics = read('graphics/manifest.json')
    coverage = {
        'text_census_is_not_full_game_coverage': True,
        'graphics': {'verified_assets': len(graphics['assets']), 'complete': graphics['coverage']['complete'],
            'remaining': graphics['coverage']['remaining'], 'evidence': 'graphics/manifest.json',
            'rejected_keyboard_candidate': 'naming_screen_keyboard is explicitly unverified, not an accepted ROM offset.'},
        'paths_requiring_further_audit': [
            {'path': 'Name input keyboard/validation/save encoding', 'status': 'UNASSESSED', 'inside_25044': 'NOT_PROVEN'},
            {'path': 'Computed menus, buffer writers and special-generated text', 'status': 'PARTIAL', 'inside_25044': 'NOT_PROVEN_COMPLETE'},
            {'path': 'CFRU battle grammar fragments/suffixes and dynamic substitutions', 'status': 'PARTIAL', 'inside_25044': 'NOT_PROVEN_COMPLETE'},
            {'path': 'Script-external UI, indexed/packed proprietary tables', 'status': 'PARTIAL', 'inside_25044': 'NOT_PROVEN_COMPLETE'},
            {'path': 'Postgame, side events and main story scene attribution', 'status': 'UNASSESSED_AT_FULL_GAME_SCALE', 'inside_25044': 'PARTIAL_UNKNOWN'}]}
    assert protected_snapshot() == protection_before
    assert sha((ROOT / BASE_ROM).read_bytes()) == BASE_SHA
    summary = {'canonical_entries': len(entries), 'raw_entries': len(raw_rows),
        'applied': len(current), 'phase6_scope': len(scope), 'phase6_remaining': len(phase6_remaining),
        'cleanup_569_applied': 142, 'cleanup_569_remaining': 427,
        'other_phase6_remaining': 347, 'outside_phase6_scope': len(canonical_ids - scope),
        'status_counts': status_counts, 'translation_state_counts': translation_counts,
        'context_hold': sum(r['holds']['context_hold'] for r in entries),
        'technical_hold': sum(r['holds']['technical_hold'] for r in entries),
        'hold_union': len(hold_rows), 'unused_proven': 0,
        'no_recorded_pointer_candidates': sum(r['unreferenced_candidate'] for r in entries),
        'legacy_debug_table_candidates': sum(r['legacy_debug_candidate'] for r in entries),
        'independent_wording_lower_bound_conditional': exact['distinct_keys'],
        'physical_translation_work_units_provisional': [25044, 25045],
        'remaining_canonical_rom_targets': sum(s['remaining'] for s in stats),
        'untranslated_no_draft': sum(s['untranslated_no_draft'] for s in stats),
        'with_existing_draft_or_review': sum(s['with_existing_draft_or_review'] for s in stats),
        'reviewed_not_applied': sum(s['reviewed_not_applied'] for s in stats),
        'draft_not_applied': sum(s['draft_not_applied'] for s in stats),
        'claude_batches_category_upper_bound': sum(s['batches_upper_bound'] for s in stats),
        'unapplied_visible_characters': sum(r['source_visible_characters'] for r in entries if r['status'] not in {'APPLIED_JAPANESE', 'KEEP_ENGLISH_APPROVED'})}
    metadata = {'phase': '7A', 'scope': 'Inventory/planning only; no translation or ROM mutation',
        'baseline_rom': BASE_ROM, 'baseline_sha256_before_and_after': BASE_SHA,
        'source_rom_md5': hashlib.md5(source).hexdigest(), 'input_sha256': dict(sorted(inputs.items())),
        'protected_files': {'count': protection_before['files'], 'aggregate_sha256': protection_before['aggregate_sha256'],
            'expected_hashes_changed': 0, 'safety_gates_changed': 0, 'unexpected_files': 0},
        'validation': {'duplicate_canonical_id': 0, 'duplicate_raw_id': 0, 'missing_id': 0,
            'original_changes': 0, 'glossary_changes': 0, 'rom_changes': 0,
            'applied_payload_mismatches': 0, 'applied_recorded_pointer_mismatches': 0,
            'applied_placements': dict(sorted(placements.items())), 'phase6_unaccounted_holds': 0},
        'summary': summary,
        'state_contract': 'status is one mutually-exclusive work bucket. Translation/injection/hold/runtime axes are separate; context and technical flags may overlap. DRAFT is not a confirmed translation. Potential unassessed gates are not confirmed holds. KEEP_ENGLISH needs an existing explicit disposition; five historic unchanged UI labels are proposals, not approved full-localization exceptions.'}
    inventory = {'metadata': metadata, 'mapping': mapping, 'entries': entries, 'raw_entries': raw_rows,
        'supplemental_unresolved_ids': [SUFFIX],
        'phase6_remaining_ids': sorted(phase6_remaining), 'duplicates': {'exact_original': exact,
        'layout_only_reuse_candidates': layout, 'semantic_equivalence': 'UNASSESSED; do not infer from address, keywords or layout-only matching.'},
        'extractor_coverage_gaps': coverage}
    category_stats = {'summary': summary, 'categories': stats,
        'content_families': dict(sorted(Counter(r['content_family'] for r in entries).items()))}
    queue = {'summary': {'counts': dict(sorted(Counter(r['priority']['level'] for r in entries).items())),
        'unverified_priority': sum(r['priority']['verification'] == 'PRIORITY_UNVERIFIED' for r in entries),
        'includes_applied_for_runtime_coverage': True, 'no_P2_P3_exclusions': True},
        'queues': {p: [{'id': r['id'], 'status': r['status'], **r['priority']} for r in entries
                      if r['priority']['level'] == p] for p in ('P0', 'P1', 'P2', 'P3')},
        'supplemental': [{'id': SUFFIX, 'priority': 'P3', 'status': 'UNRESOLVED_MAPPING'}],
        'batch_policy': {'dialogue_max_entries': 120, 'simple_tables_max_entries': 200,
            'high_control_or_unknown_buffers_max_entries': 40,
            'group_only_by': 'Proven script/map/scene/consumer bindings; never ROM adjacency alone.',
            'official_names': 'Use existing ja-hrkt deterministic localization first in a future phase; no requests/translation now.',
            'estimates_exclude': 'Additional graphics/undiscovered text and repeat review cycles; high-complexity splitting raises batch count.'}}
    technical = {'summary': {'known_unique_hold_entries': len(hold_rows), 'phase6_remaining': 774,
            'primary_total': sum(v['primary_count'] for v in blockers.values()),
            'secondary_counts_are_non_additive': True, 'raw_extra_unresolved': 1},
        'families': blockers, 'entries': hold_rows, 'mapping_obligations': [mapping['interior_candidate']],
        'completion_gates': ['Investigate all reachable text plus coverage gaps', 'Confirm kana-only wording and scoped official names',
            'Safely inject every target; justified explicit English exceptions', 'Preserve controls/buffer page state/all owners',
            'Actual renderer widths, capacity and transactional relocation checks', 'mGBA route/save/battle/menu/progression regression',
            'Reproducible BPS-only distribution; never distribute ROM assets']}
    return dict(zip(OUTPUTS, (inventory, category_stats, queue, technical)))


def planning_observations(payloads):
    """Additional read-only estimates; no edits to the frozen census outputs."""
    from lib.pokeapi_localizer import CATEGORY_SPECS
    from lib.unbound_free_space import VETTED_FREE_SPACE_RANGES

    rows = payloads[OUTPUTS[0]]['entries']
    remaining = [r for r in rows if r['status'] not in {'APPLIED_JAPANESE', 'KEEP_ENGLISH_APPROVED'}]
    latin_drafts = [r['id'] for r in remaining if r['translation_state'] == 'DRAFT_UNAPPROVED'
                    and not re.search(r'[\u3040-\u30ff]', r['candidate_japanese'])]
    batch_total = 0
    for category in {r['category'] for r in remaining}:
        selected = [r for r in remaining if r['category'] == category]
        high = sum(r['control_complexity'] == 'HIGH' for r in selected)
        normal_size = 120 if category in {'scripts', 'plain_scripts', 'battle_messages', 'gendered_dialogue_fragments'} else 200
        batch_total += ceil(high / 40) + ceil((len(selected) - high) / normal_size)
    injector = runpy.run_path(str(ROOT / '005_hybrid_injector.py'))
    blocks = injector['build_free_blocks']((ROOT / BASE_ROM).read_bytes(), [r['source'] for r in rows],
        injector['DEFAULT_MIN_FREE_RUN'], injector['DEFAULT_MIN_ADDRESS'], VETTED_FREE_SPACE_RANGES)
    return {'latin_only_unapproved_draft_ids': latin_drafts,
        'kana_draft_not_applied': sum(r['translation_state'] == 'DRAFT_UNAPPROVED' for r in remaining) - len(latin_drafts),
        'no_kana_candidate_including_latin_proposals': sum(r['translation_state'] == 'NONE' for r in remaining) + len(latin_drafts),
        'pokeapi_category_candidates_not_guaranteed_localizable': sum(r['category'] in CATEGORY_SPECS for r in remaining),
        'control_sensitive_batch_scenario': batch_total,
        'fresh_vetted_free_blocks': len(blocks),
        'fresh_vetted_free_bytes': sum(b.end - b.start for b in blocks),
        'no_recorded_pointer_or_legacy_candidate_union': sum(r['unreferenced_candidate'] or r['legacy_debug_candidate'] for r in rows)}


def main():
    payloads = build_inventory()
    result = persist_new(payloads)
    protected_snapshot()
    assert sha((ROOT / BASE_ROM).read_bytes()) == BASE_SHA
    print(result)
    print(json.dumps(payloads[OUTPUTS[0]]['metadata']['summary'], ensure_ascii=False, indent=2))
    print(json.dumps(planning_observations(payloads), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
