#!/usr/bin/env python3
"""
CrispASR TTS Web UI v0.9 — Text Splitting with Inline Markup
No project-internal imports (stdlib only).
"""

import re


def split_text(text: str, max_chars: int = 120) -> list[dict]:
    """Split text into chunks, preserving inline markup.

    Markup syntax: [voice_name]{instruct_text} before the sentence.
    Example: [vivian]{温柔}你好啊 [ryan]{平静}嗯，好久不见

    Returns list of dicts: [{text, voice, instruct}, ...]
    """
    # 1. Parse inline markup and extract clean text + per-segment annotations
    segments = _parse_markup(text)

    # 2. Split into chunks at sentence boundaries, preserving markup
    chunks = []
    for seg in segments:
        seg_voice = seg["voice"]
        seg_instruct = seg["instruct"]
        seg_text = seg["text"]

        # Split this segment's text into sentences
        parts = _split_raw(seg_text, max_chars)
        for part in parts:
            chunks.append({
                "text": part,
                "voice": seg_voice,       # empty means inherit global
                "instruct": seg_instruct,  # empty means inherit global
            })

    return chunks


def _parse_markup(text: str) -> list[dict]:
    """Parse [voice]{instruct} markup from text.
    Returns list of {text, voice, instruct} segments.

    Markup: [voice_name]{instruct_text} followed by the text to speak.
    Voice/instruct inherit from the previous segment if not specified.
    """
    # Find all markup positions: [voice] and/or {instruct}
    markup_pattern = re.compile(r'(?:\[([^\]]*)\])?(?:\{([^}]*)\})?')

    # Build list of (position, voice, instruct) for each markup tag
    markups = []
    for m in markup_pattern.finditer(text):
        voice = m.group(1) if m.group(1) is not None else None
        instruct = m.group(2) if m.group(2) is not None else None
        # Skip empty markups at position 0 or with no content
        if voice is None and instruct is None:
            continue
        if m.start() == 0 and not voice and not instruct:
            continue
        markups.append((m.start(), m.end(), voice or "", instruct or ""))

    if not markups:
        return [{"text": text, "voice": "", "instruct": ""}]

    segments = []
    last_voice = ""
    last_instruct = ""
    last_end = 0

    for i, (start, end, voice, instruct) in enumerate(markups):
        # Text before this markup (belongs to previous segment or is preamble)
        if start > last_end:
            preamble = text[last_end:start]
            if preamble.strip():
                segments.append({"text": preamble, "voice": last_voice, "instruct": last_instruct})

        # Update current voice/instruct (empty string means keep previous)
        if voice:
            last_voice = voice
        if instruct:
            last_instruct = instruct

        # Find text after this markup until next markup or end
        next_start = markups[i + 1][0] if i + 1 < len(markups) else len(text)
        seg_text = text[end:next_start]

        if seg_text.strip():
            segments.append({"text": seg_text, "voice": last_voice, "instruct": last_instruct})

        last_end = next_start

    # Handle any remaining text after last markup
    if last_end < len(text):
        remaining = text[last_end:]
        if remaining.strip():
            segments.append({"text": remaining, "voice": last_voice, "instruct": last_instruct})

    if not segments:
        segments = [{"text": text, "voice": "", "instruct": ""}]

    return segments


def _split_raw(text: str, max_chars: int = 120) -> list[str]:
    """Split raw text (no markup) into sentence chunks."""
    # 1. Split on newlines (hard break — paragraph boundary)
    paragraphs = re.split(r'\n+', text)
    paragraphs = [p.strip() for p in paragraphs if p.strip()]

    # 2. Within each paragraph, split on sentence-end punctuation
    all_groups = []
    for p in paragraphs:
        parts = re.split(r'(?<=[。！？!?])', p)
        parts = [s.strip() for s in parts if s.strip()]
        all_groups.append(parts)

    # 3. Sub-split long sentences on commas, then merge short ones
    chunks = []
    for group in all_groups:
        refined = []
        for s in group:
            if len(s) <= max_chars:
                refined.append(s)
            else:
                parts = re.split(r'(?<=[，,；;])', s)
                parts = [p.strip() for p in parts if p.strip()]
                refined.extend(parts)

        current = ""
        for s in refined:
            if not current:
                current = s
            elif len(current) + len(s) <= max_chars:
                current += s
            else:
                chunks.append(current)
                current = s
        if current:
            chunks.append(current)

    # 4. Force-split any remaining overlong chunks
    final = []
    for c in chunks:
        if len(c) <= max_chars:
            final.append(c)
        else:
            for i in range(0, len(c), max_chars):
                final.append(c[i:i + max_chars])
    return final if final else [text]


def text_to_markup(chunks_config: list[dict], global_voice: str = "", global_instruct: str = "") -> str:
    """Convert chunks_config back to markup text for the editor.
    Only emits markup when different from global settings."""
    parts = []
    for chunk in chunks_config:
        voice = chunk.get("voice", "")
        instruct = chunk.get("instruct", "")
        text = chunk.get("text", "")

        prefix = ""
        if voice and voice != global_voice:
            prefix += f"[{voice}]"
        if instruct and instruct != global_instruct:
            prefix += f"{{{instruct}}}"
        parts.append(prefix + text)
    return " ".join(parts)
