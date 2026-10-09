#!/usr/bin/env python3
"""Phase 6C-3B: NPC voice profiles and conservative rewrite candidates.

Review only. No ROM, translation JSON, glossary, injector or controlfix change.
Identity confidence is copied from Phase 6C-3A and never promoted.
The profile and rewrite decisions below are the reviewer's manual judgements;
this script validates them mechanically and writes the fixtures.
"""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import re
import runpy
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.pcs_text import Charmap
from lib.translation_tokens import semantic_tokens
from scripts.audit_ja_phase6_batch01_fit import line_widths

OUT = ROOT / "out/phase6"
FIX = ROOT / "tests/fixtures"
VOICE_INPUT = OUT / "ja_phase6_voice_review_for_claude.json"
ATTRIBUTION = OUT / "ja_phase6_speaker_attribution.json"
CANON = OUT / "ja_phase6_canon_character_candidates.json"
HANDOFF_V3 = OUT / "ja_phase6_cleanup_translation_handoff_v3.json"
COMBINED = OUT / "ja_phase6_cleanup_glossary_combined_controlfix.json"
PROFILES = FIX / "ja_phase6_voice_profiles_claude.json"
REWRITES = FIX / "ja_phase6_voice_rewrite_candidates.json"

HAN = re.compile(r"[㐀-鿿]")
STATUSES = {"CONFIRMED_VOICE", "PROVISIONAL_VOICE", "NEUTRAL_ONLY", "INSUFFICIENT_EVIDENCE"}
CONTROL = re.compile(r"\\CC[0-9A-F]+|\\[A-Za-z.]|\[[a-z0-9_]+\]|\n")
FIRST = ("わたし", "ぼく", "おれ", "あたし", "わし", "あたい", "じぶん")
SECOND = ("きみ", "あなた", "おまえ", "おぬし", "あんた", "てめえ")
ENDINGS = ("なんだ", "だよ", "だぜ", "だな", "だね", "かい", "ちゃった", "してやる", "ぞ", "ぜ", "よ", "ね", "さ", "わ", "だ", "た", "る")
SHORT_STATUS = {"C": "CONFIRMED_VOICE", "P": "PROVISIONAL_VOICE", "N": "NEUTRAL_ONLY", "I": "INSUFFICIENT_EVIDENCE"}

