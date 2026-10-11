"""Read-only, fail-closed ROM/geometry and artifact protection regression."""
import ast
from copy import deepcopy
from pathlib import Path
import subprocess

import pytest

from lib.pcs_text import Charmap
from scripts import investigate_ja_phase7_renderer as m


@pytest.fixture(scope='module')
def data():
    return m.investigate()


@pytest.fixture(scope='module')
def tables():
    return m.font_tables((m.ROOT / 'rom/unbound.gba').read_bytes())


def test_all_53_ids_and_exclusive_primary_classes(data):
    records = data['inventory']['entries']
    previous = m.read('out/phase7/ja_story_batch01_technical_holds.json')['entries']
    assert len(records) == len({r['canonical_id'] for r in records}) == 53
    assert [r['canonical_id'] for r in records] == [r['id'] for r in previous]
    assert [r['batch_index'] for r in records] == list(range(53))
    assert data['inventory']['summary']['primary_classification'] == {'A': 0, 'B': 15, 'C': 38, 'D': 0}
    assert data['inventory']['summary']['consumer_confidence'] == {'CONDITIONAL': 53}
    assert all(r['local_dispatch_confidence'] == 'PROVEN' for r in records)
    assert all(r['proven_live_max_width'] is None and not r['runtime_fit_approved'] for r in records)


def test_font_literal_ownership_and_exact_differences(data):
    profiles = data['profiles']['profiles']
    assert [r['font_id'] for r in profiles] == [2, 4, 5]
    assert [r['japanese_width_table']['rom_offset'] for r in profiles] == ['0x0020F500', '0x0021F818', '0x0022FB30']
    assert profiles[0]['japanese_width_differences_from_normal'] == []
    assert profiles[1]['japanese_width_differences_from_normal'] == [{'code': '0x2F', 'glyph': 'ぁ', 'normal': 9, 'this_font': 10}]
    assert profiles[2]['japanese_width_differences_from_normal'] == [{'code': '0x86', 'glyph': 'ョ', 'normal': 9, 'this_font': 8}]
    assert all(r['latin_width_table']['equals_repository_normal_latin'] for r in profiles)
    assert all(r['confidence'] == 'CONDITIONAL' and not r['runtime_fit_approval'] for r in profiles)


@pytest.mark.parametrize('font,glyph,expected', ((2, 'ぁ', 9), (4, 'ぁ', 10), (5, 'ぁ', 9),
                                               (2, 'ョ', 9), (4, 'ョ', 9), (5, 'ョ', 8)))
def test_font_specific_glyph_spacing_and_copy_footprint(tables, font, glyph, expected):
    raw = Charmap('ja').encode('[japanese]' + glyph + '[latin]')
    result = m.measure(raw, tables, font)
    assert result['max_copy_right_static'] == expected
    assert result['max_static_advance'] == expected + 1
    assert result['max_copy_bottom_static'] == 13


def test_space_and_latin_extra_spacing_are_not_japanese(tables):
    raw = Charmap('ja').encode('[japanese] [latin]A')
    result = m.measure(raw, tables, 2)
    assert result['max_static_advance'] == 17  # space10+1 and Latin A6+0
    assert result['max_copy_right_static'] == 17
    assert result['lines'][0]['japanese_glyphs'] == 1


def test_all_three_font_maxima_and_footprint_not_cursor(data):
    s = data['inventory']['summary']
    assert s['max_advance_by_conditional_font'] == {'2': 220, '4': 220, '5': 220}
    assert s['max_copy_right_by_conditional_font'] == {'2': 219, '4': 219, '5': 219}
    assert len(s['candidate_208_cursor_exceedance_indices']) == 21
    assert len(s['candidate_208_exceedance_indices']) == 17
    assert set(s['candidate_208_cursor_exceedance_indices']) - set(s['candidate_208_exceedance_indices']) == {1, 13, 36, 40}
    assert s['conditional_vertical_exceedance_indices'] == []
    prior = m.read('out/phase7/ja_story_batch01_technical_holds.json')['entries']
    for r, old in zip(data['inventory']['entries'], prior):
        assert r['widths_per_font_condition']['2']['max_static_advance'] == old['width_status']['normal_spacing1_diagnostic']['max_static_with_spacing']


