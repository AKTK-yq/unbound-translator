"""ROM-anchored, fail-closed renderer geometry for Japanese width audits.

This module does not claim that a source text's pointer proves the live caller.
Only the battle templates/text-printer settings below have direct ROM anchors.
"""

from __future__ import annotations

from dataclasses import dataclass

from lib.gen3_font import NORMAL_GLYPH_WIDTHS, NORMAL_JAPANESE_GLYPH_WIDTHS
from lib.pcs_text import Charmap, fc_arg_count


BATTLE_WINDOW_TABLE = 0x00248330  # GBA 0x08248330; pointer at ROM 0x0000F348.
BATTLE_TEXT_INFO = 0x003FEB64  # GBA 0x083FEB64; literals at ROM 0x000D8814 etc.
BATTLE_INIT_POINTER = 0x0000F348
BATTLE_TEXT_POINTER = 0x000D8814
WINDOW_RECORD_BYTES = 8
TEXT_INFO_RECORD_BYTES = 12


@dataclass(frozen=True)
class RendererProfile:
    key: str
    status: str
    window_id: int | None
    window_rom_offset: int | None
    printer_rom_offset: int | None
    width_tiles: int | None
    height_tiles: int | None
    text_start_x: int | None
    font_id: int | None
    letter_spacing: int | None
    line_spacing: int | None
    usable_width: int | None
    visible_lines: int | None
    wrap: str
    evidence: str
    confidence: str = "UNKNOWN"
    dynamic_width_behavior: str = "unknown"


def _pointer(rom: bytes, offset: int) -> int:
    return int.from_bytes(rom[offset:offset + 4], "little")


def battle_profiles(rom: bytes) -> dict[str, RendererProfile]:
    """Read actual Unbound window and printer records, reject changed anchors."""
    if _pointer(rom, BATTLE_INIT_POINTER) != 0x08000000 + BATTLE_WINDOW_TABLE:
        raise ValueError("Battle window table xref changed")
    if _pointer(rom, BATTLE_TEXT_POINTER) != 0x08000000 + BATTLE_TEXT_INFO:
        raise ValueError("Battle printer table xref changed")
    # The first three records also match FireRed's B_WIN_MSG/PROMPT/ACTION_MENU
    # sequence. This guards against mistaking a coincidental byte run for data.
    if rom[BATTLE_WINDOW_TABLE:BATTLE_WINDOW_TABLE + 24] != bytes.fromhex(
            "00 01 0f 1c 04 00 90 00 00 01 23 0e 04 00 c0 01 "
            "00 11 23 0c 04 05 90 01"):
        raise ValueError("Battle window records changed")
    if rom[BATTLE_TEXT_INFO:BATTLE_TEXT_INFO + 12] != bytes.fromhex(
            "ff 02 02 02 00 02 01 01 0f 06 00 00"):
        raise ValueError("Battle message printer settings changed")
    spec = {
        "battle_message": (0, 2),
        "battle_action_prompt": (1, 2),
        "battle_action_menu": (2, 1),
        "battle_move_name": (3, 0),
    }
    result: dict[str, RendererProfile] = {}
    for key, (index, expected_font) in spec.items():
        window_offset = BATTLE_WINDOW_TABLE + index * WINDOW_RECORD_BYTES
        printer_offset = BATTLE_TEXT_INFO + index * TEXT_INFO_RECORD_BYTES
        window = rom[window_offset:window_offset + WINDOW_RECORD_BYTES]
        printer = rom[printer_offset:printer_offset + TEXT_INFO_RECORD_BYTES]
        if window[0] > 3 or printer[1] != expected_font:
            raise ValueError(f"Battle {key} profile changed")
        width_tiles, height_tiles = window[3], window[4]
        x = printer[2]
        result[key] = RendererProfile(
            key=key, status="ROM_WINDOW_AND_PRINTER_PROVED", window_id=index,
            window_rom_offset=window_offset, printer_rom_offset=printer_offset,
            width_tiles=width_tiles, height_tiles=height_tiles,
            text_start_x=x, font_id=printer[1], letter_spacing=printer[4],
            line_spacing=printer[5], usable_width=width_tiles * 8 - x,
            visible_lines=2 if index in (0, 1, 2) else 1,
            wrap="explicit_FE_FA_FB_only" if index == 0 else "no_implicit_wrap_proved",
            evidence=(f"ROM 0x{window_offset:08X} template and 0x{printer_offset:08X} "
                      f"printer record; 0x{BATTLE_INIT_POINTER:08X}/0x{BATTLE_TEXT_POINTER:08X} xrefs"),
            confidence="PROVEN" if index == 0 else "PARTIAL",
            dynamic_width_behavior="expanded placeholders require per-code bounds" if index == 0
                                   else "cell/cursor width not established",
        )
    return result


