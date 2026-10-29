"""Screen-free Phase7C6 follow-up. Bounded PCS expansion model, NOT GBA runtime.

No UI APIs, emulator launch, network, ROM patch, or translation changes.
Prior evidence is immutable; only absent follow-up artifacts can be created.
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

OUTPUTS = ('docs/ja-phase7-runtime-crash-static-followup.md',
           'out/phase7/ja_callback_static_followup.json')
PRIOR_SHA = {
    'rom/unbound.gba': '7aa25bbf568f7cfcf6ee1cf2e9e6ff637350b3d0705c2375cabb6baa7d9739f7',
    'out/unbound-ja-phase6-cleanup-batch04.gba': '0d1d00e7b0f4f113514abbcf1907e6d8949fd12b9193bf2cb0ad764ace5559d8',
    'docs/ja-phase7-runtime-crash-isolation.md': '771f69f5902b9150004ded3c8bd82bfe3500787bacbf1e9c88a623e66d037066',
    'out/phase7/ja_runtime_crash_isolation_matrix.json': '7880d72f8479936b73dfdf8a21104c59a1efd47c24baf927694f354d4cbdc656',
    'out/phase7/ja_callback_writer_trace.json': 'e82b16e43c56c1024b1cbb59c1cf7a7edee58476affc0a963a5ae21a1f849f93',
    'scripts/investigate_ja_phase7_crash_isolation.py': 'bc9f2217f44d2ae14c02a7d9cc9ed02f86ca269863547304a55616e28f155189',
    'tests/test_ja_phase7_crash_isolation.py': '88c8c263e5dbe92b11b9491f8b4309558d29023d1e7c22845483c0441362a76c',
    'tests/fixtures/ja_phase7_crash_repro_plan.json': 'b518d27ab91a6727099810e858f98d8719f867b25a05dbafcde5858cd6fa2199',
}
RAM_BASE = 0x02000000
FIELD = 0x02021D18
BUFFER = {2: 0x02021CD0, 3: 0x02021CF0, 4: 0x02021D04}
TEXT = 0x09F1194E
CALLBACK = 0x02039610
STATE = 0x02039600


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read(path):
    return json.loads((ROOT / path).read_text(encoding='utf-8'))


def u32(raw, at):
    return struct.unpack_from('<I', raw, at)[0]


def loc(offset):
    return {'rom_offset': f'0x{offset:08X}', 'gba_address': f'0x{offset + 0x08000000:08X}'}


class ModelLimit(Exception):
    pass


def expand_model(rom, initial_buffers, max_writes=100000, initial_callback=0x08087FE1):
    """Model only ROM-proved FF/FD/plain-byte paths; reject FC/unknown FD.

    Explicit synthetic RAM. No game execution or observed register is produced.
    Source/destination aliasing is intentional and must NOT be snapshotted away.
    """
    ram = bytearray(0x40000)
    for index, raw in initial_buffers.items():
        start = BUFFER[index] - RAM_BASE
        assert 0 <= len(raw) <= {2: 32, 3: 20, 4: 20}[index]
        ram[start:start + len(raw)] = raw
    struct.pack_into('<I', ram, CALLBACK - RAM_BASE, initial_callback)
    count, max_depth, callback_writes = 0, 0, []

    def load(address):
        if 0x08000000 <= address < 0x08000000 + len(rom):
            return rom[address - 0x08000000]
        if RAM_BASE <= address < RAM_BASE + len(ram):
            return ram[address - RAM_BASE]
        raise ValueError(f'Model read outside mapped data: {address:08X}')

    def store(address, byte):
        nonlocal count
        if count >= max_writes:
            raise ModelLimit('WRITE_BUDGET')
        if not RAM_BASE <= address < RAM_BASE + len(ram):
            raise ValueError('Model write outside synthetic RAM')
        old = u32(ram, CALLBACK - RAM_BASE)
        ram[address - RAM_BASE] = byte
        count += 1
        if CALLBACK <= address < CALLBACK + 4:
            callback_writes.append({'address': f'0x{address:08X}', 'size': 1, 'byte': f'{byte:02X}',
                                    'before': f'0x{old:08X}',
                                    'after': f'0x{u32(ram, CALLBACK - RAM_BASE):08X}',
                                    'status': 'SYNTHETIC_NOT_OBSERVED',
                                    'static_store_candidate': loc(0x090A6), 'observed_pc': None})
        if address + 1 == STATE + 24:
            raise ModelLimit('TARGET_RANGE_CAPTURED')

    def expand(source, destination, depth):
        nonlocal max_depth
        if depth > 16:
            raise ModelLimit('RECURSION_BUDGET')
        max_depth = max(max_depth, depth)
        while True:
            byte = load(source)
            source += 1
            if byte == 0xFF:
                store(destination, byte)
                return destination
            if byte == 0xFC:
                raise ValueError('FC path not modeled; fail closed')
            if byte == 0xFD:
                index = load(source)
                source += 1
                if index not in BUFFER:
                    raise ValueError('Unknown modeled placeholder')
                destination = expand(BUFFER[index], destination, depth + 1)
            else:
                store(destination, byte)
                destination += 1

    returned, end, reason = False, None, None
    try:
        end = expand(TEXT, FIELD, 0)
        returned = True
    except ModelLimit as error:
        reason = str(error)
    state = bytes(ram[STATE - RAM_BASE:STATE - RAM_BASE + 24])
    return {'method': 'BOUNDED_SYNTHETIC_PCS_MODEL_NOT_CPU_OR_GAME_EXECUTION',
            'returned': returned, 'end_pointer': f'0x{end:08X}' if end is not None else None,
            'writes': count, 'max_depth': max_depth, 'stop_reason': reason,
            'state_bytes': state.hex(' '), 'callback_writes': callback_writes,
            'initial_callback_assumed_not_observed': f'0x{initial_callback:08X}',
            'runtime_writer_captured': False}


def static_routes(rom, baseline):
    for start, end in ((0x08FCC, 0x090B8), (0x0912C, 0x09144), (0x091E0, 0x09204),
                       (0x694C8, 0x694E4), (0x6BF14, 0x6BF3C), (0x6C4F0, 0x6C508),
                       (0x1E70929, 0x1E7093F), (0x1E709DB, 0x1E70A19),
                       (0x1EB59D0, 0x1EB5AD4), (0xB2A250, 0xB2A25C)):
        assert rom[start:end] == baseline[start:end], f'Relevant code/data changed: {start:08X}'
    assert rom[0x694CC:0x694D2] == bytes.fromhex('04 48 9f f7 7d fd')
    assert u32(rom, 0x694E0) == FIELD
    assert rom[0x090A6:0x090AC] == bytes.fromhex('22 70 01 34 92 e7')
    assert rom[0x09004:0x09018] == bytes.fromhex('28 78 01 35 00 f0 ea f8 01 1c 20 1c ff f7 dc ff 04 1c dc e7')
    assert u32(rom, 0x09140) == BUFFER[4]
    assert u32(rom, 0x091F4) == 0x08231E70
    assert u32(rom, 0x231E80) == 0x0800913D
    assert u32(rom, 0x6BF38) == 0x08B2A250
    assert [u32(rom, 0xB2A250 + i * 4) for i in range(3)] == list(BUFFER.values())
    branches = []
    for gender, start, words in ((0, 0x1E709F3, ['him', 'he', 'son']),
                                  (1, 0x1E70A06, ['her', 'she', 'daughter'])):
        copies = []
        for index in range(3):
            at = start + index * 6
            assert rom[at:at + 2] == bytes((0x85, index))
            pointer = u32(rom, at + 2)
            assert pointer == u32(baseline, at + 2)
            raw = decode_pcs(rom[pointer - 0x08000000:pointer - 0x08000000 + 16])
            assert raw.terminated and raw.text == words[index]
            assert rom[pointer - 0x08000000:pointer - 0x08000000 + raw.byte_length] == baseline[pointer - 0x08000000:pointer - 0x08000000 + raw.byte_length]
            copies.append({'command': loc(at), 'index': index, 'destination': f'0x{BUFFER[index + 2]:08X}',
                           'source': loc(pointer - 0x08000000), 'text': raw.text,
                           'bytes_including_FF': raw.byte_length})
        assert rom[start + 18] == 3
        branches.append({'gender_result': gender, 'copies': copies})
    assert rom[0x1E709DB:0x1E709F3] == bytes.fromhex('a0 21 0d 80 00 00 06 01 f3 09 e7 09 21 0d 80 01 00 06 01 06 0a e7 09 03')
    assert u32(rom, 0x15FC34) == 0x0806C4F1  # opcode A0 table owner.
    assert rom[0x6C4F0:0x6C4FE] == bytes.fromhex('03 49 04 48 00 68 00 7a 08 80 00 20 70 47')
    assert u32(rom, 0x6C504) == 0x0300500C
    return {'confidence': 'STATIC_PROVEN_RELEVANT_BRANCHES', 'relevant_english_ja_bytes_equal': True,
            'field_copy': {'function': loc(0x694C8), 'destination_literal_owner': loc(0x694E0),
                           'destination': f'0x{FIELD:08X}', 'call_expander': loc(0x694CE)},
            'expander': {'entry': loc(0x08FCC), 'ordinary_store': loc(0x090A6),
                         'FD_dispatch': loc(0x09004), 'recursive_call': loc(0x09010),
                         'FF_store': loc(0x090AE), 'capacity_parameter': False},
            'buffer3': {'factory_table_owner': loc(0x231E80), 'factory': loc(0x0913C),
                        'ram_literal_owner': loc(0x09140), 'ram': '0x02021D04',
                        'bytes_before_field_destination': 20},
            'script_preparation': {'call_owner': loc(0x1E70929), 'helper': loc(0x1E709DB),
                                   'gender_handler': loc(0x6C4F0),
                                   'gender_source': '*RAM0300500C +8, raw u8',
                                   'branches': branches,
                                   'other_gender_values': 'Return without these buffer writes; actual bridge value UNKNOWN',
                                   'runtime_executed': False},
            'intervening_header': {'native_call_owner': loc(0x1E70934),
                                   'function': loc(0x1EB59D0), 'copy_source': loc(0x1F2CAE8),
                                   'source_text': '???', 'bytes_including_FF': 4,
                                   'notes': 'This local source/header is unchanged, not the 437-byte body.'}}


def investigate():
    for path, expected in PRIOR_SHA.items():
        assert sha((ROOT / path).read_bytes()) == expected, 'Prior evidence changed: ' + path
    protected = protection.protected_snapshot()
    rom = (ROOT / 'rom/unbound.gba').read_bytes()
    baseline = (ROOT / 'out/unbound-ja-phase6-cleanup-batch04.gba').read_bytes()
    routes = static_routes(rom, baseline)
    text = rom[0x1F1194E:0x1F11B03]
    assert len(text) == 437 and text[283:285] == b'\xFD\x04'
    assert not any(byte in (0xFC, 0xFD, 0xFF) for byte in text[:283])
    old = read('out/phase7/ja_callback_writer_trace.json')['historical_bad_ram']
    observed = bytes.fromhex(old['state_bytes'])
    def buffers(words):
        return {i + 2: Charmap().encode(word) for i, word in enumerate(words)}
    male = buffers(['him', 'he', 'son'])
    female = buffers(['her', 'she', 'daughter'])
    no_ff = {**male, 4: bytes(20)}
    models = {'normal_male': expand_model(rom, male), 'normal_female': expand_model(rom, female),
              'unterminated_buffer3': expand_model(rom, no_ff)}
    gap = FIELD - BUFFER[4]
    period = gap + 283
    target_phase = (STATE - FIELD - 283) % period
    predicted = bytes((bytes(gap) + text[:283])[(target_phase + i) % period] for i in range(24))
    assert period == 303 and target_phase == 154 and target_phase - gap == 134
    assert predicted == observed == bytes.fromhex(models['unterminated_buffer3']['state_bytes'])
    for name in ('normal_male', 'normal_female'):
        assert models[name]['returned'] and not models[name]['callback_writes']
    return {'phase': '7C-6 static follow-up', 'no_screen_capture': True, 'no_UI_or_emulator_started': True,
            'new_runtime_trials': 0, 'prior_sha256': PRIOR_SHA,
            'protected909': {'files': protected['files'], 'aggregate_sha256': protected['aggregate_sha256']},
            'routes': routes, 'models': models,
            'alias_hypothesis': {'status': 'CONDITIONAL_EXACT_MATCH_NOT_RUNTIME_PROVEN',
                                 'precondition': 'buffer3 has no terminator/control recursion in its 20-byte prefix; first FD04 is reached',
                                 'first_FD04_text_offset': 283, 'gap_to_destination': gap,
                                 'repeat_period_bytes': period, 'callback_state_phase': target_phase,
                                 'matching_entry_byte_offset': 134, 'matched_bytes': 24,
                                 'predicted': predicted.hex(' '), 'historical_observed': observed.hex(' '),
                                 'predicted_callback_thumb': '0xE3E800D9',
                                 'predicted_pc_after_bx': '0xE3E800D8',
                                 'observed_live_writer': None, 'root_cause': 'UNKNOWN',
                                 'why_buffer3_unterminated': 'UNKNOWN; static 0/1 preparation normally supplies FF'},
            'next_trace_only_when_user_available': [
                'At 08008FCC r1=09F1194E, capture buffer1/2/3 and FIELD before expansion.',
                'At 08009004 for first FD04, capture r4 destination, r5 source and RAM02021D04..17.',
                'Trace helper 09E709DB, gender handler0806C4F0 and bufferstring writer0806BF14; record raw gender.',
                'Conditional store breakpoint080090A6 with r4=02039610; capture r2, LR, SP and before/after.',
                'A valid buffer3 FF before first FD04 rules out THIS synthetic precondition; inspect other writers, do not force hypothesis.',
                'English/no-GDB comparison still NOT_RUN. No runtime PASS or Batch01 approval.'],
            'writer_captured': False, 'japanese_causality': 'UNKNOWN', 'ROM_patch': False}


def markdown(data):
    return '''# Phase 7C-6 静的追補：buffer3自己参照仮説

画面取得・キー入力・mGBA起動なし。OWへ干渉するUI操作なし。新規runtime試行0。
既存のPhase7C6成果物は上書きせず、追補だけ作成。ROM・訳文・glossary変更、commit/pushなし。

## 新しい根拠

通常のfield表示はROM000694C8/GBA080694C8、literal ROM000694E0=RAM02021D18を展開先にする。
expander入口 ROM00008FCC/GBA08008FCC、通常1byte書込ROM000090A6/GBA080090A6。
FD処理ROM00009004、再帰call00009010、FF書込000090AE。容量引数・範囲検査はこの経路にない。
FD04 factory table owner ROM00231E80/GBA08231E80=0800913D、factory0000913C、literal00009140=02021D04。
buffer3はfield展開先の20bytes手前。これはライブRAM値ではなくROM上の対応関係。

scr_1F1194Eは先頭283bytesをコピーした後、最初のFD04（buffer3）に到達する。
先頭283bytesにFC/FD/FFはない。FE/FBはexpanderでそのままコピーする。
buffer3の20bytesにFFも再帰を起こすFDもない場合、再帰copyが既に展開した本文へ入り込む。
その場合は20+283=303bytes周期の自己参照copyが継続する。単なる有限長437bytesのoverflowとは別の仮説。

## 限定モデルの照合

モデルはPython bytearrayの仮想RAMだけを使用。実Thumb実行・mGBA試行・ライブPC捕捉ではない。
FF/FD/通常byteの該当経路だけをモデル化し、FC/未知FDはエラー。書込回数・再帰深度・範囲を制限。
初期callback=08087FE1、buffer3=20個の00は仮定であり観測値ではない。
RAM02039600の位相は (02039600-02021D18-283)%303=154。
最初の20bytesを引くと原文offset134（ROM01F119D4/GBA09F119D4）となる。
このモデルが予測する24bytesは、前Phaseで観測した02039600の24bytesと完全一致。
callback02039610..13はd9 00 e8 e3、Thumb pointer E3E800D9、bx後 E3E800D8を予測する。
通常byte書込候補は080090A6だが、実行時writer PCの捕捉ではない。
正常なhim/he/son、her/she/daughterをFF終端で設定した対照モデルは有限長で戻り、callbackへ書かない。

## 正常な設定経路も存在する

会話直前のscript call owner ROM01E70929/GBA09E70929は helper ROM01E709DB/GBA09E709DBを呼ぶ。
opcode A0 handler ROM0006C4F0/GBA0806C4F0は*RAM0300500Cの+8をraw u8で読む。
helperは結果0でROM01E709F3、1でROM01E70A06へ分岐し、opcode85でbuffer1/2/3を設定。
0ならhim/he/son（各4/3/4bytes、FF込み）、1ならher/she/daughter（各4/4/9bytes）。
他の値ではこのhelperのbuffer設定をせずreturnする。ただし橋での実際の値はUNKNOWN。
bufferstring handler ROM0006BF14/GBA0806BF14、table literal owner0006BF38=08B2A250。
table ROM00B2A250/54/58の宛先は02021CD0/02021CF0/02021D04。
StringCopyのbyte書込はROM00008D8A、FF書込00008D9A。設定が実行されれば終端を付ける。
このcode/table/helper/son等の本文とpointerは英語ROM・日本語ROMで一致。
途中のnative header ROM01EB59D0は、局所source ROM01F2CAE8の???（4bytes、FF込み）を扱う。
このheader sourceも不変。437-byte本文をこの小さいheader stackへコピーすると決めつけない。

## 判定と次の必要観測

CONDITIONAL_EXACT_MATCH_NOT_RUNTIME_PROVEN。単なる類似文より強い位相一致だが、原因確定ではない。
なぜbuffer3が未終端になるか、helperがどのbranchを実行したか、後から誰が壊したかは未証明。
文字列途中一致だけで推定した任意destinationを置かず、ROMで確定したFIELD/buffer3配置から計算した。
正常な設定branchがあるため「元ROMも必ず壊れる」「日本語化が無関係」とも断定しない。

次回ユーザーが操作可能な時だけ、expander r1=09F1194Eでbuffer3の20bytesとfield初期状態を捕捉。
最初のFD04直前（08009004）のr4/r5とbuffer3終端、helperのraw gender、opcode85実行を確認。
080090A6でr4=02039610の条件付き停止ができれば、実際の書込みとbefore/afterを記録。
FD04前に有効なFFがあれば、この仮説の前提は成立しない。他のwriterを調べ、仮説を押し通さない。
英語・GDBなし比較は依然NOT_RUN。新しいruntime PASSなし、Batch01 53件承認0を維持。

再現: python scripts/investigate_ja_phase7_crash_static_followup.py --verify-existing
旧成果物・保護909のハッシュ検証、新規追補のexclusive生成、負例テストを実施。結果は最終報告参照。
'''


def output_bytes(data):
    return {OUTPUTS[0]: markdown(data).encode('utf-8'),
            OUTPUTS[1]: (json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode('utf-8')}


def persist_new(data):
    contents = output_bytes(data)
    assert not any((ROOT / path).exists() for path in contents), 'Existing follow-up refused'
    for path, raw in contents.items():
        with (ROOT / path).open('xb') as output:
            output.write(raw)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--write-new', action='store_true')
    modes.add_argument('--verify-existing', action='store_true')
    args = parser.parse_args()
    data = investigate()
    if args.write_new:
        persist_new(data)
    elif args.verify_existing:
        assert all((ROOT / path).read_bytes() == raw for path, raw in output_bytes(data).items())
        print('Static follow-up reproduces; no UI or files changed')
    else:
        print(json.dumps(data['alias_hypothesis'], ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
