"""Fail-closed regression tests for the immutable 53-entry technical audit."""
from copy import deepcopy
import hashlib

import pytest

from lib.pcs_text import Charmap, decode_pcs
from scripts import build_ja_phase7_story_batch01 as m


@pytest.fixture(scope='module')
def data():
    return m.analyze()


def test_exact_53_ids_and_metadata(data):
    review = m.read(m.REVIEW)
    handoff = m.read(m.HANDOFF)['entries']
    rows = data['holds']['entries']
    assert len(rows) == len({r['id'] for r in rows}) == 53
    assert [r['id'] for r in rows] == [r['id'] for r in review] == [r['id'] for r in handoff]
    assert [r['batch_index'] for r in rows] == list(range(53))
    assert [r['reviewed_japanese'] for r in rows] == [r['reviewed_text_joined'] for r in review]
    assert all(r['translation_status'] == 'confirmed' for r in rows)
    a = data['validation']['input_accounting']
    assert a['duplicates'] == a['missing'] == a['previous_candidate_changes'] == 0
    assert a['originals_rom_verified'] == 53


@pytest.mark.parametrize('mutation', ('duplicate', 'original', 'previous', 'scene', 'speaker', 'priority'))
def test_input_tampering_fails(mutation):
    review, handoff = deepcopy(m.read(m.REVIEW)), m.read(m.HANDOFF)['entries']
    if mutation == 'duplicate':
        review[-1]['id'] = review[0]['id']
    elif mutation == 'original':
        review[0]['original'] += '!'
    elif mutation == 'previous':
        review[0]['previous_candidate'] = 'changed'
    elif mutation == 'scene':
        review[0]['scene_id'] = []
    elif mutation == 'speaker':
        review[0]['speaker_confidence'] = 'PROVEN'
    else:
        review[0]['priority_confidence'] = 'PROVEN'
    with pytest.raises(AssertionError):
        m.validate_inputs(review, handoff, m.read(m.MANIFEST), (m.ROOT/'rom/unbound.gba').read_bytes())


def test_fa_21_180_39_rom_derived_and_notes12(data):
    rows = data['holds']['entries']
    fa = [r for r in rows if r['fa_segmented']]
    assert len(fa) == 21
    assert sum(len(r['original_wait_segments_rom_derived']) for r in fa) == 180
    assert sum(r['control_status']['source_sequence'].count('fa') for r in rows) == 39
    assert tuple(r['batch_index'] for r in fa if r['fa_phrase_note_present']) == m.PHRASE_INDICES
    assert all(r['fa_independent_note'] for r in fa)
    assert sum(r['fa_semantic_verdict'] == 'FA_SEMANTIC_BOUNDARY_REVIEW_REQUIRED' for r in fa) == 3


@pytest.mark.parametrize('index,english,japanese', ((31, 3, 2), (40, 2, 1)))
def test_early_complete_light_of_ruin_is_blocking(data, index, english, japanese):
    r = data['holds']['entries'][index]
    assert r['completed_name_reveal']['english_completed_name_phase'] == english
    assert r['completed_name_reveal']['japanese_completed_name_phase'] == japanese
    assert r['completed_name_reveal']['early_by_waits'] == 1
    assert r['fa_semantic_verdict'] == 'FA_SEMANTIC_BOUNDARY_REVIEW_REQUIRED'
    assert 'HOLD_SEMANTIC:FA_SEMANTIC_BOUNDARY_REVIEW_REQUIRED' in m.technical_reasons(r)


def test_dark_force_and_nuance_judgments_are_independent(data):
    rows = data['holds']['entries']
    assert rows[1]['fa_semantic_verdict'] == 'FA_SEMANTIC_BOUNDARY_REVIEW_REQUIRED'
    assert tuple(r['batch_index'] for r in rows if r['semantic_state']['status'] == 'CLAUDE_REVIEW_REQUIRED') == (19, 40, 49)
    assert all(rows[i]['semantic_state']['note'] for i in m.NUANCE_INDICES)
    assert rows[47]['semantic_state']['status'] == 'PASS_WITH_NUANCE_NOTE'


def test_name_buffer10_producer_is_not_all_values_proof(data):
    rows = data['holds']['entries']
    assert tuple(r['batch_index'] for r in rows if r['buffer_status']['tokens']) == m.NAME_INDICES
    for i in m.NAME_INDICES:
        r = rows[i]
        assert not r['buffer_status']['all_values_and_writer_proven']
        assert r['buffer_status']['local_keyboard_bound_normal_latin'] == 42
        assert '[latin][player][japanese]' in r['page_controlled_candidate_only']
        assert r['width_status']['normal_spacing0']['unknown_placeholder_codes'] == ['0x01']
        assert any(x.startswith('HOLD_BUFFER:') for x in m.technical_reasons(r))
    evidence = data['validation']['renderer_evidence']
    assert evidence['FD01_dispatch_owner'] == 'ROM 00231E74 / GBA 08231E74'
    assert evidence['naming']['max_chars_excluding_terminator'] == 7
    assert evidence['naming']['confidence'] == 'PROVEN_LOCAL_NAMING_INPUT_ONLY'


