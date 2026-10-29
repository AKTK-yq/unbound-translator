"""No false comparison PASS, no historical RAM transfer to new trial, no patch."""
import ast
from copy import deepcopy
from pathlib import Path

import pytest

from scripts import investigate_ja_phase7_crash_isolation as m
from scripts import build_ja_phase6_cleanup_batch03 as protection


@pytest.fixture(scope='module')
def result():
    return m.investigate()


def test_only_current_completed_b_trial_and_separate_history(result):
    matrix, _ = result
    conditions = {c['condition']: c for c in matrix['conditions']}
    assert conditions['B']['completed_target_trials'] == conditions['B']['crashes'] == 1
    assert conditions['B']['result'] == 'CRASH_OBSERVED' and not conditions['B']['gdb']
    for key in ('A', 'C', 'D'):
        assert conditions[key]['result'] == 'NOT_RUN'
        assert conditions[key]['started_trials'] == conditions[key]['completed_target_trials'] == 0
    assert matrix['historical_phase7c5']['crashes'] == 1
    assert not matrix['historical_phase7c5']['controlled_current_trial']
    assert not matrix['setup_only_excluded'][0]['count_as_reproduction']


def test_gdb_not_required_does_not_identify_japanese_cause(result):
    conclusion = result[0]['conclusion']
    assert conclusion['gdb_required_for_crash'] is False
    assert conclusion['japanese_causality'] == 'UNKNOWN'
    assert not conclusion['resolved'] and not conclusion['runtime_pass']
    assert conclusion['repeat_reproducibility'] == 'NOT_ESTABLISHED_ONE_CURRENT_TRIAL'


def test_manual_policy_and_fresh_isolated_save(result):
    matrix, _ = result
    assert not matrix['conclusion']['automatic_inputs_now_allowed']
    trial = matrix['observed_trials'][0]
    assert m.no_debugger_argv(trial['argv'])
    assert not trial['debugger_started'] and not trial['listener_2345_before_gameplay']
    assert not trial['debugger_connection']
    assert trial['save_before_launch'].startswith('Empty new save')
    assert trial['temporary_directory'] in trial['save_after']
    assert trial['last_precrash_text'] == 'UNKNOWN'
    assert trial['runtime_registers'] == 'NOT_CAPTURED_NO_DEBUGGER'


@pytest.mark.parametrize('flag', ['-g', '--gdb', '-d', '--debug'])
def test_no_debugger_classification_rejects_flags(flag):
    assert not m.no_debugger_argv(['-C', 'autoload=0', flag, 'trial.gba'])


def test_static_normal_callback_values_not_live_measurements(result):
    _, trace = result
    lifecycle = trace['static_lifecycle']
    assert lifecycle['callback_ram'] == '0x02039610'
    assert not lifecycle['clear']['callback_field_cleared']
    setter = lifecycle['set_params']
    assert setter['write'] == {'rom_offset': '0x00087F28', 'gba_address': '0x08087F28'}
    assert setter['bytes'] == '01 61' and setter['width_bytes'] == 4
    assert [c['value'] for c in setter['normal_candidates']] == ['0x08087FE1', '0x08088001']
    assert setter['normal_candidates_confidence'] == 'STATIC_PROVEN_NOT_OBSERVED_LIVE'
    assert lifecycle['normal_live_values'] == trace['current_normal_ram_observations'] == []
    assert lifecycle['first_write'] == 'UNKNOWN'


def test_actual_first_writer_stays_unknown_and_watchpoint_not_executed(result):
    _, trace = result
    assert not trace['first_invalid_write_captured']
    assert trace['writer_pc'] is None and trace['writer_function'] == 'UNKNOWN'
    assert trace['current_live_write_observations'] == []
    watch = trace['static_lifecycle']['watchpoint_support']
    assert watch['source_verified'] and not watch['runtime_validated_this_phase']
    assert trace['no_patch_proposed']


def test_prior_ram_is_not_b2_snapshot(result):
    old = result[1]['historical_bad_ram']
    assert old['provenance'] == 'Phase7C5 only; NOT B2 memory measurement'
    assert old['state_byte'] == '0xE6'
    assert old['target_check']['value'] == '0xE3E800D9'
    assert old['target_check']['target'] == '0xE3E800D8'
    assert not old['target_check']['location_plausible']


@pytest.mark.parametrize('value,plausible,mode', [
    (0x08087FE1, True, 'Thumb'), (0x08088001, True, 'Thumb'),
    (0x02000001, True, 'Thumb'), (0x03000000, True, 'ARM'),
    (0x0B087FE1, True, 'Thumb'), (0x08087FE2, False, 'ARM'),
    (0xE3E800D9, False, 'Thumb'), (0x040000B0, False, 'ARM'),
    (0, False, 'ARM')])
def test_callback_location_alignment_not_code_execution_proof(value, plausible, mode):
    check = m.callback_target(value)
    assert check['location_plausible'] == plausible and check['mode'] == mode
    assert not check['executable_code_proven']


