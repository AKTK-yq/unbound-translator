"""Phase 6C-4H immutable-input and independent semantic/ROM gates."""
from collections import Counter
from copy import deepcopy
import runpy

import pytest

from lib.fa_control import join_segments
from lib.pcs_text import Charmap, decode_pcs
from scripts import build_ja_phase6_cleanup_batch03 as m


@pytest.fixture(scope='module')
def data():
    return m.read(m.OUT / (m.PREFIX + 'reviewed.json'))


@pytest.fixture(scope='module')
def rows(data):
    return data['entries']


def test_accounting_and_metadata(data):
    result = m.validate_review(m.read(m.REVIEW), m.read(m.BATCH)['entries'],
                              m.read(m.FIX / 'ja_phase6_cleanup_batch_manifest.json'),
                              m.read(m.FIX / (m.PREFIX + 'voice_audit.json')))
    assert result['ids'] == 140 and result['confirmed'] == 112 and result['context_unique'] == 28
    assert result['duplicates'] == result['missing'] == 0
    assert result['speaker_confidence'] == {'UNKNOWN': 129, 'PROVEN': 3, 'PLAUSIBLE': 8}
    assert len(result['proven_groups']) == 2
    assert sum(map(len, result['proven_groups'].values())) == 3
    assert data['metadata']['baseline_applied'] == 2357


@pytest.mark.parametrize('field,value', [('original', 'wrong'), ('previous_candidate', 'wrong'),
                                        ('speaker_confidence', 'PROVEN'), ('protected_tokens', ['[player]']),
                                        ('hold_reason', {})])
def test_changed_source_metadata_rejected(field, value):
    review = deepcopy(m.read(m.REVIEW))
    review[0][field] = value
    with pytest.raises(AssertionError):
        m.validate_review(review, m.read(m.BATCH)['entries'],
                          m.read(m.FIX / 'ja_phase6_cleanup_batch_manifest.json'),
                          m.read(m.FIX / (m.PREFIX + 'voice_audit.json')))


def test_context_memberships_are_28_unique(data, rows):
    memberships = data['metadata']['validation']['buffer_memberships']
    assert len(memberships['[buffer1]']) == 25 and len(memberships['[buffer2]']) == 3
    assert set(memberships['[buffer1]']) & set(memberships['[buffer2]']) == {rows[19]['id']}
    assert len(set().union(*map(set, memberships.values()))) == 27
    assert rows[68]['review_status'] == 'needs_context'
    assert all(x['decision'] == 'HOLD' for x in rows if x['review_status'] == 'needs_context')


def test_fa_accounting_and_full_semantic_coverage(rows):
    fa = [x for x in rows if x['FA_state']['present']]
    complete = [x for x in fa if x['review_status'] == 'confirmed']
    assert len(fa) == 76 and len(complete) == 63
    assert sum(len(x['review']['translated_segments']) for x in complete) == 501
    assert all(x['semantic_voice_state']['method'].startswith('Manual') for x in complete)
    for x in complete:
        assert x['control_state']['state'] == 'PASS'
        assert x['control_state']['source_boundaries'] == x['control_state']['target_boundaries']
        assert x['control_state']['per_segment_tokens_preserved']
        assert join_segments(m.previous.segments(x['review']), x['review']['translated_segments']) == x['candidate_japanese']


@pytest.mark.parametrize('index', m.PHRASE_INDICES)
def test_phrase_notes_are_independent_audits(index, rows):
    x = rows[index]
    assert x['FA_state']['phrase_note'] and x['control_state']['state'] == 'PASS'
    if index in m.PHRASE_PASS:
        assert x['semantic_voice_state']['state'] == 'PASS'
        assert x['semantic_voice_state']['checkpoint'] == m.PHRASE_PASS[index]
    else:
        assert x['decision'] == 'HOLD' and 'FA_SEMANTIC_REVIEW_REQUIRED' in x['all_holds']


@pytest.mark.parametrize('index', (109, 132))
def test_claimed_timing_fixes_do_not_approve_whole_entry(index, rows):
    x = rows[index]
    prior = x['semantic_voice_state']['prior_timing_revision']
    assert prior['previous_candidate_available'] is False
    assert prior['before_after_fix_claim_proved'] is False
    assert x['decision'] == 'HOLD' and x['semantic_voice_state']['fa_issue']