def test_scope_gap_exact14_and_no_extension(data):
    rows = data['holds']['entries']
    assert tuple(r['batch_index'] for r in rows if r['glossary_status']['scope_gaps']) == m.GAP_INDICES
    for r in rows:
        assert not r['glossary_status']['approved_match_violations']
        for g in r['glossary_status']['scope_gaps']:
            assert g['current_entry_id'] == r['id']
            assert not g['entry_in_approved_scope']
            assert g['approved_scope'] and g['independent_evidence']
    assert data['validation']['glossary_changes'] == 0


def test_official_names2_entity_not_inferred_from_api(data):
    rows = data['holds']['entries']
    assert tuple(r['batch_index'] for r in rows if r['official_name_status']['issues']) == (19, 32)
    assert rows[19]['official_name_status']['state'].startswith('HOLD_')
    assert rows[32]['official_name_status']['state'].startswith('HOLD_')
    e = data['validation']['official_lexical_and_table_evidence']
    assert e['rom_tables']['Prison Bottle']['id'] == 'tbl_item_names_00538_EB919B'
    assert e['rom_tables']['Rift Cave']['id'] == 'tbl_map_names_00051_3EEF2D'
    assert e['api_names']['Cacnea']['ja_hrkt'] == 'サボネア'
    assert e['api_names']['Cut']['ja_hrkt'] == 'いあいぎり'
    assert e['api_names']['Prison Bottle']['ja_hrkt'] == 'いましめのツボ'
    assert not e['api_names']['Prison Bottle']['narrative_entity_proven_by_api']


def test_relocation21_exact_bytes_length_and_owners(data):
    rows = data['holds']['entries']
    assert [r['batch_index'] for r in rows if r['pointer_status']['relocation_needed']] == [21]
    p = rows[21]['pointer_status']
    assert p['source_rom_offset'] == '0x01F46217'
    assert p['slot_size'] == 19 and p['encoded_length'] == 23
    assert p['recorded'] == p['whole_rom_exact_hits'] == ['0x01E82C9B']
    assert p['missing'] == p['stale'] == p['interior_hits'] == []
    assert not p['actual_relocation_approved']
    assert rows[21]['technical_status'] == 'HOLD_RENDERER'


def test_raw_interior_values_are_not_proven_pointer_owners(data):
    rows = data['holds']['entries']
    assert sum(bool(r['pointer_status']['interior_hits']) for r in rows) == 29
    for r in rows:
        assert r['pointer_status']['raw_candidates_are_not_proven_owners']
        for p in r['pointer_status']['unresolved_reference_samples']:
            assert p['structural_consumer'] == 'UNKNOWN'
            assert len(p['surrounding_bytes'].split()) == 20
    assert rows[50]['pointer_status']['missing'] == ['0x01057ED1']


def test_renderer_actual_chain_font_variants_not_global208(data):
    e = data['validation']['renderer_evidence']
    assert e['std6_script'] == 'ROM 01E7D5DA / GBA 09E7D5DA'
    assert e['font_variants'] == [4, 5, 2]
    assert e['conditional_japanese_letter_spacing'] == 1
    assert e['candidate_physical_width'] == 208 and e['entry_live_usable_width'] is None
    for r in data['holds']['entries']:
        assert not r['consumer_status']['proved_live_profile_or_conservative_bound']
        assert any(x.startswith('HOLD_RENDERER:') for x in m.technical_reasons(r))
        assert not r['width_status']['actual_fit_approved']


def test_claiming_consumer_alone_does_not_bypass_width_gate(data):
    r = deepcopy(data['holds']['entries'][23])
    r['consumer_status']['proved_live_profile_or_conservative_bound'] = True
    assert 'HOLD_WIDTH:actual_renderer_fit_unproved' in m.technical_reasons(r)


def test_exact_normal_glyph_metrics_spacing_and_controls(data):
    s = data['validation']['summary']
    assert s['normal_spacing0_max_static'] == 200
    assert s['normal_spacing1_max_static_diagnostic'] == 220
    assert len(s['spacing1_candidate_208_exceedances']) == 21
    assert m.normal_widths('[japanese]こんにちは[latin]')['max_static_with_spacing'] == 50
    assert m.normal_widths('[japanese]こんにちは[latin]', 1)['max_static_with_spacing'] == 55
    assert m.normal_widths('[japanese] 、。[latin]', 1)['max_static_with_spacing'] != 30
    assert m.normal_widths('[japanese]こ\nん\\lに\n\nち[latin]', 1)['line_static_with_spacing'] == [11, 11, 11, 11]


def test_existing_english_envelope_gate_not_relaxed(data):
    rows = data['holds']['entries']
    assert [r['batch_index'] for r in rows if r['width_status']['old_fa_source_envelope_exceeded']] == [0, 6, 12, 15, 24, 28, 29, 32, 49]
    for r in rows:
        if r['width_status']['old_fa_source_envelope_exceeded']:
            assert 'HOLD_WIDTH:existing_fa_source_envelope_gate_retained' in m.technical_reasons(r)


