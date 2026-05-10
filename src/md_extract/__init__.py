"""md-extract — extract structured sections from Markdown.

Public API:
    MDExtractor — entry point for parsing a Markdown document.
    Section     — a node in the parsed header tree.
    Block       — a node in a section's parsed body block tree.
"""

from md_extract.blocks import Block
from md_extract.extractor import MDExtractor
from md_extract.section import Section

__version__ = "0.1.0"
__all__ = ["MDExtractor", "Section", "Block", "__version__"]