def test_note_free_semantic_conflict_is_not_missed(rows):
    x = rows[130]
    assert not x['review']['fa_phrase_boundary_notes']
    assert x['control_state']['state'] == 'PASS'
    assert 'FA_SEMANTIC_REVIEW_REQUIRED' in x['all_holds']
    with pytest.raises(AssertionError):
        m.assert_safe_record(x)


def test_official_13_and_glossary_14_independent_gates(rows):
    assert tuple(i for i, x in enumerate(rows) if x['review']['official_name_warnings']) == m.OFFICIAL_INDICES
    assert tuple(i for i, x in enumerate(rows) if x['review']['glossary_scope_warnings']) == m.GAP_INDICES
    for i in (40, 41, 42, 49, 56, 85, 86, 87, 91, 123):
        assert rows[i]['official_name_state']['state'] == 'HOLD' and rows[i]['decision'] == 'HOLD'
    assert rows[124]['official_name_state']['state'] == 'PASS'
    assert all(x['glossary_state']['scope_changes'] == x['glossary_state']['global_replace_changes'] == 0 for x in rows)
    assert rows[53]['glossary_state']['gap_records'][0]['state'] == 'EXISTING_GLOBAL_PERMISSION'


@pytest.mark.parametrize('index', (92, 115))
def test_latin_spells_guarded_without_new_pronunciation(index, rows):
    x = rows[index]
    literal = x['latin_literal_guards'][0]
    fixed = x['controlfixed_japanese']
    assert '[latin]' + literal + '[japanese]' in fixed
    raw = Charmap('ja').encode(fixed)
    # Existing codec decodes spaces/comma/pause to canonical display aliases.
    # Lossless byte roundtrip, not spelling of aliases, is the contract.
    decoded = decode_pcs(raw).text
    assert Charmap('ja').encode(decoded) == raw
    assert '[latin]' + literal + '[japanese]' in decoded
    assert x['control_state']['raw_controls_preserved_except_language_pages']
    assert fixed.replace('[japanese]', '').replace('[latin]', '') == x['candidate_japanese']


def test_five_width_warnings_and_no_guessed_player_bound(data, rows):
    assert {int(k): v for k, v in data['metadata']['validation']['reported_width_warnings'].items()} == m.WIDTHS
    for i, width in m.WIDTHS.items():
        assert rows[i]['decision'] == 'HOLD'
        if i != 118:
            assert rows[i]['width_state']['max_total'] == width > 208
            assert 'field_208px_overflow' in rows[i]['all_holds']
    assert rows[118]['width_state']['max_total'] == 173
    assert rows[118]['width_state']['unknown_placeholder_codes'] == ['0x01']
    assert rows[118]['encoded_bytes'] == 32 > rows[118]['source_slot'] == 30
    assert data['metadata']['validation']['width_118']['proven_dynamic_bound'] is None


def test_reported_relocations_and_extra_guarded_candidate(data, rows):
    assert data['metadata']['validation']['reported_relocation_indices'] == [91, 123]
    assert data['metadata']['validation']['actual_relocation_indices'] == [91, 118, 123]
    assert all(rows[i]['decision'] == 'HOLD' for i in (91, 118, 123))
    assert rows[91]['official_name_state']['issues'] and rows[123]['official_name_state']['issues']


def test_owner_99_unclassified_hit_is_fail_closed(rows):
    x = rows[99]
    assert x['pointer_state']['recorded'] == ['0x01E67EEF']
    assert x['pointer_state']['missing'] == ['0x009FF6C2']
    assert not x['pointer_state']['interior_hits']
    assert x['pointer_state']['consumer_proven_for_extra_hits'] is False
    assert 'owner_incomplete_or_interior' in x['all_holds'] and x['decision'] == 'HOLD'


@pytest.mark.parametrize('index', m.VOICE_INDICES)
def test_voice_changes_do_not_promote_identity(index, rows):
    s = rows[index]['semantic_voice_state']
    assert s['voice_note'] == m.VOICE_NOTES[index]
    assert not s['identity_or_voice_confidence_promoted'] and not s['new_wording_created']