# index -> (status, politeness, observed traits, recommended endings, note)
P = {
    0: ("P", "くだけた常体", ["落ち着いた独白調", "虫ポケモンの収集を淡々と語る"], ["んだ", "だな"],
        "Shadow Adminクラス。2行のみ。他場面のMarlon発話は話者未帰属のため統合しない。"),
    1: ("P", "くだけた常体", ["負け惜しみ", "手持ち不足を理由にする"], ["のに", "だ"],
        "Light of Ruin Adminクラス。1行のみで根拠が薄い。他場面のIvory発話は未帰属。"),
    2: ("P", "常体(～してやる)", ["挑発的", "炎タイプを誇る", "負けると少し拗ねる"], ["してやる！", "ちゃった"],
        "Daniel/Reneeはタイプ宣言の定型で、個人固有の口調とまでは言えない。"),
    3: ("P", "常体(～してやる)", ["挑発的", "水タイプを誇る", "負けると少し拗ねる"], ["してやる！", "ちゃった"],
        "Danielと同じ定型。個人固有の口調とは確定しない。"),
    4: ("P", "くだけた常体", ["力自慢", "別の戦闘では擬音を交えて食べる話をする"], ["！", "ちゃえ！"],
        "同じtrainer IDに虫タイプ版とノーマルタイプ版の2系統の台詞がある。人物像を一つにまとめない。"),
    5: ("C", "芝居がかった常体", ["大げさな怒り", "闇の力を自称する", "敗北を糧にする", "いじめられたと感じる"],
        ["あじわえ！", "なる。"],
        "4行で一貫した芝居がかった態度。話し方の確認であり、性別・年齢・一人称は確定しない。"),
    6: ("P", "常体", ["前向きな宣言", "負けは率直に認める"], ["！", "なかった。"], "Picnickerクラス。3行で目立った癖は少ない。"),
    7: ("P", "くだけた口語", ["間延びした呼びかけ", "のんびり"], ["かい？"],
        "原文の長音(Heeeeey / Whooooa)を保つ。語尾の癖までは確定しない。"),
    8: ("N", "常体", ["海辺が好き", "素直に悔しがる"], ["！"], "手がかりは素朴な好みのみ。"),
    9: ("P", "くだけた常体", ["自信満々な宣言(未訳行)", "負けは認める"], ["な", "だ"],
        "Go-Gogglesの台詞(scr_1F12A15)は未翻訳でholdのまま。口調は既訳の1行と原文から推定。"),
    10: ("P", "子どもっぽい口語", ["興奮して見せたがる", "『みて、みて』の反復"], ["よ", "！"], "Bug Catcherクラス。"),
    11: ("P", "くだけた口語", ["言葉遊び(high)", "のんき"], ["？", "かも"], "駄洒落が両方の台詞の核。"),
    12: ("N", "常体", ["のんびりした趣味の話", "あきらめが早い"], ["。", "か..."], "Fishermanクラス。"),
    13: ("P", "幼い印象の口語", ["ママを探す", "人違いに気づく"], ["？", "ない"],
        "二人称『あなた』は根拠がなく硬いので、人称なしを推奨。"),
    14: ("P", "くだけた常体", ["驚かせるのが好き", "負けを軽く受け流す"], ["？", "だ！"], "Camperクラス。"),
    15: ("N", "常体", ["ピクニックが好き", "素直に悔しがる"], ["！", "だよ"], "Picnickerクラス。"),
    16: ("N", "伝聞調", ["噂話を伝える"], ["らしい"], "『They say』に由来する伝聞のみ。"),
    17: ("P", "くだけた常体", ["植物の話に夢中", "勝敗より話したがる"], ["！", "よう！"], "Collectorクラス。"),
    18: ("P", "くだけた口語", ["チャント(Na na na)を挟む", "Super Nerdを名乗る"], ["！"], "Batman風のチャントをそのまま残す。"),
    19: ("N", "常体", ["地面の強さへの素朴な疑問"], ["のかな？", "だ！"], "Collectorクラス。"),
    20: ("N", "常体", ["雨の橋を走る爽快感"], ["！"], "Hikerクラス。"),
    21: ("N", "常体", ["山の話をする"], ["？", "らしい"], "Hikerクラス。"),
    22: ("N", "励まし", ["道案内的な励まし"], ["だよ！", "だ！"], "Hikerクラス。"),
    23: ("N", "常体", ["化石を探す話"], ["？", "のに"], "名前Lucasは本編の人物と同名だが名前一致のみ。"),
    24: ("N", "常体", ["釣りの話"], ["？", "ない！"], "Fishermanクラス。"),
    25: ("N", "常体", ["道路の上にいると教える"], ["んだよ！", "？"], "Workerクラス。"),
    26: ("P", "荒っぽい口語", ["豪快な笑い", "自分を『にいちゃん』と呼ぶ(原文: this dude)"], ["ぜ", "た"],
        "三人称自称は原文(this dude)に由来する。一人称の確定には使わない。"),
    27: ("P", "常体", ["まじめに心配する", "トイレの話が核"], ["？", "よ"], "Fishermanクラス。"),
    28: ("P", "威嚇的な常体", ["脅し文句", "短く言い切る"], ["してやる！", "。"], "Roughneckクラス。"),
    29: ("P", "ぶっきらぼうな常体", ["『Hmph』の短い反応", "不機嫌"], ["た。", "よ。"], "Roughneckクラス。"),
    30: ("P", "年長者へのたしなめ口調", ["相手を『Youngin』と呼ぶ", "動揺すると言い淀む"], ["な", "か。"],
        "『Youngin』は呼びかけ語で、相手より年長であることの手がかりに限る。高齢とまでは断定しない。"),
    31: ("P", "古風な宣言", ["名乗りを上げる", "潔く負けを認める"], ["いざ", "よう！"], "Ninja Boyクラス。原文のthee/honorは古風な語感の根拠。"),
    32: ("P", "くだけた口語", ["バンド活動の話", "ロック調の決めゼリフ"], ["ぜ", "ない！"], "Guitaristクラス。"),
    33: ("N", "常体", ["応援してから事実を告げる"], ["だよ！", "。"], "Bird Keeperクラス。落差が冗談の核。"),
    34: ("P", "くだけた口語", ["いたずら好き", "ネタばらしをする"], ["ぞ！", "ない。"], "Bird Keeperクラス。"),
    35: ("N", "常体", ["待ち伏せをして失敗する"], ["。", "ないな"], "Bird Keeperクラス。"),
    36: ("P", "熱心な趣味人の口調(未訳)", ["バードウォッチングに熱心", "Rufflet贔屓"], [], "2行とも未翻訳でholdのまま。Reedとは別のtrainer ID。統合しない。"),
    37: ("P", "熱心な趣味人の口調(未訳)", ["Vullaby贔屓", "友人を軽くけなす"], [], "2行とも未翻訳でholdのまま。Rogerとは別のtrainer ID。統合しない。"),
    38: ("N", "常体", ["兄の自慢を紹介する"], ["よ！", "んだ！"], "Black Beltクラス。現行訳は『あに』と『よ』が混在するが破綻はしない。"),
    39: ("P", "気合の入った口語", ["武道の掛け声", "格言調"], ["！"], "Black Beltクラス。"),
    40: ("N", "常体", ["岩を砕いた話"], ["た！", "なかった。"], "Black Beltクラス。"),
    41: ("P", "機械的な報告調", ["確率を計算する", "結果を淡々と告げる"], ["中。", "パーセント。"], "Scientistクラス。"),
    42: ("N", "常体", ["称号を名乗る"], ["！", "ね。"], "Ace Trainerクラス。"),
    43: ("N", "断定調", ["霊についての説明"], ["だ。", "る。"], "Mediumクラス。神秘的とまでは言えない。"),
    44: ("N", "独白調", ["鳴き声を気味悪がる"], ["だ。", "だろう？"], "Mediumクラス。1行は未翻訳でhold。"),
    45: ("I", "未確定", [], [], "両行とも未翻訳のhold。内容は事実の説明のみで口調の手がかりがない。"),
    46: ("N", "常体", ["超能力を誇る"], ["！", "た。"], "Psychicクラス。"),
    47: ("P", "かたい常体", ["尊大な挑発", "秘密を暴くと宣言する"], ["やろう！", "た。"], "Ruin Maniacクラス。"),
    48: ("P", "くだけた口語", ["炎ポケモンに大喜び"], ["！", "そう！"], "Kindlerクラス。"),
    49: ("P", "熱血口調", ["暑さで気合が入る", "短い感嘆で終える"], ["くる！"], "Kindlerクラス。"),
    50: ("P", "年配を思わせる穏やかな口調", ["温泉的に砂で癒やされた話", "感心する"], ["だ！", "ね！"],
        "『Oh, my goodness』は驚きの感嘆で、年齢の断定には使わない。"),
    51: ("N", "常体", ["洞窟の生き物を守る仕事を説明する"], ["んだ", "なんだ。"], "Rangerクラス。"),
    52: ("I", "未確定", [], [], "『Hold.』『Picture perfect!』の2行のみ。『しゃしん』という媒体は原文から断定できない。"),
    53: ("N", "常体", ["岩について問いかける"], ["？", "ある。"], "Ruin Maniacクラス。"),
    54: ("P", "冷たい断定", ["気配を察知したと言う", "降参を迫る"], ["た。", "ろ。"], "Psychicクラス。"),
    55: ("N", "常体", ["砂漠の生き物を褒める"], ["いる！", "ね！"], "Rangerクラス。"),
}
NAME_COLLISIONS = {
    "Lucas": "本編にLucasという人物が存在し得るが、名前一致のみ",
    "Larry": "本編にLarryという人物が存在し得るが、名前一致のみ",
    "Marlon": "本編にMarlonという人物が存在し得るが、名前一致のみ（Unbound側はShadow Admin）",
    "Nate": "本編にNateという人物が存在し得るが、名前一致のみ",
    "Aaron": "本編にAaronという人物が存在し得るが、名前一致のみ",
}

