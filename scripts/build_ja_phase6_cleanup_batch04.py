#!/usr/bin/env python3
"""Phase 6C-4J, fail-closed technical integration of immutable Claude Batch 04.

No translation, glossary, validator or past-batch edits. Existing artifacts are
verified, never overwritten; a partial stage stops the run. Usage from the root::

    python scripts/build_ja_phase6_cleanup_batch04.py analyze   # audit + write review/hold/safe artifacts
    python scripts/build_ja_phase6_cleanup_batch04.py build     # controlfix x2, dry-runs, ROM, binary audit
    python scripts/build_ja_phase6_cleanup_batch04.py validate  # regression + final validation JSON
    python scripts/build_ja_phase6_cleanup_batch04.py explore   # print mechanical gates only, writes nothing
"""
from __future__ import annotations

from collections import Counter
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
from lib.fa_control import join_segments, parse_raw_segments, reconstruct_reviewed_segments
from lib.pcs_text import Charmap, decode_pcs
from lib.renderer_profiles import normal_line_widths_with_placeholders
from lib.translation_glossary import load_glossary
from lib.translation_tokens import semantic_tokens, strip_hma_quotes
from scripts import build_ja_phase6_cleanup_batch02 as previous
from scripts import build_ja_phase6_cleanup_batch03 as b3
from scripts.build_ja_phase6_batch02 import owner_audit
from scripts.build_ja_phase6_batch06 import interior_pointer_hits
from scripts.build_ja_phase6_cleanup_batch01 import cli, digest, official_record, persist, read
from scripts.build_ja_phase6_cleanup_glossary import assert_strict_map
from scripts.build_ja_phase6_voice_integration import encoded

OUT, FIX = ROOT / 'out/phase6', ROOT / 'tests/fixtures'
PREFIX = 'ja_phase6_cleanup_batch04_'
BASE = ROOT / 'out/unbound-ja-phase6-cleanup-batch03.gba'
ROM = ROOT / 'out/unbound-ja-phase6-cleanup-batch04.gba'
REVIEW = FIX / (PREFIX + 'claude_review.json')
VOICE = FIX / (PREFIX + 'voice_audit.json')
BATCH = OUT / (PREFIX + 'for_claude.json')
MANIFEST = FIX / 'ja_phase6_cleanup_batch_manifest.json'
# Hashes pinned from the files as they existed before any 4J write.
BASE_SHA = '546f18a50e0ab0eadb9ed0eb53d5773c2cf5aefae1028cc8e8a631379292cc62'
REVIEW_SHA = '31219a4ec2a9dc8e5a5eb017ef93418984bf626373dcb34fb0d2ceb5c2f33d5b'
HANDOFF_SHA = 'c5a2d951abb06a5918b6eba63a10af0139f62f825052dd7bb66db13005a449a1'
VOICE_SHA = '6b09c5de29fe3ffe0c35e72583ea604522366fff20803917bea89067afb55452'
PRIOR_ARTIFACTS_SHA = 'ac2f7b5b1a9754d4bfe1d231533e91b2e6130044d0670c8c18d8f73c930eb1e6'
BASELINE_APPLIED = 2383
PHASE6_REMAINING_BEFORE = 794
PRIOR_ARTIFACT_PATTERNS = (
    'out/phase6/ja_phase6_cleanup_batch0[123]_*', 'tests/fixtures/ja_phase6_cleanup_batch0[123]_*',
    'docs/ja-phase6-final-cleanup-batch0[123]-*', 'out/unbound-ja-phase6-cleanup-batch0[123].gba',
    'out/unbound-ja-phase6-cleanup-batch01.gba')
LATIN_STRIP = re.compile('\\[[a-z0-9_]+\\]|\\\\(?:CC[0-9A-Fa-f]{4}|btn[0-9A-Fa-f]{2}|qo|qc|Lv|[A-Za-z.])')
PAUSE_OR_SPACE = re.compile(r'\\CC[0-9A-Fa-f]{4}|\\\.|\s+')
PLAYER_CODE, RIVAL_CODE = 0x01, 0x06  # FD codes of [player] / [rival] (checked by encode below)

# Review indices are zero-based positions in the 140-entry review list (not batch_position).
EXPECTED = {'confirmed': 129, 'needs_context': 10, 'needs_technical_fit': 1}
CONTEXT_HOLDS = (0, 2, 3, 17, 26, 40, 41, 61, 92, 115)
BUFFER_CONTEXT_HOLDS = (0, 2, 3, 26, 40, 41, 61, 115)
TECHNICAL_HOLD = 60
PHRASE_INDICES = (58, 70, 100)
OFFICIAL_INDICES = (10, 11, 24, 37, 38, 39, 109)
RELOCATION_INDICES = (4, 10, 139)
VOICE_INDICES = (16, 20, 49, 57, 72)
RAID_INDICES = tuple(range(118, 137))
SUFFIXES = ('reviewed', 'technical_holds', 'safe_input', 'combined_controlfix',
            'scope_extension_proposal', 'controlfix', 'controlfix_twice',
            'controlfix_report', 'controlfix_twice_report', 'full_dry_run_map',
            'incremental_dry_run_map', 'map', 'binary_audit', 'validation')
NEW_PATHS = {f'out/phase6/{PREFIX}{s}.json' for s in SUFFIXES} | {
    'scripts/build_ja_phase6_cleanup_batch04.py', 'tests/test_ja_phase6_cleanup_batch04.py',
    'docs/ja-phase6-final-cleanup-batch04-technical.md',
    f'tests/fixtures/{PREFIX}runtime_qa.json', 'out/unbound-ja-phase6-cleanup-batch04.gba'}
OUTPUT_PATHS = [ROOT / p for p in sorted(NEW_PATHS) if not p.startswith(('scripts/', 'tests/test_'))]

