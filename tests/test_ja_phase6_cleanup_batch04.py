"""Phase 6C-4J: independent gates for the Batch 04 technical integration."""
from collections import Counter
from copy import deepcopy

import pytest

from lib.fa_control import join_segments
from lib.pcs_text import Charmap
from scripts import build_ja_phase6_cleanup_batch03 as b3
from scripts import build_ja_phase6_cleanup_batch04 as m


@pytest.fixture(scope='module')
def data():
    return m.read(m.OUT / (m.PREFIX + 'reviewed.json'))


@pytest.fixture(scope='module')
def rows(data):
    return data['entries']


def _validate(review):
    return m.validate_review(review, m.read(m.BATCH)['entries'], m.read(m.MANIFEST), m.read(m.VOICE))


def test_existing_snapshot_fix_keeps_909_and_separates_new_artifacts():
    proof = b3.protected_snapshot()
    assert proof['files'] == 909 and proof['aggregate_sha256'] == b3.INITIAL_SNAPSHOT
    # The allow-list in the Batch 03 script is exactly this stage's artifacts, no wildcard, nothing else.
    assert b3.LATER_STAGE_PATHS == frozenset(m.NEW_PATHS | {
        'tests/fixtures/ja_phase6_cleanup_batch04_claude_review.json',
        'tests/fixtures/ja_phase6_cleanup_batch04_voice_audit.json',
        'docs/ja-phase6-final-cleanup-batch04-claude-review.md'})
    assert 'out/phase6/ja_phase6_cleanup_batch04_for_claude.json' not in b3.LATER_STAGE_PATHS


def test_unlisted_new_file_still_breaks_the_snapshot(tmp_path, monkeypatch):
    stray = m.ROOT / 'docs' / '_stray_unlisted_probe.md'
    assert not stray.exists()
    stray.write_text('probe', encoding='utf-8')
    try:
        with pytest.raises(AssertionError):
            b3.protected_snapshot()
    finally:
        stray.unlink()
    assert b3.protected_snapshot()['files'] == 909


def test_past_batch_artifacts_unchanged():
    proof = m.prior_artifact_snapshot()
    assert proof['aggregate_sha256'] == m.PRIOR_ARTIFACTS_SHA and proof['files'] == 63


def test_140_accounting_and_immutable_metadata(data):
    result = data['metadata']['validation']
    assert result['ids'] == 140 and result['duplicates'] == result['missing'] == 0
    assert result['status_counts'] == {'confirmed': 129, 'needs_context': 10, 'needs_technical_fit': 1}
    assert result['translation_class'] == 105 and result['context_class'] == 35
    assert result['original_candidate_hold_confidence_tokens_controls_preserved']
    assert data['metadata']['baseline_applied'] == 2383


@pytest.mark.parametrize('field,value', [('original', 'wrong'), ('previous_candidate', 'wrong'),
                                        ('speaker_confidence', 'PROVEN'), ('protected_tokens', ['[x]']),
                                        ('hold_reason', {}), ('source_controls', {'FE': 99})])
def test_changed_source_metadata_rejected(field, value):
    review = deepcopy(m.read(m.REVIEW))
    review[0][field] = value
    with pytest.raises(AssertionError):
        _validate(review)


def test_context_ten_and_technical_one(rows):
    held = [r['review_index'] for r in rows if r['review_status'] == 'needs_context']
    assert tuple(held) == m.CONTEXT_HOLDS == (0, 2, 3, 17, 26, 40, 41, 61, 92, 115)
    for i in m.BUFFER_CONTEXT_HOLDS:
        assert rows[i]['review']['buffers'] and rows[i]['buffer_state']['state'] == 'UNKNOWN_CONTRACT'
    assert rows[17]['review']['buffers'] == [] and rows[92]['review']['buffers'] == ['[rival]', '[player]']
    assert all(r['decision'] == 'HOLD' and not r['candidate_japanese'] for r in rows if r['review_status'] == 'needs_context')
    tech = rows[m.TECHNICAL_HOLD]
    assert tech['review_status'] == 'needs_technical_fit' and tech['decision'] == 'HOLD'
    assert tech['all_holds'][:2] == ['review_needs_technical_fit', 'incomplete_pointer_ownership']
    assert tech['pointer_state']['missing'] == ['0x012CE3E5'] and tech['pointer_state']['recorded'] == ['0x01E59488']


def test_pointer_60_unrecorded_hit_is_not_called_non_owner(data, rows):
    audit = data['metadata']['validation']['audits']['pointer_60']
    assert audit['unrecorded_exact_hit'] == ['0x012CE3E5']
    assert 'NOT accepted' in audit['finding']
    assert rows[m.TECHNICAL_HOLD]['pointer_state']['consumer_proven_for_extra_hits'] is False