# entry_id -> (proposed Japanese, reason, confidence, change risk)
REWRITES_TABLE = {
    "scr_1F02029": (
        "[japanese]とくしゅこうげきの [green]ほのお[blue]タイプで\nまるこげに してやる！[latin]",
        "『special Fire-types』の『とくせい』は、ポケモンの『とくせい(アビリティ)』と同じ語になり誤解される。"
        "同じ型の定型文で既に『ぶつりこうげきの あくの いかり』(scr_1F02164)と書いているので、攻撃の種類として揃える。口調は変えない。",
        "medium", "low: 『special』を特殊攻撃寄りと解釈する前提。スロットを超えたら要technical review"),
    "scr_1F02145": (
        "[japanese]くさタイプは\nたすけてくれなかった。[latin]",
        "対になる直前の台詞『しょうりに みちびいてくれる』（scr_1F02118）に合わせ、『helpしてくれる/くれなかった』の対応にする。"
        "『やくに たたなかった』は原文より辛辣で、文句というより拗ねた調子の原文とずれる。",
        "medium", "low: 語尾の印象のみ変更"),
    "scr_740753": (
        "[japanese]もしかして ママ？[latin]",
        "二人称『あなた』は根拠がなく、子どもが人違いをする場面には硬い。人称を省いて原文の意味(あなたは私のママ？)を保つ。",
        "medium", "low: 二人称の省略のみ"),
    "scr_1F06A82": (
        "[japanese]こてんぱんに してやる！[latin]",
        "『してあげる』は恩恵を与える言い方で、Roughneckクラスの威嚇と合わない。Daniel/Renee等の挑発文と同じ『してやる』にする。",
        "medium", "low: 威嚇の言い方のみ"),
}
UNCHANGED_NOTES = {
    "scr_74BFC6": "『まけなかったのに』は『you would've lost』のやや弱い言い換えだが意味は通る。無理に変えない。",
    "scr_1F0207D": "擬音ブクブクは泡/飲む音の解釈が割れる。根拠がないため据え置き。",
    "scr_1F0B02C": "『しゃしん』は媒体を断定している可能性があるが、場面が未確認のため据え置き(観察事項に記録)。",
}
OBSERVATIONS = [
    {"entry_id": "scr_1F0AECE", "kind": "glossary_alignment", "note": "『フロストマウンテン』は承認済みglossaryの『フロストやま』と異なる。声の見直しではないので本ファイルでは変更しない。"},
    {"entry_id": "scr_1F0B076", "kind": "glossary_alignment", "note": "『ルート8』は文中のRoute表記。glossaryのRoute [N]=[N]ばんどうろはmap_names限定のため、方針の確認が必要。"},
    {"entry_id": "scr_1F0B284", "kind": "typography", "note": "末尾の『!』が半角。声の問題ではないので変更しない。"},
    {"entry_id": "scr_1F12C64", "kind": "second_person_convention", "note": "『きみ』は主人公への一般的な呼びかけとして残る。話者固有の二人称とは扱わない。"},
]


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def tokens(text):
    return CONTROL.findall(text or "")