# ---------------------------------------------------------------------------
# Manual audit tables (filled from a full side-by-side reading of every entry).
# These record observations about THIS exact input hash. They create no wording.
# ---------------------------------------------------------------------------
# Wait phase n = number of FA/FB boundaries before a segment (FE is NOT an input wait).
# Rubric (same as the Batch 03 precedent): HOLD when a key noun/proper term (M1) or the
# information-bearing main predicate (M2) is revealed in a different wait phase than in the
# English. Moved modality/negation/adverbials/subordinate clauses (M3) are recorded as notes.
# P<n> below is the wait phase; EN = source, JA = reviewed Japanese.
FA_ISSUES = {
    1: "EN P1 'there was a boy with you' (predicate 'was with you') reaches JA only in P2 (いっしょだったそうだな); 'operation' EN P2 -> JA P1 (さくせん); 'historian' EN P4 -> JA P3 and 'grandson' EN P3 -> JA P4.",
    5: "Threat predicate 'I'm going to do' EN P3 -> JA P5 (あわせる); 'hideout' EN P5 -> JA P3 (アジトで).",
    6: "'learn' EN P1 -> JA P2 (おぼえなさい); 'effective' EN P1 -> JA P2 (こうかが ある); 'follow through' EN P2 -> JA P1 (じっこう).",
    7: "'some kid' EN P2 -> JA P1 (こども あつかい); the prohibition 'can't pretend ... treat me' becomes しないで only in P2.",
    19: "Main predicate 'I'd be swimming' EN P0 -> JA P1 (およいで いた); 'right about now' EN P1 -> JA P0 (いまごろ).",
    21: "'put up (a barrier)' EN P8 -> JA P9 (はったんだ); only the object 'invisible barrier' is shown in P8.",
    24: "'HM moves' EN P3 -> JA P2 (ひでんわざを); 'can take ya' EN P4 -> JA P5 (いける).",
    27: "Main predicate 'I got a deep-tissue massage' EN P0 -> JA P1 (あるんだ); 'later today' EN P1 -> JA P0 (このあと).",
    34: "'unbinding' EN P6 -> JA P5 (ふういんを とく ぎしき); 'needed/gotten' split swapped across P5/P6; 'steal back' EN P12 -> JA P13 (とりもどそう).",
    35: "'you'll need it' EN P2 -> JA P3 (ひつようだからな).",
    43: "'you can never know' EN P2 -> JA P3 (わからない); 'flying' EN P3 -> JA P2 (とんで くる).",
    45: "'people and Pokémon' EN P3 -> JA P2; main predicate 'continued to inflict' EN P2 -> JA P3 (つづけた).",
    46: "Main predicate 'outweighs' EN P2 -> JA P4 (うわまわって いる); 'good ... thought' EN P2/P3 -> JA P2/P3 reordered.",
    47: "'would have been restricted to' EN P1 -> JA P3 (かぎって いたはずだ); 'hurt' EN P3 -> JA P2 (きずつかない).",
    48: "'better get used to' EN P2 -> JA P3 (なれる ことだ).",
    50: "Key term 'Cube Space' EN P2 -> JA P0 (ここが キューブスペースの): revealed two waits earlier.",
    55: "'giving back' EN P4 -> JA P5 (かえして おいたよ); 'lost because of them' EN P5 -> JA P4.",
    58: "'broke' EN P3 -> JA P4 (やぶった); 'with her' EN P4 -> JA P3; 'consider ourselves' EN P9 and 'fortunate' EN P10 are swapped in JA (うんが よかったと P9 / おもうべきだ P10); 'creating' EN P11 -> JA P12. The phrase note claims a within-phase regroup, but E15-E18 are separated by FA.",
    63: "Key noun 'old adage' EN P2 -> JA P1 (あの ことわざは ほんとうだ); 'I suppose' EN P1 -> JA P2.",
    69: "'the magma' EN P3 -> JA P2 (マグマの した); 'controlling' EN P1 -> JA P3 (あやつる).",
    70: "Name 'Shadow / Warriors' is split EN P4/P5, but whole シャドウせんし is shown in JA P4; 'there are only so many' EN P3 -> JA P5 (かぎられる). The Frozen / Heights regroup (E9/E10) stays inside one FE phase and is valid.",
    74: "'they'd already done it' EN P0 -> JA P1 (すんで いた); 'by the time I got there' EN P1 -> JA P0 (ついた ころには).",
    76: "'pose an even larger threat' EN P2 -> JA P3 (きょういだ); 'than I suspected' EN P3 -> JA P2; 'abominations' EN P7 -> JA P6 (いまわしい すがた); 'turn into' EN P6 -> JA P7.",
    78: "'hold off on your act of vengeance' EN P2 -> JA P3 (まって くれ); 'over' EN P3 -> JA P2 (おさまる まで).",
    80: "'I'll be waiting for' EN P0 -> JA P1 (まってる).",
    83: "'spent way too long' EN P2 -> JA P3 (いすぎたよ); 'inside here' EN P3 -> JA P2 (ここには).",
    87: "'figure out' EN P1 -> JA P2; 'spotted' EN P2 -> JA P1; 'block' EN P3 -> JA P4 (ふさげれば); 'their view' EN P4 -> JA P3.",
    88: "'is lending you' EN P0 -> JA P1 (かして くれる).",
    89: "'hope' EN P2 -> JA P3 (いのる だけだ).",
    93: "'seal (the dark force) away' EN P0 -> JA P1 (ふういん できる).",
    95: "Key noun 'the weapon' EN P2 -> JA P1 (へいきへの とうごう).",
    97: "Key term 'fire the Weapon' EN P2 -> JA P3 (へいきを うって); 'be done with it' EN P3 -> JA P2 (おしまい).",
    100: "Subject 'his Pokémon' EN P4 (E8) -> JA P5 (おうの ポケモンは). The phrase note says the regroup stays in one wait, but E8 and E9 are separated by FA, so the subject reveal moves across a wait.",
    102: "Key place 'Cinder Volcano' EN P2 -> JA P1 (シンダーかざんの); 'cavern' EN P1 -> JA P2.",
    103: "Key noun 'scapegoat' EN P3 -> JA P2 (みがわりに); the 'left you as' clause is completed one wait earlier.",
    105: "Main predicate 'understand' EN P2 -> JA P4 (わかって いる); 'abandoning them' EN P3 -> JA P2.",
    106: "'show him' EN P3 -> JA P5 (みせる).",
    108: "'helped save us' EN P2 -> JA P3 (すくったんだ); 'disaster' EN P3 -> JA P2 (さいなん).",
    109: "'finish off' EN P6 -> JA P7 (やりとげたら どうだ); 'the rest of the Gym Challenge' EN P7 -> JA P6.",
    112: "'what are your plans' EN P4 -> JA P5 (これから どうするの); 'Borrius' EN P5 -> JA P4.",
    113: "'was hoping' EN P1 -> JA P2; 'returned home' EN P2 -> JA P1; 'hope' EN P6 -> JA P7; 'if I look just like her' EN P7 -> JA P6.",
    114: "'gather' EN P3 -> JA P2 (あつまる).",
}
# Completed FA rows with no M1/M2 shift. Notes are M3 (modality/adverbial/subordinate) observations.
FA_NOTES = {
    23: "'one of 'em said' (P7) reaches いってた only in P8; quotative って marks the quotation in P7.",
    30: "'even if' EN P4 -> たとえ JA P5; the Zapdos / Marlon / escape content stays in P4.",
    51: "'shows' (evidential) EN P3 -> あかしだ JA P4; the proposition 'terminated our partnership' stays in P4.",
    73: "'never' EN P5 -> ぜったいに JA P6; 'agree to help' stays in P6. 'aid in finding' EN P3 -> さがす ために JA P4.",
    77: "'he will be' EN P6 -> いるはず JA P7; 'with them' stays in P7.",
    81: "Subordinate 'mess up' EN P5 -> しくじる JA P6 and 'when it matters most' EN P6 -> JA P5; main clause stays in P5.",
    94: "'there's a chance' (modality) EN P1 -> かもしれない JA P2; 'won't notice' (きづかれずに) and 'sneak past' (とおりぬけ) keep their phases. JA P1 is an adverbial fragment: M3 note only.",
    96: "'on your own' EN P3 -> ひとりで JA P2; the whole inference 'could not have escaped' stays in P2.",
    111: "'so don't go' EN P0 -> はなれないで JA P1 (the request is complete in P1 in both).",
}
FA_PASS_CHECKED = {11, 13, 18, 22, 33, 44, 54, 75, 79, 84, 85, 86, 91, 104, 110}
WORDING_ISSUES = {
    54: "'help Marlon end the Shadow Warrior Project' became マーロンの シャドウせんしけいかくを とめて: 'help' is dropped and the project is presented as Marlon's to be stopped. Meaning change; return to Claude.",
    89: "'for just long enough' has no Japanese counterpart (the temporal limit of the stall is lost).",
}
CHECKPOINTS = {
    18: 'P1 condition (surprise attack / remove it) and P2 conclusion (sorely mistaken) keep their waits; P3 silly attempts / tiring together. FE/FA/FB unchanged.',
    94: 'P0 condition, P1 not-noticed adverbial, P2 sneak-past/possibility; only the M3 modality moves (recorded as note).',
}
PHRASE_AUDIT = {
    58: {'code': 'FA_PHRASE_BOUNDARY_NOTE', 'verdict': 'HOLD',
         'finding': "The note says the 'so we should consider ourselves fortunate ...' clause was regrouped in E15-E18. Those four segments sit in four different wait phases (P9-P12), so the regroup crosses FA: 'consider' and 'fortunate' are swapped across a wait. 'living weapons' stays in P12 (the note's key-term claim is correct)."},
    70: {'code': 'FA_PHRASE_BOUNDARY_NOTE', 'verdict': 'NOTE_VALID_ENTRY_HELD',
         'finding': "The note's Frozen / Heights regroup (E9 FE E10) stays inside wait phase P6 in both languages, so the note itself is valid. The entry is held for other FA shifts (whole 'Shadow Warriors' shown in P4; 'there are only so many' predicate in P5) and for incomplete/interior pointer ownership."},
    100: {'code': 'FA_PHRASE_BOUNDARY_NOTE', 'verdict': 'HOLD',
          'finding': "The note says 'his Pokémon' was regrouped into E9. E8 (EN P4) and E9 (EN P5) are separated by FA, so the subject of the final clause appears one wait later in Japanese. Not a within-phase move."},
}
VOICE_AUDIT = {
    16: {'verdict': 'CONSISTENT', 'finding': "'Please, come with me' -> ください (polite request). No invented first/second person, gender, age, dialect. Added comma after the vocative only."},
    20: {'verdict': 'CONSISTENT', 'finding': "'Come on' -> ちょっと; the commanding おい is removed. Plain, neutral request (てを かして ほしいんだ). No invented speaker traits."},
    49: {'verdict': 'CONSISTENT', 'finding': "Unneeded きみ removed; 'know you better' -> おたがいの こと. English wistful tone preserved."},
    57: {'verdict': 'CONSISTENT', 'finding': "Rough おまえ removed; surprise/alarm of the English is carried by だが / なぜ. 'out of the picture' -> もう いない (slightly narrower)."},
    72: {'verdict': 'CONSISTENT', 'finding': "Unneeded きみ removed; 'Poké Balls' -> モンスターボール (official generic term). 'your' is implicit."},
}
OFFICIAL_AUDIT = {
    10: {'state': 'HOLD', 'classification': 'ONOMATOPOEIA_OR_CRY_LATIN_RETAINED', 'hold': "Shhhhzzz! is a cry/sound effect. Keeping the Latin text is the no-guess choice, but (a) no source verifies it as an official cry rendering and (b) on the [japanese] page the Latin letters would use Japanese-page glyphs, so the injected text is not the original Latin-page rendering. Applying it changes nothing intended; hold, keep baseline English.",
         'note': 'official_name_verification_required; language-switch behaviour not runtime verified'},
    11: {'state': 'HOLD', 'classification': 'GENERIC_TERM_PROJECT_CONSISTENT_ONLY', 'hold': "HM=ひでんマシン: consistent with Batch 01 usage, but there is no independent official-name evidence in the repo (no HM item in the PokeAPI cache, no glossary term). The Pokédex note (ずかん) is ordinary wording."},
    24: {'state': 'HOLD', 'classification': 'GENERIC_TERM_PROJECT_CONSISTENT_ONLY', 'hold': "HM=ひでんマシン / HM moves=ひでんわざ: no independent official-name evidence in the repo; Batch 01 consistency only."},
    37: {'state': 'PASS', 'classification': 'MACHINE_VOICE_TRANSLATOR_STYLE', 'basis': "All-caps machine messages are rendered in katakana without sentence-final polish. PAYLOAD RECEIVED = ペイロード ジュシン; PROCESSING = ショリチュウ with the source's three pauses unchanged. Not a name, no official/glossary claim; runtime appearance not verified."},
    38: {'state': 'PASS', 'classification': 'MACHINE_VOICE_TRANSLATOR_STYLE', 'basis': "PROCESSING COMPLETE = ショリ カンリョウ; SENTIENT MATTER DETECTED = イシキ ヲ モツ ブッシツ ヲ ケンチ (sentient = conscious); COPYING... = コピー チュウ with three pauses. Meaning matches the source line by line."},
    39: {'state': 'PASS', 'classification': 'MACHINE_VOICE_TRANSLATOR_STYLE', 'basis': "ENTRY H005 kept verbatim; HAS BEEN COPIED SUCCESSFULLY = コピー ニ セイコウ シマシタ; DATA UPLOADED TO THE MAINFRAME = メインフレーム ニ アップロード サレマシタ. Meaning matches."},
    109: {'state': 'HOLD', 'classification': 'UNVERIFIED_PLACE_NAME', 'hold': "Magnolia Town=マグノリアタウン: the glossary has only Magnolia Fields. No independent evidence that this is the same place or that マグノリア+タウン is the project's name. Not treated as official."},
}
NEXT_ACTION = {
    'review_needs_context': 'Prove the dynamic buffer contract (writer, value type/range, word form, particles, maximum width) from ROM evidence; never guess a form.',
    'review_needs_technical_fit': 'Classify the unrecorded exact pointer hit(s) and interior hits with structural proof (or find the real owner) before any relocation or injection.',
    'dynamic_buffer_contract_unproved': 'Prove [player]/[rival] maximum width and page state for this exact caller in the live renderer; the 42px local naming bound is diagnostic only.',
    'FA_SEMANTIC_REVIEW_REQUIRED': 'Return to Claude: re-translate the named segments so the listed key elements stay in their English wait phases. No automatic rewrite.',
    'CLAUDE_WORDING_REVIEW_REQUIRED': 'Return to Claude for the meaning correction named in the semantic state.',
    'official_or_project_name_unverified': 'Find independent evidence for the name/term (official Japanese data), or keep the baseline English.',
    'glossary_scope_or_target_unapproved': 'Prove the exact entity and approve explicit script IDs in a separate glossary task (see scope_extension_proposal); no global substitution.',
    'fa_source_width_envelope_exceeded': 'Regroup within the English source line envelope or prove the usable field width; do not relax the validator.',
    'owner_incomplete_or_interior': 'Prove each unaligned/interior hit is non-pointer data (structural proof) or identify its consumer; then re-audit.',
    'renderer_consumer_unproved': 'Locate the consumer code/window (font, width, FE handling) for this pointer owner before injecting.',
    'control_boundary_or_token_placement_changed': 'Return to Claude: control/token placement differs from the ROM source.',
    'field_208px_overflow': 'Shorten or regroup the line without losing meaning; return to Claude.',
}
INDEPENDENT_ENTITY = {  # exact entity proof from the PokeAPI cache (this entry only, no glossary change)
    'Surf': ('move', 'surf', 'Surf', 'なみのり'),
    'Hoopa': ('pokemon-species', 'hoopa', 'Hoopa', 'フーパ'),
}


