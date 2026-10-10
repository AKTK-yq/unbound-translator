#!/usr/bin/env python3
"""Phase 6C-4H, fail-closed integration of immutable Claude Batch 03.

No translation or validator edits. Existing files are read-only. Run with
``python scripts/build_ja_phase6_cleanup_batch03.py analyze`` then ``build``.
An existing stage is checked, never overwritten; partial stages stop the run.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import runpy
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lib.fa_control import join_segments, parse_raw_segments
from lib.pcs_text import Charmap, decode_pcs
from lib.translation_glossary import load_glossary
from lib.translation_tokens import semantic_tokens, strip_hma_quotes
from scripts import build_ja_phase6_cleanup_batch02 as previous
from scripts.build_ja_phase6_batch02 import owner_audit
from scripts.build_ja_phase6_batch06 import interior_pointer_hits
from scripts.build_ja_phase6_cleanup_batch01 import cli, digest, official_record, persist, read
from scripts.build_ja_phase6_cleanup_glossary import assert_strict_map
from scripts.build_ja_phase6_voice_integration import encoded

OUT, FIX = ROOT / 'out/phase6', ROOT / 'tests/fixtures'
PREFIX = 'ja_phase6_cleanup_batch03_'
BASE = ROOT / 'out/unbound-ja-phase6-cleanup-batch02.gba'
ROM = ROOT / 'out/unbound-ja-phase6-cleanup-batch03.gba'
REVIEW = FIX / (PREFIX + 'claude_review.json')
BATCH = OUT / (PREFIX + 'for_claude.json')
BASE_SHA = '192b43b79f75174d9fd5618c47276d2a21cf47ec58b2a902becbe872b19a0284'
REVIEW_SHA = 'b7c7b5f241776bada78cc76d48c032e9f93da9e69017f3ecf9d768b93c4ab94f'
INITIAL_SNAPSHOT = 'f932aab110e4dc228c628314c43ce5b0dc0ba89d5f15f6740da9ef6117bad4df'
PHRASE_INDICES = (2, 5, 29, 31, 40, 53, 63, 69, 98, 132)
OFFICIAL_INDICES = (40, 41, 42, 49, 56, 85, 86, 87, 91, 92, 115, 123, 124)
GAP_INDICES = (6, 12, 41, 42, 53, 56, 59, 66, 73, 79, 110, 112, 129, 132)
WIDTHS = {36: 217, 85: 210, 118: 227, 127: 225, 132: 210}
RELOCATION_INDICES = (91, 123)
VOICE_INDICES = (52, 83, 107, 117)
SUFFIXES = ('reviewed', 'technical_holds', 'safe_input', 'combined_controlfix',
            'scope_extension_proposal', 'controlfix', 'controlfix_twice',
            'controlfix_report', 'controlfix_twice_report', 'full_dry_run_map',
            'incremental_dry_run_map', 'map', 'binary_audit', 'validation')
NEW_PATHS = {f'out/phase6/{PREFIX}{s}.json' for s in SUFFIXES} | {
    'scripts/build_ja_phase6_cleanup_batch03.py', 'tests/test_ja_phase6_cleanup_batch03.py',
    'docs/ja-phase6-final-cleanup-batch03-technical.md',
    f'tests/fixtures/{PREFIX}runtime_qa.json', 'out/unbound-ja-phase6-cleanup-batch03.gba'}
# Phase 6C-4I/4J artifacts created AFTER the 909-file Batch 03 snapshot. They are
# legitimate later-stage outputs, never part of the protected 909 inputs. The list
# is exact (no wildcard/prefix): any other new or changed file still breaks the
# aggregate hash, and the 909 count/hash expectations are unchanged.
LATER_STAGE_PATHS = frozenset({
    # Batch 04 Claude review deliverables (Phase 6C-4I).
    'tests/fixtures/ja_phase6_cleanup_batch04_claude_review.json',
    'tests/fixtures/ja_phase6_cleanup_batch04_voice_audit.json',
    'docs/ja-phase6-final-cleanup-batch04-claude-review.md',
    # Batch 04 technical integration artifacts (Phase 6C-4J).
    'scripts/build_ja_phase6_cleanup_batch04.py',
    'tests/test_ja_phase6_cleanup_batch04.py',
    'docs/ja-phase6-final-cleanup-batch04-technical.md',
    'tests/fixtures/ja_phase6_cleanup_batch04_runtime_qa.json',
    'out/unbound-ja-phase6-cleanup-batch04.gba',
    'out/phase6/ja_phase6_cleanup_batch04_reviewed.json',
    'out/phase6/ja_phase6_cleanup_batch04_technical_holds.json',
    'out/phase6/ja_phase6_cleanup_batch04_safe_input.json',
    'out/phase6/ja_phase6_cleanup_batch04_combined_controlfix.json',
    'out/phase6/ja_phase6_cleanup_batch04_scope_extension_proposal.json',
    'out/phase6/ja_phase6_cleanup_batch04_controlfix.json',
    'out/phase6/ja_phase6_cleanup_batch04_controlfix_twice.json',
    'out/phase6/ja_phase6_cleanup_batch04_controlfix_report.json',
    'out/phase6/ja_phase6_cleanup_batch04_controlfix_twice_report.json',
    'out/phase6/ja_phase6_cleanup_batch04_full_dry_run_map.json',
    'out/phase6/ja_phase6_cleanup_batch04_incremental_dry_run_map.json',
    'out/phase6/ja_phase6_cleanup_batch04_map.json',
    'out/phase6/ja_phase6_cleanup_batch04_binary_audit.json',
    'out/phase6/ja_phase6_cleanup_batch04_validation.json',
})

# Manual review of THIS exact input hash. These are audit observations, not new
# wording or a reusable automated semantic validator. FE is not an input wait.
# Existing width/event validators are called unchanged in addition to this audit.
FA_ISSUES = {
    2: 'E1 stump possessed by spirits becomes Phantump is a spirit; children/spirits delayed to E3, lost woods advanced E3->E2 across FA.',
    5: 'Pumpkaboo is first named in source E2 after FA, target E1 before FA. City merge alone is FE-only, but species reveal is not.',
    29: 'Source entrance is E2 before the second FA; target entrance E3 after it. Two target waits interrupt introductory adverbs, not the same clause reveal.',
    31: 'in the tomb E8->E6 crosses FA. Final find-every-item request loses find and leaves two item objects without a predicate.',
    40: 'titan Pokemon E2 after FA->E1 before FA. Commemorate/building predicates are also regrouped; the reveal is not preserved.',
    41: 'Victory Road E2 after FA->E1 before FA; Pokemon League E5 after FA->E4 before FA.',
    42: 'Victory Road E2 after FA->E1 before FA; Pokemon League E5 after FA->E4 before FA.',
    69: 'any ol cowpoke E17 after FA->どこの だれにでも E16 before FA; the unrestricted-recipient condition is advanced.',
    109: 'Retrieving predicate in source E3 before FA is target とりかえす E5 after FA. Species and Shadows stay in their source wait phases, but that is not a complete semantic proof.',
    130: 'next Gym Badge after FA in source becomes つぎの ジムバッジ before FA in target; note-free draft still changes reveal timing.',
    132: 'Grim / Woods straddles FA; complete ぶきみなもり moves before FA. Cinder Volcano remains after FA. Only key-name checks cannot certify the whole clause.',
    135: 'tried to interfere in E3 before FA becomes ほうがい in E4 after FA; attempted interference also becomes completed interference.',
}
WORDING_ISSUES = {
    0: 'ゴーストタイプの ポケモンが / ここが has two が subjects; attachment needs Claude review.',
    24: 'at least 3 times modifies fishing, but せめて3かいは いってくれ can modify number of statements; gameplay condition ambiguous.',
    28: '3かも つって is not a faithful clear rendering of have not fished 3 times; missing い requires review, not automatic correction.',
    51: 'Granbulls for dem ta give to describes recipients for the nerds to give to; やつらに やる グランブル reverses giver/recipient and treats Granbull as gift.',
    64: 'しんしんから is not natural truly/sincerely wording; do not silently repair Claude text.',
    87: 'ずかんの ための しゅの / かんさつ する has incomplete Japanese particles; review required.',
    111: 'legacy -> いさん is ambiguous; take YOUR place as Champion loses replacement-of-player meaning. No independent voice rewrite.',
    112: 'Bagon training predicate is absent; fond of both -> どちらにも なついている changes attachment direction/agency. Review required.',
}
PHRASE_PASS = {
    53: 'Leader / Crater Town Gym regrouped only across FE within the same FB-delimited view. FE introduces no wait; fear/strength remain in their FA views.',
    63: 'Blizzard / City merged across FE, not FA. Weather cause stays after its FA, show-Pokemon request stays before the next FA.',
    98: 'Three legendary, reunion, Ruins of Void and released power remain in their respective waits. at a place called/the is recast as ばしょは before the same following FA; Ruins remains after it.',
}
VOICE_NOTES = {
    52: 'my test licenses わたし; polite request is source tell-me tone, not added sex/age. No わし/elder ending. [player] width/page still unproved.',
    83: 'Removes unsupported きみ; long-way-to-go and [player] retained. Neutral encouragement; no speaker upgrade.',
    107: 'Removes unsupported elder dialect. youngster permits わかい ひと as addressee, not speaker-age attribution; injury/fall-back/Jax clauses retained.',
    117: 'Second gratuitous きみ removed; first きみは corresponds to you-are/player recognition. Grampa Arthur is an addressee reference, not speaker identity.',
}
# Clause checkpoints make coverage explicit even for drafts held for other gates.
CHECKPOINTS = {
    6: 'bugs by desert / Borrius conclusion separated by FB', 7: 'Unova houses / pottery / relic buyer and high price',
    8: 'Science Society study fossils after FA / revival offer after FB', 12: 'Hard Stones desert / KBT wall before FA / find after FA',
    15: 'Gems stock / indifference after FA / Hard Stones exchange after FB',
    32: 'remaining treasure unknown / complete discovery after FA / sense after FA',
    33: 'important trainer / more important things before FA / to do after FA',
    34: 'hidden treasure / unknown quantity / Dowsing Machine before FA / find all after',
    35: 'centuries Egg / burial-chamber conditional / Trainer after FA',
    43: 'birthday discount / catch / buy cheaper before FA / sell less after FA',
    49: 'Leaf Badge / Lv26 obedience / cool TM last FB view; Lv icon unmodelled separately',
    54: 'foe intel / myself after FA / pressure / Vision Badge',
    56: 'Lv32 traded outsiders / Cut small trees / TM use; Lv icon and names independently held',
    57: 'Thief held item / opponent resources before FA / advantage after FA',
    58: 'development NOTE received here / Vega elsewhere after FA; no current-runtime claim',
    59: 'Groudon then Kyogre / Hoopa / Kyogre in Vivill after FA / responsibility / Guardian title',
    60: 'two captured / player / father and meteorite/Borrius; dynamic player gate remains',
    66: 'Rock Smash outside battle after FA / Lv36 / TM',
    67: 'Aerial Ace certainty / misses / wind metaphor / departure',
    70: 'congratulations / hypothetical style competition / would win after FA',
    71: 'format obstacle / showed me after FA / Fall Badge after FB',
    73: 'Lv45 / Strength / strong Pokemon paradox / TM; no type identity inferred',
    74: 'Icicle Cave larger / Pokemon burrow through wall / new cave after final FA',
    78: 'stats/capture rates / Professor not old man / unharmed / rare Pokemon / rival gift no longer needed',
    79: 'rival gift / errands / parents search / not seen for years / too big alone / refuses listen',
    80: 'guardian / does not know me after FA / strong / parents / demonstration',
    81: 'player / prior promised battle / real Trainer method after FA',
    82: 'player / prior teach ropes / real Trainer method after FA',
    88: 'Repel prevents encounters / lab / mother / player; existing dynamic gate not waived',
    89: 'package already delivered / blame Log / someone gets it / chase man before too far',
    94: 'lab recognition / imprisonment / send you / time / cannot allow pursuit',
    99: 'black clothing / heading seen / Cinder Volcano after FA; raw extra owner remains unresolved',
    100: 'suspicion confirmed after FA / Moltres target after FB; player gated',
    106: 'player follows Jax / mother errand then Gym Leader after FA',
    110: 'peace / Pokemon League after FA / champion after FB; challenge predicate was after FE before FA in English, target after FA: additional review required',
    114: 'player Cinder Volcano / Jax competent / help welcome after FA',
    116: 'sigh / light party / other allies Pokemon after FA / Shadow Warriors request',
    120: 'teamed with Jax / first THREE viable before FA / selected for battle after FA',
    124: 'quoted shadowy terror ordinary rhetoric / Moltres rights / evil after FA / stakes',
    125: 'player help defeat / stakes claim / chase Moltres after FA',
    129: 'different task / Shadows lack sealing object / Route9 friends / explain / find before Shadows',
    131: 'Staravia tired / lift back before FA / Cinder Volcano after FA / yes-no question',
    136: 'refusal / Ivory before FA / incentive euphemism after FA, timed pause retained',
    139: 'player / patience / forced hand after FA / suffer for interference after FB',
}


def protected_snapshot():
    paths = set((ROOT / 'rom').rglob('*')) | set((ROOT / 'out').rglob('*')) | set((ROOT / 'glossaries').rglob('*'))
    paths |= {ROOT / p for p in subprocess.check_output(
        ['git', 'ls-files', '--cached', '--others', '--exclude-standard'], cwd=ROOT, text=True).splitlines()}
    hashes = {p.relative_to(ROOT).as_posix(): digest(p.read_bytes()) for p in sorted(paths)
              if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc'
              and p.relative_to(ROOT).as_posix() not in NEW_PATHS | LATER_STAGE_PATHS}
    aggregate = digest(json.dumps(hashes, sort_keys=True).encode())
    assert len(hashes) == 909 and aggregate == INITIAL_SNAPSHOT, 'Existing file changed: stop, never restore automatically.'
    return {'files': len(hashes), 'aggregate_sha256': aggregate, 'hashes': hashes}


def baseline():
    rows = read(OUT / 'ja_phase6_cleanup_batch02_combined_controlfix.json')['entries']
    assert len(rows) == len({x['id'] for x in rows}) == 2357
    return rows


def validate_review(review, handoff, manifest, voice):
    ids = [x['id'] for x in review]
    assert len(ids) == len(set(ids)) == 140
    assert ids == [x['id'] for x in handoff] == manifest['batches'][2]['entry_ids']
    assert Counter(x['status'] for x in review) == {'confirmed': 112, 'needs_context': 28}
    assert Counter(x['speaker_confidence'] for x in review) == {'PROVEN': 3, 'PLAUSIBLE': 8, 'UNKNOWN': 129}
    assert Counter((x['input_resolution_class'], x['status']) for x in review) == {
        ('CLAUDE_TRANSLATION', 'confirmed'): 74, ('CLAUDE_TRANSLATION', 'needs_context'): 4,
        ('CLAUDE_CONTEXT', 'confirmed'): 38, ('CLAUDE_CONTEXT', 'needs_context'): 24}
    groups = defaultdict(list)
    voice_rows = {x['id']: x for x in voice['entry_voice_index']}
    for r, s in zip(review, handoff):
        for k in ('id', 'category', 'original', 'speaker_id', 'speaker_confidence', 'dialogue_group_id',
                  'protected_tokens', 'source_control_structure'):
            assert r[k] == s[k], (r['id'], k)
        assert r['previous_candidate'] == s['candidate'] == s['previous_japanese_candidate']
        assert r['hold_reason'] == s['current_hold_reason']
        assert r['input_resolution_class'] == s['resolution_class']
        assert r['source_controls'] == s['controls'] and r['buffers'] == s['buffers']
        assert r['unresolved_glossary_warnings'] == [v['term'] if isinstance(v, dict) else v for v in s['unresolved_glossary_warnings']]
        assert r['review_source'] == 'claude_cli' and r['batch'] == 3
        assert join_segments(previous.segments(r)) == strip_hma_quotes(r['original'])
        assert semantic_tokens(strip_hma_quotes(r['original'])) == r['protected_tokens']
        for k in ('speaker_id', 'speaker_confidence', 'voice_application', 'status', 'candidate_disposition'):
            assert r[k] == voice_rows[r['id']][k]
        if r['speaker_confidence'] == 'PROVEN':
            groups[r['speaker_id']].append(r['id'])
        if r['status'] == 'needs_context':
            assert not r['reviewed_japanese'] and not any(r['translated_segments'])
    assert dict(groups) == {x['speaker_id']: x['entry_ids_in_batch'] for x in voice['proven_speaker_groups']}
    assert len(groups) == 2 and set(groups) == {'trainer_0442', 'trainer_0444'}
    assert tuple(i for i, x in enumerate(review) if x.get('fa_phrase_boundary_notes')) == PHRASE_INDICES
    assert tuple(i for i, x in enumerate(review) if x['official_name_warnings']) == OFFICIAL_INDICES
    assert tuple(i for i, x in enumerate(review) if x['glossary_scope_warnings']) == GAP_INDICES
    fa = [x for x in review if x['fa_segmented']]
    assert len(fa) == 76 and sum(x['status'] == 'confirmed' for x in fa) == 63
    assert sum(len(x['translated_segments']) for x in fa if x['status'] == 'confirmed') == 501
    context = [x for x in review if x['status'] == 'needs_context']
    memberships = {t: [x['id'] for x in context if t in x['buffers']] for t in ('[buffer1]', '[buffer2]')}
    assert len(memberships['[buffer1]']) == 25 and len(memberships['[buffer2]']) == 3
    assert set(memberships['[buffer1]']) & set(memberships['[buffer2]']) == {ids[19]}
    assert {x['id'] for x in context} - set().union(*map(set, memberships.values())) == {ids[68]}
    return {'ids': 140, 'duplicates': 0, 'missing': 0, 'confirmed': 112, 'context_unique': 28,
            'fa_total': 76, 'fa_complete': 63, 'fa_context_hold': 13, 'fa_completed_segments': 501,
            'phrase_note_ids': {str(i): ids[i] for i in PHRASE_INDICES},
            'official_warning_ids': {str(i): ids[i] for i in OFFICIAL_INDICES},
            'scope_gap_ids': {str(i): ids[i] for i in GAP_INDICES},
            'buffer_memberships': memberships, 'sweetie_id': ids[68], 'proven_groups': dict(groups),
            'speaker_confidence': dict(Counter(x['speaker_confidence'] for x in review)),
            'original_candidate_hold_confidence_tokens_controls_preserved': True}


def page_text(row):
    text = previous.completed_text(row)
    pages = []
    # Data-only page guards, no changed spell characters, meaning or boundaries.
    for literal in ('Sankren fimbulvetr!', 'Sankren bolganone!'):
        if literal in text:
            assert literal in strip_hma_quotes(row['original']) and text.count(literal) == 1
            text = text.replace(literal, '[latin]' + literal + '[japanese]')
            pages.append(literal)
    fix = runpy.run_path(str(ROOT / '004_controlfix_translations.py'))
    return fix['ensure_japanese_page'](text)[0] if text else None, pages


def semantic_audit(index, row):
    issue = FA_ISSUES.get(index)
    if index == 110:
        issue = 'challenge in source E1 before FA becomes ちょうせん in E2 after FA; invitation action is delayed although League stays after FA.'
    wording = WORDING_ISSUES.get(index)
    return {'state': 'HOLD' if issue or wording else 'PASS', 'fa_issue': issue, 'wording_issue': wording,
            'method': 'Manual comparison of full source/target clauses and every wait view of REVIEW_SHA, independent of Claude flags. Structural equality is not semantic evidence.',
            'checkpoint': PHRASE_PASS.get(index, CHECKPOINTS.get(index, 'Full English and reviewed Japanese compared: actors, actions, quantities, polarity, modifiers and FE/FB views; no additional FA reveal issue identified.')),
            'source_and_target_units': [{'index': n, 'english': s['text'], 'japanese': t, 'after_control': s['after_control']}
                                        for n, (s, t) in enumerate(zip(previous.segments(row), row['translated_segments']))],
            'voice_note': VOICE_NOTES.get(index), 'speaker_confidence': row['speaker_confidence'],
            'voice_profile_status': row['voice_profile_status'], 'identity_or_voice_confidence_promoted': False,
            'new_wording_created': False,
            'prior_timing_revision': {'previous_candidate_available': row['previous_candidate'] is not None,
                                      'before_after_fix_claim_proved': False,
                                      'detail': 'previous_candidate is null; no pre-fix draft is provided. Current segments independently audited; report does not identify both corrected drafts.'} if index in (109, 132) else None}


def official_audit(index, row, text):
    records, issues = [], []
    for claim in row['official_names_verified']:
        match = re.fullmatch(r'(.+?)=(.+?) \(PokeAPI cache, ([\w-]+)/([\w-]+), verified_exact\)', claim)
        assert match, claim
        english, japanese, category, slug = match.groups()
        record = official_record(category, slug, english, japanese)
        # Pokédex narration may omit the full compound: do not falsify exact proof.
        assert japanese in text, (row['id'], claim)
        records.append(record)
    reasons = {
        40: 'Unbound titan category has no approved entity-specific Japanese label.',
        41: 'Same English Victory Road does not establish identity with canon location; Unbound map binding unproved.',
        42: 'Same English Victory Road does not establish identity with canon location; Unbound map binding unproved.',
        49: 'TM machine term outside verified scope; existing usage alone is not independent official Japanese proof.',
        56: 'HM exact official entity wording unverified; Cut move exact name does not verify machine label.',
        85: 'Professor Oak mention is not independent proof of canon Oak identity; no voice/profile inferred.',
        86: 'Pokédex dictionary term needs independent Japanese franchise wording evidence, not borrowed candidate usage.',
        87: 'Pokédex dictionary term needs independent wording evidence; source observing species is not species-table extraction.',
        91: 'サボ is guessed from Cacnea name, not verified cry/utterance in this scene.',
        123: 'バード is guessed from Staravia name, not verified cry/utterance in this scene.',
    }
    if index in reasons:
        issues.append(reasons[index])
    if index in (92, 115):
        literal = 'Sankren fimbulvetr!' if index == 92 else 'Sankren bolganone!'
        assert '[latin]' + literal + '[japanese]' in text
        records.append({'state': 'SOURCE_LATIN_LITERAL_RETAINED', 'literal': literal,
                        'pronunciation_or_meaning_invented': False, 'page_guard': '[latin]literal[japanese]'})
    if index == 124:
        records.append({'state': 'ORDINARY_QUOTED_RHETORIC_NOT_CANON_NAME',
                        'basis': 'Source quotes Shadowy reign of terror? Seriously? then rejects moral accusation evil. No naming/registration statement; no organization identity inferred.',
                        'warning': 'Rhetorical reading, not approval as proper-name translation or glossary extension.'})
    return {'state': 'HOLD' if issues else 'PASS', 'records': records, 'issues': issues,
            'warnings': deepcopy(row['official_name_warnings'])}


def glossary_audit(row, handoff, text, glossary):
    hits = [{'source': t.source, 'target': t.target, 'scope': t.context_scope,
             'target_present': bool(text) and t.target in text}
            for _, _, t in glossary.matches(strip_hma_quotes(row['original']), row['category'], entry_id=row['id'])]
    warnings = deepcopy(row['glossary_scope_warnings'])
    gap_records, issues = [], []
    for warning in warnings:
        source, rest = warning.split('=', 1)
        target = rest.split(' (', 1)[0]
        terms = [t for t in glossary.terms if t.source.casefold() == source.casefold()]
        # Independent evidence is existing global permission, not matching prose
        # or another entry's Japanese. No scoped term is silently promoted.
        global_terms = [t for t in terms if t.global_replace and t.target == target]
        state = 'EXISTING_GLOBAL_PERMISSION' if global_terms else 'INDEPENDENT_ENTITY_PROOF_REQUIRED'
        if not global_terms:
            issues.append(warning)
        gap_records.append({'source': source, 'target': target, 'state': state,
                            'terms': [{'source': t.source, 'target': t.target, 'scope': t.context_scope,
                                       'entry_ids': list(t.entry_ids), 'categories': list(t.categories),
                                       'global_replace': t.global_replace} for t in terms]})
    missing = [x for x in hits if not x['target_present']]
    return {'state': 'HOLD' if issues or missing else 'PASS', 'matched_scoped_terms': hits,
            'scope_warnings': warnings, 'gap_records': gap_records, 'unresolved': issues,
            'missing_targets': missing, 'approved_handoff_terms': deepcopy(handoff['approved_glossary_terms']),
            'scope_changes': 0, 'global_replace_changes': 0, 'automatic_replacements': 0}


def analyze():
    protection = protected_snapshot()
    source, base = (ROOT / 'rom/unbound.gba').read_bytes(), BASE.read_bytes()
    assert hashlib.md5(source).hexdigest() == previous.SOURCE_MD5 and digest(base) == BASE_SHA
    assert digest(REVIEW.read_bytes()) == REVIEW_SHA
    anchors = previous.renderer_evidence(source)
    assert previous.renderer_evidence(base) == anchors
    review, handoff = read(REVIEW), read(BATCH)['entries']
    validation = validate_review(review, handoff, read(FIX / 'ja_phase6_cleanup_batch_manifest.json'),
                                 read(FIX / (PREFIX + 'voice_audit.json')))
    old = baseline()
    assert not {x['id'] for x in old} & {x['id'] for x in review}
    prepared = {x['id']: x for x in read(ROOT / 'out/ja-phase5e-prepared.json')['entries']}
    selection = {x['id']: x for x in read(FIX / 'ja_phase6_selection.json')['entries']}
    chosen = [selection[x['id']] for x in review]
    owners = {x['id']: x for x in owner_audit(chosen, source)['entries']}
    interiors = interior_pointer_hits(source, chosen)
    injector, codec = runpy.run_path(str(ROOT / '005_hybrid_injector.py')), Charmap('ja')
    glossary = load_glossary(ROOT / 'glossaries/ja.json', expected_language='ja')
    assert len(glossary.terms) == 292
    records, safe = [], []
    controls_all, controls_confirmed = Counter(), Counter()
    for i, (r, s) in enumerate(zip(review, handoff)):
        key = r['id']
        entry, sel = deepcopy(prepared[key]), selection[key]
        pos, slot = int(entry['address'], 16), entry['byte_length']
        assert pos == sel['rom_offset'] and slot == sel['slot_size'] and entry['original'] == r['original']
        length = decode_pcs(source, pos, slot).byte_length
        raw = source[pos:pos + length]
        source_segments = parse_raw_segments(raw, rom_offset=pos)
        assert join_segments(source_segments) == strip_hma_quotes(r['original'])
        assert [(x['text'], x['after_control']) for x in source_segments] == [(x['text'], x['after_control']) for x in previous.segments(r)]
        # Recount controls from ROM with parsed argument widths, never glyph bytes.
        counts = Counter()
        for control in previous.raw_controls(raw):
            b = control.split()
            counts[b[0].upper()] += 1
            if b[0] == 'fc':
                counts['FC_' + b[1].upper()] += 1
        assert dict(counts) == r['source_controls'], (key, counts, r['source_controls'])
        controls_all.update(counts)
        if r['status'] == 'confirmed':
            controls_confirmed.update(counts)
        assert source[pos:pos + slot] == base[pos:pos + slot]
        assert sorted(int(p, 16) for p in entry.get('pointer_sources', [])) == sorted(int(p, 16) for p in sel['pointer_owners'])
        for p in entry.get('pointer_sources', []):
            p = int(p, 16)
            assert source[p:p + 4] == base[p:p + 4] == (pos + 0x08000000).to_bytes(4, 'little')
        text = previous.completed_text(r)
        fixed, latin_guards = page_text(r)
        holds = ['review_needs_context'] if not text else []
        controls = previous.control_audit(r, text, fixed, raw) if text else {'state': 'NOT_COMPLETED'}
        semantic = semantic_audit(i, r) if text else {'state': 'NOT_COMPLETED'}
        profile = previous.caller_profile(r, owners[key], source)
        width = previous.width_audit(r, fixed, raw, profile) if text else {'state': 'NOT_MEASURED', 'problems': []}
        official = official_audit(i, r, fixed) if text else {'state': 'NOT_COMPLETED', 'records': [], 'issues': []}
        terms = glossary_audit(r, s, text, glossary)
        buffer = {'state': 'NOT_REQUIRED' if not r['buffers'] else 'UNKNOWN_CONTRACT',
                  'tokens': deepcopy(r['buffers']), 'writer': 'UNKNOWN', 'caller': profile,
                  'type': 'player/rival name' if r['buffers'] and set(r['buffers']) <= {'[player]', '[rival]'} else 'UNKNOWN',
                  'all_values': 'UNKNOWN', 'maximum_width': 'UNKNOWN', 'expansion_page_contract': 'UNKNOWN',
                  'handoff_evidence': deepcopy(s['buffer_metadata'])}
        if r['buffers']:
            holds.append('dynamic_buffer_contract_unproved')
        if text:
            assert not previous.HAN.search(text)
            if controls['state'] != 'PASS':
                holds.append('control_boundary_or_token_placement_changed')
            if semantic['fa_issue']:
                holds.append('FA_SEMANTIC_REVIEW_REQUIRED')
            if semantic['wording_issue']:
                holds.append('CLAUDE_WORDING_REVIEW_REQUIRED')
            if official['state'] != 'PASS':
                holds.append('official_or_project_name_unverified')
            if terms['state'] != 'PASS':
                holds.append('glossary_scope_or_target_unapproved')
            holds.extend(width['problems'])
            if profile['profile_id'] == 'unproved_consumer':
                holds.append('renderer_consumer_unproved')
            if any('bufferstring' in k for k in owners[key]['owner_kinds']):
                holds.append('bufferstring_consumer_width_and_page_unproved')
        payload = encoded(injector, codec, entry, fixed) if text else None
        size = len(payload) if payload else None
        relocate = size is not None and size > slot
        pointer = {**owners[key], 'interior_hits': interiors[key], 'fixed': sel['fixed'],
                   'no_relocation': sel['no_relocation'], 'relocation_needed': relocate,
                   'consumer_proven_for_extra_hits': not owners[key]['missing'],
                   'source_rom_offset': f'0x{pos:08X}', 'source_gba_address': f'0x{pos + 0x08000000:08X}'}
        if text and (pointer['missing'] or pointer['stale'] or interiors[key]):
            holds.append('owner_incomplete_or_interior')
        if relocate and (sel['fixed'] or sel['no_relocation']):
            holds.append('fixed_or_no_relocation_overflow')
        if relocate and (not entry.get('is_pointer_based') or not entry.get('pointer_sources')):
            holds.append('relocation_owner_absent')
        if i == 99:
            assert pointer['missing'] == ['0x009FF6C2'] and not pointer['interior_hits']
            pointer['extra_hit_bytes'] = source[0x9FF6B2:0x9FF6D6].hex(' ')
            pointer['extra_hit_status'] = 'UNCLASSIFIED_UNALIGNED_DATA; no proven consumer. Do not label an accidental match a real pointer.'
        record = {'id': key, 'review_index': i, 'review_status': r['status'], 'review': deepcopy(r),
                  'source_handoff': deepcopy(s), 'original_english': r['original'], 'candidate_japanese': text,
                  'decision': 'HOLD' if holds else 'APPLY', 'primary_hold': holds[0] if holds else None,
                  'secondary_holds': holds[1:], 'all_holds': holds, 'buffer_state': buffer,
                  'FA_state': {'present': r['fa_segmented'], 'layout_status': 'NOT_APPLICABLE' if not r['fa_segmented'] else 'LAYOUT_PASS' if not holds else 'LAYOUT_HOLD',
                               'completed_segments': bool(text) and r['fa_segmented'], 'source_segments': source_segments,
                               'translated_segments': deepcopy(r['translated_segments']), 'phrase_note': i in PHRASE_INDICES},
                  'control_state': controls, 'semantic_voice_state': semantic, 'width_state': width,
                  'official_name_state': official, 'glossary_state': terms, 'pointer_state': pointer,
                  'source_slot': slot, 'source_encoded_bytes': length, 'encoded_bytes': size,
                  'controlfixed_japanese': fixed, 'latin_literal_guards': latin_guards,
                  'planned_placement': 'relocated' if relocate else 'in_place',
                  'next_action': 'Resolve named evidence gaps. Return semantic/wording drafts to Claude; no automatic rewrite.' if holds else 'Inspect exact original caller in mGBA and all wait frames; not yet runtime tested.'}
        records.append(record)
        if not holds:
            entry['translated'] = fixed
            if r['fa_segmented']:
                entry.update(control_segments=deepcopy(source_segments), translated_segments=deepcopy(r['translated_segments']),
                             source_boundary_sequence=controls['source_boundaries'], controls=deepcopy(r['source_controls']),
                             fa_placement_policy='require_segments', fa_layout_reviewed=True, fa_placement_status='RESOLVED_SEGMENTED')
            safe.append(entry)
    # Claude counted only outer language guards. Existing controlfix also adds
    # guards around [player], so #118 becomes 32 bytes against a 30-byte slot.
    # Keep the reported TWO candidates and the actual THREE distinct; all held.
    actual_relocations = [x['review_index'] for x in records if x['pointer_state']['relocation_needed']]
    assert actual_relocations == [91, 118, 123]
    assert {x['review_index']: x['width_state']['max_total'] for x in records
            if x['width_state'].get('max_total', 0) > 208} == {i: p for i, p in WIDTHS.items() if i != 118}
    assert records[118]['width_state']['max_total'] == 173
    assert records[118]['width_state']['unknown_placeholder_codes'] == ['0x01']
    # Its 227px claim includes a guessed 54px name. 173+54 is a diagnostic
    # illustration, NOT an approved bound; do not inject a guessed width.
    validation.update(reported_width_warnings={str(i): p for i, p in WIDTHS.items()}, reported_relocation_indices=list(RELOCATION_INDICES),
                      actual_relocation_indices=actual_relocations,
                      width_118={'static_pixels': 173, 'claude_diagnostic_name_pixels': 54,
                                 'claude_estimate': 227, 'proven_dynamic_bound': None,
                                 'actual_encoded_bytes': 32, 'slot': 30, 'decision': 'HOLD'})
    assert {k: controls_confirmed[k] for k in ('FE', 'FA', 'FB')} == {'FE': 240, 'FA': 105, 'FB': 204}
    validation.update(all_rom_controls=dict(controls_all), confirmed_rom_controls=dict(controls_confirmed))
    return {'validation': validation, 'renderer_evidence': anchors, 'baseline_sha256': BASE_SHA,
            'baseline_applied': 2357, 'applied': len(safe), 'held': 140 - len(safe),
            'japanese_applied_total': 2357 + len(safe), 'phase6_remaining_holds': 820 - len(safe),
            'fa_applied': sum(x['decision'] == 'APPLY' and x['FA_state']['present'] for x in records),
            'protected_inputs': protection, 'new_wording': 0, 'validator_edits': 0,
            'kanji': 0, 'encode_errors': 0}, records, safe


def assert_safe_record(r):
    assert r['decision'] == 'APPLY' and r['review_status'] == 'confirmed' and not r['all_holds']
    assert r['control_state']['state'] == r['semantic_voice_state']['state'] == 'PASS'
    assert r['buffer_state']['state'] == 'NOT_REQUIRED'
    assert r['official_name_state']['state'] == r['glossary_state']['state'] == 'PASS'
    assert not r['width_state']['problems'] and r['width_state']['max_total'] <= 208
    if r['FA_state']['present']:
        assert r['FA_state']['layout_status'] == 'LAYOUT_PASS'
        assert r['width_state']['max_total'] <= max(r['width_state']['source_line_pixels'])
    p = r['pointer_state']
    assert not p['missing'] and not p['stale'] and not p['interior_hits']
    assert r['encoded_bytes'] <= r['source_slot'] or (p['recorded'] and not p['fixed'] and not p['no_relocation'])


def save_analysis(metadata, records, safe):
    for r in records:
        if r['decision'] == 'APPLY':
            assert_safe_record(r)
    persist(OUT / (PREFIX + 'reviewed.json'), {'metadata': metadata, 'entries': records})
    persist(OUT / (PREFIX + 'technical_holds.json'), {'metadata': {'count': len(records) - len(safe)},
                                                   'entries': [r for r in records if r['decision'] == 'HOLD']})
    persist(OUT / (PREFIX + 'safe_input.json'), {'entries': safe})
    persist(OUT / (PREFIX + 'combined_controlfix.json'), {'entries': baseline() + safe})
    persist(OUT / (PREFIX + 'scope_extension_proposal.json'), {
        'glossary_changed': False, 'proposal_only': True,
        'entries': [{'id': r['id'], 'index': r['review_index'], 'gaps': r['glossary_state']['gap_records'],
                     'next_action': 'Prove exact entity and approve explicit script IDs; no broad category/global substitution.'}
                    for r in records if r['review']['glossary_scope_warnings']]})


def build(safe):
    inp, fixed, twice = [OUT / (PREFIX + n) for n in ('safe_input.json', 'controlfix.json', 'controlfix_twice.json')]
    for src, dst, rep in ((inp, fixed, OUT / (PREFIX + 'controlfix_report.json')),
                          (fixed, twice, OUT / (PREFIX + 'controlfix_twice_report.json'))):
        cli('004_controlfix_translations.py', [src, '-o', dst, '--source', ROOT / 'out/ja-phase5e-prepared.json',
                                              '--report', rep, '--target-lang', 'ja', '--no-wrap'], [dst, rep])
        assert read(dst)['entries'] == safe, 'Controlfix changed reviewed text or boundary'
        stats = read(rep)['stats']
        assert stats['remaining_control_mismatches'] == stats['fa_placement_review_required'] == 0
    assert fixed.read_bytes() == twice.read_bytes()
    full = OUT / (PREFIX + 'full_dry_run_map.json')
    cli('005_hybrid_injector.py', [ROOT / 'rom/unbound.gba', OUT / (PREFIX + 'combined_controlfix.json'),
                                 '-o', ROM, '--target-lang', 'ja', '--dry-run', '--fail-on-no-space', '--map-output', full], [full])
    assert_strict_map(read(full), read(full), 2357 + len(safe))
    dry, built = [OUT / (PREFIX + n) for n in ('incremental_dry_run_map.json', 'map.json')]
    args = [BASE, fixed, '-o', ROM, '--target-lang', 'ja', '--fail-on-no-space']
    cli('005_hybrid_injector.py', [*args, '--dry-run', '--map-output', dry], [dry])
    assert_strict_map(read(dry), read(dry), len(safe))
    cli('005_hybrid_injector.py', [*args, '--map-output', built], [ROM, built])
    assert_strict_map(read(dry), read(built), len(safe))


def audit_binary(before, after, safe, mapping, old):
    assert len(before) == len(after) == 0x2000000 and digest(before) == BASE_SHA
    injector, codec = runpy.run_path(str(ROOT / '005_hybrid_injector.py')), Charmap('ja')
    moves = {x['id']: x for x in mapping['relocations']}
    allowed = {k: set() for k in ('in_place_text', 'relocated_text', 'pointer_writes')}
    for e in safe:
        pos, slot = int(e['address'], 16), e['byte_length']
        payload = encoded(injector, codec, e, e['translated'])
        if e['id'] in moves:
            move = moves[e['id']]
            dest = int(move['new_offset'], 16)
            from lib.unbound_free_space import VETTED_FREE_SPACE_RANGES
            assert move['storage'] == 'vetted_ff' and move['byte_length'] == len(payload)
            assert any(a <= dest and dest + len(payload) <= b for a, b in VETTED_FREE_SPACE_RANGES)
            assert not any(dest < b and a < dest + len(payload) for a, b in injector['FREE_SPACE_EXCLUDE_RANGES'])
            assert before[dest:dest + len(payload)] == b'\xff' * len(payload)
            assert after[dest:dest + len(payload)] == payload and before[pos:pos + slot] == after[pos:pos + slot]
            allowed['relocated_text'].update(range(dest, dest + len(payload)))
            assert sorted(move['pointer_sources']) == sorted(e['pointer_sources'])
            for p in e['pointer_sources']:
                p = int(p, 16)
                assert before[p:p + 4] == (pos + 0x08000000).to_bytes(4, 'little')
                assert after[p:p + 4] == (dest + 0x08000000).to_bytes(4, 'little')
                allowed['pointer_writes'].update(range(p, p + 4))
            assert after.find((pos + 0x08000000).to_bytes(4, 'little')) == -1
        else:
            assert len(payload) <= slot and after[pos:pos + slot] == payload.ljust(slot, b'\xff')
            allowed['in_place_text'].update(range(pos, pos + slot))
    old_moves = {}
    for name in ('ja_phase6_batch04_map.json', 'ja_phase6_batch05_incremental_map.json',
                 'ja_phase6_batch06_incremental_map.json', 'ja_phase6_cleanup_incremental_map.json',
                 'ja_phase6_cleanup_glossary_incremental_map.json', 'ja_phase6_cleanup_batch01_map.json',
                 'ja_phase6_cleanup_batch02_map.json'):
        old_moves.update({x['id']: x for x in read(OUT / name)['relocations']})
    protected = set()
    for e in old:
        move = old_moves.get(e['id'])
        pos = int(move['new_offset'], 16) if move else int(e['address'], 16)
        size = move['byte_length'] if move else e['byte_length']
        payload = encoded(injector, codec, e, e['translated'])
        assert before[pos:pos + len(payload)] == payload, ('Baseline payload mismatch', e['id'])
        assert before[pos:pos + size] == after[pos:pos + size], e['id']
        protected.update(range(pos, pos + size))
        for p in e.get('pointer_sources', []):
            p = int(p, 16)
            assert before[p:p + 4] == after[p:p + 4], e['id']
            protected.update(range(p, p + 4))
    union = set().union(*allowed.values())
    assert len(union) == sum(map(len, allowed.values())) and not protected & union
    changed = {i for i, (a, b) in enumerate(zip(before, after)) if a != b}
    assert not changed - union and not changed & protected, 'Unexpected binary diff'
    voice = {k: next(e for e in old if e['id'] == k)['translated'] for k in ('scr_1F02145', 'scr_740753', 'scr_1F06A82')}
    assert 'scr_1F02029' not in {e['id'] for e in safe}
    # Daniel is an older applied draft, not an entry in this batch; all prior
    # payloads above prove that its previous wording remains unchanged.
    return {'status': 'PASS', 'existing_2357_payload_storage_and_pointers_unchanged': True,
            'voice_three_preserved': voice, 'Daniel_not_newly_applied': True,
            'changed_byte_count': len(changed), 'unexpected_byte_count': 0,
            'classified_changed_bytes': {k: len(v & changed) for k, v in allowed.items()},
            'classified_changed_ranges': {k: previous.ranges(v & changed) for k, v in allowed.items()},
            'all_changed_ranges': previous.ranges(changed),
            'in_place_count': mapping['stats']['in_place'], 'relocation_count': len(moves),
            'pointer_writes': mapping['stats']['pointer_writes'], 'output_sha256': digest(after),
            'baseline_sha256': digest(before), 'runtime_font_graphics_ASM_changes': 0}


def runtime_qa(records):
    selected = [x for x in records if x['decision'] == 'APPLY'][:6]
    indices = [*PHRASE_INDICES, *VOICE_INDICES, 91, 123, 99, 36, 109]
    for i in indices:
        if records[i] not in selected:
            selected.append(records[i])
    selected = selected[:25]
    assert 15 <= len(selected) <= 25
    return {'metadata': {'count': len(selected), 'performed': False, 'rom': str(ROM.relative_to(ROOT)),
                          'map_event_unknown_is_not_reachability_proof': True},
            'entries': [{'id': x['id'], 'index': x['review_index'], 'decision': x['decision'],
                         'original': x['original_english'], 'japanese': x['candidate_japanese'],
                         'rom_offset': x['pointer_state']['source_rom_offset'], 'gba_address': x['pointer_state']['source_gba_address'],
                         'pointer_owners': x['pointer_state']['recorded'],
                         'speaker_evidence': deepcopy(x['source_handoff']['speaker_evidence']),
                         'map': 'UNKNOWN', 'event': 'UNKNOWN', 'runtime_reachability': 'UNKNOWN_NOT_PLAYED',
                         'procedure': 'Use recorded caller/actor evidence to locate exact event. Do not infer map from text proximity. Compare every source FE/FA/FB view, scroll line, color, pause and next English dialogue. HOLD entries must remain baseline text.',
                         'checks': ['original wait timing', 'scroll after FA', 'Latin/Japanese page recovery', 'no implicit wrap', 'neutral source-backed voice'],
                         'all_holds': x['all_holds']} for x in selected]}


def validate_outputs(metadata, safe):
    """Run regressions and create only the new final validation artifact."""
    mapping = read(OUT / (PREFIX + 'map.json'))
    audit = audit_binary(BASE.read_bytes(), ROM.read_bytes(), safe, mapping, baseline())
    assert audit == read(OUT / (PREFIX + 'binary_audit.json'))
    outcomes = {}
    for name, args in (
        ('focused_pytest', [sys.executable, '-X', 'utf8', '-m', 'pytest', 'tests/test_ja_phase6_cleanup_batch03.py', '-q']),
        ('pytest', [sys.executable, '-X', 'utf8', '-m', 'pytest', '-q']),
        ('py_compile', [sys.executable, '-X', 'utf8', '-m', 'py_compile',
                        'scripts/build_ja_phase6_cleanup_batch03.py', 'tests/test_ja_phase6_cleanup_batch03.py']),
        ('git_diff_check', ['git', 'diff', '--check']),
    ):
        print('Validating ' + name, flush=True)
        result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, encoding='utf-8')
        assert result.returncode == 0, result.stdout + result.stderr
        record = {'state': 'PASS', 'returncode': result.returncode, 'command': args}
        if 'pytest' in name:
            match = re.search(r'(\d+) passed(?:, (\d+) subtests passed)?', result.stdout)
            assert match, result.stdout
            record.update(passed=int(match[1]), subtests_passed=int(match[2] or 0))
        outcomes[name] = record
    proof = protected_snapshot()
    dry = read(OUT / (PREFIX + 'incremental_dry_run_map.json'))
    assert_strict_map(dry, mapping, len(safe))
    full = read(OUT / (PREFIX + 'full_dry_run_map.json'))
    assert_strict_map(full, full, 2357 + len(safe))
    first, twice = [OUT / (PREFIX + n) for n in ('controlfix.json', 'controlfix_twice.json')]
    assert first.read_bytes() == twice.read_bytes()
    validation = {
        'phase': '6C-4H', 'status': 'PASS_STATIC_TECHNICAL_INTEGRATION_RUNTIME_NOT_PLAYED',
        **outcomes, 'input_accounting': metadata['validation'],
        'applied': len(safe), 'held': 140 - len(safe), 'japanese_applied_total': 2357 + len(safe),
        'phase6_remaining_holds': 820 - len(safe), 'incremental_dry_run_stats': dry['stats'],
        'full_dry_run_stats': full['stats'], 'binary_audit': audit,
        'controlfix_byte_idempotent': True, 'controlfix_sha256': digest(first.read_bytes()),
        'runtime_qa_count': read(FIX / (PREFIX + 'runtime_qa.json'))['metadata']['count'],
        'protected_inputs': {'files': proof['files'], 'aggregate_sha256': proof['aggregate_sha256']},
        'existing_file_changes': 0, 'existing_validator_changes': 0, 'glossary_changes': 0,
        'commit': False, 'push': False, 'batch04_started': False,
        'git_status': subprocess.check_output(['git', 'status', '--short'], cwd=ROOT, text=True),
    }
    persist(OUT / (PREFIX + 'validation.json'), validation)
    print(json.dumps({k: validation[k] for k in ('status', 'applied', 'held', 'pytest', 'focused_pytest')}, indent=2))


def main():
    stage = sys.argv[1:]
    assert stage in (['analyze'], ['build'], ['validate']), 'Usage: build_ja_phase6_cleanup_batch03.py analyze|build|validate'
    metadata, records, safe = analyze()
    save_analysis(metadata, records, safe)
    if stage == ['build']:
        assert safe, 'No approved safe subset; do not create a translated ROM'
        build(safe)
        mapping = read(OUT / (PREFIX + 'map.json'))
        audit = audit_binary(BASE.read_bytes(), ROM.read_bytes(), safe, mapping, baseline())
        persist(OUT / (PREFIX + 'binary_audit.json'), audit)
        persist(FIX / (PREFIX + 'runtime_qa.json'), runtime_qa(records))
    if stage == ['validate']:
        validate_outputs(metadata, safe)
    protected_snapshot()
    print(json.dumps({'applied': len(safe), 'held': len(records) - len(safe), 'fa_applied': metadata['fa_applied'],
                      'total': metadata['japanese_applied_total'], 'remaining': metadata['phase6_remaining_holds'],
                      'primary_holds': dict(Counter(x['primary_hold'] for x in records if x['primary_hold']))}, indent=2))


if __name__ == '__main__':
    main()
