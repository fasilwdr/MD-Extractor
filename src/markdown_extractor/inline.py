"""Inline-markdown tokenizer — the single source for inline regexes.

The block parser in :mod:`markdown_extractor.blocks` builds the tree of
paragraphs/lists/quotes. This module is the inline pass: given the text
of a paragraph or list item, it produces a flat list of inline tokens
(``image``, ``link``, ``code``, ``bold``, ``em``, ``text``) so consumers
of ``to_dict`` / ``to_json`` get the same granularity that ``to_html``
already exposes via the rendered ``<img>`` / ``<a>`` / ``<strong>`` tags.

Both renderers (:mod:`markdown_extractor.html_renderer`,
:mod:`markdown_extractor.text_renderer`) import the regex constants from
here, so the three call sites can't drift out of sync.

Token shape — each inline is a :class:`~markdown_extractor.blocks.Block`
reusing the existing fields:

==========  =======================  =================
kind        ``text``                 ``info``
==========  =======================  =================
``image``   alt text                 src URL
``link``    label text               href URL
``code``    code content             (unused)
``bold``    bold content             (unused)
``em``      italic content           (unused)
``text``    plain text segment       (unused)
==========  =======================  =================

Limitation — tokenization is **flat**. ``**[link](url)**`` emits one
``bold`` token whose ``text`` is ``"[link](url)"``; the link is not
recursively split out. Callers needing nested structure can re-run
:func:`parse_inlines` on the inner ``text``. The HTML renderer still
resolves the common nested cases through substitution order, so
``to_html`` output is unchanged.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, List, Optional, Tuple

from markdown_extractor._collections import BlockList

if TYPE_CHECKING:
    from markdown_extractor.blocks import Block


_INLINE_CODE_RE = re.compile(r"`([^`]+)`")
_IMG_RE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)\)")
_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
_BOLD_RE = re.compile(r"\*\*([^*]+)\*\*")
_EM_STAR_RE = re.compile(r"(?<![*\w])\*([^*\n]+?)\*(?!\w)")
_EM_UNDER_RE = re.compile(r"(?<![\w_])_([^_\n]+?)_(?!\w)")


# Priority for tie-breaking when two patterns match at the same offset.
# Code wins so its contents are never re-tokenized; image beats link so
# ``![alt](src)`` doesn't degrade to a link match on the ``[alt](src)``
# tail; bold beats em so ``**x**`` isn't read as ``*`` + em + ``*``.
_PATTERNS: List[Tuple[str, "re.Pattern[str]"]] = [
    ("code", _INLINE_CODE_RE),
    ("image", _IMG_RE),
    ("link", _LINK_RE),
    ("bold", _BOLD_RE),
    ("em", _EM_STAR_RE),
    ("em", _EM_UNDER_RE),
]


def parse_inlines(text: str) -> BlockList:
    """Tokenize ``text`` into a flat :class:`BlockList` of inline ``Block``s.

    Returns an empty list when ``text`` contains no inline markers — a
    plain-text paragraph carries no ``inlines`` payload, keeping the
    ``to_dict`` output quiet for the common case. Otherwise the returned
    list includes ``text`` tokens for the segments between matches, so
    the original ordering is preserved end-to-end.
    """
    # Lazy import to avoid a top-level cycle: blocks.py imports this
    # module, and Block lives there.
    from markdown_extractor.blocks import Block

    if not text:
        return BlockList()

    tokens: List["Block"] = []
    pos = 0
    n = len(text)

    while pos < n:
        best: Optional[Tuple[int, int, str, "re.Match[str]"]] = None
        for prio, (kind, pat) in enumerate(_PATTERNS):
            m = pat.search(text, pos)
            if m is None:
                continue
            key = (m.start(), prio)
            if best is None or key < (best[0], best[1]):
                best = (m.start(), prio, kind, m)

        if best is None:
            # No more matches — the remainder is a plain text segment.
            tokens.append(Block(kind="text", text=text[pos:]))
            break

        start, _, kind, m = best
        if start > pos:
            tokens.append(Block(kind="text", text=text[pos:start]))

        if kind == "image":
            tokens.append(Block(kind="image", text=m.group(1), info=m.group(2)))
        elif kind == "link":
            tokens.append(Block(kind="link", text=m.group(1), info=m.group(2)))
        else:  # code, bold, em
            tokens.append(Block(kind=kind, text=m.group(1)))

        pos = m.end()

    # If nothing structural was found, suppress the lone text token so
    # the paragraph's ``inlines`` stays empty (and is omitted from
    # ``to_dict``). The raw text is already on ``Block.text``.
    if not any(t.kind != "text" for t in tokens):
        return BlockList()
    return BlockList(tokens)