def test_fe_fa_fb_keep_language_and_separate_y_behavior(tables):
    raw = Charmap('ja').encode('[japanese]こ\nん\\lに\n\nち[latin]')
    result = m.measure(raw, tables, 2)
    assert [r['y'] for r in result['lines']] == [1, 16, 16, 1]
    assert [e['control'] for e in result['page_events']] == ['FE', 'FA', 'FB']
    assert all(e['page_japanese'] for e in result['page_events'])
    assert result['page_events'][1]['scroll_pixels'] == 15
    assert not result['final_japanese_page']
    assert result['max_copy_bottom_static'] == 28


def test_third_fe_line_is_clipped_in_conditional_32_height(tables):
    raw = Charmap('ja').encode('[japanese]こ\nん\nに[latin]')
    result = m.measure(raw, tables, 2)
    assert result['max_copy_bottom_static'] == 43
    assert not result['cursor_over_255_diagnostic']


def test_unknown_player_is_not_zero_width_approval(tables):
    raw = Charmap('ja').encode('[japanese]こ[latin][player][japanese]ん[latin]')
    result = m.measure(raw, tables, 2)
    assert result['unresolved_dynamic'] and result['conditional_max_total'] is None
    assert result['max_static_advance'] == 22
    local = m.measure(raw, tables, 2, name_bound=42)
    assert local['conditional_max_total'] == 64
    assert local['status'] == 'CONDITIONAL_COMPONENT_MODEL_NOT_LIVE_FIT'


def test_ordinary_player_expansion_returns_to_japanese(tables):
    raw = Charmap('ja').encode('[japanese]こ[latin][player][japanese]ん[latin]')
    child = Charmap().encode('WMMMMMM')
    expanded = raw.replace(b'\xfd\x01', child[:-1])  # ROM recursive copy omits childFF.
    result = m.measure(expanded, tables, 2)
    assert result['conditional_max_total'] == 64
    assert result['lines'][0]['japanese_glyphs'] == 2
    assert not result['final_japanese_page']


def test_buffer_embedded_controls_are_not_made_safe_by_page_wrapper(tables):
    raw = Charmap('ja').encode('[japanese]こ[latin][player][japanese]ん[latin]')
    expanded = raw.replace(b'\xfd\x01', b'\xfc\x06\x04\xfe')
    result = m.measure(expanded, tables, 2)
    assert result['unsupported_controls'] == ['FC06']
    assert result['conditional_max_total'] is None
    assert result['lines'][-1]['y'] == 16
    assert not result['final_japanese_page']


def test_fc_argument_fa_is_not_page_scroll(tables):
    raw = bytes.fromhex('fc 15 0a fc 08 fa 2e fc 16 ff')
    result = m.measure(raw, tables, 2)
    assert result['page_events'] == [] and result['max_static_advance'] == 22


def test_unknown_geometry_controls_fail_closed(tables):
    result = m.measure(bytes.fromhex('fc 15 0a fc 14 20 2e fc 16 ff'), tables, 2)
    assert result['unsupported_controls'] == ['FC14'] and result['conditional_max_total'] is None


def test_model_reports_byte_cursor_wrap_not_implicit_wrap(tables):
    result = m.measure(Charmap('ja').encode('[japanese]' + 'こ' * 24 + '[latin]'), tables, 2)
    assert result['max_static_advance'] == 264 and result['cursor_over_255_diagnostic']
    assert len(result['lines']) == 1 and not result['page_events']


def test_native8a_is_not_window_initializer(data):
    native = data['profiles']['std6_native_8A']
    assert native['handler']['rom_offset'] == '0x01EC9DD0'
    assert native['task']['rom_offset'] == '0x00069570'
    assert 'No InitWindows' in native['finding']
    assert data['profiles']['fully_live_proven_profiles'] == 0


def test_names_remain_held_despite_local_writer_and42(data):
    name = data['profiles']['name_buffer']
    assert name['commit_copy_call']['rom_offset'] == '0x0009F830'
    assert name['local_keyboard_width_per_font'] == {'2': 42, '4': 42, '5': 42}
    assert name['arbitrary_ordinary_latin7_diagnostic'] == {'2': 84, '4': 84, '5': 84}
    assert name['universal_safe_width'] is None and not name['automatic_fit_approval']
    rows = [r for r in data['inventory']['entries'] if r['conditional_local_keyboard42_widths']]
    assert len(rows) == 10
    assert all(r['widths_per_font_condition']['2']['conditional_max_total'] is None for r in rows)
    assert not name['defaults_enumerated'] and not name['external_values_bounded']


