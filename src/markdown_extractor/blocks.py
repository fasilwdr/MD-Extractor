"""Body-block parser — turn a section's prose into a tree of blocks.

The header parser in :mod:`markdown_extractor.parser` splits a document by header
*level* and stops there: it never looks inside a section's body. This
module is the second pass — it walks the lines of a single section and
produces a small block tree (paragraphs, lists, list items, code blocks,
blockquotes) so callers can ask for ``Section.to_list()``, embed the
structure in ``Section.to_dict()``, or render it to HTML.

The grammar is intentionally a CommonMark *subset* — enough to do useful
things with typical README/spec/FAQ-style documents without growing into
a full Markdown parser. The header parser stays the source of truth for
the document's outline; this module only sees the body text in between.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterator, List, Optional

from markdown_extractor.text_renderer import strip_inline


# A block is one of:
#   "paragraph"     — a run of non-empty, non-structural lines
#   "list"          — bullet (-, *, +) container; children are list_items
#   "ordered_list"  — numbered (1. 1)) container; children are list_items
#   "list_item"     — one item; children are nested lists or paragraphs
#   "code"          — fenced block (``` or ~~~); language stored in ``info``
#   "blockquote"    — `>`-prefixed run; children are inner blocks
@dataclass
class Block:
    kind: str
    text: str = ""
    children: List["Block"] = field(default_factory=list)
    info: str = ""  # code language, list marker style, etc.

    def walk(self) -> Iterator["Block"]:
        yield self
        for child in self.children:
            yield from child.walk()

    def to_dict(self) -> dict:
        out: dict = {"kind": self.kind, "text": self.text}
        if self.info:
            out["info"] = self.info
        if self.children:
            out["children"] = [c.to_dict() for c in self.children]
        return out

    @property
    def text_plain(self) -> str:
        """``self.text`` with inline Markdown markers stripped.

        ``**bold**`` → ``bold``, ``[label](url)`` → ``label``, etc.
        Returns ``""`` for the null sentinel returned by :meth:`get`.
        """
        return strip_inline(self.text)

    def get(self, *indices: int) -> "Block":
        """Soft index walk into ``self.children`` by integer index.

        ``block.get(1, 0)`` is equivalent to ``block.children[1].children[0]``
        but returns a *null Block* sentinel (whose ``text_plain`` is
        ``""``) if any index is out of range. Subsequent ``.get()`` calls
        on the null block keep returning the null block, so chains like
        ``block.get(99).get(0).text_plain`` are safe.
        """
        node: "Block" = self
        for i in indices:
            if not node:
                return _null_block()
            n = len(node.children)
            if not n or i < -n or i >= n:
                return _null_block()
            node = node.children[i]
        return node

    def __bool__(self) -> bool:
        """``False`` only for the null sentinel returned by :meth:`get`.

        Real blocks always have a non-empty ``kind`` (the parser assigns
        one); the sentinel uses ``kind=""``.
        """
        return self.kind != ""


_FENCE_RE = re.compile(r"^([ ]{0,3})(`{3,}|~{3,})(.*)$")
_BULLET_RE = re.compile(r"^(?P<indent>[ \t]*)(?P<marker>[-*+])[ \t]+(?P<rest>.*)$")
_ORDERED_RE = re.compile(r"^(?P<indent>[ \t]*)(?P<num>\d+)(?P<sep>[.)])[ \t]+(?P<rest>.*)$")
_BLOCKQUOTE_RE = re.compile(r"^[ ]{0,3}>[ ]?(?P<rest>.*)$")


def _expand_indent(s: str) -> int:
    """Visual column of the first non-whitespace char (tabs = 4 cols)."""
    col = 0
    for ch in s:
        if ch == " ":
            col += 1
        elif ch == "\t":
            col += 4 - (col % 4)
        else:
            break
    return col


def parse_blocks(text: str) -> List[Block]:
    """Parse a section's body text into a list of top-level blocks."""
    if not text or not text.strip():
        return []
    lines = text.split("\n")
    return _parse(lines, 0, len(lines), base_indent=0)


def _parse(lines: List[str], start: int, end: int, base_indent: int) -> List[Block]:
    blocks: List[Block] = []
    i = start
    while i < end:
        line = lines[i]
        stripped = line.strip()

        # Skip blank lines between blocks.
        if not stripped:
            i += 1
            continue

        indent = _expand_indent(line)
        if indent < base_indent:
            break

        # Code fence.
        m_fence = _FENCE_RE.match(line)
        if m_fence:
            block, i = _consume_fence(lines, i, end, m_fence)
            blocks.append(block)
            continue

        # Blockquote.
        if _BLOCKQUOTE_RE.match(line):
            block, i = _consume_blockquote(lines, i, end)
            blocks.append(block)
            continue

        # Lists.
        m_b = _BULLET_RE.match(line)
        m_o = _ORDERED_RE.match(line)
        if m_b or m_o:
            block, i = _consume_list(lines, i, end, base_indent, ordered=m_o is not None)
            blocks.append(block)
            continue

        # Paragraph.
        block, i = _consume_paragraph(lines, i, end, base_indent)
        blocks.append(block)

    return blocks


def _consume_fence(lines, i, end, m_fence):
    marker = m_fence.group(2)
    info = m_fence.group(3).strip()
    fence_char = marker[0]
    fence_len = len(marker)
    body: List[str] = []
    j = i + 1
    closer = re.compile(r"^[ ]{0,3}" + re.escape(fence_char) + r"{" + str(fence_len) + r",}[ \t]*$")
    while j < end and not closer.match(lines[j]):
        body.append(lines[j])
        j += 1
    # Skip the closing fence if present.
    if j < end:
        j += 1
    return Block(kind="code", text="\n".join(body), info=info), j