def ending_of(text):
    body = re.sub(r"\[[a-z0-9_]+\]|\\[A-Za-z.]|\\CC[0-9A-F]+", "", text or "").replace("\n", "")
    body = body.rstrip("。！？!?.…\\ ")
    return next((e for e in ENDINGS if body.endswith(e)), None)


def observed(text, words):
    return [w for w in words if w in (text or "")]


def clean(text):
    return re.sub(r"\[[a-z0-9_]+\]|\\[A-Za-z.]|\\CC[0-9A-F]+", "", text or "").replace("\n", "")


def validate_rewrite(entry, current, proposed, codec, injector, slot):
    base = dict(entry)
    def payload(value):
        item = dict(base)
        item["translated"] = value
        return injector["encode_text"](codec, injector["translation_for_injection"](item), plain_script=False)
    now, new = payload(current), payload(proposed)
    ok_tokens = tokens(current) == tokens(proposed)
    ok_semantic = semantic_tokens(current) == semantic_tokens(proposed)
    widths = line_widths(new)
    codec.encode(proposed)
    return {
        "control_validation": {
            "control_token_sequence_equal": ok_tokens, "protected_tokens_equal": ok_semantic,
            "newline_count_equal": current.count("\n") == proposed.count("\n"),
            "source_controls": tokens(current), "proposed_controls": tokens(proposed),
            "encoded_bytes_current": len(now), "encoded_bytes_proposed": len(new),
            "source_slot_size": slot, "fits_source_slot": len(new) <= slot,
            "line_pixels_proposed": widths, "max_line_pixels_current": max(line_widths(now), default=0),
            "within_240px": max(widths, default=0) < 240},
        "charmap_validation": {"encodes_in_japanese_charmap": True, "kanji_free": not HAN.search(proposed)},
    }