def test_semantic_and_other_independent_holds_unchanged(data):
    rows = data['inventory']['entries']
    old = m.read('out/phase7/ja_story_batch01_technical_holds.json')['entries']
    for row, prior in zip(rows, old):
        assert row['original_all_holds_unchanged'] == prior['all_holds']
        assert row['fa_semantic_verdict'] == prior['fa_semantic_verdict']
        assert row['meaning_verdict'] == prior['semantic_state']['status']
    for i in (1, 31, 40):
        assert rows[i]['fa_semantic_verdict'] == 'FA_SEMANTIC_BOUNDARY_REVIEW_REQUIRED'
        assert rows[i]['classification_primary'] == 'C'
    assert rows[31]['completed_name_reveal']['early_by_waits'] == 1
    assert rows[40]['completed_name_reveal']['early_by_waits'] == 1
    assert rows[21]['slot_size'] == 19 and rows[21]['encoded_bytes'] == 23
    assert rows[21]['relocation_needed_not_approved'] and not rows[21]['translation_or_injection_approval']


def test_no_unproved_runtime_claim_and_qa_all53(data):
    qa = data['runtime_qa']
    assert len(qa['entries']) == 53
    assert not qa['test_performed'] and not qa['runtime_PASS']
    assert all(not r['japanese_candidate_installed'] and not r['runtime_PASS'] for r in qa['entries'])
    assert all(r['arrival_steps'].startswith('UNKNOWN') for r in qa['entries'])
    assert data['inventory']['applied_payload_proof']['verified_payloads'] == 2403
    assert data['inventory']['summary']['phase6_remaining_unchanged'] == 774


def test_no_existing_gate_or_rom_or_input_changes(data):
    assert data['inventory']['management_proof']['existing_function_AST_changes'] == 0
    assert m.snapshot() == data['inventory']['immutable_input_sha256']
    assert m.sha((m.ROOT / m.BASE_ROM).read_bytes()) == m.BASE_SHA
    assert m.protection.protected_snapshot()['files'] == 909
    assert m.protection.protected_snapshot()['aggregate_sha256'] == m.protection.INITIAL_SNAPSHOT


def test_deterministic_results_and_existing_reports(data):
    again = m.investigate()
    assert m.output_bytes(again) == m.output_bytes(data)
    for relative, content in m.output_bytes(data).items():
        assert (m.ROOT / relative).read_bytes() == content


def test_exclusive_writer_checks_all_paths_before_writing(data, tmp_path, monkeypatch):
    monkeypatch.setattr(m, 'ROOT', tmp_path)
    existing = tmp_path / m.OUTPUTS[-1]
    existing.parent.mkdir(parents=True)
    existing.write_bytes(b'PRESERVE USER ARTIFACT')
    with pytest.raises(AssertionError):
        m.persist_new(data)
    assert existing.read_bytes() == b'PRESERVE USER ARTIFACT'
    assert not (tmp_path / m.OUTPUTS[0]).exists()


def test_exact_paths_and_removed_allowance_fails(data, monkeypatch):
    allowed = set(m.OUTPUTS) | {'scripts/investigate_ja_phase7_renderer.py', 'tests/test_ja_phase7_renderer.py'}
    assert m.protection.PHASE7C4_PATHS == frozenset(allowed)
    assert not any(c in p for p in allowed for c in '*?[')
    for relative in sorted(allowed):
        with monkeypatch.context() as patch:
            patch.setattr(m.protection, 'LATER_STAGE_PATHS', m.protection.LATER_STAGE_PATHS - {relative})
            with pytest.raises(AssertionError):
                m.protection.protected_snapshot()


def test_unlisted_file_still_fails_without_creating_repo_artifact(monkeypatch):
    relative = 'docs/unapproved_renderer_probe.md'
    fake = m.ROOT / relative
    real_check = subprocess.check_output
    real_is_file, real_bytes = Path.is_file, Path.read_bytes
    def check(command, *args, **kwargs):
        result = real_check(command, *args, **kwargs)
        if command[:2] == ['git', 'ls-files']:
            return result + relative + '\n'
        return result
    monkeypatch.setattr(subprocess, 'check_output', check)
    monkeypatch.setattr(Path, 'is_file', lambda p: True if p == fake else real_is_file(p))
    monkeypatch.setattr(Path, 'read_bytes', lambda p: b'UNAPPROVED' if p == fake else real_bytes(p))
    with pytest.raises(AssertionError):
        m.protection.protected_snapshot()
