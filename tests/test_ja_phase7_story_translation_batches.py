"""Phase 7C-1 handoff invariants; no translation/injection approval implied."""
from collections import Counter
from copy import deepcopy

import pytest

from lib.fa_control import join_segments
from lib.translation_tokens import strip_hma_quotes
from scripts import build_ja_phase7_story_translation_batches as m


@pytest.fixture(scope='module')
def data():
    return m.build()


@pytest.fixture(scope='module')
def scene():
    return m.read(m.SCENES)


def test_exact_population_and_prior_plan(data, scene):
    manifest = data[m.OUTPUTS[0]]
    ids = [i for b in manifest['batches'] for i in b['entry_ids']]
    expected = m.eligible(scene['entries'])
    assert len(ids) == len(set(ids)) == 706
    assert set(ids) == {x['id'] for x in expected}
    assert set(ids) == {i for b in m.read(m.PLAN)['batches'] for i in b['entry_ids']}
    assert manifest['summary']['priority_counts'] == {'P0': 467, 'P1': 239}
    assert manifest['metadata']['applied_target_entries'] == 0


def test_sixteen_bounded_batches_priority_first(data, scene):
    batches = data[m.OUTPUTS[0]]['batches']
    assert len(batches) == 16
    assert all(30 <= b['count'] == len(b['entry_ids']) <= 60 for b in batches)
    by_id = m.unique(scene['entries'])
    levels = [by_id[i]['priority']['level'] for b in batches for i in b['entry_ids']]
    assert levels == sorted(levels)
    assert [b['payload_created'] for b in batches] == [True] + [False] * 15


def test_partition_independent_of_input_order(scene):
    rows = m.eligible(scene['entries'])
    first, split = m.partition(rows)
    second, other_split = m.partition(list(reversed(rows)))
    assert [[x['id'] for x in b] for b in first] == [[x['id'] for x in b] for b in second]
    assert split == other_split


def test_large_group_split_is_explicit_and_minimal(data):
    splits = data[m.OUTPUTS[0]]['group_splits']
    scene_splits = [s for s in splits if s['is_scene_or_speaker_group']]
    assert len(scene_splits) == 1
    assert len(scene_splits[0]['entry_ids']) == 72
    assert scene_splits[0]['batches'] == [1, 2]
    assert 'not scene chronology' in scene_splits[0]['reason']


def test_batch01_only_actual_payload(data):
    manifest, handoff = data[m.OUTPUTS[0]], data[m.OUTPUTS[1]]
    assert len(handoff['entries']) == handoff['metadata']['count'] == 53
    assert [x['id'] for x in handoff['entries']] == manifest['batches'][0]['entry_ids']
    assert set(data) == set(m.OUTPUTS)
    assert handoff['injection_readiness'] == 'NOT_APPROVED_REQUIRES_EXISTING_GATES'
    assert all(x['injection_readiness'] == handoff['injection_readiness'] for x in handoff['entries'])


def test_original_candidate_holds_confidences_controls_preserved(data, scene):
    by_id = m.unique(scene['entries'])
    for actual in data[m.OUTPUTS[1]]['entries']:
        old = by_id[actual['id']]
        assert all(actual[k] == old[k] for k in m.PRESERVED_FIELDS)
        assert actual['previous_japanese_candidate'] == old['candidate_japanese']
        assert not actual['candidate_approved_for_injection']
        assert actual['source_game_confidence'] == 'UNKNOWN'


def test_prepared_metadata_and_candidate_sources_preserved(data):
    inv = m.unique(m.read(m.INVENTORY)['entries'])
    for row in data[m.OUTPUTS[1]]['entries']:
        old = inv[row['id']]
        assert row['prepared_source_metadata'] == old['source']
        assert row['candidate_source'] == old['candidate_source']
        assert row['previous_japanese_candidate'] == old['candidate_japanese']
    links = data[m.OUTPUTS[0]]['existing_candidate_linkage']
    assert len(links) == 74
    for link in links:
        assert link['holds'] == inv[link['id']]['holds']
        assert link['candidate_sha256'] == m.sha(m.serialize(inv[link['id']]['candidate_japanese']))