def build():
    voice = read(VOICE_INPUT)
    groups = voice["groups"]
    assert len(groups) == 56 and sorted(P) == list(range(56))
    attribution = read(ATTRIBUTION)
    canon = read(CANON)
    handoff = {x["id"]: x for x in read(HANDOFF_V3)["entries"]}
    combined = {x["id"]: x for x in read(COMBINED)["entries"]}
    selection = {x["id"]: x for x in read(FIX / "ja_phase6_selection.json")["entries"]}
    codec = Charmap("ja")
    injector = runpy.run_path(str(ROOT / "005_hybrid_injector.py"))

    profiles, candidates, unchanged, held = [], [], [], []
    for index, group in enumerate(groups):
        status_key, politeness, traits, rec_endings, note = P[index]
        dialogue = group["dialogue"]
        translated = [d for d in dialogue if d["current_japanese"]]
        untranslated = [d["id"] for d in dialogue if not d["current_japanese"]]
        lines = [d["current_japanese"] for d in translated]
        first_seen = sorted({w for x in lines for w in observed(x, FIRST)})
        second_seen = sorted({w for x in lines for w in observed(x, SECOND)})
        ends = sorted({e for e in (ending_of(x) for x in lines) if e})
        evidence = group["speaker_evidence"]
        classes = sorted({e.get("trainer_class") for lst in evidence for e in lst if e.get("trainer_class")})
        trainer_ids = sorted({e.get("trainer_id") for lst in evidence for e in lst if e.get("trainer_id") is not None})
        examples = []
        for d in translated:
            examples.append(clean(d["current_japanese"]))
            if d["id"] in REWRITES_TABLE:
                examples[-1] = clean(REWRITES_TABLE[d["id"]][0])
        examples = sorted(examples, key=len)[:2]
        name = group["speaker_name"]
        prohibited = ["一人称を断定しない(現行訳の一人称は参考値)", "二人称を断定しない", "性別・年齢を語尾で付与しない",
                      "他のtrainer ID・他マップの発話と統合しない", "同名の公式キャラクターと同一視しない",
                      "性格を原文以上に創作しない"]
        if name in NAME_COLLISIONS:
            prohibited.append(NAME_COLLISIONS[name])
        profile = {
            "speaker_id": group["speaker_id"], "character_name": name,
            "character_name_japanese": None,
            "identity_confidence": group["confidence"],
            "identity_basis": "trainer ID binding via a trainerbattle text operand (Phase 6C-3A); not a canon identity claim",
            "canon_identity": {"status": "NOT_ESTABLISHED", "official_character_proven": False},
            "character_category": group["character_category"],
            "trainer_class": classes, "trainer_ids": trainer_ids,
            "source_game": group["source_game"] or {"game": None, "confidence": "UNKNOWN"},
            "voice_status": SHORT_STATUS[status_key],
            "first_person": {"value": None, "status": "unspecified",
                             "observed_in_current_japanese": first_seen,
                             "policy": "原文に一人称の根拠がない限り確定しない。省略を優先"},
            "second_person": {"value": None, "status": "unspecified",
                              "observed_in_current_japanese": second_seen,
                              "policy": "『きみ』は主人公への一般的な呼びかけとして既訳に残るが、話者固有とは扱わない"},
            "politeness": politeness,
            "sentence_endings": {"observed_in_current_japanese": ends, "recommended": rec_endings},
            "personality_traits": traits,
            "speech_examples_short": examples,
            "evidence_entry_ids": group["dialogue_ids"],
            "untranslated_entry_ids": untranslated,
            "prohibited_assumptions": prohibited,
            "original_japanese_voice_reference": {"status": "not_collected", "applied": False},
            "notes": note,
        }
        profiles.append(profile)
        for d in dialogue:
            key = d["id"]
            if not d["current_japanese"]:
                held.append({"entry_id": key, "speaker_id": group["speaker_id"], "original_english": d["original"],
                             "reason": "現行訳なし(翻訳キューにhold)。翻訳はこの工程の対象外。口調の目安はprofileにのみ記録"})
                continue
            if key in REWRITES_TABLE:
                proposed, reason, confidence, risk = REWRITES_TABLE[key]
                checks = validate_rewrite(combined[key], d["current_japanese"], proposed, codec, injector,
                                          selection[key]["slot_size"] if key in selection else combined[key]["byte_length"])
                review = not (checks["control_validation"]["fits_source_slot"] and checks["control_validation"]["within_240px"])
                candidates.append({
                    "entry_id": key, "speaker_id": group["speaker_id"], "speaker_confidence": group["confidence"],
                    "original_english": d["original"], "current_japanese": d["current_japanese"],
                    "proposed_japanese": proposed, "reason": reason,
                    "speaker_evidence": [{"kind": e["kind"], "trainer_id": e.get("trainer_id"),
                                          "trainer_class": e.get("trainer_class"),
                                          "text_operand_offset": e.get("text_operand_offset")}
                                         for e in group["speaker_evidence"][group["dialogue_ids"].index(key)]],
                    "control_validation": checks["control_validation"], "charmap_validation": checks["charmap_validation"],
                    "confidence": confidence, "change_risk": risk,
                    "requires_technical_review": review})
            else:
                unchanged.append({"entry_id": key, "speaker_id": group["speaker_id"],
                                  "reason": UNCHANGED_NOTES.get(key, "既訳が原文の調子に合っており、変更の必要がない")})
    return groups, profiles, candidates, unchanged, held, attribution, canon, handoff


