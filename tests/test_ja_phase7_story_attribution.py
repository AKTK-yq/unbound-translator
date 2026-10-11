"""Phase 7B: static evidence is never runtime, story, or injection approval."""
from collections import Counter
from copy import deepcopy
import json

import pytest

from scripts import build_ja_phase7_story_attribution as m


@pytest.fixture(scope='module')
def data():
    result = m.build_attribution()
    # Full offline recomputation, not merely loading the newly written report.
    for path, value in result.items():
        assert value == json.loads((m.ROOT / path).read_text(encoding='utf-8'))
    return result


def pointer(target):
    return (m.GBA_BASE + target).to_bytes(4, 'little')


def root(start=0):
    return {'root_id': 'synthetic_root', 'script_offset': m.hx(start)}


def test_argument_lengths_match_fixed_command_signatures():
    assert m.LENGTHS[0x28] == 3  # delay u16, not five bytes
    assert m.LENGTHS[0x7C] == 3  # checkpartymove u16
    assert m.LENGTHS[0x7D] == m.LENGTHS[0x80] == 4
    assert m.LENGTHS[0x7E] == 2 and m.LENGTHS[0x85] == 6
    assert m.LENGTHS[0x3C] == 3 and m.LENGTHS[0x39] == 8
    assert m.LENGTHS[0x4F] == 7 and m.LENGTHS[0x50] == 9


def test_call_return_keeps_actual_stack_and_indirect_reference():
    rom = bytearray(256)
    rom[0:11] = b'\x04' + pointer(40) + b'\x67' + pointer(128) + b'\x02'
    rom[40:46] = b'\x67' + pointer(160) + b'\x03'
    nodes = {}
    walked = m.walk_script(bytes(rom), root(), {128: ['caller'], 160: ['callee']}, nodes)
    by_id = {r['id']: r for r in walked['references']}
    assert by_id['callee']['call_depth'] == 1
    assert by_id['callee']['reference_confidence'] == 'INDIRECT_REFERENCE'
    assert by_id['caller']['call_depth'] == 0
    assert by_id['caller']['static_path'] == [m.hx(p) for p in (0, 40, 45, 5)]
    assert not walked['parse_gaps']


def test_call_that_ends_does_not_invent_caller_fallthrough():
    rom = bytearray(256)
    rom[0:11] = b'\x04' + pointer(40) + b'\x67' + pointer(128) + b'\x02'
    rom[40] = 2  # end, not return
    assert m.walk_script(bytes(rom), root(), {128: ['unreachable_after_end']})['references'] == []


def test_conditional_paths_are_not_claimed_feasible():
    rom = bytearray(256)
    rom[0:3] = bytes.fromhex('2b 23 01')
    rom[3:15] = b'\x06\x01' + pointer(40) + b'\x67' + pointer(128) + b'\x02'
    rom[40:46] = b'\x67' + pointer(160) + b'\x02'
    nodes = {}
    w = m.walk_script(bytes(rom), root(), {128: ['else'], 160: ['then']}, nodes)
    assert {r['id'] for r in w['references']} == {'then', 'else'}
    assert all(not r['conditions_evaluated'] and r['runtime_reachability'] == 'UNVERIFIED' for r in w['references'])
    assert nodes[m.hx(0)]['flag_operation']['story_meaning'] == 'UNKNOWN'


def test_native_functions_are_opaque_not_parsed_as_scripts():
    rom = bytearray(256)
    rom[0:11] = b'\x23' + pointer(40) + b'\x67' + pointer(128) + b'\x02'
    rom[40:46] = b'\x67' + pointer(160) + b'\x02'
    w = m.walk_script(bytes(rom), root(), {128: ['after_native'], 160: ['not_a_script']})
    assert [r['id'] for r in w['references']] == ['after_native']
    assert w['references'][0]['opaque_effect_on_path']
    assert m.hx(40) not in w['instruction_offsets']


