"""Restricted mGBA 0.10.5 GDB reader. No memory/register writes or injection.

Use only with a disposable ROM/save environment. Capture files are exclusive.
Register and memory replies, including packet checksums, are retained as evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import socket
import struct
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lib.pcs_text import decode_pcs


def permitted_packet(payload):
    """No arbitrary RSP command: hardware breakpoints and CPU control only."""
    if payload in ('?', 'g', 'c', 's', 'qSupported:hwbreak+', 'QStartNoAckMode'):
        return True
    if re.fullmatch(r'[Zz]1,(?:08|09)[0-9a-f]{6},2', payload):
        return True
    match = re.fullmatch(r'm([0-9a-f]+),([0-9a-f]+)', payload)
    if not match:
        return False
    address, size = (int(v, 16) for v in match.groups())
    return 0 < size <= 512 and any(a <= address and address + size <= b for a, b in (
        (0x02000000, 0x02040000), (0x03000000, 0x03008000),
        (0x06000000, 0x06018000), (0x08000000, 0x0A000000)))


class Reader:
    def __init__(self, port=2345, timeout=3):
        self.connection = socket.create_connection(('127.0.0.1', port), timeout)
        self.connection.settimeout(timeout)
        self.buffer = b''
        self.transcript = []

    def send(self, payload):
        if not permitted_packet(payload):
            raise ValueError('Forbidden GDB packet: ' + payload)
        raw = payload.encode('ascii')
        packet = b'$' + raw + b'#' + f'{sum(raw) & 255:02x}'.encode()
        self.connection.sendall(packet)
        self.transcript.append({'direction': 'sent', 'payload': payload})

    def receive(self):
        while True:
            start = self.buffer.find(b'$')
            if start >= 0:
                end = self.buffer.find(b'#', start)
                if end >= 0 and len(self.buffer) >= end + 3:
                    raw = self.buffer[start + 1:end]
                    check = self.buffer[end + 1:end + 3]
                    self.buffer = self.buffer[end + 3:]
                    if sum(raw) & 255 != int(check, 16):
                        raise ValueError('Bad GDB reply checksum')
                    self.connection.sendall(b'+')
                    reply = raw.decode('ascii')
                    self.transcript.append({'direction': 'received', 'payload': reply,
                                            'checksum': check.decode()})
                    return reply
            chunk = self.connection.recv(4096)
            if not chunk:
                raise ConnectionError('GDB disconnected')
            self.buffer += chunk

    def query(self, payload):
        self.send(payload)
        return self.receive()

    def interrupt(self):
        self.connection.sendall(b'\x03')
        self.transcript.append({'direction': 'sent', 'payload': 'INTERRUPT_03'})
        return self.receive()

    def memory(self, address, size):
        raw = self.query(f'm{address:x},{size:x}')
        if not re.fullmatch('[0-9a-fA-F]{' + str(size * 2) + '}', raw):
            raise ValueError('Invalid memory reply: ' + raw)
        return bytes.fromhex(raw)

    def registers(self):
        raw = bytes.fromhex(self.query('g'))
        if len(raw) != 68:
            raise ValueError('Unexpected mGBA register layout')
        return dict(zip([f'r{i}' for i in range(13)] + ['sp', 'lr', 'pc', 'cpsr'],
                        struct.unpack('<17I', raw)))


def address_ok(address):
    return any(a <= address < b for a, b in (
        (0x02000000, 0x02040000), (0x03000000, 0x03008000), (0x08000000, 0x0A000000)))


def snapshot(reader, label):
    regs = reader.registers()
    regions = {}
    def region(name, address, size):
        if not address_ok(address) or not permitted_packet(f'm{address:x},{size:x}'):
            return None
        raw = reader.memory(address, size)
        regions[name] = {'address': f'0x{address:08X}', 'bytes': raw.hex(' ')}
        return raw
    region('stopped_code', regs['pc'], 16)
    region('stack', regs['sp'], 128)
    region('font_info_pointer', 0x03003D90, 4)
    region('font_override', 0x020370DA, 2)
    region('object_index', 0x03005074, 1)
    region('windows', 0x020204B4, 96)
    region('printer_window0', 0x02020034, 36)
    region('glyph_info', 0x03003DA0, 144)
    region('expanded_string', 0x02021D18, 512)
    region('player_pointer', 0x0300500C, 4)
    name = struct.unpack('<I', bytes.fromhex(regions['player_pointer']['bytes']))[0]
    if name:
        region('player_name', name, 16)
    region('script_context', 0x020370B8, 64)
    for register in ('r0', 'r1', 'r2', 'r3', 'r4', 'r5'):
        if address_ok(regs[register]):
            region(register + '_memory', regs[register], 128)
    if regs['pc'] in (0x08003014, 0x08005C4E, 0x08005C50, 0x08005880,
                       0x0800589E, 0x080058A0, 0x08005C98, 0x08005CD0, 0x08005C6C):
        # r0 is the CopyGlyph argument; RenderText keeps the printer in r6.
        region('live_printer', regs['r0'] if regs['pc'] == 0x08003014 else regs['r6'], 36)
    return {'label': label, 'registers': {k: f'0x{v:08X}' for k, v in regs.items()},
            'memory': regions, 'method': 'mGBA0.10.5 localhost GDB registers/memory; hardware breakpoints; no writes'}


def capture(args):
    path = Path(args.output).resolve()
    assert not path.exists(), 'Existing capture refused'
    assert not path.is_relative_to(ROOT), 'Raw capture must be outside repository'
    reader = Reader(timeout=3)
    records, errors = [], []
    breakpoints = [int(value, 16) for value in args.breakpoints.split(',') if value]
    try:
        reader.interrupt()
        records.append(snapshot(reader, args.label + ':attached'))
        for address in breakpoints:
            assert reader.query(f'Z1,{address:08x},2') == 'OK'
        deadline = time.monotonic() + args.seconds
        for count in range(args.events):
            reader.send('c')
            while True:
                try:
                    stop = reader.receive()
                    break
                except TimeoutError:
                    if time.monotonic() >= deadline:
                        stop = reader.interrupt()
                        break
            records.append(snapshot(reader, f'{args.label}:stop{count}:{stop}'))
            pc = int(records[-1]['registers']['pc'], 16)
            print(f'stop {count} PC={pc:08X}', flush=True)
            if time.monotonic() >= deadline or pc not in breakpoints:
                break
            for address in breakpoints:
                assert reader.query(f'z1,{address:08x},2') == 'OK'
            assert reader.query('s').startswith('S')
            for address in breakpoints:
                assert reader.query(f'Z1,{address:08x},2') == 'OK'
    except Exception as error:
        errors.append(type(error).__name__ + ': ' + str(error))
        raise
    finally:
        try:
            for address in breakpoints:
                reader.query(f'z1,{address:08x},2')
        except Exception as error:
            errors.append('cleanup:' + type(error).__name__ + ':' + str(error))
        reader.connection.close()  # mGBA resumes after detaching; no kill/reset/save command.
        content = {'observations': records, 'packet_transcript': reader.transcript,
                   'capture_errors': errors, 'new_translation_injected': False}
        with path.open('x', encoding='utf-8') as output:
            json.dump(content, output, ensure_ascii=False, indent=2)
            output.write('\n')
        print(str(path), flush=True)


def interactive(args):
    """One persistent debugger connection; typed commands cannot write RAM."""
    path = Path(args.output).resolve()
    assert not path.exists() and not path.is_relative_to(ROOT)
    reader = Reader(timeout=3)
    records, active, errors = [], set(), []
    try:
        reader.interrupt()
        records.append(snapshot(reader, args.label + ':attach'))
        print('READY: b ADDRESS / u / c / s / r / q', flush=True)
        while True:
            command = input('trace> ').strip().split()
            if not command:
                continue
            if command[0] == 'b' and len(command) == 2:
                address = int(command[1], 16)
                assert reader.query(f'Z1,{address:08x},2') == 'OK'
                active.add(address)
            elif command == ['u']:
                for address in sorted(active):
                    assert reader.query(f'z1,{address:08x},2') == 'OK'
                active.clear()
            elif command == ['c']:
                reader.send('c')
                while True:
                    try:
                        result = reader.receive()
                        break
                    except TimeoutError:
                        pass
                records.append(snapshot(reader, args.label + ':continue:' + result))
                print('STOP ' + records[-1]['registers']['pc'], flush=True)
            elif command == ['s']:
                result = reader.query('s')
                records.append(snapshot(reader, args.label + ':step:' + result))
                print('STEP ' + records[-1]['registers']['pc'], flush=True)
            elif command == ['r']:
                records.append(snapshot(reader, args.label + ':read'))
                print(json.dumps(records[-1], ensure_ascii=False), flush=True)
            elif command == ['q']:
                break
            else:
                print('REJECTED', flush=True)
    except Exception as error:
        errors.append(type(error).__name__ + ':' + str(error))
        raise
    finally:
        try:
            for address in sorted(active):
                reader.query(f'z1,{address:08x},2')
        except Exception as error:
            errors.append('cleanup:' + str(error))
        reader.connection.close()
        with path.open('x', encoding='utf-8') as output:
            json.dump({'observations': records, 'packet_transcript': reader.transcript,
                       'capture_errors': errors, 'new_translation_injected': False},
                      output, ensure_ascii=False, indent=2)
            output.write('\n')
        print(str(path), flush=True)


BASELINE = 'out/unbound-ja-phase6-cleanup-batch04.gba'
BASELINE_SHA = '0d1d00e7b0f4f113514abbcf1907e6d8949fd12b9193bf2cb0ad764ace5559d8'
OUTPUTS = (
    'docs/ja-phase7-renderer-runtime-trace.md',
    'out/phase7/ja_renderer_runtime_trace_log.json',
    'out/phase7/ja_renderer_runtime_proof_matrix.json',
    'tests/fixtures/ja_phase7_renderer_runtime_repro_steps.json',
)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def memory_at(record, address, size):
    """Use captured ranges only; never manufacture missing RAM observations."""
    for region in record['memory'].values():
        start = int(region['address'], 16)
        raw = bytes.fromhex(region['bytes'])
        if start <= address and address + size <= start + len(raw):
            return raw[address - start:address - start + size]
    return None


def exact_entry(pointer, entries):
    hits = [e for e in entries if 0x08000000 + int(e['address'], 16) == pointer]
    return hits[0] if len(hits) == 1 else None


def printer_fields(raw):
    if raw is None or len(raw) < 34:
        return None
    return {'text_pointer': f'0x{struct.unpack_from("<I", raw)[0]:08X}',
            'window_id': raw[4], 'template_font': raw[5],
            'initial_x': raw[6], 'initial_y': raw[7],
            'current_x': raw[8], 'current_y': raw[9],
            'letter_spacing': raw[10], 'line_spacing': raw[11],
            'dispatch_font': raw[20] & 15, 'japanese': bool(raw[33])}


def analyze_captures(paths):
    baseline = (ROOT / BASELINE).read_bytes()
    assert sha(baseline) == BASELINE_SHA
    entries = read_json(ROOT / 'out/unbound-texts.json')['entries']
    attempts, events = [], []
    for path in paths:
        content = read_json(path)
        attempts.append({'path': str(Path(path).resolve()), 'sha256': sha(Path(path).read_bytes()),
                         **content})
        for index, record in enumerate(content['observations']):
            pc = int(record['registers']['pc'], 16)
            event = {'capture': Path(path).name, 'record_index': index, 'pc': f'0x{pc:08X}',
                     'confidence': 'OBSERVED', 'entry_id': 'UNKNOWN_ENTRY'}
            if pc == 0x08008FCC:
                pointer = int(record['registers']['r1'], 16)
                entry = exact_entry(pointer, entries)
                observed = memory_at(record, pointer, 128)
                offset = pointer - 0x08000000
                if entry and observed == baseline[offset:offset + 128]:
                    event.update(entry_id=entry['id'], text_pointer=f'0x{pointer:08X}',
                                 original=entry['original'], caller_lr=record['registers']['lr'],
                                 owner_status='STATIC_PROVEN_NOT_OBSERVED_EXECUTION',
                                 static_pointer_owners=entry['pointer_sources'],
                                 observed_source=decode_pcs(observed).text)
                    for owner in entry['pointer_sources']:
                        owner_offset = int(owner, 16)
                        assert struct.unpack_from('<I', baseline, owner_offset)[0] == pointer
            elif pc == 0x080F6D7C:
                selector = int(record['registers']['r0'], 16)
                event.update(selector=selector, static_selected_font={0: 4, 1: 5}.get(selector, 2),
                             selected_font_confidence='STATIC_PROVEN_BRANCH_NOT_OBSERVED_PRINTER')
            elif pc == 0x08003014:
                pointer = int(record['registers']['r0'], 16)
                printer = printer_fields(memory_at(record, pointer, 36))
                assert printer is not None
                window = memory_at(record, 0x020204B4 + printer['window_id'] * 12, 12)
                glyph = memory_at(record, 0x03003DA0, 130)
                event.update(printer_address=f'0x{pointer:08X}', printer=printer,
                             window={'left_px': window[1] * 8, 'top_px': window[2] * 8,
                                     'width_px': window[3] * 8, 'height_px': window[4] * 8},
                             glyph_width=glyph[128], glyph_height=glyph[129],
                             copy_right_exclusive=printer['current_x'] + glyph[128],
                             reserved_padding='UNKNOWN', clipping_exercised=False)
            elif pc == 0x08005C4E:
                event.update(cursor_value_before_store=int(record['registers']['r0'], 16),
                             addend=int(record['registers']['r1'], 16),
                             store_instruction='STATIC_PROVEN: strb r0,[r6,#8]')
            elif pc == 0x08005880:
                event.update(control='FE', printer_address=record['registers']['r6'],
                             input_control=int(record['registers']['r3'], 16))
            elif pc == 0x0800589E:
                event.update(control='FE_AFTER_Y_STORE', new_y=int(record['registers']['r0'], 16),
                             line_step=int(record['registers']['r1'], 16),
                             printer_address=record['registers']['r6'])
            else:
                continue
            events.append(event)
    return attempts, events


def crash_evidence(path):
    raw = read_json(path)
    state = bytes.fromhex(raw['state_bytes'])
    assert raw['state_address'] == '0x02039600'
    target = struct.unpack_from('<I', state, 16)[0]
    assert target == int(raw['registers']['r3'], 16) == 0xE3E800D9
    assert int(raw['registers']['pc'], 16) == target & ~1
    rom = (ROOT / BASELINE).read_bytes()
    source = (ROOT / 'rom/unbound.gba').read_bytes()
    assert rom[0x1ED1420:0x1ED146E] == source[0x1ED1420:0x1ED146E]
    assert rom[0x1F119D4:0x1F119D4 + len(state)] == state
    return {**raw, 'confidence': 'OBSERVED', 'cause': 'UNRESOLVED',
            'callback_load': 'ROM01ED1440/GBA09ED1440: ldr r3,[r4,#0x10]',
            'indirect_jump': 'ROM01ED1466/GBA09ED1466: bx r3',
            'callback_code_unchanged_from_source': True,
            'RAM_PCS_decode': decode_pcs(state).text,
            'matching_ROM_offset': '0x01F119D4', 'matching_GBA_address': '0x09F119D4',
            'containing_entry': 'scr_1F1194E',
            'identity_status': 'BYTE_PROVENANCE_ONLY_NOT_RENDERER_ENTRY_PROOF',
            'writer': 'UNKNOWN', 'packet_transcript': raw['packet_transcript']}


def build_results(paths, crash_path=None):
    from scripts import build_ja_phase6_cleanup_batch03 as protection
    protection.protected_snapshot()
    prior = read_json(ROOT / 'out/phase7/ja_story_batch01_renderer_inventory.json')
    attempts, events = analyze_captures(paths)
    # This bounded investigation did not reach any of the 53 story entries.
    observed_ids = {e['entry_id'] for e in events} - {'UNKNOWN_ENTRY'}
    assert not observed_ids & {e['canonical_id'] for e in prior['entries']}
    matrix = {'phase': '7C-5', 'baseline_rom_sha256': BASELINE_SHA,
              'summary': {'story_entries': 53, 'story_observed': 0, 'story_not_reached': 53,
                          'proven_live_fit': 0, 'injection_approvals': 0,
                          'control_sample_source_ids': sorted(observed_ids),
                          'applied_unchanged': 2403, 'phase6_holds_unchanged': 774},
              'entries': [{'batch_index': e['batch_index'], 'canonical_id': e['canonical_id'],
                           'runtime_status': 'NOT_REACHED', 'consumer_confidence': 'CONDITIONAL',
                           'observed_conditions': [], 'runtime_fit_approved': False,
                           'unproven': ['actual font', 'actual window/padding', 'FA/name branch'],
                           'semantic_hold_maintained': e['batch_index'] in (1, 31, 40)}
                          for e in prior['entries']]}
    log = {'phase': '7C-5', 'baseline_rom_sha256': BASELINE_SHA,
           'environment': {'mGBA': '0.10.5 Qt Windows', 'gdb': 'localhost:2345 RSP',
                           'gui_operation': 'sky; boot human-assisted',
                           'SDL_listener': 'NOT_AVAILABLE_IN_OBSERVED_LAUNCH'},
           'observations': events, 'raw_capture_attempts': attempts,
           'limitations': ['capture03 disconnected: preserve errors',
                          'capture04 manually interrupted while waiting; breakpoints removed in finally',
                          'historical printer_window0/script_context dumps are diagnostic guesses, not identity proof',
                          'field script-context data2 was stale; cannot identify text by that value',
                          'source pointer identity does not prove static owner executed',
                          'intro source -> stack/printer linkage is temporally consistent, not an explicit return trace'],
           'new_translation_injected': False, 'runtime_fit_pass': False,
           'FA': 'NOT_REACHED', 'FB': 'NOT_REACHED', 'player_expansion': 'NOT_REACHED',
           'font4_5': 'NOT_REACHED'}
    if crash_path:
        log['crash_evidence'] = crash_evidence(crash_path)
        log['runtime_execution_result'] = 'CRASH_OBSERVED'
    repro = {'baseline': BASELINE, 'sha256': BASELINE_SHA,
             'isolation': 'Copy baseline to new temporary folder; savegamePath/savestatePath there; autoload=0; no old saves.',
             'launch': 'mGBA.exe -g -C autoload=0 -C cheatAutoload=0 -C cheatAutosave=0 -C savegamePath=TEMP -C savestatePath=TEMP TEMP/baseline.gba',
             'security': 'Prefer GDB GUI bind127.0.0.1. Never expose network listener; no M/X/P/G packets.',
             'capture': 'python scripts/investigate_ja_phase7_runtime_trace.py --interactive --output TEMP/new-capture.json --label field',
             'commands': ['b 08008FCC', 'b 080F6D7C', 'b 080F6D44', 'c',
                          'u (remove breakpoint before step)', 's', 'b 08003014', 'c', 'r', 'q'],
             'GUI': 'Enter=START, X=A. If short automated input fails, hold manually. Stop at breakpoint is intentional.',
             'continuation': ['Record expander r1 exact source; reject interior/proximity matches.',
                              'F6D44: r0 template pointer; capture font/window/x/y/spacing.',
                              'CopyGlyph: r0 live printer; render/control handlers: r6 live printer.',
                              'FE 08005880/0800589E; FA 08005C98/08005CD0/08005D40; FB 08005C6C.',
                              'Player expansion 08009018/08009120: capture FD01 and writer, full child bytes and language controls.',
                              'Use fresh capture filenames; q clears breakpoints; Ctrl+C also preserves log in finally.',
                              'If reconnect times out, restart GDB server in Qt; do not overwrite saved captures.'],
             'remaining': {'FA_semantic_hold': [1, 31, 40],
                           'player_indices': [20, 22, 26, 28, 29, 30, 35, 36, 38, 40]},
             'approval': 'No translation injection approval; no global name-width bound from one input.'}
    return log, matrix, repro


def persist_results(paths, crash_path=None):
    targets = [ROOT / p for p in OUTPUTS]
    assert not any(p.exists() for p in targets), 'Existing deliverable refused'
    log, matrix, repro = build_results(paths, crash_path)
    document = """# Phase 7C-5: mGBA Runtime Renderer Trace