def plausible_pool(attribution, handoff):
    tendencies = {
        "scr_1F01267": "丁寧で驚きを抑えた呼びかけ。『Wait.』『Can it be.』の間を保つ",
        "scr_1F012BD": "敬意をもって興奮気味に話す。父(Aros)を称える調子",
        "scr_1F02458": "くつろいだ歓迎。ゆったり落ち着かせる言い方",
        "scr_1F075CB": "駄洒落(Wingderful)好きの明るい依頼人",
        "scr_1F078CB": "丁寧で威厳のある依頼人。同じマップの近接オブジェクトだが同一NPCとは未確定",
        "scr_1F07929": "丁寧で威厳のある依頼人(同上)",
        "scr_1F079B1": "要点を整えて説明する依頼人(同上)",
        "scr_1F07AB1": "確認を促す短い問いかけ(同上)",
        "scr_1F07EC2": "ひそひそ声の陰謀論者(コミカル)",
        "scr_1F08005": "スローガンを叫ぶ陰謀論者(コミカル)",
        "scr_1F082E2": "『Shush, quiet.』と声を潜める陰謀論者(コミカル)",
        "scr_1F083F2": "革命を叫ぶ誇張した調子(コミカル)",
        "scr_1F08691": "進化論的優越を語る冷静だが不穏な語り口",
        "scr_1F08AC4": "自分をTrash-Manと名乗る奇矯で誇らしげな宣言(本文中に自己紹介あり)",
        "scr_1F08E36": "『woman of science』と本文で自称する、丁寧で内省的な話し方。性別の手がかりは本文の自称のみ",
        "scr_1F08F28": "依頼の説明を丁寧に行う科学者的な調子",
        "scr_1F09045": "結果を総括するやや芝居がかった調子",
        "scr_1F0935A": "富への飢えを問う儀式的でもったいぶった調子",
        "scr_1F09BFC": "商品の情報を伝える親切な説明口調",
        "scr_1F0A0E6": "丁寧に頼む控えめな依頼人(家族の宴のため)",
        "scr_1F0A273": "礼を述べ、手がかりを教える親切な調子",
        "scr_1F0B7A3": "動揺し、叱ってから納得する忙しい口調",
        "scr_1F0B9B3": "物知り顔の軽い雑談調",
        "scr_1F0C34F": "トロフィーの説明文。口調を付けず中立",
        "scr_1F0C3AF": "トロフィーの説明文(同上)",
        "scr_1F0C40F": "トロフィーの説明文(同上)",
        "scr_1F0C46E": "親しげに声をかけ背中を押す調子。家族とは限らない",
        "scr_1F0C52E": "親しげに声をかけ背中を押す調子(同上)",
        "scr_1F0CECE": "礼儀正しい受け取りの返事",
        "scr_1F14710": "地の文に近い定型文。口調を付けず中立",
        "scr_1F15C6C": "ゆるく間延びしたくだけた話し方。口癖が強い",
        "scr_1F164BE": "落ち着いた威厳のある口調。名前を尋ねる",
        "scr_1F1653E": "本文中でVégaと名乗る、丁寧で抑えた口調。本人確認の昇格はしない",
        "scr_1F17516": "『Howdy, partner』系の西部風のくだけた方言調(原文に根拠あり)",
        "scr_1F17729": "同上。冗談めいた自信を見せる",
        "scr_1F2FCB5": "丁寧で知識のある助言者。Prof. Euler Logの名を出すが、本人とは限らない",
        "scr_1F30F7B": "指示を出す簡潔で切迫した調子",
        "scr_1F62EC8": "戦闘結果の地の文。口調を付けず中立",
    }
    rows = []
    for item in attribution["entries"]:
        if item["speaker_confidence"] != "PLAUSIBLE":
            continue
        binding = item["speaker_evidence"][0]
        bindings = binding.get("bindings", [])
        rows.append({
            "entry_id": item["id"], "identity_confidence": "PLAUSIBLE",
            "original_english": handoff[item["id"]]["original_english"],
            "evidence_kind": binding["kind"],
            "map_section_names": sorted({b.get("map_section_name") for b in bindings if b.get("map_section_name")}),
            "graphics_ids": sorted({b.get("graphics_id") for b in bindings if b.get("graphics_id") is not None}),
            "candidate_object_count": len(bindings),
            "tendency_suggestion": tendencies[item["id"]],
            "voice_status": "NEUTRAL_ONLY" if "中立" in tendencies[item["id"]] else "PROVISIONAL_VOICE",
            "applies_to_other_entries": False})
    assert {r["entry_id"] for r in rows} == set(tendencies)
    return rows


