"""The :class:`Section` node — one entry in the parsed header tree."""

from __future__ import annotations

import json
from typing import Any, Dict, Iterator, List, Optional, Union

from md_extract.blocks import Block, flatten, parse_blocks
from md_extract.html_renderer import query_xpath, render
from md_extract.text_renderer import render_text


class Section:
    """A single header (and its body) in a parsed Markdown document.

    A ``Section`` lazily slices the original document on access — there is
    no per-section copy of the source, so the tree is cheap to hold even
    for very large documents.
    """

    __slots__ = (
        "title",
        "level",
        "line_start",
        "line_end",
        "parent",
        "children",
        "_lines",
        "_blocks_cache",
    )

    def __init__(
        self,
        title: str,
        level: int,
        line_start: int,
        line_end: Optional[int] = None,
        parent: Optional["Section"] = None,
        lines: Optional[List[str]] = None,
    ) -> None:
        self.title = title
        self.level = level
        self.line_start = line_start
        self.line_end = line_end
        self.parent = parent
        self.children: List["Section"] = []
        self._lines = lines
        self._blocks_cache: Optional[List[Block]] = None

    # ------------------------------------------------------------------ slices

    @property
    def content(self) -> str:
        """The header line plus everything beneath it, including subsections."""
        if self._lines is None or self.line_end is None:
            return ""
        return "\n".join(self._lines[self.line_start : self.line_end])

    @property
    def body(self) -> str:
        """The section content with the header line removed.

        For the synthetic root (level 0) this is identical to :attr:`content`
        because the root has no header line to strip.
        """
        if self._lines is None or self.line_end is None:
            return ""
        start = self.line_start if self.level == 0 else self.line_start + 1
        return "\n".join(self._lines[start : self.line_end])

    @property
    def text(self) -> str:
        """Just this section's own prose — the header is dropped and any
        nested subsections are excluded."""
        if self._lines is None or self.line_end is None:
            return ""
        start = self.line_start if self.level == 0 else self.line_start + 1
        end = self.children[0].line_start if self.children else self.line_end
        return "\n".join(self._lines[start:end])

    # ------------------------------------------------------------------ navigation

    @property
    def path(self) -> List[str]:
        """Titles from the topmost ancestor down to this section (root excluded)."""
        result: List[str] = []
        node: Optional[Section] = self
        while node is not None and node.level > 0:
            result.append(node.title)
            node = node.parent
        result.reverse()
        return result

    def list(self) -> List[str]:
        """Titles of immediate child sections."""
        return [c.title for c in self.children]

    def get_section(self, *path: str) -> "Section":
        """Walk a sequence of child titles, e.g. ``s.get_section("A", "B")``.

        Strict — raises :class:`KeyError` if any title is missing. For
        an error-free version that flows through to empty results, use
        :meth:`get`.
        """
        node: Section = self
        for title in path:
            node = node[title]
        return node

    def get(self, *path: str) -> "Section":
        """Soft path walk — returns a *null* section on miss instead of raising.

        ``e.get("Foo", "Bar").to_list()`` returns ``[]`` (not a ``KeyError``)
        if either ``"Foo"`` or ``"Bar"`` is missing. The returned null
        section is falsy (``bool(s) is False``) and its ``to_list``,
        ``to_dict``, ``to_json``, ``to_html``, and ``to_text`` methods
        return empty values, so chains stay safe.

        Use ``[]`` (or :meth:`get_section`) when you want missing keys
        to fail loudly.
        """
        node: Section = self
        for title in path:
            if not node:  # already null — keep flowing
                return _null_section()
            found: Optional[Section] = None
            for child in node.children:
                if child.title == title:
                    found = child
                    break
            if found is None:
                return _null_section()
            node = found
        return node

    def find(self, title: str) -> List["Section"]:
        """All descendants whose title equals ``title`` (depth-first order)."""
        results: List[Section] = []
        for child in self.children:
            if child.title == title:
                results.append(child)
            results.extend(child.find(title))
        return results

    def walk(self) -> Iterator["Section"]:
        """Yield this section and every descendant, depth-first."""
        yield self
        for child in self.children:
            yield from child.walk()

    # ------------------------------------------------------------------ body blocks

    @property
    def blocks(self) -> List[Block]:
        """Lazy parse of this section's own prose into a block tree.

        The block tree covers paragraphs, ordered/unordered lists with
        nested items, code fences, and blockquotes. Header subsections
        of this section are *not* included — those live in
        :attr:`children`.
        """
        if self._blocks_cache is None:
            self._blocks_cache = parse_blocks(self.text)
        return self._blocks_cache

    def to_list(self) -> List[str]:
        """Flatten the body into a list of strings, one per top-level
        block (or one per top-level list item if the body is a list).

        Useful when you want the section's body as data — e.g. ``Overview``
        bullets as a list of feature strings — rather than as a header
        title roster (which is what :meth:`list` returns).
        """
        return flatten(self.blocks)

    def to_text(self) -> str:
        """Render the body to plain text with Markdown markers stripped.

        Bullets become ``- `` lines, ordered items become ``1. `` lines,
        nested children indent by four spaces, code blocks are kept
        verbatim, and inline ``**bold**`` / ``*em*`` / ``` `code` `` /
        links / images are reduced to their visible text.
        """
        return render_text(self.blocks)

    # ------------------------------------------------------------------ serialisation

    def to_dict(self) -> Dict[str, Any]:
        """Convert to a JSON-friendly nested dict.

        Includes both header subsections (``children``) and the body
        block tree (``blocks``). The ``blocks`` field captures bullet
        lists, paragraphs, and indented continuations as nested nodes.
        """
        return {
            "title": self.title,
            "level": self.level,
            "text": self.text,
            "blocks": [b.to_dict() for b in self.blocks],
            "children": [c.to_dict() for c in self.children],
        }

    def to_json(self, **kwargs: Any) -> str:
        """Shorthand for ``json.dumps(self.to_dict(), **kwargs)``."""
        return json.dumps(self.to_dict(), **kwargs)

    def to_html(self, xpath: Optional[str] = None) -> Union[str, List[str]]:
        """Render this section's body as an HTML fragment.

        Without ``xpath``, returns the full HTML string. With ``xpath``,
        returns a list of matched fragments (each match is itself an
        HTML string for element matches, or the raw value for string /
        attribute matches).

        XPath support requires the optional ``lxml`` extra::

            pip install md-extractor[xpath]
        """
        html = render(self.blocks)
        if xpath is None:
            return html
        return query_xpath(html, xpath)

    def tree(self, _indent: int = 0) -> str:
        """ASCII tree rendering of this section and its descendants."""
        label = "<root>" if self.level == 0 else f"{'#' * self.level} {self.title}"
        out = "  " * _indent + label
        for child in self.children:
            out += "\n" + child.tree(_indent + 1)
        return out

    # ------------------------------------------------------------------ dunder

    def __getitem__(self, key: Union[str, int]) -> "Section":
        if isinstance(key, int):
            return self.children[key]
        for child in self.children:
            if child.title == key:
                return child
        raise KeyError(
            f"Section {key!r} not found. Available children: {self.list()!r}"
        )

    def __contains__(self, key: object) -> bool:
        if isinstance(key, str):
            return any(child.title == key for child in self.children)
        return False

    def __iter__(self) -> Iterator["Section"]:
        return iter(self.children)

    def __len__(self) -> int:
        return len(self.children)

    def __str__(self) -> str:
        return self.content

    def __bool__(self) -> bool:
        """A non-null section is truthy. The sentinel returned by
        :meth:`get` on a missing path is the only falsy ``Section``."""
        return self._lines is not None

    def __repr__(self) -> str:
        if self._lines is None:
            return "Section(<null>)"
        return (
            f"Section(title={self.title!r}, level={self.level}, "
            f"children={len(self.children)})"
        )


# ---------------------------------------------------------------- null sentinel

_NULL_SECTION: Optional[Section] = None


def _null_section() -> Section:
    """Cached null-section sentinel returned by :meth:`Section.get` on miss.

    Behaviour summary:
    - ``bool(s)`` is ``False``
    - ``to_list()`` → ``[]``
    - ``to_dict()`` → ``{"title": "", "level": 0, "text": "", "blocks": [], "children": []}``
    - ``to_json()`` → JSON of the above
    - ``to_html()`` → ``""``  (with ``xpath=...`` → ``[]``)
    - ``to_text()`` → ``""``
    - ``get(*more)`` → keeps returning this sentinel
    """
    global _NULL_SECTION
    if _NULL_SECTION is None:
        _NULL_SECTION = Section(
            title="", level=0, line_start=0, line_end=None, lines=None
        )
    return _NULL_SECTION
