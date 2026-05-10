"""Header detection for Markdown documents.

The parser walks the document line by line while tracking which "block
context" each line belongs to. Headers found inside fenced code blocks,
math blocks, tables, or YAML front matter are intentionally ignored.
"""

from __future__ import annotations

import re
from typing import List, NamedTuple, Tuple


class Header(NamedTuple):
    """A single header occurrence detected in the source document."""

    line: int
    level: int
    title: str


# ATX header: optional indentation, 1–6 #s, required space, title, optional
# trailing #s.  We allow any amount of leading whitespace because the spec
# explicitly calls for "indentation support".
_ATX_RE = re.compile(r"^[ \t]*(#{1,6})[ \t]+(.+?)(?:[ \t]+#+[ \t]*)?$")

# Fenced code block opener: 3+ backticks or 3+ tildes with up to 3 leading
# spaces (CommonMark restricts the indent of a fence to <4 spaces).
_FENCE_RE = re.compile(r"^[ ]{0,3}(`{3,}|~{3,})")

# Setext underlines.
_SETEXT_H1_RE = re.compile(r"^[ ]{0,3}=+[ \t]*$")
_SETEXT_H2_RE = re.compile(r"^[ ]{0,3}-+[ \t]*$")

# Quick check for "looks like a list item" — used to disambiguate setext h2
# from a regular --- horizontal rule below a paragraph.
_LIST_RE = re.compile(r"^[ \t]*([-*+]|\d+[.)])[ \t]")

# Table separator row: |---|---| or :---:|---: etc.
_TABLE_SEP_RE = re.compile(r"^[ \t]*\|?[ \t]*:?-+:?([ \t]*\|[ \t]*:?-+:?)+[ \t]*\|?[ \t]*$")


def _closing_fence_re(fence_char: str, fence_len: int) -> re.Pattern[str]:
    return re.compile(
        r"^[ ]{0,3}" + re.escape(fence_char) + r"{" + str(fence_len) + r",}[ \t]*$"
    )


def parse(content: str) -> Tuple[List[Header], List[str]]:
    """Return ``(headers, lines)`` for ``content``.

    ``lines`` is the document split on ``\n`` (newlines stripped) and is
    shared with :class:`markdown_extractor.section.Section` so each section can
    rebuild its own slice of the source on demand.
    """
    lines = content.split("\n")
    headers: List[Header] = []

    in_code = False
    fence_char = ""
    fence_len = 0
    closing_re: re.Pattern[str] | None = None

    in_math = False

    in_yaml = False
    yaml_checked = False

    in_table = False

    for i, line in enumerate(lines):
        stripped = line.strip()

        # ---------- YAML front matter (only at the very top of the file)
        if not yaml_checked:
            yaml_checked = True
            if stripped == "---":
                in_yaml = True
                continue

        if in_yaml:
            if stripped == "---" or stripped == "...":
                in_yaml = False
            continue

        # ---------- Fenced code blocks
        if in_code:
            assert closing_re is not None
            if closing_re.match(line):
                in_code = False
                closing_re = None
            continue

        m_fence = _FENCE_RE.match(line)
        if m_fence:
            in_code = True
            marker = m_fence.group(1)
            fence_char = marker[0]
            fence_len = len(marker)
            closing_re = _closing_fence_re(fence_char, fence_len)
            in_table = False
            continue

        # ---------- Math blocks ($$ ... $$)
        if stripped == "$$":
            in_math = not in_math
            in_table = False
            continue
        if in_math:
            continue

        # ---------- Tables
        # A table block runs from the first pipe-line through a blank line.
        # Headers inside a table are extremely unusual but we still skip
        # them to honour the spec.
        if not stripped:
            in_table = False
        elif _TABLE_SEP_RE.match(line) or "|" in stripped:
            # Stay in table mode while we see pipe-lines or separators.
            if in_table or _TABLE_SEP_RE.match(line) or stripped.startswith("|"):
                in_table = True
                # Continue: a pipe-line itself can never be a header.
                continue

        if in_table:
            continue

        # ---------- ATX headers
        m_atx = _ATX_RE.match(line)
        if m_atx:
            level = len(m_atx.group(1))
            title = m_atx.group(2).strip().rstrip("#").rstrip()
            if title:
                headers.append(Header(line=i, level=level, title=title))
            continue

        # ---------- Setext headers (=== / ---)
        # The underline lives on the *current* line; the title is the
        # previous line.  We only accept it when the previous line is
        # genuine paragraph text (not a list item, not blank, and not
        # already classified as something else).
        if i > 0 and stripped:
            prev = lines[i - 1]
            prev_stripped = prev.strip()
            if prev_stripped and not _LIST_RE.match(prev) and not _ATX_RE.match(prev):
                if _SETEXT_H1_RE.match(line):
                    headers.append(Header(line=i - 1, level=1, title=prev_stripped))
                    continue
                if _SETEXT_H2_RE.match(line) and prev_stripped != "---":
                    headers.append(Header(line=i - 1, level=2, title=prev_stripped))
                    continue

    return headers, lines
