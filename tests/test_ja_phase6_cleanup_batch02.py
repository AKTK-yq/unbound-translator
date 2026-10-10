"""Batch 02 gates: bad metadata, semantic timing, widths and ROM writes fail."""
from copy import deepcopy
from collections import Counter
import hashlib
import runpy

import pytest

from lib.fa_control import join_segments, reconstruct_reviewed_segments
from lib.translation_glossary import load_glossary
from scripts import build_ja_phase6_cleanup_batch02 as m


@pytest.fixture(scope='module')
def data():
    return m.read(m.OUT / (m.PREFIX + 'reviewed.json'))


@pytest.fixture(scope='module')
def records(data):
    return {x['id']: x for x in data['entries']}


def test_review_identity_and_speaker_groups():
    review, batch = m.read(m.REVIEW), m.read(m.BATCH)['entries']
    manifest = m.read(m.FIX / 'ja_phase6_cleanup_batch_manifest.json')
    voice = m.read(m.FIX / (m.PREFIX + 'voice_audit.json'))
    result = m.validate_review(review, batch, manifest, voice)
    assert result['count'] == 142 and result['context_unique'] == 49
    assert result['status_counts'] == {'confirmed': 93, 'needs_context': 49}
    assert len(result['proven_groups']) == 7
    assert sum(map(len, result['proven_groups'].values())) == 9
    for field, value in [('original', 'changed'), ('previous_candidate', 'changed'),
                         ('speaker_confidence', 'PROVEN'), ('protected_tokens', ['[player]'])]:
        bad = deepcopy(review)
        bad[0][field] = value
        with pytest.raises(AssertionError):
            m.validate_review(bad, batch, manifest, voice)
    bad = deepcopy(review)
    bad[-1] = bad[0]
    with pytest.raises(AssertionError):
        m.validate_review(bad, batch, manifest, voice)


def test_unique_context_not_sum_of_memberships(data, records):
    v = data['metadata']['validation']
    held_ids = {x['id'] for x in records.values() if x['review_status'] == 'needs_context'}
    assert len(held_ids) == 49
    assert set().union(*map(set, v['buffer_memberships'].values())) == held_ids
    assert sum(map(len, v['buffer_memberships'].values())) > len(held_ids)
    assert all(records[key]['decision'] == 'HOLD' for key in held_ids)


def test_fa_55_and_control_populations(data, records):
    rows = list(records.values())
    fa = [x for x in rows if x['FA_state']['present']]
    assert len(fa) == 55
    assert sum(x['FA_state']['completed_segments'] for x in fa) == 38
    assert sum(x['review_status'] == 'needs_context' for x in fa) == 17
    assert data['metadata']['validation']['confirmed_source_controls'] == {'FE': 153, 'FB': 126, 'FA': 67}
    assert data['metadata']['validation']['all_source_controls'] == {'FE': 238, 'FB': 196, 'FA': 92}
    for x in fa:
        if x['review_status'] == 'confirmed':
            r = x['review']
            assert r['reviewed_japanese'] == ''
            rebuilt = reconstruct_reviewed_segments(m.strip_hma_quotes(r['original']), m.segments(r), r['translated_segments'])
            assert rebuilt == x['candidate_japanese']
            if x['decision'] == 'APPLY':
                assert x['FA_state']['layout_status'] == 'LAYOUT_PASS'


@pytest.mark.parametrize('key', list(m.SPECIAL_FA.values()))
def test_special_fa_semantic_boundary_fails_even_with_controls_equal(key, records):
    x = records[key]
    assert x['control_state']['state'] == 'PASS'
    assert x['semantic_voice_state']['state'] == 'HOLD'
    assert x['decision'] == 'HOLD'
    assert 'CONTROL_BOUNDARY_REVIEW_REQUIRED' in x['all_holds']
    with pytest.raises(AssertionError):
        m.assert_safe_record(x)


@pytest.mark.parametrize('key', list(m.TROPHIES.values()))
def test_trophy_terminal_fa_fixed_but_semantic_timing_held(key, records):
    x = records[key]
    assert len(x['review']['translated_segments']) == 3
    assert x['control_state']['source_boundaries'] == x['control_state']['target_boundaries'] == ['FE', 'FA']
    assert x['review']['translated_segments'][-1].endswith('！')
    assert not x['candidate_japanese'].endswith('\\l')
    assert x['decision'] == 'HOLD'
    assert 'before FA' in x['semantic_voice_state']['boundary_note']