def test_existing_review_is_read_only_evidence(data):
    rows = [x for x in data[m.OUTPUTS[1]]['entries'] if x['previous_review_record'] is not None]
    assert len(rows) == 3
    for row in rows:
        expected = m.unique(m.read(row['candidate_source'])['entries'])[row['id']]
        assert row['previous_review_record'] == expected
        assert row['official_name_warnings'] == expected['review'].get('official_name_warnings', [])
        assert row['glossary_scope_gaps'] == expected['review'].get('glossary_scope_gaps', [])


def test_fa_segments_and_reveal_not_auto_approved(data):
    for row in data[m.OUTPUTS[1]]['entries']:
        segments = row['original_segments']
        assert join_segments(segments) == strip_hma_quotes(row['original'])
        boundaries = [x['kind'] for x in row['control_order'] if x['kind'] in {'FE', 'FA', 'FB'}]
        assert boundaries == [x['after_control'] for x in segments if x['after_control']]
        assert Counter(boundaries) == Counter({k: v for k, v in row['source_controls'].items() if k in {'FE', 'FA', 'FB'}})
        if row['source_controls'].get('FA'):
            assert row['fa_review']['layout_approval_required']
            assert not row['fa_review']['new_semantic_approval']
            units = row['translation_units']
            assert len(units) == len(segments)
            phase = 0
            for unit, segment in zip(units, segments):
                assert unit['source'] == segment['text'] and unit['after_control'] == segment['after_control']
                assert unit['wait_phase'] == phase
                if segment['after_control'] in {'FA', 'FB'}:
                    phase += 1
        else:
            assert row['translation_units'] is None


def test_fc_arguments_not_mistaken_for_boundaries():
    raw = bytes.fromhex('FC 04 FA FB FE FC 08 FF FD 06 FE BB FA BC FB BD FF')
    controls = m.raw_controls(raw, 0x1234)
    assert [c['kind'] for c in controls] == ['FC', 'FC', 'FD', 'FE', 'FA', 'FB']
    assert controls[0]['bytes'] == 'fc 04 fa fb fe'
    assert [c['after_control'] for c in m.parse_raw_segments(raw)] == ['FE', 'FA', 'FB', None]


def test_battle_alias_is_not_field_name_semantics():
    controls = m.raw_controls(bytes.fromhex('FD 06 FD 05 FF'), 0)
    battle = m.buffers(controls, 'battle_messages')
    assert all(x['semantic_type'] == 'UNKNOWN' and not x['value_semantics_known'] for x in battle)
    assert all(x['codec_label_is_not_runtime_semantics'] for x in battle)
    field = m.buffers(controls, 'scripts')
    assert field[0]['semantic_type'] == 'RIVAL_NAME'
    assert field[0]['writer_status'] == 'UNKNOWN' and field[0]['maximum_width'] is None


def test_buffer_metrics_and_retained_ready_warning(data):
    manifest = data[m.OUTPUTS[0]]
    assert manifest['summary']['unknown_buffer_entries'] == 13
    assert manifest['summary']['unknown_buffer_writer_entries'] == 64
    warnings = manifest['buffer_context_warnings']
    assert len(warnings) == len({x['id'] for x in warnings}) == 13
    assert all(x['category'] == 'battle_messages' and x['prior_translation_readiness'] == 'READY_FOR_CLAUDE'
               and not x['new_injection_approval'] for x in warnings)
    assert manifest['batches'][0]['unknown_buffer_entries'] == 0
    for row in data[m.OUTPUTS[1]]['entries']:
        if row['buffer_metadata']:
            assert 'BUFFER_WRITER_UNKNOWN' in row['technical_warnings']
            assert 'DYNAMIC_NAME_WIDTH_UNVERIFIED' in row['technical_warnings']


def test_no_invented_voice_profile_or_story_promotion(data):
    manifest, handoff = data[m.OUTPUTS[0]], data[m.OUTPUTS[1]]
    assert manifest['summary']['speaker_profile_entries'] == 0
    assert handoff['voice_profiles'] == []
    assert all(x['speaker']['speaker_confidence'] == 'UNKNOWN' and x['voice_profile'] is None for x in handoff['entries'])
    assert all(x['story_category'] == 'MAIN_STORY_CANDIDATE' and x['priority']['confidence'] == 'PROVISIONAL'
               for x in handoff['entries'])
    assert manifest['metadata']['main_story_verified'] == manifest['metadata']['confidence_promotions'] == 0