def prior_artifact_snapshot():
    files = sorted({p for pat in PRIOR_ARTIFACT_PATTERNS for p in ROOT.glob(pat) if p.is_file()})
    hashes = {p.relative_to(ROOT).as_posix(): digest(p.read_bytes()) for p in files}
    return {'files': len(hashes), 'aggregate_sha256': digest(json.dumps(hashes, sort_keys=True).encode()), 'hashes': hashes}


def assert_inputs():
    """Read-only gates before any write: no existing artifact may have changed."""
    proof = b3.protected_snapshot()
    prior = prior_artifact_snapshot()
    assert prior['aggregate_sha256'] == PRIOR_ARTIFACTS_SHA, 'Past-batch artifact changed: stop, never restore automatically.'
    assert digest(BASE.read_bytes()) == BASE_SHA
    for path, sha in ((REVIEW, REVIEW_SHA), (BATCH, HANDOFF_SHA), (VOICE, VOICE_SHA)):
        assert digest(path.read_bytes()) == sha, path
    return proof, prior


def baseline():
    rows = read(OUT / 'ja_phase6_cleanup_batch03_combined_controlfix.json')['entries']
    assert len(rows) == len({x['id'] for x in rows}) == BASELINE_APPLIED
    return rows


def completed_text(row):
    """Reviewed Japanese for confirmed AND needs_technical_fit rows; '' for context holds."""
    if row['status'] not in ('confirmed', 'needs_technical_fit'):
        return ''
    if row['fa_segmented']:
        return reconstruct_reviewed_segments(strip_hma_quotes(row['original']), previous.segments(row), row['translated_segments'])
    text = row['reviewed_japanese']
    assert text == join_segments(previous.segments(row), row['translated_segments'])
    return text