@pytest.mark.parametrize('key', ['scr_1F07D7B', 'scr_1F13575'])
def test_negation_and_daytime_cannot_cross_fa_despite_pixel_fit(key, records):
    x = records[key]
    assert x['width_state']['max_total'] <= 208
    assert x['control_state']['state'] == 'PASS'
    assert x['decision'] == 'HOLD'
    assert 'CONTROL_BOUNDARY_REVIEW_REQUIRED' in x['all_holds']
    with pytest.raises(AssertionError):
        m.assert_safe_record(x)


def test_width_208_not_screen_240_and_rom_anchors(records):
    rom = (m.ROOT / 'rom/unbound.gba').read_bytes()
    proof = m.renderer_evidence(rom)
    assert proof['field_physical_pixels'] == 208
    broken = bytearray(rom)
    broken[0x3A73BF] = 30
    with pytest.raises(AssertionError):
        m.renderer_evidence(broken)
    for x in records.values():
        if x['width_state'].get('max_total', 0) > 208:
            assert x['decision'] == 'HOLD'
    voice = records['scr_1F0AC39']
    assert voice['width_state']['max_total'] == 167
    assert 'あなたは' not in voice['candidate_japanese'] and 'ようね' not in voice['candidate_japanese']
    assert voice['decision'] == 'APPLY'
    assert m.normal_line_widths_with_placeholders('[japanese]' + voice['review']['previous_candidate'] + '[latin]', {})['max_total'] == 247


def test_13_official_warnings_verified_separately(records):
    assert sum(bool(x['review']['official_name_warnings']) for x in records.values()) == 13
    for key in ['scr_1F09D6C', 'scr_1F09E0D', 'scr_1F09E94']:
        a = records[key]['official_name_state']
        assert a['state'] == 'PASS'
        assert any('flower' in x.get('context_proof', '') for x in a['records'])
    assert records['scr_1F0A83E']['official_name_state']['state'] == 'HOLD'
    assert records['scr_1F0B2DB']['official_name_state']['state'] == 'HOLD'
    assert records['scr_1F0A708']['official_name_state']['records'][-1]['official_claim'] is False
    assert records['scr_1F0D8AA']['candidate_japanese'] == 'Sankren fimbulvetr!'
    with pytest.raises(AssertionError):
        m.official_record('item', 'gracidea', 'Another Flower', 'グラシデアのはな')


def test_scope_gap_10_and_no_glossary_extension(records):
    assert sum(bool(x['review']['glossary_scope_gaps']) for x in records.values()) == 10
    for key in ['scr_1F07929', 'scr_1F082E2', 'scr_1F0E49D']:
        assert records[key]['glossary_state']['gap_state'] == 'ALREADY_IN_SCOPE'
    assert records['scr_1F0A273']['glossary_state']['gap_state'] == 'INDEPENDENT_OFFICIAL_ENTITY'
    assert records['scr_1F0C46E']['glossary_state']['state'] == 'HOLD'
    assert all(x['glossary_state']['scope_extensions'] == x['glossary_state']['automatic_replacements'] == 0 for x in records.values())
    p = m.read(m.OUT / (m.PREFIX + 'scope_extension_proposal.json'))
    assert len(p['entries']) == p['count'] == 9
    g = load_glossary(m.ROOT / 'glossaries/ja.json', expected_language='ja')
    assert len(g.terms) == 292


def test_relocation_seven_exact_owner_inventory(records):
    moves = {x['id'] for x in records.values() if x['pointer_state']['relocation_needed']}
    assert moves == set(m.RELOCATIONS.values())
    for key in moves:
        x = records[key]
        assert x['encoded_bytes'] > x['source_slot']
        assert not x['pointer_state']['fixed'] and not x['pointer_state']['no_relocation']
        if x['decision'] == 'APPLY':
            assert not x['pointer_state']['missing'] and not x['pointer_state']['interior_hits']
    assert records['scr_1F0734A']['decision'] == records['scr_1F0DD47']['decision'] == 'HOLD'


def test_completed_translation_raw_control_and_pcs_checks(records):
    for x in records.values():
        if x['decision'] != 'APPLY':
            continue
        m.assert_safe_record(x)
        text = x['controlfixed_japanese']
        assert not m.HAN.search(text)
        raw = m.Charmap('ja').encode(text)
        assert len(raw) == x['encoded_bytes']
        assert x['control_state']['state'] == 'PASS'
        assert x['control_state']['source_controls_hex'] == x['control_state']['target_controls_hex']
    bad = m.read(m.REVIEW)[72]
    original = m.Charmap('ja').encode(m.strip_hma_quotes(bad['original']))
    fix = runpy.run_path(str(m.ROOT / '004_controlfix_translations.py'))
    altered = deepcopy(bad)
    altered['translated_segments'][0] = altered['translated_segments'][0].replace('\\.', '')
    text = join_segments(m.segments(altered), altered['translated_segments'])
    fixed = fix['ensure_japanese_page'](text)[0]
    assert m.control_audit(altered, text, fixed, original)['state'] == 'HOLD'


