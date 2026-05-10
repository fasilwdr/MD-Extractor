"""markdown-extractor — extract structured sections from Markdown.

Public API:
    MDExtractor — entry point for parsing a Markdown document.
    Section     — a node in the parsed header tree.
    Block       — a node in a section's parsed body block tree.
"""

from markdown_extractor.blocks import Block
from markdown_extractor.extractor import MDExtractor
from markdown_extractor.section import Section

__version__ = "0.1.1"
__all__ = ["MDExtractor", "Section", "Block", "__version__"]
