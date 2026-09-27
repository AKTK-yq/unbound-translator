"""Lossless FE/FA/FB boundaries for reviewed Japanese dialogue segments.

The raw parser skips arguments of multi-byte PCS controls.  A translator may
replace text *inside* each segment, but never owns the boundary controls.
"""

from __future__ import annotations

from lib.pcs_text import decode_pcs, fc_arg_count


BOUNDARY_BYTES = {0xFE: "FE", 0xFA: "FA", 0xFB: "FB"}
BOUNDARY_TEXT = {"FE": "\n", "FA": "\\l", "FB": "\n\n"}


def parse_raw_segments(raw: bytes, *, rom_offset: int = 0) -> list[dict]:
    """Split a terminated PCS string at actual control bytes, not text indexes."""
    segments: list[dict] = []
    start = 0
    index = 0
    while index < len(raw):
        byte = raw[index]
        if byte in BOUNDARY_BYTES or byte == 0xFF:
            piece = decode_pcs(raw[start:index] + b"\xff")
            if not piece.terminated or piece.byte_length != index - start + 1:
                raise ValueError("Invalid PCS segment")
            segments.append({
                "text": piece.text,
                "after_control": BOUNDARY_BYTES.get(byte),
                "control_offset": rom_offset + index if byte != 0xFF else None,
            })
            if byte == 0xFF:
                if index != len(raw) - 1:
                    raise ValueError("Bytes after PCS terminator")
                return segments
            index += 1
            start = index
            continue
        if byte == 0xFC:
            if index + 1 >= len(raw):
                raise ValueError("Truncated FC control")
            index += 2 + fc_arg_count(raw[index + 1])
        elif byte in (0xFD, 0xF7, 0xF8, 0xF9):
            index += 2
        else:
            index += 1
        if index > len(raw):
            raise ValueError("Truncated PCS control argument")
    raise ValueError("Unterminated PCS string")


def join_segments(segments: list[dict], texts: list[str] | None = None) -> str:
    if texts is not None and len(texts) != len(segments):
        raise ValueError("Segment count mismatch")
    parts = []
    for index, segment in enumerate(segments):
        parts.append(segment["text"] if texts is None else texts[index])
        control = segment.get("after_control")
        if control not in (*BOUNDARY_TEXT, None):
            raise ValueError(f"Unknown boundary control: {control}")
        if control:
            parts.append(BOUNDARY_TEXT[control])
    return "".join(parts)


def reconstruct_reviewed_segments(original: str, segments: list[dict],
                                  translated_segments: list[str]) -> str:
    """Fail closed unless source structure and every translated unit are valid."""
    if not isinstance(segments, list) or not isinstance(translated_segments, list):
        raise ValueError("Reviewed FA segments required")
    if not segments or segments[-1].get("after_control") is not None:
        raise ValueError("Missing final source segment")
    if join_segments(segments) != original:
        raise ValueError("Source segment structure differs from original")
    if not any(segment.get("after_control") == "FA" for segment in segments):
        raise ValueError("Source has no FA boundary")
    if len(segments) != len(translated_segments):
        raise ValueError("Translated segment count mismatch")
    for source, text in zip(segments, translated_segments):
        if not isinstance(text, str) or (source["text"].strip() and not text.strip()):
            raise ValueError("Empty translated segment")
        if not source["text"].strip() and text.strip():
            raise ValueError("Text inserted into empty source segment")
        if "\n" in text or any(token in text for token in ("\\l", "\\p", "\\n")):
            raise ValueError("Translator inserted a layout boundary")
        if "[japanese]" in text or "[latin]" in text:
            raise ValueError("Page switches belong to controlfix")
    return join_segments(segments, translated_segments)