def test_fa_71_66_703_and_every_completed_row_has_a_manual_verdict(data, rows):
    fa = data['metadata']['validation']['audits']['fa']
    assert (fa['rows'], fa['completed'], fa['completed_segments']) == (71, 66, 703)
    assert len(fa['context_holds']) == 5
    assert set(fa['semantic_hold']) | set(fa['semantic_pass']) == {r['review_index'] for r in rows if r['FA_state']['present'] and r['review_status'] == 'confirmed'}
    assert len(fa['semantic_hold']) == 42 and len(fa['semantic_pass']) == 24
    covered = set(m.FA_ISSUES) | set(m.FA_NOTES) | m.FA_PASS_CHECKED
    assert covered == set(fa['semantic_hold']) | set(fa['semantic_pass']) and not set(m.FA_ISSUES) & (set(m.FA_NOTES) | m.FA_PASS_CHECKED)
    for r in rows:
        if r['FA_state']['present'] and r['review_status'] == 'confirmed':
            c = r['control_state']
            assert c['state'] == 'PASS' and c['source_boundaries'] == c['target_boundaries'] and c['per_segment_tokens_preserved']
            assert join_segments(m.previous.segments(r['review']), r['review']['translated_segments']) == r['candidate_japanese']
            assert r['FA_state']['layout_approval_required_by_review'] is True
            assert (r['semantic_voice_state']['state'] == 'HOLD') == ('FA_SEMANTIC_REVIEW_REQUIRED' in r['all_holds'] or 'CLAUDE_WORDING_REVIEW_REQUIRED' in r['all_holds'])


def test_structure_equal_does_not_imply_semantic_pass(rows):
    # #7 mirrors the ROM FA/FB structure exactly yet moves 'some kid' across a wait.
    r = rows[7]
    assert r['control_state']['state'] == 'PASS' and r['decision'] == 'HOLD'
    assert 'FA_SEMANTIC_REVIEW_REQUIRED' in r['all_holds'] and 'kid' in r['semantic_voice_state']['fa_issue']


@pytest.mark.parametrize('index', m.PHRASE_INDICES)
def test_three_phrase_notes_are_independently_audited(index, rows):
    r = rows[index]
    assert r['FA_state']['phrase_note'] and r['semantic_voice_state']['phrase'] == m.PHRASE_AUDIT[index]
    assert r['decision'] == 'HOLD'
    if index == 70:
        assert r['semantic_voice_state']['phrase']['verdict'] == 'NOTE_VALID_ENTRY_HELD'
    else:
        assert r['semantic_voice_state']['phrase']['verdict'] == 'HOLD' and 'FA_SEMANTIC_REVIEW_REQUIRED' in r['all_holds']


def test_raid_notices_19(data, rows):
    raid = data['metadata']['validation']['audits']['raid_notice']
    assert len(raid['entries']) == 19 == len(m.RAID_INDICES)
    assert raid['direct_references_to_table_base_in_rom'] == []
    for e in raid['entries']:
        assert e['source_FE'] == e['target_FE'] == 2 and e['target_FA_FB'] == [0, 0] == e['source_FA_FB']
        assert len(e['japanese_lines']) == 3 and e['dynamic_buffers'] == [] and e['max_px'] <= 208
        assert e['renderer_profile'] == 'unproved_consumer' and e['decision'] == 'HOLD' and 'renderer_consumer_unproved' in e['holds']
    assert all(rows[i]['pointer_state']['recorded'][0].startswith('0x01E61') for i in m.RAID_INDICES)


def test_voice_five_are_consistent_but_held_for_dynamic_names(data, rows):
    voice = data['metadata']['validation']['audits']['voice']
    assert [v['index'] for v in voice] == list(m.VOICE_INDICES)
    assert all(v['verdict'] == 'CONSISTENT' for v in voice)
    for i in m.VOICE_INDICES:
        s = rows[i]['semantic_voice_state']
        assert not s['identity_or_voice_confidence_promoted'] and not s['new_wording_created']
        assert 'dynamic_buffer_contract_unproved' in rows[i]['all_holds']


def test_official_names_seven(data, rows):
    assert tuple(i for i, r in enumerate(rows) if r['review']['official_name_warnings']) == m.OFFICIAL_INDICES
    states = {i: rows[i]['official_name_state']['state'] for i in m.OFFICIAL_INDICES}
    assert states == {10: 'HOLD', 11: 'HOLD', 24: 'HOLD', 37: 'PASS', 38: 'PASS', 39: 'PASS', 109: 'HOLD'}
    assert rows[10]['decision'] == rows[109]['decision'] == 'HOLD'
    for i in (37, 38, 39):
        assert rows[i]['decision'] == 'APPLY' and m.OFFICIAL_AUDIT[i]['classification'] == 'MACHINE_VOICE_TRANSLATOR_STYLE'
    assert rows[10]['candidate_japanese'] == '[green]Shhhhzzz!'  # source Latin retained, no invented rendering


