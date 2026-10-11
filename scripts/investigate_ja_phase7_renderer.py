#!/usr/bin/env python3
"""Phase 7C-4: read-only ROM investigation; exclusive new report writer.

No translation, controlfix, injector, emulator, or ROM-writing entry point runs.
``python scripts/investigate_ja_phase7_renderer.py`` checks the investigation.
``--write`` creates only the four previously absent declared reports.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lib.gen3_font import NORMAL_GLYPH_WIDTHS, NORMAL_JAPANESE_GLYPH_WIDTHS
from lib.pcs_text import Charmap, JAPANESE_PCS_CHAR_TABLE, decode_pcs, fc_arg_count
from lib.renderer_profiles import rom_naming_profiles
from lib.translation_tokens import strip_hma_quotes
from scripts import build_ja_phase6_cleanup_batch03 as protection
from scripts import build_ja_phase7_story_batch01 as previous

OUTPUTS = (
    'docs/ja-phase7-renderer-investigation.md',
    'out/phase7/ja_renderer_consumer_profiles.json',
    'out/phase7/ja_story_batch01_renderer_inventory.json',
    'tests/fixtures/ja_phase7_renderer_runtime_qa.json',
)
INPUTS = (
    'docs/ja-phase7-story-batch01-technical.md',
    'tests/fixtures/ja_phase7_story_batch01_claude_review.json',
    'out/phase7/ja_story_batch01_technical_holds.json',
    'out/phase7/ja_story_batch01_validation.json',
    'tests/fixtures/ja_phase7_story_batch01_runtime_qa.json',
    'docs/ja-phase6-fa-bottleneck-investigation.md',
    'out/phase7/ja_story_translation_batch01_for_claude.json',
    'out/phase7/ja_full_localization_inventory.json',
    'glossaries/ja.json',
    'lib/pcs_text.py', 'lib/gen3_font.py', 'lib/renderer_profiles.py',
    'lib/fa_control.py', '004_controlfix_translations.py',
    '005_hybrid_injector.py', 'scripts/build_ja_phase7_story_batch01.py',
)
BASE_ROM = 'out/unbound-ja-phase6-cleanup-batch04.gba'
BASE_SHA = '0d1d00e7b0f4f113514abbcf1907e6d8949fd12b9193bf2cb0ad764ace5559d8'
SOURCE_MD5 = '9cad8e771940e7f7094d13911552cef0'
FONT_DATA = {
    2: {'wrapper': 0x53E8, 'glyph_routine': 0x65B8, 'japanese_glyph': 0x207500,
        'japanese_width': 0x20F500, 'latin_width': 0x207300,
        'glyph_literal': 0x6650, 'japanese_literal': 0x6658, 'latin_literal': 0x6698},
    4: {'wrapper': 0x5458, 'glyph_routine': 0x67EC, 'japanese_glyph': 0x217818,
        'japanese_width': 0x21F818, 'latin_width': 0x217618,
        'glyph_literal': 0x6884, 'japanese_literal': 0x688C, 'latin_literal': 0x6928},
    5: {'wrapper': 0x5490, 'glyph_routine': 0x6958, 'japanese_glyph': 0x227B30,
        'japanese_width': 0x22FB30, 'latin_width': 0x227930,
        'glyph_literal': 0x69F0, 'japanese_literal': 0x69F8, 'latin_literal': 0x6A94},
}
# Bounded code slices avoid treating literal pools as instructions.
BLOCKS = (
    (0xF6CD0, 0xF6D58), (0xF6D5C, 0xF6DA6), (0xF6DB0, 0xF6DD6),
    (0xF6DDC, 0xF6E04), (0x9C9EE0, 0x9C9F1A),
    (0x9C9E54, 0x9C9E84), (0x9C9CB4, 0x9C9D20),
    (0xF79C8, 0xF79D4), (0x2C1C, 0x2C22), (0x2CF4, 0x2D0A),
    (0x2D30, 0x2D4C), (0x2E7C, 0x2EA4),
    (0x53E8, 0x541C), (0x5458, 0x548C), (0x5490, 0x54C4),
    (0x5B6C, 0x5B80), (0x5B9C, 0x5BEE),
    (0x65B8, 0x65F4), (0x65F8, 0x664E),
    (0x67EC, 0x6828), (0x682C, 0x6882),
    (0x6958, 0x6994), (0x6998, 0x69EE),
    (0x6890, 0x68C8), (0x68D0, 0x691E),
    (0x69FC, 0x6A34), (0x6A3C, 0x6A8A),
    (0x3014, 0x3082), (0x5880, 0x589E),
    (0x5B10, 0x5B34), (0x5C28, 0x5C40), (0x5C44, 0x5C50),
    (0x5C6C, 0x5CCA), (0x5CD0, 0x5D02), (0x5D0C, 0x5D44),
    (0x5634, 0x5638), (0xA0F1CC, 0xA0F240),
    (0x1EC9DD0, 0x1EC9DEC), (0x1ECEBC8, 0x1ECEBD2),
    (0x69570, 0x69590), (0x69590, 0x695B2), (0x5C270, 0x5C2AC),
    (0x6FB22, 0x6FB34), (0x3B24, 0x3BB8),
    (0xA093AC, 0xA093E6), (0x6943C, 0x69456), (0x694C8, 0x694E0),
    (0x8FCC, 0x8FE8), (0x9004, 0x9034), (0x908C, 0x90B8),
    (0x91E0, 0x91F4), (0x9120, 0x9126),
    (0x9D954, 0x9D980), (0x9D984, 0x9D9C8),
    (0x9DAC4, 0x9DAD8), (0x9DAD8, 0x9DB3A),
    (0x9F634, 0x9F662), (0x9DFA4, 0x9DFEC),
    (0x9F7EC, 0x9F7FE), (0x9F808, 0x9F836), (0x9F83C, 0x9F858),
)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def serialized(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8')


def read(path):
    return json.loads((ROOT / path).read_text(encoding='utf-8'))


def u32(rom, offset):
    return int.from_bytes(rom[offset:offset + 4], 'little')


def location(offset):
    return {'rom_offset': f'0x{offset:08X}', 'gba_address': f'0x{offset + 0x08000000:08X}'}


def snapshot():
    paths = set(INPUTS) | set(previous.PHASE7A_PATHS | previous.PHASE7B_PATHS
        | previous.PHASE7C1_PATHS | previous.PHASE7C2_PATHS | previous.PHASE7C3_PATHS)
    return {p: sha((ROOT / p).read_bytes()) for p in sorted(paths)}


def management_proof():
    """Only exact path-set management is permitted in the existing guard."""
    relative = 'scripts/build_ja_phase6_cleanup_batch03.py'
    old = subprocess.check_output(['git', 'show', 'HEAD:' + relative], cwd=ROOT).decode()
    new = (ROOT / relative).read_text(encoding='utf-8')
    def functions(text):
        tree = ast.parse(text)
        return {n.name: ast.dump(n, include_attributes=False) for n in tree.body
                if isinstance(n, ast.FunctionDef)}
    assert functions(old) == functions(new), 'Existing protection function changed'
    assert protection.PHASE7C4_PATHS == frozenset(set(OUTPUTS) | {
        'scripts/investigate_ja_phase7_renderer.py', 'tests/test_ja_phase7_renderer.py'})
    return {'existing_function_AST_changes': 0, 'new_exact_paths': sorted(protection.PHASE7C4_PATHS)}


def font_tables(rom):
    assert rom[0x20F500:0x20F618] == NORMAL_JAPANESE_GLYPH_WIDTHS
    result = {}
    for font, spec in FONT_DATA.items():
        for literal, target in (('glyph_literal', 'japanese_glyph'),
                                ('japanese_literal', 'japanese_width'), ('latin_literal', 'latin_width')):
            assert u32(rom, spec[literal]) == 0x08000000 + spec[target]
        ja = rom[spec['japanese_width']:spec['japanese_width'] + 280]
        latin = rom[spec['latin_width']:spec['latin_width'] + 256]
        assert latin == bytes(NORMAL_GLYPH_WIDTHS)
        record = 0x41F444 + font * 12
        assert u32(rom, record) == 0x08000001 + spec['wrapper']
        assert rom[record + 5] == 14
        diffs = [{'code': f'0x{i:02X}', 'glyph': JAPANESE_PCS_CHAR_TABLE.get(i),
                  'normal': a, 'this_font': b} for i, (a, b) in enumerate(zip(NORMAL_JAPANESE_GLYPH_WIDTHS, ja)) if a != b]
        expected = [] if font == 2 else [{'code': '0x2F', 'glyph': 'ぁ', 'normal': 9, 'this_font': 10}] if font == 4 else [{'code': '0x86', 'glyph': 'ョ', 'normal': 9, 'this_font': 8}]
        assert diffs == expected
        result[font] = {'japanese': ja, 'latin': latin, 'record': record, 'differences': diffs}
    return result


def measure(raw, tables, font, spacing=1, name_bound=None):
    """Conditional ROM cursor/copy-footprint model, not a live fit validator.

    FC01/08 have no geometry effect; FC06/position/min-spacing/icons remain
    unsupported. FD is unresolved unless an explicitly conditional bound is
    supplied. Y is modelled with the observed 14+1 advance, not JP bitmap 12.
    """
    i = x = highest = japanese_count = 0
    japanese = False
    y = 1
    lines, events, unsupported = [], [], []
    unknown = False
    bottom = copy_right = 0
    def line():
        return {'static_advance': x, 'copy_right_bound': copy_right,
                'max_cursor': highest, 'japanese_glyphs': japanese_count,
                'y': y, 'copy_bottom': bottom, 'unknown_dynamic': unknown}
    while i < len(raw):
        value = raw[i]
        i += 1
        if value == 0xFF:
            assert i == len(raw), 'Unexpected bytes after terminator'
            break
        if value == 0xFC:
            assert i < len(raw)
            command = raw[i]
            i += 1
            count = fc_arg_count(command)
            assert i + count <= len(raw)
            i += count
            if command in (0x15, 0x16):
                japanese = command == 0x15
            elif command not in (0x01, 0x08):
                unsupported.append(f'FC{command:02X}')
            continue
        if value in (0xFE, 0xFA, 0xFB):
            lines.append(line())
            before_y = y
            if value == 0xFE:
                y += 15
            elif value == 0xFB:
                y = 1
            events.append({'control': f'{value:02X}', 'page_japanese': japanese,
                           'y_before': before_y, 'y_after': y,
                           'scroll_pixels': 15 if value == 0xFA else 0})
            x = highest = japanese_count = copy_right = bottom = 0
            unknown = False
            continue
        if value == 0xFD:
            assert i < len(raw)
            placeholder = raw[i]
            i += 1
            if placeholder == 1 and name_bound is not None:
                x += name_bound
                copy_right = max(copy_right, x)
                highest = max(highest, x)
                bottom = max(bottom, y + 14)
            else:
                unknown = True
            continue
        if value in (0xF7, 0xF8, 0xF9):
            assert i < len(raw)
            i += 1
            unsupported.append(f'{value:02X}')
            continue
        width = (10 if value == 0 else tables[font]['japanese'][value]) if japanese else tables[font]['latin'][value]
        copy_right = max(copy_right, x + width)
        bottom = max(bottom, y + (12 if japanese else 14))
        x += width + (spacing if japanese else 0)
        highest = max(highest, x)
        japanese_count += int(japanese)
    lines.append(line())
    incomplete = any(l['unknown_dynamic'] for l in lines) or bool(unsupported)
    return {'lines': lines, 'max_static_advance': max(l['max_cursor'] for l in lines),
            'max_copy_right_static': max(l['copy_right_bound'] for l in lines),
            'conditional_max_total': None if incomplete else max(l['max_cursor'] for l in lines),
            'unresolved_dynamic': any(l['unknown_dynamic'] for l in lines),
            'unsupported_controls': sorted(set(unsupported)), 'page_events': events,
            'final_japanese_page': japanese,
            'max_copy_bottom_static': max(l['copy_bottom'] for l in lines),
            'cursor_over_255_diagnostic': any(l['max_cursor'] > 255 for l in lines),
            'status': 'CONDITIONAL_COMPONENT_MODEL_NOT_LIVE_FIT',
            'name_bound_diagnostic_only': name_bound}


def code_evidence(source, base):
    from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB
    dis = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
    blocks = []
    for a, b in BLOCKS:
        assert source[a:b] == base[a:b], location(a)
        instructions = []
        for ins in dis.disasm(source[a:b], a + 0x08000000):
            instructions.append({'gba_address': f'0x{ins.address:08X}',
                'bytes': ins.bytes.hex(' '), 'mnemonic': ins.mnemonic, 'operands': ins.op_str})
        blocks.append({**location(a), 'rom_end_exclusive': f'0x{b:08X}',
            'bytes': source[a:b].hex(' '), 'sha256': sha(source[a:b]), 'instructions': instructions,
            'not_exhaustive_call_graph': True})
    return blocks


def profiles(source, base, tables):
    assert u32(source, 0xF79D4) == 0x0841F444
    assert u32(source, 0x15F9B4 + 0x8A * 4) == 0x09EC9DD1
    assert source[0x1E7D5DA:0x1E7D5E5] == bytes.fromhex('8a 67 00 00 00 00 66 6d 6c 03 03')
    assert source[0x3A73BC:0x3A73C4] == bytes.fromhex('00 02 0f 1a 04 0f 98 01')
    assert u32(source, 0x6FB38) == 0x083A73BC
    assert u32(source, 0x9C9F1C) == 0x020370DA
    assert u32(source, 0x9C9F20) == 0x03005074
    assert u32(source, 0x9C9F24) == 0x02036E38
    assert u32(source, 0x5638) == 0x08A0F1CD
    result = []
    for font, spec in FONT_DATA.items():
        table = tables[font]
        result.append({'id': f'field_std6_font{font}', 'confidence': 'CONDITIONAL',
            'component_geometry_confidence': 'PROVEN_ROM_BRANCH_ONLY',
            'font_id': font, 'selector_result_condition': '0' if font == 4 else '1' if font == 5 else 'other',
            'entry_live_state_observed': False, 'viewport_live_proven': False,
            'call_chain': ['0F00 pointer / 0906 callstd6', 'std6 ROM01E7D5DA',
                'message ROM00A093AC', 'field expand ROM000694C8 -> ROM00008FCC',
                'setup ROM000F6D5C -> ROM000F6CD0', 'AddTextPrinter ROM00002CF4',
                'font record RAM03003D90 / ROM0041F444', f'wrapper ROM{spec["wrapper"]:08X}',
                'RenderText ROM00005790'],
            'font_info_record': {**location(table['record']), 'bytes': source[table['record']:table['record'] + 12].hex(' ')},
            'japanese_glyph_asset': location(spec['japanese_glyph']),
            'japanese_width_table': {**location(spec['japanese_width']), 'size': 280,
                'sha256': sha(table['japanese']), 'bytes': table['japanese'].hex(' ')},
            'latin_width_table': {**location(spec['latin_width']), 'size': 256,
                'sha256': sha(table['latin']), 'equals_repository_normal_latin': True},
            'literal_owners': {k: {**location(spec[k]), 'word': f'0x{u32(source, spec[k]):08X}'}
                for k in ('glyph_literal', 'japanese_literal', 'latin_literal')},
            'japanese_width_differences_from_normal': table['differences'],
            'template': {'window': 0, 'x': 0, 'y': 1, 'letter_spacing': 1,
                'line_spacing': 1, 'initial_language_flag': 'latin', 'minimum_spacing': 0},
            'glyph_height': {'japanese': 12, 'latin': 14, 'font_record_max_height': 14},
            'advance': {'japanese': 'glyph width + 1 after EVERY ordinary glyph including last/space',
                'latin': 'glyph width only', 'space_japanese': 10, 'space_latin': 6,
                'FE_line_step': 15, 'FA_scroll_distance': 15},
            'window_candidate': {'template': location(0x3A73BC), 'left_tile': 2, 'top_tile': 15,
                'width_tiles': 26, 'height_tiles': 4, 'physical_width': 208, 'physical_height': 32,
                'buffer_copy_padding': 0, 'padding_scope': 'ROM00003014 copies against live record; no additional padding subtraction there',
                'actual_live_usable_width': None, 'live_window_record_ram': '0x020204B4 + 12 * window_id'},
            'page_behavior': {'FE': 'X=initialX, Y+=font-record-height+lineSpacing; no wait',
                'FA': 'wait hook -> X=initialX, Y unchanged, scroll then resume',
                'FB': 'wait hook -> fill entire window, restore initialX/initialY',
                'language_reset_by_FE_FA_FB': False, 'automatic_wrap': False,
                'right_edge': 'copy footprint is clipped by live width; NOT automatic wrap; cursor byte can wrap above255'},
            'application_conditions': ['Recorded operand executes callstd6/message',
                f'Live selector and wrapper select font{font}', 'Live RAM03003D90 points to ROM0041F444',
                'No later printer/font/min-spacing override', 'Live window0 geometry and margins recorded',
                'FD expansion values/page/control effects bounded independently'],
            'exclusions': ['Unknown computed/interior consumer', 'FC06 font change', 'FC14 minimum spacing',
                'Unmodelled position/icon/F9 controls', 'Arbitrary imported/default/edited player name',
                'Window0 replacement or font-info pointer replacement'],
            'runtime_fit_approval': False})
    naming = rom_naming_profiles(source, 0)['player_name']
    return {'phase': '7C-4', 'status': 'READ_ONLY_INVESTIGATION', 'profiles': result,
        'common_dispatch_chain_count': 1, 'conditional_profiles': 3, 'fully_live_proven_profiles': 0,
        'selector': {'hook': location(0x9C9EE0), 'override_halfword_ram': '0x020370DA',
            'non_FF_override': 'return low byte of halfword', 'FF_override': 'RAM03005074 object index; if zero return3; else record RAM02036E38+index*0x24, helpers089C9E54/089C9CB4, style byte+0E maps0/1/other',
            'script_event_does_not_prove_style': True, 'missing_live_values': ['020370DA', '03005074', 'object record', 'resolved style record']},
        'std6_native_8A': {'owner': location(0x15F9B4 + 0x8A * 4), 'handler': location(0x1EC9DD0),
            'task': location(0x69570), 'wait_predicate': location(0x69590),
            'finding': 'CreateTask0807741C with08069571/priority50, setup native08069591; task checks08069554 then0805C270 and destroys itself. No InitWindows in this bounded handler.',
            'window_creation_proof': 'InitWindows08003B24 is called atROM0006FB24 with template083A73BC, not by opcode8A; every root last-initializer/overrides still unknown'},
        'name_buffer': {'placeholder': 'FD01', 'entries': 10, 'producer': location(0x9120),
            'dispatch_owner': location(0x231E74), 'producer_pointer_ram': '0x0300500C',
            'expander': location(0x8FCC), 'expansion': 'recursive byte copy before printer setup; child FF omitted; controls copied, not sanitized',
            'keyboard_bound': naming, 'naming_state_pointer_ram': '0x0203998C',
            'naming_dest_storage': '*RAM0203998C + 0x1E30 stores incoming r1 at ROM0009D9A6',
            'commit_input': location(0x9F7EC), 'commit_copy_call': location(0x9F830),
            'commit_input_bytes': '*naming_state + 0x1800', 'copy_count': 'selected naming template length + 1; player local template yields8',
            'input_commit_caveat': 'Local generic writer destination is proved; live NEW GAME destination equals *RAM0300500C and every alternative writer/default producer are not proved',
            'local_keyboard_width_per_font': {str(f): 7 * max(tables[f]['latin'][c] for c in [int(x, 16) for x in naming['accepted_byte_codes']]) for f in FONT_DATA},
            'arbitrary_ordinary_latin7_diagnostic': {str(f): 7 * max(tables[f]['latin'][:0xF7]) for f in FONT_DATA},
            'universal_safe_width': None, 'defaults_enumerated': False, 'external_values_bounded': False,
            'page_wrapper': '[latin][player][japanese]',
            'page_safety': 'PROVEN_CONDITIONAL_LOCAL_ORDINARY_BYTES: local keyboard has no control bytes; outer FC15 restores page. Embedded controls may alter font, Y or parser even if page restored.',
            'automatic_fit_approval': False},
        'wait_hook': {'entry': location(0x5634), 'target': location(0xA0F1CC),
            'caveat': 'Auto/input/options predicates; do not assume every FA waits for one key press'},
        'code_evidence': code_evidence(source, base), 'runtime_execution': False,
        'reusable_method': ['Prove operand AND command boundary, callstd and handler owners',
            'Resolve live selector branches and font-info pointer; do not infer from category/font number',
            'Observe last window initializer and record width/height/initialX/Y/margins',
            'Trace every ordinary glyph copy edge and advance; account for trailing JP spacing',
            'Trace FE/FA/FB vertically; no implicit wrap safety assumption',
            'Bound every FD writer/value/control/page effect separately; unknown means hold',
            'Keep FA semantics, ownership, glossary/entity approval as independent gates',
            'Batch02-16 reuse verified profile only after matching the new entry consumer conditions']}


def investigate():
    guard_before = protection.protected_snapshot()
    inputs_before = snapshot()
    management = management_proof()
    source = (ROOT / 'rom/unbound.gba').read_bytes()
    base = (ROOT / BASE_ROM).read_bytes()
    assert hashlib.md5(source).hexdigest() == SOURCE_MD5 and sha(base) == BASE_SHA
    tables = font_tables(source)
    profile = profiles(source, base, tables)
    holds = read('out/phase7/ja_story_batch01_technical_holds.json')['entries']
    review = read('tests/fixtures/ja_phase7_story_batch01_claude_review.json')
    handoff = read('out/phase7/ja_story_translation_batch01_for_claude.json')['entries']
    assert len(holds) == len(review) == len(handoff) == 53
    assert len({r['id'] for r in holds}) == 53
    assert [r['id'] for r in holds] == [r['id'] for r in review] == [r['id'] for r in handoff]
    entries, qa = [], []
    for index, (old, reviewed, selected) in enumerate(zip(holds, review, handoff)):
        assert old['batch_index'] == reviewed['review_index'] == index
        assert old['reviewed_japanese'] == reviewed['reviewed_text_joined']
        offset, size = int(selected['rom_offset'], 16), selected['slot_size']
        raw = source[offset:offset + size]
        assert raw == base[offset:offset + size]
        decoded = decode_pcs(raw, max_length=size)
        assert decoded.terminated and decoded.byte_length == size
        assert decoded.text == strip_hma_quotes(reviewed['original'])
        routes = []
        for route in old['consumer_status']['owner_routes']:
            p = int(route['owner_rom'], 16)
            assert source[p-2:p] == b'\x0f\x00' and source[p+4:p+6] == b'\x09\x06'
            assert u32(source, p) == 0x08000000 + offset
            assert base[p-2:p+6] == source[p-2:p+6]
            routes.append({**route, 'owner_gba': f'0x{p+0x08000000:08X}',
                           'evidence_bytes': source[p-2:p+6].hex(' '), 'local_route_proven': True})
        assert routes
        for root in selected['event_root_records']:
            p = int(root['script_pointer_owner']['rom_offset'], 16)
            assert u32(source, p) == 0x08000000 + int(root['script_offset'], 16)
        payload = Charmap('ja').encode(old['page_controlled_candidate_only'])
        assert sha(payload) == old['control_status']['encoded_sha256']
        width = {str(f): measure(payload, tables, f) for f in FONT_DATA}
        name = {str(f): measure(payload, tables, f, name_bound=42) for f in FONT_DATA} if old['buffer_status']['tokens'] else None
        non_renderer = [h for h in old['all_holds'] if not h.startswith('HOLD_RENDERER:')
                        and not h.startswith('HOLD_WIDTH:conditional_normal_spacing1')]
        primary = 'C' if non_renderer else 'B'
        unresolved = ['Live font-selector/style/override value', 'Last window0 initializer and overrides',
            'Live viewport/margins and vertical footprint', 'Runtime root reachability/state']
        if name:
            unresolved += ['All player name writers/default values', 'Buffer values/control effects and complete rendered width']
        entry = {'batch_index': index, 'canonical_id': old['id'], 'category': old['category'],
            'text_location': location(offset), 'slot_size': size, 'encoded_bytes': len(payload),
            'encoded_sha256': sha(payload), 'script_callers': routes,
            'event_root_records': selected['event_root_records'], 'event_bindings': selected['event_bindings'],
            'consumer': 'loadword0/callstd6 -> message field printer window0',
            'confidence': 'CONDITIONAL', 'local_dispatch_confidence': 'PROVEN',
            'live_font_id': None, 'conditional_font_ids': [2, 4, 5],
            'profile_ids': [p['id'] for p in profile['profiles']],
            'viewport': {'actual_width': None, 'actual_height': None,
                'conditional_template_width': 208, 'conditional_template_height': 32},
            'spacing': {'branch_template_japanese': 1, 'branch_latin_extra': 0,
                        'live_override_excluded': False},
            'rendering_branch': '0 -> font4; 1 -> font5; other -> font2',
            'page_behavior_profile': 'FE step15 / FA scroll15 sameY / FB resetXY; language survives all',
            'widths_per_font_condition': width, 'proven_live_max_width': None,
            'conditional_local_keyboard42_widths': name,
            'conditional_208_exceeded_fonts': [f for f, w in width.items() if w['max_copy_right_static'] > 208],
            'conditional_32_height_exceeded_fonts': [f for f, w in width.items() if w['max_copy_bottom_static'] > 32],
            'original_normal0_diagnostic': old['width_status']['normal_spacing0']['max_static_with_spacing'],
            'fa_semantic_verdict': old['fa_semantic_verdict'],
            'meaning_verdict': old['semantic_state']['status'], 'completed_name_reveal': old['completed_name_reveal'],
            'original_primary_hold': old['primary_hold'], 'original_all_holds_unchanged': old['all_holds'],
            'classification_primary': primary, 'primary_classification_reason': non_renderer[0] if non_renderer else 'Live renderer/window observation required',
            'secondary_blockers': non_renderer[1:] + unresolved if non_renderer else unresolved,
            'relocation_needed_not_approved': old['pointer_status']['relocation_needed'],
            'relocation_note': 'No destination allocation/pointer write; old ownership risks remain',
            'unresolved_conditions': unresolved, 'runtime_observed': False,
            'runtime_fit_approved': False, 'translation_or_injection_approval': False}
        entries.append(entry)
        qa.append({'batch_index': index, 'canonical_id': old['id'], 'baseline_rom': BASE_ROM,
            'baseline_sha256': BASE_SHA, 'original_english_for_identification': old['original_english'],
            'original_script_operand_breakpoints': [r['command_rom'] for r in routes],
            'event_bindings': selected['event_bindings'], 'root_records': selected['event_root_records'],
            'arrival_steps': 'UNKNOWN: map/record binding only; obtain a legitimately progressed disposable save, do not edit flags or ROM',
            'root_reachability_proven': False, 'observe': ['selector override/object/style', 'printer font/X/Y/spacing/language',
                'window0 live record, font-info pointer', 'FE/FA/FB page frames and exact cursor/copy edges'],
            'name_observation_required': bool(name), 'FA_observation_required': old['fa_segmented'],
            'japanese_candidate_installed': False, 'test_performed': False, 'runtime_PASS': False,
            'result': 'NOT_RUN', 'secondary_blockers': entry['secondary_blockers']})
    remaining = read('out/phase7/ja_full_localization_inventory.json')['phase6_remaining_ids']
    assert len(remaining) == len(set(remaining)) == 774
    assert previous.sha(previous.serialize(sorted(remaining))) == read('out/phase7/ja_story_batch01_validation.json')['summary']['phase6_remaining_ids_sha256']
    applied = previous.verify_prior_applied(base)  # Read-only encode and payload/owner comparison.
    summary = {'entries': 53, 'duplicates': 0, 'missing': 0,
        'consumer_confidence': dict(Counter(e['confidence'] for e in entries)),
        'primary_classification': {k: sum(e['classification_primary'] == k for e in entries) for k in 'ABCD'},
        'proven_live_fit': 0, 'static_rescue_approved': 0, 'runtime_trace_for_renderer_needed': 53,
        'renderer_only_primary_runtime_candidates': sum(e['classification_primary'] == 'B' for e in entries),
        'max_advance_by_conditional_font': {str(f): max(e['widths_per_font_condition'][str(f)]['max_static_advance'] for e in entries) for f in FONT_DATA},
        'max_copy_right_by_conditional_font': {str(f): max(e['widths_per_font_condition'][str(f)]['max_copy_right_static'] for e in entries) for f in FONT_DATA},
        'candidate_208_cursor_exceedance_indices': [e['batch_index'] for e in entries
            if any(w['max_static_advance'] > 208 for w in e['widths_per_font_condition'].values())],
        'candidate_208_exceedance_indices': [e['batch_index'] for e in entries if e['conditional_208_exceeded_fonts']],
        'conditional_vertical_exceedance_indices': [e['batch_index'] for e in entries if e['conditional_32_height_exceeded_fonts']],
        'name_buffer_entries': 10, 'FA_entries': 21, 'FA_segments': 180, 'FA_controls': 39,
        'semantic_hold_indices_unchanged': [1, 31, 40], 'meaning_review_indices_unchanged': [19, 40, 49],
        'glossary_scope_entries_unchanged': 14, 'official_entity_holds_unchanged': [19, 32],
        'relocation_candidate_not_allocated': [21], 'applied_total_unchanged': 2403,
        'phase6_remaining_unchanged': 774, 'rom_generated': False, 'runtime_executed': False,
        'translation_changes': 0, 'glossary_changes': 0, 'renderer_changes': 0, 'validator_changes': 0}
    assert snapshot() == inputs_before and protection.protected_snapshot() == guard_before
    assert sha((ROOT / BASE_ROM).read_bytes()) == BASE_SHA
    inventory = {'phase': '7C-4', 'summary': summary, 'entries': entries,
        'immutable_input_sha256': inputs_before, 'protected909': {'files': guard_before['files'],
            'aggregate_sha256': guard_before['aggregate_sha256']}, 'management_proof': management,
        'baseline_rom_sha256': BASE_SHA, 'source_rom_sha256': sha(source), 'applied_payload_proof': applied}
    order = [2, 3, 4, 0, 1, 19, 21, 31, 40, 49]
    qa.sort(key=lambda e: (order.index(e['batch_index']) if e['batch_index'] in order else 100 + e['batch_index']))
    runtime = {'phase': '7C-4', 'test_performed': False, 'runtime_PASS': False,
        'status': 'STATIC_ONLY_NO_ATTACHED_EMULATOR_TRACE', 'rom_write_prohibited': True,
        'debugger_observation_only': True, 'baseline_rom': BASE_ROM, 'baseline_sha256': BASE_SHA,
        'read_only_breakpoints_gba': ['0x080F6D5C', '0x089C9EE0', '0x080F6D44', '0x08002CF4',
            '0x08005790', '0x08003014', '0x08005C98', '0x08005CD0', '0x08005C6C', '0x08008FCC',
            '0x08009120', '0x0809D954', '0x0809F830'],
        'printer_fields': {'currentChar': '+00 u32', 'window': '+04 u8', 'font': '+05 u8',
            'initialX': '+06', 'initialY': '+07', 'currentX': '+08', 'currentY': '+09',
            'letterSpacing': '+0A', 'lineSpacing': '+0B', 'state': '+1C',
            'scrollDistance': '+1F', 'minimumSpacing': '+20', 'japanese': '+21'},
        'live_ram': {'font_info_pointer': '0x03003D90', 'printer_window0': '0x02020034 (stride0x24)',
            'windows': '0x020204B4 (stride0x0C)', 'font_override': '0x020370DA u16',
            'object_index': '0x03005074 u8', 'player_record_pointer': '0x0300500C u32',
            'expanded_field_string': '0x02021D18', 'naming_state_pointer': '0x0203998C'},
        'capture_rules': ['Use original source/current baseline ROM only, copy saves externally, disable battery autosave or use disposable copies',
            'Do not modify ROM, RAM, save variables or install Japanese candidates',
            'Break at actual script operand, correlate root/currentChar/expanded text; screenshot alone cannot prove owner',
            'Record all setup calls/windows/style flags on that event, then inspect printer before every glyph',
            'Native240x160 frames: first/last glyph copy edges, waits, scroll and clear',
            '53 candidates remain English: their runtime trace proves geometry, not Japanese text PASS',
            'Observe already-applied Japanese dialogue for Japanese flag behavior only when its same live consumer is traced',
            'Use longest accepted local player name; trace destination and writer; imported/default values need separate evidence',
            'Repeat option/object/style branches without claiming an unseen branch passed'],
        'entries': qa}
    return {'profiles': profile, 'inventory': inventory, 'runtime_qa': runtime}


def markdown(data):
    summary = data['inventory']['summary']
    lines = ['# Phase 7C-4: Renderer / Consumer / Layout Investigation', '',
        '解析のみ。ROM生成・注入・翻訳変更・既存validator変更・commit/pushなし。mGBA未実施、runtime PASSなし。', '',
        '## 結果', '', '```json', json.dumps(summary, ensure_ascii=False, indent=2), '```', '',
        '53件の局所operandは同じcallstd6/message経路。共通dispatch1系統、条件付きfont profile3、live証明済みprofile0。',
        'PROVENな局所部品と、未証明の実際の呼出状態・viewportを分離。Aも注入承認ではない。', '',
        '## ROM根拠', '',
        '|処理|ROM offset / GBA address|確認|', '|---|---|---|',
        '|std6|01E7D5DA / 09E7D5DA|8A / message67 / wait66 / close6D / release6C|',
        '|8A table owner / handler|0015FBDC / 0815FBDC、01EC9DD0 / 09EC9DD0|task作成とnative待機。ここではInitWindowsしない|',
        '|field window initializer|0006FB24 / 0806FB24、literal0006FB38 / 0806FB38|InitWindows08003B24へtemplate083A73BC|',
        '|candidate window|003A73BC / 083A73BC|left2/top15、26x4 tiles、208x32px。live適用は未証明|',
        '|message / expansion|00A093AC / 08A093AC、000694C8 / 080694C8、00008FCC / 08008FCC|FD再帰展開後、RAM02021D18でprinter作成|',
        '|setup|000F6D5C / 080F6D5C、000F6CD0 / 080F6CD0|window0/x0/y1/letterSpacing1/lineSpacing1|',
        '|selector|009C9EE0 / 089C9EE0|override RAM020370DA、object index03005074、record02036E38とstyleで条件分岐|',
        '|font-info setter|000F79C8 / 080F79C8、00002C1C / 08002C1C|ROM0041F444をRAM03003D90へ。live pointer変更の排除は未証明|',
        '|glyph dispatch / copy|00005B6C / 08005B6C、00003014 / 08003014|scratch font nibbleからglyph routine。live window幅でcopyをclip|',
        '|cursor advance|00005C28 / 08005C28|Japaneseはglyph幅+letterSpacing。Latinはglyph幅のみ。末尾にも加算|',
        '|FE / FA / FB|00005880 / 08005880、00005C98 / 08005C98、00005C6C / 08005C6C|FE Y+15、FA同Yで15px scroll、FB XYを初期値へ|',
        '|language|00005B10 / 08005B10、00005B18 / 08005B18|FC15/16がprinter+21を切替。FE/FA/FBではresetしない|',
        '|wait hook|00005634 / 08005634、00A0F1CC / 08A0F1CC|Unbound固有auto/input条件。必ず1キー待つとは限らない|', '',
        '## font 2/4/5', '',
        '|font|wrapper / glyph routine (ROM)|Japanese glyph / width (ROM)|Latin width (ROM)|normalとのJapanese差|',
        '|---:|---|---|---|---|',
        '|2|000053E8 / 000065B8|00207500 / 0020F500|00207300|なし|',
        '|4|00005458 / 000067EC|00217818 / 0021F818|00217618|0x2F「ぁ」9→10px|',
        '|5|00005490 / 00006958|00227B30 / 0022FB30|00227930|0x86「ョ」9→8px|', '',
        '表中GBA addressはROM offset+08000000。exact literal owners・width280 bytes・code生bytes/命令はprofiles JSON。',
        'selector result0=font4、1=font5、その他=font2。font4/5をカテゴリや話者だけから選ばない。',
        '3種類とも日本語glyph高12、Latin高14。font record max-height14なのでFE/FAは14+lineSpacing1=15。',
        '日本語space00はtable byte0でなく特殊処理で10px、spacing込み11px。Latin space6px、追加spacingなし。',
        '最終Japanese glyph後の+1はcursor advanceに含む。copy footprintの右端と最終cursorは区別する。',
        '右端は自動FE/FAしない。copyのclipは欠損救済ではない。printer Xはu8なので256以上のadvanceはwrapの別リスク。', '',
        '## viewport / 共通profileの条件', '',
        'ROM00003014はlive window record+3のtile幅×8からcurrentXを引き、glyph copy幅を制限する。',
        '同helper内に追加padding減算なし。ただしwindowの直前初期化・上書き・portrait等の予約領域は未証明。',
        '26x4 templateを見つけても全53件へ208pxを適用しない。全entryの実usable-widthとlive最大幅はnull。',
        '8Aはwindow初期化ではなくtask/native待機だった。window0がいつどのtemplateで作成されたかはroot別traceが必要。',
        'spacing1・font2/4/5・font-info ROM0041F444・window0が確認された時だけ条件付き計測を利用可能。',
        'FC06/FC14/未モデル位置・icon/F9・未知buffer・別window/font pointer/rendererは除外。', '',
        '## 幅再計測', '',
        '既存normal/spacing0最大200pxと、今回の各font/spacing1 cursor・copy右端をinventoryに分離。',
        'FD01を0幅で合格にせず、unknown dynamicがあればconditional_max_total=null。静的部分の幅だけを表示。',
        '208x32での超過は条件付き診断であり、実consumerのoverflow確定ではない。全entryのFE/FA/FB Y/page traceを保存。',
        'cursor>208は21件、copy-footprint>208は17件。#1/#13/#36/#40はcursor209/copy208。末尾spacingだけの超過をglyph欠損と同一視しないが、UNKNOWN viewportを理由にhold維持。',
        '旧English envelope gateはそのまま。今回の再計測で閾値を緩和しない。', '',
        '## 名前buffer10件', '',
        'FD01 owner ROM00231E74/GBA08231E74、producer ROM00009120/GBA08009120は*RAM0300500Cを返す。',
        'ROM00008FCCで子FFを除く再帰copy。FDをrendererで展開しているわけではなく、embedded FC/FE/FAもcopyされる。',
        'naming ROM0009D954/GBA0809D954のincoming r1はstate+1E30へROM0009D9A6で保存。',
        'commit ROM0009F7EC/GBA0809F7EC、copy call ROM0009F830/GBA0809F830はstate+1800から保存destへtemplate長+1をcopy。',
        'local player template7文字なので8 bytes。keyboardはROM003E22D0/GBA083E22D0、参照ROM0009F664。',
        'このkeyboardの通常Latin値だけなら3fontsとも最大6×7=42px。入力→任意保存名の全経路証明ではない。',
        '任意ordinary Latin7文字の84pxも長さ・ordinary-only条件の仮定付き。普遍上限ではない。',
        '既定名候補・外部save・別writer・実NEW GAME destとFD producerの一致はUNKNOWN。10件全hold維持。',
        '外側[latin][player][japanese]は通常local名のpageを維持。embedded FC等はfont/位置/制御parserにも影響し、万能安全ではない。', '',
        '## FA / 別blocker', '',
        'FA21件/180segments/39controlsは不変。#1/#31/#40 semantic hold、#19/#40/#49 meaning reviewは維持。',
        '#31/#40「はめつのひかり」の完成形が1wait早い問題はrenderer証明で解消しない。',
        '#19/#32公式entity、glossary scope14件、raw/interior owner候補、#21 slot19/encoded23のrelocation承認も変更しない。',
        'A=renderer/layout証明済み、B=renderer traceが主、C=独立した別gateが主、D=consumerをたどれない。primary排他的、secondary別記。', '',
        '## mGBA: ROM変更なしの観測手順', '',
        '1. 基準ROM hashを確認。saveをrepo外へ退避し、使い捨てcopyで観測。battery autosaveは本番saveに向けない。',
        '2. QA JSONのroot/map/条件とoperandを使う。到達手順はUNKNOWNで、map名や変数値だけで進行イベントを断定しない。',
        '3. Frozen Heightsの#2/#3/#4 time-cardから候補。次に#0/#1、Rift Cave #19/#21、Shadow Base #31/#40/#49。進行済みsaveが必要なら用意。',
        '4. debuggerでsetup080F6D5C/selector089C9EE0を止め、override/object/style、font-info pointer、window0 recordを読む。',
        '5. 080F6D44でtemplate、08005790/08003014でprinter fields/currentCharを読む。native240x160のfirst/last glyphを記録。',
        '6. FE前後、FA待機/scroll後、FB clear前後にX/Y/language/stateと15px移動を比較。auto条件も別記。',
        '7. 名前付き10件では08009120/08008FCCの入力/展開結果、0809D954/0809F830のdest/長さを観測。RAM/saveを編集しない。',
        '8. 53件は未注入で英語のまま。ここで証明できるのはgeometry。既存2403件の日本語を測る場合も同じlive consumerとの照合が必要。',
        '9. 全条件・全分岐が記録できない場合はCONDITIONAL/UNKNOWN維持。未実施をruntime PASSにしない。', '',
        '## 再利用・検証', '',
        'Batch02〜16はprofileの適用条件、除外条件、pointer/script境界、live値とwindow、FD契約をentry別に照合。自動承認しない。',
        '今回の打切り点: live window/style状態と全name値域は静的局所解析だけでは確定不能。次は上記traceを採取し、同じ仮説を再走査しない。',
        '新規6完全一致パスのみallowlist追加。既存全function AST、909件/期待aggregate、未許可ファイル検出を維持。',
        '新規出力はexclusive作成。既存出力が1件でもあれば全writer開始前に拒否。--check-existingは再生成bytes照合だけ。',
        '`python scripts/investigate_ja_phase7_renderer.py --check-existing`',
        '`python -m pytest`、変更Pythonの`py_compile`、`git diff --check`。最終実行結果は作業完了報告。', '',
        '## 全53件', '',
        '|index|ID|confidence|A/B/C/D|font2/4/5 static advance px|secondaryの要点|',
        '|---:|---|---|---|---|---|']
    for e in data['inventory']['entries']:
        widths = '/'.join(str(e['widths_per_font_condition'][str(f)]['max_static_advance']) for f in FONT_DATA)
        hold = e['primary_classification_reason'].replace('|', '/')
        lines.append(f'|{e["batch_index"]}|{e["canonical_id"]}|{e["confidence"]}|{e["classification_primary"]}|{widths}|{hold}|')
    return '\n'.join(lines) + '\n'


def output_bytes(data):
    return {OUTPUTS[0]: markdown(data).encode('utf-8'), OUTPUTS[1]: serialized(data['profiles']),
            OUTPUTS[2]: serialized(data['inventory']), OUTPUTS[3]: serialized(data['runtime_qa'])}


def persist_new(data):
    contents = output_bytes(data)
    assert not any((ROOT / p).exists() for p in OUTPUTS), 'Existing deliverable: no writes permitted'
    for relative, raw in contents.items():
        path = ROOT / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream:
            stream.write(raw)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    flags = parser.add_mutually_exclusive_group()
    flags.add_argument('--write', action='store_true')
    flags.add_argument('--check-existing', action='store_true')
    args = parser.parse_args()
    data = investigate()
    if args.write:
        persist_new(data)
    elif args.check_existing:
        for relative, raw in output_bytes(data).items():
            assert (ROOT / relative).read_bytes() == raw, f'Non-deterministic or changed output: {relative}'
    protection.protected_snapshot()
    print(json.dumps(data['inventory']['summary'], ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