def test_unknown_or_changed_commands_and_text_targets_stop():
    rom = bytearray(256)
    rom[0:7] = b'\xff\x67' + pointer(128) + b'\x02'
    w = m.walk_script(bytes(rom), root(), {128: ['not_accepted']})
    assert w['references'] == [] and w['parse_gaps'][0]['reason'] == 'UNSUPPORTED_OPCODE_OR_MODE'
    rom[0] = 0x8A
    w = m.walk_script(bytes(rom), root(), {128: ['not_accepted']}, blocked_opcodes=m.UNPROVED_PATCHED_OPCODES)
    assert w['references'] == [] and w['parse_gaps'][0]['reason'] == 'PATCHED_HANDLER_OPERANDS_UNPROVEN'
    rom[0:5] = b'\x05' + pointer(128)
    w = m.walk_script(bytes(rom), root(), {128: ['data']}, text_spans=((128, 150),))
    assert w['parse_gaps'][0]['reason'] == 'SCRIPT_TARGET_INSIDE_TEXT_SLOT'


def test_loadword_and_buffer_writer_are_not_automatically_display():
    rom = bytearray(256)
    rom[0:13] = b'\x0f\x00' + pointer(128) + b'\x85\x00' + pointer(160) + b'\x02'
    w = m.walk_script(bytes(rom), root(), {128: ['load'], 160: ['buffer']})
    assert {r['role'] for r in w['references']} == {'LOADWORD_ONLY_CONSUMER_UNPROVEN', 'BUFFERSTRING_WRITER'}
    rom[6:9] = b'\x09\x06\x02'
    w = m.walk_script(bytes(rom), root(), {128: ['load']})
    assert w['references'][0]['role'] == 'LOADWORD_CALLSTD_TEXT'


def test_long_and_extended_trainerbattle_modes_fail_closed():
    rom = bytearray(256)
    rom[0:14] = b'\x5c\x00\x01\x00\x00\x00' + pointer(128) + pointer(160)
    rom[14] = 2
    w = m.walk_script(bytes(rom), root(), {128: ['intro'], 160: ['defeat']})
    assert {r['id'] for r in w['references']} == {'intro', 'defeat'}
    rom[1] = 13
    w = m.walk_script(bytes(rom), root(), {128: ['unproved_mode']})
    assert not w['references'] and w['parse_gaps'][0]['reason'] == 'UNSUPPORTED_OPCODE_OR_MODE'


def test_no_story_speaker_or_progression_claim_from_proximity_or_name():
    row = {'id': 'unproved', 'category': 'scripts', 'content_family': 'UNKNOWN',
           'original': 'Jax in Frozen Heights', 'rom_offset': '0x01F0F7ED'}
    assert m.classify_story(row, [], {}) == ('UNKNOWN', 'UNKNOWN',
        'No proved mandatory/optional/postgame event assignment; address/name matching forbidden.')
    refs = [{'root_id': 'level', 'role': 'MESSAGE', 'call_depth': 0}]
    roots = {'level': {'kind': 'level_condition', 'map_id': 'only_map'}}
    assert m.classify_story(row, refs, roots)[:2] == ('MAIN_STORY_CANDIDATE', 'PROVISIONAL')
    refs[0]['call_depth'] = 1
    assert m.classify_story(row, refs, roots)[0] == 'UNKNOWN'


def test_all_populations_originals_and_translation_states_unchanged(data):
    inv = m.read(m.INVENTORY)
    index = data[m.OUTPUTS[0]]
    assert len(index['entries']) == len({r['id'] for r in index['entries']}) == 25044
    assert index['raw_entries'] == inv['raw_entries'] and len(index['raw_entries']) == 25045
    assert index['raw_mapping'] == inv['mapping']
    assert index['supplemental_unresolved_ids'] == inv['supplemental_unresolved_ids']
    assert index['phase6_remaining_ids'] == inv['phase6_remaining_ids'] and len(index['phase6_remaining_ids']) == 774
    for row, old in zip(index['entries'], inv['entries']):
        for field in ('id', 'original', 'candidate_japanese', 'status', 'translation_state', 'injection_state', 'holds', 'pointer_ownership'):
            assert row[field] == old[field]
        assert row['current_japanese'] == (old['candidate_japanese'] if old['status'] == 'APPLIED_JAPANESE' else None)
    assert sum(r['status'] == 'APPLIED_JAPANESE' for r in index['entries']) == 2403


