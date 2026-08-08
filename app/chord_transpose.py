"""
Chord transposition + ChordPro-style rendering.

Song section content is stored with chords inline, directly before the
lyric syllable they belong above, e.g.:

    [E]Take me back to where
    [B]I first believed

This module does two things:

1. transpose_content(content, semitones) - shifts every chord inside
   [brackets] by N semitones, leaving all other text (including any digits
   that are part of the lyrics) completely untouched.

2. render_chordpro_line(line) - converts one line of the stored format
   into a (chord_line, lyric_line) pair of plain strings, spaced so that
   each chord lines up above the exact character it was written before.
   The frontend renders these two strings in a monospace font stacked on
   top of each other.
"""
import re

NOTES_SHARP = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
NOTES_FLAT = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]

# Recognizes a chord root: a letter A-G optionally followed by # or b.
_ROOT_RE = re.compile(r"^([A-G])([#b]?)(.*)$")
# Matches any [chord] token in stored content.
_BRACKET_RE = re.compile(r"\[([^\]\[]*)\]")


def _note_index(note: str) -> int | None:
    if note in NOTES_SHARP:
        return NOTES_SHARP.index(note)
    if note in NOTES_FLAT:
        return NOTES_FLAT.index(note)
    return None


def transpose_note(note: str, semitones: int) -> str:
    """Transpose a single note/root, e.g. 'C#' -> 'D' for +1."""
    idx = _note_index(note)
    if idx is None:
        return note  # unrecognized - leave unchanged rather than guess
    new_idx = (idx + semitones) % 12
    use_flat = "b" in note
    return (NOTES_FLAT if use_flat else NOTES_SHARP)[new_idx]


def transpose_chord(chord: str, semitones: int) -> str:
    """Transpose a full chord symbol, preserving quality/extensions and
    slash-bass notes, e.g. 'C#m7/G#' -> 'Dm7/A' for +1 semitone."""
    if semitones == 0 or not chord:
        return chord

    chord = chord.strip()
    match = _ROOT_RE.match(chord)
    if not match:
        return chord

    root, accidental, rest = match.groups()
    bass_suffix = ""

    if "/" in rest:
        quality, bass_part = rest.split("/", 1)
        bass_match = _ROOT_RE.match(bass_part)
        if bass_match:
            bass_root, bass_acc, bass_rest = bass_match.groups()
            new_bass = transpose_note(bass_root + bass_acc, semitones)
            bass_suffix = "/" + new_bass + bass_rest
        else:
            # Not a recognizable note after the slash - leave as-is.
            quality = rest
            bass_suffix = ""
    else:
        quality = rest

    new_root = transpose_note(root + accidental, semitones)
    return f"{new_root}{quality}{bass_suffix}"


def transpose_content(content: str, semitones: int) -> str:
    """Transpose every [chord] token in a block of stored section content.
    Everything outside brackets (the lyrics) is left byte-for-byte
    identical, so numbers/text in lyrics are never touched."""
    if not content or semitones == 0:
        return content

    def _replace(m: re.Match) -> str:
        return "[" + transpose_chord(m.group(1), semitones) + "]"

    return _BRACKET_RE.sub(_replace, content)


def transpose_key(key: str | None, semitones: int) -> str | None:
    """Transpose a song key label like 'E', 'C#m', 'Bb' etc."""
    if not key or semitones == 0:
        return key
    match = _ROOT_RE.match(key.strip())
    if not match:
        return key
    root, accidental, rest = match.groups()
    return transpose_note(root + accidental, semitones) + rest


def render_chordpro_line(line: str) -> dict:
    """Convert one stored line (with inline [chords]) into a chord line and
    a lyric line, aligned by character position, for monospace rendering.
    """
    chord_positions: list[tuple[int, str]] = []
    lyric_chars: list[str] = []
    pos = 0
    i = 0
    n = len(line)
    while i < n:
        if line[i] == "[":
            end = line.find("]", i)
            if end == -1:
                # Unterminated bracket - treat rest as literal text.
                lyric_chars.append(line[i])
                pos += 1
                i += 1
                continue
            chord = line[i + 1 : end]
            chord_positions.append((pos, chord))
            i = end + 1
        else:
            lyric_chars.append(line[i])
            pos += 1
            i += 1

    lyric_line = "".join(lyric_chars)

    if not chord_positions:
        return {"chord_line": "", "lyric_line": lyric_line, "has_chords": False}

    chord_chars: list[str] = []
    for position, chord in chord_positions:
        while len(chord_chars) < position:
            chord_chars.append(" ")
        # If two chords would collide (rare), separate with a space.
        if len(chord_chars) > position:
            chord_chars.append(" ")
        chord_chars.extend(list(chord))
    chord_line = "".join(chord_chars)

    return {"chord_line": chord_line, "lyric_line": lyric_line, "has_chords": True}


def render_section_content(content: str, semitones: int = 0) -> list[dict]:
    """Transpose (if needed) then render a whole section's content into a
    list of {chord_line, lyric_line, has_chords} rows, one per source
    line, ready for the frontend to display in a monospace block."""
    transposed = transpose_content(content, semitones)
    lines = transposed.split("\n")
    return [render_chordpro_line(line) for line in lines]