def validate_review(review, handoff, manifest, voice):
    ids = [x['id'] for x in review]
    assert len(ids) == len(set(ids)) == 140
    assert ids == [x['id'] for x in handoff] == manifest['batches'][3]['entry_ids']
    assert Counter(x['status'] for x in review) == EXPECTED
    assert Counter((x['input_resolution_class'], x['status']) for x in review) == {
        ('CLAUDE_TRANSLATION', 'confirmed'): 101, ('CLAUDE_TRANSLATION', 'needs_context'): 3,
        ('CLAUDE_TRANSLATION', 'needs_technical_fit'): 1, ('CLAUDE_CONTEXT', 'confirmed'): 28,
        ('CLAUDE_CONTEXT', 'needs_context'): 7}
    assert Counter(x['speaker_confidence'] for x in review) == {'UNKNOWN': 139, 'PLAUSIBLE': 1}
    assert not voice['proven_speaker_groups']
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
        assert r['review_source'] == 'claude_cli' and r['batch'] == 4
        assert join_segments(previous.segments(r)) == strip_hma_quotes(r['original'])
        assert semantic_tokens(strip_hma_quotes(r['original'])) == r['protected_tokens']
        for k in ('speaker_id', 'speaker_confidence', 'voice_application', 'status', 'candidate_disposition'):
            assert r[k] == voice_rows[r['id']][k], (r['id'], k)
        if r['status'] == 'needs_context':
            assert not r['reviewed_japanese'] and not any(r['translated_segments'])
    fa = [x for x in review if x['fa_segmented']]
    done = [x for x in fa if x['status'] == 'confirmed' and any(x['translated_segments'])]
    assert len(fa) == 71 and len(done) == 66
    assert sum(len(x['translated_segments']) for x in done) == 703
    assert sum(1 for x in fa if x['status'] == 'needs_context') == 5
    assert tuple(i for i, x in enumerate(review) if x.get('fa_phrase_boundary_notes')) == PHRASE_INDICES
    assert tuple(i for i, x in enumerate(review) if x['official_name_warnings']) == OFFICIAL_INDICES
    assert tuple(i for i, x in enumerate(review) if x['relocation_warning'].get('needs_relocation')) == RELOCATION_INDICES
    gap = tuple(i for i, x in enumerate(review) if x['glossary_scope_warnings'])
    assert len(gap) == 23
    assert tuple(i for i, x in enumerate(review) if x['status'] == 'needs_context') == CONTEXT_HOLDS
    assert tuple(i for i, x in enumerate(review) if x['status'] == 'needs_technical_fit') == (TECHNICAL_HOLD,)
    context = [x for x in review if x['status'] == 'needs_context']
    memberships = {t: [x['id'] for x in context if t in x['buffers']] for t in sorted({b for x in context for b in x['buffers']})}
    dynamic = [i for i, x in enumerate(review) if x['status'] == 'confirmed' and set(x['buffers']) & {'[player]', '[rival]'}]
    assert len(dynamic) == 45, len(dynamic)
    assert sum(bool(set(x['buffers']) & {'[player]', '[rival]'}) for x in review) == 50  # +5 context-held
    return {'ids': 140, 'duplicates': 0, 'missing': 0, 'status_counts': dict(Counter(x['status'] for x in review)),
            'translation_class': 105, 'context_class': 35,
            'fa_total': 71, 'fa_complete': 66, 'fa_completed_segments': 703, 'fa_context_hold': 5,
            'phrase_note_ids': {str(i): ids[i] for i in PHRASE_INDICES},
            'official_warning_ids': {str(i): ids[i] for i in OFFICIAL_INDICES},
            'scope_gap_ids': {str(i): ids[i] for i in gap},
            'relocation_candidate_ids': {str(i): ids[i] for i in RELOCATION_INDICES},
            'dynamic_name_indices': dynamic, 'buffer_memberships': memberships,
            'speaker_confidence': dict(Counter(x['speaker_confidence'] for x in review)),
            'original_candidate_hold_confidence_tokens_controls_preserved': True}


def page_text(row, text):
    fix = runpy.run_path(str(ROOT / '004_controlfix_translations.py'))
    return fix['ensure_japanese_page'](text)[0] if text else None


def dynamic_width(fixed):
    """Diagnostic expansion of [player]/[rival] at the ROM-proved LOCAL naming-input bound
    (7 chars x 6px = 42px) and the conditional broad bound (7 x 12px = 84px). Neither is
    proof of the live renderer: external names / page state after expansion are unproved."""
    local = normal_line_widths_with_placeholders(fixed, {PLAYER_CODE: 42, RIVAL_CODE: 42})
    broad = normal_line_widths_with_placeholders(fixed, {PLAYER_CODE: 84, RIVAL_CODE: 84})
    return {'local_input_bound_px_per_name': 42, 'broad_conditional_px_per_name': 84,
            'max_line_local': local['max_total'], 'max_line_broad': broad['max_total'],
            'unknown_placeholder_codes_local': local['unknown_placeholder_codes'],
            'exceeds_208_local': local['max_total'] > 208, 'exceeds_208_broad': broad['max_total'] > 208,
            'line_total_local': local['line_total_max'], 'line_total_broad': broad['line_total_max'],
            'status': 'DIAGNOSTIC_ONLY_NOT_PROOF'}


def phase_view(row):
    """Group the ROM segments into wait phases (FA/FB end a phase; FE never does)."""
    phases, current = [], {'english': [], 'japanese': [], 'segments': []}
    for n, (src, tgt) in enumerate(zip(previous.segments(row), row['translated_segments'])):
        current['english'].append(src['text'])
        current['japanese'].append(tgt)
        current['segments'].append(n)
        if src['after_control'] in ('FA', 'FB'):
            phases.append({'phase': len(phases), 'wait_after': src['after_control'], **current})
            current = {'english': [], 'japanese': [], 'segments': []}
    if current['segments']:
        phases.append({'phase': len(phases), 'wait_after': 'END', **current})
    return phases