def test_map_group_xor_and_name_bias_are_engine_proven(data):
    index = data[m.OUTPUTS[0]]
    by_id = {r['map_id']: r for r in index['maps']}
    assert len(by_id) == 645
    for mid, name, address in (('map_003_066', 'Frozen Heights', '0x007738E4'),
                               ('map_003_067', 'Route 1', '0x00775030'),
                               ('map_003_068', 'Bellin Town', '0x00775870')):
        assert by_id[mid]['map_name'] == name and by_id[mid]['header']['rom_offset'] == address
        assert by_id[mid]['name_table_index'] == by_id[mid]['region_section_id'] - 88
        assert by_id[mid]['runtime_reachability'] == 'UNVERIFIED'
    assert index['map_audit']['engine']['xor_key'] == '0x00B749DE'
    assert index['map_audit']['engine']['decoded_group_count'] == 57
    assert set(index['command_audit']['excluded_patched_opcodes']) == {f'0x{x:02X}' for x in m.UNPROVED_PATCHED_OPCODES}
    assert all(int(n['opcode'], 16) not in m.UNPROVED_PATCHED_OPCODES for n in index['script_nodes'].values())


def test_reference_and_priority_counts_reconcile(data):
    index = data[m.OUTPUTS[0]]
    summary = index['metadata']['summary']
    entries = index['entries']
    assert Counter(r['reference_confidence'] for r in entries) == summary['reference_counts']
    assert Counter(r['priority']['level'] for r in entries) == summary['priority_counts']
    assert sum(summary['story_counts'].values()) == sum(summary['readiness_counts'].values()) == 25044
    assert summary['event_associated_entries'] == sum(bool(r['event_references']) for r in entries) == 4450
    assert summary['content_unknown_before'] == 15209 and summary['content_unknown_after'] == 10849
    assert summary['story_counts']['MAIN_STORY_VERIFIED'] == 0
    assert summary['story_counts']['MAIN_STORY_CANDIDATE'] == 717
    assert summary['priority_confidence']['P0'] == {'PROVISIONAL': 717, 'SUPPORTED': 2, 'VERIFIED': 3}
    assert summary['story_counts']['MANDATORY_GAMEPLAY_UI'] == 5
    queued = [r for q in data[m.OUTPUTS[1]]['queues'].values() for r in q]
    assert len(queued) == len({r['id'] for r in queued}) == 25044


def test_speakers_voices_duplicates_and_unresolved_suffix_retained(data):
    index = data[m.OUTPUTS[0]]
    old = m.read(m.SPEAKERS)
    old_by_id = {r['id']: r for r in old['entries'] + old['applied_candidates']}
    for row in index['entries']:
        assert not row['speaker_confidence_promoted']
        if row['id'] in old_by_id:
            assert row['speaker'] == old_by_id[row['id']]
        if row['duplicate_reuse_candidate']:
            assert not row['duplicate_reuse_candidate']['automatic_reuse_approved']
            assert not row['duplicate_reuse_candidate']['physical_slots_merged']
    assert index['voice_profiles_preserved'] == m.read(m.VOICES)
    assert index['raw_mapping']['interior_candidate']['mapping_status'] == 'UNRESOLVED_MAPPING'
    assert not index['raw_mapping']['interior_candidate']['unused_proven']
    assert all(not r['unused_proven'] for r in index['entries'])
    assert index['story_progression_sequence'] == []


def test_every_static_reference_points_to_bytes_and_parsed_witness(data):
    index = data[m.OUTPUTS[0]]
    nodes = index['script_nodes']
    rom = (m.ROOT / 'rom/unbound.gba').read_bytes()
    root_index = {r['root_id']: r for r in index['roots']}
    for row in index['entries']:
        for ref in row['event_references']:
            assert m.gba_pointer(rom, int(ref['owner'], 16)) == int(row['rom_offset'], 16)
            assert ref['static_path'][0] == root_index[ref['root_id']]['script_offset']
            assert ref['static_path'][-1] == ref['command_offset']
            assert all(pc in nodes for pc in ref['static_path'])
            assert ref['runtime_reachability'] == 'UNVERIFIED' and not ref['conditions_evaluated']
    for pc, n in nodes.items():
        start = int(pc, 16)
        assert rom[start:start + n['length']].hex(' ') == n['bytes']


