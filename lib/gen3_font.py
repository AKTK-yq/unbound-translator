"""Pixel metrics for the FireRed normal Latin and Japanese font pages."""

from __future__ import annotations

from lib.pcs_text import Charmap, fc_arg_count

# sFontNormalLatinGlyphWidths from pret/pokefirered src/text.c. Values are
# glyph advances, including inter-glyph spacing, indexed by encoded byte.
NORMAL_GLYPH_WIDTHS = (
    6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6,
    8, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6,
    6, 6, 6, 6, 6, 8, 6, 6, 6, 6, 6, 6, 9, 8, 8, 6,
    6, 6, 6, 6, 10, 8, 5, 6, 6, 6, 6, 6, 6, 6, 6, 6,
    6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6,
    6, 6, 6, 8, 8, 8, 8, 8, 8, 4, 6, 8, 5, 5, 6, 6,
    6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6,
    6, 6, 6, 6, 6, 6, 6, 6, 6, 12, 12, 12, 12, 6, 6, 6,
    6, 6, 6, 6, 8, 8, 8, 6, 6, 6, 6, 6, 6, 6, 6, 6,
    6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6,
    8, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 5, 6, 5,
    6, 6, 6, 3, 3, 6, 6, 8, 5, 9, 6, 6, 6, 6, 6, 6,
    6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6,
    6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 5, 6, 6, 4, 6, 5,
    5, 6, 5, 6, 6, 6, 5, 5, 5, 6, 6, 6, 6, 6, 6, 8,
    5, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6,
)

# Unbound ROM 0x0020F500 (GBA 0x0820F500), 0x118 bytes. The normal
# Japanese width table is byte-for-byte identical in the local FireRed JPN ROM.
NORMAL_JAPANESE_GLYPH_WIDTHS = bytes.fromhex(
    "00 0a 0a 0a 0a 0a 0a 0a 0a 0a 0a 0a 0a 0a 0a 0a 0a 0a 0a 0a 0a 0a 0a 0a 0a 0a 0a 0a 0a 0a 0a 0a"
    "0a 0a 0a 0a 0a 0a 0a 0a 0a 0a 0a 0a 0a 0a 0a 09 09 09 09 09 09 09 09 0a 0a 0a 0a 0a 0a 0a 0a 0a"
    "0a 0a 0a 0a 0a 0a 0a 0a 0a 0a 0a 0a 0a 0a 0a 0a 09 0a 0a 0a 0a 0a 0a 0a 0a 0a 0a 0a 0a 0a 0a 0a"
    "0a 0a 0a 0a 0a 0a 0a 0a 0a 0a 0a 0a 0a 0a 0a 0a 0a 0a 0a 0a 0a 0a 0a 0a 0a 0a 0a 0a 0a 0a 0a 09"
    "09 09 09 09 09 09 09 0a 0a 0a 0a 0a 0a 0a 0a 0a 0a 0a 0a 0a 0a 0a 0a 0a 0a 0a 0a 0a 0a 0a 0a 0a"
    "09 08 07 08 08 08 08 08 08 08 08 05 09 0a 0a 0a 08 0a 0a 0a 0a 08 08 08 0a 0a 08 06 06 06 06 06"
    "06 06 06 06 06 06 06 06 06 06 06 06 06 06 06 06 06 06 06 06 06 06 06 06 06 06 05 06 06 02 04 06"
    "03 06 06 06 06 06 06 06 06 06 06 06 06 06 06 06 05 06 06 06 06 06 06 00 00 00 00 00 00 00 00 00"
    "0a 0a 0a 0a 0a 0a 0a 0a 0a 0a 0a 0a 0a 0a 0a 0a 0a 0a 0a 0a 0a 0a 0a 00"
)

RUNTIME_BUFFER_WIDTH = 54


def text_pixel_width(text: str, cmap: Charmap | None = None) -> int:
    """Return the rendered width of one line, ignoring layout/control bytes."""
    cmap = cmap or Charmap("it")
    encoded = cmap.encode(text)
    width = 0
    index = 0
    japanese_page = False
    while index < len(encoded):
        byte = encoded[index]
        index += 1
        if byte == 0xFF:
            break
        if byte == 0xFC:
            if index >= len(encoded):
                break
            command = encoded[index]
            index += 1 + fc_arg_count(command)
            if command == 0x15:
                japanese_page = True
            elif command == 0x16:
                japanese_page = False
            continue
        if byte == 0xFD:
            width += RUNTIME_BUFFER_WIDTH
            index += 1
            continue
        if byte in {0xFA, 0xFB, 0xFE}:
            continue
        if japanese_page:
            # Glyph 0 is a space: the ROM's special-case renderer assigns it
            # a 10-pixel advance even though width-table byte 0 is zero.
            width += 10 if byte == 0 else NORMAL_JAPANESE_GLYPH_WIDTHS[byte]
        else:
            width += NORMAL_GLYPH_WIDTHS[byte]
    return width