def test_rom_text_owner_and_controls_unchanged(result):
    text = result[1]['PCS_comparison']
    assert text['slot_bytes'] == text['source_encoded_bytes'] == 437
    assert text['slot_unchanged'] and text['owner_unchanged']
    assert text['source_sha256'] == text['baseline_sha256']
    assert text['pointer_owner'] == {'rom_offset': '0x01E7093B', 'gba_address': '0x09E7093B'}
    assert text['pointer_bytes'] == '4e 19 f1 09'
    assert text['source_controls'] == {'FE': 7, 'FA': 0, 'FB': 8, 'FC': 0, 'FD': 3}
    assert text['codec_roundtrip'] and text['terminator'] == 'FF'
    assert not text['present_in_applied_2403']


def test_interior_match_cannot_prove_writer_or_overflow(result):
    text = result[1]['PCS_comparison']
    assert text['match']['entry_byte_offset'] == 134 and text['match']['byte_count'] == 24
    assert text['match']['rom_offset'] == '0x01F119D4'
    assert text['match']['decode'] == '\nthan if you were to rem'
    assert text['copy_writer'] == 'UNKNOWN' and not text['buffer_overflow_proven']
    assert text['source_to_ram_identity'] == 'BYTE_PROVENANCE_NOT_EXECUTION_OR_CAUSAL_PROOF'


def test_bad_callback_guard_rejects_unexpected_code():
    source = (m.ROOT / m.SOURCE).read_bytes()
    changed = bytearray((m.ROOT / m.BASELINE).read_bytes())
    changed[0x087F28] ^= 1
    with pytest.raises(AssertionError):
        m.static_callback(source, changed)


def test_owner_guard_rejects_unexpected_pointer():
    source = (m.ROOT / m.SOURCE).read_bytes()
    changed = bytearray((m.ROOT / m.BASELINE).read_bytes())
    changed[0x1E7093B] ^= 1
    entry = next(e for e in m.read('out/unbound-texts.json')['entries'] if e['id'] == 'scr_1F1194E')
    old = m.read('out/phase7/ja_renderer_runtime_trace_log.json')['crash_evidence']
    with pytest.raises(AssertionError):
        m.compare_text(source, changed, entry, bytes.fromhex(old['state_bytes']))


def test_keep_2403_774_and_all_story_unapproved(result):
    summary = result[0]['unchanged_management']
    assert summary['applied_unchanged'] == 2403 and summary['phase6_holds_unchanged'] == 774
    assert summary['story_not_reached'] == 53 and summary['injection_approvals'] == 0


def test_artifacts_reproduce_byte_exact(result):
    assert all((m.ROOT / path).read_bytes() == raw for path, raw in m.output_bytes(result).items())


def test_no_overwriting_existing_deliverables(result):
    before = {path: (m.ROOT / path).read_bytes() for path in m.OUTPUTS}
    with pytest.raises(AssertionError, match='Existing deliverable refused'):
        m.persist_new(result)
    assert before == {path: (m.ROOT / path).read_bytes() for path in m.OUTPUTS}


@pytest.mark.parametrize('path', sorted(protection.PHASE7C6_PATHS))
def test_each_exact_allowlist_path_removal_still_fails(path, monkeypatch):
    assert (m.ROOT / path).is_file()
    monkeypatch.setattr(protection, 'LATER_STAGE_PATHS', protection.LATER_STAGE_PATHS - {path})
    with pytest.raises(AssertionError, match='Existing file changed'):
        protection.protected_snapshot()


def test_unlisted_new_file_still_fails():
    probe = m.ROOT / 'out/phase7/_phase7c6_unlisted_probe.json'
    assert not probe.exists()
    try:
        probe.write_text('{}', encoding='utf-8')
        with pytest.raises(AssertionError, match='Existing file changed'):
            protection.protected_snapshot()
    finally:
        probe.unlink()
    assert protection.protected_snapshot()['files'] == 909


def test_safety_gates_and_expected_hashes_unmodified(result):
    proof = result[0]['protection']['protected909']
    assert proof['files'] == 909
    assert proof['aggregate_sha256'] == protection.INITIAL_SNAPSHOT
    assert len(result[0]['protection']['existing_save_sha256']) == 7
    assert m.sha((m.ROOT / m.BASELINE).read_bytes()) == m.BASELINE_SHA


def test_no_emulator_automation_or_patch_writes_in_script():
    source = Path(m.__file__).read_text(encoding='utf-8')
    tree = ast.parse(source)
    calls = [node.func.attr for node in ast.walk(tree) if isinstance(node, ast.Call)
             and isinstance(node.func, ast.Attribute)]
    assert not {'press_key', 'type_text', 'Popen', 'send', 'query'} & set(calls)
    assert "'xb'" in source and 'Existing deliverable refused' in source