def semantic_audit(index, row):
    issue = FA_ISSUES.get(index)
    wording = WORDING_ISSUES.get(index)
    phrase = PHRASE_AUDIT.get(index)
    if phrase and phrase['verdict'] == 'HOLD' and not issue:
        issue = phrase['finding']
    if row['fa_segmented'] and row['status'] == 'confirmed':
        assert index in FA_ISSUES or index in FA_NOTES or index in FA_PASS_CHECKED, ('FA row without a manual verdict', index)
    return {'state': 'HOLD' if issue or wording else 'PASS', 'fa_issue': issue, 'wording_issue': wording,
            'fa_note': FA_NOTES.get(index),
            'method': 'Manual comparison of every English segment against its reviewed Japanese, per wait phase, independent of the Claude flags. Equal FA/FE/FB counts are structural, not semantic, evidence.',
            'rubric': 'HOLD when a key noun/term (M1) or the information-bearing main predicate (M2) is revealed in a different FA/FB wait phase; M3 modality/adverbial/subordinate shifts are notes.',
            'checkpoint': CHECKPOINTS.get(index, 'Full English and reviewed Japanese compared: actors, actions, quantities, polarity, modifiers and FE/FA/FB views.'),
            'wait_phases': phase_view(row),
            'source_and_target_units': [{'index': n, 'english': s['text'], 'japanese': t, 'after_control': s['after_control']}
                                        for n, (s, t) in enumerate(zip(previous.segments(row), row['translated_segments']))],
            'voice': deepcopy(VOICE_AUDIT.get(index)), 'phrase': deepcopy(phrase),
            'speaker_confidence': row['speaker_confidence'], 'voice_profile_status': row['voice_profile_status'],
            'identity_or_voice_confidence_promoted': False, 'new_wording_created': False}


def official_audit(index, row, text):
    records = []
    for claim in row['official_names_verified']:
        match = re.fullmatch(r'(.+?)=(.+?) \(PokeAPI cache, ([\w-]+)/([\w-]+), verified_exact\)', claim)
        assert match, claim
        english, japanese, category, slug = match.groups()
        record = official_record(category, slug, english, japanese)
        if japanese not in text:
            # Source spells the name over pauses (Hoo/pa); the reviewed kana must join to the exact name.
            assert japanese in PAUSE_OR_SPACE.sub('', text) and english.lower() in PAUSE_OR_SPACE.sub('', strip_hma_quotes(row['original'])).lower(), (row['id'], claim)
            record['context_proof'] = 'Source spells the name across pauses; reviewed kana joins to the exact species name once pauses/spaces are removed.'
        records.append(record)
    entry = OFFICIAL_AUDIT.get(index)
    issues = []
    if entry:
        records.append({k: v for k, v in entry.items() if k != 'hold'})
        if entry['state'] == 'HOLD':
            issues.append(entry['hold'])
    if row['official_name_warnings']:
        assert entry, ('Official-name warning without an audit verdict', index)
    return {'state': 'HOLD' if issues else 'PASS', 'records': records, 'issues': issues,
            'warnings': deepcopy(row['official_name_warnings'])}


def glossary_audit(index, row, handoff, text, glossary):
    result = b3.glossary_audit(row, handoff, text, glossary)
    issues, records = [], []
    for gap in result['gap_records']:
        key = f"{gap['source']}={gap['target']}"
        in_scope = any(t['target'] == gap['target'] and row['id'] in t['entry_ids'] for t in gap['terms'])
        if gap['state'] == 'EXISTING_GLOBAL_PERMISSION':
            records.append({**gap, 'audit': 'EXISTING_GLOBAL_PERMISSION', 'applied_as_approved_glossary': True})
        elif in_scope:
            records.append({**gap, 'audit': 'TERM_ENTRY_IDS_INCLUDE_THIS_ENTRY', 'applied_as_approved_glossary': True})
        elif gap['source'] in INDEPENDENT_ENTITY:
            category, slug, english, japanese = INDEPENDENT_ENTITY[gap['source']]
            assert japanese == gap['target']
            records.append({**gap, 'audit': 'INDEPENDENT_OFFICIAL_ENTITY_POKEAPI', 'applied_as_approved_glossary': False,
                            'entity_evidence': official_record(category, slug, english, japanese),
                            'basis': 'Exact entity proven independently of the glossary; entry-level safe, glossary scope unchanged.'})
        else:
            issues.append(key)
            records.append({**gap, 'audit': 'SCOPE_GAP_UNRESOLVED', 'applied_as_approved_glossary': False,
                            'basis': 'Existing scope does not cover this entry and no independent official evidence for the same entity was found.'})
    result['gap_records'] = records
    result['unresolved'] = issues
    result['state'] = 'HOLD' if issues or result['missing_targets'] else 'PASS'
    return result


def latin_in_japanese(text):
    """ASCII letters that remain in reviewed Japanese (recorded; baseline rows contain such letters too)."""
    plain = LATIN_STRIP.sub('', text or '')
    return re.findall(r'[A-Za-z]+', plain)


def waveform_smoothness(rom, offset):
    window = [b for i, b in enumerate(rom[offset - 32:offset + 36]) if not offset - 32 + i in range(offset, offset + 4)]
    diffs = [abs(window[i + 1] - window[i]) for i in range(len(window) - 1)]
    return round(sum(diffs) / len(diffs), 2)


