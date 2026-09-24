from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib.pcs_text import Charmap, decode_pcs


@pytest.mark.parametrize(
    "text",
    [
        "ABC xyz 012!?.-",
        "Ciao [player]!\n[black]Premi \\btn01",
        "\\pk\\mn \\qoOK\\qc",
        "\\CC100102\\?2A\\9AA\\\\AA",
    ],
)
def test_pcs_encode_decode_roundtrip_for_text_and_controls(text):
    cmap = Charmap(target_lang="it")

    encoded = cmap.encode(text)
    decoded = decode_pcs(encoded)

    assert decoded.terminated
    assert decoded.byte_length == len(encoded)
    assert decoded.text == text


@pytest.mark.parametrize(
    "input_text,expected_decoded",
    [
        ("\\pnon possiamo farlo", "\n\nnon possiamo farlo"),
        ("\\pnord della citta", "\n\nnord della citta"),
        ("\\pnecessario per la missione", "\n\nnecessario per la missione"),
        ("\\pNon possiamo farlo", "\n\nNon possiamo farlo"),
        ("\\pkamu lanjut", "\n\nkamu lanjut"),
        ("ottenere il pacco\n\nnecessario", "ottenere il pacco\n\nnecessario"),
        ("\\Possiamo andare", "Possiamo andare"),
        ("\\Po\\Ke", "\\Po\\Ke"),
    ],
)
def test_pcs_paragraph_preserves_words_starting_with_n_and_k(input_text, expected_decoded):
    cmap = Charmap(target_lang="it")

    encoded = cmap.encode(input_text)
    decoded = decode_pcs(encoded)

    assert decoded.terminated
    assert decoded.text == expected_decoded


def test_pcs_byte_length_excludes_terminator():
    cmap = Charmap(target_lang="it")

    encoded = cmap.encode("AB[player]")

    assert encoded.endswith(bytes([0xFF]))
    assert cmap.byte_length("AB[player]") == len(encoded) - 1


def test_japanese_encode_exact_bytes():
    cmap = Charmap(target_lang="ja")

    assert cmap.encode("[japanese]こんにちは[latin]") == bytes(
        [0xFC, 0x15, 0x0A, 0x2E, 0x16, 0x11, 0x1A, 0xFC, 0x16, 0xFF]
    )


def test_japanese_decode_exact_bytes():
    encoded = bytes([0xFC, 0x15, 0x0A, 0x2E, 0x16, 0x11, 0x1A, 0xFC, 0x16, 0xFF])

    decoded = decode_pcs(encoded)

    assert decoded.terminated
    assert decoded.byte_length == len(encoded)
    assert decoded.text == "[japanese]こんにちは[latin]"


def test_japanese_encode_decode_roundtrip():
    cmap = Charmap(target_lang="ja")
    text = "[japanese]こんにちは[latin]"

    assert decode_pcs(cmap.encode(text)).text == text


def test_japanese_kana_and_symbol_table_boundaries():
    cmap = Charmap(target_lang="ja")
    text = "[japanese]あぽアポ　！？。ー‥[latin]"

    encoded = cmap.encode(text)

    assert encoded == bytes(
        [
            0xFC,
            0x15,
            0x01,
            0x4F,
            0x51,
            0x9F,
            0x00,
            0xAB,
            0xAC,
            0xAD,
            0xAE,
            0xB0,
            0xFC,
            0x16,
            0xFF,
        ]
    )
    assert decode_pcs(encoded).text == text


def test_japanese_to_latin_page_switch():
    cmap = Charmap(target_lang="ja")
    text = "[japanese]こ[latin]A"

    encoded = cmap.encode(text)

    assert encoded == bytes([0xFC, 0x15, 0x0A, 0xFC, 0x16, 0xBB, 0xFF])
    assert decode_pcs(encoded).text == text


def test_latin_japanese_latin_mixed_roundtrip():
    cmap = Charmap(target_lang="ja")
    text = "ABC[japanese]こんにちは[latin]xyz"

    assert decode_pcs(cmap.encode(text)).text == text


def test_unknown_japanese_character_raises_encode_error():
    cmap = Charmap(target_lang="ja")

    with pytest.raises(UnicodeEncodeError, match="Japanese PCS page"):
        cmap.encode("[japanese]漢[latin]")


def test_japanese_page_preserves_newline_scroll_and_paragraph_controls():
    cmap = Charmap(target_lang="ja")
    text = "[japanese]こ\nん\\lに\n\nち[latin]"

    encoded = cmap.encode(text)

    assert bytes([0xFE]) in encoded
    assert bytes([0xFA]) in encoded
    assert bytes([0xFB]) in encoded
    assert decode_pcs(encoded).text == text