def _consume_blockquote(lines, i, end):
    body: List[str] = []
    j = i
    while j < end:
        m = _BLOCKQUOTE_RE.match(lines[j])
        if not m:
            # A blank line ends the quote.
            if not lines[j].strip():
                break
            # A non-quote, non-blank line also ends it (lazy continuation
            # is not supported in this subset).
            break
        body.append(m.group("rest"))
        j += 1
    inner_text = "\n".join(body)
    inner_blocks = parse_blocks(inner_text)
    return Block(kind="blockquote", text=inner_text, children=inner_blocks), j


def _consume_list(lines, i, end, base_indent, ordered: bool):
    """Consume a contiguous list at the indentation of ``lines[i]``.

    Items at the same indent attach to the same list. Greater-indent
    content (sub-list or indented paragraph) becomes the previous item's
    child. Lesser-indent content terminates the list.
    """
    list_indent = _expand_indent(lines[i])
    kind = "ordered_list" if ordered else "list"
    items: List[Block] = []
    j = i
    while j < end:
        line = lines[j]
        if not line.strip():
            # Blank lines are allowed inside a list; peek ahead to decide
            # whether we're still inside it.
            k = j + 1
            while k < end and not lines[k].strip():
                k += 1
            if k >= end:
                j = k
                break
            next_indent = _expand_indent(lines[k])
            next_b = _BULLET_RE.match(lines[k])
            next_o = _ORDERED_RE.match(lines[k])
            if next_indent < list_indent:
                j = k
                break
            if next_indent == list_indent and (next_b or next_o):
                # Same indent + list marker: stay in this list ONLY if the
                # marker type matches (- vs 1.). A different type starts a
                # new list at the outer level.
                same_type = next_o if ordered else next_b
                if same_type:
                    j = k
                    continue
                j = k
                break
            if next_indent > list_indent:
                # Indented continuation belongs to the previous item.
                j = k
                # Fall through into the item-extension branch below.
            else:
                # Same indent but not a list marker → list ends.
                j = k
                break

        line = lines[j]
        indent = _expand_indent(line)
        m_b = _BULLET_RE.match(line)
        m_o = _ORDERED_RE.match(line)

        if indent == list_indent and (m_b or m_o):
            # Marker at this list's indent — keep it only if the type
            # matches; a different type ends this list so the outer
            # parser can start a fresh one.
            m = m_o if ordered else m_b
            if m is None:
                break
            rest = m.group("rest")
            item = Block(kind="list_item", text=rest.strip())
            items.append(item)
            j += 1
            continue

        if indent > list_indent and items:
            # Continuation / nested content for the most recent item.
            sub_end = _find_block_end(lines, j, end, list_indent)
            sub_lines = lines[j:sub_end]
            child_indent = _expand_indent(lines[j])
            sub_blocks = _parse(sub_lines, 0, len(sub_lines), base_indent=child_indent)
            # Strip leading whitespace so child text reads naturally.
            for b in sub_blocks:
                items[-1].children.append(b)
            j = sub_end
            continue

        # Lower indent → list ends.
        break

    return Block(kind=kind, text="", children=items), j


def _find_block_end(lines, start, end, parent_indent):
    """Find the first line at-or-below ``parent_indent`` (or EOF)."""
    j = start
    while j < end:
        line = lines[j]
        if not line.strip():
            # Look past blank lines.
            k = j + 1
            while k < end and not lines[k].strip():
                k += 1
            if k >= end:
                return k
            if _expand_indent(lines[k]) <= parent_indent:
                return j
            j = k
            continue
        if _expand_indent(line) <= parent_indent:
            return j
        j += 1
    return j


def _consume_paragraph(lines, i, end, base_indent):
    body: List[str] = []
    j = i
    while j < end:
        line = lines[j]
        stripped = line.strip()
        if not stripped:
            break
        indent = _expand_indent(line)
        if indent < base_indent:
            break
        if (
            _BULLET_RE.match(line)
            or _ORDERED_RE.match(line)
            or _BLOCKQUOTE_RE.match(line)
            or _FENCE_RE.match(line)
        ):
            break
        body.append(stripped)
        j += 1
    return Block(kind="paragraph", text=" ".join(body)), j


def flatten(blocks: List[Block]) -> List[str]:
    """Flatten a block tree to a list of strings — one entry per top-level
    block. Lists expand to one string per top-level list_item."""
    out: List[str] = []
    for b in blocks:
        if b.kind in ("list", "ordered_list"):
            for item in b.children:
                out.append(item.text)
        elif b.kind == "code":
            out.append(b.text)
        elif b.kind == "blockquote":
            out.append(b.text.strip())
        else:
            out.append(b.text)
    return out


# ---------------------------------------------------------------- null sentinel

_NULL_BLOCK: Optional[Block] = None


def _null_block() -> Block:
    """Cached null-Block sentinel returned by :meth:`Block.get` /
    :meth:`Section.block` on out-of-range indices.

    Behaviour:
    - ``bool(b)`` is ``False``
    - ``b.text_plain`` → ``""``
    - ``b.text`` → ``""``, ``b.children`` → ``[]``
    - ``b.get(*more)`` → keeps returning this sentinel
    """
    global _NULL_BLOCK
    if _NULL_BLOCK is None:
        _NULL_BLOCK = Block(kind="", text="", children=[], info="")
    return _NULL_BLOCK
