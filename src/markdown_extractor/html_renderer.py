"""Render the parsed block tree to HTML.

Pure-Python, zero-dependency renderer for the same Markdown subset that
:mod:`markdown_extractor.blocks` understands: paragraphs, ordered/unordered
lists with nesting, code fences, blockquotes — plus the common inline
constructs (``**bold**``, ``*em*``, ``` `code` ```, ``[text](url)``,
``![alt](url)``).

The output is plain HTML5 with no styling. It is intentionally minimal:
``markdown-extractor``'s job is structural extraction, not pretty rendering.
"""

from __future__ import annotations

import re
from html import escape
from typing import Iterable, List

from markdown_extractor.blocks import Block
from markdown_extractor.inline import (
    _BOLD_RE,
    _EM_STAR_RE,
    _EM_UNDER_RE,
    _IMG_RE,
    _INLINE_CODE_RE,
    _LINK_RE,
)


def render(blocks: Iterable[Block]) -> str:
    """Render a sequence of blocks to an HTML fragment."""
    return "\n".join(_render_block(b) for b in blocks)


def _render_block(block: Block) -> str:
    if block.kind == "paragraph":
        return f"<p>{_inline(block.text)}</p>"
    if block.kind == "code":
        cls = f' class="language-{escape(block.info)}"' if block.info else ""
        return f"<pre><code{cls}>{escape(block.text)}</code></pre>"
    if block.kind == "blockquote":
        inner = render(block.children) if block.children else f"<p>{_inline(block.text)}</p>"
        return f"<blockquote>\n{inner}\n</blockquote>"
    if block.kind in ("list", "ordered_list"):
        tag = "ol" if block.kind == "ordered_list" else "ul"
        items = "\n".join(_render_block(item) for item in block.children)
        return f"<{tag}>\n{items}\n</{tag}>"
    if block.kind == "list_item":
        body = _inline(block.text)
        if block.children:
            nested = render(block.children)
            return f"<li>{body}\n{nested}\n</li>"
        return f"<li>{body}</li>"
    return f"<div>{_inline(block.text)}</div>"


# ---------------------------------------------------------------- inline

# Order matters: replace inline code first (so its contents are not further
# transformed), then images, links, bold, em. Regex patterns live in
# :mod:`markdown_extractor.inline` so the parser and both renderers
# share one source of truth.


def _inline(text: str) -> str:
    """Convert the inline-formatting subset to HTML.

    Inline ``code`` content is escaped and stashed before any other rule
    runs, so backticks shield their contents from bold/em/link parsing.
    """
    if not text:
        return ""

    placeholders: List[str] = []

    def stash(html: str) -> str:
        placeholders.append(html)
        return f"\x00{len(placeholders) - 1}\x00"

    def repl_code(m: re.Match) -> str:
        return stash(f"<code>{escape(m.group(1))}</code>")

    out = _INLINE_CODE_RE.sub(repl_code, text)
    out = escape(out, quote=False)

    def repl_img(m: re.Match) -> str:
        alt = escape(m.group(1), quote=True)
        src = escape(m.group(2), quote=True)
        return stash(f'<img src="{src}" alt="{alt}">')

    def repl_link(m: re.Match) -> str:
        label = m.group(1)
        href = escape(m.group(2), quote=True)
        return stash(f'<a href="{href}">{label}</a>')

    # The escape pass replaced angle brackets — restore the markers our
    # regexes need by working on the escaped string for img/link too.
    out = _IMG_RE.sub(repl_img, out)
    out = _LINK_RE.sub(repl_link, out)
    out = _BOLD_RE.sub(lambda m: f"<strong>{m.group(1)}</strong>", out)
    out = _EM_STAR_RE.sub(lambda m: f"<em>{m.group(1)}</em>", out)
    out = _EM_UNDER_RE.sub(lambda m: f"<em>{m.group(1)}</em>", out)

    # Restore stashed HTML.
    def unstash(m: re.Match) -> str:
        return placeholders[int(m.group(1))]

    out = re.sub(r"\x00(\d+)\x00", unstash, out)
    return out


def query_xpath(html: str, xpath: str, as_text: bool = False) -> List[str]:
    """Run ``xpath`` over ``html`` and return the matched fragments.

    Requires the ``lxml`` extra (``pip install markdown-extractor[xpath]``).
    By default each element match is returned as an HTML string;
    string/attribute matches are returned as-is.

    With ``as_text=True``, element matches are flattened to their text
    content (recursively — so ``<li><strong>Bold</strong> rest</li>``
    yields ``"Bold rest"``). Use this when you want the data inside the
    element rather than the markup. Compare to writing ``/text()`` in
    the XPath itself, which only collects *direct* text children and
    skips text nested inside inline tags.
    """
    if not html:
        return []
    try:
        from lxml import etree, html as lxml_html
    except ImportError as e:  # pragma: no cover - only hit without lxml
        raise ModuleNotFoundError(
            "XPath queries require the 'lxml' package. "
            "Install with: pip install markdown-extractor[xpath]"
        ) from e

    fragment = lxml_html.fragment_fromstring(html, create_parent="div")
    results = fragment.xpath(xpath)
    out: List[str] = []
    for r in results:
        if isinstance(r, str):
            out.append(r)
        elif isinstance(r, etree._Element):
            if as_text:
                out.append(r.text_content())
            else:
                # ``with_tail=False`` excludes sibling text after the closing
                # tag — callers asking for an element fragment want just the
                # element, not its trailing context.
                out.append(
                    lxml_html.tostring(r, encoding="unicode", with_tail=False).rstrip()
                )
        else:
            out.append(str(r))
    return out