def unknown_profile(key: str, reason: str) -> RendererProfile:
    return RendererProfile(key, "UNKNOWN_RENDERER", None, None, None, None, None,
                           None, None, None, None, None, None, "unknown", reason)


def focused_menu_profiles(rom: bytes) -> dict[str, RendererProfile]:
    """Only menus with ROM-anchored callers/templates; no category-wide reuse."""
    if _pointer(rom, 0x0008867C) != 0x083CC2B8:
        raise ValueError("Options InitWindows xref changed")
    if rom[0x003CC2B8:0x003CC2D0] != bytes.fromhex(
            "01 02 03 1a 02 01 02 00 00 02 07 1a 0c 01 36 00 "
            "02 00 00 1e 02 0f 6e 01"):
        raise ValueError("Options templates changed")
    if _pointer(rom, 0x00088DDC) != 0x083CC314:
        raise ValueError("Options label text table xref changed")
    if (_pointer(rom, 0x000EB778), _pointer(rom, 0x000EB804)) != (
            0x08402248, 0x08402250):
        raise ValueError("PC item action window xrefs changed")
    profiles = {}
    for key, index, origin in (("options_title", 0, None),
                               ("options_label_value_row", 1, 8),
                               ("options_help", 2, None)):
        offset = 0x003CC2B8 + index * 8
        window = rom[offset:offset + 8]
        profiles[key] = RendererProfile(
            key=key, status="ROM_TEMPLATE_PARTIAL_LAYOUT", window_id=index,
            window_rom_offset=offset, printer_rom_offset=0x00088D8C if index == 1 else None,
            width_tiles=window[3], height_tiles=window[4], text_start_x=origin,
            font_id=2 if index == 1 else None, letter_spacing=None, line_spacing=None,
            usable_width=None, visible_lines=None, wrap="not_proved",
            evidence=f"ROM 0x{offset:08X} via InitWindows caller 0x0008861C; "
                     "label printer caller 0x00088D8C for window 1 only",
            confidence="PARTIAL", dynamic_width_behavior="label/value share row; column boundary unproved")
    for key, offset in (("pc_item_action_short", 0x00402248),
                        ("pc_item_action_tall", 0x00402250)):
        window = rom[offset:offset + 8]
        profiles[key] = RendererProfile(
            key=key, status="ROM_TEMPLATE_PARTIAL_LAYOUT", window_id=None,
            window_rom_offset=offset, printer_rom_offset=None,
            width_tiles=window[3], height_tiles=window[4], text_start_x=None,
            font_id=None, letter_spacing=None, line_spacing=None,
            usable_width=None, visible_lines=None, wrap="not_proved",
            evidence=f"ROM 0x{offset:08X} AddWindow path 0x000EB74C/0x000EB77E; "
                     "item-storage text/function pairs at 0x00402208",
            confidence="PARTIAL", dynamic_width_behavior="action cursor and text origin unproved")
    return profiles


def maximum_table_width(entries: list[dict], rom: bytes, category: str) -> dict:
    """Conservative maximum over *all extracted ROM records*, including dummies."""
    rows = [row for row in entries if row["category"] == category]
    if not rows:
        raise ValueError(f"No {category} records")
    widths = []
    for row in rows:
        start = int(row["address"], 16)
        raw = rom[start:start + int(row["byte_length"])]
        text = raw.split(b"\xff", 1)[0]
        if any(byte >= 0xF8 for byte in text):
            raise ValueError(f"Control byte inside {category} name: {row['id']}")
        widths.append((sum(NORMAL_GLYPH_WIDTHS[byte] for byte in text), row["id"], len(text)))
    largest = max(widths)
    return {"category": category, "record_count": len(rows), "max_width": largest[0],
            "max_id": largest[1], "max_encoded_chars": largest[2],
            "evidence": "ROM original fixed table; Latin normal-font glyph advances; all extracted rows scanned",
            "future_translation_caveat": "Recompute after name-table localization; source ROM maximum is not a Japanese-name bound"}