def test_glossary_gaps_23_and_scope_not_changed(data, rows):
    gaps = [r for r in rows if r['review']['glossary_scope_warnings']]
    assert len(gaps) == 23
    scope = m.read(m.OUT / (m.PREFIX + 'scope_extension_proposal.json'))
    assert scope['glossary_changed'] is False and len(scope['entries']) == 23
    verdicts = Counter(g['audit'] for r in gaps for g in r['glossary_state']['gap_records'])
    assert verdicts['INDEPENDENT_OFFICIAL_ENTITY_POKEAPI'] == 2  # Surf (#35) and Hoopa (#109)
    for r in gaps:
        for g in r['glossary_state']['gap_records']:
            if g['audit'] == 'INDEPENDENT_OFFICIAL_ENTITY_POKEAPI':
                assert g['applied_as_approved_glossary'] is False
            if g['audit'] == 'SCOPE_GAP_UNRESOLVED':
                assert r['decision'] == 'HOLD' and 'glossary_scope_or_target_unapproved' in r['all_holds']
    assert all(r['glossary_state']['scope_changes'] == r['glossary_state']['global_replace_changes'] == 0
               for r in rows if r['review_status'] != 'needs_context')


def test_dynamic_names_45_all_held_and_diagnostic_only(data, rows):
    dyn = data['metadata']['validation']['audits']['dynamic_names']
    assert len(dyn) == 45 == len(data['metadata']['validation']['dynamic_name_indices'])
    for e in dyn:
        r = rows[e['index']]
        assert r['decision'] == 'HOLD' and 'dynamic_buffer_contract_unproved' in r['all_holds']
        assert r['buffer_state']['dynamic_width_diagnostic']['status'] == 'DIAGNOSTIC_ONLY_NOT_PROOF'
        assert e['max_line_local'] >= e['static_max_px']
    assert not [r for r in rows if r['decision'] == 'APPLY' and r['review']['buffers']]


def test_relocation_three_reported_one_unreported_and_only_one_applied(data, rows):
    v = data['metadata']['validation']
    assert v['reported_relocation_indices'] == [4, 10, 139] and v['actual_relocation_indices'] == [4, 10, 12, 139]
    assert v['unreported_relocation_indices'] == [12]
    assert rows[4]['decision'] == 'APPLY' and rows[4]['planned_placement'] == 'relocated'
    for i in (10, 12, 139):
        assert rows[i]['decision'] == 'HOLD'
    audit = {x['index']: x for x in v['audits']['relocation']}
    assert audit[4]['pointer_owners_recorded'] == audit[4]['whole_rom_exact_hits'] == ['0x01E58F51']
    assert audit[10]['pointer_owners_recorded'] == audit[10]['whole_rom_exact_hits'] and 'official_or_project_name_unverified' in audit[10]['holds']
    assert 'renderer_consumer_unproved' in audit[139]['holds'] and 'dynamic_buffer_contract_unproved' in audit[12]['holds']


def test_safe_subset_is_exactly_the_independent_gate_result(data, rows):
    applied = [r['review_index'] for r in rows if r['decision'] == 'APPLY']
    assert applied == [4, 9, 18, 28, 29, 32, 37, 38, 39, 52, 59, 62, 67, 82, 90, 94, 98, 99, 107, 137]
    assert data['metadata']['applied'] == 20 and data['metadata']['held'] == 120
    assert data['metadata']['japanese_applied_total'] == 2403 and data['metadata']['phase6_remaining_holds'] == 774
    for r in rows:
        if r['decision'] == 'APPLY':
            m.assert_safe_record(r)
            assert r['width_state']['max_total'] <= 199 and not r['width_state']['unknown_placeholder_codes']
        else:
            with pytest.raises(AssertionError):
                m.assert_safe_record(r)
    assert data['metadata']['fa_applied'] == 2 and rows[18]['FA_state']['present'] and rows[94]['FA_state']['present']


def test_pcs_and_controls_for_every_completed_row(data, rows):
    codec = Charmap('ja')
    for r in rows:
        if r['candidate_japanese']:
            assert r['control_state']['state'] == 'PASS'
            assert not m.previous.HAN.search(r['candidate_japanese'])
            codec.encode(r['controlfixed_japanese'])
            assert r['control_state']['source_controls_hex'] == r['control_state']['target_controls_hex']
    assert data['metadata']['kanji'] == data['metadata']['encode_errors'] == 0