def test_context_is_witnessed_not_rom_neighborhood(data, scene):
    by_id = m.unique(scene['entries'])
    for row in data[m.OUTPUTS[1]]['entries']:
        for ref in row['event_references']:
            link = ref['witness_reference']
            original = by_id[link['entry_id']]['event_references'][link['event_reference_index']]
            assert ref['static_path_sha256'] == m.sha(m.serialize(original['static_path']))
            assert all(ref[k] == v for k, v in original.items() if k != 'static_path')
        for context in row['static_script_context']:
            assert context['runtime_sequence'] == 'UNVERIFIED'
            assert context['read_only_context_not_translation_target']
            link = context['witness_reference']
            witness = by_id[link['entry_id']]['event_references'][link['event_reference_index']]
            assert witness['root_id'] == context['root_id']
            assert context['command_offset'] in witness['static_path']
            assert context['original'] == by_id[context['id']]['original']


def test_initial_candidates_and_already_applied_ui_excluded(data, scene):
    handoff = data[m.OUTPUTS[1]]
    ids = {x['id'] for x in handoff['entries']}
    assert {'scr_1F113ED', 'scr_1F11594', 'scr_1F1184B', 'scr_1F11864', 'scr_1F11CFD'} <= ids
    assert not ids & set(handoff['required_ui_already_applied_excluded'])
    by_id = m.unique(scene['entries'])
    assert all(by_id[i]['status'] == 'APPLIED_JAPANESE' for i in handoff['required_ui_already_applied_excluded'])
    assert all(x['renderer_metadata']['usable_width'] is None for x in handoff['entries'])


def test_protected_sources_and_baseline_unchanged(data):
    meta = data[m.OUTPUTS[0]]['metadata']
    assert meta['protected_files']['files'] == 909
    assert m.protected_snapshot()['aggregate_sha256'] == meta['protected_files']['aggregate_sha256']
    assert m.sha((m.ROOT / m.BASE_ROM).read_bytes()) == m.BASE_SHA
    for path, expected in meta['input_sha256'].items():
        assert m.sha((m.ROOT / path).read_bytes()) == expected


def test_exact_persistence_and_no_overwrite(data, tmp_path):
    assert m.persist_new(data, tmp_path) == 'CREATED_NEW'
    before = {p: (tmp_path / p).read_bytes() for p in m.OUTPUTS}
    assert m.persist_new(data, tmp_path) == 'VERIFIED_EXISTING_IDENTICAL'
    conflict = deepcopy(data)
    conflict[m.OUTPUTS[0]]['metadata']['phase'] = 'NOT_AUTHORIZED'
    with pytest.raises(FileExistsError):
        m.persist_new(conflict, tmp_path)
    assert before == {p: (tmp_path / p).read_bytes() for p in m.OUTPUTS}


def test_partial_and_unlisted_output_rejected(data, tmp_path):
    path = tmp_path / m.OUTPUTS[1]
    path.parent.mkdir(parents=True)
    path.write_bytes(b'old protected bytes')
    with pytest.raises(FileExistsError):
        m.persist_new(data, tmp_path)
    assert path.read_bytes() == b'old protected bytes'
    assert not (tmp_path / m.OUTPUTS[0]).exists()
    with pytest.raises(AssertionError):
        m.persist_new({**data, 'out/phase7/unlisted.json': {}}, tmp_path)


def test_deterministic_build_json_parse_and_stored_outputs(data):
    again = m.build()
    for path in m.OUTPUTS:
        expected = m.serialize(data[path])
        assert m.serialize(again[path]) == expected
        assert m.serialize(m.read(path)) == expected
        assert (m.ROOT / path).read_bytes() == expected


def test_style_preserved_and_no_execution(data):
    style = data[m.OUTPUTS[2]]
    assert style['previous_style_handoff'] == m.read(m.STYLE)
    assert not style['existing_gates_changed'] and style['no_claude_execution']
    assert style['output_contract'] == m.read(m.STYLE)['output_contract']
    assert len(data[m.OUTPUTS[1]]['voice_profiles']) == 0