def conservative_variable_bounds() -> dict:
    """FireRed struct/name lengths, deliberately not an Unbound runtime proof."""
    latin_max = max(NORMAL_GLYPH_WIDTHS[:0xF8])
    japanese_max = max(NORMAL_JAPANESE_GLYPH_WIDTHS[:0xF8])
    return {
        "player": {"max_chars_reference": 7, "latin_upper_pixels": 7 * latin_max,
                   "japanese_upper_pixels": 7 * japanese_max,
                   "proof": "FireRed PLAYER_NAME_LENGTH=7; Unbound naming/save cap unproved",
                   "approved_for_automatic_fit": False},
        "rival": {"max_chars_reference": 7, "latin_upper_pixels": 7 * latin_max,
                  "japanese_upper_pixels": 7 * japanese_max,
                  "proof": "FireRed rivalName[PLAYER_NAME_LENGTH+1]; Unbound cap unproved",
                  "approved_for_automatic_fit": False},
        "nickname": {"max_chars_reference": 10, "latin_upper_pixels": 10 * latin_max,
                     "japanese_upper_pixels": 10 * japanese_max,
                     "proof": "FireRed POKEMON_NAME_LENGTH=10; Unbound GetMonData cap unproved",
                     "approved_for_automatic_fit": False},
        "max_latin_advance": latin_max, "max_japanese_advance": japanese_max,
    }


NAMING_KEYBOARD_OFFSET = 0x003E22D0  # Three pages, four rows, eight cells.
NAMING_TEMPLATE_OFFSETS = (0x003E245C, 0x003E2468, 0x003E2474, 0x003E2480)
NAMING_TEMPLATE_POINTERS = 0x00A6CE38  # Player, box, caught, renamed, rival.
LATIN_NORMAL_WIDTH_ROM = 0x001FB100


def rom_naming_profiles(rom: bytes, species_max: int) -> dict:
    """Bound names entered on Unbound's actual three-page naming keyboard.

    The local keyboard is Latin-only. Foreign/traded/edited names are kept as a
    distinct, unapproved provenance; this is not a universal battle-name bound.
    """
    if rom[LATIN_NORMAL_WIDTH_ROM:LATIN_NORMAL_WIDTH_ROM + 256] != bytes(NORMAL_GLYPH_WIDTHS):
        raise ValueError("ROM normal Latin width table differs from codec")
    if _pointer(rom, 0x0009F664) != 0x08000000 + NAMING_KEYBOARD_OFFSET:
        raise ValueError("Naming input code no longer references keyboard")
    if _pointer(rom, 0x0009DB58) != 0x08000000 + NAMING_TEMPLATE_POINTERS:
        raise ValueError("Naming initialization code no longer references templates")
    offsets = [NAMING_TEMPLATE_OFFSETS[i] for i in (0, 1, 2, 2, 3)]
    pointers = [_pointer(rom, NAMING_TEMPLATE_POINTERS + i * 4) - 0x08000000
                for i in range(5)]
    if pointers != offsets:
        raise ValueError("Naming template ownership changed")
    template_lengths = [rom[offset + 1] for offset in NAMING_TEMPLATE_OFFSETS]
    if template_lengths != [7, 8, 10, 7]:
        raise ValueError("Naming template limits changed")
    keyboard = rom[NAMING_KEYBOARD_OFFSET:NAMING_KEYBOARD_OFFSET + 3 * 4 * 8]
    expected_prefix = bytes.fromhex("d5 d6 d7 d8 d9 da 00 ad")
    if len(keyboard) != 96 or keyboard[:8] != expected_prefix:
        raise ValueError("Naming keyboard changed")
    allowed = sorted(set(keyboard))
    if any(value >= 0xF7 for value in allowed):
        raise ValueError("Naming keyboard includes a control/terminator")
    keyboard_advance = max(NORMAL_GLYPH_WIDTHS[value] for value in allowed)
    latin_any_advance = max(NORMAL_GLYPH_WIDTHS[:0xF7])
    japanese_any_advance = max(NORMAL_JAPANESE_GLYPH_WIDTHS[:0xF7])

    def profile(kind: str, maximum: int) -> dict:
        return {
            "kind": kind, "max_chars_excluding_terminator": maximum,
            "naming_output_bytes_with_terminator": maximum + 1,
            "naming_template_rom": f"0x{NAMING_TEMPLATE_OFFSETS[2 if kind == 'pokemon_nickname' else 0 if kind == 'player_name' else 3]:08X}",
            "keyboard_rom": f"0x{NAMING_KEYBOARD_OFFSET:08X}",
            "accepted_byte_codes": [f"0x{value:02X}" for value in allowed],
            "unique_nonzero_codes": len(set(allowed) - {0}),
            "space_or_padding_code": "0x00",
            "local_keyboard_pages": ["latin_lowercase", "latin_uppercase", "digits_symbols"],
            "local_keyboard_japanese": False, "local_keyboard_mixed": False,
            "font": "normal Latin", "letter_spacing": 0,
            "keyboard_max_advance": keyboard_advance,
            "safe_local_keyboard_width": maximum * keyboard_advance,
            "safe_any_ordinary_latin_code_width": maximum * latin_any_advance,
            "conditional_japanese_page_width": maximum * japanese_any_advance,
            "actual_known_species_max_width": species_max if kind == "pokemon_nickname" else None,
            "confidence": "PROVEN_LOCAL_NAMING_INPUT_ONLY",
            "external_name_caveat": "Link/trade/modified save and its page state are not bounded by keyboard evidence",
        }

    return {"pokemon_nickname": profile("pokemon_nickname", 10),
            "player_name": profile("player_name", 7),
            "rival_name": profile("rival_name", 7)}


