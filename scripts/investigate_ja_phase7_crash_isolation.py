"""Phase 7C-6 read-only investigation; no emulator input, patch or injection.

Default prints findings. --write-new creates only absent phase deliverables.
--verify-existing reproduces JSON without overwriting any artifact.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lib.pcs_text import Charmap, decode_pcs
from scripts import build_ja_phase6_cleanup_batch03 as protection

PLAN = 'tests/fixtures/ja_phase7_crash_repro_plan.json'
OUTPUTS = (
    'docs/ja-phase7-runtime-crash-isolation.md',
    'out/phase7/ja_runtime_crash_isolation_matrix.json',
    'out/phase7/ja_callback_writer_trace.json',
)
SOURCE = 'rom/unbound.gba'
BASELINE = 'out/unbound-ja-phase6-cleanup-batch04.gba'
BASELINE_SHA = '0d1d00e7b0f4f113514abbcf1907e6d8949fd12b9193bf2cb0ad764ace5559d8'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read(path):
    return json.loads((ROOT / path).read_text(encoding='utf-8'))


def location(offset):
    return {'rom_offset': f'0x{offset:08X}', 'gba_address': f'0x{offset + 0x08000000:08X}'}


def u32(raw, offset):
    return struct.unpack_from('<I', raw, offset)[0]


def callback_target(value):
    """Location/alignment check, NOT a proof that a location contains code."""
    target = value & ~1
    thumb = bool(value & 1)
    region = next((name for start, end, name in (
        (0x02000000, 0x02040000, 'EWRAM'), (0x03000000, 0x03008000, 'IWRAM'),
        (0x08000000, 0x0E000000, 'CARTRIDGE_ROM_INCLUDING_MIRRORS'))
                   if start <= target < end), None)
    return {'value': f'0x{value:08X}', 'target': f'0x{target:08X}',
            'mode': 'Thumb' if thumb else 'ARM', 'region': region or 'INVALID_CALLBACK_REGION',
            'alignment_valid': thumb or target % 4 == 0,
            'location_plausible': region is not None and (thumb or target % 4 == 0),
            'executable_code_proven': False}


def no_debugger_argv(argv):
    # Exact commandline flags, not the appearance of a title/GUI dialog.
    return not any(x in ('-g', '--gdb', '-d', '--debug') for x in argv)


def compare_text(source, baseline, entry, old_state):
    offset, size = int(entry['address'], 16), entry['byte_length']
    source_text = source[offset:offset + size]
    baseline_text = baseline[offset:offset + size]
    decoded = decode_pcs(source_text)
    assert decoded.terminated and decoded.byte_length == size == 437
    assert Charmap().encode(decoded.text) == source_text
    owner = int(entry['pointer_sources'][0], 16)
    assert u32(source, owner) == u32(baseline, owner) == offset + 0x08000000
    match = 0x01F119D4
    assert source[match:match + len(old_state)] == baseline[match:match + len(old_state)] == old_state
    assert offset <= match < match + len(old_state) <= offset + size
    return {'entry_id': entry['id'], 'location': location(offset), 'slot_bytes': size,
            'source_encoded_bytes': decoded.byte_length, 'source_text': decoded.text,
            'source_sha256': sha(source_text), 'baseline_sha256': sha(baseline_text),
            'slot_unchanged': source_text == baseline_text,
            'pointer_owner': location(owner), 'pointer_bytes': source[owner:owner + 4].hex(' '),
            'owner_unchanged': source[owner:owner + 4] == baseline[owner:owner + 4],
            'owner_neighborhood': source[owner - 2:owner + 6].hex(' '),
            'source_controls': {f'{b:02X}': source_text.count(bytes([b])) for b in (0xFE, 0xFA, 0xFB, 0xFC, 0xFD)},
            'terminator': 'FF', 'codec_roundtrip': True,
            'match': {**location(match), 'entry_byte_offset': match - offset,
                      'byte_count': len(old_state), 'bytes': old_state.hex(' '),
                      'decode': decode_pcs(old_state).text},
            'copy_writer': 'UNKNOWN', 'buffer_overflow_proven': False,
            'runtime_destination_inference': 'No destination inferred from interior match',
            'source_to_ram_identity': 'BYTE_PROVENANCE_NOT_EXECUTION_OR_CAUSAL_PROOF'}


def static_callback(source, baseline):
    # Exact offsets were inspected in the ROM and correlated with the FireRed
    # ScanlineEffect layout. No broad pointer-search result is a function proof.
    checks = {0x087F28: bytes.fromhex('01 61'), 0x01ED1440: bytes.fromhex('23 69'),
              0x01ED1466: bytes.fromhex('18 47'),
              0x087F54: bytes.fromhex('00 48 00 47 f5 13 ed 09')}
    for offset, expected in checks.items():
        assert source[offset:offset + len(expected)] == baseline[offset:offset + len(expected)] == expected
    assert u32(source, 0x087EE0) == u32(source, 0x087F0C) == u32(source, 0x087F48) == u32(source, 0x01ED1450) == 0x02039600
    normal = [u32(source, 0x087F14), u32(source, 0x087F50)]
    assert normal == [0x08087FE1, 0x08088001]
    assert source[0x087EA4:0x088020] == baseline[0x087EA4:0x088020]
    assert source[0x01ED13F4:0x01ED146E] == baseline[0x01ED13F4:0x01ED146E]
    return {'confidence': 'STATIC_PROVEN_ROM_SEMANTICS',
            'decomp_correlated_structure': 'ScanlineEffect (DMA first-scanline callback)',
            'structure_ram': '0x02039600', 'callback_ram': '0x02039610',
            'state_ram': '0x02039615', 'source_index_ram': '0x02039614',
            'clear': {**location(0x087EA4), 'callback_field_cleared': False,
                      'notes': 'Clears DMA src/dest/control and state. Leaves +10 callback retained, inactive state prevents call.'},
            'set_params': {**location(0x087EE4), 'write': location(0x087F28),
                           'instruction': 'str r1,[r0,#0x10]', 'bytes': '01 61',
                           'width_bytes': 4, 'destination': '0x02039610',
                           'normal_candidates': [callback_target(v) for v in normal],
                           'normal_candidates_confidence': 'STATIC_PROVEN_NOT_OBSERVED_LIVE',
                           'mode16_literal': {**location(0x087F08), 'value': '0xA2600001'},
                           'mode16_callback_literal': location(0x087F14),
                           'mode32_callback_literal': location(0x087F50)},
            'reader': {**location(0x01ED13F4), 'load': location(0x01ED1440),
                       'instruction': 'ldr r3,[r4,#0x10]', 'call': location(0x01ED1442),
                       'trampoline': location(0x01ED1466), 'jump': 'bx r3',
                       'gate': 'state0 return; state3 stop DMA; other state invokes callback',
                       'dma_register_base': '0x040000B0',
                       'hook': {**location(0x087F54), 'target_thumb': '0x09ED13F5'}},
            'code_unchanged': True, 'first_write': 'UNKNOWN', 'normal_live_values': [],
            'first_invalid_write': 'NOT_CAPTURED', 'writer_pc': None,
            'watchpoint_support': {'source_verified': True, 'runtime_validated_this_phase': False,
                                  'source': 'https://github.com/mgba-emu/mgba/blob/0.10.5/src/debugger/gdb-stub.c',
                                  'source_semantics': 'Z2 sets WRITE_CHANGE or WRITE; GDB size argument not consumed in _setBreakpoint.',
                                  'plan': 'Experimentally verify four separate watch addresses 02039610/11/12/13; record before/after and first invalid write.'}}


def verify_inputs(plan):
    for path, expected in plan['inputs'].items():
        assert sha((ROOT / path).read_bytes()) == expected, 'Immutable input changed: ' + path
    assert plan['inputs'][BASELINE] == BASELINE_SHA
    assert hashlib.md5((ROOT / SOURCE).read_bytes()).hexdigest() == '9cad8e771940e7f7094d13911552cef0'
    for path, expected in plan['global_config'].items():
        assert sha(Path(path).read_bytes()) == expected, 'Original mGBA config changed: ' + path
    proof = protection.protected_snapshot()
    assert proof['files'] == plan['protected909']['files'] == 909
    assert proof['aggregate_sha256'] == plan['protected909']['aggregate_sha256']
    return {k: proof[k] for k in ('files', 'aggregate_sha256')}


def investigate():
    plan = read(PLAN)
    protection_result = verify_inputs(plan)
    source, baseline = (ROOT / SOURCE).read_bytes(), (ROOT / BASELINE).read_bytes()
    prior = read('out/phase7/ja_renderer_runtime_trace_log.json')
    prior_proof = read('out/phase7/ja_renderer_runtime_proof_matrix.json')
    old = prior['crash_evidence']
    state = bytes.fromhex(old['state_bytes'])
    bad = u32(state, 16)
    assert bad == int(old['registers']['r3'], 16) == 0xE3E800D9
    entry = next(e for e in read('out/unbound-texts.json')['entries'] if e['id'] == 'scr_1F1194E')
    text = compare_text(source, baseline, entry, state)
    applied = read('out/phase6/ja_phase6_cleanup_batch04_combined_controlfix.json')['entries']
    assert len(applied) == 2403 and entry['id'] not in {e['id'] for e in applied}
    text['present_in_applied_2403'] = False
    trial = plan['observed_trial']
    assert not plan['current_automatic_input_permission']
    assert no_debugger_argv(trial['argv']) and not trial['debugger_started'] and not trial['debugger_connection']
    assert trial['result'] == 'CRASH_OBSERVED' and trial['reported_error'].endswith('E3E800D8')
    local = {}
    # Raw image/ROM evidence may later leave TEMP. Missing evidence stays missing,
    # never changes a recorded, human-reviewed report into a new PASS.
    for label, path, expected in (
        ('temporary_rom', trial['temporary_rom'], BASELINE_SHA),
        ('screenshot', trial['evidence']['image_path'], trial['evidence']['image_sha256'])):
        file = Path(path)
        local[label] = 'NOT_AVAILABLE' if not file.exists() else 'HASH_VERIFIED'
        if file.exists():
            assert sha(file.read_bytes()) == expected, 'Recorded local evidence changed: ' + path
    conditions = [{'condition': c, 'variant': 'english' if c in 'AC' else 'ja',
                   'gdb': c in 'CD', 'started_trials': 1 if c == 'B' else 0,
                   'completed_target_trials': 1 if c == 'B' else 0,
                   'crashes': 1 if c == 'B' else 0,
                   'result': 'CRASH_OBSERVED' if c == 'B' else 'NOT_RUN',
                   'trial_ids': ['B2'] if c == 'B' else []} for c in 'ABCD']
    matrix = {'phase': '7C-6', 'conditions': conditions, 'observed_trials': [trial],
              'setup_only_excluded': [plan['setup_only']],
              'historical_phase7c5': {'variant': 'ja', 'gdb': True, 'crashes': 1,
                                      'result': 'CRASH_OBSERVED', 'controlled_current_trial': False,
                                      'notes': 'Prior stepping/detach launch, not matched current C/D comparison.'},
              'conclusion': {'gdb_required_for_crash': False, 'japanese_causality': 'UNKNOWN',
                             'english_comparison': 'NOT_RUN', 'resolved': False,
                             'repeat_reproducibility': 'NOT_ESTABLISHED_ONE_CURRENT_TRIAL',
                             'runtime_pass': False, 'automatic_inputs_now_allowed': False},
              'protection': {'protected909': protection_result, 'input_sha256': plan['inputs'],
                             'original_config_sha256': plan['global_config'],
                             'existing_save_sha256': plan['saves_in_protected_909'],
                             'local_evidence': local},
              'unchanged_management': prior_proof['summary']}
    trace = {'phase': '7C-6', 'static_lifecycle': static_callback(source, baseline),
             'historical_bad_ram': {**old, 'provenance': 'Phase7C5 only; NOT B2 memory measurement',
                                    'target_check': callback_target(bad),
                                    'state_byte': f'0x{state[21]:02X}'},
             'PCS_comparison': text,
             'current_live_write_observations': [], 'current_normal_ram_observations': [],
             'first_invalid_write_captured': False, 'writer_pc': None, 'writer_function': 'UNKNOWN',
             'causality': 'UNKNOWN', 'no_patch_proposed': True,
             'next_steps': plan['future_manual_steps']}
    return matrix, trace


def markdown(matrix, trace):
    text = trace['PCS_comparison']
    return f'''# Phase 7C-6: Runtime Crash Isolation / Callback Writer Investigation

調査のみ。修正・注入・commit/pushなし。自動操作の許可は撤回済み、追加キー入力なし。

## 比較結果

|条件|ROM|GDB|今回対象試行|結果|
|---|---|---|---:|---|
|A|英語元ROM|なし|0|NOT_RUN|
|B|基準日本語ROM|なし|1|橋の場面でCRASH_OBSERVED、E3E800D8|
|C|英語元ROM|あり|0|NOT_RUN|
|D|基準日本語ROM|あり|0|NOT_RUN（前Phaseのクラッシュ履歴1件は別枠）|

B2は新規portableディレクトリ・独立saveで起動。autoload/cheat/patch/rewindなし、-g/-dなし、2345 listenerなし。
原ROMをbyte同一コピー。installed mGBA Qt0.10.5 executableもコピーし、portable.iniでconfig.ini/qt.iniを隔離。
[mGBA config.c](https://github.com/mgba-emu/mgba/blob/0.10.5/src/core/config.c)と
[Qt ConfigController](https://github.com/mgba-emu/mgba/blob/0.10.5/src/platform/qt/ConfigController.cpp)でrouting確認。
setup-only B1はhidden launchで打切り。再現試行に数えず、新しいB2 saveを使用。削除なし。
B2開始は人間操作。許可されたX1回を序盤で使用後、許可撤回。後続の正確な手動操作列はUNKNOWN。
最後の観測文章は「はるか むかし…」、次の観測はHoopa。クラッシュ直前の文章と正確な時刻はUNKNOWN。
ユーザーの画像と報告で橋のクラッシュを確認。画像SHA/一時ROMSHA/起動argvはfixture・matrixへ記録。
後の読取確認でmGBA processは存在せず、今回RAM/register捕捉なし。

GDB接続はクラッシュの必要条件ではない。ただし英語ROM比較未実施なので、日本語化原因とは断定しない。
新規条件の反復は1件のみ。通常実行PASS・修正済み・全条件再現性とも判定しない。

## callbackライフサイクル（静的根拠）

RAM02039600はScanlineEffect相当。+10=callback、+14=source index、+15=state。
ROM00087EA4 / GBA08087EA4 clearはsource/dest/control/state等をreset。callback +10は消さず、state0でcallしない。
ROM00087EE4 / GBA08087EE4 SetParams、00087F28 / 08087F28 `01 61: str r1,[r0,#10]`がcallback4bytesを設定。
16bit比較literal ROM00087F08=A2600001、pointer literal00087F14=08087FE1。
別分岐literal00087F50=08088001。little endianはe1 7f 08 08 / 01 80 08 08。
これらは静的候補。正常時実値・初回書込み・更新時刻は未観測。
ROM00087F54 / GBA08087F54のhook literalは09ED13F5。
ROM01ED13F4 / GBA09ED13F4はstate0でreturn、3でstop、その他でDMA設定とcallbackを呼ぶ。
ROM01ED1440 / GBA09ED1440 `23 69: ldr r3,[r4,#10]`、01ED1442から01ED1466 / 09ED1466の`18 47: bx r3`へ。
構造/順序は[FireRed scanline_effect.c](https://github.com/pret/pokefirered/blob/master/src/scanline_effect.c)と照合。
対象code/literal blockは元ROMと日本語ROMで同一。全writerを列挙した証明ではない。

## 前PhaseのRAM証拠とPCS照合

以下はPhase7C5のGDB捕捉。今回B2のRAM実測に転用しない。
02039610=d9 00 e8 e3、r3=E3E800D9、PC=E3E800D8、LR=09ED1447、SP=03007DB0。
Thumbビットは立つが、実行先はROM/RAM callback範囲外。state02039615=E6も0/3でなくcall分岐と整合。
02039600の24bytesはROM01F119D4 / GBA09F119D4のPCS本文と完全一致。
scr_1F1194E開始ROM01F1194E / GBA09F1194Eから+0x86(134bytes)、decodeは改行+`than if you were to rem`。
本文437bytes、FF終端、FE7/FA0/FB8/FC0/FD3。PCS roundtrip一致。
pointer owner ROM01E7093B / GBA09E7093B=4e 19 f1 09。
本文全slotとownerは元ROM・基準ROMで同一。このentryは適用済み2403件に含まれず、relocationなし。
source SHA={text['source_sha256']}。
途中一致はbyte由来の証拠のみ。active renderer、実destination、write関数、overflowの証明ではない。
source pointerが同一でも、他の日本語化entryやdynamic bufferの間接的影響は未除外。

## writer追跡・保留

最初の不正書込みNOT_CAPTURED、writer PC/function UNKNOWN。正常RAM値の実測0。
write watchpointは[mGBA0.10.5 GDB source](https://github.com/mgba-emu/mgba/blob/0.10.5/src/debugger/gdb-stub.c)でZ2の実装を確認。
_setBreakpointはsizeを消費しない。4bytes指定だけで全面監視を証明せず、02039610/11/12/13の各addressを実験検証する。
今回watchpointは実行していない。GDBのみが原因でないと分かったため、先に英語/GDBなしAを比較。
その後必要ならcallback setter/読出し、write watchでold/new、PC/LR/SP、実instructionのwidth/addressを捕捉。
最後のbxをwriterと誤認しない。根拠のない修正patchは作らない。

## 再現計画・保護

tests/fixtures/ja_phase7_crash_repro_plan.json参照。自動キー入力は現在禁止。
A/Bは毎回新しいfolder/save、同version/config、NEW GAME。既存save・savestate禁止。
橋を通過して初めて「対象まで再現せず」とする。title/Hoopaのみ到達はINCOMPLETE。
C/Dは別試行。接続・step・detach順も記録する。前PhaseのDを同条件比較と偽装しない。
前Phaseのfont2/224px/spacing1/FE14は部品観測として維持。font4/5、FA/FB、player、Batch01 53件は未観測のまま。
Batch01注入承認0、既適用2403、Phase6保留774を維持。
元ROM SHA=7aa25bbf568f7cfcf6ee1cf2e9e6ff637350b3d0705c2375cabb6baa7d9739f7、MD5=9cad8e771940e7f7094d13911552cef0。
日本語ROM SHA={BASELINE_SHA}。既存save7ファイル、global config/qt.ini、protected909 hash不変を検証。
実施済み/未実施はmatrixで区別。原因確度UNKNOWN。追加の手動比較が必要なので今回writer追跡を打切り。

再現可能な解析: `python scripts/investigate_ja_phase7_crash_isolation.py --verify-existing`。
新規成果物だけ`--write-new`で生成。既存成果物は無断上書きしない。
pytest/py_compile/diff-check結果は最終報告参照。安全gateと期待SHAは変更せず、完全一致6パスだけ追加。
'''


def output_bytes(result):
    matrix, trace = result
    return {OUTPUTS[0]: markdown(matrix, trace).encode('utf-8'),
            OUTPUTS[1]: (json.dumps(matrix, ensure_ascii=False, indent=2) + '\n').encode('utf-8'),
            OUTPUTS[2]: (json.dumps(trace, ensure_ascii=False, indent=2) + '\n').encode('utf-8')}


def persist_new(result):
    contents = output_bytes(result)
    assert not any((ROOT / path).exists() for path in contents), 'Existing deliverable refused'
    for path, raw in contents.items():
        file = ROOT / path
        file.parent.mkdir(parents=True, exist_ok=True)
        with file.open('xb') as stream:
            stream.write(raw)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--write-new', action='store_true')
    group.add_argument('--verify-existing', action='store_true')
    args = parser.parse_args()
    result = investigate()
    if args.write_new:
        persist_new(result)
    elif args.verify_existing:
        assert all((ROOT / path).read_bytes() == raw for path, raw in output_bytes(result).items())
        print('Evidence reproduces; no files written')
    else:
        print(json.dumps(result[0]['conclusion'], ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
