"""Render the parsed block tree to plain text — Markdown stripped.

Same subset as :mod:`md_extract.html_renderer`: paragraphs, ordered /
unordered lists with nesting, code fences (kept verbatim), blockquotes,
and the common inline markers (``**bold**``, ``*em*``, ``` `code` ```,
``[text](url)``, ``![alt](url)``).

Output rules:
- Paragraphs are separated by one blank line.
- List items are emitted with a ``- `` (unordered) or ``1. `` (ordered)
  marker; nested children indent by four spaces.
- Code blocks reproduce their original lines unchanged (no marker).
- Blockquotes prefix each output line with ``> ``.
"""

from __future__ import annotations

import re
from typing import Iterable, List

from md_extract.blocks import Block


_INLINE_CODE_RE = re.compile(r"`([^`]+)`")
_IMG_RE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)\)")
_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
_BOLD_RE = re.compile(r"\*\*([^*]+)\*\*")
_EM_STAR_RE = re.compile(r"(?<![*\w])\*([^*\n]+?)\*(?!\w)")
_EM_UNDER_RE = re.compile(r"(?<![\w_])_([^_\n]+?)_(?!\w)")


def strip_inline(text: str) -> str:
    """Remove the inline-markdown markers, leaving the visible text."""
    if not text:
        return ""
    out = _INLINE_CODE_RE.sub(lambda m: m.group(1), text)
    out = _IMG_RE.sub(lambda m: m.group(1) or m.group(2), out)
    out = _LINK_RE.sub(lambda m: m.group(1), out)
    out = _BOLD_RE.sub(lambda m: m.group(1), out)
    out = _EM_STAR_RE.sub(lambda m: m.group(1), out)
    out = _EM_UNDER_RE.sub(lambda m: m.group(1), out)
    return out


def render_text(blocks: Iterable[Block], indent: str = "") -> str:
    """Render ``blocks`` to plain text. ``indent`` is prepended to every line."""
    parts: List[str] = []
    for b in blocks:
        parts.append(_render(b, indent))
    return "\n\n".join(p for p in parts if p)


def _render(block: Block, indent: str) -> str:
    if block.kind == "paragraph":
        return indent + strip_inline(block.text)

    if block.kind == "code":
        return "\n".join(indent + line for line in block.text.split("\n"))

    if block.kind == "blockquote":
        inner = (
            render_text(block.children) if block.children else strip_inline(block.text)
        )
        out_lines: List[str] = []
        for line in inner.split("\n"):
            out_lines.append(indent + ("> " + line if line else ">"))
        return "\n".join(out_lines)

    if block.kind in ("list", "ordered_list"):
        ordered = block.kind == "ordered_list"
        item_lines: List[str] = []
        for i, item in enumerate(block.children, start=1):
            marker = f"{i}. " if ordered else "- "
            head = indent + marker + strip_inline(item.text)
            piece_lines = [head]
            if item.children:
                child_indent = indent + (" " * len(marker))
                piece_lines.append(render_text(item.children, child_indent))
            item_lines.append("\n".join(piece_lines))
        return "\n".join(item_lines)

    return indent + strip_inline(block.text)