def normal_line_widths_with_placeholders(text: str, placeholder_widths: dict[int, int | None]) -> dict:
    """Compute ROM-normal-font advances with control/page state and FD bounds."""
    raw = Charmap("ja").encode(text)
    line_widths = []
    static_widths = []
    dynamic_widths = []
    unknown = []
    width = static = dynamic = 0
    page_japanese = False
    index = 0
    while index < len(raw):
        byte = raw[index]
        index += 1
        if byte == 0xFF:
            break
        if byte == 0xFC:
            command = raw[index]
            index += 1 + fc_arg_count(command)
            if command == 0x15:
                page_japanese = True
            elif command == 0x16:
                page_japanese = False
            continue
        if byte in (0xFE, 0xFA, 0xFB):
            line_widths.append(width)
            static_widths.append(static)
            dynamic_widths.append(dynamic)
            width = static = dynamic = 0
            continue
        if byte == 0xFD:
            code = raw[index]
            index += 1
            bound = placeholder_widths.get(code)
            if bound is None:
                unknown.append(f"0x{code:02X}")
            else:
                width += bound
                dynamic += bound
            continue
        advance = (10 if byte == 0 else NORMAL_JAPANESE_GLYPH_WIDTHS[byte]) if page_japanese else NORMAL_GLYPH_WIDTHS[byte]
        width += advance
        static += advance
    line_widths.append(width)
    static_widths.append(static)
    dynamic_widths.append(dynamic)
    return {"line_total_max": line_widths, "line_static": static_widths,
            "line_dynamic_max": dynamic_widths, "max_total": max(line_widths),
            "unknown_placeholder_codes": sorted(set(unknown))}


def horizontal_layout_trace(text: str) -> dict:
    """Trace normal-font cursor positions; FC 12/13 are positions, not glyphs.

    Unknown dynamic/font/button controls are recorded and must block fit
    approval. Single-byte ``\\al``/``\\ar`` are arrow glyphs, not alignment.
    """
    data = Charmap("ja").encode(text)
    x = highest = 0
    lines: list[int] = []
    events: list[dict] = []
    unsupported: list[str] = []
    japanese = False
    min_advance = 0
    i = 0
    while i < len(data):
        byte = data[i]
        i += 1
        if byte == 0xFF:
            break
        if byte in (0xFE, 0xFA, 0xFB):
            lines.append(highest)
            x = highest = 0
            continue
        if byte == 0xFC:
            command = data[i]
            i += 1
            count = fc_arg_count(command)
            args = data[i:i + count]
            i += count
            if command == 0x15:
                japanese = True
            elif command == 0x16:
                japanese = False
            elif command in (0x0D, 0x11):
                x += args[0]
            elif command == 0x12:
                x = args[0]
            elif command == 0x13:
                x = max(x, args[0])
            elif command == 0x14:
                min_advance = args[0]
            elif command == 0x06:
                unsupported.append("font_switch")
            if command in (0x0D, 0x11, 0x12, 0x13):
                events.append({"line": len(lines), "control": f"FC{command:02X}",
                               "cursor_x": x})
            highest = max(highest, x)
            continue
        if byte in (0xFD, 0xF7, 0xF8, 0xF9):
            unsupported.append(f"0x{byte:02X}")
            i += 1
            continue
        advance = (10 if byte == 0 else NORMAL_JAPANESE_GLYPH_WIDTHS[byte]) if japanese else NORMAL_GLYPH_WIDTHS[byte]
        x += max(advance, min_advance)
        highest = max(highest, x)
    lines.append(highest)
    return {"line_rightmost_x": lines, "max_rightmost_x": max(lines),
            "position_events": events, "unsupported_controls": sorted(set(unsupported))}
