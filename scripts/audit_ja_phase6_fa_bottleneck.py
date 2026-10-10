#!/usr/bin/env python3
"""Phase 6C-4F investigation only; never calls controlfix/inject/build.

Reads existing audit decisions. Creates three new research JSON artifacts;
existing paths must be absent or byte-identical. No approval is granted.
Run: python scripts/audit_ja_phase6_fa_bottleneck.py
Capstone is used solely to record local ROM instructions, not as a runtime dependency.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lib.fa_control import join_segments, parse_raw_segments
from lib.pcs_text import Charmap, decode_pcs
from lib.translation_tokens import strip_hma_quotes

OUT = ROOT / 'out/phase6'
EXPECTED_ROM_SHA = '192b43b79f75174d9fd5618c47276d2a21cf47ec58b2a902becbe872b19a0284'
PROTECTED_SNAPSHOT = 'ea8f4deae2c3462b50816e33913f3a03a5186f9d723b510e6a84274306db5ab7'
OUTPUT_NAMES = ('ja_phase6_fa_bottleneck', 'ja_phase6_fa_claude_resegment_handoff',
                'ja_phase6_fa_runtime_qa_plan', 'ja-phase6-fa-bottleneck-investigation')
CLASSES = {'A': 'STATIC_SAFE_CANDIDATE', 'B': 'CLAUDE_RESEGMENT_REQUIRED',
           'C': 'RUNTIME_VERIFICATION_REQUIRED', 'D': 'BLOCKED_BY_CONTEXT'}
SPECIAL = {44: 'scr_1F09154', 63: 'scr_1F0A436', 137: 'scr_1F1330A',
           81: 'scr_1F0C34F', 82: 'scr_1F0C3AF', 83: 'scr_1F0C40F'}
SPECIAL_FINDINGS = {
    'scr_1F09154': 'Science Society/cloned move only across FE within the same pre-FA view. Not a byte/control mismatch. Copy assertion remains after FA. 209px exceeds the candidate field physical span, and Science Society scope is unresolved. Claude must fit the width and confirm terminology; do not remove overflow gate.',
    'scr_1F0A436': 'Flower Paradise and Honey Gather regroup across FE, not FA. The blue/flowers continuation retains two FA waits. Japanese とくせいが / みつあつめも has an awkward predicate; refer to Claude. 208px static leaves no room if live X/padding is nonzero; English envelope is not a physical limit.',
    'scr_1F1330A': 'ぜつめつの / きき continues a noun phrase across FA. Growing back moves before the wait; contractual obligation is completed after the second FA rather than before it. Full meaning is retained in the draft, but checkpoint/rhetorical timing needs review, not automatic rejection by lexical identity.',
    'scr_1F0C34F': 'Frontier Brain moves across FE; Single Battle moves before FA, trophy assertion after FA. Structurally matched; natural Japanese modifier-before-noun, but the reveal timing differs. Claude checkpoint review, then visual check. Raw interior hits remain unclassified risk signals.',
    'scr_1F0C3AF': 'Frontier Brain moves across FE; Double Battle moves before FA, trophy assertion after FA. Structurally matched; natural Japanese modifier-before-noun, but the reveal timing differs. Claude checkpoint review, then visual check. Raw interior hits remain unclassified risk signals.',
    'scr_1F0C40F': 'Frontier Brain moves across FE; Multi Battle moves before FA, trophy assertion after FA. Natural Japanese modifier-before-noun; no additional raw interior hit in prior audit. Different reveal timing needs Claude checkpoint review, not necessarily rewriting.',
}
# Additional manual observations. No text is changed and no machine semantic
# equivalence is claimed for other rows whose old semantic state says PASS.
EXTRA_REVIEW = {
    'scr_1F078CB': 'Old semantic_audit PASS is absence of a manual note, not proof. English defeating precedes FA, Japanese たおした follows FA. Natural relative-clause ordering may justify it, but request explicit checkpoint review.',
    'scr_1F07BC4': 'もらって ほしい / にがした バタフリーの かわりに is a postposed qualifier over FA. Not inherently unsafe, but unnatural ordering/read timing deserves Claude review.',
    'scr_1F07EC2': 'Controlled and oppression clauses are reordered around FA; あっぱくの / やつらの きかい is awkward. Old semantic PASS is not a comprehensive linguistic check.',
}
# FE-only movement is not classified as an FA timing violation. Remaining
# width/ownership/name gates still stand.
FE_ONLY = {'scr_1F09045', 'scr_1F130DC', 'scr_1F0B2DB'}
CONTEXT_NAMES = {'scr_1F0B2DB', 'scr_1F0BE99', 'scr_1F0C46E', 'scr_1F0C52E'}


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def protected_snapshot():
    paths = set((ROOT / 'rom').rglob('*')) | set((ROOT / 'out').rglob('*')) | set((ROOT / 'glossaries').rglob('*'))
    paths |= {ROOT / x for x in subprocess.check_output(
        ['git', 'ls-files', '--cached', '--others', '--exclude-standard'], cwd=ROOT, text=True).splitlines()}
    hashes = {p.relative_to(ROOT).as_posix(): sha(p) for p in sorted(paths)
              if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc'
              and not any(name in p.name for name in OUTPUT_NAMES)}
    return {'files': len(hashes), 'aggregate_sha256': hashlib.sha256(
        json.dumps(hashes, sort_keys=True).encode()).hexdigest(), 'hashes': hashes}


def printer_evidence(source, baseline):
    from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB
    disasm = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
    blocks = {
        'state_dispatch': (0x5790, 0x57AA), 'byte_read_dispatch': (0x5840, 0x585C),
        'FE': (0x5880, 0x58A2), 'FA_FB_dispatch': (0x5B22, 0x5B34),
        'FB_wait_clear': (0x5C6C, 0x5C98), 'FA_wait_scroll_start': (0x5C98, 0x5CCC),
        'scroll_step1': (0x5CD0, 0x5D02), 'scroll_step2': (0x5D0C, 0x5D44),
        'language_flags': (0x5B10, 0x5B22), 'FD_skip_argument': (0x58A8, 0x58AC),
        'FD_skip_shared_tail': (0x5B0A, 0x5B10), 'glyph_read_and_copy': (0x5BE2, 0x5C22),
        'glyph_advance_no_wrap': (0x5C28, 0x5C40), 'glyph_advance_tail': (0x5C44, 0x5C54),
        'wait_hook': (0x5634, 0x5638), 'unbound_wait': (0xA0F1CC, 0xA0F210),
        'unbound_extra_wait_conditions': (0xA0F190, 0xA0F1B8),
        'auto_wait_counter': (0x5608, 0x5628), 'auto_wait_done': (0x562C, 0x5634),
        'down_arrow_clear': (0x55D4, 0x5606), 'scroll_window_header': (0x44A8, 0x453E),
        'scroll_window_copy_fill': (0x4548, 0x457C), 'field_window_init': (0x6FB22, 0x6FB34),
    }
    assert source[0x5B22:0x5B2A] == bytes.fromhex('02 20 00 e0 03 20 30 77')
    assert int.from_bytes(source[0x5638:0x563C], 'little') == 0x08A0F1CD
    state_targets = [int.from_bytes(source[0x57B0 + 4*i:0x57B4 + 4*i], 'little') for i in range(7)]
    special_targets = {f'{c:02X}': f'0x{int.from_bytes(source[0x5860+4*(c-0xF8):0x5864+4*(c-0xF8)], "little"):08X}' for c in (0xFA, 0xFB, 0xFE)}
    assert special_targets == {'FA': '0x08005B26', 'FB': '0x08005B22', 'FE': '0x08005880'}
    assert int.from_bytes(source[0x58C8:0x58CC], 'little') == 0x080058CC
    language_targets = {f'FC {c:02X}': f'0x{int.from_bytes(source[0x58CC+4*(c-1):0x58D0+4*(c-1)], "little"):08X}' for c in (0x15, 0x16)}
    assert language_targets == {'FC 15': '0x08005B10', 'FC 16': '0x08005B18'}
    rows = []
    for name, (start, end) in blocks.items():
        assert source[start:end] == baseline[start:end], name
        rows.append({'name': name, 'rom_start': f'0x{start:08X}', 'rom_end_exclusive': f'0x{end:08X}',
                     'gba_start': f'0x{start+0x08000000:08X}', 'bytes': source[start:end].hex(' '),
                     'baseline_identical': True, 'instructions': [
                         f'0x{i.address:08X}: {i.mnemonic} {i.op_str}'
                         for i in disasm.disasm(source[start:end], start+0x08000000)]})
    return {'state_targets_gba': [f'0x{x:08X}' for x in state_targets],
            'special_targets_gba': special_targets, 'language_targets_gba': language_targets,
            'wait_hook_literal': '0x08A0F1CD (Thumb, code 0x08A0F1CC)', 'blocks': rows,
            'proved': ['FA stores state 3; byte pointer already advanced past control',
                       'state 3 calls hooked wait; on success clears arrow, sets distance=font[fontId].maxHeight+lineSpacing, restores X, state 4',
                       'state 4 moves window pixels upward with speed-table steps and background fill; distance exhausted -> state 0',
                       'FA does not reset Y or write Japanese/color fields; FB resets X/Y after wait and pixel fill',
                       'FE resets X and increments Y by font maximum height plus lineSpacing without input wait',
                       'FC15/16 write printer+0x21 Japanese flag; next ordinary glyph decompress call reads this flag',
                       'ordinary glyph advance adds width (plus letterSpacing in Japanese); inspected path has no edge-triggered implicit wrapping',
                       'FD low-bank renderer skips argument, not field buffer expansion; pre-render expansion must be proved separately'],
            'unproved': ['all per-entry live callers, X/padding/font/spacing/viewport variants',
                         'transitive auto/R-held wait flag semantics and every timing option',
                         'field placeholder expansion writers/copies, embedded FC controls and worst-case values',
                         'battle high-bank FD handlers complete transitive outputs and width bounds']}


def causes(row, batch):
    result = []
    def add(value):
        if value not in result:
            result.append(value)
    old = row['all_holds']
    if row['review_status'] != 'confirmed':
        add('UNKNOWN_BUFFER')
        add('TRANSLATION_SEGMENT_INCOMPLETE')
    if any('overflow' in x and 'width' not in x for x in old) or 'field_208px_overflow' in old:
        add('LINE_WIDTH_OVERFLOW')
    semantic = row.get('semantic_voice_state', {})
    if semantic.get('boundary_note') or row['id'] in EXTRA_REVIEW:
        add('SEMANTIC_BOUNDARY_AMBIGUITY')
    if semantic.get('voice_note'):
        add('OTHER')
    for value in old:
        if value in ('control_boundary_or_token_placement_changed', 'scroll_or_page_sequence_changed'):
            add('CONTROL_BOUNDARY_MISMATCH')
        elif 'owner' in value:
            add('POINTER_OWNER_INCOMPLETE')
        elif 'glossary' in value:
            add('GLOSSARY_UNRESOLVED')
        elif 'official' in value:
            add('OFFICIAL_NAME_UNVERIFIED')
        elif 'dynamic' in value or 'buffer_contract' in value:
            add('DYNAMIC_WIDTH_UNVERIFIED')
    # All candidates still need exact caller geometry / checkpoint approval.
    add('FA_LAYOUT_UNVERIFIED')
    return result


def disposition(row, batch):
    key, old = row['id'], row['all_holds']
    if row['review_status'] != 'confirmed' or key in CONTEXT_NAMES:
        return 'D'
    if batch == 1:
        return 'C'
    if 'field_208px_overflow' in old or key in EXTRA_REVIEW or row.get('semantic_voice_state', {}).get('voice_note'):
        return 'B'
    if row.get('semantic_voice_state', {}).get('boundary_note') and key not in FE_ONLY:
        return 'B'
    if any('owner' in x or 'dynamic' in x or 'unmodelled' in x for x in old):
        return 'C'
    return 'A'


def record(row, batch, source, baseline, selection):
    key = row['id']
    selected = selection[key]
    start, slot = selected['rom_offset'], row['source_slot']
    decoded = decode_pcs(source, start, slot)
    raw = source[start:start+decoded.byte_length]
    assert decoded.terminated and decoded.text == strip_hma_quotes(row['original_english']), key
    segments = parse_raw_segments(raw, rom_offset=start)
    assert any(x['after_control'] == 'FA' for x in segments), key
    assert join_segments(segments) == decoded.text
    width = row['width_state']
    fixed = row['controlfixed_japanese']
    if fixed:
        payload = Charmap('ja').encode(fixed)
        assert len(payload) == row['encoded_bytes'], key
        decoded_target = decode_pcs(payload).text
        encoded_check = {'bytes': len(payload), 'hex': payload.hex(' '), 'encode': 'PASS',
                         'roundtrip': Charmap('ja').encode(decoded_target) == payload,
                         'literal_text_identical': decoded_target == fixed,
                         'canonical_space_note': 'Japanese byte 00 decodes to U+3000; ASCII-space alias is byte-equivalent.',
                         'note': 'Full-string page-aware codec; never decode Japanese segments with a reset Latin state.'}
        assert encoded_check['roundtrip'], key
    else:
        encoded_check = {'encode': 'NOT_EVALUATED_NO_COMPLETED_TRANSLATION'}
    classification = disposition(row, batch)
    all_causes = causes(row, batch)
    if classification == 'D' and row['review_status'] == 'confirmed':
        all_causes = [x for x in ('OFFICIAL_NAME_UNVERIFIED', 'GLOSSARY_UNRESOLVED') if x in all_causes] + [x for x in all_causes if x not in ('OFFICIAL_NAME_UNVERIFIED', 'GLOSSARY_UNRESOLVED')]
    owners = row['pointer_state']['recorded']
    owner_bytes = []
    for owner in owners:
        pos = int(owner, 16)
        actual = baseline[pos:pos+4]
        if row['decision'] == 'HOLD':
            assert actual == source[pos:pos+4] == (start+0x08000000).to_bytes(4, 'little'), key
        owner_bytes.append({'rom': owner, 'gba': f'0x{pos+0x08000000:08X}', 'baseline_bytes': actual.hex(' ')})
    if row['decision'] == 'HOLD':
        assert baseline[start:start+slot] == source[start:start+slot], key
    units = row['FA_state']['translated_segments']
    assert not units or len(units) == len(segments), key
    context = row['source_handoff'].get('preserved_metadata', row['source_handoff'].get('context', {}))
    return {'id': key, 'batch': batch, 'review_index': row.get('review_index'),
            'review_status': row['review_status'], 'prior_decision': row['decision'],
            'translation_complete': row['review_status'] == 'confirmed' and bool(units),
            'classification': classification, 'classification_name': CLASSES[classification],
            'approved_for_injection': False, 'primary_hold': all_causes[0], 'secondary_holds': all_causes[1:],
            'prior_primary_hold': row['primary_hold'], 'prior_secondary_holds': row['secondary_holds'],
            'prior_all_holds': row['all_holds'], 'original': row['original_english'],
            'japanese': row['candidate_japanese'], 'previous_candidate_not_approved': row['review'].get('previous_candidate'),
            'segments': [{'index': i, 'english': s['text'], 'japanese': units[i] if units else None,
                          'after_control': s['after_control'], 'rom_control_offset': s['control_offset']} for i, s in enumerate(segments)],
            'raw_source_hex': raw.hex(' '), 'rom_offset': f'0x{start:08X}', 'gba_address': f'0x{start+0x08000000:08X}',
            'source_slot': slot, 'source_encoded_bytes': len(raw), 'planned_placement': row['planned_placement'],
            'PCS': encoded_check, 'control_audit': row['control_state'],
            'buffer_audit': row['buffer_state'], 'buffer_tokens': row['review'].get('buffers', row['buffer_state'].get('review_metadata', [])),
            'pointer_audit': row['pointer_state'], 'pointer_owner_bytes': owner_bytes,
            'width_audit': width, 'physical_limit_policy': {
                'renderer_candidate': 'battle_message' if batch == 1 else width.get('profile', {}).get('profile_id', 'field_candidate_not_measured'),
                'physical_template_span': 224 if batch == 1 else 208,
                'known_battle_origin_x': 2 if batch == 1 else None,
                'proved_entry_usable_width': 222 if batch == 1 else None,
                'entry_live_path_proved': False,
                'field_warning': '208 is a candidate template span, not universally approved usable width. Recorded 209/210 static overflows remain blocking unless a different actual renderer is proved.',
                'dynamic_maximum': None, 'implicit_wrap_allowed': False,
                'Japanese_letter_spacing': 'Glyph widths alone assume spacing 0; live spacing not proved for each field caller.'},
            'semantic_audit_prior': row.get('semantic_voice_state'), 'glossary_audit': row['glossary_state'],
            'official_name_audit': row['official_name_state'], 'runtime_context': context,
            'investigation_note': SPECIAL_FINDINGS.get(key, EXTRA_REVIEW.get(key,
                'FE-only lexical regrouping is not by itself an FA timing violation; other gates remain.' if key in FE_ONLY else
                'Candidate classification is a next-evidence task, not a fit approval. Prior semantic PASS is not exhaustive review.')),
            'next_action': {'A': 'Prove caller X/font/spacing/padding and semantic checkpoints; replace English envelope gate only in a separately authorized phase.',
                            'B': 'Claude checkpoint/grammar review; fit any real overflow while retaining protected controls. Rewriting not always required.',
                            'C': 'Trace live renderer/expansion and classify raw pointer hits; then mGBA. Visual PASS alone does not resolve ownership.',
                            'D': 'Resolve writer/value types or proper-name/map identity/scope before requesting translation approval.'}[classification]}


def qa_plan(records, applied):
    lookup = {x['id']: x for x in records+applied}
    chosen = [('scr_1F0D935', 1, 'simple_FE_FA_applied'), ('scr_1F126CE', 2, 'FE_FB_FA_applied'),
              ('scr_1F0BE99', 3, 'three_or_more_scroll_lines_icons'),
              ('scr_1F0CAF5', 4, 'player_name_expansion'),
              ('tbl_battle_messages_00122_3FC048', 4, 'battle_dynamic'),
              ('scr_1F0B7A3', 4, 'unknown_buffer_values'),
              ('scr_1F0C40F', 5, 'trophy_word_order'), ('scr_1F1330A', 5, 'predicate_timing')]
    cases = []
    for key, priority, condition in chosen:
        row = lookup[key]
        cases.append({'id': key, 'priority': priority, 'condition': condition, 'performed': False,
                      'baseline_appearance': 'Japanese' if row['prior_decision'] == 'APPLY' else 'English; held Japanese is NOT in this ROM',
                      'map': 'UNKNOWN', 'event_route': 'UNKNOWN', 'event_evidence': row['runtime_context'],
                      'pointer_owners': row['pointer_owner_bytes'], 'original': row['original'], 'japanese_reference_only': row['japanese'],
                      'segments': row['segments'], 'controls': [s['after_control'] for s in row['segments'] if s['after_control']],
                      'procedure': ['Use unchanged baseline ROM, native 240x160 captures; preserve current save and create a separate QA save.',
                                    'Locate the recorded pointer-owned event using a matching save/runtime script trace; route/map UNKNOWN until observed.',
                                    'Record printer at FA: currentChar, windowId, fontId, x/y/currentX/currentY, line/letterSpacing, state, Japanese flag.',
                                    'Capture before wait, each scroll step and first/last glyph of next row; one input per checkpoint, then test auto/held-input options separately.',
                                    'At FB verify clearing and X/Y reset; at FE verify no added input wait. Check color and Japanese/Latin state after each transition.',
                                    'For dynamics log full expanded bytes before RenderText, every writer and long accepted values; do not replace UNKNOWN buffers by guessed values.',
                                    'Held candidates can only be checked in English now. Japanese screen testing needs a separately authorized future focused build after blockers resolve.'],
                      'expected': 'FA: one rendered-line upward scroll, next row at same printer Y and initial X; original event/control order; no clipping or page/color loss.',
                      'NG': ['Missing/extra waits', 'FA clears the entire page', 'blank/lost/overprinted row', 'clipped last glyph',
                             'placeholder has wrong glyph page', 'unexpected plot reveal/predicate timing', 'unresolved writer or pointer ownership'],
                      'pass_conditions': ['Bind observed screen to this exact pointer/caller, not matching prose alone.',
                                          'All frames, waits, widths and dynamic values match the recorded trace.',
                                          'Separate geometry/control PASS from semantic reviewer approval; unresolved context remains HOLD.'],
                      'Japanese_runtime_status': 'NOT_RUN' if row['prior_decision'] == 'APPLY' else 'BLOCKED_NO_APPROVED_JAPANESE_BUILD'})
    return {'metadata': {'phase': '6C-4F', 'rom': 'out/unbound-ja-phase6-cleanup-batch02.gba',
                         'sha256': EXPECTED_ROM_SHA, 'performed': False, 'count': len(cases),
                         'no_inferred_maps_or_routes': True}, 'entries': cases}


def main():
    paths = [OUT / 'ja_phase6_fa_bottleneck_inventory.json', OUT / 'ja_phase6_fa_claude_resegment_handoff.json',
             ROOT / 'tests/fixtures/ja_phase6_fa_runtime_qa_plan.json']
    presence = {p.relative_to(ROOT).as_posix(): p.exists() for p in paths}
    before = protected_snapshot()
    assert before['aggregate_sha256'] == PROTECTED_SNAPSHOT, 'Protected inputs differ from initial 4F snapshot; stop and investigate.'
    baseline_path = ROOT / 'out/unbound-ja-phase6-cleanup-batch02.gba'
    assert sha(baseline_path) == EXPECTED_ROM_SHA
    source, baseline = (ROOT / 'rom/unbound.gba').read_bytes(), baseline_path.read_bytes()
    assert hashlib.md5(source).hexdigest() == '9cad8e771940e7f7094d13911552cef0'
    selection = {x['id']: x for x in read(ROOT / 'tests/fixtures/ja_phase6_selection.json')['entries']}
    records, applied, checks = [], [], {}
    for batch in (1, 2):
        prior = read(OUT / f'ja_phase6_cleanup_batch0{batch}_reviewed.json')['entries']
        holds = read(OUT / f'ja_phase6_cleanup_batch0{batch}_technical_holds.json')['entries']
        reviews = read(ROOT / f'tests/fixtures/ja_phase6_cleanup_batch0{batch}_claude_review.json')
        assert len({x['id'] for x in reviews}) == len(reviews)
        assert {x['id'] for x in reviews} == {x['id'] for x in prior}
        fa = [x for x in prior if x['FA_state']['present']]
        fa_holds = [x for x in fa if x['decision'] == 'HOLD']
        hold_ids = {x['id'] for x in holds if x['FA_state']['present']}
        assert {x['id'] for x in fa_holds} == hold_ids
        for row in fa:
            if batch == 2:
                assert reviews[row['review_index']]['id'] == row['id']
            result = record(row, batch, source, baseline, selection)
            (records if row['decision'] == 'HOLD' else applied).append(result)
        checks[str(batch)] = {'FA_total': len(fa), 'FA_holds': len(fa_holds),
                             'complete_holds': sum(x['review_status'] == 'confirmed' for x in fa_holds),
                             'context_holds': sum(x['review_status'] != 'confirmed' for x in fa_holds),
                             'applied': len(fa)-len(fa_holds), 'missing': 0, 'duplicates': 0}
    assert checks['1'] == {'FA_total': 4, 'FA_holds': 4, 'complete_holds': 3, 'context_holds': 1, 'applied': 0, 'missing': 0, 'duplicates': 0}
    assert checks['2'] == {'FA_total': 55, 'FA_holds': 53, 'complete_holds': 36, 'context_holds': 17, 'applied': 2, 'missing': 0, 'duplicates': 0}
    assert len(records) == len({x['id'] for x in records}) == 57
    for index, key in SPECIAL.items():
        assert next(x for x in records if x['id'] == key)['review_index'] == index
    counts = lambda rows: dict(sorted(Counter(x['classification'] for x in rows).items()))
    b2 = [x for x in records if x['batch'] == 2]
    metadata = {'phase': '6C-4F', 'mode': 'INVESTIGATION_ONLY', 'accounting': checks,
                'hold_ids': [x['id'] for x in records], 'duplicates': 0, 'missing': 0,
                'classification_counts': counts(records), 'batch02_classification_counts': counts(b2),
                'batch02_complete_classification_counts': counts([x for x in b2 if x['translation_complete']]),
                'batch02_context_classification_counts': counts([x for x in b2 if not x['translation_complete']]),
                'primary_cause_counts': dict(Counter(x['primary_hold'] for x in records)),
                'cause_memberships_not_unique_count': dict(Counter(c for x in records for c in [x['primary_hold']]+x['secondary_holds'])),
                'prior_batch02_hold_memberships': dict(Counter(c for x in b2 for c in x['prior_all_holds'])),
                'new_safe_confirmed': 0, 'newly_applied': 0, 'source_or_ROM_writes': 0,
                'salvage': {'near_term_unchanged_wording_candidates': sum(x['classification'] == 'A' for x in b2),
                            'additional_owner_clearance_candidates': ['scr_1F09045', 'scr_1F0CE14'],
                            'all_numbers_conditional_not_approvals': True},
                'protected_initial_901_files': {'files': before['files'], 'aggregate_sha256': before['aggregate_sha256']},
                'protected_input_hashes': before['hashes'],
                'baseline_ROM_sha256': EXPECTED_ROM_SHA, 'glossary_sha256': sha(ROOT / 'glossaries/ja.json'),
                'original_json_ROM_glossary_unchanged': True,
                'historical_batch02_validation': read(OUT / 'ja_phase6_cleanup_batch02_validation.json'),
                'special_indices_zero_based': {str(k): v for k, v in SPECIAL.items()},
                'note': 'Classification is investigation/design only. A does not satisfy the old English-envelope gate and is conditional on a separately approved evidence-based validator improvement.'}
    inventory = {'metadata': metadata, 'printer_evidence': printer_evidence(source, baseline), 'entries': records,
                 'previously_applied_FA_references': applied}
    handoff = {'metadata': {'phase': '6C-4F', 'count': sum(x['classification'] == 'B' for x in records),
                           'instructions': 'Review only these existing segments against input/scroll checkpoints. Do not translate unknown buffers, move protected controls, add pages, or infer speaker/map. Preserve reviewed source provenance. Not all timing differences require rewriting; explicitly approve natural Japanese clause continuation when justified. No review performed in 4F.'},
               'entries': [x for x in records if x['classification'] == 'B'],
               'context_prerequisites': [x for x in records if x['classification'] == 'D']}
    payloads = [inventory, handoff, qa_plan(records, applied)]
    serialized = [json.dumps(x, ensure_ascii=False, indent=2)+'\n' for x in payloads]
    assert protected_snapshot()['aggregate_sha256'] == before['aggregate_sha256']
    # Preflight every destination before any write; never overwrite.
    for path, text in zip(paths, serialized):
        if path.exists() and path.read_text(encoding='utf-8') != text:
            raise FileExistsError(f'Existing artifact differs; not overwriting: {path}')
    for path, text in zip(paths, serialized):
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open('x', encoding='utf-8', newline='\n') as stream:
                stream.write(text)
        read(path)
    assert protected_snapshot()['aggregate_sha256'] == before['aggregate_sha256']
    print(json.dumps({'accounting': checks, 'classification_counts': metadata['classification_counts'],
                      'batch02_complete': metadata['batch02_complete_classification_counts'],
                      'output_preexisting': presence, 'protected_inputs': 'UNCHANGED'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
