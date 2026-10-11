#!/usr/bin/env python3
"""Phase 7C-1: offline batch preparation only; no translation or ROM writes.

python scripts/build_ja_phase7_story_translation_batches.py --analyze
python scripts/build_ja_phase7_story_translation_batches.py
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lib.fa_control import parse_raw_segments
from lib.pcs_text import decode_pcs, fc_arg_count
from lib.translation_tokens import semantic_tokens, strip_hma_quotes
from scripts.build_ja_phase6_cleanup_batch03 import (
    PHASE7A_PATHS, PHASE7B_PATHS, PHASE7C1_PATHS, protected_snapshot,
)
from scripts.build_ja_phase7_inventory import BASE_ROM, BASE_SHA

OUTPUTS = (
    'out/phase7/ja_story_translation_batch_manifest.json',
    'out/phase7/ja_story_translation_batch01_for_claude.json',
    'out/phase7/ja_story_translation_style_handoff.json',
)
SCENES = 'out/phase7/ja_story_scene_index.json'
INVENTORY = 'out/phase7/ja_full_localization_inventory.json'
STYLE = 'out/phase6/ja_phase6_cleanup_translation_style_handoff.json'
VOICE = 'tests/fixtures/ja_phase6_voice_profiles_claude.json'
FA_REPORT = 'docs/ja-phase6-fa-bottleneck-investigation.md'
PLAN = 'out/phase7/ja_story_translation_batch_plan.json'
QUEUE = 'out/phase7/ja_story_priority_queue.json'
# These are concrete Phase 7B roots, not ROM-neighbor scene guesses.
INTRO_ROOTS = frozenset({
    'map_031_005_level_condition_01E702B7',
    'map_031_005_level_condition_01E702BF',
    'map_031_005_level_condition_01E702C7',
})
EARLY_MAPS = frozenset({'map_003_066', 'map_003_067', 'map_003_068'})
PRESERVED_FIELDS = (
    'id', 'category', 'original', 'candidate_japanese', 'translation_state',
    'status', 'injection_state', 'holds', 'phase6_remaining', 'rom_offset',
    'gba_address', 'slot_size', 'pointer_ownership', 'verified_source_owners',
    'reference_confidence', 'story_category',
    'story_confidence', 'story_reason', 'scene_ids', 'event_bindings',
    'speaker', 'voice_profile', 'legacy_speaker_map_labels', 'glossary_state',
    'priority', 'translation_readiness', 'translation_readiness_reason',
    'injection_readiness', 'source_controls', 'protected_tokens',
    'source_visible_characters', 'qa', 'duplicate_reuse_candidate',
)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    return json.loads((ROOT / path).read_text(encoding='utf-8'))


def serialize(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8')


def unique(rows):
    result = {x['id']: x for x in rows}
    assert len(result) == len(rows), 'Duplicate input ID'
    return result


def eligible(rows):
    result = [x for x in rows if x['priority']['level'] in {'P0', 'P1'}
              and x['translation_readiness'] == 'READY_FOR_CLAUDE']
    unique(result)
    assert len(result) == 706
    assert Counter(x['priority']['level'] for x in result) == {'P0': 467, 'P1': 239}
    assert all(x['status'] != 'APPLIED_JAPANESE' and x['injection_state'] == 'NOT_APPLIED'
               and x['current_japanese'] is None for x in result)
    assert all(x['story_category'] != 'MAIN_STORY_VERIFIED' for x in result)
    return result


def group_key(row):
    speaker = row['speaker']
    if speaker['speaker_confidence'] == 'PROVEN' and speaker.get('speaker_id'):
        key = ('PROVEN_SPEAKER', speaker['speaker_id'])
    elif row['scene_ids']:
        # Exact same proved reference set, not a cinematic/speaker assertion.
        key = ('STATIC_ROOT_SET', *sorted(row['scene_ids']))
    else:
        key = ('STRUCTURED_CATEGORY', row['category'])
    return (row['priority']['level'], *key)


def initial_rank(rows):
    if any(set(x['scene_ids']) & INTRO_ROOTS for x in rows):
        return 0
    if any(b['map_id'] in EARLY_MAPS and b.get('entry_condition', {})
           and b['entry_condition'].get('variable') == '0x00005011'
           for x in rows for b in x['event_bindings']):
        return 1
    if any(b['map_id'] == 'map_003_067' for x in rows for b in x['event_bindings']):
        return 2
    if any(b['map_id'] == 'map_003_068' for x in rows for b in x['event_bindings']):
        return 3
    return 4


def partition(rows):
    """Ordered DP: 16 x 30..60; balance text/FA work, penalize group splits.

    Priority is always the first ordering key. IDs break ties ONLY for reproducibility.
    A group is split when size/work constraints require it; every split is reported.
    """
    groups = defaultdict(list)
    for row in rows:
        groups[group_key(row)].append(row)
    keys = sorted(groups, key=lambda k: (k[0], initial_rank(groups[k]), k[1:]))
    ordered = [x for k in keys for x in sorted(groups[k], key=lambda x: x['id'])]
    n = len(ordered)
    work = [0]
    for x in ordered:
        work.append(work[-1] + x['source_visible_characters']
                    + 120 * x['source_controls'].get('FA', 0)
                    + 30 * x['source_controls'].get('FC', 0)
                    + 60 * x['source_controls'].get('FD', 0))
    # Penalize splitting an actual root/speaker group, but category is not a scene.
    def split_cost(end):
        if end == n or group_key(ordered[end - 1]) != group_key(ordered[end]):
            return 0
        return 4000000 if group_key(ordered[end])[1] != 'STRUCTURED_CATEGORY' else 2000
    target = work[-1] / 16
    dp = {(0, 0): (0, ())}
    for batch in range(1, 17):
        for end in range(batch * 30, min(batch * 60, n) + 1):
            best = None
            for start in range(max(0, end - 60), end - 29):
                previous = dp.get((batch - 1, start))
                if previous is None:
                    continue
                cost = previous[0] + ((work[end] - work[start] - target) / 10) ** 2
                cost += 100 * (end - start - n / 16) ** 2 + split_cost(end)
                candidate = (cost, (*previous[1], end))
                if best is None or candidate < best:
                    best = candidate
            if best is not None:
                dp[batch, end] = best
    assert (16, n) in dp, 'Cannot partition into sixteen bounded batches'
    batches, start = [], 0
    for end in dp[16, n][1]:
        batches.append(ordered[start:end])
        start = end
    ownership = {x['id']: i + 1 for i, b in enumerate(batches) for x in b}
    splits = []
    for key in keys:
        numbers = sorted({ownership[x['id']] for x in groups[key]})
        if len(numbers) > 1:
            splits.append({'group_key': list(key), 'entry_ids': sorted(x['id'] for x in groups[key]),
                           'batches': numbers, 'reason': '30..60 count / text-control workload; not scene chronology',
                           'is_scene_or_speaker_group': key[1] != 'STRUCTURED_CATEGORY'})
    return batches, splits


def raw_controls(raw, rom_offset):
    """PCS boundary-aware trace; arguments FA/FB/FF are never boundary bytes."""
    out, index = [], 0
    names = {0xFE: 'FE', 0xFA: 'FA', 0xFB: 'FB', 0xFC: 'FC', 0xFD: 'FD',
             0xF7: 'F7', 0xF8: 'F8', 0xF9: 'F9'}
    while index < len(raw):
        byte = raw[index]
        if byte == 0xFF:
            assert index == len(raw) - 1
            return out
        size = 2 + fc_arg_count(raw[index + 1]) if byte == 0xFC else 2 if byte in (0xFD, 0xF7, 0xF8, 0xF9) else 1
        piece = raw[index:index + size]
        assert len(piece) == size
        if byte in names:
            out.append({'kind': names[byte], 'rom_offset': f'0x{rom_offset + index:08X}',
                        'bytes': piece.hex(' '), 'token': decode_pcs(piece + b'\xff').text})
        index += size
    raise ValueError('Unterminated PCS source')


def buffers(controls, category='scripts'):
    result = []
    for control in controls:
        if control['kind'] != 'FD':
            continue
        token = control['token']
        # PCS aliases are not battle expansion semantics. No field-name inference.
        known = category != 'battle_messages' and token in {'[player]', '[rival]'}
        result.append({**control, 'semantic_type': 'UNKNOWN' if not known else
                       'PLAYER_NAME' if token == '[player]' else 'RIVAL_NAME',
                       'value_semantics_known': known, 'consumer': category,
                       'codec_label_is_not_runtime_semantics': category == 'battle_messages',
                       'writer_status': 'UNKNOWN',
                       'writer': None, 'full_value_set': None, 'maximum_width': None,
                       'page_state_after_expansion': 'REQUIRES_RUNTIME_PROOF'})
    return result


def metrics(rows, control_data):
    return {'count': len(rows),
            'english_visible_characters': sum(x['source_visible_characters'] for x in rows),
            'english_original_string_characters': sum(len(x['original']) for x in rows),
            'priority_counts': dict(sorted(Counter(x['priority']['level'] for x in rows).items())),
            'fa_entries': sum(bool(x['source_controls'].get('FA')) for x in rows),
            'fa_waits': sum(x['source_controls'].get('FA', 0) for x in rows),
            'unknown_buffer_entries': sum(any(not b['value_semantics_known'] for b in buffers(control_data[x['id']], x['category'])) for x in rows),
            'unknown_buffer_writer_entries': sum(bool(buffers(control_data[x['id']], x['category'])) for x in rows),
            'dynamic_name_entries': sum(any(b['value_semantics_known'] for b in buffers(control_data[x['id']], x['category'])) for x in rows),
            'speaker_profile_entries': sum(x['voice_profile'] is not None for x in rows),
            'category_counts': dict(sorted(Counter(x['category'] for x in rows).items()))}


def script_context(row, all_rows):
    """Previous/next text on the same witnessed static path, never ROM adjacency.

    Paths can have opaque effects and unevaluated conditions. No runtime order claim.
    """
    result = []
    for ref in row['event_references']:
        path = ref['static_path']
        for direction, positions in (('before_on_static_path', path[:-1][::-1]),):
            for pc in positions:
                matches = [(x, r) for x in all_rows for r in x['event_references']
                           if r['root_id'] == ref['root_id'] and r['command_offset'] == pc
                           and x['id'] != row['id']]
                if matches:
                    for other, other_ref in matches:
                        result.append({'id': other['id'], 'original': other['original'],
                            'current_japanese': other['current_japanese'],
                            'candidate_japanese': other['candidate_japanese'],
                            'status': other['status'], 'relation': direction,
                            'root_id': ref['root_id'], 'command_offset': pc,
                            'witness_reference': {'source': SCENES, 'entry_id': row['id'],
                                                  'event_reference_index': row['event_references'].index(ref)},
                            'runtime_sequence': 'UNVERIFIED',
                            'opaque_effect_on_path': ref['opaque_effect_on_path'],
                            'read_only_context_not_translation_target': True})
                    break
    # Reverse witness: a later message path contains this entry's command.
    for other in all_rows:
        if other['id'] == row['id']:
            continue
        for ref in row['event_references']:
            for following in other['event_references']:
                if following['root_id'] != ref['root_id']:
                    continue
                path = following['static_path']
                if ref['command_offset'] in path[:-1]:
                    between = path[path.index(ref['command_offset']) + 1:-1]
                    other_text_pcs = {r['command_offset'] for x in all_rows for r in x['event_references']
                                      if r['root_id'] == ref['root_id'] and x['id'] not in {row['id'], other['id']}}
                    if not set(between) & other_text_pcs:
                        result.append({'id': other['id'], 'original': other['original'],
                            'current_japanese': other['current_japanese'],
                            'candidate_japanese': other['candidate_japanese'], 'status': other['status'],
                            'relation': 'after_on_static_path', 'root_id': ref['root_id'],
                            'command_offset': following['command_offset'],
                            'witness_reference': {'source': SCENES, 'entry_id': other['id'],
                                                  'event_reference_index': other['event_references'].index(following)},
                            'runtime_sequence': 'UNVERIFIED',
                            'opaque_effect_on_path': following['opaque_effect_on_path'],
                            'read_only_context_not_translation_target': True})
    return list({json.dumps(x, sort_keys=True): x for x in result}.values())


def build():
    protection = protected_snapshot()
    assert sha((ROOT / BASE_ROM).read_bytes()) == BASE_SHA
    scene = read(SCENES)
    inventory = read(INVENTORY)
    by_id = unique(scene['entries'])
    old = unique(inventory['entries'])
    assert len(by_id) == len(old) == 25044 and set(by_id) == set(old)
    assert len(scene['raw_entries']) == 25045
    assert sum(x['status'] == 'APPLIED_JAPANESE' for x in by_id.values()) == 2403
    assert len(scene['phase6_remaining_ids']) == 774
    for path, expected in scene['metadata']['input_sha256'].items():
        assert sha((ROOT / path).read_bytes()) == expected, ('Phase 7B frozen input changed', path)
    selected = eligible(scene['entries'])
    ids = {x['id'] for x in selected}
    plan = read(PLAN)
    prior_ids = [i for b in plan['batches'] for i in b['entry_ids']]
    assert len(prior_ids) == len(set(prior_ids)) == 706 and set(prior_ids) == ids
    queue = read(QUEUE)
    queue_ids = {x['id'] for level in ('P0', 'P1') for x in queue['queues'][level]
                 if x['translation_readiness'] == 'READY_FOR_CLAUDE'}
    assert queue_ids == ids
    for x in selected:
        original = old[x['id']]
        for key in ('original', 'candidate_japanese', 'source_controls', 'protected_tokens', 'holds'):
            assert x[key] == original[key], (key, x['id'])
    input_paths = PHASE7A_PATHS | PHASE7B_PATHS | {STYLE, VOICE, FA_REPORT, 'glossaries/ja.json',
                    'rom/unbound.gba', BASE_ROM}
    input_paths |= {old[x['id']]['candidate_source'] for x in selected if old[x['id']]['candidate_source']}
    input_hashes = {p: sha((ROOT / p).read_bytes()) for p in sorted(input_paths)}
    source = (ROOT / 'rom/unbound.gba').read_bytes()
    control_data, segments = {}, {}
    for x in selected:
        offset, size = int(x['rom_offset'], 16), x['slot_size']
        raw = source[offset:offset + size]
        assert sha(raw) == old[x['id']]['source_bytes_sha256']
        decoded = decode_pcs(raw, max_length=size)
        assert decoded.terminated and decoded.text == strip_hma_quotes(x['original'])
        terminated = raw[:decoded.byte_length]
        control_data[x['id']] = raw_controls(terminated, offset)
        segments[x['id']] = parse_raw_segments(terminated, rom_offset=offset)
    batches, splits = partition(selected)
    all_ids = [x['id'] for b in batches for x in b]
    assert len(all_ids) == len(set(all_ids)) == 706 and set(all_ids) == ids
    metadata = {'phase': '7C-1', 'translation_started': False, 'claude_invoked': False,
                'rom_generated': False, 'existing_translation_changes': 0,
                'canonical_count': 25044, 'raw_count': 25045, 'applied_count': 2403,
                'phase6_hold_count': 774, 'baseline_rom': BASE_ROM, 'baseline_sha256': BASE_SHA,
                'protected_files': {'files': protection['files'], 'aggregate_sha256': protection['aggregate_sha256']},
                'input_sha256': input_hashes, 'main_story_verified': 0,
                'missing_ids': 0, 'duplicate_ids': 0, 'applied_target_entries': 0,
                'confidence_promotions': 0, 'unresolved_raw_mapping_preserved': scene['supplemental_unresolved_ids']}
    manifest = {'metadata': metadata, 'summary': metrics(selected, control_data),
                'algorithm': {'version': 1, 'batch_count': 16, 'min_entries': 30, 'max_entries': 60,
                    'work_score': 'visible chars + 120*FA + 30*FC + 60*FD; balanced by ordered DP',
                    'priority_first': True, 'tie_breaker': 'exact group key then stable ID, NOT story order',
                    'early_candidates': sorted(INTRO_ROOTS), 'story_chronology_proven': False},
                'batches': [{'batch_id': f'P7C_batch_{i:02d}', 'entry_ids': [x['id'] for x in b],
                            **metrics(b, control_data), 'payload_created': i == 1,
                            'injection_approved': False} for i, b in enumerate(batches, 1)],
                'group_splits': splits,
                'existing_candidate_linkage': [{
                    'id': x['id'], 'translation_state': x['translation_state'],
                    'candidate_source': old[x['id']]['candidate_source'], 'holds': x['holds'],
                    'candidate_sha256': sha(serialize(x['candidate_japanese'])),
                } for x in selected if old[x['id']]['candidate_source']],
                'buffer_context_warnings': [{
                    'id': x['id'], 'category': x['category'],
                    'buffer_metadata': buffers(control_data[x['id']], x['category']),
                    'prior_translation_readiness': x['translation_readiness'],
                    'new_injection_approval': False,
                    'required_action': 'Prove consumer/writer semantics before translating buffer-dependent meaning; return needs_context, never interpret field codec alias as a battle value',
                } for x in selected if any(not b['value_semantics_known'] for b in buffers(control_data[x['id']], x['category']))],
                'prior_plan_id_set_identical': True,
                'warning': 'Static event roots are not confirmed scenes or mandatory story. All original holds persist.'}
    prior_reviews = {p: unique(read(p)['entries']) for p in sorted(input_paths)
                     if p.startswith('out/phase6/') and p.endswith('_reviewed.json')}
    # Only rows sharing a Batch 01 root qualify as potential context.
    first_roots = {r for x in batches[0] for r in x['scene_ids']}
    related_rows = [x for x in scene['entries'] if first_roots & set(x['scene_ids'])]
    roots = {x['root_id']: x for x in scene['roots']}
    handoff_rows = []
    for x in batches[0]:
        original = old[x['id']]
        candidate_path = original['candidate_source']
        prior = prior_reviews.get(candidate_path, {}).get(x['id'])
        prior_review = prior.get('review', {}) if prior else {}
        bs = buffers(control_data[x['id']], x['category'])
        warnings = ['POINTER_OWNERSHIP_NOT_GLOBALLY_REPROVEN', 'RENDERER_CONSUMER_OR_LIVE_WIDTH_UNVERIFIED',
                    'GLOSSARY_SCOPE_GAPS_REQUIRE_ENTRY_REVIEW']
        if bs:
            warnings += ['BUFFER_WRITER_UNKNOWN', 'DYNAMIC_NAME_WIDTH_UNVERIFIED', 'BUFFER_PAGE_STATE_REQUIRES_PROOF']
        if any(not b['value_semantics_known'] for b in bs):
            warnings.append('UNKNOWN_BUFFER_VALUE_DO_NOT_GUESS')
        if x['source_controls'].get('FA'):
            warnings.append('FA_LAYOUT_AND_REVEAL_UNVERIFIED')
        if original['source'].get('no_relocation') or not original['source'].get('is_pointer_based'):
            warnings.append('FIXED_SLOT_CAPACITY_REQUIRES_COMPLETE_WORDING')
        units, wait_phase = [], 0
        for i, segment in enumerate(segments[x['id']]):
            units.append({'segment_index': i, 'source': segment['text'],
                          'after_control': segment['after_control'], 'control_offset': segment['control_offset'],
                          'protected_tokens': semantic_tokens(segment['text']), 'wait_phase': wait_phase,
                          'information_reveal': 'Original text in this input-wait phase; semantic facts not yet reviewed'})
            if segment['after_control'] in {'FA', 'FB'}:
                wait_phase += 1
        handoff_rows.append({**{key: x[key] for key in PRESERVED_FIELDS},
            'event_references': [{**{k: v for k, v in ref.items() if k != 'static_path'},
                'witness_reference': {'source': SCENES, 'entry_id': x['id'], 'event_reference_index': i},
                'static_path_sha256': sha(serialize(ref['static_path']))}
                for i, ref in enumerate(x['event_references'])],
            'previous_japanese_candidate': x['candidate_japanese'],
            'candidate_source': candidate_path, 'candidate_approved_for_injection': False,
            'prepared_source_metadata': original['source'],
            'previous_review_record': prior,
            'official_name_warnings': prior_review.get('official_name_warnings', []),
            'official_name_review_status': 'EXISTING_REVIEW_ONLY' if prior else 'NOT_NEWLY_VERIFIED',
            'unresolved_glossary_warnings': prior_review.get('unresolved_glossary_warnings', []),
            'glossary_scope_gaps': prior_review.get('glossary_scope_gaps', []),
            'source_game_confidence': 'UNKNOWN',
            'source_game_candidate': x['speaker'].get('source_game_candidate'),
            'control_order': control_data[x['id']], 'buffer_metadata': bs,
            'original_segments': segments[x['id']],
            'translation_units': units if x['source_controls'].get('FA') else None,
            'fa_review': {'required': bool(x['source_controls'].get('FA')),
                'information_reveal_timing': 'FA waits/scrolls one line; FB waits/clears; FE does not wait',
                'semantic_boundary_warning': 'Do not advance/delay important facts across FA/FB; separate review if needed',
                'layout_approval_required': bool(x['source_controls'].get('FA')),
                'live_geometry': 'UNKNOWN', 'new_semantic_approval': False},
            'renderer_metadata': {'group': original['renderer_group'],
                'runtime_verification': original['renderer_runtime_verification'], 'usable_width': None},
            'technical_warnings': warnings,
            'static_script_context': script_context(x, related_rows),
            'event_root_records': [roots[r] for r in x['scene_ids']],
            'context_rule': 'Same witnessed bytecode path only; conditions/opaque effects unproved; NOT runtime order',
        })
    handoff = {'metadata': {**metadata, 'batch_id': 'P7C_batch_01', 'count': len(handoff_rows),
                           'input_only_not_translated': True},
               'selection_reason': 'P0 first; Frozen Heights conditional prologue roots, then structurally referenced early-region candidates; NOT proven game order',
               'required_ui_already_applied_excluded': ['scr_1F0F7EC', 'scr_1F0F800', 'scr_1F0F814', 'scr_1F0FE27', 'scr_1F0FF35'],
               'style_handoff': OUTPUTS[2], 'entries': handoff_rows,
               'voice_profiles': [x['voice_profile'] for x in handoff_rows if x['voice_profile'] is not None],
               'injection_readiness': 'NOT_APPROVED_REQUIRES_EXISTING_GATES'}
    style = {'metadata': {'phase': '7C-1', 'guidance_only': True, 'translation_started': False,
                          'source_style_sha256': input_hashes[STYLE], 'source_voice_sha256': input_hashes[VOICE],
                          'fa_report_sha256': input_hashes[FA_REPORT]},
             'previous_style_handoff': read(STYLE),
             'current_rules': [
                'Kana-only. Natural Pokemon-style Japanese; preserve meaning, conditions, numbers and foreshadowing.',
                'Use verified official names and exact scoped glossary hits only. No memory-only name or scope expansion.',
                'Do not unnecessarily add first/second person. Follow the English attitude, not an invented character.',
                'PROVEN speaker identity is NOT CONFIRMED_VOICE; no canon or source-game identity from a shared name.',
                'Use an attached CONFIRMED_VOICE only as approved; other profiles are provisional or neutral guidance.',
                'Do not guess unknown buffer values or writers. Player/rival field semantics do not prove width/page safety; battle FD codec aliases do not prove field-name semantics.',
                'Preserve FE/FA/FB/FC/FD and protected tokens. No introduced page switches; controlfix owns Japanese/Latin.',
                'FA rows return one unit per original segment, same control order. Do not invent/merge boundaries.',
                'Important information crossing FA/FB needs separate semantic/reveal review; natural grammar alone is insufficient.',
                'Translation readiness is NOT injection approval. Never truncate meaning to fit unproved width or slot.',
                'Prior candidate/review is read-only evidence, not automatically approved. Preserve original confidence and holds.',
                'Static path context is not runtime chronology. No map/address proximity speaker or scene inference.',
             ],
             'output_contract': read(STYLE)['output_contract'],
             'attached_profile_policy': 'Only profiles already linked to actual Batch 01 IDs; zero invented matches',
             'existing_gates_changed': False, 'no_claude_execution': True}
    for actual in handoff_rows:
        expected = by_id[actual['id']]
        assert all(actual[key] == expected[key] for key in PRESERVED_FIELDS)
    assert {p: sha((ROOT / p).read_bytes()) for p in input_hashes} == input_hashes
    assert protected_snapshot() == protection
    return dict(zip(OUTPUTS, (manifest, handoff, style)))


def persist_new(data, root=ROOT):
    if set(data) != set(OUTPUTS) or not set(data) <= PHASE7C1_PATHS:
        raise AssertionError('Only the three exact Phase 7C-1 JSON paths are writable')
    payloads = {p: serialize(v) for p, v in data.items()}
    present = {p for p in data if (root / p).exists()}
    if present:
        if present != set(data):
            raise FileExistsError('Partial outputs; no write authorized')
        if any((root / p).read_bytes() != b for p, b in payloads.items()):
            raise FileExistsError('Conflicting output; never overwrite')
        return 'VERIFIED_EXISTING_IDENTICAL'
    for p, b in payloads.items():
        path = root / p
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as handle:
            handle.write(b)
    return 'CREATED_NEW'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--analyze', action='store_true')
    args = parser.parse_args()
    data = build()
    action = 'ANALYZED_READ_ONLY' if args.analyze else persist_new(data)
    print(json.dumps({'action': action, 'summary': data[OUTPUTS[0]]['summary'],
                      'batches': [{k: v for k, v in b.items() if k != 'entry_ids'}
                                  for b in data[OUTPUTS[0]]['batches']]}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
