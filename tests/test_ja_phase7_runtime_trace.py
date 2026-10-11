"""Read-only runtime evidence: no invented identity or blanket layout approval."""
import json
from pathlib import Path
import struct

import pytest

from scripts import investigate_ja_phase7_runtime_trace as m
from scripts import build_ja_phase6_cleanup_batch03 as protection


@pytest.mark.parametrize('packet', ['M2020010,1:00', 'X2020010,1:0', 'P0=00000000',
                                  'G' + '00' * 68, 'c08008fcc', 'Z0,08008fcc,2',
                                  'Z2,02020010,1', 'm4000000,4', 'm9ffffff,2',
                                  'm2020010,201', 'm2020010,0'])
def test_write_and_out_of_bounds_packets_rejected(packet):
    assert not m.permitted_packet(packet)


@pytest.mark.parametrize('packet', ['g', '?', 'c', 's', 'm2020010,24',
                                  'Z1,08008fcc,2', 'z1,08008fcc,2'])
def test_read_and_hardware_breakpoints_permitted(packet):
    assert m.permitted_packet(packet)


def test_register_reply_layout():
    reader = object.__new__(m.Reader)
    reader.query = lambda _: struct.pack('<17I', *range(17)).hex()
    assert reader.registers()['pc'] == 15
    assert reader.registers()['cpsr'] == 16
    reader.query = lambda _: '00'
    with pytest.raises(ValueError):
        reader.registers()


def test_missing_ram_stays_unknown():
    record = {'memory': {'test': {'address': '0x02020010', 'bytes': '01 02 03'}}}
    assert m.memory_at(record, 0x02020011, 2) == b'\x02\x03'
    assert m.memory_at(record, 0x02020012, 2) is None
    assert m.printer_fields(None) is None


def test_pointer_exact_only_not_interior_or_similar_text():
    rows = [{'id': 'real', 'address': '0x1F0F5A6', 'original': 'same text'}]
    assert m.exact_entry(0x09F0F5A6, rows)['id'] == 'real'
    assert m.exact_entry(0x09F0F5A7, rows) is None
    assert m.exact_entry(0x09F0F79C, rows) is None
    assert m.exact_entry(0x09F0F5A6, rows * 2) is None


def test_actual_printer_from_argument_not_guessed_window_array():
    log = m.read_json(m.ROOT / m.OUTPUTS[1])
    event = next(e for e in log['observations'] if e['pc'] == '0x08003014')
    assert event['printer_address'] == '0x02020010'
    assert event['printer']['dispatch_font'] == event['printer']['template_font'] == 2
    assert event['printer']['japanese']
    assert event['printer']['letter_spacing'] == 1
    assert event['printer']['line_spacing'] == 0
    assert event['window']['width_px'] == 224  # Not field template208.
    assert event['glyph_width'] == 10 and event['glyph_height'] == 12
    assert event['copy_right_exclusive'] == 48 and not event['clipping_exercised']
    assert event['reserved_padding'] == 'UNKNOWN'


def test_observed_cursor_and_fe_not_field_step_assumption():
    events = m.read_json(m.ROOT / m.OUTPUTS[1])['observations']
    cursor = next(e for e in events if e['pc'] == '0x08005C4E')
    assert cursor['cursor_value_before_store'] == 49 and cursor['addend'] == 11
    fe = next(e for e in events if e['pc'] == '0x0800589E')
    assert fe['new_y'] == 18 and fe['line_step'] == 14


def test_failed_attempts_and_unreached_controls_not_runtime_pass():
    log = m.read_json(m.ROOT / m.OUTPUTS[1])
    assert not log['runtime_fit_pass'] and not log['new_translation_injected']
    assert any(a['capture_errors'] for a in log['raw_capture_attempts'])
    assert log['FA'] == log['FB'] == log['player_expansion'] == 'NOT_REACHED'
    assert log['font4_5'] == 'NOT_REACHED'
    selector = next(e for e in log['observations'] if e['pc'] == '0x080F6D7C')
    assert selector['selector'] == 3 and selector['entry_id'] == 'UNKNOWN_ENTRY'
    assert selector['selected_font_confidence'].startswith('STATIC_PROVEN')
    for attempt in log['raw_capture_attempts']:
        for packet in attempt['packet_transcript']:
            if packet['direction'] == 'sent' and packet['payload'] != 'INTERRUPT_03':
                assert m.permitted_packet(packet['payload'])
            if packet['direction'] == 'received':
                assert sum(packet['payload'].encode('ascii')) & 255 == int(packet['checksum'], 16)