@pytest.mark.parametrize('field,value', [('semantic_voice_state', {'state': 'HOLD'}),
                                      ('buffer_state', {'state': 'UNKNOWN_CALLER_DEPENDENT'}),
                                      ('official_name_state', {'state': 'HOLD'}),
                                      ('glossary_state', {'state': 'HOLD'}),
                                      ('all_holds', ['CLAUDE_VOICE_REVIEW_REQUIRED'])])
def test_tampered_semantic_or_technical_approval_rejected(records, field, value):
    good = deepcopy(next(x for x in records.values() if x['decision'] == 'APPLY'))
    m.assert_safe_record(good)
    good[field] = value
    with pytest.raises(AssertionError):
        m.assert_safe_record(good)


def test_controlfix_two_passes_exact_bytes_and_fa_approval(records):
    safe = m.read(m.OUT / (m.PREFIX + 'safe_input.json'))['entries']
    fixed = m.OUT / (m.PREFIX + 'controlfix.json')
    twice = m.OUT / (m.PREFIX + 'controlfix_twice.json')
    assert fixed.read_bytes() == twice.read_bytes()
    assert m.read(fixed)['entries'] == safe
    for e in safe:
        if records[e['id']]['FA_state']['present']:
            assert e['fa_placement_policy'] == 'require_segments' and e['fa_layout_reviewed']
    for name in ['controlfix_report.json', 'controlfix_twice_report.json']:
        stats = m.read(m.OUT / (m.PREFIX + name))['stats']
        assert stats['remaining_control_mismatches'] == stats['fa_placement_review_required'] == 0


def test_strict_full_incremental_and_prior_2329(data):
    count = data['metadata']['applied']
    for name, expected in [('full_dry_run_map.json', 2329+count), ('incremental_dry_run_map.json', count), ('map.json', count)]:
        mapping = m.read(m.OUT / (m.PREFIX + name))
        m.assert_strict_map(mapping, mapping, expected)
        assert all(v == 0 for k, v in mapping['stats'].items() if k.startswith('skipped_') and isinstance(v, int))
    combined = m.read(m.OUT / (m.PREFIX + 'combined_controlfix.json'))['entries']
    assert combined[:2329] == m.baseline()
    assert data['metadata']['phase6_remaining_holds'] == 848-count


def test_binary_all_prior_payloads_and_unexpected_byte_failure(data):
    before, after = m.BASE.read_bytes(), m.ROM.read_bytes()
    mapping = m.read(m.OUT / (m.PREFIX + 'map.json'))
    safe = m.read(m.OUT / (m.PREFIX + 'controlfix.json'))['entries']
    audit = m.audit_binary(before, after, safe, mapping, m.baseline())
    assert audit['existing_2329_text_and_pointers_unchanged'] and audit['voice_pass1_three_revisions_preserved']
    assert audit['unexpected_byte_count'] == 0
    assert audit['relocation_count'] == 5
    assert hashlib.sha256(before).hexdigest() == m.BASE_SHA
    bad = bytearray(after)
    bad[0xAC] ^= 1
    with pytest.raises(AssertionError, match='Unexpected binary'):
        m.audit_binary(before, bad, safe, mapping, m.baseline())
    for name, sha in data['metadata']['input_hashes'].items():
        assert m.digest((m.ROOT / name).read_bytes()) == sha


def test_runtime_qa_positive_and_negative_cases():
    qa = m.read(m.FIX / (m.PREFIX + 'runtime_qa.json'))
    assert len(qa['entries']) == len({x['id'] for x in qa['entries']}) == 20
    assert any(x['apply_status'] == 'APPLY' and x['expected_controls'].get('FA') for x in qa['entries'])
    assert any(x['relocation'] for x in qa['entries'])
    assert any(x['speaker_confidence'] == 'PROVEN' for x in qa['entries'])
    assert any(x['id'] == 'scr_1F0A708' and x['apply_status'] == 'APPLY' for x in qa['entries'])
    assert all(x['pointer_owners'] and x['source_gba_address'] for x in qa['entries'])
    assert {x['id'] for x in qa['entries'] if x['apply_status'] == 'HOLD'} == set(m.SPECIAL_FA.values())


def test_existing_artifacts_not_replaced(tmp_path):
    path = tmp_path / 'result.json'
    m.persist(path, {'state': 'reviewed'})
    contents = path.read_bytes()
    m.persist(path, {'state': 'reviewed'})
    with pytest.raises(AssertionError):
        m.persist(path, {'state': 'changed'})
    assert path.read_bytes() == contents