def test_controlfix_byte_idempotency():
    first, second = [m.OUT / (m.PREFIX + n) for n in ('controlfix.json', 'controlfix_twice.json')]
    assert first.read_bytes() == second.read_bytes()
    safe = m.read(m.OUT / (m.PREFIX + 'safe_input.json'))['entries']
    assert m.read(first)['entries'] == safe
    for name in ('controlfix_report', 'controlfix_twice_report'):
        stats = m.read(m.OUT / (m.PREFIX + name + '.json'))['stats']
        assert stats['remaining_control_mismatches'] == stats['fa_placement_review_required'] == 0


def test_strict_dry_runs_and_map(data):
    dry, built = [m.read(m.OUT / (m.PREFIX + n)) for n in ('incremental_dry_run_map.json', 'map.json')]
    m.assert_strict_map(dry, built, 20)
    full = m.read(m.OUT / (m.PREFIX + 'full_dry_run_map.json'))
    m.assert_strict_map(full, full, 2403)
    bad = deepcopy(built)
    bad['stats']['skipped_pointer_mismatch'] = 1
    with pytest.raises(AssertionError):
        m.assert_strict_map(bad, bad, 20)


def test_baseline_2383_preserved_and_binary_audit_has_no_unexpected_diff():
    safe = m.read(m.OUT / (m.PREFIX + 'safe_input.json'))['entries']
    before, after = m.BASE.read_bytes(), m.ROM.read_bytes()
    mapping = m.read(m.OUT / (m.PREFIX + 'map.json'))
    result = m.audit_binary(before, after, safe, mapping, m.baseline())
    assert result == m.read(m.OUT / (m.PREFIX + 'binary_audit.json'))
    assert len(m.baseline()) == 2383 and result['existing_2383_payload_storage_and_pointers_unchanged']
    assert result['unexpected_byte_count'] == 0 and result['changed_byte_count'] == 1454
    assert result['classified_changed_bytes'] == {'in_place_text': 1431, 'relocated_text': 19, 'pointer_writes': 4}
    assert (result['in_place_count'], result['relocation_count'], result['pointer_writes']) == (19, 1, 1)
    assert len(result['voice_three_preserved']) == 3 and result['Daniel_not_newly_applied']
    assert m.digest(before) == m.BASE_SHA == '546f18a50e0ab0eadb9ed0eb53d5773c2cf5aefae1028cc8e8a631379292cc62'
    # A single unrelated byte flip must fail even though every statistic would still pass.
    corrupted = bytearray(after)
    corrupted[0x100] ^= 1
    with pytest.raises(AssertionError):
        m.audit_binary(before, corrupted, safe, mapping, m.baseline())


def test_held_entry_text_and_owners_unchanged_in_rom(rows):
    before, after = m.BASE.read_bytes(), m.ROM.read_bytes()
    for r in rows:
        if r['decision'] == 'HOLD':
            offset = int(r['pointer_state']['source_rom_offset'], 16)
            assert before[offset:offset + r['source_slot']] == after[offset:offset + r['source_slot']]
            for p in r['pointer_state']['recorded']:
                p = int(p, 16)
                assert before[p:p + 4] == after[p:p + 4]


def test_hold_inventory_and_runtime_qa_shape(rows):
    holds = m.read(m.OUT / (m.PREFIX + 'technical_holds.json'))['entries']
    assert len(holds) == 120 and {h['id'] for h in holds} == {r['id'] for r in rows if r['decision'] == 'HOLD'}
    need = {'id', 'batch_index', 'translation_status', 'reviewed_japanese', 'primary_hold', 'secondary_holds', 'FA_status',
            'buffer_status', 'official_name_status', 'glossary_scope_status', 'dynamic_width_status', 'pointer_status', 'next_action'}
    assert all(need <= set(h) for h in holds) and all(h['batch_index'] == 4 for h in holds)
    qa = m.read(m.FIX / (m.PREFIX + 'runtime_qa.json'))
    assert 15 <= qa['metadata']['count'] == len(qa['entries']) <= 25 and not qa['metadata']['performed']
    assert all(x['map'] == x['event'] == 'UNKNOWN' for x in qa['entries'])
    assert any(x['decision'] == 'APPLY' for x in qa['entries']) and any(x['decision'] == 'HOLD' for x in qa['entries'])


def test_four_batch_totals_do_not_mix_review_and_applied_counts():
    reviewed = {'batch01': (114, 32, 1), 'batch02': (93, 49, 0), 'batch03': (112, 28, 0), 'batch04': (129, 10, 1)}
    assert tuple(map(sum, zip(*reviewed.values()))) == (448, 119, 2)
    applied = {'batch01': 68, 'batch02': 28, 'batch03': 26, 'batch04': 20}
    assert sum(list(applied.values())[:3]) == 122 and sum(applied.values()) == 142