def test_all_53_retained_without_promotions_and_semantic_hold():
    proof = m.read_json(m.ROOT / m.OUTPUTS[2])
    prior = m.read_json(m.ROOT / 'out/phase7/ja_story_batch01_renderer_inventory.json')
    rows = proof['entries']
    assert len(rows) == len({e['canonical_id'] for e in rows}) == 53
    assert [e['canonical_id'] for e in rows] == [e['canonical_id'] for e in prior['entries']]
    assert all(e['runtime_status'] == 'NOT_REACHED' and not e['runtime_fit_approved'] for e in rows)
    assert [e['batch_index'] for e in rows if e['semantic_hold_maintained']] == [1, 31, 40]
    assert proof['summary']['proven_live_fit'] == proof['summary']['injection_approvals'] == 0
    assert proof['summary']['control_sample_source_ids'] == ['scr_1F0F5A6']


def test_baseline_and_protected_909_unchanged():
    assert m.sha((m.ROOT / m.BASELINE).read_bytes()) == m.BASELINE_SHA
    assert protection.protected_snapshot()['files'] == 909


def test_removed_allowlist_member_fails(monkeypatch):
    path = 'scripts/investigate_ja_phase7_runtime_trace.py'
    monkeypatch.setattr(protection, 'LATER_STAGE_PATHS', protection.LATER_STAGE_PATHS - {path})
    with pytest.raises(AssertionError, match='Existing file changed'):
        protection.protected_snapshot()


def test_unlisted_path_still_detected(monkeypatch, tmp_path):
    # Independent isolated miniature root, no mutation of repository artifacts.
    (tmp_path / 'docs').mkdir()
    (tmp_path / 'docs' / 'unexpected.json').write_text('{}', encoding='utf-8')
    monkeypatch.setattr(protection, 'ROOT', tmp_path)
    monkeypatch.setattr(protection.subprocess, 'check_output', lambda *a, **k: 'docs/unexpected.json\n')
    with pytest.raises(AssertionError, match='Existing file changed'):
        protection.protected_snapshot()


def test_existing_deliverables_not_overwritten():
    before = {p: (m.ROOT / p).read_bytes() for p in m.OUTPUTS}
    with pytest.raises(AssertionError, match='Existing deliverable refused'):
        m.persist_results([])
    assert before == {p: (m.ROOT / p).read_bytes() for p in m.OUTPUTS}


def test_reproduction_json_has_real_addresses_and_no_injection():
    repro = m.read_json(m.ROOT / m.OUTPUTS[3])
    assert 'b 08008FCC' in repro['commands'] and 'b 08003014' in repro['commands']
    assert repro['remaining']['FA_semantic_hold'] == [1, 31, 40]
    assert 'No translation injection approval' in repro['approval']


def test_observed_crash_never_becomes_a_story_renderer_proof():
    log = m.read_json(m.ROOT / m.OUTPUTS[1])
    assert log['runtime_execution_result'] == 'CRASH_OBSERVED'
    crash = log['crash_evidence']
    assert crash['registers']['pc'] == '0xE3E800D8'
    assert crash['registers']['r3'] == '0xE3E800D9'
    assert crash['cause'] == 'UNRESOLVED' and crash['writer'] == 'UNKNOWN'
    assert crash['identity_status'] == 'BYTE_PROVENANCE_ONLY_NOT_RENDERER_ENTRY_PROOF'
    assert crash['containing_entry'] == 'scr_1F1194E'
    assert crash['callback_code_unchanged_from_source']
    assert not log['runtime_fit_pass']
