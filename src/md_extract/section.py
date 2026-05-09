"""The :class:`Section` node — one entry in the parsed header tree."""

from __future__ import annotations

from typing import Any, Dict, Iterator, List, Optional, Union


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
        """Walk a sequence of child titles, e.g. ``s.get_section("A", "B")``."""
        node: Section = self
        for title in path:
            node = node[title]
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

    # ------------------------------------------------------------------ serialisation

    def to_dict(self) -> Dict[str, Any]:
        """Convert to a JSON-friendly nested dict."""
        return {
            "title": self.title,
            "level": self.level,
            "text": self.text,
            "children": [c.to_dict() for c in self.children],
        }

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

    def __repr__(self) -> str:
        return (
            f"Section(title={self.title!r}, level={self.level}, "
            f"children={len(self.children)})"
        )