def unknown_pool(attribution, handoff):
    cues = Counter()
    conv = 0
    for item in attribution["entries"]:
        if item["speaker_confidence"] != "UNKNOWN":
            continue
        if item["speaker_category"] == "NON_DIALOGUE":
            continue
        conv += 1
        text = handoff[item["id"]]["original_english"]
        for name, pattern in (("exclamation", r"!"), ("question", r"\?"), ("pause_token", r"\\\."), ("please", r"(?i)please"),
                              ("contraction_slang", r"(?i)\b(ya|yer|gonna|wanna|'em|kinda|ain't)\b"),
                              ("player_address", r"\[player\]"), ("buffer_in_text", r"\[buffer[123]\]")):
            if re.search(pattern, text):
                cues[name] += 1
    return {
        "dialogue_candidates": conv, "non_dialogue": sum(1 for i in attribution["entries"] if i["speaker_category"] == "NON_DIALOGUE"),
        "english_cue_counts": dict(cues),
        "rules": ["キャラ付けしない。誰かの口調を借りない",
                  "老人語・女性語・方言は、原文にその根拠(自称・方言表記)がない限り足さない",
                  "原文の気分(元気・怒り・丁寧な説明・皮肉・冗談・驚き・落胆)に合わせて自然な文末を選ぶ",
                  "全員を同じ無機質な敬語に揃えない。ただし情報や条件は一切変えない"]}