def summaries(records, rom):
    """Entry-level audits requested for Batch 04; computed from the fresh analysis, not copied from Claude."""
    codec = Charmap('ja')
    raid = []
    table = 0x1E613B0
    for i in RAID_INDICES:
        r, rv = records[i], records[i]['review']
        raw = codec.encode(r['controlfixed_japanese'])
        controls = [c.split()[0] for c in previous.raw_controls(raw, ignore_pages=True)]
        owner = int(r['pointer_state']['recorded'][0], 16)
        assert (owner - table) % 16 == 4 and 0 <= (owner - table) // 16 < 32, (i, hex(owner))
        raid.append({'index': i, 'id': r['id'], 'english': rv['original'], 'japanese_lines': r['candidate_japanese'].split('\n'),
                     'source_FE': rv['source_controls'].get('FE', 0), 'target_FE': controls.count('fe'),
                     'source_FA_FB': [rv['source_controls'].get('FA', 0), rv['source_controls'].get('FB', 0)],
                     'target_FA_FB': [controls.count('fa'), controls.count('fb')],
                     'dynamic_buffers': rv['buffers'], 'static_line_px': r['width_state']['line_total_max'],
                     'source_line_px': r['width_state']['source_line_pixels'], 'max_px': r['width_state']['max_total'],
                     'table_record': (owner - table) // 16, 'renderer_profile': r['width_state']['profile']['profile_id'],
                     'decision': r['decision'], 'holds': r['all_holds']})
        assert raid[-1]['source_FE'] == raid[-1]['target_FE'] == 2 and raid[-1]['target_FA_FB'] == [0, 0]
        assert len(raid[-1]['japanese_lines']) == 3
    pattern = (0x08000000 + table).to_bytes(4, 'little')
    found, cursor = [], 0
    while (cursor := rom.find(pattern, cursor)) >= 0:
        found.append(hex(cursor))
        cursor += 1
    p60 = records[TECHNICAL_HOLD]['pointer_state']
    extra = int(p60['missing'][0], 16)
    relocation = []
    for i in (*RELOCATION_INDICES, 12):
        r = records[i]
        relocation.append({'index': i, 'id': r['id'], 'reported_by_claude': i in RELOCATION_INDICES, 'decision': r['decision'],
                           'original_slot_bytes': r['source_slot'], 'source_encoded_bytes': r['source_encoded_bytes'],
                           'final_encoded_bytes_with_page_controls': r['encoded_bytes'],
                           'source_control_bytes': r['review']['source_controls'],
                           'pointer_owners_recorded': r['pointer_state']['recorded'], 'whole_rom_exact_hits': r['pointer_state']['whole_rom_exact_hits'],
                           'owner_kinds': r['pointer_state']['owner_kinds'], 'interior_hits': r['pointer_state']['interior_hits'],
                           'fixed': r['pointer_state']['fixed'], 'no_relocation': r['pointer_state']['no_relocation'],
                           'holds': r['all_holds']})
    dynamic = [{'index': r['review_index'], 'id': r['id'], 'tokens': r['buffer_state']['tokens'],
                'static_max_px': r['width_state']['max_total'], **{k: r['buffer_state']['dynamic_width_diagnostic'][k] for k in
                ('max_line_local', 'max_line_broad', 'exceeds_208_local', 'exceeds_208_broad')}}
               for r in records if r['buffer_state'].get('dynamic_width_diagnostic')]
    glossary = [{'index': r['review_index'], 'id': r['id'], 'gaps': [{'term': f"{g['source']}={g['target']}", 'audit': g['audit'],
                 'applied_as_approved_glossary': g['applied_as_approved_glossary']} for g in r['glossary_state']['gap_records']],
                 'unresolved': r['glossary_state']['unresolved']} for r in records if r['review']['glossary_scope_warnings']]
    official = [{'index': i, 'id': records[i]['id'], 'state': records[i]['official_name_state']['state'],
                 'classification': OFFICIAL_AUDIT[i]['classification']} for i in OFFICIAL_INDICES]
    fa = [r for r in records if r['FA_state']['present']]
    done = [r for r in fa if r['review_status'] == 'confirmed']
    return {
        'raid_notice': {'table_base_rom': hex(table), 'record_stride': 16, 'record_fields': ['name_ptr', 'description_ptr', 'ewram_flag_ptr', 'id'],
                        'records_in_table': 32, 'direct_references_to_table_base_in_rom': found,
                        'consumer': 'UNPROVEN: no ROM reference to the table base found; the display window/width/font of the description are unproved',
                        'entries': raid},
        'pointer_60': {'recorded': p60['recorded'], 'unrecorded_exact_hit': p60['missing'], 'interior_hits': p60['interior_hits'],
                       'unrecorded_hit_context_hex': rom[extra - 12:extra + 12].hex(' '), 'neighbour_byte_mean_abs_delta': waveform_smoothness(rom, extra),
                       'finding': 'The recorded owner is a loadpointer+callstd 6 message. The unrecorded exact hit sits in smooth byte runs that look like PCM sample data, but no sample header/voicegroup proof was made: it is NOT accepted as a non-owner. Hold stays.'},
        'relocation': relocation, 'dynamic_names': dynamic, 'glossary_scope': glossary, 'official_names': official,
        'voice': [{'index': i, 'id': records[i]['id'], **VOICE_AUDIT[i], 'decision': records[i]['decision'], 'holds': records[i]['all_holds']} for i in VOICE_INDICES],
        'fa': {'rows': len(fa), 'completed': len(done), 'completed_segments': sum(len(r['review']['translated_segments']) for r in done),
               'semantic_hold': sorted(r['review_index'] for r in done if r['semantic_voice_state']['fa_issue']),
               'semantic_pass': sorted(r['review_index'] for r in done if not r['semantic_voice_state']['fa_issue']),
               'phrase_notes': {str(i): PHRASE_AUDIT[i] for i in PHRASE_INDICES},
               'context_holds': sorted(r['review_index'] for r in fa if r['review_status'] != 'confirmed')}}


def analyze():
    protection, prior = assert_inputs()
    source, base = (ROOT / 'rom/unbound.gba').read_bytes(), BASE.read_bytes()
    assert hashlib.md5(source).hexdigest() == previous.SOURCE_MD5
    anchors = previous.renderer_evidence(source)
    assert previous.renderer_evidence(base) == anchors
    review, handoff = read(REVIEW), read(BATCH)['entries']
    validation = validate_review(review, handoff, read(MANIFEST), read(VOICE))
    old = baseline()
    assert not {x['id'] for x in old} & {x['id'] for x in review}
    prepared = {x['id']: x for x in read(ROOT / 'out/ja-phase5e-prepared.json')['entries']}
    selection = {x['id']: x for x in read(FIX / 'ja_phase6_selection.json')['entries']}
    chosen = [selection[x['id']] for x in review]
    owners = {x['id']: x for x in owner_audit(chosen, source)['entries']}
    interiors = interior_pointer_hits(source, chosen)
    injector, codec = runpy.run_path(str(ROOT / '005_hybrid_injector.py')), Charmap('ja')
    assert codec.encode('[player][rival]')[:2] == bytes([0xFD, PLAYER_CODE]) and codec.encode('[rival]')[:2] == bytes([0xFD, RIVAL_CODE])
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
        assert source[pos:pos + slot] == base[pos:pos + slot], 'baseline already changed this slot'
        assert sorted(int(p, 16) for p in entry.get('pointer_sources', [])) == sorted(int(p, 16) for p in sel['pointer_owners'])
        for p in entry.get('pointer_sources', []):
            p = int(p, 16)
            assert source[p:p + 4] == base[p:p + 4] == (pos + 0x08000000).to_bytes(4, 'little')
        text = completed_text(r)
        fixed = page_text(r, text)
        holds = []
        if r['status'] == 'needs_context':
            holds.append('review_needs_context')
        if r['status'] == 'needs_technical_fit':
            holds.append('review_needs_technical_fit')
            holds.append('incomplete_pointer_ownership')
        controls = previous.control_audit(r, text, fixed, raw) if text else {'state': 'NOT_COMPLETED'}
        semantic = semantic_audit(i, r) if text else {'state': 'NOT_COMPLETED'}
        profile = previous.caller_profile(r, owners[key], source)
        width = previous.width_audit(r, fixed, raw, profile) if text else {'state': 'NOT_MEASURED', 'problems': []}
        official = official_audit(i, r, fixed) if text else {'state': 'NOT_COMPLETED', 'records': [], 'issues': []}
        terms = glossary_audit(i, r, s, text, glossary) if text else {'state': 'NOT_COMPLETED', 'gap_records': [], 'unresolved': []}
        dynamic = bool(set(r['buffers']) & {'[player]', '[rival]'})
        buffer = {'state': 'NOT_REQUIRED' if not r['buffers'] else 'UNKNOWN_CONTRACT',
                  'tokens': deepcopy(r['buffers']), 'writer': 'UNKNOWN', 'caller': profile,
                  'type': 'player/rival name' if r['buffers'] and set(r['buffers']) <= {'[player]', '[rival]'} else 'UNKNOWN',
                  'all_values': 'UNKNOWN', 'maximum_width': 'UNKNOWN', 'expansion_page_contract': 'UNKNOWN',
                  'handoff_evidence': deepcopy(s['buffer_metadata']),
                  'dynamic_width_diagnostic': dynamic_width(fixed) if text and dynamic else None}
        if r['buffers'] and text:
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
        record = {'id': key, 'review_index': i, 'batch_position': s['batch_position'], 'review_status': r['status'],
                  'review': deepcopy(r), 'source_handoff': deepcopy(s), 'original_english': r['original'],
                  'candidate_japanese': text, 'decision': 'HOLD' if holds else 'APPLY',
                  'primary_hold': holds[0] if holds else None, 'secondary_holds': holds[1:], 'all_holds': holds,
                  'buffer_state': buffer,
                  'FA_state': {'present': r['fa_segmented'],
                               'layout_status': 'NOT_APPLICABLE' if not r['fa_segmented'] else 'LAYOUT_PASS' if not holds else 'LAYOUT_HOLD',
                               'completed_segments': bool(text) and r['fa_segmented'], 'source_segments': source_segments,
                               'translated_segments': deepcopy(r['translated_segments']), 'phrase_note': i in PHRASE_INDICES,
                               'layout_approval_required_by_review': r.get('fa_layout_approval_required', False)},
                  'control_state': controls, 'semantic_voice_state': semantic, 'width_state': width,
                  'official_name_state': official, 'glossary_state': terms, 'pointer_state': pointer,
                  'source_slot': slot, 'source_encoded_bytes': length, 'encoded_bytes': size,
                  'controlfixed_japanese': fixed, 'latin_letters_in_japanese': latin_in_japanese(text),
                  'planned_placement': 'relocated' if relocate else 'in_place',
                  'next_action': NEXT_ACTION[holds[0]] if holds else 'Inspect the exact original caller in mGBA and every wait frame; not yet runtime tested.'}
        records.append(record)
        if not holds:
            entry['translated'] = fixed
            if r['fa_segmented']:
                entry.update(control_segments=deepcopy(source_segments), translated_segments=deepcopy(r['translated_segments']),
                             source_boundary_sequence=controls['source_boundaries'], controls=deepcopy(r['source_controls']),
                             fa_placement_policy='require_segments', fa_layout_reviewed=True, fa_placement_status='RESOLVED_SEGMENTED')
            safe.append(entry)
    actual_relocations = [x['review_index'] for x in records if x['pointer_state']['relocation_needed']]
    validation.update(actual_relocation_indices=actual_relocations, confirmed_rom_controls=dict(controls_confirmed),
                      all_rom_controls=dict(controls_all))
    assert actual_relocations == [4, 10, 12, 139], actual_relocations  # #12 is an extra, unreported candidate
    validation.update(reported_relocation_indices=list(RELOCATION_INDICES), unreported_relocation_indices=[12],
                      audits=summaries(records, source))
    metadata = {'validation': validation, 'renderer_evidence': anchors, 'baseline_sha256': BASE_SHA,
                'baseline_applied': BASELINE_APPLIED, 'applied': len(safe), 'held': 140 - len(safe),
                'japanese_applied_total': BASELINE_APPLIED + len(safe),
                'phase6_remaining_holds': PHASE6_REMAINING_BEFORE - len(safe),
                'fa_applied': sum(x['decision'] == 'APPLY' and x['FA_state']['present'] for x in records),
                'protected_inputs': {'files': protection['files'], 'aggregate_sha256': protection['aggregate_sha256']},
                'prior_artifacts': {'files': prior['files'], 'aggregate_sha256': prior['aggregate_sha256']},
                'review_sha256': REVIEW_SHA, 'new_wording': 0, 'validator_edits': 0, 'kanji': 0, 'encode_errors': 0}
    return metadata, records, safe


