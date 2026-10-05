"""Text normalisation for quote matching, with a map back to original offsets.

Rules (see docs/decisions.md):
- NFKC (handles ligatures such as "ﬁ"), then case folding
- soft hyphens and zero-width characters are removed
- hyphens and dashes are dropped; whitespace straight after one is dropped
  too, which joins words hyphenated across a line break
- commas between digits are dropped ("1,500" -> "1500")
- a full stop between digits is kept ("1.50" stays distinct from "150")
- "$" and "%" are kept
- any other punctuation becomes a space; whitespace runs collapse to one space
"""

from __future__ import annotations

import re
import unicodedata
from decimal import Decimal, InvalidOperation

_INVISIBLE = {"­", "​", "‌", "‍", "⁠", "﻿"}
_DASHES = set("-‐‑‒–—―−﹘﹣－")
_KEEP_SYMBOLS = {"$", "%"}


def normalise(text: str) -> tuple[str, list[int]]:
    """Return (normalised text, offsets), where offsets[i] is the index in
    `text` of the character that produced normalised character i."""
    # Pass 1: NFKC + casefold per character, drop invisibles, keep provenance.
    chars: list[tuple[str, int]] = []
    for i, ch in enumerate(text):
        if ch in _INVISIBLE:
            continue
        for c in unicodedata.normalize("NFKC", ch).casefold():
            if c not in _INVISIBLE:
                chars.append((c, i))

    # Pass 2: punctuation and whitespace.
    out: list[str] = []
    offs: list[int] = []
    n = len(chars)
    skip_space = False
    for k, (c, i) in enumerate(chars):
        if c in _DASHES:
            skip_space = True
            continue
        if c.isspace():
            if skip_space:
                continue
            _space(out, offs, i)
            continue
        skip_space = False
        if c.isalnum() or c in _KEEP_SYMBOLS:
            out.append(c)
            offs.append(i)
            continue
        prev_digit = k > 0 and chars[k - 1][0].isdigit()
        next_digit = k + 1 < n and chars[k + 1][0].isdigit()
        if c == "," and prev_digit and next_digit:
            continue
        if c == "." and prev_digit and next_digit:
            out.append(c)
            offs.append(i)
            continue
        _space(out, offs, i)

    if out and out[-1] == " ":
        out.pop()
        offs.pop()
    return "".join(out), offs


def _space(out: list[str], offs: list[int], i: int) -> None:
    if out and out[-1] != " ":
        out.append(" ")
        offs.append(i)


def norm(text: str) -> str:
    return normalise(text)[0]


def word_count(normalised: str) -> int:
    return len(normalised.split()) if normalised else 0


def find_words(haystack: str, needle: str, start: int = 0) -> int:
    """Find `needle` in `haystack` (both normalised) at word boundaries.
    Returns the start index, or -1."""
    if not needle:
        return -1
    pos = haystack.find(needle, start)
    while pos != -1:
        end = pos + len(needle)
        if (pos == 0 or haystack[pos - 1] == " ") and (end == len(haystack) or haystack[end] == " "):
            return pos
        pos = haystack.find(needle, pos + 1)
    return -1


# Numeric facts: money, percentages, day and hour counts, in canonical form.
# Plan documents often spell durations out ("five business days"), so number
# words count too. Hyphens are already dropped: "forty-five" is "fortyfive".
_NUMBER_WORDS = {
    w: str(i)
    for i, w in enumerate(
        "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen "
        "fifteen sixteen seventeen eighteen nineteen twenty".split()
    )
}
_NUMBER_WORDS.update({"thirty": "30", "fortyfive": "45", "sixty": "60", "ninety": "90"})
_NUM = r"(\d+(?:\.\d+)?|" + "|".join(sorted(_NUMBER_WORDS, key=len, reverse=True)) + r")"
_MONEY = re.compile(r"\$ ?(\d+(?:\.\d+)?)")
_PERCENT = re.compile(r"(\d+(?:\.\d+)?) ?%")
_DAYS = re.compile(r"\b" + _NUM + r" (?:calendar |business |working )?days?\b")
_HOURS = re.compile(r"\b" + _NUM + r" hours?\b")


def numeric_facts(normalised: str) -> set[tuple[str, str]]:
    """Money amounts, percentages, day and hour counts in normalised text, as
    ("money" | "percent" | "days" | "hours", canonical number)."""
    facts: set[tuple[str, str]] = set()
    for kind, pattern in (("money", _MONEY), ("percent", _PERCENT), ("days", _DAYS), ("hours", _HOURS)):
        for m in pattern.finditer(normalised):
            facts.add((kind, _canonical(m.group(1))))
    return facts


def _canonical(num: str) -> str:
    if num in _NUMBER_WORDS:
        return _NUMBER_WORDS[num]
    try:
        d = Decimal(num).normalize()
    except InvalidOperation:
        return num
    return format(d, "f")