def test_control_tokens_boundary_and_pcs_all53(data):
    for r in data['holds']['entries']:
        c = r['control_status']
        assert c['state'] == 'PASS' and c['segment_tokens_match']
        assert c['source_sequence'] == c['candidate_sequence_ignoring_only_language_switches']
        assert c['kanji'] == c['encode_errors'] == 0
        raw = Charmap('ja').encode(r['page_controlled_candidate_only'])
        assert len(raw) == c['encoded_bytes']
        assert Charmap('ja').encode(decode_pcs(raw, max_length=len(raw)).text) == raw


def test_control_failure_cannot_be_approved(data):
    r = deepcopy(data['holds']['entries'][23])
    r['control_status']['state'] = 'FAIL'
    assert m.technical_reasons(r)[0] == 'HOLD_TECHNICAL_OTHER:control_or_PCS_failure'
    with pytest.raises(UnicodeEncodeError):
        Charmap('ja').encode('[japanese]漢[latin]')


def test_controlfix_idempotency_refuses_unapproved_fa21(data):
    fix = data['validation']['controlfix']
    assert fix['byte_identical']
    assert fix['non_fa_page_only_results'] == 32 and fix['fa_refusals'] == 21
    assert fix['non_fa_candidate_encoded_byte_changes'] == 0
    assert fix['prior_2403_entries_sent_to_controlfix'] == 0
    for p in fix['passes']:
        assert p['remaining_control_mismatches'] == 0
        assert p['fa_placement_review_required'] == 21


def test_safe0_strict_empty_subset_not_53_approval(data):
    v, dry = data['validation'], data['validation']['strict_dry_run']
    assert v['summary']['safe'] == 0 and v['summary']['held'] == 53
    assert dry['status'] == 'PASS_EMPTY_SAFE_SUBSET_ONLY'
    assert dry['held_entries_attempted'] == dry['input_entries'] == 0
    assert dry['not_approval_for_53'] and dry['no_rom_written']
    mapping = {'stats': dry['stats'], 'relocations': [], 'missing_relocations': [],
               'missing_fixed_slots': [], 'runtime_patches': [], 'graphics_patches': []}
    m.assert_strict_map(mapping, mapping, 0)
    bad = deepcopy(mapping)
    bad['stats']['encode_errors'] = 1
    with pytest.raises(AssertionError):
        m.assert_strict_map(bad, bad, 0)


def test_binary_and_prior2403_baseline_unchanged(data):
    a = data['binary']
    assert a['status'] == 'NO_ROM_GENERATED_SAFE_SUBSET_EMPTY'
    assert a['output_rom'] is a['output_sha256'] is None
    assert a['baseline_sha256_before'] == a['baseline_sha256_after'] == m.BASE_SHA
    assert a['prior_applied_byte_verification']['verified_payloads'] == 2403
    assert a['prior_2403_changed'] == a['unexpected_byte_count'] == 0
    assert a['changed_offsets'] == []
    assert set(a['classified_changed_bytes'].values()) == {0}
    assert hashlib.sha256((m.ROOT/m.BASE_ROM).read_bytes()).hexdigest() == m.BASE_SHA
    assert data['validation']['summary']['phase6_remaining'] == 774


def test_runtime_qa23_holds_and_unknown_routes(data):
    qa = data['qa']
    assert qa['metadata']['count'] == 23
    indices = {r['batch_index'] for r in qa['entries']}
    assert {0, 1, 19, 20, 21, 31, 32, 40} <= indices
    assert all(not r['runtime_test_performed'] and not r['japanese_applied_this_pass'] for r in qa['entries'])
    assert all(r['actual_route_and_required_save_flags'] == 'UNKNOWN' for r in qa['entries'])


def test_exclusive_output_writer_refuses_existing_before_any_write(data, tmp_path, monkeypatch):
    monkeypatch.setattr(m, 'ROOT', tmp_path)
    first = tmp_path/m.OUTPUTS[0]
    first.parent.mkdir(parents=True)
    first.write_bytes(b'USER EXISTING REPORT')
    with pytest.raises(AssertionError):
        m.persist_new(data)
    assert first.read_bytes() == b'USER EXISTING REPORT'
    assert not (tmp_path/m.OUTPUTS[1]).exists()


def test_exact_output_registration_and_909_protection(data):
    assert set(m.OUTPUTS) | {'scripts/build_ja_phase7_story_batch01.py',
                           'tests/test_ja_phase7_story_batch01.py'} == m.PHASE7C3_PATHS
    assert not any(ch in p for p in m.PHASE7C3_PATHS for ch in '*?[')
    assert data['validation']['protected909']['files'] == 909
    assert data['validation']['protected909']['aggregate_sha256'] == m.INITIAL_SNAPSHOT
    assert not data['validation']['existing_safety_gate_changes']
