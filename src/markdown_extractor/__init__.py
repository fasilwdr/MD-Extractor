"""markdown-extractor — extract structured sections from Markdown.

Public API:
    MDExtractor  — entry point for parsing a Markdown document.
    Section      — a node in the parsed header tree.
    Block        — a node in a section's parsed body block tree.
    SectionList  — the filterable list returned by ``.children`` / ``walk()`` / ``find()`` / ``headers()``.
    BlockList    — the filterable list returned by ``.blocks`` and ``Block.children`` / ``walk()``.
"""

from markdown_extractor._collections import BlockList, FilteredList, SectionList
from markdown_extractor.blocks import Block
from markdown_extractor.extractor import MDExtractor
from markdown_extractor.section import Section

__version__ = "0.2.0"
__all__ = [
    "MDExtractor",
    "Section",
    "Block",
    "SectionList",
    "BlockList",
    "FilteredList",
    "__version__",
]