def main():
    groups, profiles, candidates, unchanged, held, attribution, canon, handoff = build()
    counts = Counter(p["voice_status"] for p in profiles)
    plausible = plausible_pool(attribution, handoff)
    unknown = unknown_pool(attribution, handoff)
    metadata = {
        "phase": "6C-3B", "review_only": True, "rom_changed": False, "glossary_changed": False,
        "input_groups": len(groups), "profiles": len(profiles),
        "input_entries": sum(len(g["dialogue"]) for g in groups),
        "voice_status_counts": dict(counts),
        "identity_confidence_preserved": dict(Counter(p["identity_confidence"] for p in profiles)),
        "official_character_voice_applied": 0,
        "official_voice_reference": canon["external_japanese_voice_reference_status"],
        "proven_canon_characters": canon["metadata"]["proven_canon"],
        "policy": "PROVEN is a trainer-ID binding only. CONFIRMED_VOICE needs repeated, consistent, observable manner; "
                  "PLAUSIBLE/UNKNOWN are never promoted; first/second person and gender are not assigned without evidence."}
    write(PROFILES, {"metadata": metadata, "profiles": profiles,
                     "plausible_pool": {"entries": plausible, "rule": "傾向の提案のみ。人物固有の口調として確定せず、一括変更しない"},
                     "unknown_pool": unknown})
    write(REWRITES, {"metadata": {
        "phase": "6C-3B", "candidates": len(candidates), "unchanged": len(unchanged), "held_untranslated": len(held),
        "reviewed_entries": len(candidates) + len(unchanged) + len(held),
        "requires_technical_review": sum(c["requires_technical_review"] for c in candidates),
        "applied_to_translation_json": False,
        "rule": "Meaning, proper nouns and every control token are unchanged; a candidate is a proposal only."},
        "candidates": candidates, "unchanged": unchanged, "held_untranslated": held,
        "out_of_scope_observations": OBSERVATIONS})
    return {"groups": len(profiles), "entries": len(candidates) + len(unchanged) + len(held),
            "status": dict(counts), "candidates": len(candidates), "unchanged": len(unchanged), "held": len(held)}


if __name__ == "__main__":
    print(main())
