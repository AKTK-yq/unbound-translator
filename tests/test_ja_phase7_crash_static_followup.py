"""Synthetic exact match is not live callback-writer or Japanese-cause proof."""
import ast
from pathlib import Path

import pytest

from lib.pcs_text import Charmap
from scripts import investigate_ja_phase7_crash_static_followup as m
from scripts import build_ja_phase6_cleanup_batch03 as protection


@pytest.fixture(scope='module')
def rom():
    return (m.ROOT / 'rom/unbound.gba').read_bytes()


@pytest.fixture(scope='module')
def data():
    return m.investigate()


def normal_buffers():
    return {2: Charmap().encode('him'), 3: Charmap().encode('he'), 4: Charmap().encode('son')}


def test_first_fd04_and_actual_buffer_alias_layout(data):
    routes = data['routes']
    assert routes['field_copy']['destination'] == '0x02021D18'
    assert routes['buffer3']['ram'] == '0x02021D04'
    assert routes['buffer3']['bytes_before_field_destination'] == 20
    assert routes['buffer3']['factory_table_owner']['rom_offset'] == '0x00231E80'
    assert routes['relevant_english_ja_bytes_equal']


def test_period_and_all_24_bytes_match_not_only_crash_pointer(data):
    hypothesis = data['alias_hypothesis']
    assert hypothesis['first_FD04_text_offset'] == 283
    assert hypothesis['repeat_period_bytes'] == 303
    assert hypothesis['callback_state_phase'] == 154
    assert hypothesis['matching_entry_byte_offset'] == 134
    assert hypothesis['matched_bytes'] == 24
    assert hypothesis['predicted'] == hypothesis['historical_observed']
    assert hypothesis['predicted_callback_thumb'] == '0xE3E800D9'
    assert hypothesis['predicted_pc_after_bx'] == '0xE3E800D8'


@pytest.mark.parametrize('normal', ['normal_male', 'normal_female'])
def test_normal_ff_terminated_buffers_return_before_callback(data, normal):
    model = data['models'][normal]
    assert model['returned'] and model['stop_reason'] is None
    assert model['callback_writes'] == []
    assert model['writes'] < 500


def test_missing_buffer3_ff_copies_into_callback_only_in_model(data):
    model = data['models']['unterminated_buffer3']
    assert not model['returned'] and model['stop_reason'] == 'TARGET_RANGE_CAPTURED'
    assert [e['byte'] for e in model['callback_writes']] == ['D9', '00', 'E8', 'E3']
    assert [e['address'] for e in model['callback_writes']] == ['0x02039610', '0x02039611', '0x02039612', '0x02039613']
    assert all(e['observed_pc'] is None and e['status'] == 'SYNTHETIC_NOT_OBSERVED' for e in model['callback_writes'])
    assert not model['runtime_writer_captured']


def test_alias_requires_live_reads_not_pre_snapshotted_child(rom, data):
    inputs = {**normal_buffers(), 4: Charmap().encode('abcdefghijklmnopqrst')[:-1]}
    assert len(inputs[4]) == 20 and 0xFF not in inputs[4]
    model = m.expand_model(rom, inputs)
    assert model['state_bytes'] == data['alias_hypothesis']['historical_observed']
    assert model['stop_reason'] == 'TARGET_RANGE_CAPTURED'


@pytest.mark.parametrize('index,size', [(2, 32), (3, 20)])
def test_missing_other_terminator_not_automatically_same_infinite_alias(rom, index, size):
    model = m.expand_model(rom, {**normal_buffers(), index: bytes(size)})
    # Later adjacent buffers retain FF; do not generalize the buffer3 hypothesis.
    assert model['returned'] and not model['callback_writes']


def test_write_budget_can_stop_without_fabricating_evidence(rom):
    model = m.expand_model(rom, {**normal_buffers(), 4: bytes(20)}, max_writes=300)
    assert model['writes'] == 300 and model['stop_reason'] == 'WRITE_BUDGET'
    assert model['callback_writes'] == []


