"""Phase 7A census regression: no translation, ROM writes, or gate bypass."""
from collections import Counter
import json
from pathlib import Path

import pytest

from scripts import build_ja_phase7_inventory as m


@pytest.fixture(scope='module')
def data():
    # Recompute from immutable inputs without persisting anything.
    result = m.build_inventory()
    for path, value in result.items():
        assert value == json.loads((m.ROOT / path).read_text(encoding='utf-8'))
    return result


def test_canonical_and_raw_populations_are_retained_separately(data):
    inv = data[m.OUTPUTS[0]]
    canonical, raw = inv['entries'], inv['raw_entries']
    assert len(canonical) == len({r['id'] for r in canonical}) == 25044
    assert len(raw) == len({r['id'] for r in raw}) == 25045
    assert {r['id'] for r in canonical} == {
        r['id'] for r in json.loads((m.ROOT / m.CANONICAL).read_text(encoding='utf-8'))['entries']}
    assert {r['id'] for r in raw} == {
        r['id'] for r in json.loads((m.ROOT / m.RAW).read_text(encoding='utf-8'))['entries']}
    assert inv['mapping']['union_ids'] == 25046
    assert inv['mapping']['missing_id_count'] == 0


def test_full_warning_alias_is_not_confused_with_interior_suffix(data):
    inv = data[m.OUTPUTS[0]]
    full, suffix = inv['mapping']['full_string_alias'], inv['mapping']['interior_candidate']
    assert (full['raw_id'], full['canonical_id']) == (m.OLD_WARNING, m.WARNING)
    assert full['status'] == 'PROVEN_SAME_STRING'
    assert full['pointer_sources'] == ['0x01EBD7FC']
    assert full['slot_size'] == 185 and suffix['slot_size'] == 180
    assert suffix['offset_into_parent'] == 5 and suffix['omitted_prefix_hex'] == 'fc 01 04 d1 bb'
    assert suffix['mapping_status'] == 'UNRESOLVED_MAPPING'
    assert suffix['relationship'] == 'STRICT_BYTE_SUFFIX_NOT_IDENTICAL_STRING'
    assert suffix['whole_rom_direct_pointer_hits'] == [] and suffix['unused_proven'] is False
    assert suffix['computed_or_interior_consumer'] == 'NOT_PROVEN_OR_DISPROVED'
    row = next(r for r in inv['raw_entries'] if r['id'] == m.SUFFIX)
    assert row['canonical_id'] is None and row['status'] == 'UNKNOWN'
    assert inv['supplemental_unresolved_ids'] == [m.SUFFIX]
    assert inv['mapping']['history']['current_focused_extraction'] == 'PROVEN_FULL_BOUNDARY'


def test_originals_and_pointer_metadata_versions_are_not_normalized(data):
    inv = data[m.OUTPUTS[0]]
    for path, rows in ((m.CANONICAL, inv['entries']), (m.RAW, inv['raw_entries'])):
        source = m.index_unique(json.loads((m.ROOT / path).read_text(encoding='utf-8'))['entries'], path)
        for r in rows:
            assert r['source'] == source[r['id']]
    assert inv['mapping']['common_original_changes'] == 0
    assert inv['mapping']['common_pointer_metadata_deltas']
    assert all(r['source_rom_words_verified'] for r in inv['mapping']['common_pointer_metadata_deltas'])


def test_phase6_set_reconciliation_has_no_double_counting(data):
    inv = data[m.OUTPUTS[0]]
    summary = inv['metadata']['summary']
    scope = {r['id'] for r in inv['entries'] if r['phase6_scope']}
    applied = {r['id'] for r in inv['entries'] if r['status'] == 'APPLIED_JAPANESE'}
    remaining = set(inv['phase6_remaining_ids'])
    cleanup = {r['id'] for r in inv['entries'] if r['cleanup_569_member']}
    assert len(scope) == 3177 and len(applied) == 2403 and applied <= scope
    assert remaining == scope - applied and len(remaining) == 774
    assert len(cleanup) == 569 and len(cleanup & applied) == 142
    assert len(cleanup & remaining) == 427 and len(remaining - cleanup) == 347
    assert summary['outside_phase6_scope'] == 21867


