"""Phase 6C-4C release gates, including deliberately unsafe counterexamples."""
from copy import deepcopy
import hashlib

import pytest

from scripts import build_ja_phase6_cleanup_batch01 as m
from lib.fa_control import reconstruct_reviewed_segments
from lib.translation_glossary import load_glossary


@pytest.fixture(scope='module')
def data():
    return m.read(m.OUT / (m.PREFIX + 'reviewed.json'))


@pytest.fixture(scope='module')
def records(data):
    return {x['id']: x for x in data['entries']}


def test_review_147_and_metadata():
    review = m.read(m.REVIEW)
    batch = m.read(m.BATCH)['entries']
    manifest = m.read(m.FIX / 'ja_phase6_cleanup_batch_manifest.json')
    assert m.validate_review(review, batch, manifest)['identity_errors'] == 0
    duplicated = deepcopy(review)
    duplicated[-1] = duplicated[0]
    with pytest.raises(AssertionError):
        m.validate_review(duplicated, batch, manifest)
    changed = deepcopy(review)
    changed[0]['protected_tokens'] = ['[player]']
    with pytest.raises(AssertionError):
        m.validate_review(changed, batch, manifest)


def test_context_unique_overlap_and_evidence():
    audit = m.context_accounting(m.read(m.REVIEW))
    assert len(audit['held_unique_ids']) == 32 and audit['membership_count'] == 33
    assert audit['overlaps'] == {'tbl_battle_messages_00081_3FBC62': ['\\\\00', '\\\\28']}
    assert audit['resolved_unique'] == 56
    assert audit['evidence_occurrences']['pret_battle_buffer_definition'] == 39
    assert audit['evidence_occurrences']['sibling_entries_applied'] == 24
    detailed = m.read(m.OUT / (m.PREFIX + 'context_verification.json'))
    assert detailed['count'] == len(detailed['entries']) == 56
    cube = next(x for x in detailed['entries'] if x['id'] == 'tbl_menu_cube_system_00003_A4E06F')
    assert len(cube['exact_existing_siblings']) == 7
    assert all(x['source_category_consistent'] for x in detailed['entries'])


def test_special_buffer_33_gate(data, records):
    ids = data['metadata']['special_33_confirmed_ids']
    assert len(ids) == len(set(ids)) == 33
    assert len(data['metadata']['special_all_37_ids']) == 37
    for key in ids:
        assert records[key]['decision'] == 'HOLD'
        assert records[key]['buffer_state']['state'] == 'UNVERIFIED'
        assert 'unbound_buffer_contract_unproved' in records[key]['all_holds']
    rom = (m.ROOT / 'rom/unbound.gba').read_bytes()
    proof = m.buffer_evidence(rom)
    assert {x['handler_address'] for x in proof['codes'].values()} == {
        '0x089BD36C', '0x089BD434', '0x089BD45C', '0x089BD462',
        '0x089BD480', '0x089BD5A0', '0x089BD5B2'}
    broken = bytearray(rom)
    broken[0xD786C] ^= 2
    with pytest.raises(AssertionError):
        m.buffer_evidence(broken)


@pytest.mark.parametrize('key', ['tbl_battle_messages_00122_3FC048',
                               'tbl_battle_messages_00185_3FC75D',
                               'tbl_battle_messages_00219_3FCAAA'])
def test_fa_completed_reconstruction_invariants(key, records):
    record = records[key]
    row = record['review']
    assert row['reviewed_japanese'] == ''
    rebuilt = reconstruct_reviewed_segments(m.strip_hma_quotes(row['original']), row['source_segments'], row['translated_segments'])
    assert rebuilt == record['candidate_japanese']
    assert m.segment_check(row, rebuilt)['state'] == 'PASS'
    assert record['FA_state']['semantic_status'] == 'COMPLETED_SEGMENTS'
    assert record['decision'] == 'HOLD'
    bad = deepcopy(row['translated_segments'])
    bad[0] += '\n'
    with pytest.raises(ValueError):
        reconstruct_reviewed_segments(m.strip_hma_quotes(row['original']), row['source_segments'], bad)
    # Preserve total tokens, but move a name across a source FE boundary.
    moved = rebuilt.replace('\\\\0F', '', 1) + '\\\\0F' if '\\\\0F' in rebuilt else rebuilt.replace('\\\\10', '', 1) + '\\\\10'
    assert m.segment_check(row, moved)['state'] == 'HOLD_BOUNDARY_OR_TOKEN_PLACEMENT'