実ROM実行・人間のSTART補助あり。解析のみ。ROM/訳文/セーブ/validator変更、注入承認、commit/pushなし。

## 結果と範囲

mGBA Qt 0.10.5 + localhost GDBでレジスタ・メモリを読み、hardware breakpointを使用。
SDL起動ではlistenerなし。GDB単体実行ファイル不要。独自RSP readerは書込みpacketを拒否。
制約は[mGBA 0.10.5実装](https://github.com/mgba-emu/mgba/blob/0.10.5/src/debugger/gdb-stub.c)に照合。
一時フォルダへbyte同一ROMをコピーし、既存saveのautoloadなし。基準ROM SHA-256は不変。
最初の停止は08008FCCの意図したbreak。後でbreak全解除・detachして再開。停止をgame freezeと誤認しない。

## 直接観測

NEW GAME注意画面: scr_1F0F5A6、ROM 01F0F5A6 / GBA 09F0F5A6。
08008FCCのr1=09F0F5A6、捕捉128byteと基準ROM一致。static owner 01E6F945の4byte=a6 f5 f0 09。
caller LR=09EB2FCD。owner命令が実行された証明とは別。原文Welcome to Pokémon Unbound!。
既適用日本語の注意文を画面で確認。途中からのpointer/類似文/アドレス近接でID一致判定しない。

CopyGlyph ROM00003014 / GBA08003014: r0=02020010のlive printer。
font template2/dispatch2、window0、initial/current X38/Y4、letterSpacing1/lineSpacing0、Japanese=true。
window RAM020204B4: left0/top2、28x18tiles =224x144px、画面origin0/16。
このsampleの開始Xから右境界まで186px。追加padding/予約領域とoverflowの実測はUNKNOWN。
glyph scratch03003DA0+80/+81=10/12px、copy右端exclusive48（最終pixel47）。
08005C4Eはstore直前、r0=49、r1=11。10px glyph+1px spacingを実測。
FE入口08005880でr3=FE、0800589EでY書込後r0=18、step r1=14。
field想定の15pxではない（font max-height14+lineSpacing0）。全行・末尾・clip/wrapの実測ではない。
source->stack expansion->printerは時系列整合。return時buffer全文を捕捉していないため完全な連結証明は未完。

別のfield setup観測: 080F6D5C r0=1はflagでありtext pointerではない。
selector ROM009C9EE0/GBA089C9EE0の実行、戻り080F6D7C r0=3、override020370DA=00FF。
RAMfont info03003D90=0841F444、window0は26x4tiles=208x32px（left16/top120）。
selector3→font2はstatic branch。printer作成時font/spacingは未捕捉。
context r5=03000EB0のdata2=09F0F79Cは以前の文の残存値。現在Choose a characterとの一致証明に使用しない。
このfield sampleはUNKNOWN_ENTRY。共通field経路を部分観測したが、完全なID/font/window連結は未証明。

## 保留を維持

Batch01全53件NOT_REACHED、consumer CONDITIONAL53、live-fit PROVEN0、注入承認0。
B15/C38、既適用2403、Phase6保留774は変更しない。font4/5、FA/FB、FD01展開はNOT_REACHED。
名前入力1例の42pxを全writer/外部saveの上限にしない。#1/#31/#40のFA意味境界はClaude再レビューへ。
対照sample224pxをfield53件へ転用しない。208候補超過も今回救済しない。

## 再現・次工程

repro fixtureの手順とhelperを使用。NEW GAMEのfield文についてexpander r1、selector戻り、F6D44 template、
CopyGlyph r0を同一接続で捕捉する。RenderText側はr6を使い、固定printer番地を仮定しない。
次に到達可能なFA1件とFD01 name1件を追跡。未注入Batch01日本語のruntime PASSは別工程。
全raw records/packet checksum/失敗試行はtrace JSONに保持。capture03切断、capture04待機中の手動中断も隠さない。
既存global mGBA設定はQt終了時更新され得るが、既存ROM/訳文/909保護対象とは別。既存saveを読み込まない。
新規4成果物をexclusive作成。再生成は別出力へ比較し、無断上書きしない。

## 検証

pytest・py_compile・git diff --checkの実行結果は最終報告参照。
helper testで書込packet拒否、exact pointer照合、観測欠落時UNKNOWN、全53件の未承認維持、
exact allowlist除去/許可外追加FAIL、保護909の期待hash不変を確認する。
"""
    if crash_path:
        document += """
## 後続クラッシュ（実行全体はPASSではない）

ユーザー報告後、GUIのエラー `Jumped to invalid address: E3E800D8` を直接確認。
GDB読取だけでPC=E3E800D8、r3=E3E800D9、LR=09ED1447、r4=02039600を取得。
ROM01ED1440/GBA09ED1440のldr r3,[r4,#10]、01ED1442のBL、01ED1466のbx r3と整合。
RAM02039610のcallback欄=d9 00 e8 e3。不正な関数pointerにPCS本文が入っている。
RAM02039600の24bytesはROM01F119D4/GBA09F119D4と完全一致、scr_1F1194Eの途中。
PCS decodeは改行+`than if you were to rem`。本文途中一致は表示entry/owner実行の証明ではない。
このためBatch01のNOT_REACHED判定を昇格しない。callback codeは元英語ROMから不変。
誰がRAMを書いたか、デバッガなしで再現するかはUNKNOWN。翻訳、renderer、デバッガのいずれにも原因を断定しない。
次回は同一hashの隔離ROMをGDBなしでNEW GAME再現し、再現時にcallback欄へのwriterを追跡する。
クラッシュdialogは閉じず保全。今回のtraceで観測できた部品は有効だが、ゲーム進行runtime PASSは撤回/不成立。
"""
    contents = [document] + [json.dumps(d, ensure_ascii=False, indent=2) + '\n' for d in (log, matrix, repro)]
    for target, content in zip(targets, contents):
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('x', encoding='utf-8', newline='\n') as output:
            output.write(content)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output')
    parser.add_argument('--label')
    parser.add_argument('--build-from', nargs='+')
    parser.add_argument('--crash-evidence')
    parser.add_argument('--verify-existing', action='store_true')
    parser.add_argument('--breakpoints', default='080F6D5C')
    parser.add_argument('--seconds', type=int, default=45)
    parser.add_argument('--events', type=int, default=8)
    parser.add_argument('--interactive', action='store_true')
    args = parser.parse_args()
    if args.build_from:
        if args.verify_existing:
            expected = build_results(args.build_from, args.crash_evidence)
            assert all(read_json(ROOT / path) == value
                       for path, value in zip(OUTPUTS[1:], expected)), 'Evidence regeneration differs'
            print('Existing JSON evidence reproduces; no files written')
            return
        persist_results(args.build_from, args.crash_evidence)
        return
    parser.error('--output and --label required') if not args.output or not args.label else None
    assert 1 <= args.seconds <= 60 and 1 <= args.events <= 100
    (interactive if args.interactive else capture)(args)


if __name__ == '__main__':
    main()