def test_all_applied_payloads_and_recorded_owners_match_current_rom(data):
    inv = data[m.OUTPUTS[0]]
    applied = [r for r in inv['entries'] if r['status'] == 'APPLIED_JAPANESE']
    assert len(applied) == 2403
    assert all(r['applied_rom_verification']['payload_and_recorded_owners_match'] for r in applied)
    assert inv['metadata']['validation']['applied_placements'] == {'IN_PLACE': 1984, 'RELOCATED': 419}
    assert m.sha((m.ROOT / m.BASE_ROM).read_bytes()) == m.BASE_SHA
    assert inv['metadata']['protected_files']['count'] == 909
    assert m.protected_snapshot()['aggregate_sha256'] == inv['metadata']['protected_files']['aggregate_sha256']


def test_status_axes_and_category_totals_reconcile(data):
    inv, stats = data[m.OUTPUTS[0]], data[m.OUTPUTS[1]]
    assert sum(inv['metadata']['summary']['status_counts'].values()) == 25044
    assert sum(inv['metadata']['summary']['translation_state_counts'].values()) == 25044
    assert sum(r['target_count'] for r in stats['categories']) == 25044
    assert sum(r['applied'] for r in stats['categories']) == 2403
    for s in stats['categories']:
        assert s['applied'] + s['approved_english'] + s['remaining'] == s['target_count']
        assert s['with_existing_draft_or_review'] + s['untranslated_no_draft'] + s['approved_english'] == s['target_count']
    assert inv['metadata']['summary']['reviewed_not_applied'] == 306
    assert inv['metadata']['summary']['draft_not_applied'] == 324
    assert all(not r['candidate_is_approved_for_injection'] for r in inv['entries'] if r['status'] != 'APPLIED_JAPANESE')


def test_holds_are_latest_and_primary_secondary_are_separate(data):
    inv, blockers = data[m.OUTPUTS[0]], data[m.OUTPUTS[3]]
    summary = inv['metadata']['summary']
    assert summary['context_hold'] == 217 and summary['technical_hold'] == 794
    assert summary['hold_union'] == 813
    assert sum(v['primary_count'] for v in blockers['families'].values()) == 813
    assert len({r['id'] for r in blockers['entries']}) == 813
    assert any(r['context_hold'] and r['technical_hold'] for r in blockers['entries'])
    for r in inv['entries']:
        if r['status'] == 'APPLIED_JAPANESE':
            assert not r['holds']['context_hold'] and not r['holds']['technical_hold']
    assert set(blockers['families']) == set(m.HOLD_FAMILIES)


def test_keep_english_requires_explicit_disposition_and_no_false_unused(data):
    inv = data[m.OUTPUTS[0]]
    keep = [r for r in inv['entries'] if r['status'] == 'KEEP_ENGLISH_APPROVED']
    assert len(keep) == 3 and all(r['category'] == 'credits_text' for r in keep)
    proposals = [r for r in inv['entries'] if r['holds']['primary_reason'] == 'english_retention_proposed_not_approved_for_full_localization']
    assert len(proposals) == 5 and all(r['status'] == 'TECHNICAL_HOLD' for r in proposals)
    assert inv['metadata']['summary']['unused_proven'] == 0
    assert all(not r['runtime']['unused_proven'] for r in inv['entries'])
    assert all(r['pointer_ownership']['no_pointer_does_not_prove_unused'] for r in inv['entries'])


def test_no_scene_or_reachability_claim_from_rom_proximity(data):
    row = {'id': 'unknown', 'category': 'scripts', 'address': '0x1F0F79C'}
    assert m.classify(row, None) == 'UNKNOWN'
    assert m.classify(row, {'speaker_confidence': 'PLAUSIBLE', 'speaker_category': 'TRAINER_CLASS'}) == 'UNKNOWN'
    assert m.classify(row, {'speaker_confidence': 'PROVEN', 'speaker_category': 'TRAINER_CLASS'}) == 'TRAINER_DIALOGUE'
    assert m.priority(row, 'UNKNOWN', 'UNKNOWN')['verification'] == 'PRIORITY_UNVERIFIED'
    assert data[m.OUTPUTS[1]]['content_families']['UNKNOWN'] > 15000