def test_fa_unknown_00_not_completed(records):
    r = records['tbl_battle_messages_00216_3FCA49']
    assert r['decision'] == 'HOLD' and r['review_status'] == 'needs_context'
    assert r['FA_state']['layout_status'] == 'HOLD_UNKNOWN_00'


def test_cube_fixed_overflow(records):
    cube = records[m.CUBE]
    assert cube['source_slot'] == 8 and cube['encoded_bytes'] == 11
    assert cube['pointer_state']['fixed'] and cube['pointer_state']['no_relocation']
    assert 'fixed_or_no_relocation_overflow' in cube['all_holds']
    with pytest.raises(AssertionError):
        m.assert_safe_record(cube)


def test_223_is_not_static_width_and_is_held(records):
    row = records[m.WIDE]
    width = row['width_state']
    assert width['line_static'] == [10, 115]
    assert width['legacy_54px_estimate'] == [64, 223]
    assert width['physical_or_project_limit'] == 222
    assert row['decision'] == 'HOLD'
    assert '223px_estimate_dynamic_bounds_unproved' in row['all_holds']


def test_notation_meaning_entry_gate(records):
    audited = [x for x in records.values() if x['notation_audit']['required']]
    assert len(audited) == 4 and all(x['notation_audit']['approved'] for x in audited)
    assert m.notation_audit({'original': '"A & B"'}, 'A/B')['approved'] is False
    assert m.notation_audit({'original': '"Low (Faster)"'}, 'はやい')['approved'] is False
    assert records['tbl_setting_names_00008_1F4DADB']['decision'] == 'HOLD'


def test_official_names_exact_scope(records):
    named = [x for x in records.values() if x['review']['official_name_warnings']]
    assert len(named) == 6
    assert records['tbl_battle_messages_00239_3FCC39']['official_name_state']['state'] == 'HOLD'
    assert records['tbl_mission_objectives_00033_1F56736']['official_name_state']['records'][0]['entity_type'] == 'item'
    assert records['tbl_pokedex_descriptions_00013_166896A']['official_name_state']['records'][0]['entity_id'] == 75
    with pytest.raises(AssertionError):
        m.official_record('item', 'go-goggles', 'Other Goggles', 'ゴーゴーゴーグル')
    with pytest.raises(AssertionError):
        m.official_audit(records['scr_1EEA8A9']['review'], 'タポルのみだけ')


def test_glossary_does_not_extend_other_entry_scope(records):
    glossary = load_glossary(m.ROOT / 'glossaries/ja.json', expected_language='ja')
    assert len(glossary.terms) == 292
    row = records['tbl_menu_pokemon_summary_00014_419A3D']
    assert not glossary.matches('Day-Care', row['review']['category'], entry_id=row['id'])
    day = row['official_name_state']['records'][0]
    assert day['state'] == 'INDEPENDENT_PROJECT_WORDING' and not day['official_claim']
    assert all(x['glossary_state']['scope_extensions'] == 0 for x in records.values())


def test_controlfix_boundary_and_idempotency(records):
    safe = m.read(m.OUT / (m.PREFIX + 'safe_input.json'))['entries']
    assert safe == m.read(m.OUT / (m.PREFIX + 'controlfix.json'))['entries']
    assert safe == m.read(m.OUT / (m.PREFIX + 'controlfix_twice.json'))['entries']
    for entry in safe:
        r = records[entry['id']]
        assert m.segment_check(r['review'], r['candidate_japanese'])['state'] == 'PASS'
    row = records['tbl_menu_link_controls_00005_418E09']['review']
    # A wait crossing FE must fail even if the same controls are still present.
    bad = row['reviewed_japanese'].replace('\n\\qo', '\\qo\n')
    assert m.segment_check(row, bad)['state'] == 'HOLD_BOUNDARY_OR_TOKEN_PLACEMENT'


