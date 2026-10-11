#!/usr/bin/env python3
"""Read-only, evidence-limited Phase 7B event attribution and batch planning.

python scripts/build_ja_phase7_story_attribution.py --analyze  # no writes
python scripts/build_ja_phase7_story_attribution.py            # new JSON only

Existing complete outputs are compared, never overwritten; partial outputs fail.
Script edges are static possibilities, not an execution trace or injection gate.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict, deque
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lib.pcs_text import decode_pcs
from lib.translation_glossary import load_glossary
from lib.translation_tokens import strip_hma_quotes
from scripts.build_ja_phase6_cleanup_batch03 import PHASE7A_PATHS, PHASE7B_PATHS, protected_snapshot
from scripts.build_ja_phase6_speaker_attribution import SOURCE_MD5, gba_pointer, trainerbattle_owners
from scripts.build_ja_phase7_inventory import BASE_ROM, BASE_SHA, RUNTIME_OBSERVED

INVENTORY = 'out/phase7/ja_full_localization_inventory.json'
SPEAKERS = 'out/phase6/ja_phase6_speaker_attribution.json'
VOICES = 'tests/fixtures/ja_phase6_voice_profiles_claude.json'
DIFFICULTY = 'out/ja-phase5c-difficulty-audit.json'
OUTPUTS = tuple('out/phase7/ja_story_' + x + '.json' for x in (
    'scene_index', 'priority_queue', 'evidence_gaps', 'translation_batch_plan')) + (
    'tests/fixtures/ja_phase7_story_attribution_manifest.json',)
GBA_BASE = 0x08000000
MAP_GROUP_TABLE = 0xB70498
MAP_XOR = 0x00B749DE
MAP_GROUP_COUNT = 57
MAP_NAME_TABLE = 0x3F1CAC
MAP_SECTION_BIAS = 88
MAP_NAME_COUNT = 109
NEW_GAME_DIFFICULTY_PROMPTS = frozenset(('scr_1F0FE27', 'scr_1F0FF35'))
MAX_INSTRUCTIONS_PER_ROOT = 4096
MAX_CALL_DEPTH = 8
REFERENCE_LEVELS = ('DIRECT_REFERENCE', 'INDIRECT_REFERENCE', 'HEURISTIC_CANDIDATE', 'UNKNOWN_REFERENCE')
STORY_CATEGORIES = ('MAIN_STORY_VERIFIED', 'MAIN_STORY_CANDIDATE', 'MANDATORY_GAMEPLAY_UI',
                    'IMPORTANT_SIDE_EVENT', 'OPTIONAL_NPC', 'POSTGAME', 'NON_DIALOGUE', 'UNKNOWN')
READINESS = ('READY_FOR_CLAUDE', 'NEEDS_EVENT_CONTEXT', 'NEEDS_BUFFER_ANALYSIS',
             'NEEDS_OFFICIAL_TERM', 'NEEDS_TECHNICAL_REVIEW', 'ALREADY_APPLIED')

# Pinned primary references. Rebuild is offline; no downloads or source edits.
EXTERNAL_SOURCES = {
    'pret_event_macros': {
        'url': 'https://github.com/pret/pokefirered/blob/037335f4c725d7c9aecdac87066f2002b4bd7e14/asm/macros/event.inc',
        'sha256': '848e5e791adeddbe7ae7fe2717729af666a8d8aa163ab7781c74bfd49ce58671'},
    'pret_script_commands': {
        'url': 'https://github.com/pret/pokefirered/blob/037335f4c725d7c9aecdac87066f2002b4bd7e14/data/script_cmd_table.inc',
        'sha256': '6b59babf9b8a33bdc37a322a1a4b6e2261426126097330f305823e53415b1389'},
    'pret_map_scripts': {
        'url': 'https://github.com/pret/pokefirered/blob/037335f4c725d7c9aecdac87066f2002b4bd7e14/include/constants/map_scripts.h',
        'sha256': '02f8c3a4dd660d5b11f7d4af1f5a6d4530a994df33ba8304024e2a5ba004afc8'},
    'cfru_map_layout': {
        'url': 'https://github.com/Skeli789/Complete-Fire-Red-Upgrade/blob/b637a27898b14e25dd24d0f69a3e302f0069deb8/include/global.fieldmap.h',
        'sha256': 'e281137a65d166f7fc51f7983d58b7159d0b8c9526dc9a0ec3d619fa64f99235'},
    'cfru_map_names_hints': {
        'url': 'https://github.com/Skeli789/Complete-Fire-Red-Upgrade/blob/b637a27898b14e25dd24d0f69a3e302f0069deb8/include/constants/maps.h',
        'sha256': '45421f951db0b978c237cb4cdba17f7f9f255c105aa8d93d62ab8bb4c4643708'},
    'cfru_flags_hints_not_unbound_story_definitions': {
        'url': 'https://github.com/Skeli789/Complete-Fire-Red-Upgrade/blob/b637a27898b14e25dd24d0f69a3e302f0069deb8/include/constants/flags.h',
        'sha256': '16b21242d769683d69404595615758e8aff7763760196d753e882cc51e7b0e71'},
}

# Conservative subset: standard fixed-length commands, plus explicitly sized
# movement/warp/buffer macros. Unsupported/virtual-address commands stop parsing.
# Special/native effects and Unbound-specific command semantics remain opaque.
LENGTHS = {
    **{x: 1 for x in (0, 1, 2, 3, 12, 13, 39, 45, 46, 48, 50, 53, 67, 90,
                     93, 94, 95, 102, 104, 105, 106, 107, 108, 109, 114, 118,
                     139, 140, 141, 142, 160, 163, 165, 174, 178, 183, 197, 201, 202, 203)},
    **{x: 2 for x in (8, 9, 14, 55, 56, 119, 151, 154, 166, 195, 199)},
    **{x: 3 for x in (10, 11, 16, 20, 27, 28, 37, 41, 42, 43, 47, 49,
                     52, 54, 72, 75, 76, 77, 78, 81, 83, 85, 96, 97, 98,
                     100, 110, 122, 137, 148, 150, 152, 153, 156, 158, 159,
                     164, 167, 171, 179, 180, 181, 192, 193, 194, 205, 206, 208)},
    **{x: 4 for x in (51, 91, 101, 125, 127, 128, 129, 130, 131, 132,
                     138, 147, 149, 157, 210)},
    **{x: 5 for x in (4, 5, 22, 23, 24, 25, 26, 33, 34, 35, 36, 38, 40,
                     66, 68, 69, 70, 71, 73, 74, 82, 84, 86, 103, 111,
                     115, 116, 117, 120, 123, 124, 126, 134, 135, 136,
                     155, 161, 172, 173, 175, 176, 200, 211)},
    **{x: 6 for x in (6, 7, 15, 17, 18, 19, 29, 30, 31, 133, 112, 113,
                     144, 145, 146, 182, 204)},
    **{x: 7 for x in (79, 87, 99)},
    **{x: 8 for x in (57, 58, 59, 60, 61, 62, 63, 64, 65, 177)},
    **{x: 9 for x in (21, 32, 80, 162, 170)},
    121: 15,
}
# bufferleadmonspecies (0x7E) is 2 bytes, bufferspecies/etc include a u16.
LENGTHS[0x7E] = 2
LENGTHS[0x3C] = 3
LENGTHS[0x28] = 3
LENGTHS[0x7C] = 3
LENGTHS[0x8F] = 3
# Actual command-table hooks, not a list inferred from text. Stop before these
# changed handlers until their complete operand consumption is proved.
UNPROVED_PATCHED_OPCODES = frozenset((0x46, 0x78, 0x81, 0x8A, 0xB2, 0xB6, 0xD3))


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    return json.loads((ROOT / path).read_text(encoding='utf-8'))


def hx(offset):
    return f'0x{offset:08X}'


def location(offset):
    return {'rom_offset': hx(offset), 'gba_address': hx(GBA_BASE + offset)}


def u16(rom, offset):
    return int.from_bytes(rom[offset:offset + 2], 'little')


def nullable_pointer(rom, offset):
    return rom[offset:offset + 4] == bytes(4) or gba_pointer(rom, offset) is not None


def valid_header(rom, offset):
    """Validate decoded master-table members, not arbitrary pointer hits."""
    if offset is None or not 0 <= offset <= len(rom) - 28:
        return False
    layout = gba_pointer(rom, offset)
    if layout is None or layout + 24 > len(rom) or rom[offset + 23] > 15:
        return False
    if not (1 <= int.from_bytes(rom[layout:layout + 4], 'little') <= 1024
            and 1 <= int.from_bytes(rom[layout + 4:layout + 8], 'little') <= 1024):
        return False
    if any(gba_pointer(rom, layout + k) is None for k in (8, 12)):
        return False
    if not all(nullable_pointer(rom, offset + k) for k in (4, 8, 12)):
        return False
    events = gba_pointer(rom, offset + 4)
    if events is None:
        return True  # A real empty map may have a null event block.
    if events + 20 > len(rom):
        return False
    for i, stride in enumerate((24, 8, 16, 12)):
        count, target = rom[events + i], gba_pointer(rom, events + 4 + 4 * i)
        if count and (target is None or target + count * stride > len(rom)):
            return False
    return True


def map_engine_evidence(rom):
    """Exact current ROM operands prove XOR tables and region-name bias."""
    anchors = (
        (0x55238, '00 4a 10 47 d5 15 ed 09'),
        (0x1ED15D4, '03 4b 80 00 c2 58 03 4b 89 00 53 40 c8 58 70 47 98 04 b7 08 de 49 b7 00'),
        (0xC4D78, '70 b5 06 1c 09 04 12 04 14 0c 08 0c 05 4a 89 18 0d 0c 6c 2d'),
        (0xC4D9C, '00 00 a8 ff 2e f2 3e 08 04 48 a9 00 09 18 09 68'),
        (0xC4DB8, 'ac 1c 3f 08'),
    )
    result = []
    for offset, raw in anchors:
        expected = bytes.fromhex(raw)
        assert rom[offset:offset + len(expected)] == expected, ('Map engine changed', hx(offset))
        result.append({**location(offset), 'bytes': raw})
    assert rom[MAP_GROUP_TABLE + 4 * MAP_GROUP_COUNT:MAP_GROUP_TABLE + 4 * (MAP_GROUP_COUNT + 1)] == b'\xf7' * 4
    return {'anchors': result, 'group_table': location(MAP_GROUP_TABLE), 'xor_key': hx(MAP_XOR),
            'decoded_group_count': MAP_GROUP_COUNT, 'group_count_basis': '57 valid decoded bases followed by F7 sentinel; no runtime bounds-check assertion',
            'region_section_to_name_index': 'section_id - 88, valid indices 0..108',
            'name_lookup': location(MAP_NAME_TABLE), 'old_0x3526A8_not_used_as_live_master': True}


def command_engine_evidence(rom):
    assert rom[0x69B1C:0x69B24] == bytes.fromhex('b4 f9 15 08 08 fd 15 08')
    table = 0x15F9B4
    hooks, handlers = set(), []
    for op in sorted(set(LENGTHS) | {0x5C}):
        pointer = gba_pointer(rom, table + 4 * op)
        assert pointer is not None
        handler = pointer & ~1
        raw = rom[handler:handler + 12]
        trampoline = (raw[:2] in (b'\x00\x48', b'\x00\x49', b'\x00\x4a', b'\x00\x4b')
                      and raw[2:4] in (b'\x00\x47', b'\x08\x47', b'\x10\x47', b'\x18\x47'))
        patched = handler > 0x1000000 or trampoline
        if patched:
            hooks.add(op)
        handlers.append({'opcode': f'0x{op:02X}', 'table_owner': location(table + 4 * op),
                         'handler': location(handler), 'handler_prefix': raw.hex(' '),
                         'patched_handler_stopped': patched})
    assert hooks == UNPROVED_PATCHED_OPCODES, ('Changed command hook set', hooks)
    return {'context_setup_literals': location(0x69B1C), 'literal_bytes': 'b4 f9 15 08 08 fd 15 08',
            'command_table': location(table), 'command_table_end': location(0x15FD08),
            'handler_records': handlers, 'excluded_patched_opcodes': [f'0x{x:02X}' for x in sorted(hooks)],
            'signature_limit': 'Supported fixed arguments use pinned BPRE macros; hooks stop, delegated/native side effects and feasible paths remain unproved.'}


def collect_maps(rom):
    engine = map_engine_evidence(rom)
    bases = [(int.from_bytes(rom[MAP_GROUP_TABLE + 4 * i:MAP_GROUP_TABLE + 4 * i + 4], 'little')
              ^ MAP_XOR) - GBA_BASE for i in range(MAP_GROUP_COUNT)]
    assert all(0 <= b < len(rom) for b in bases)
    maps, roots, gaps, group_audit = [], [], [], []
    for group, base in enumerate(bases):
        boundary = min([b for b in bases if b > base] + [len(rom)])
        accepted, rejected, terminated = 0, [], False
        for index in range(min(256, (boundary - base) // 4)):
            owner = base + 4 * index
            header = gba_pointer(rom, owner)
            if header is None:
                terminated = True
                break
            if not valid_header(rom, header):
                rejected.append({'map_index': index, 'header': hx(header), 'owner': hx(owner)})
                continue  # Invalid slot is not proof that later slots are absent.
            accepted += 1
            mid = f'map_{group:03d}_{index:03d}'
            section = rom[header + 20]
            name_index = section - MAP_SECTION_BIAS
            name_ptr = gba_pointer(rom, MAP_NAME_TABLE + name_index * 4) if 0 <= name_index < MAP_NAME_COUNT else None
            name = decode_pcs(rom, name_ptr, 96).text if name_ptr is not None else None
            events = gba_pointer(rom, header + 4)
            mp = {'map_id': mid, 'map_group': group, 'map_index': index,
                  'header': location(header), 'group_record': location(MAP_GROUP_TABLE + 4 * group),
                  'group_record_encoded_bytes': rom[MAP_GROUP_TABLE + 4 * group:MAP_GROUP_TABLE + 4 * group + 4].hex(' '),
                  'header_pointer_owner': location(owner), 'header_bytes': rom[header:header + 28].hex(' '),
                  'region_section_id': section, 'name_table_index': name_index if name_ptr is not None else None,
                  'map_name': name, 'map_name_pointer_owner': location(MAP_NAME_TABLE + name_index * 4) if name_ptr is not None else None,
                  'events_offset': hx(events) if events is not None else None,
                  'layout_offset': hx(gba_pointer(rom, header)),
                  'event_counts': list(rom[events:events + 4]) if events is not None else [0] * 4,
                  'runtime_reachability': 'UNVERIFIED', 'map_role': 'UNKNOWN', 'root_ids': []}
            maps.append(mp)

            def add_root(kind, script, record, field, **extra):
                if script is None:
                    return
                rid = f'{mid}_{kind}_{record:08X}'
                root = {'root_id': rid, 'kind': kind, 'script_offset': hx(script),
                        'map_id': mid, 'map_group': group, 'map_index': index, 'map_name': name,
                        'map_header': location(header), 'root_record': location(record),
                        'script_pointer_owner': location(field),
                        'pointer_bytes': rom[field:field + 4].hex(' '), 'runtime_reachability': 'UNVERIFIED',
                        'mandatory_progression': 'NOT_ESTABLISHED', **extra}
                roots.append(root)
                mp['root_ids'].append(rid)

            if events is not None:
                for kind, count_index, stride, pointer_delta in (
                        ('object', 0, 24, 16), ('coord', 2, 16, 12), ('background', 3, 12, 8)):
                    start = gba_pointer(rom, events + 4 + count_index * 4)
                    for j in range(rom[events + count_index]):
                        rec = start + j * stride
                        if kind == 'background' and rom[rec + 5] > 4:
                            continue  # Hidden-item union is data, never a script pointer.
                        script = gba_pointer(rom, rec + pointer_delta)
                        extra = {'event_index': j, 'record_bytes': rom[rec:rec + stride].hex(' '),
                                 'coordinates': [int.from_bytes(rom[rec + k:rec + k + 2], 'little', signed=kind == 'object')
                                                 for k in ((4, 6) if kind == 'object' else (0, 2))]}
                        if kind == 'object':
                            extra.update(local_object_id=rom[rec], graphics_id=rom[rec + 1] | rom[rec + 3] << 8,
                                         visibility_flag_fields=[hx(u16(rom, rec + 20)), hx(u16(rom, rec + 22))],
                                         visibility_semantics='CFRU fields; polarity and Unbound conditions not inferred')
                        elif kind == 'coord':
                            extra['entry_condition'] = {'variable': hx(u16(rom, rec + 6)), 'value': u16(rom, rec + 8),
                                                        'condition_semantics': 'CoordEvent trigger/index fields; engine behavior not independently traced'}
                        else:
                            extra['background_kind'] = rom[rec + 5]
                        add_root(kind, script, rec, rec + pointer_delta, **extra)
            table = gba_pointer(rom, header + 8)
            if table is None:
                continue
            for j in range(32):
                rec = table + 5 * j
                if rec + 5 > len(rom):
                    gaps.append({'kind': 'map_script_bounds', 'map_id': mid, 'offset': hx(rec)})
                    break
                typ = rom[rec]
                if typ == 0:
                    break
                target = gba_pointer(rom, rec + 1)
                if typ not in range(1, 8) or target is None:
                    gaps.append({'kind': 'unsupported_map_script_record', 'map_id': mid, 'offset': hx(rec),
                                 'bytes': rom[rec:rec + 5].hex(' ')})
                    break
                if typ in (2, 4):
                    for k in range(64):
                        row = target + 8 * k
                        if row + 8 > len(rom):
                            gaps.append({'kind': 'level_condition_bounds', 'map_id': mid, 'offset': hx(row)})
                            break
                        var = u16(rom, row)
                        if var == 0:
                            break
                        script = gba_pointer(rom, row + 4)
                        if script is None:
                            gaps.append({'kind': 'invalid_level_script_pointer', 'map_id': mid, 'offset': hx(row)})
                            break
                        add_root('level_condition', script, row, row + 4, map_script_type=typ,
                                 parent_map_script_record=location(rec),
                                 entry_condition={'variable': hx(var), 'value': u16(rom, row + 2),
                                                  'condition_semantics': 'Map script variable/value table; required progression not established'})
                else:
                    add_root('level', target, rec, rec + 1, map_script_type=typ)
            else:
                gaps.append({'kind': 'map_script_record_limit', 'map_id': mid, 'offset': hx(table)})
        group_audit.append({'group': group, 'decoded_table_offset': hx(base), 'upper_storage_boundary': hx(boundary),
                            'accepted_maps': accepted, 'rejected_slots': rejected,
                            'terminated_by_non_rom_pointer': terminated,
                            'runtime_array_length': 'NOT_INDEPENDENTLY_PROVEN'})
    assert len({m['map_id'] for m in maps}) == len(maps)
    by_map = {m['map_id']: m for m in maps}
    assert by_map['map_003_066']['map_name'] == 'Frozen Heights'
    assert by_map['map_003_067']['map_name'] == 'Route 1'
    assert by_map['map_003_068']['map_name'] == 'Bellin Town'
    return maps, roots, {'engine': engine, 'group_storage_audit': group_audit, 'record_gaps': gaps}


def decode_command(rom, pc):
    if not 0 <= pc < len(rom):
        return None, 'OUT_OF_ROM'
    op, size = rom[pc], LENGTHS.get(rom[pc])
    if op == 0x5C:
        if pc + 2 > len(rom):
            return None, 'TRUNCATED_TRAINERBATTLE'
        # Do not guess Unbound modes 10..15. The canonical extractor also knows
        # modes 13..15, but their full control-flow signature is not proved here.
        size = {0: 14, 1: 18, 2: 18, 3: 10, 4: 18, 5: 14, 6: 22, 7: 18, 8: 22, 9: 14}.get(rom[pc + 1])
    if size is None:
        return None, 'UNSUPPORTED_OPCODE_OR_MODE'
    if pc + size > len(rom):
        return None, 'TRUNCATED_COMMAND'
    node = {**location(pc), 'opcode': f'0x{op:02X}', 'length': size,
            'bytes': rom[pc:pc + size].hex(' '), 'text_operands': [], 'edges': []}
    operands = []
    if op == 0x0F:
        role = ('LOADWORD_CALLSTD_TEXT' if rom[pc + 1] == 0 and rom[pc + 6:pc + 8] in (b'\x09\x02', b'\x09\x06')
                else 'LOADWORD_ONLY_CONSUMER_UNPROVEN')
        operands.append((pc + 2, role))
    elif op in (0x67, 0x9B):
        operands.append((pc + 1, 'MESSAGE' if op == 0x67 else 'MESSAGE_AUTOSCROLL'))
    elif op == 0x85:
        operands.append((pc + 2, 'BUFFERSTRING_WRITER'))
        node['buffer_index'] = rom[pc + 1]
    elif op == 0x5C:
        mode = rom[pc + 1]
        offsets = (6,) if mode == 3 else (6, 10, 14) if mode in (4, 6, 7, 8) else (6, 10)
        operands.extend((pc + delta, 'TRAINERBATTLE_TEXT') for delta in offsets)
        node['trainer_id'] = u16(rom, pc + 2)
        node['trainer_mode'] = mode
    elif op == 0xC8:
        operands.append((pc + 1, 'HELP_TEXT'))
    for owner, role in operands:
        target = gba_pointer(rom, owner)
        if target is not None:
            node['text_operands'].append({'owner': hx(owner), 'target': hx(target), 'role': role})
    if op in (0x29, 0x2A, 0x2B, 0x60, 0x61, 0x62):
        node['flag_operation'] = {'kind': 'trainer_flag' if op >= 0x60 else 'flag',
                                  'operation': {0x29: 'set', 0x2A: 'clear', 0x2B: 'check', 0x60: 'check', 0x61: 'set', 0x62: 'clear'}[op],
                                  'value': hx(u16(rom, pc + 1)), 'story_meaning': 'UNKNOWN'}
    if op in (0x16, 0x17, 0x18, 0x19, 0x1A, 0x21, 0x22):
        node['variable_operation'] = {'variable': hx(u16(rom, pc + 1)), 'operand': hx(u16(rom, pc + 3)),
                                      'operation': f'0x{op:02X}', 'story_meaning': 'UNKNOWN'}
    if op in (0x23, 0x24, 0x25, 0x26):
        node['opaque_engine_effect'] = True
    if op in (4, 5, 6, 7):
        owner = pc + (2 if op in (6, 7) else 1)
        target = gba_pointer(rom, owner)
        # Script pointers need not be aligned. Native Thumb pointers must not be
        # followed merely because their address is odd: only call/goto operands.
        if target is None:
            return None, 'INVALID_SCRIPT_TARGET'
        node['edges'].append({'kind': 'call' if op in (4, 7) else 'goto', 'target': hx(target),
                              'condition': rom[pc + 1] if op in (6, 7) else None})
        if op in (6, 7):
            node['edges'].append({'kind': 'conditional_fallthrough', 'target': hx(pc + size)})
    elif op == 0x5C and rom[pc + 1] in (1, 2, 6, 8):
        owner = pc + size - 4
        target = gba_pointer(rom, owner)
        if target is not None:
            node['edges'].append({'kind': 'battle_script_possible', 'target': hx(target)})
        node['edges'].append({'kind': 'fallthrough', 'target': hx(pc + size)})
    elif op not in (2, 3, 8, 12, 13, 0x24, 0x5E, 0x5F):
        node['edges'].append({'kind': 'fallthrough', 'target': hx(pc + size)})
    if op in (8, 9, 10, 11):
        node['standard_script_id'] = rom[pc + 1]
        node['standard_script_effects'] = 'OPAQUE_NOT_FOLLOWED'
    return node, None


def walk_script(rom, root, text_by_offset, nodes=None, text_spans=(), blocked_opcodes=frozenset()):
    """A bounded pushdown walk: actual return stack, never a nearby byte scan."""
    nodes = {} if nodes is None else nodes
    start = int(root['script_offset'], 16)
    queue = deque([(start, (), (), False)])
    visited, refs, gaps, visited_pcs = set(), {}, [], set()
    while queue and len(visited) < MAX_INSTRUCTIONS_PER_ROOT:
        pc, stack, path, opaque = queue.popleft()
        state = (pc, stack, opaque)
        if state in visited:
            continue
        visited.add(state)
        if 0 <= pc < len(rom) and rom[pc] in blocked_opcodes:
            gaps.append({'offset': hx(pc), 'byte': f'0x{rom[pc]:02X}', 'reason': 'PATCHED_HANDLER_OPERANDS_UNPROVEN'})
            continue
        inside_text = (text_spans.contains(pc) if hasattr(text_spans, 'contains')
                       else any(a <= pc < b for a, b in text_spans))
        if inside_text:
            gaps.append({'offset': hx(pc), 'reason': 'SCRIPT_TARGET_INSIDE_TEXT_SLOT'})
            continue
        key = hx(pc)
        if key in nodes:
            node, error = nodes[key], None
        else:
            node, error = decode_command(rom, pc)
        if error:
            gaps.append({'offset': hx(pc), 'byte': f'0x{rom[pc]:02X}' if 0 <= pc < len(rom) else None, 'reason': error})
            continue
        nodes[key] = node
        visited_pcs.add(pc)
        path = path + (pc,)
        opaque = opaque or node.get('opaque_engine_effect', False) or 'standard_script_id' in node
        for operand in node['text_operands']:
            for entry_id in text_by_offset.get(int(operand['target'], 16), ()):
                k = (entry_id, operand['owner'], operand['role'])
                if k in refs:
                    continue
                refs[k] = {'id': entry_id, **operand, 'command_offset': key,
                           'root_id': root['root_id'], 'call_depth': len(stack),
                           'reference_confidence': 'INDIRECT_REFERENCE' if stack else 'DIRECT_REFERENCE',
                           'static_path': [hx(p) for p in path], 'opaque_effect_on_path': opaque,
                           'runtime_reachability': 'UNVERIFIED', 'conditions_evaluated': False}
        if node['opcode'] == '0x03':
            if stack:
                queue.append((stack[-1], stack[:-1], path, opaque))
            continue
        for edge in node['edges']:
            target = int(edge['target'], 16)
            if edge['kind'] == 'call':
                if len(stack) >= MAX_CALL_DEPTH:
                    gaps.append({'offset': key, 'reason': 'CALL_DEPTH_LIMIT'})
                    continue
                queue.append((target, stack + (pc + node['length'],), path, opaque))
            else:
                queue.append((target, stack, path, opaque))
    if queue:
        gaps.append({'offset': hx(start), 'reason': 'ROOT_STATE_LIMIT'})
    return {'root_id': root['root_id'], 'instruction_offsets': [hx(p) for p in sorted(visited_pcs)],
            'references': sorted(refs.values(), key=lambda r: (r['id'], r['owner'], r['role'])),
            'parse_gaps': sorted({(r['offset'], r['reason']): r for r in gaps}.values(), key=lambda r: (r['offset'], r['reason'])),
            'static_only': True}


def classify_story(row, refs, root_index):
    if row['id'] in RUNTIME_OBSERVED:
        return 'MANDATORY_GAMEPLAY_UI', 'VERIFIED', 'Human-observed NEW GAME character/skin/hair selection; exact byte operand revalidated.'
    if row['id'] in NEW_GAME_DIFFICULTY_PROMPTS and any(
            r['role'] == 'MESSAGE' and root_index[r['root_id']]['kind'] == 'observed_ui_anchor' for r in refs):
        return 'MANDATORY_GAMEPLAY_UI', 'SUPPORTED', 'Difficulty prompt directly messaged by parsed NEW GAME selection flow; individual branch not human-playtested here.'
    # A level/coordinate display is an event candidate, NOT proof of mandatory
    # story. Generic loadword data and background signs are not enough.
    display_refs = [r for r in refs if r['role'] in ('MESSAGE', 'MESSAGE_AUTOSCROLL', 'LOADWORD_CALLSTD_TEXT')]
    event_roots = [root_index[r['root_id']] for r in display_refs if r['call_depth'] == 0]
    map_contexts = {root_index[r['root_id']].get('map_id') for r in refs}
    if len(map_contexts) == 1 and row['category'] in ('scripts', 'plain_scripts', 'pointer_texts', 'gendered_dialogue_fragments') and any(
            r['kind'] in ('level', 'level_condition', 'coord') for r in event_roots):
        return 'MAIN_STORY_CANDIDATE', 'PROVISIONAL', 'Direct level/coordinate display in one map context: investigation candidate, not proof of mandatory progress.'
    if row['content_family'] not in ('UNKNOWN', 'GENERAL_NPC_DIALOGUE', 'TRAINER_DIALOGUE') and row['category'] not in (
            'scripts', 'plain_scripts', 'pointer_texts', 'gendered_dialogue_fragments'):
        return 'NON_DIALOGUE', 'SUPPORTED', 'Structured extractor category; no assertion that its table is reachable on every path.'
    return 'UNKNOWN', 'UNKNOWN', 'No proved mandatory/optional/postgame event assignment; address/name matching forbidden.'


def priority_for(row, story, confidence, refs, speaker, difficulty_role):
    if story == 'MANDATORY_GAMEPLAY_UI':
        return {'level': 'P0', 'confidence': confidence, 'reason': 'Required NEW GAME selection UI; static versus human-observed evidence remains explicit.'}
    if story == 'MAIN_STORY_CANDIDATE':
        return {'level': 'P0', 'confidence': 'PROVISIONAL', 'reason': 'Investigate map-triggered event, not approved mandatory-story membership.'}
    if speaker.get('speaker_category') == 'UNBOUND_ORIGINAL' and speaker.get('speaker_confidence') == 'PROVEN':
        return {'level': 'P1', 'confidence': 'SUPPORTED', 'reason': 'Preserved Unbound-specific trainer identity; major-event importance remains provisional.'}
    if difficulty_role or row['category'] in ('battle_messages', 'menu_battle', 'menu_pause', 'start_menu_labels',
            'menu_pokemon', 'menu_save', 'menu_save_prompts', 'menu_options', 'mission_names', 'mission_log', 'mission_objectives'):
        return {'level': 'P1', 'confidence': 'SUPPORTED', 'reason': 'Structured gameplay/mission/UI owner, prioritized by usage policy; mandatory progression not asserted.'}
    if refs or row['content_family'] != 'UNKNOWN':
        return {'level': 'P2', 'confidence': 'SUPPORTED', 'reason': 'Proved static event association or owned reference-data category; not excluded.'}
    return {'level': 'P3', 'confidence': 'UNKNOWN', 'reason': 'Event/consumer context unresolved; remains a full-localization obligation.'}


def translation_readiness(row, refs, speaker, glossary_hits, difficulty_role):
    if row['status'] == 'APPLIED_JAPANESE':
        return 'ALREADY_APPLIED', 'Read-only applied text; no retranslation authorized.'
    if row['status'] == 'KEEP_ENGLISH_APPROVED':
        return 'NEEDS_TECHNICAL_REVIEW', 'Intentional English disposition retained; exclude from Claude action, not inventory.'
    families = set(row['holds']['all_families'])
    # Semantic labels [player]/[rival] are known names; width still needs an
    # injection audit. Generic buffers remain unresolved without exact evidence.
    unresolved_buffer = bool(re.search(r'\[(?:buffer[0-9]+|v[0-9a-fA-F]+)\]|\\\\[0-9A-Fa-f]{2}', row['original']))
    if ('unknown buffer' in families or unresolved_buffer) and not difficulty_role:
        return 'NEEDS_BUFFER_ANALYSIS', 'No speculative expansion of dynamic buffer; writer candidates are not reaching-definition proof.'
    if 'official name' in families:
        return 'NEEDS_OFFICIAL_TERM', 'Existing official-name hold preserved; no localization performed.'
    if row['source_raw_count'] or 'glyph/font' in families:
        return 'NEEDS_TECHNICAL_REVIEW', 'Lossless raw/glyph interpretation requires technical evidence before wording.'
    dialogue = row['category'] in ('scripts', 'plain_scripts', 'pointer_texts', 'gendered_dialogue_fragments')
    display_refs = [r for r in refs if r['role'] in ('MESSAGE', 'MESSAGE_AUTOSCROLL', 'LOADWORD_CALLSTD_TEXT', 'TRAINERBATTLE_TEXT', 'HELP_TEXT')]
    if dialogue and refs and not display_refs and not difficulty_role and speaker.get('speaker_confidence') != 'PROVEN':
        return 'NEEDS_EVENT_CONTEXT', 'Text load/buffer writer proves a data reference, not its display consumer or dialogue meaning.'
    if dialogue and not difficulty_role and not refs and speaker.get('speaker_confidence') != 'PROVEN':
        return 'NEEDS_EVENT_CONTEXT', 'Unknown event/consumer/speaker; do not translate context-free dialogue.'
    if row['holds']['context_hold'] and not difficulty_role:
        return 'NEEDS_EVENT_CONTEXT', 'Prior context hold not auto-resolved by a static map reference.'
    return 'READY_FOR_CLAUDE', 'Source and static/table context available for review, NOT injection approval; FA/width/owners still gated.'


def plan_batches(entries):
    eligible = [r for r in entries if r['priority']['level'] in ('P0', 'P1') and r['translation_readiness'] == 'READY_FOR_CLAUDE']
    units = defaultdict(list)
    for r in eligible:
        sid = r['speaker'].get('speaker_id') if r['speaker'].get('speaker_confidence') == 'PROVEN' else None
        # A verified static event root can group context but never voices. Only
        # unique-root association is used; overlapping event roots remain separate.
        unit = 'speaker:' + sid if sid else 'scene:' + r['scene_ids'][0] if len(r['scene_ids']) == 1 else 'entry:' + r['id']
        units[(r['priority']['level'], unit)].append(r)
    batches, current, chars, ceiling = [], [], 0, 160

    def flush():
        nonlocal current, chars, ceiling
        if current:
            batches.append({'batch_id': f'P7B_plan_{len(batches) + 1:03d}', 'entry_ids': [r['id'] for r in current],
                            'count': len(current), 'visible_source_characters': chars,
                            'fa_entries': sum(bool(r['source_controls'].get('FA')) for r in current),
                            'priority_counts': dict(sorted(Counter(r['priority']['level'] for r in current).items())),
                            'split_reason': '160-entry normal / 40-entry FA-heavy / 16000-character caps; final tail may be smaller',
                            'requires_human_context_review': True, 'claude_invoked': False})
        current, chars, ceiling = [], 0, 160

    splits = []
    for (_, key), rows in sorted(units.items()):
        rows.sort(key=lambda r: r['id'])  # Determinism only, NOT story sequence.
        cap = 40 if any(r['source_controls'].get('FA') for r in rows) else 160
        if len(rows) > cap:
            splits.append({'group': key, 'entries': len(rows), 'reason': 'Group exceeds safe review batch cap; retain shared context in all chunks.'})
        chunks = [rows[i:i + cap] for i in range(0, len(rows), cap)]
        for chunk in chunks:
            count_chars = sum(r['source_visible_characters'] for r in chunk)
            if current and (len(current) + len(chunk) > min(ceiling, cap)
                            or chars + count_chars > 16000 or current[0]['priority']['level'] != chunk[0]['priority']['level']):
                flush()
            if count_chars > 16000:
                splits.append({'group': key, 'entries': len(chunk), 'reason': 'Character budget exceeds cap; split explicitly, not by inferred scene order.'})
                for r in chunk:
                    if current and (chars + r['source_visible_characters'] > 16000 or len(current) >= cap):
                        flush()
                    current.append(r)
                    chars += r['source_visible_characters']
                    ceiling = min(ceiling, cap)
                flush()
            else:
                current.extend(chunk)
                chars += count_chars
                ceiling = min(ceiling, cap)
    flush()
    ids = [k for b in batches for k in b['entry_ids']]
    assert len(ids) == len(set(ids)) == len(eligible)
    return {'metadata': {'eligible_unique_entries': len(eligible), 'recommended_batches': len(batches),
                         'normal_target': '120..160 entries; tails/groups may be smaller', 'fa_heavy_cap': 40,
                         'maximum_visible_characters': 16000, 'no_translation_started': True,
                         'entry_order_is_not_story_order': True},
            'batches': batches, 'group_splits': splits,
            'deferred_P0_P1': [{'id': r['id'], 'reason': r['translation_readiness']}
                              for r in entries if r['priority']['level'] in ('P0', 'P1')
                              and r['translation_readiness'] not in ('READY_FOR_CLAUDE', 'ALREADY_APPLIED')]}


def build_attribution():
    before = protected_snapshot()
    preserved_7a = {p: sha((ROOT / p).read_bytes()) for p in sorted(PHASE7A_PATHS)}
    inv, speakers, voices, difficulty = (read(p) for p in (INVENTORY, SPEAKERS, VOICES, DIFFICULTY))
    rows = inv['entries']
    assert len(rows) == len({r['id'] for r in rows}) == 25044
    assert len(inv['raw_entries']) == 25045 and len(inv['supplemental_unresolved_ids']) == 1
    assert sum(r['status'] == 'APPLIED_JAPANESE' for r in rows) == 2403
    assert len(inv['phase6_remaining_ids']) == 774
    for path, digest in inv['metadata']['input_sha256'].items():
        assert sha((ROOT / path).read_bytes()) == digest, ('Phase 7A input changed', path)
    rom = (ROOT / 'rom/unbound.gba').read_bytes()
    assert hashlib.md5(rom).hexdigest() == SOURCE_MD5
    assert sha((ROOT / BASE_ROM).read_bytes()) == BASE_SHA
    maps, roots, map_audit = collect_maps(rom)
    command_audit = command_engine_evidence(rom)
    # Human-observed entry operands, not a guessed whole NEW GAME script range.
    for key, pc in (('scr_1F0F7EC', 0x1E6F9F1), ('scr_1F0F800', 0x1E6FA31), ('scr_1F0F814', 0x1E6FA73)):
        assert rom[pc] == 0x67
        expected = next(r for r in rows if r['id'] == key)
        assert gba_pointer(rom, pc + 1) == int(expected['rom_offset'], 16)
        roots.append({'root_id': 'observed_new_game_' + key, 'kind': 'observed_ui_anchor',
                      'script_offset': hx(pc), 'map_id': None, 'map_name': None,
                      'runtime_reachability': 'HUMAN_OBSERVED_PREVIOUS_PHASE',
                      'expected_entry_id': key, 'mandatory_progression': 'NEW_GAME_SELECTION',
                      'observation_source': 'Phase 3 user runtime PASS, retained in Phase 7A; no new emulator session'})
    offsets = defaultdict(list)
    spans = []
    for row in rows:
        target = int(row['rom_offset'], 16)
        offsets[target].append(row['id'])
        spans.append((target, target + row['slot_size']))
    # Use a sorted interval lookup instead of checking 25K spans per command.
    from bisect import bisect_right
    starts = sorted(a for a, _ in spans)
    ends = {a: b for a, b in spans}

    class TextSpans:
        def contains(self, pc):
            i = bisect_right(starts, pc) - 1
            return i >= 0 and pc < ends[starts[i]]

        def __iter__(self):
            return iter(spans)

    # walk_script accepts tuple intervals in unit tests and this fast membership
    # implementation in real ROM analyses.
    span_index = TextSpans()
    nodes, walks, refs_by_id = {}, [], defaultdict(list)
    for root in roots:
        walk = walk_script(rom, root, offsets, nodes, span_index, UNPROVED_PATCHED_OPCODES)
        walks.append(walk)
        for ref in walk['references']:
            refs_by_id[ref['id']].append(ref)
    root_index = {r['root_id']: r for r in roots}
    existing_speakers = {r['id']: r for r in speakers['entries'] + speakers['applied_candidates']}
    profile_index = {p['speaker_id']: p for p in voices['profiles']}
    difficulty_roles = {('tbl_menu_game_settings_00000_1F4E26F' if r['id'] == 'scr_1F4E26F' else r['id']): r['runtime_role']
                        for r in difficulty['entries']}
    for anchor in difficulty['runtime_anchors']:
        p = int(anchor['rom_offset'], 16)
        raw = bytes.fromhex(anchor['bytes'])
        assert rom[p:p + len(raw)] == raw, ('Difficulty anchor changed', anchor['name'])
    duplicate_membership = {}
    for i, group in enumerate(inv['duplicates']['exact_original']['groups']):
        for key in group:
            duplicate_membership[key] = {'group_id': f'exact_duplicate_{i:05d}', 'member_ids': group,
                                         'automatic_reuse_approved': False, 'physical_slots_merged': False}
    glossary = load_glossary(ROOT / 'glossaries/ja.json', expected_language='ja')
    entries = []
    for row in rows:
        key, target = row['id'], int(row['rom_offset'], 16)
        refs = refs_by_id.get(key, [])
        speaker = deepcopy(existing_speakers.get(key, {'id': key, 'speaker_id': None,
                           'speaker_category': 'UNKNOWN_SPEAKER', 'speaker_confidence': 'UNKNOWN', 'speaker_evidence': []}))
        owned = []
        heuristics = []
        for p in row['pointer_ownership']['recorded_sources']:
            owner = int(p, 16)
            assert gba_pointer(rom, owner) == target, ('Source owner mismatch', key, p)
            owned.append({'owner': location(owner), 'pointer_bytes': rom[owner:owner + 4].hex(' '),
                          'ownership_scope': 'canonical extractor; completeness not globally re-proved'})
            if not refs and row['category'] in ('scripts', 'plain_scripts', 'pointer_texts'):
                if rom[max(0, owner - 2):owner] == b'\x0f\x00' or (owner > 0 and rom[owner - 1] in (0x67, 0x9B)):
                    heuristics.append({'owner': hx(owner), 'kind': 'opcode_operand_shape_without_proved_root',
                                       'runtime_reachability': 'UNKNOWN'})
                trainers = trainerbattle_owners(rom, owner, target)
                if trainers:
                    heuristics.append({'owner': hx(owner), 'kind': 'trainer_operand_shape_without_proved_map_path', 'evidence': trainers})
        confidence = ('DIRECT_REFERENCE' if any(r['reference_confidence'] == 'DIRECT_REFERENCE' for r in refs) else
                      'INDIRECT_REFERENCE' if refs else
                      'DIRECT_REFERENCE' if key in difficulty_roles and owned else
                      'HEURISTIC_CANDIDATE' if heuristics or owned else 'UNKNOWN_REFERENCE')
        story, story_confidence, story_reason = classify_story(row, refs, root_index)
        priority = priority_for(row, story, story_confidence, refs, speaker, difficulty_roles.get(key))
        hits = [{'source': term.source, 'target': term.target_for(row['category']), 'context_scope': term.context_scope,
                 'span': [a, b], 'categories': list(term.categories), 'entry_ids': list(term.entry_ids)}
                for a, b, term in glossary.matches(strip_hma_quotes(row['original']), row['category'], entry_id=key)]
        readiness, readiness_reason = translation_readiness(row, refs, speaker, hits, difficulty_roles.get(key))
        scenes = sorted({r['root_id'] for r in refs})
        family = row['content_family']
        if family == 'UNKNOWN' and refs:
            family = 'EVENT_SCRIPT_REFERENCED_TEXT' if any(r['role'] not in ('BUFFERSTRING_WRITER', 'LOADWORD_ONLY_CONSUMER_UNPROVEN') for r in refs) else 'EVENT_SCRIPT_LOADED_DATA'
        bindings = [{'root_id': rid, 'map_id': root_index[rid].get('map_id'),
                     'map_name': root_index[rid].get('map_name'), 'trigger_kind': root_index[rid]['kind'],
                     'entry_condition': root_index[rid].get('entry_condition'),
                     'visibility_flag_fields': root_index[rid].get('visibility_flag_fields'),
                     'mandatory_progression': root_index[rid]['mandatory_progression']} for rid in scenes]
        qa = {'route_status': 'HUMAN_OBSERVED_PREVIOUS_PHASE' if key in RUNTIME_OBSERVED else 'STATIC_LOCATION_ONLY' if refs else 'UNKNOWN',
              'route': 'NEW GAME > character / skin / hair selection' if key in RUNTIME_OBSERVED else None,
              'expected_text_id': key, 'static_event_bindings': bindings,
              'required_save_flags_and_actual_route': 'UNKNOWN' if key not in RUNTIME_OBSERVED else 'Fresh NEW GAME',
              'new_runtime_test_performed': False}
        entries.append({
            'id': key, 'category': row['category'], 'original': row['original'],
            'current_japanese': row['candidate_japanese'] if row['status'] == 'APPLIED_JAPANESE' else None,
            'candidate_japanese': row['candidate_japanese'], 'translation_state': row['translation_state'],
            'status': row['status'], 'injection_state': row['injection_state'], 'holds': deepcopy(row['holds']),
            'phase6_remaining': row['phase6_remaining'], 'rom_offset': row['rom_offset'],
            'gba_address': row['gba_address'], 'slot_size': row['slot_size'],
            'pointer_ownership': deepcopy(row['pointer_ownership']), 'verified_source_owners': owned,
            'reference_confidence': confidence, 'event_references': refs, 'heuristic_reference_candidates': heuristics,
            'story_category': story, 'story_confidence': story_confidence, 'story_reason': story_reason,
            'content_family_before': row['content_family'], 'content_family': family,
            'scene_ids': scenes, 'event_bindings': bindings, 'speaker': speaker,
            'speaker_confidence_promoted': False, 'voice_profile': profile_index.get(speaker.get('speaker_id')),
            'legacy_speaker_map_labels': 'Preserved verbatim; old section-name lookup did not subtract 88. Use current event_bindings for map names, not proximity candidates.',
            'glossary_state': {'matches': hits, 'scope_policy_unchanged': True,
                               'wording_compliance_reapproval': 'NOT_PERFORMED'},
            'priority': priority, 'translation_readiness': readiness, 'translation_readiness_reason': readiness_reason,
            'injection_readiness': 'ALREADY_APPLIED_BYTE_VERIFIED' if row['status'] == 'APPLIED_JAPANESE' else 'NOT_APPROVED_REQUIRES_EXISTING_GATES',
            'source_controls': deepcopy(row['source_controls']), 'protected_tokens': row['protected_tokens'],
            'source_visible_characters': row['source_visible_characters'], 'qa': qa,
            'duplicate_reuse_candidate': duplicate_membership.get(key),
            'difficulty_runtime_role': difficulty_roles.get(key), 'unused_proven': False,
        })
    assert {r['id'] for r in entries} == {r['id'] for r in rows}
    assert all(r['original'] == a['original'] and r['candidate_japanese'] == a['candidate_japanese']
               and r['status'] == a['status'] and r['holds'] == a['holds'] for r, a in zip(entries, rows))
    assert len({r['id'] for r in entries if r['phase6_remaining']}) == 774
    for r in entries:
        if r['id'] in existing_speakers:
            assert r['speaker'] == existing_speakers[r['id']]
    summary = {
        'canonical_entries': 25044, 'raw_entries': 25045, 'unresolved_mapping': 1, 'applied': 2403, 'phase6_remaining': 774,
        'event_associated_entries': sum(bool(r['event_references']) for r in entries),
        'reference_counts': {k: sum(r['reference_confidence'] == k for r in entries) for k in REFERENCE_LEVELS},
        'story_counts': {k: sum(r['story_category'] == k for r in entries) for k in STORY_CATEGORIES},
        'priority_counts': {p: sum(r['priority']['level'] == p for r in entries) for p in ('P0', 'P1', 'P2', 'P3')},
        'priority_confidence': {p: dict(sorted(Counter(r['priority']['confidence'] for r in entries if r['priority']['level'] == p).items())) for p in ('P0', 'P1', 'P2', 'P3')},
        'readiness_counts': {k: sum(r['translation_readiness'] == k for r in entries) for k in READINESS},
        'P0_P1_state_counts': {p: {'exclusive_status': dict(sorted(Counter(r['status'] for r in entries if r['priority']['level'] == p).items())),
                                    'readiness': dict(sorted(Counter(r['translation_readiness'] for r in entries if r['priority']['level'] == p).items())),
                                    'phase6_remaining': sum(r['phase6_remaining'] and r['priority']['level'] == p for r in entries)} for p in ('P0', 'P1')},
        'content_unknown_before': sum(r['content_family_before'] == 'UNKNOWN' for r in entries),
        'content_unknown_after': sum(r['content_family'] == 'UNKNOWN' for r in entries),
        'unknown_reduction_is_event_reference_not_main_story_proof': True,
        'preserved_proven_speaker_entries': sum(r['speaker']['speaker_confidence'] == 'PROVEN' for r in entries),
        'preserved_plausible_speaker_entries': sum(r['speaker']['speaker_confidence'] == 'PLAUSIBLE' for r in entries),
        'major_npc_supported_entries': sum(r['speaker'].get('speaker_category') == 'UNBOUND_ORIGINAL' and r['speaker']['speaker_confidence'] == 'PROVEN' for r in entries),
        'unsupported_speaker_promotions': 0, 'unsupported_main_story_verified': 0,
        'maps': len(maps), 'event_roots': len(roots), 'instruction_nodes': len(nodes),
        'exact_duplicate_groups': inv['duplicates']['exact_original']['duplicate_groups'],
        'exact_duplicate_redundant_members': inv['duplicates']['exact_original']['redundant_members'],
    }
    assert summary['content_unknown_before'] == 15209
    assert sum(summary['reference_counts'].values()) == sum(summary['story_counts'].values()) == 25044
    batches = plan_batches(entries)
    summary['ready_P0_P1'] = batches['metadata']['eligible_unique_entries']
    summary['recommended_batches'] = batches['metadata']['recommended_batches']
    input_hashes = {p: sha((ROOT / p).read_bytes()) for p in sorted(set(PHASE7A_PATHS) | {SPEAKERS, VOICES, DIFFICULTY, 'glossaries/ja.json', 'rom/unbound.gba', BASE_ROM})}
    assert before == protected_snapshot()
    assert preserved_7a == {p: sha((ROOT / p).read_bytes()) for p in sorted(PHASE7A_PATHS)}
    metadata = {'phase': '7B', 'source_rom_md5': SOURCE_MD5, 'baseline_rom': BASE_ROM,
                'baseline_sha256': BASE_SHA, 'protected_files': before, 'input_sha256': input_hashes,
                'summary': summary, 'translation_changes': 0, 'rom_changes': 0,
                'glossary_changes': 0, 'no_new_runtime_play': True,
                'limitations': ['Partial standard-opcode parser, not all Unbound bytecode semantics.',
                                'Static branch paths do not establish feasible conditions or mandatory progress.',
                                'Native/special/standard-script effects opaque; no flag names guessed.',
                                'Map group/index is engine-proven; allocation boundaries are conservative, not runtime count checks.']}
    walk_summaries = [{**{k: v for k, v in w.items() if k != 'references'},
                       'entry_operand_refs': [{k: r[k] for k in ('id', 'owner', 'command_offset', 'role', 'call_depth')}
                                              for r in w['references']]} for w in walks]
    index = {'metadata': metadata, 'entries': entries, 'maps': maps, 'roots': roots,
             'script_walks': walk_summaries, 'script_nodes': dict(sorted(nodes.items())), 'map_audit': map_audit,
             'command_audit': command_audit,
             'raw_mapping': deepcopy(inv['mapping']), 'raw_entries': deepcopy(inv['raw_entries']),
             'supplemental_unresolved_ids': inv['supplemental_unresolved_ids'],
             'phase6_remaining_ids': inv['phase6_remaining_ids'],
             'story_progression_sequence': [], 'progression_sequence_status': 'UNKNOWN_NOT_ROM_ADDRESS_ORDER',
             'voice_profiles_preserved': voices}
    priority_queue = {'metadata': metadata, 'queues': {p: [
        {'id': r['id'], **r['priority'], 'story_category': r['story_category'], 'status': r['status'],
         'translation_readiness': r['translation_readiness'], 'injection_readiness': r['injection_readiness'],
         'scene_ids': r['scene_ids']} for r in entries if r['priority']['level'] == p] for p in ('P0', 'P1', 'P2', 'P3')},
        'supplemental': [{'id': inv['supplemental_unresolved_ids'][0], 'status': 'UNRESOLVED_MAPPING',
                         'priority': 'P3', 'independent_display': 'UNPROVEN_NOT_DISPROVED'}],
        'P2_P3_are_not_excluded': True}
    gaps = {'metadata': metadata, 'parser_gaps': [{'root_id': w['root_id'], **g} for w in walks for g in w['parse_gaps']],
            'map_record_gaps': map_audit['record_gaps'],
            'by_readiness': {k: [r['id'] for r in entries if r['translation_readiness'] == k] for k in READINESS},
            'investigation_tasks': [
                {'task': 'Validate Unbound custom opcodes/extended trainerbattle modes against command handlers, then expand fail-closed walk.', 'affected': 'parser_gaps'},
                {'task': 'Trace flag/variable writers and mandatory sequence, not just check/set occurrences.', 'affected': 'MAIN_STORY_CANDIDATE; all UNKNOWN story memberships'},
                {'task': 'Identify native/common/menu consumers and buffer reaching definitions; preserve call-stack boundaries.', 'affected': 'opaque paths, HEURISTIC/UNKNOWN references'},
                {'task': 'Verify map group allocation limits, rejected slots, warps/connections and actual in-game routes.', 'affected': 'group_storage_audit and static-location QA candidates'},
                {'task': 'Keep RNING suffix as a separate unresolved coverage obligation; computed/interior consumer still unproved.', 'affected': inv['supplemental_unresolved_ids']},
                {'task': 'Collect speaker/scene identity evidence and runtime screenshots; never promote by nearby address or names.', 'affected': 'UNKNOWN/PLAUSIBLE speakers'},
            ], 'extractor_coverage_gaps_unchanged': deepcopy(inv['extractor_coverage_gaps'])}
    batches['metadata']['summary'] = summary
    manifest = {'metadata': metadata, 'external_primary_sources': EXTERNAL_SOURCES,
                'exact_new_paths': sorted(PHASE7B_PATHS), 'preserved_phase7a_sha256': preserved_7a,
                'map_engine_evidence': map_audit['engine'],
                'validation': {'duplicate_ids': 0, 'missing_ids': 0, 'original_changes': 0, 'applied_changes': 0,
                               'phase6_holds_removed': 0, 'speaker_promotions': 0, 'main_story_verified_without_proof': 0,
                               'protected_909_hash_unchanged': True, 'baseline_rom_hash_unchanged': True,
                               'phase7a_7_files_unchanged': True, 'glossary_unchanged': True,
                               'rebuild_contract': 'Recompute offline; compare all five complete JSON artifacts; never overwrite.'},
                'human_observed_ids_retained': sorted(RUNTIME_OBSERVED),
                'raw_suffix_obligation': deepcopy(inv['mapping']['interior_candidate'])}
    return dict(zip(OUTPUTS, (index, priority_queue, gaps, batches, manifest)))


def serialize(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8')


def persist_new(data, root=ROOT):
    if set(data) != set(OUTPUTS) or not set(data) <= PHASE7B_PATHS:
        raise AssertionError('Only the five exact Phase 7B JSON paths are writable')
    payloads = {p: serialize(v) for p, v in data.items()}
    present = {p for p in data if (root / p).exists()}
    if present:
        if present != set(data):
            raise FileExistsError('Partial Phase 7B outputs; no write authorized')
        for p, b in payloads.items():
            if (root / p).read_bytes() != b:
                raise FileExistsError('Conflicting Phase 7B output: ' + p)
        return 'VERIFIED_EXISTING_IDENTICAL'
    for p, b in payloads.items():
        path = root / p
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as handle:
            handle.write(b)
    return 'CREATED_NEW'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--analyze', action='store_true', help='Read-only calculation; no output files written')
    args = parser.parse_args()
    data = build_attribution()
    action = 'ANALYZED_READ_ONLY' if args.analyze else persist_new(data)
    print(json.dumps({'action': action, **data[OUTPUTS[0]]['metadata']['summary']}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