def test_planning_is_not_injection_approval_and_no_claude_run(data):
    index, plan = data[m.OUTPUTS[0]], data[m.OUTPUTS[3]]
    by_id = {r['id']: r for r in index['entries']}
    ids = [key for b in plan['batches'] for key in b['entry_ids']]
    assert len(ids) == len(set(ids)) == 706
    assert len(plan['batches']) == 16
    for batch in plan['batches']:
        assert batch['count'] <= 160 and not batch['claude_invoked']
        assert batch['visible_source_characters'] <= 16000
        if batch['fa_entries']:
            assert batch['count'] <= 40
        for key in batch['entry_ids']:
            row = by_id[key]
            assert row['priority']['level'] in ('P0', 'P1')
            assert row['translation_readiness'] == 'READY_FOR_CLAUDE'
            assert row['status'] != 'APPLIED_JAPANESE'
            assert row['injection_readiness'] == 'NOT_APPROVED_REQUIRES_EXISTING_GATES'
    assert all(not r['qa']['new_runtime_test_performed'] for r in index['entries'])
    assert {r['id'] for r in index['entries'] if r['qa']['route_status'] == 'HUMAN_OBSERVED_PREVIOUS_PHASE'} == set(m.RUNTIME_OBSERVED)


def test_all_old_hashes_rom_and_phase7a_remain_identical(data):
    manifest = data[m.OUTPUTS[4]]
    assert manifest['metadata']['protected_files'] == m.protected_snapshot()
    assert manifest['metadata']['protected_files']['files'] == 909
    assert manifest['metadata']['protected_files']['aggregate_sha256'] == 'f932aab110e4dc228c628314c43ce5b0dc0ba89d5f15f6740da9ef6117bad4df'
    assert m.sha((m.ROOT / m.BASE_ROM).read_bytes()) == m.BASE_SHA
    assert {p: m.sha((m.ROOT / p).read_bytes()) for p in m.PHASE7A_PATHS} == manifest['preserved_phase7a_sha256']
    assert all(m.sha((m.ROOT / p).read_bytes()) == h for p, h in manifest['metadata']['input_sha256'].items())


def test_new_artifacts_use_only_exact_allowlist_and_never_overwrite(tmp_path):
    small = {p: {'fixture': p} for p in m.OUTPUTS}
    assert set(small) <= m.PHASE7B_PATHS
    assert len(m.PHASE7B_PATHS) == 8 and not any('*' in p for p in m.PHASE7B_PATHS)
    assert m.persist_new(small, tmp_path) == 'CREATED_NEW'
    before = {p: (tmp_path / p).read_bytes() for p in small}
    assert m.persist_new(small, tmp_path) == 'VERIFIED_EXISTING_IDENTICAL'
    assert before == {p: (tmp_path / p).read_bytes() for p in small}
    wrong = deepcopy(small)
    wrong[m.OUTPUTS[0]] = {'different': True}
    with pytest.raises(FileExistsError, match='Conflicting'):
        m.persist_new(wrong, tmp_path)
    assert before == {p: (tmp_path / p).read_bytes() for p in small}
    with pytest.raises(AssertionError):
        m.persist_new({'out/phase7/not_allowed.json': {}}, tmp_path)


def test_partial_stage_stops_before_writing_any_other_file(tmp_path):
    path = tmp_path / m.OUTPUTS[0]
    path.parent.mkdir(parents=True)
    path.write_bytes(b'do not overwrite')
    with pytest.raises(FileExistsError, match='Partial'):
        m.persist_new({p: {} for p in m.OUTPUTS}, tmp_path)
    assert path.read_bytes() == b'do not overwrite'
    assert all(not (tmp_path / p).exists() for p in m.OUTPUTS[1:])
