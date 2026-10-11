#!/usr/bin/env python3
"""Phase 7C-3, immutable Batch 01 audit. No ROM writer or translation editor.

python scripts/build_ja_phase7_story_batch01.py --analyze
python scripts/build_ja_phase7_story_batch01.py --write

This evidence-limited pass holds all 53 entries. It deliberately has no build
fallback: new consumer/width proof needs another reviewed integration pass.
Generated artifacts are exclusive-create; existing results are never replaced.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import re
import runpy
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lib.fa_control import join_segments, parse_raw_segments
from lib.gen3_font import NORMAL_GLYPH_WIDTHS, NORMAL_JAPANESE_GLYPH_WIDTHS
from lib.pcs_text import Charmap, decode_pcs, fc_arg_count
from lib.renderer_profiles import (horizontal_layout_trace,
    normal_line_widths_with_placeholders, rom_naming_profiles)
from lib.translation_glossary import load_glossary
from lib.translation_tokens import semantic_tokens, strip_hma_quotes
from scripts.build_ja_phase6_batch02 import owner_audit
from scripts.build_ja_phase6_batch06 import interior_pointer_hits
from scripts.build_ja_phase6_cleanup_batch03 import (
    PHASE7A_PATHS, PHASE7B_PATHS, PHASE7C1_PATHS, PHASE7C2_PATHS,
    PHASE7C3_PATHS, INITIAL_SNAPSHOT, protected_snapshot)
from scripts.build_ja_phase6_cleanup_glossary import assert_strict_map
from scripts.build_ja_phase6_voice_integration import encoded
from scripts.build_ja_phase7_inventory import APPLIED, BASE_ROM, BASE_SHA, MAPS
from scripts.build_ja_phase7_story_translation_batches import raw_controls

REVIEW = 'tests/fixtures/ja_phase7_story_batch01_claude_review.json'
HANDOFF = 'out/phase7/ja_story_translation_batch01_for_claude.json'
MANIFEST = 'out/phase7/ja_story_translation_batch_manifest.json'
REVIEW_SHA = 'f526bf823e248ddc273ddb6b52517d6d1694ac0ce9e69f5e8033095627a29b2d'
HANDOFF_SHA = '6868f808fd8d023ae7cd0864a51a8c478f4e027d2e161394b535b5e4f3692d7c'
SOURCE_MD5 = '9cad8e771940e7f7094d13911552cef0'
PHRASE_INDICES = (0, 1, 13, 15, 30, 31, 32, 34, 35, 37, 40, 48)
NAME_INDICES = (20, 22, 26, 28, 29, 30, 35, 36, 38, 40)
GAP_INDICES = (9, 20, 24, 30, 32, 33, 34, 36, 37, 38, 40, 41, 51, 52)
NUANCE_INDICES = (1, 16, 19, 24, 40, 41, 47)
OFFICIAL_INDICES = (19, 32)
FA_HOLD_INDICES = (1, 31, 40)
MEANING_HOLD_INDICES = (19, 40, 49)
QA_INDICES = (0, 1, 2, 4, 5, 6, 7, 9, 12, 15, 17, 19, 20, 21, 22,
              28, 29, 31, 32, 35, 40, 48, 49)
OUTPUTS = (
    'docs/ja-phase7-story-batch01-technical.md',
    'out/phase7/ja_story_batch01_technical_holds.json',
    'out/phase7/ja_story_batch01_validation.json',
    'out/phase7/ja_story_batch01_binary_audit.json',
    'tests/fixtures/ja_phase7_story_batch01_runtime_qa.json',
)
HAN = re.compile(r'[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]')

# Independent human-readable judgments, pinned to the immutable review digest.
# These are annotations only, never replacement translations or FA approvals.
MEANING_NOTES = (
    '心の傷・怒り→世界を許せず機械を兵器へ→終戦。因果と主語を保持。',
    '怒り・補償要求・王に渡すものがない・クーデターを保持。FAでdark force先行は別保留。',
    '16 Years Ago=16ねんまえ。中央寄せの見た目は未承認。',
    '15 Years Later=15ねんご。時間経過は保持。',
    'Present Day=げんざい。',
    'CacneaとCut、命令文を保持。サボネア/いあいぎりは既存公式名資料と別照合。',
    'guardianへの反発・自立・両親にも力を見せる。日本語の主語省略は自然。話者属性は推定しない。',
    'stats=のうりょく、potential=そしつ。Abilityと混同しない。',
    '手がかかる人物と用事を頼めなくなる嘆き。性別省略は自然。',
    'Martの荷物を受領したかという質問。施設名のscopeは別保留。',
    '肯定と丁寧な応答。sirの直訳省略は自然な敬語化。',
    'discreet=めだたないように。秘密裏の受領確認を保持。',
    '逃した二人の一人と遭遇、対立回避、尾行なしの認識。I let escapeをにがしたで保持。',
    '加入時に求めた報酬へ再び近づいた評価。加入条件は最後のwaitへ保持。',
    '母親のmechanical leg=きかいのあし。医療/義足との確定はしない。',
    '手足等の冷淡な列挙と必要物資が揃えば科学者が作る条件を保持。',
    '北へ向かいtarget捕獲、Zephに現在の状況を伝える指示。myは文脈上自然に省略。',
    'ポケモンの進行先はIcicle Caveで推量appearsも保持。',
    'Wait…isn’t this…? の戸惑いを保持。',
    'must be backは確信の強い推論。もどったようだは確度が弱く、CLAUDE_REVIEW_REQUIRED。',
    'Ruins of Voidで何があったか/Aklove/時間がない。nameと地名scopeは別保留。',
    'No, not this timeの拒否。そうはいかないは拒否の自然な補いだが対象行為や話者は断定しない。',
    '幽閉の教訓、ポケモンなしの無力、再発拒否、Vivill Town、今回の準備を保持。',
    '楽しんでほしいという丁寧な短い案内。',
    'Feyの命令、加入先、Marlonへの確認、残留の奇跡を保持。Franklyの語気は自然な言い換えの範囲。',
    '悪化への認識、差を埋める案、同意されにくい提案を保持。',
    '制服の認識と[player]なのかという驚き。新しい話者属性は付与しない。',
    '本人否定、spyの疑念、Akloveへの怒り。原文のyouをあなたとするが声質承認はしない。',
    '偽物、以前の欺き、顔、追い返した後の伝言、罪への威嚇を保持。',
    '戦い方/aura/正体の驚き→[player]確認→否定の順を保持。',
    '内輪争い禁止、[player]は敵でない、敵はLight of Ruin、指揮権の最後通告を保持。',
    '全体の攻撃計画は一致。ただしLight of Ruinの完成形が一wait早い。',
    '基地捜索/奇襲/奪還/Hoopa研究/封印の計画を保持。Prison Bottleのentityは別保留。',
    'Feyの報復がない確信を問う。うごいてもの条件は次waitへ保持。',
    'Feyの無関心・研究目的・支援・成否はAklove次第・単独でも危険を保持。',
    '計画成功に必要な全戦力と[player]同伴提案を保持。without a hitchは早期に完結するが固有情報ではない。',
    'Cube幽閉、約束、Shadow Warriorsと魂の解放、拘束の継続条件を保持。',
    '二人の生還だけでなく他の人もCubeにいたか、その知識を問う。insideの遅れは倒置注記。',
    'Aros/16年前/Fey/[player]の父という開示順を保持。',
    'Arosの行方、systemのバグ発見能力、不完全でも脱出法を見つける人物を保持。',
    'most important secretsがだいじなひみつへ弱まり最高重要度を失う。FA早期開示も別保留。',
    '17年前/Zephの子の死/old friends/Hoennから訪問を保持。oldはふるいゆうじんで残る。',
    '状態を気遣い、Marlonと共に子の死を今聞いた、弔意を保持。',
    'IvoryとMarlonへの弔意の礼、久々の再会を保持。',
    '船旅の確認と感想の質問。',
    '数日の所要時間と快い旅を保持。',
    '相手にも息子がいる記憶の確認。',
    '息子がいた/若くして病死/残念な気持ち。much tooの強度は薄いがわかくしての早逝含意と弔意は残る。',
    '科学者の知識と蘇生を考えたかの質問。対象は次waitへ保持。',
    'no known methods to truly reviveをほうほうはないと断定。既知の方法がないと不可能の区別が消え、CLAUDE_REVIEW_REQUIRED。',
    '子どもの現在地を丁寧に質問。',
    '友人Euler Logの一時的子守とFrozen Heightsの現在地。省略に意味上の問題なし、名前scopeは別保留。',
    'Frozen Heightsの友人/旧partner/創業協力/Guardian称号/幻のポケモン/最近の出産/子の名は忘れたを保持。',
)
FA_NOTES = {
    0: 'P2で機械の変換述語、P3でweapon/Ultimate Weapon。倒置だが重要名は後のwait。',
    1: '原文P3 dark / P4 force。訳P3やみのちから。重要な力の完成形の早期開示を同等と証明できない。',
    6: 'guardianと自立/両親/相手への挑戦が各waitで一致。',
    12: '遭遇→対立を避ける決定→尾行なしの各waitを保持。',
    13: '求めた報酬への道(P1)、加入した時(P2)。修飾の後置を注記。',
    15: '必要品の条件(P1)、operation/科学者が作る(P2)、母の望む手足(P3)。倒置を注記。',
    24: '加入の命令/理解確認/残留の事実/奇跡が各wait一致。',
    28: '本人の顔/偽物否定/伝言/for me/罪の威嚇が各wait一致。',
    29: '[player]という確認はFA後、最後の否定はFB後。',
    30: '指揮をとる(P3)、残るShadows(P4)。後置所有句で読みにくいが対象は後のwait。',
    31: '原文完成形Light of Ruin=P3、訳はめつのひかり=P2。攻撃対象名をFA前に完成させる。',
    32: 'Prison Bottle/Warriors/remainingのwait維持。奪還述語の再掲とoff guardの倒置を注記。',
    33: '確信の質問、take action条件はFA後。',
    34: 'could not care lessの否定を先に言い、Aklove goalsを後に言う。無関心の強意完成は早まるが固有目的は維持。',
    35: 'hitchの完結はP1→P0。進行条件/固有名の開示ではなくwithout aの修飾を先に完成する自然な語順差。',
    36: 'Warriorsへの約束/魂解放、Light of Ruin保持/魂拘束が各wait一致。',
    37: 'trip inside(P0)はなかに(P1)へ遅れる。Cube名と第三者/存在の知識は原文waitに残る。',
    39: '脱出法をみつけるなら(P3)→かれだろう(P4)。',
    40: '原文完成形Light of Ruin=P2、訳はめつのひかり=P1。攻撃対象名をFA前に完成させる。',
    48: 'thought about trying(P0)、bring him back(P1)。蘇生の目的はFA後に残る。',
    49: 'be us、子どもが穴を埋めるの述語完結がFA後に一致。本文の断定化は別の意味保留。',
}


def read(path):
    return json.loads((ROOT / path).read_text(encoding='utf-8'))


def sha(data):
    return hashlib.sha256(data).hexdigest()


def serialize(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8')


def prior_snapshot():
    paths = PHASE7A_PATHS | PHASE7B_PATHS | PHASE7C1_PATHS | PHASE7C2_PATHS
    return {p: sha((ROOT / p).read_bytes()) for p in sorted(paths)}


def unchanged_snapshot_gate():
    path = 'scripts/build_ja_phase6_cleanup_batch03.py'
    old = subprocess.check_output(['git', 'show', 'HEAD:'+path], cwd=ROOT).decode('utf-8')
    new = (ROOT/path).read_text(encoding='utf-8')
    def body(text):
        tree = ast.parse(text)
        function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'protected_snapshot')
        return ast.dump(function, include_attributes=False)
    assert body(old) == body(new), 'Protected snapshot safety gate changed'
    return {'protected_snapshot_function_AST_unchanged_from_HEAD': True,
            'function_AST_sha256': sha(body(new).encode()),
            'management_changes_limited_to_exact_path_sets': True}


def phases(segments):
    """Wait phases derived from byte-boundary segments, never review.phase_view."""
    phase = 0
    result = []
    for index, segment in enumerate(segments):
        result.append({'segment_index': index, 'wait_phase': phase, **segment})
        if segment['after_control'] in ('FA', 'FB'):
            phase += 1
    return result


def canonical_controls(raw):
    return [c['bytes'] for c in raw_controls(raw, 0)
            if c['bytes'] not in ('fc 15', 'fc 16')]


def phrase_phase(segment_phases, phrase):
    """Locate a completed phrase, including one split across layout boundaries."""
    text = ''
    for s in segment_phases:
        text += (' ' if text else '') + s['text']
        if phrase in text:
            return s['wait_phase']
    return None


def normal_widths(text, spacing=0):
    """ROM normal-font diagnostic. Caller font/viewport NOT approved here.

    The existing repository calculator is authoritative for advance widths.
    Add ROM-observed Japanese letterSpacing on ordinary glyphs only. FC/FD
    arguments are skipped, never counted as glyphs; unknown expansions stay null.
    """
    result = normal_line_widths_with_placeholders(text, {})
    counts, count, japanese, i = [], 0, False, 0
    raw = Charmap('ja').encode(text)
    while i < len(raw):
        b = raw[i]
        i += 1
        if b == 0xFF:
            break
        if b == 0xFC:
            cmd = raw[i]
            i += 1 + fc_arg_count(cmd)
            if cmd in (0x15, 0x16):
                japanese = cmd == 0x15
        elif b in (0xFE, 0xFA, 0xFB):
            counts.append(count)
            count = 0
        elif b in (0xFD, 0xF7, 0xF8, 0xF9):
            i += 1
        elif japanese:
            count += 1
    counts.append(count)
    assert len(counts) == len(result['line_static'])
    lines = [w + spacing * n for w, n in zip(result['line_static'], counts)]
    return {**result, 'japanese_ordinary_glyphs_by_line': counts,
            'letter_spacing_diagnostic': spacing, 'line_static_with_spacing': lines,
            'max_static_with_spacing': max(lines), 'actual_entry_usable_width': None,
            'status': 'CONDITIONAL_NORMAL_FONT_NOT_RUNTIME_FIT_PROOF'}


def renderer_evidence(source, baseline):
    """Store inspected local Thumb blocks and literal owners, with proof limits."""
    from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB
    dis = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
    blocks = ((0x6A180, 0x6A1A6), (0x6A2B4, 0x6A2D6),
              (0xA093AC, 0xA093E6), (0x6943C, 0x69464),
              (0x694C8, 0x694E0), (0x8FCC, 0x8FE8),
              (0x9004, 0x901C), (0x91E0, 0x91F4), (0x9120, 0x9128),
              (0xF6D5C, 0xF6DA6), (0xF6DB0, 0xF6DD6),
              (0xF6DDC, 0xF6E04), (0xF6CD0, 0xF6D06),
              (0xF6D3E, 0xF6D48), (0xCBE00, 0xCBE04),
              (0x9C9EE0, 0x9C9F1A), (0x2D30, 0x2D4C),
              (0x5B10, 0x5B22), (0x5C28, 0x5C54),
              (0x5C6C, 0x5C98), (0x5C98, 0x5CCC),
              (0x5880, 0x58A2), (0x6FB22, 0x6FB34))
    out = []
    for a, b in blocks:
        assert source[a:b] == baseline[a:b], hex(a)
        out.append({'rom_start': f'0x{a:08X}', 'gba_start': f'0x{a+0x08000000:08X}',
                    'rom_end_exclusive': f'0x{b:08X}', 'bytes': source[a:b].hex(' '),
                    'instructions': [f'{x.address:08X}: {x.mnemonic} {x.op_str}'
                                     for x in dis.disasm(source[a:b], a+0x08000000)]})
    assert source[0x1FB100:0x1FB200] == bytes(NORMAL_GLYPH_WIDTHS)
    assert source[0x20F500:0x20F618] == NORMAL_JAPANESE_GLYPH_WIDTHS
    table = int.from_bytes(source[0x6A1A8:0x6A1AC], 'little') - 0x08000000
    std6 = int.from_bytes(source[table+24:table+28], 'little') - 0x08000000
    assert table == 0x160450 and std6 == 0x1E7D5DA
    assert source[std6:std6+11] == bytes.fromhex('8a 67 00 00 00 00 66 6d 6c 03 03')
    assert source[0x15FB50:0x15FB54] == bytes.fromhex('ad 93 a0 08')
    assert int.from_bytes(source[0x91F4:0x91F8], 'little') == 0x08231E70
    assert int.from_bytes(source[0x231E74:0x231E78], 'little') == 0x08009121
    assert source[0x9128:0x912C] == bytes.fromhex('0c 50 00 03')
    assert source[0xCBE04:0xCBE08] == bytes.fromhex('e1 9e 9c 08')
    assert source[0x3A73BC:0x3A73C4] == bytes.fromhex('00 02 0f 1a 04 0f 98 01')
    return {'blocks': out, 'command_table': 'ROM 0015F9B4 / GBA 0815F9B4',
            'std_table': 'ROM 00160450 / GBA 08160450',
            'std6_owner': 'ROM 00160468 / GBA 08160468',
            'std6_script': 'ROM 01E7D5DA / GBA 09E7D5DA',
            'std6_bytes': source[std6:std6+11].hex(' '),
            'message_handler': 'ROM 00A093AC / GBA 08A093AC',
            'field_expand': 'ROM 00008FCC / GBA 08008FCC',
            'FD01_dispatch_owner': 'ROM 00231E74 / GBA 08231E74',
            'FD01_producer': 'ROM 00009120 / GBA 08009120',
            'FD01_record_pointer_ram': '0x0300500C; producer returns dereferenced pointer, record offset 0',
            'field_printer_setup': 'ROM 000F6D5C / GBA 080F6D5C',
            'font_selector_hook': 'ROM 000CBE00 -> ROM 009C9EE0 / GBA 089C9EE0',
            'font_variants': [4, 5, 2], 'conditional_setup_x': 0,
            'conditional_setup_y': 1, 'conditional_japanese_letter_spacing': 1,
            'candidate_window': 'ROM 003A73BC / GBA 083A73BC, 26x4 tiles',
            'candidate_physical_width': 208, 'entry_live_usable_width': None,
            'page_controls': 'FC15/16 change printer+21; FE resets X/increments Y; FA restores X/scrolls; FB restores X/Y/clears, no language reset in inspected handlers',
            'proof_gap': 'All owners reach callstd6, but native setup opcode8A and live window0 initialization/overrides, font4/5 glyph metrics and font-selector RAM state are not proved on each root. Normal table at 20F500 is not approval for every variant. No proved conservative per-entry bound.',
            'naming': rom_naming_profiles(source, 0)['player_name'],
            'buffer_gap': 'FD01 producer and recursion are proven locally, not a complete naming writer-to-saved-record proof or all allowed values. Local keyboard bound42px assumes normal Latin; font variants and expansion/page effects of external values remain unproved.'}


def validate_inputs(review, handoff, manifest, rom):
    ids = [x['id'] for x in review]
    assert len(ids) == len(set(ids)) == 53
    assert ids == [x['id'] for x in handoff] == manifest['batches'][0]['entry_ids']
    assert Counter(x['category'] for x in review) == {'scripts': 50, 'plain_scripts': 3}
    for i, (r, h) in enumerate(zip(review, handoff)):
        assert r['review_index'] == i and r['status'] == 'confirmed'
        for key in ('id', 'category', 'original', 'protected_tokens', 'priority'):
            assert r[key] == h[key], (i, key)
        assert r['previous_candidate'] == h['previous_japanese_candidate']
        assert r['priority_confidence'] == h['priority']['confidence']
        assert r['speaker_id'] == h['speaker']['speaker_id']
        assert r['speaker_confidence'] == h['speaker']['speaker_confidence']
        assert r['scene_id'] == h['scene_ids']
        assert r['scene_evidence']['event_bindings'] == h['event_bindings']
        assert r['source_control_structure']['slot_size'] == h['slot_size']
        a, size = int(h['rom_offset'], 16), h['slot_size']
        decoded = decode_pcs(rom, a, size)
        assert decoded.terminated and decoded.byte_length == size and decoded.raw_count == 0
        assert decoded.text == strip_hma_quotes(h['original'])
        segments = parse_raw_segments(rom[a:a+size], rom_offset=a)
        assert join_segments(segments) == decoded.text
        assert segments == h['original_segments']
        assert raw_controls(rom[a:a+size], a) == r['source_control_structure']['control_order']
        assert semantic_tokens(decoded.text) == r['protected_tokens']
        assert len(r['translated_segments']) == len(segments)
        assert join_segments(segments, r['translated_segments']) == r['reviewed_text_joined']
        for s, target in zip(segments, r['translated_segments']):
            assert semantic_tokens(s['text']) == semantic_tokens(target), (i, 'segment tokens')
        for root in h['event_root_records']:
            p = int(root['script_pointer_owner']['rom_offset'], 16)
            assert int.from_bytes(rom[p:p+4], 'little') == 0x08000000+int(root['script_offset'], 16)
    return {'unique_ids': 53, 'duplicates': 0, 'missing': 0, 'manifest_match': True,
            'originals_rom_verified': 53, 'previous_candidate_changes': 0,
            'scene_event_speaker_priority_changes': 0, 'protected_token_changes': 0,
            'source_control_metadata_changes': 0, 'index_base': 0,
            'static_roots_do_not_prove_runtime_reachability': True}


def verify_prior_applied(rom):
    rows = read(APPLIED)['entries']
    assert len(rows) == len({x['id'] for x in rows}) == 2403
    moves = {}
    for path in MAPS:
        moves.update({r['id']: r for r in read(path)['relocations']})
    injector, codec = runpy.run_path(str(ROOT/'005_hybrid_injector.py')), Charmap('ja')
    checks = []
    for r in rows:
        dest = int(moves[r['id']]['new_offset'], 16) if r['id'] in moves else int(r['address'], 16)
        payload = encoded(injector, codec, r, r['translated'])
        assert rom[dest:dest+len(payload)] == payload, r['id']
        for p in r.get('pointer_sources', []):
            a = int(p, 16)
            assert int.from_bytes(rom[a:a+4], 'little') == 0x08000000+dest, r['id']
        checks.append({'id': r['id'], 'destination': dest, 'payload_sha256': sha(payload),
                       'pointer_sources': r.get('pointer_sources', [])})
    return {'verified_payloads': 2403, 'payload_mismatches': 0, 'recorded_pointer_mismatches': 0,
            'translation_input_sha256': sha((ROOT/APPLIED).read_bytes()),
            'payload_owner_manifest_sha256': sha(serialize(checks))}


def independent_names(source, baseline):
    """Official lexical names and ROM table identity are separate evidence."""
    evidence = {}
    for kind, slug, en, ja in (
        ('pokemon-species', 'cacnea', 'Cacnea', 'サボネア'),
        ('move', 'cut', 'Cut', 'いあいぎり'),
        ('pokemon-species', 'hoopa', 'Hoopa', 'フーパ'),
        ('item', 'prison-bottle', 'Prison Bottle', 'いましめのツボ')):
        path = '.cache/pokeapi/'+kind+'/'+slug+'.json'
        data = read(path)
        names = {x['language']['name']: x['name'] for x in data['names']}
        assert (names['en'], names['ja-hrkt']) == (en, ja)
        evidence[en] = {'lexical_names_verified': True, 'english': en, 'ja_hrkt': ja,
                        'entity_type': kind, 'api_entity_id': data['id'],
                        'cached_primary_source': path, 'cache_sha256': sha((ROOT/path).read_bytes()),
                        'narrative_entity_proven_by_api': False}
    extracted = read('out/unbound-texts.json')['entries']
    table_proofs = {}
    for text, category in (('Prison Bottle', 'item_names'), ('Rift Cave', 'map_names')):
        rows = [e for e in extracted if e['category'] == category and strip_hma_quotes(e['original']) == text]
        assert len(rows) == 1
        e = rows[0]
        a = int(e['address'], 16)
        d = decode_pcs(source, a, e['byte_length'])
        assert d.text == text and d.terminated
        for p in e['pointer_sources']:
            o = int(p, 16)
            assert int.from_bytes(source[o:o+4], 'little') == 0x08000000+a
        table_proofs[text] = {'id': e['id'], 'category': category,
                             'rom_offset': e['address'], 'gba_address': f'0x{a+0x08000000:08X}',
                             'pointer_owners': e['pointer_sources'], 'table_index': e.get('table_index'),
                             'source_rom_text': d.text,
                             'text_occurrence_is_not_item_operand_identity': True}
    return {'api_names': evidence, 'rom_tables': table_proofs}


def technical_reasons(record):
    reasons = []
    if record['control_status']['state'] != 'PASS':
        reasons.append('HOLD_TECHNICAL_OTHER:control_or_PCS_failure')
    if record['semantic_state']['status'] == 'CLAUDE_REVIEW_REQUIRED':
        reasons.append('HOLD_SEMANTIC:CLAUDE_REVIEW_REQUIRED')
    if record['fa_semantic_verdict'] == 'FA_SEMANTIC_BOUNDARY_REVIEW_REQUIRED':
        reasons.append('HOLD_SEMANTIC:FA_SEMANTIC_BOUNDARY_REVIEW_REQUIRED')
    if record['buffer_status']['tokens'] and not record['buffer_status']['all_values_and_writer_proven']:
        reasons.append('HOLD_BUFFER:writer_values_page_and_live_width_unproved')
    if record['official_name_status']['state'] != 'NOT_REQUIRED':
        reasons.append('HOLD_OFFICIAL_NAME:entity_or_project_name_approval_missing')
    if record['glossary_status']['scope_gaps']:
        reasons.append('HOLD_GLOSSARY_SCOPE:entry_scope_not_approved')
    p = record['pointer_status']
    if p['missing'] or p['stale'] or p['interior_hits']:
        reasons.append('HOLD_POINTER:unresolved_owner_or_interior_reference')
    if record['width_status']['old_fa_source_envelope_exceeded']:
        reasons.append('HOLD_WIDTH:existing_fa_source_envelope_gate_retained')
    if not record['consumer_status']['proved_live_profile_or_conservative_bound']:
        reasons.append('HOLD_RENDERER:font_variants_and_live_viewport_unproved')
    elif not record['width_status']['actual_fit_approved']:
        reasons.append('HOLD_WIDTH:actual_renderer_fit_unproved')
    if record['width_status']['spacing1_diagnostic_over_208']:
        reasons.append('HOLD_WIDTH:conditional_normal_spacing1_exceeds_candidate_208')
    return reasons


def make_runtime_qa(records, handoff):
    result = []
    for i in QA_INDICES:
        r, h = records[i], handoff[i]
        checks = ['正しいentryの発火を英文で特定', 'font/window/X/Y/spacingを記録', 'FE/FBの表示と進行']
        if r['fa_segmented']:
            checks += ['FA前後で入力停止と1行scroll', '各wait_phaseの重要名詞・述語の初出順を比較']
        if i in (31, 40):
            checks += ['はめつのひかりの早期完成を再レビュー。保留解除前に日本語ROMを作らない']
        if i in NAME_INDICES:
            checks += ['NEW GAMEの7文字最大幅Latin名、FD01展開、Latin→Japanese復元と次行']
        if i == 21:
            checks += ['後続承認時のみ19→23 bytes relocation、全ownerと旧pointer残存を再検査']
        result.append({'batch_index': i, 'id': r['id'], 'technical_status': r['technical_status'],
                       'japanese_applied_this_pass': False, 'candidate_only': r['reviewed_japanese'],
                       'map_event_conditions': h['event_bindings'],
                       'route_status': 'STATIC_LOCATION_ONLY' if h['event_bindings'] else 'UNKNOWN',
                       'actual_route_and_required_save_flags': 'UNKNOWN',
                       'new_game_early_candidate': i <= 17,
                       'route_hint': '序章/初期イベント候補' if i <= 17 else '記録したmapのイベント条件を満たす検証saveを別途用意',
                       'checks': checks, 'runtime_test_performed': False})
    return {'metadata': {'count': len(result), 'tested': 0, 'applied_in_this_pass': 0,
                         'baseline_rom': BASE_ROM, 'new_rom': None,
                         'warning': '日本語候補は全保留。基準ROMでconsumerを観測し、意味再レビューとgate通過後に別build。'},
            'entries': result}


def run_cli(script, args):
    command = [sys.executable, '-X', 'utf8', str(ROOT/script), *map(str, args)]
    p = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding='utf-8')
    assert p.returncode == 0, p.stdout+p.stderr
    return p.stdout


def controlfix_diagnostic(review, handoff):
    """No unearned FA layout flag: verify refusal and stable repair twice."""
    entries = []
    for r, h in zip(review, handoff):
        e = {**h['prepared_source_metadata'], 'translated': r['reviewed_text_joined']}
        if r['fa_segmented']:
            e.update(control_segments=h['original_segments'], translated_segments=r['translated_segments'],
                     fa_placement_policy='require_segments', fa_layout_reviewed=False,
                     source_boundary_sequence=[s['after_control'] for s in h['original_segments'] if s['after_control']],
                     controls=dict(Counter(s['after_control'] for s in h['original_segments'] if s['after_control'])))
        entries.append(e)
    with tempfile.TemporaryDirectory(prefix='unbound-p7c3-controlfix-') as td:
        p = Path(td)
        (p/'input.json').write_bytes(serialize({'entries': entries}))
        reports = []
        for a, b, report in (('input.json', 'once.json', 'once-report.json'),
                             ('once.json', 'twice.json', 'twice-report.json')):
            run_cli('004_controlfix_translations.py', [p/a, '-o', p/b,
                    '--source', p/'input.json', '--target-lang', 'ja', '--no-wrap', '--report', p/report])
            reports.append(json.loads((p/report).read_text(encoding='utf-8'))['stats'])
        once, twice = (p/'once.json').read_bytes(), (p/'twice.json').read_bytes()
        assert once == twice, 'Controlfix is not byte-idempotent'
        fixed = json.loads(once)['entries']
        by_id = {x['id']: x for x in fixed}
        for r in review:
            item = by_id[r['id']]
            if r['fa_segmented']:
                assert item['translated'] is None
                assert item['fa_placement_status'] == 'FA_PLACEMENT_REVIEW_REQUIRED'
            else:
                assert strip_hma_quotes(item['original']) == strip_hma_quotes(r['original'])
                expected = FIX['ensure_japanese_page'](r['reviewed_text_joined'])[0]
                assert Charmap('ja').encode(item['translated']) == Charmap('ja').encode(expected), (
                    r['review_index'], 'Controlfix changed candidate bytes, not merely layout escape spelling')
        assert reports[0]['remaining_control_mismatches'] == reports[1]['remaining_control_mismatches'] == 0
        assert reports[0]['fa_placement_review_required'] == reports[1]['fa_placement_review_required'] == 21
        return {'status': 'IDEMPOTENT_DIAGNOSTIC_FA21_CORRECTLY_REFUSED_NOT_APPROVED',
                'byte_identical': True, 'result_sha256': sha(once), 'passes': reports,
                'non_fa_page_only_results': 32, 'fa_refusals': 21,
                'non_fa_candidate_encoded_byte_changes': 0,
                'prior_2403_entries_sent_to_controlfix': 0}


def empty_strict_dry_run():
    """Real injector, empty safe subset. NOT approval or capacity proof for 53."""
    with tempfile.TemporaryDirectory(prefix='unbound-p7c3-inject-') as td:
        p = Path(td)
        (p/'safe.json').write_bytes(serialize({'entries': []}))
        run_cli('005_hybrid_injector.py', [ROOT/BASE_ROM, p/'safe.json', '-o', p/'NEVER.gba',
                '--target-lang', 'ja', '--dry-run', '--fail-on-no-space', '--map-output', p/'map.json'])
        mapping = json.loads((p/'map.json').read_text(encoding='utf-8'))
        assert_strict_map(mapping, mapping, 0)
        assert mapping['stats']['in_place'] == mapping['stats']['pointer_writes'] == 0
        assert not mapping['relocations'] and not (p/'NEVER.gba').exists()
        return {'status': 'PASS_EMPTY_SAFE_SUBSET_ONLY', 'input_entries': 0,
                'held_entries_attempted': 0, 'not_approval_for_53': True,
                'no_rom_written': True, 'stats': mapping['stats'],
                'missing_relocations': mapping['missing_relocations'],
                'full_rebuild': 'NOT_RUN_NO_SAFE_ADDITIONS'}


FIX = runpy.run_path(str(ROOT/'004_controlfix_translations.py'))


def analyze():
    protected, previous = protected_snapshot(), prior_snapshot()
    management = unchanged_snapshot_gate()
    assert protected['files'] == 909 and protected['aggregate_sha256'] == INITIAL_SNAPSHOT
    assert sha((ROOT/REVIEW).read_bytes()) == REVIEW_SHA
    assert sha((ROOT/HANDOFF).read_bytes()) == HANDOFF_SHA
    review, handoff = read(REVIEW), read(HANDOFF)['entries']
    source, baseline = (ROOT/'rom/unbound.gba').read_bytes(), (ROOT/BASE_ROM).read_bytes()
    assert hashlib.md5(source).hexdigest() == SOURCE_MD5 and sha(baseline) == BASE_SHA
    accounting = validate_inputs(review, handoff, read(MANIFEST), source)
    anchors = renderer_evidence(source, baseline)
    name_evidence = independent_names(source, baseline)
    selections = [{'id': h['id'], 'rom_offset': int(h['rom_offset'], 16),
                   'slot_size': h['slot_size'], 'pointer_owners': h['pointer_ownership']['recorded_sources']}
                  for h in handoff]
    owners = owner_audit(selections, source)['entries']
    interiors = interior_pointer_hits(source, selections)
    prior_applied = verify_prior_applied(baseline)
    inv = read('out/phase7/ja_full_localization_inventory.json')
    remaining = inv['phase6_remaining_ids']
    assert len(remaining) == len(set(remaining)) == 774
    assert not set(x['id'] for x in review) & set(x['id'] for x in read(APPLIED)['entries'])
    glossary = load_glossary(ROOT/'glossaries/ja.json', expected_language='ja')
    glossary_terms = read('glossaries/ja.json')['terms']
    records = []
    source_control_counts = Counter()
    for i, (r, h, own) in enumerate(zip(review, handoff, owners)):
        a, size = int(h['rom_offset'], 16), h['slot_size']
        raw = source[a:a+size]
        source_control_counts.update(c['kind'] for c in raw_controls(raw, a))
        fixed = FIX['ensure_japanese_page'](r['reviewed_text_joined'])[0]
        payload = Charmap('ja').encode(fixed)
        assert not HAN.search(fixed)
        assert Charmap('ja').encode(decode_pcs(payload, max_length=len(payload)).text) == payload
        assert canonical_controls(raw) == canonical_controls(payload), i
        source_segments = parse_raw_segments(raw, rom_offset=a)
        target_segments = parse_raw_segments(payload)
        # Source boundary/control offsets cannot equal relocated Japanese offsets;
        # byte codes and segment indices (including token-containing segments) must.
        assert [x['after_control'] for x in source_segments] == [x['after_control'] for x in target_segments]
        original_phases = phases(source_segments)
        translated_phases = phases([{**s, 'text': t} for s, t in zip(source_segments, r['translated_segments'])])
        reveal = None
        if i in (31, 40):
            before = phrase_phase(original_phases, 'Light of Ruin')
            after = phrase_phase(translated_phases, 'はめつのひかり')
            assert (before, after) == ((3, 2) if i == 31 else (2, 1))
            reveal = {'english_completed_name_phase': before, 'japanese_completed_name_phase': after,
                      'early_by_waits': before-after, 'same_wait_phase': False,
                      'plot_surprise_equivalence': 'UNPROVED',
                      'note': 'Light of before FA already suggests the organization; earlier complete name is still not proven equivalent. No FA movement authorized.'}
        fa_state = 'NOT_REQUIRED' if not r['fa_segmented'] else (
            'FA_SEMANTIC_BOUNDARY_REVIEW_REQUIRED' if i in FA_HOLD_INDICES else
            'PASS_WITH_NOTE' if i in PHRASE_INDICES else 'PASS_PHASE_COMPARISON')
        source_width = normal_widths(strip_hma_quotes(r['original']))
        widths, spacing1 = normal_widths(fixed), normal_widths(fixed, 1)
        matched = glossary.matches(strip_hma_quotes(r['original']), r['category'], entry_id=r['id'])
        glossary_missing = [term.source for _, _, term in matched if term.target_for(r['category']) not in fixed]
        assert not glossary_missing, (i, glossary_missing)
        gaps = []
        for warning in r['glossary_scope_warnings']:
            term_name = warning.split('=', 1)[0]
            terms = [t for t in glossary_terms if t['source'] == term_name]
            if term_name == 'Mart':
                terms = [t for t in glossary_terms if t['source'] == 'Poké Mart']
            gaps.append({'english_term': term_name, 'japanese_candidate': warning.split('=', 1)[1].split(' (', 1)[0] if '=' in warning else warning,
                         'entity': 'Franchise region' if term_name == 'Hoenn' else 'Unbound narrative reference; exact entity/writer not newly proved',
                         'approved_scope': [{k: t.get(k) for k in ('source', 'target', 'context_scope', 'categories', 'entry_ids', 'global_replace')} for t in terms],
                         'current_entry_id': r['id'], 'entry_in_approved_scope': False,
                         'independent_evidence': 'Exact source contains term, glossary inspected via scoped matcher; previous usage is not new scope authorization',
                         'verdict': 'HOLD_SCOPE_APPROVAL_REQUIRED', 'review_warning': warning})
        pointer = {**own, 'interior_hits': interiors[r['id']], 'slot_size': size,
                   'encoded_length': len(payload), 'relocation_needed': len(payload) > size,
                   'source_rom_offset': h['rom_offset'], 'source_gba_address': h['gba_address'],
                   'all_observed_exact_owners_recorded': not own['missing'] and not own['stale'],
                   'global_completeness_limit': 'Whole-ROM exact/interior scan cannot exclude computed references',
                   'raw_candidates_are_not_proven_owners': True,
                   'unresolved_reference_samples': [
                       {'reference': hit, 'surrounding_bytes': source[int(hit.split('->')[0], 16)-8:
                           int(hit.split('->')[0], 16)+12].hex(' '),
                        'structural_consumer': 'UNKNOWN'} for hit in interiors[r['id']]],
                   'actual_relocation_approved': False}
        owner_routes = []
        for p in own['recorded']:
            o = int(p, 16)
            assert source[o-2:o] == b'\x0f\x00' and source[o+4:o+6] == b'\x09\x06'
            assert baseline[o:o+4] == source[o:o+4]
            owner_routes.append({'owner_rom': p, 'command_rom': f'0x{o-2:08X}',
                                 'command_bytes': source[o-2:o+6].hex(' '), 'consumer': 'loadword0/callstd6'})
        assert baseline[a:a+size] == raw, ('Batch source changed in baseline', r['id'])
        record = {'batch_index': i, 'canonical_entry_id': r['id'], 'id': r['id'], 'category': r['category'],
                  'original_english': r['original'], 'reviewed_japanese': r['reviewed_text_joined'],
                  'translation_status': r['status'], 'translation_review_source': r['review_source'],
                  'technical_audit_source': 'codex_independent_local_rom', 'page_controlled_candidate_only': fixed,
                  'semantic_state': {'status': 'CLAUDE_REVIEW_REQUIRED' if i in MEANING_HOLD_INDICES else
                                     'PASS_WITH_NUANCE_NOTE' if i in NUANCE_INDICES else 'PASS_TEXT_COMPARISON',
                                     'note': MEANING_NOTES[i], 'speaker_inference': 'NONE'},
                  'fa_segmented': r['fa_segmented'], 'fa_phrase_note_present': i in PHRASE_INDICES,
                  'fa_semantic_verdict': fa_state, 'fa_independent_note': FA_NOTES.get(i),
                  'original_wait_segments_rom_derived': original_phases if r['fa_segmented'] else [],
                  'japanese_wait_segments': translated_phases if r['fa_segmented'] else [],
                  'completed_name_reveal': reveal,
                  'control_status': {'state': 'PASS', 'source_sequence': canonical_controls(raw),
                                     'candidate_sequence_ignoring_only_language_switches': canonical_controls(payload),
                                     'protected_tokens': r['protected_tokens'], 'segment_tokens_match': True,
                                     'kanji': 0, 'encode_errors': 0, 'roundtrip_bytes': True,
                                     'encoded_bytes': len(payload), 'encoded_sha256': sha(payload)},
                  'buffer_status': {'tokens': ['FD01'] if i in NAME_INDICES else [],
                                    'producer_reference': anchors['FD01_producer'] if i in NAME_INDICES else None,
                                    'local_keyboard_bound_normal_latin': 42 if i in NAME_INDICES else None,
                                    'all_values_and_writer_proven': False if i in NAME_INDICES else True,
                                    'page_wrapper': '[latin][player][japanese]' if i in NAME_INDICES else None,
                                    'runtime_page_restoration': 'CONDITIONAL_ORDINARY_LOCAL_NAME_ONLY' if i in NAME_INDICES else 'NOT_REQUIRED',
                                    'note': anchors['buffer_gap'] if i in NAME_INDICES else None},
                  'consumer_status': {'owner_routes': owner_routes, 'std6_script': anchors['std6_script'],
                                      'proved_live_profile_or_conservative_bound': False,
                                      'font_variants': [4, 5, 2], 'live_font_x_margin_and_viewport': 'UNPROVED',
                                      'proof_gap': anchors['proof_gap']},
                  'width_status': {'normal_spacing0': widths, 'normal_spacing1_diagnostic': spacing1,
                                   'source_normal_spacing0': source_width,
                                   'old_fa_source_envelope_exceeded': r['fa_segmented'] and widths['max_total'] > source_width['max_total'],
                                   'source_envelope_is_not_actual_overflow_proof': True,
                                   'spacing1_diagnostic_over_208': spacing1['max_static_with_spacing'] > 208,
                                   'horizontal_trace': horizontal_layout_trace(fixed),
                                   'local_name_width_diagnostic': normal_line_widths_with_placeholders(fixed, {1: 42}) if i in NAME_INDICES else None,
                                   'actual_fit_approved': False},
                  'pointer_status': pointer,
                  'official_name_status': {'state': 'HOLD_ENTITY_OR_PROJECT_NAME_UNPROVED' if i in OFFICIAL_INDICES else 'NOT_REQUIRED',
                                           'issues': r['official_name_warnings'],
                                           'independent_evidence': name_evidence if i in (5, 19, 32) else None,
                                           'independent_note': 'Rift Cave map binding establishes a named location, not approved Japanese spelling' if i == 19 else
                                            'Prison Bottle literal matches item table name; no item-number script operand ties this utterance to the record' if i == 32 else None},
                  'glossary_status': {'approved_matches': [asdict(t) for _, _, t in matched],
                                      'approved_match_violations': [], 'scope_gaps': gaps}}
        reasons = technical_reasons(record)
        assert reasons, 'New proof needs a separately reviewed build, not this hold-only writer'
        record.update(technical_status=reasons[0].split(':')[0], primary_hold=reasons[0],
                      secondary_holds=reasons[1:], all_holds=reasons,
                      next_action='Resolve each listed proof gap, then rerun independent review; never use confirmed or <=208 as approval.')
        records.append(record)
    assert len(MEANING_NOTES) == 53 and len(FA_NOTES) == 21
    assert tuple(r['batch_index'] for r in records if r['fa_phrase_note_present']) == PHRASE_INDICES
    assert tuple(r['batch_index'] for r in records if r['buffer_status']['tokens']) == NAME_INDICES
    assert tuple(r['batch_index'] for r in records if r['glossary_status']['scope_gaps']) == GAP_INDICES
    assert tuple(r['batch_index'] for r in records if r['official_name_status']['issues']) == OFFICIAL_INDICES
    fa = [r for r in records if r['fa_segmented']]
    assert len(fa) == 21 and sum(len(r['original_wait_segments_rom_derived']) for r in fa) == 180
    assert sum(r['control_status']['source_sequence'].count('fa') for r in records) == 39
    fix_result, dry = controlfix_diagnostic(review, handoff), empty_strict_dry_run()
    assert protected_snapshot() == protected and prior_snapshot() == previous
    assert sha((ROOT/BASE_ROM).read_bytes()) == BASE_SHA
    summary = {'entries': 53, 'confirmed_translation': 53, 'safe': 0, 'held': 53,
               'in_place': 0, 'relocations': 0, 'pointer_writes': 0, 'japanese_applied_total': 2403,
               'phase6_remaining': 774, 'phase6_remaining_ids_sha256': sha(serialize(sorted(remaining))),
               'status_counts': dict(Counter(r['technical_status'] for r in records)),
               'all_hold_family_counts': {},
               'fa_entries': 21, 'fa_segments': 180, 'fa_controls': 39,
               'fa_semantic_counts': dict(Counter(r['fa_semantic_verdict'] for r in fa)),
               'phrase_notes': 12, 'name_buffer_entries': 10, 'scope_gap_entries': 14,
               'official_name_entries': 2, 'pcs_errors': 0, 'control_errors': 0, 'kanji': 0,
               'source_control_counts': dict(source_control_counts),
               'normal_spacing0_max_static': max(r['width_status']['normal_spacing0']['max_total'] for r in records),
               'normal_spacing1_max_static_diagnostic': max(r['width_status']['normal_spacing1_diagnostic']['max_static_with_spacing'] for r in records),
               'spacing1_candidate_208_exceedances': [r['batch_index'] for r in records if r['width_status']['spacing1_diagnostic_over_208']],
               'relocation_candidates': [r['batch_index'] for r in records if r['pointer_status']['relocation_needed']],
               'exact_raw_extra_hit_entries': [r['batch_index'] for r in records if r['pointer_status']['missing']],
               'interior_raw_candidate_entries': sum(bool(r['pointer_status']['interior_hits']) for r in records),
               'interior_raw_candidate_count': sum(len(r['pointer_status']['interior_hits']) for r in records),
               'runtime_qa_count': len(QA_INDICES), 'runtime_qa_performed': False}
    summary['all_hold_family_counts'] = dict(Counter(f for r in records for f in sorted({h.split(':')[0] for h in r['all_holds']})))
    binary = {'status': 'NO_ROM_GENERATED_SAFE_SUBSET_EMPTY', 'baseline_rom': BASE_ROM,
              'baseline_sha256_before': BASE_SHA, 'baseline_sha256_after': BASE_SHA,
              'output_rom': None, 'output_sha256': None,
              'classified_changed_bytes': {'in_place_text': 0, 'relocated_text': 0, 'pointer_writes': 0},
              'changed_offsets': [], 'unexpected_byte_count': 0,
              'comparison_scope': 'Baseline before/after entire-file hash; no nonexistent output ROM comparison claimed',
              'prior_applied_byte_verification': prior_applied, 'prior_2403_changed': 0,
              'runtime_font_graphics_ASM_changes': 0, 'phase6_remaining': 774}
    validation = {'phase': '7C-3', 'status': 'AUDIT_COMPLETE_ALL_HELD_NO_ROM',
                  'summary': summary, 'input_accounting': accounting,
                  'step2_before_audit_pytest': {'passed': 610, 'subtests_passed': 16,
                                             'note': 'Observed prerequisite run; not a prediction of later regression results'},
                  'input_hashes': previous, 'protected909': {'files': 909, 'aggregate_sha256': INITIAL_SNAPSHOT},
                  'allowlist_management_audit': management,
                  'renderer_evidence': anchors, 'controlfix': fix_result, 'strict_dry_run': dry,
                  'official_lexical_and_table_evidence': name_evidence,
                  'binary_audit': binary, 'existing_translation_changes': 0,
                  'glossary_changes': 0, 'existing_safety_gate_changes': 0,
                  'rom_created': False, 'batch02_to16_processed': False, 'commit': False, 'push': False}
    return {'holds': {'metadata': summary, 'entries': records}, 'validation': validation,
            'binary': binary, 'qa': make_runtime_qa(records, handoff)}


def regression_checks():
    result = {}
    commands = {'pytest': [sys.executable, '-X', 'utf8', '-m', 'pytest', '-q'],
                'py_compile': [sys.executable, '-X', 'utf8', '-m', 'py_compile',
                    'scripts/build_ja_phase7_story_batch01.py', 'tests/test_ja_phase7_story_batch01.py',
                    'scripts/build_ja_phase6_cleanup_batch03.py', 'tests/test_ja_phase6_cleanup_batch03.py',
                    'tests/test_ja_phase6_cleanup_batch04.py'],
                'git_diff_check': ['git', 'diff', '--check']}
    for name, cmd in commands.items():
        print('Verifying '+name, flush=True)
        p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding='utf-8')
        assert p.returncode == 0, p.stdout+p.stderr
        row = {'state': 'PASS', 'returncode': 0, 'command': cmd[1:]}
        if name == 'pytest':
            m = re.search(r'(\d+) passed(?:, (\d+) subtests passed)?', p.stdout)
            assert m, p.stdout
            row.update(passed=int(m[1]), subtests_passed=int(m[2] or 0))
        result[name] = row
    return result


def document(data):
    v, records = data['validation'], data['holds']['entries']
    s = v['summary']
    lines = ['# Phase 7C-3: Story Priority Batch 01 Technical Integration', '',
        '独立監査完了。53件すべて技術保留、適用0件。新ROMは生成していない。Claude confirmed53は変更しない。', '',
        '## テスト修復・保護', '',
        '失敗原因はPhase 7C-2のレビュー3成果物が既存909-file snapshotの後工程allowlistに未登録だったこと。',
        'scripts/build_ja_phase6_cleanup_batch03.py の完全一致パス集合と対応するBatch03/04テストだけを更新。',
        f'909件・期待aggregate `{INITIAL_SNAPSHOT}` は不変。validator本体/期待hash/skip/xfailは変更なし。',
        '許可から1件を除く負例、許可外ファイルを追加する負例はFAILを確認する回帰テストを追加。',
        '独立監査前に全pytest 610 PASS + 16 subtests。最終回帰は下記。', '',
        '## 件数', '', '```json', json.dumps(s, ensure_ascii=False, indent=2), '```', '',
        '## ROMから確認した描画経路と未証明点', '',
        '53 ownerの命令はすべて`0F 00 <text pointer> 09 06`。callstd handler ROM0006A180/GBA0806A180が',
        'ROM00160450/GBA08160450のstd tableを使用し、slot6 owner ROM00160468/GBA08160468は',
        'ROM01E7D5DA/GBA09E7D5DAへ向く。bytes `8a 67 00 00 00 00 66 6d 6c 03 03`。',
        'message opcode67のtable owner ROM0015FB50/GBA0815FB50 → ROM00A093AC/GBA08A093AC。',
        'そのhandlerがliteral ROM00A093F8の0806943Dを呼び、ROM000694C8/GBA080694C8で',
        'ROM00008FCC/GBA08008FCCのplaceholder展開、ROM000F6D5C/GBA080F6D5Cのprinter setupへ進む。',
        'ROM000F6D78がfont selector ROM000CBE00/GBA080CBE00を呼ぶ。これは',
        'ROM000CBE04の089C9EE1によるhookで、ROM009C9EE0/GBA089C9EE0がRAM状態から分岐する。',
        'setupはfont4/5/2へ分岐。ROM000F6CD0/GBA080F6CD0のprinter templateにはx=0,y=1,letterSpacing=1。',
        'ROM00002CF4/GBA08002CF4がtemplateをprinterへコピーする。これらは局所コード証拠であり全rootのlive状態証明ではない。',
        'field候補template ROM003A73BC/GBA083A73BCは26×4 tiles=208pxだが、各rootのnative opcode8A/別window初期化・',
        'override・font4/5 metricsの全variantを証明できていない。208px/240pxやscript分類による一律承認は禁止。', '',
        '幅table: Latin ROM001FB100/GBA081FB100、Japanese normal ROM0020F500/GBA0820F500(280 bytes)をROMで再照合。',
        f'既存width calculatorでnormal/spacing0静的最大{s["normal_spacing0_max_static"]}px。',
        f'しかしROMで観測したspacing1をnormal fontに条件付き適用すると最大{s["normal_spacing1_max_static_diagnostic"]}px。',
        f'候補208超indices={s["spacing1_candidate_208_exceedances"]}。実font4/5のoverflow確定とは区別する。',
        'FDを幅0の本文として合格にせず、動的幅はUNKNOWN。英語最大行幅を超える既存FA gateも変更しない。', '',
        '## FA・意味監査', '',
        'ROMの終端境界から21件180 segments/FA39を再取得。FE/FBもwait区間へ反映し、Claude phase_viewを承認には使わない。',
        '意味監査は全文/全FA区間で実施。#19 mustの確度、#40 most importantの欠落、#49 no known methodsの断定化を',
        'CLAUDE_REVIEW_REQUIREDにした。#1/16/24/41/47の語気差は台帳の個別noteに記録。訳文は一文字も修正していない。',
        '#1のdark force完成形、#31/#40のLight of Ruin完成形の先行はFA_SEMANTIC_BOUNDARY_REVIEW_REQUIRED。',
        '#31原文P3→日本語P2、#40原文P2→日本語P1。英語のLight ofが先に見える点も検討したが、',
        '完成形の早期開示と同等であること、驚き/伏線への影響は証明できない。FAを動かして救済しない。', '',
        '|index|ID|FA注記の独立判定|根拠|', '|---:|---|---|---|']
    for i in PHRASE_INDICES:
        r = records[i]
        lines.append(f'|{i}|{r["id"]}|{r["fa_semantic_verdict"]}|{r["fa_independent_note"]}|')
    lines += ['', '注記なし9件も同じ基準で全wait区間を比較。重要名詞・述語は概ね維持（#49の本文断定化は別保留）。', '',
        '## 名前buffer・用語', '',
        'FD01はfield展開ROM00009004/GBA08009004→ROM000091E0/GBA080091E0のdispatch。',
        'table ROM00231E70/GBA08231E70、FD01 owner ROM00231E74/GBA08231E74→ROM00009120/GBA08009120。',
        'producerはRAM0300500Cのrecord pointerを返し、展開器は再帰copyする。renderer側のFD skipとは別。',
        '名前keyboard ROM003E22D0/GBA083E22D0、player template ROM003E245C/GBA083E245Cは7文字上限。',
        '既存rom_naming_profilesのnormal Latin条件付き最大42px。writer→保存recordの全経路/外部値/',
        '各fontの最悪幅は未証明、10件ともbuffer保留。controlfixは[latin][player][japanese]を入れるが、',
        '任意buffer内のFCを含む値までpage安全とする証明ではない。FE/FA/FBのhandlersは言語flagをresetしない。', '',
        'scope警告14件: 台帳にはexact ID、英語語句、候補、glossaryのcategory/entry IDs/scope、',
        '独立証拠を記録。全14件、既存使用歴だけでは新scope承認にしない。',
        '#19 Rift Caveはevent map bindingで地名と確認できるが、さけめのどうくつの正式project承認なし。',
        '#32 Prison Bottleは原文literalと既存どうぐ名の一致だけ。該当会話をitem番号へ結ぶoperand証明なし、entity保留。', '',
        '## Pointer・容量・dry-run・controlfix', '',
        '#21 scr_1F46217: ROM01F46217/GBA09F46217、owner ROM01E82C9B/GBA09E82C9B。',
        '元slot19 bytes、日本語23 bytes（FC15/16と終端を含む）。whole-ROM exact/interior scanは台帳に記録。',
        '唯一のoversized候補。live renderer未承認なので実際の割当・pointer writeは0。',
        '#21のexact ownerは記録と一致、interior raw hit0。53件全体では29件にinterior候補、#50に追加exact raw hit。',
        'それらは実ownerと確定したものではない。圧縮/画像等の偶然一致を除く構造証明はUNKNOWNで、保守的にpointer保留。',
        'vetted FFの残量はinjectorのempty planに記録されるが、#21にdestinationは選んでいない。',
        'controlfix --no-wrapを53件の診断入力に2回。FA layout未承認flagはfalseのまま、21件が正しく拒否される。',
        '32 non-FAは既存page処理とnewlineのescape表記化のみ、candidateのencoded bytes変更0。',
        '結果は2回byte-identical、control mismatch0。これはFA21注入承認ではない。',
        '既存2403件はcontrolfix入力へ渡していない。',
        'strict incremental dry-runは本物のinjectorにsafe subset0件を渡した診断。encode/pointer/truncation/',
        'runtime/graphics patch等0を既存assert_strict_mapで確認。ただし53件のcapacity/注入承認と誤記しない。', '',
        '## Binary audit・ROM', '',
        f'基準ROM SHA-256 `{BASE_SHA}` が作業前後不変。2403件のpayloadとrecorded ownerも基準ROMで再照合。',
        '新ROMなし、新ROMhash=null。in-place/relocated/pointer writes各0、changed offsetなし。',
        'これは基準ROMの不変監査であり、存在しない新ROMとの差分PASSを捏造しない。Phase6残774件のID集合も不変。', '',
        '## 全53件', '', '|index|ID|slot / encoded|normal0 / conditional1 px|primary|secondary|', '|---:|---|---|---|---|---|']
    for r in records:
        w, p = r['width_status'], r['pointer_status']
        lines.append(f'|{r["batch_index"]}|{r["id"]}|{p["slot_size"]} / {p["encoded_length"]}|'
                     f'{w["normal_spacing0"]["max_total"]} / {w["normal_spacing1_diagnostic"]["max_static_with_spacing"]}|'
                     f'{r["primary_hold"]}|{"; ".join(r["secondary_holds"])}|')
    lines += ['', '## Runtime QAと次の作業', '',
        'QA fixtureは23件。序章/初期候補→FA→Rift Caveのbuffer/#21→Shadow Baseの#31/#40/長文の順。',
        '静的map/event条件は記載したが、具体的save flag・実到達ルートはUNKNOWN。今回mGBA実行なし。',
        'まず基準ROMでwindow0/font/X/Y/spacingとfont selectorのRAM値を観測し、保存name writerを追う。',
        '次に#1/#31/#40のwait境界と#19/#40/#49の本文をClaude再レビュー。scope/名称entityの承認を別途取得。',
        '全gateが揃った時だけ別の承認済みintegrationとしてsafe subsetをcontrolfix/injectする。Batch02以降には進まない。', '',
        '## 再現・最終回帰', '',
        '`python scripts/build_ja_phase7_story_batch01.py --analyze` は監査のみ。`--write` は全pytest等のPASS後に',
        '新規5成果物をexclusive-createする。既存出力があれば上書きせず停止。既存ROMを書く処理はない。', '',
        '```json', json.dumps(v.get('regressions', {}), ensure_ascii=False, indent=2), '```', '',
        '作成: このreport、holds/validation/binary audit JSON、runtime QA fixture、再現script、test。',
        '変更: Batch03 allowlist管理scriptとBatch03/04対応testのみ。glossary/既訳/injector/controlfix/font/renderer/FA validator不変。',
        'docs-sync skillの方針に従い詳細は本専用reportへ集約し、README/AGENTSは変更していない。', '']
    return '\n'.join(lines).encode('utf-8')


def persist_new(data):
    assert not any((ROOT/p).exists() for p in OUTPUTS), 'Existing Phase 7C-3 output; no overwrite'
    assert set(OUTPUTS) <= PHASE7C3_PATHS
    payloads = {OUTPUTS[0]: document(data), OUTPUTS[1]: serialize(data['holds']),
                OUTPUTS[2]: serialize(data['validation']), OUTPUTS[3]: serialize(data['binary']),
                OUTPUTS[4]: serialize(data['qa'])}
    # Preflight every exact path before the first write.
    for path in payloads:
        assert not (ROOT/path).exists(), path
    for path, payload in payloads.items():
        with (ROOT/path).open('xb') as f:
            f.write(payload)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument('--analyze', action='store_true')
    mode.add_argument('--write', action='store_true')
    args = p.parse_args()
    if args.write:
        assert not any((ROOT/path).exists() for path in OUTPUTS), 'Outputs exist; refusing overwrite'
    print('Auditing immutable Batch01 and protected inputs', flush=True)
    data = analyze()
    if args.write:
        data['validation']['regressions'] = regression_checks()
        persist_new(data)
        protected_snapshot()
    print(json.dumps(data['validation']['summary'], ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