def assert_safe_record(r):
    """Independent fail-closed release gate, also re-run on every reused artifact."""
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


def scope_proposal(records):
    return {'glossary_changed': False, 'proposal_only': True,
            'entries': [{'id': r['id'], 'index': r['review_index'], 'gaps': r['glossary_state']['gap_records'],
                         'next_action': 'Prove the exact entity and approve explicit script IDs; no broad category/global substitution.'}
                        for r in records if r['review']['glossary_scope_warnings']]}


def save_analysis(metadata, records, safe):
    for r in records:
        if r['decision'] == 'APPLY':
            assert_safe_record(r)
    persist(OUT / (PREFIX + 'reviewed.json'), {'metadata': metadata, 'entries': records})
    persist(OUT / (PREFIX + 'technical_holds.json'), {
        'metadata': {'count': len(records) - len(safe), 'batch': 4},
        'entries': [hold_record(r) for r in records if r['decision'] == 'HOLD']})
    persist(OUT / (PREFIX + 'safe_input.json'), {'entries': safe})
    persist(OUT / (PREFIX + 'combined_controlfix.json'), {'entries': baseline() + safe})
    persist(OUT / (PREFIX + 'scope_extension_proposal.json'), scope_proposal(records))


def hold_record(r):
    fa = r['FA_state']
    return {'id': r['id'], 'review_index': r['review_index'], 'batch_index': 4, 'translation_status': r['review_status'],
            'reviewed_japanese': r['candidate_japanese'], 'primary_hold': r['primary_hold'],
            'secondary_holds': r['secondary_holds'],
            'FA_status': {'present': fa['present'], 'completed': fa['completed_segments'], 'layout': fa['layout_status'],
                          'phrase_note': fa['phrase_note'], 'semantic': r['semantic_voice_state'].get('state'),
                          'semantic_issue': r['semantic_voice_state'].get('fa_issue')},
            'buffer_status': {'state': r['buffer_state']['state'], 'tokens': r['buffer_state']['tokens'],
                              'dynamic_width_diagnostic': r['buffer_state'].get('dynamic_width_diagnostic')},
            'official_name_status': {'state': r['official_name_state']['state'], 'issues': r['official_name_state'].get('issues')},
            'glossary_scope_status': {'state': r['glossary_state']['state'], 'unresolved': r['glossary_state'].get('unresolved')},
            'dynamic_width_status': r['buffer_state'].get('dynamic_width_diagnostic') or r['width_state'].get('problems'),
            'pointer_status': {'missing': r['pointer_state']['missing'], 'stale': r['pointer_state']['stale'],
                               'interior_hits': r['pointer_state']['interior_hits'], 'relocation_needed': r['pointer_state']['relocation_needed']},
            'next_action': r['next_action']}


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
    assert_strict_map(read(full), read(full), BASELINE_APPLIED + len(safe))
    dry, built = [OUT / (PREFIX + n) for n in ('incremental_dry_run_map.json', 'map.json')]
    args = [BASE, fixed, '-o', ROM, '--target-lang', 'ja', '--fail-on-no-space']
    cli('005_hybrid_injector.py', [*args, '--dry-run', '--map-output', dry], [dry])
    assert_strict_map(read(dry), read(dry), len(safe))
    assert not ROM.exists(), f'Refusing to overwrite an existing ROM: {ROM}'
    cli('005_hybrid_injector.py', [*args, '--map-output', built], [ROM, built])
    assert_strict_map(read(dry), read(built), len(safe))


def old_relocations():
    moves = {}
    for name in ('ja_phase6_batch04_map.json', 'ja_phase6_batch05_incremental_map.json',
                 'ja_phase6_batch06_incremental_map.json', 'ja_phase6_cleanup_incremental_map.json',
                 'ja_phase6_cleanup_glossary_incremental_map.json', 'ja_phase6_cleanup_batch01_map.json',
                 'ja_phase6_cleanup_batch02_map.json', 'ja_phase6_cleanup_batch03_map.json'):
        moves.update({x['id']: x for x in read(OUT / name)['relocations']})
    return moves