@pytest.mark.parametrize('field,value', [('buffer_state', {'state': 'UNVERIFIED'}),
                                      ('all_holds', ['known_width_overflow']),
                                      ('official_name_state', {'state': 'HOLD'}),
                                      ('control_state', {'state': 'HOLD_BOUNDARY_OR_TOKEN_PLACEMENT'}),
                                      ('notation_audit', {'approved': False})])
def test_application_gate_rejects_tampered_approval(records, field, value):
    safe = deepcopy(next(x for x in records.values() if x['decision'] == 'APPLY'))
    m.assert_safe_record(safe)
    safe[field] = value
    with pytest.raises(AssertionError):
        m.assert_safe_record(safe)


def test_existing_2261_and_strict_binary(data):
    safe = m.read(m.OUT / (m.PREFIX + 'controlfix.json'))['entries']
    mapping = m.read(m.OUT / (m.PREFIX + 'map.json'))
    before, after = m.BASE.read_bytes(), m.ROM.read_bytes()
    result = m.audit_binary(before, after, safe, mapping, m.baseline())
    assert result['existing_2261_text_and_pointers_unchanged']
    assert result['unexpected_byte_count'] == 0
    assert result['in_place_count'] == 48 and result['relocation_count'] == 20 and result['pointer_writes'] == 33
    assert result['output_sha256'] == '02c3fcb7a488e6620a274491d5490bd3339eda6935f69973f1b083e67932533c'
    assert data['metadata']['japanese_applied_total'] == 2329
    tampered = bytearray(after)
    tampered[0xAC] ^= 1
    with pytest.raises(AssertionError, match='Unexpected binary'):
        m.audit_binary(before, tampered, safe, mapping, m.baseline())


def test_full_and_incremental_strict_zero_errors():
    for filename, count in [('full_dry_run_map.json', 2329), ('incremental_dry_run_map.json', 68), ('map.json', 68)]:
        mapping = m.read(m.OUT / (m.PREFIX + filename))
        m.assert_strict_map(mapping, mapping, count)
        assert all(value == 0 for key, value in mapping['stats'].items() if key.startswith('skipped_') and isinstance(value, int))
        assert mapping['used_reclaimed_text_bytes'] == 0
    assert m.read(m.OUT / (m.PREFIX + 'incremental_dry_run_map.json'))['relocations'] == m.read(m.OUT / (m.PREFIX + 'map.json'))['relocations']


def test_runtime_qa_and_protected_inputs():
    qa = m.read(m.FIX / (m.PREFIX + 'runtime_qa.json'))
    assert len(qa['entries']) == len({x['id'] for x in qa['entries']}) == 20
    assert any(x['apply_status'] == 'APPLY' and x['expected_controls'].get('FB') for x in qa['entries'])
    assert any(x['relocation'] for x in qa['entries'])
    assert any(x['apply_status'] == 'HOLD' and x['expected_controls'].get('FA') for x in qa['entries'])
    hashes = m.read(m.FIX / 'ja_phase6_cleanup_batch_manifest.json')['metadata']['protected_files_sha256']
    for name, expected in hashes.items():
        assert hashlib.sha256((m.ROOT / name).read_bytes()).hexdigest() == expected


def test_existing_output_never_overwritten(tmp_path):
    path = tmp_path / 'audit.json'
    m.persist(path, {'state': 'reviewed'})
    original = path.read_bytes()
    m.persist(path, {'state': 'reviewed'})
    with pytest.raises(AssertionError, match='Existing artifact differs'):
        m.persist(path, {'state': 'different'})
    assert path.read_bytes() == original