def test_rom_controls_are_batch03_populations(data, rows):
    counts = data['metadata']['validation']['confirmed_rom_controls']
    assert {k: counts[k] for k in ('FE', 'FA', 'FB')} == {'FE': 240, 'FA': 105, 'FB': 204}
    assert data['metadata']['kanji'] == data['metadata']['encode_errors'] == 0
    for x in rows:
        if x['review_status'] == 'confirmed':
            assert x['control_state']['state'] == 'PASS'
            assert not m.previous.HAN.search(x['candidate_japanese'])
            Charmap('ja').encode(x['controlfixed_japanese'])
        if x['decision'] == 'APPLY':
            m.assert_safe_record(x)


def test_controlfix_byte_idempotency():
    first, second = [m.OUT / (m.PREFIX + n) for n in ('controlfix.json', 'controlfix_twice.json')]
    assert first.read_bytes() == second.read_bytes()
    assert m.read(first)['entries'] == m.read(m.OUT / (m.PREFIX + 'safe_input.json'))['entries']
    for name in ('controlfix_report', 'controlfix_twice_report'):
        stats = m.read(m.OUT / (m.PREFIX + name + '.json'))['stats']
        assert stats['remaining_control_mismatches'] == stats['fa_placement_review_required'] == 0


def test_strict_incremental_and_full_dry_runs(data):
    dry, built = [m.read(m.OUT / (m.PREFIX + n)) for n in ('incremental_dry_run_map.json', 'map.json')]
    m.assert_strict_map(dry, built, data['metadata']['applied'])
    full = m.read(m.OUT / (m.PREFIX + 'full_dry_run_map.json'))
    m.assert_strict_map(full, full, data['metadata']['japanese_applied_total'])
    bad = deepcopy(built)
    bad['stats']['skipped_pointer_mismatch'] = 1
    with pytest.raises(AssertionError):
        m.assert_strict_map(bad, bad, data['metadata']['applied'])


def test_baseline_all_2357_payloads_storage_and_pointers_and_binary(data):
    safe = m.read(m.OUT / (m.PREFIX + 'safe_input.json'))['entries']
    before, after = m.BASE.read_bytes(), m.ROM.read_bytes()
    result = m.audit_binary(before, after, safe, m.read(m.OUT / (m.PREFIX + 'map.json')), m.baseline())
    assert result == m.read(m.OUT / (m.PREFIX + 'binary_audit.json'))
    assert result['existing_2357_payload_storage_and_pointers_unchanged']
    assert len(result['voice_three_preserved']) == 3 and result['Daniel_not_newly_applied']
    assert result['unexpected_byte_count'] == 0
    # A one-byte unrelated mutation must fail even if all statistics pass.
    corrupted = bytearray(after)
    corrupted[0x100] ^= 1
    with pytest.raises(AssertionError):
        m.audit_binary(before, corrupted, safe, m.read(m.OUT / (m.PREFIX + 'map.json')), m.baseline())
    assert m.digest(m.BASE.read_bytes()) == m.BASE_SHA


def test_held_entry_text_and_owners_not_changed(rows):
    before, after = m.BASE.read_bytes(), m.ROM.read_bytes()
    for x in rows:
        if x['decision'] == 'HOLD':
            offset = int(x['pointer_state']['source_rom_offset'], 16)
            assert before[offset:offset + x['source_slot']] == after[offset:offset + x['source_slot']]
            for p in x['pointer_state']['recorded']:
                p = int(p, 16)
                assert before[p:p + 4] == after[p:p + 4]


def test_original_909_files_preserved_and_no_existing_validator_edit():
    proof = m.protected_snapshot()
    assert proof['files'] == 909 and proof['aggregate_sha256'] == m.INITIAL_SNAPSHOT


def test_runtime_qa_does_not_invent_maps_or_reachability():
    qa = m.read(m.FIX / (m.PREFIX + 'runtime_qa.json'))
    assert 15 <= qa['metadata']['count'] == len(qa['entries']) <= 25
    assert not qa['metadata']['performed']
    assert all(x['map'] == x['event'] == 'UNKNOWN' for x in qa['entries'])
    assert any(x['decision'] == 'APPLY' for x in qa['entries'])
    assert any(x['decision'] == 'HOLD' for x in qa['entries'])