def audit_binary(before, after, safe, mapping, old):
    assert len(before) == len(after) == 0x2000000 and digest(before) == BASE_SHA
    injector, codec = runpy.run_path(str(ROOT / '005_hybrid_injector.py')), Charmap('ja')
    moves = {x['id']: x for x in mapping['relocations']}
    allowed = {k: set() for k in ('in_place_text', 'relocated_text', 'pointer_writes')}
    from lib.unbound_free_space import VETTED_FREE_SPACE_RANGES
    for e in safe:
        pos, slot = int(e['address'], 16), e['byte_length']
        payload = encoded(injector, codec, e, e['translated'])
        if e['id'] in moves:
            move = moves[e['id']]
            dest = int(move['new_offset'], 16)
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
    old_moves = old_relocations()
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
    return {'status': 'PASS', f'existing_{BASELINE_APPLIED}_payload_storage_and_pointers_unchanged': True,
            'voice_three_preserved': voice, 'Daniel_not_newly_applied': True,
            'changed_byte_count': len(changed), 'unexpected_byte_count': 0,
            'classified_changed_bytes': {k: len(v & changed) for k, v in allowed.items()},
            'classified_changed_ranges': {k: previous.ranges(v & changed) for k, v in allowed.items()},
            'all_changed_ranges': previous.ranges(changed),
            'in_place_count': mapping['stats']['in_place'], 'relocation_count': len(moves),
            'pointer_writes': mapping['stats']['pointer_writes'], 'output_sha256': digest(after),
            'baseline_sha256': digest(before), 'runtime_font_graphics_ASM_changes': 0}


def runtime_qa(records):
    picks = [x for x in records if x['decision'] == 'APPLY'][:8]
    for i in (*PHRASE_INDICES, *VOICE_INDICES, *RELOCATION_INDICES, *RAID_INDICES[:2], 37, 60, 109):
        if records[i] not in picks:
            picks.append(records[i])
    picks = picks[:25]
    assert 15 <= len(picks) <= 25
    return {'metadata': {'count': len(picks), 'performed': False, 'rom': str(ROM.relative_to(ROOT)),
                         'map_event_unknown_is_not_reachability_proof': True},
            'entries': [{'id': x['id'], 'index': x['review_index'], 'decision': x['decision'],
                         'original': x['original_english'], 'japanese': x['candidate_japanese'],
                         'rom_offset': x['pointer_state']['source_rom_offset'], 'gba_address': x['pointer_state']['source_gba_address'],
                         'pointer_owners': x['pointer_state']['recorded'],
                         'speaker_evidence': deepcopy(x['source_handoff']['speaker_evidence']),
                         'map': 'UNKNOWN', 'event': 'UNKNOWN', 'runtime_reachability': 'UNKNOWN_NOT_PLAYED',
                         'procedure': 'Use recorded caller/actor evidence to locate the exact event. Do not infer a map from text proximity. Compare every source FE/FA/FB view, scroll line, colour, pause and the next English dialogue. HOLD entries must remain baseline text.',
                         'checks': ['original wait timing', 'scroll after FA', 'Latin/Japanese page recovery', 'no implicit wrap', 'neutral source-backed voice'],
                         'all_holds': x['all_holds']} for x in picks]}


def validate_outputs(metadata, safe):
    """Run regressions and create only the final validation artifact."""
    mapping = read(OUT / (PREFIX + 'map.json'))
    audit = audit_binary(BASE.read_bytes(), ROM.read_bytes(), safe, mapping, baseline())
    assert audit == read(OUT / (PREFIX + 'binary_audit.json'))
    outcomes = {}
    for name, args in (
        ('focused_pytest', [sys.executable, '-X', 'utf8', '-m', 'pytest', 'tests/test_ja_phase6_cleanup_batch04.py', 'tests/test_ja_phase6_cleanup_batch03.py', '-q']),
        ('pytest', [sys.executable, '-X', 'utf8', '-m', 'pytest', '-q']),
        ('py_compile', [sys.executable, '-X', 'utf8', '-m', 'py_compile',
                        'scripts/build_ja_phase6_cleanup_batch04.py', 'tests/test_ja_phase6_cleanup_batch04.py',
                        'scripts/build_ja_phase6_cleanup_batch03.py', 'tests/test_ja_phase6_cleanup_batch03.py']),
        ('git_diff_check', ['git', 'diff', '--check']),
    ):
        print('Validating ' + name, flush=True)
        result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, encoding='utf-8')
        assert result.returncode == 0, result.stdout + result.stderr
        record = {'state': 'PASS', 'returncode': result.returncode, 'command': args[3:] if 'pytest' in name or name == 'py_compile' else args}
        if 'pytest' in name:
            match = re.search(r'(\d+) passed(?:, (\d+) subtests passed)?', result.stdout)
            assert match, result.stdout
            record.update(passed=int(match[1]), subtests_passed=int(match[2] or 0))
        outcomes[name] = record
    proof = b3.protected_snapshot()
    prior = prior_artifact_snapshot()
    assert prior['aggregate_sha256'] == PRIOR_ARTIFACTS_SHA
    dry = read(OUT / (PREFIX + 'incremental_dry_run_map.json'))
    assert_strict_map(dry, mapping, len(safe))
    full = read(OUT / (PREFIX + 'full_dry_run_map.json'))
    assert_strict_map(full, full, BASELINE_APPLIED + len(safe))
    first, twice = [OUT / (PREFIX + n) for n in ('controlfix.json', 'controlfix_twice.json')]
    assert first.read_bytes() == twice.read_bytes()
    validation = {
        'phase': '6C-4J', 'status': 'PASS_STATIC_TECHNICAL_INTEGRATION_RUNTIME_NOT_PLAYED',
        **outcomes, 'input_accounting': metadata['validation'],
        'applied': len(safe), 'held': 140 - len(safe), 'japanese_applied_total': BASELINE_APPLIED + len(safe),
        'phase6_remaining_holds': PHASE6_REMAINING_BEFORE - len(safe), 'incremental_dry_run_stats': dry['stats'],
        'full_dry_run_stats': full['stats'], 'binary_audit': audit,
        'baseline_rom_sha256': BASE_SHA, 'output_rom_sha256': audit['output_sha256'],
        'controlfix_byte_idempotent': True, 'controlfix_sha256': digest(first.read_bytes()),
        'runtime_qa_count': read(FIX / (PREFIX + 'runtime_qa.json'))['metadata']['count'], 'runtime_qa_performed': False,
        'protected_inputs': {'files': proof['files'], 'aggregate_sha256': proof['aggregate_sha256']},
        'prior_artifacts': {'files': prior['files'], 'aggregate_sha256': prior['aggregate_sha256']},
        'existing_file_changes': 0, 'glossary_changes': 0, 'commit': False, 'push': False,
        'git_status': subprocess.check_output(['git', 'status', '--short'], cwd=ROOT, text=True),
    }
    persist(OUT / (PREFIX + 'validation.json'), validation)
    print(json.dumps({k: validation[k] for k in ('status', 'applied', 'held', 'pytest', 'focused_pytest')}, indent=2))


def explore():
    metadata, records, safe = analyze()
    print(json.dumps({k: metadata[k] for k in ('applied', 'held', 'japanese_applied_total', 'phase6_remaining_holds', 'fa_applied')}))
    print(json.dumps(dict(Counter(x['primary_hold'] for x in records)), ensure_ascii=False))
    print(json.dumps(dict(Counter(h for x in records for h in x['all_holds'])), ensure_ascii=False))
    return metadata, records, safe


def main():
    stage = sys.argv[1:]
    assert stage in (['analyze'], ['build'], ['validate'], ['explore']), 'Usage: build_ja_phase6_cleanup_batch04.py analyze|build|validate|explore'
    if stage == ['explore']:
        explore()
        return
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
    b3.protected_snapshot()
    assert prior_artifact_snapshot()['aggregate_sha256'] == PRIOR_ARTIFACTS_SHA
    print(json.dumps({'applied': len(safe), 'held': len(records) - len(safe), 'fa_applied': metadata['fa_applied'],
                      'total': metadata['japanese_applied_total'], 'remaining': metadata['phase6_remaining_holds'],
                      'primary_holds': dict(Counter(x['primary_hold'] for x in records if x['primary_hold']))}, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