def test_model_rejects_fc_and_unknown_placeholders(rom):
    for raw in (b'\xFC\x15\xFF', b'\xFD\x01\xFF'):
        with pytest.raises(ValueError):
            m.expand_model(rom, {**normal_buffers(), 4: raw})


def test_newline_and_page_controls_are_preserved_not_executed(data):
    assert data['models']['normal_male']['method'].startswith('BOUNDED_SYNTHETIC')
    assert data['models']['unterminated_buffer3']['state_bytes'].startswith('fe e8')


def test_gender_branches_supply_terminators_but_no_live_branch_inference(data):
    preparation = data['routes']['script_preparation']
    assert [[e['text'] for e in b['copies']] for b in preparation['branches']] == [
        ['him', 'he', 'son'], ['her', 'she', 'daughter']]
    assert [e['bytes_including_FF'] for e in preparation['branches'][0]['copies']] == [4, 3, 4]
    assert [e['bytes_including_FF'] for e in preparation['branches'][1]['copies']] == [4, 4, 9]
    assert 'actual bridge value UNKNOWN' in preparation['other_gender_values']
    assert not preparation['runtime_executed']


def test_model_match_never_approves_runtime_or_identifies_root_cause(data):
    assert data['alias_hypothesis']['status'] == 'CONDITIONAL_EXACT_MATCH_NOT_RUNTIME_PROVEN'
    assert data['alias_hypothesis']['root_cause'] == data['japanese_causality'] == 'UNKNOWN'
    assert data['alias_hypothesis']['observed_live_writer'] is None
    assert data['new_runtime_trials'] == 0 and not data['writer_captured']
    assert not data['ROM_patch']


def test_unexpected_rom_code_rejected_before_model(rom):
    altered = bytearray((m.ROOT / 'out/unbound-ja-phase6-cleanup-batch04.gba').read_bytes())
    altered[0x090A6] ^= 1
    with pytest.raises(AssertionError):
        m.static_routes(rom, altered)


def test_prior_phase_reports_and_translation_inputs_unchanged(data):
    for path, expected in data['prior_sha256'].items():
        assert m.sha((m.ROOT / path).read_bytes()) == expected
    assert data['protected909']['files'] == 909
    assert data['protected909']['aggregate_sha256'] == protection.INITIAL_SNAPSHOT


def test_followup_reproduces_and_refuses_overwriting(data):
    content = m.output_bytes(data)
    assert all((m.ROOT / path).read_bytes() == raw for path, raw in content.items())
    with pytest.raises(AssertionError, match='Existing follow-up refused'):
        m.persist_new(data)
    assert all((m.ROOT / path).read_bytes() == raw for path, raw in content.items())


@pytest.mark.parametrize('path', [*m.OUTPUTS,
                                 'scripts/investigate_ja_phase7_crash_static_followup.py',
                                 'tests/test_ja_phase7_crash_static_followup.py'])
def test_exact_new_allowlist_member_removal_fails(path, monkeypatch):
    assert path in protection.PHASE7C6_PATHS
    monkeypatch.setattr(protection, 'LATER_STAGE_PATHS', protection.LATER_STAGE_PATHS - {path})
    with pytest.raises(AssertionError):
        protection.protected_snapshot()


def test_script_has_no_capture_input_process_or_network_interfaces():
    source = Path(m.__file__).read_text(encoding='utf-8')
    tree = ast.parse(source)
    imports = {node.names[0].name.split('.')[0] for node in ast.walk(tree) if isinstance(node, ast.Import)}
    assert not imports & {'socket', 'subprocess', 'requests', 'ctypes', 'PIL'}
    calls = {node.func.attr for node in ast.walk(tree) if isinstance(node, ast.Call)
             and isinstance(node.func, ast.Attribute)}
    assert not calls & {'get_window_state', 'press_key', 'Popen', 'connect', 'send', 'query'}
