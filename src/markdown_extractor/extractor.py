"""Top-level facade that turns a Markdown string into a :class:`Section` tree."""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional, Union

from markdown_extractor._collections import SectionList
from markdown_extractor.blocks import Block
from markdown_extractor.parser import parse
from markdown_extractor.section import Section


class MDExtractor:
    """Parse a Markdown document and expose its headers as a navigable tree.

    Bracket access mirrors the ergonomics of a nested dictionary::

        extractor = MDExtractor(text)
        extractor["Section 1"]["Subsection 1.1"]

    The empty string returns the synthetic root section, which represents
    the entire document::

        extractor[""]   # whole document, including front matter
    """

    def __init__(self, markdown_content: str) -> None:
        if not isinstance(markdown_content, str):
            raise TypeError(
                "markdown_content must be a str, got "
                f"{type(markdown_content).__name__}"
            )
        self._content = markdown_content
        self._root = self._build_tree()

    # ------------------------------------------------------------------ construction

    @classmethod
    def from_file(
        cls, path: Union[str, Path], encoding: str = "utf-8"
    ) -> "MDExtractor":
        """Read ``path`` and parse its contents."""
        return cls(Path(path).read_text(encoding=encoding))

    def _build_tree(self) -> Section:
        headers, lines = parse(self._content)
        root = Section(
            title="",
            level=0,
            line_start=0,
            line_end=len(lines),
            lines=lines,
        )
        stack: List[Section] = [root]
        for header in headers:
            # Pop ancestors whose level is >= this header's level: the new
            # section attaches to the deepest still-open parent.
            while stack[-1].level >= header.level:
                stack.pop()
            parent = stack[-1]
            section = Section(
                title=header.title,
                level=header.level,
                line_start=header.line,
                parent=parent,
                lines=lines,
            )
            parent.children.append(section)
            stack.append(section)
        self._fill_line_ends(root, len(lines))
        return root

    @staticmethod
    def _fill_line_ends(section: Section, doc_end: int) -> None:
        """Populate ``line_end`` for every section by sibling/parent boundaries."""
        if section.line_end is None:
            section.line_end = doc_end
        for i, child in enumerate(section.children):
            if i + 1 < len(section.children):
                child.line_end = section.children[i + 1].line_start
            else:
                child.line_end = section.line_end
            MDExtractor._fill_line_ends(child, doc_end)

    # ------------------------------------------------------------------ accessors

    @property
    def root(self) -> Section:
        """The synthetic top-level section that owns every other section."""
        return self._root

    @property
    def content(self) -> str:
        """The original Markdown source, unmodified."""
        return self._content

    def list(self) -> List[str]:
        """Top-level section titles."""
        return self._root.list()

    def get_section(self, *path: str) -> Section:
        """Navigate by a sequence of titles (root → leaf)."""
        return self._root.get_section(*path)

    def find(self, title: str) -> SectionList:
        """Find every section whose title equals ``title`` (any depth)."""
        return self._root.find(title)

    def walk(self) -> SectionList:
        """Every header section in the document, depth-first.

        Returns a :class:`SectionList` (the synthetic root is excluded),
        so the result can be chained with ``.filtered(...)``.
        """
        return self._root.walk().filtered(level__gt=0)

    def headers(self) -> SectionList:
        """All header sections as a flat :class:`SectionList`."""
        return self.walk()

    def to_dict(self) -> dict:
        """JSON-friendly dict of the whole tree."""
        return self._root.to_dict()

    def to_json(self, **kwargs) -> str:
        """Shorthand for ``json.dumps(self.to_dict(), **kwargs)``."""
        return json.dumps(self.to_dict(), **kwargs)

    def to_list(self) -> List[str]:
        """Flatten the document's body into one entry per top-level block.

        See :meth:`Section.to_list` for the per-section equivalent.
        """
        return self._root.to_list()

    def to_text(self) -> str:
        """Render the document body to plain text (Markdown markers stripped).

        See :meth:`Section.to_text` for the per-section equivalent.
        """
        return self._root.to_text()

    def to_html(
        self, xpath: Optional[str] = None, as_text: bool = False
    ) -> Union[str, List[str]]:
        """Render the whole document's body to HTML.

        See :meth:`Section.to_html` for the per-section equivalent,
        XPath usage notes, and the ``as_text`` parameter.
        """
        return self._root.to_html(xpath, as_text=as_text)

    def block(self, *indices: int) -> Block:
        """Soft index walk into the document's body blocks.

        See :meth:`Section.block` for the per-section equivalent.
        """
        return self._root.block(*indices)

    def get(self, *path: str) -> Section:
        """Soft path walk on the document — see :meth:`Section.get`.

        Returns the matched section, or a null section sentinel if any
        title in ``path`` is missing. The null section is falsy and its
        ``to_list``/``to_dict``/``to_json``/``to_html``/``to_text``
        methods all return empty values, so chains stay safe.
        """
        return self._root.get(*path)

    def tree(self) -> str:
        """ASCII tree of the document's header structure."""
        return self._root.tree()

    # ------------------------------------------------------------------ dunder

    def __getitem__(self, key: Union[str, int]) -> Section:
        if isinstance(key, str) and key == "":
            return self._root
        return self._root[key]

    def __contains__(self, key: object) -> bool:
        return key in self._root

    def __iter__(self) -> Iterator[Section]:
        return iter(self._root)

    def __len__(self) -> int:
        return len(self._root)

    def __str__(self) -> str:
        return self._content

    def __repr__(self) -> str:
        return f"MDExtractor(headers={len(self.headers())})"