def test_queue_preserves_all_entries_and_supplemental_obligation(data):
    inv, q = data[m.OUTPUTS[0]], data[m.OUTPUTS[2]]
    rows = [r for group in q['queues'].values() for r in group]
    assert len(rows) == len({r['id'] for r in rows}) == 25044
    assert {r['id'] for r in rows} == {r['id'] for r in inv['entries']}
    assert Counter(r['level'] for r in rows) == q['summary']['counts']
    assert q['summary']['no_P2_P3_exclusions']
    assert q['supplemental'] == [{'id': m.SUFFIX, 'priority': 'P3', 'status': 'UNRESOLVED_MAPPING'}]
    assert inv['extractor_coverage_gaps']['graphics']['complete'] is False
    assert all(r['inside_25044'] != 'TRUE' for r in inv['extractor_coverage_gaps']['paths_requiring_further_audit'])


def test_duplicate_candidates_never_merge_targets(data):
    inv = data[m.OUTPUTS[0]]
    for kind in ('exact_original', 'layout_only_reuse_candidates'):
        d = inv['duplicates'][kind]
        assert d['merge_authorized'] is False
        assert d['members'] - d['duplicate_groups'] == d['redundant_members']
        assert d['distinct_keys'] + d['redundant_members'] == 25044
    with pytest.raises(ValueError, match='Duplicate IDs'):
        m.index_unique([{'id': 'x'}, {'id': 'x'}], 'unit test')


def test_planning_distinguishes_latin_proposals_and_conservative_capacity(data):
    observations = m.planning_observations(data)
    assert len(observations['latin_only_unapproved_draft_ids']) == 7
    assert observations['kana_draft_not_applied'] == 317
    assert observations['no_kana_candidate_including_latin_proposals'] == 22015
    assert observations['pokeapi_category_candidates_not_guaranteed_localizable'] == 6652
    assert observations['control_sensitive_batch_scenario'] == 292
    assert observations['fresh_vetted_free_blocks'] == 131
    assert observations['fresh_vetted_free_bytes'] == 610162
    assert observations['no_recorded_pointer_or_legacy_candidate_union'] == 5307


def test_exact_output_allow_list_and_immutable_repeat(data, tmp_path):
    assert set(m.OUTPUTS) <= m.PHASE7A_PATHS
    assert m.persist_new(data, tmp_path) == 'CREATED_NEW'
    before = {p: (tmp_path / p).read_bytes() for p in m.OUTPUTS}
    assert m.persist_new(data, tmp_path) == 'VERIFIED_EXISTING_IDENTICAL'
    assert before == {p: (tmp_path / p).read_bytes() for p in m.OUTPUTS}
    with pytest.raises(AssertionError):
        m.persist_new({'out/phase7/unlisted.json': {}}, tmp_path)


def test_partial_or_conflicting_outputs_fail_before_any_write(data, tmp_path):
    first = tmp_path / m.OUTPUTS[0]
    first.parent.mkdir(parents=True)
    first.write_bytes(b'preserve-me')
    with pytest.raises(FileExistsError, match='Partial'):
        m.persist_new(data, tmp_path)
    assert first.read_bytes() == b'preserve-me'
    assert all(not (tmp_path / p).exists() for p in m.OUTPUTS[1:])
    for p in m.OUTPUTS[1:]:
        (tmp_path / p).write_bytes(b'other-existing')
    before = {p: (tmp_path / p).read_bytes() for p in m.OUTPUTS}
    with pytest.raises(FileExistsError, match='Conflicting'):
        m.persist_new(data, tmp_path)
    assert before == {p: (tmp_path / p).read_bytes() for p in m.OUTPUTS}
