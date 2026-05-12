<p align="center">
  <img src="https://raw.githubusercontent.com/fasilwdr/MD-Extractor/main/assets/markdown-extractor.svg" alt="markdown-extractor logo">
</p>

# markdown-extractor

[![GitHub Release](https://img.shields.io/github/release/fasilwdr/MD-Extractor.svg)]()
[![Python Version](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/downloads/)
[![Downloads](https://static.pepy.tech/badge/markdown-extractor)](https://pepy.tech/project/markdown-extractor)

Turn a Markdown document into a navigable tree of sections keyed by header,
then drop into the body of any section to get its blocks, plain text, JSON,
or HTML — with optional XPath filtering.

- **Header tree** — bracket access, recursive search, ASCII tree.
- **Block tree** — paragraphs, ordered/unordered lists with nesting, code
  fences, blockquotes — parsed lazily per section.
- **Renderers** — `to_list()`, `to_dict()`, `to_json()`, `to_html()`,
  `to_text()`, all on both `MDExtractor` and any `Section`.
- **Robust parsing** — headers inside code blocks, tables, math blocks, and
  YAML front matter are correctly ignored.
- **Zero runtime dependencies** for everything except XPath (opt-in extra).
- **Pure Python**, `>= 3.8`. Lazy slicing — large documents stay cheap.

---

## Installation

```bash
pip install markdown-extractor
```

For XPath support on `to_html()`:

```bash
pip install markdown-extractor[xpath]
```

From a local checkout:

```bash
pip install -e .
```

---

## Quick start

```python
from markdown_extractor import MDExtractor

md = """
# Section 1
Some content here.

- **Lightweight** — small footprint.
- *Flexible* — extensible by design.
- `Tested` — full coverage.

## Subsection 1.1
More details.

## FAQ
- **Which versions are supported?**

    Versions 1.0 and up.
- **Where do I report bugs?**

    Open an issue on GitHub.
"""

e = MDExtractor(md)

e["Section 1"]                       # bracket access by title
e["Section 1"]["Subsection 1.1"]     # nested
e.get("Section 1", "Subsection 1.1") # multi-step (soft — see below)
e.list()                             # ['Section 1']
e[""]                                # synthetic root: the whole document
```

Every example below uses this same `md`. Load straight from disk instead:

```python
e = MDExtractor.from_file("docs/guide.md")
```

---

## Navigating the header tree

### Strict access — `[]` / `get_section()`

```python
e["Section 1"]                          # KeyError if missing
e.get_section("Section 1", "Sub 1.1")   # KeyError if any title is missing
"Section 1" in e
```

### Soft access — `get()`

`get()` walks the same path but returns a **null section sentinel** instead
of raising when something is missing. The sentinel is falsy and its
renderer methods all return empty values, so chains stay safe:

```python
e.get("Section 1", "Subsection 1.1").to_list()   # works
e.get("Nope", "Anything").to_list()              # []  — no exception
e.get("Nope").to_html()                          # ""
e.get("Nope").to_dict()                          # {'title':'', 'level':0, ...}

if not e.get("Optional Section"):
    print("section absent")
```

Use `[]`/`get_section()` when you want missing keys to fail loudly; use
`get()` when you want to flow through to an empty result.

### Discovery

```python
e.list()                              # immediate child titles
e["Section 1"].list()                 # children of "Section 1"
e.find("Subsection 1.1")              # every section with that title
e.walk()                              # depth-first iterator over every header
e.tree()                              # ASCII tree of the whole document
```

---

## Reading a section's body

Every `Section` parses its own body lazily into a tree of blocks
(paragraphs / lists / list items / code / blockquote). This view is what
powers `to_list`, `to_dict`, `to_html`, and `to_text`.

```python
s = e["Section 1"]

s.blocks       # the parsed Block tree (lazy, cached)
s.text         # raw prose, no header line, no subsections
s.body         # raw prose + nested subsections
s.content      # the full slice including the header line
```

### Reaching a single block — `block()` and `text_plain`

When you've isolated a single piece of text inside the block tree,
`Block.text_plain` strips the inline Markdown markers so you don't have
to round-trip through `to_text()`:

```python
s.blocks[1].children[1].text          # '*Flexible* — extensible by design.'
s.blocks[1].children[1].text_plain    # 'Flexible — extensible by design.'
```

`block.text` is kept raw on purpose — `to_dict()` / `to_json()` is a
lossless round-trip of the source. `text_plain` is the on-demand
plain-text view.

For chains that might break (a missing list item, an empty section),
use `Section.block(*indices)` and `Block.get(*indices)`. These return
a *null Block* on out-of-range indices instead of raising
`IndexError` — so the chain stays safe end-to-end:

```python
s.block(1, 1).text_plain            # 'Flexible — extensible by design.'
s.block(99, 99).text_plain          # ''  — no exception

# Equivalent two-step form (block() walks .blocks; .get() walks .children):
s.block(1).get(1).text_plain

bool(s.block(99))                   # False — null sentinel
```

`section.blocks[i]` / `block.children[j]` keep raising `IndexError` on
out-of-range — strict access stays strict. Use `block()` / `.get()` only
when you want soft fall-through.

### `.filtered(**kwargs)` — narrow any collection in place

Collection accessors return `BlockList` / `SectionList`, both `list`
subclasses that add a `.filtered(**kwargs)` method for chainable,
attribute-based narrowing. The kwargs form keeps the API usable from
Jinja2 / Django templates (which can't define lambdas). Existing list
operations (indexing, iteration, `len()`, `isinstance(x, list)`) keep
working unchanged.

```python
s = e["Section 1"]

# Equality (most common):
s.blocks.filtered(kind="paragraph")
e["Section 1"].children.filtered(level=2)

# Multiple kwargs AND together:
s.blocks.filtered(kind="code", info="python")

# Operator suffixes:
e.headers().filtered(level__gte=2)
e.headers().filtered(level__in=[2, 3])
e.headers().filtered(title__startswith="Sub")

# Chains keep the typed return — both results are SectionList:
e.headers() \
    .filtered(level=2) \
    .filtered(title__startswith="A")

# No kwargs → a shallow copy of the same subclass.
e.headers().filtered()
```

Supported operator suffixes:

| Suffix | Meaning |
|--------|---------|
| *(none)* | `==` |
| `__ne` | `!=` |
| `__lt`, `__lte`, `__gt`, `__gte` | comparison |
| `__in` | membership in iterable |
| `__contains` | substring (`b in a`) or container-`in` |
| `__startswith`, `__endswith` | string prefix / suffix |

Items missing the requested attribute are treated as non-matches — no
exception. Slices preserve the subclass too, so
`section.children[1:].filtered(level=2)` works.

The method is available on:

| Returns `BlockList` | Returns `SectionList` |
|---------------------|------------------------|
| `Section.blocks` | `Section.children` |
| `Block.children` | `Section.find(title)` |
| `Block.walk()` | `Section.walk()` |
| | `MDExtractor.find(title)` |
| | `MDExtractor.walk()` |
| | `MDExtractor.headers()` |


### `.mapped(path)` — extract / flatten across a collection

`BlockList` and `SectionList` also expose a `.mapped(path)` method —
Odoo-style attribute traversal that flattens list-valued attributes
and keeps the typed return so you can keep chaining `.filtered(...)`.

```python
s = e["Section 1"]

# Pull every body block from every direct subsection (flat BlockList):
s.children.mapped("blocks")

# Dotted paths walk further — every list_item inside every top-level
# block of Section 1, fully flattened:
s.blocks.mapped("children")             # → 3 list_items (the bullets)

# Equivalent — chained calls produce the same result:
s.blocks.mapped("children") == s.blocks.mapped("children")

# Two-level dotted path — every inline token under those bullets:
s.blocks.mapped("children.inlines")
# → [bold 'Lightweight', text ' — …', em 'Flexible', text ' — …',
#    code 'Tested',     text ' — …']

# Chain with .filtered() — still a BlockList:
s.blocks.mapped("children").filtered(kind="list_item")

# Scalar attributes return a plain list:
s.children.mapped("title")              # ['Subsection 1.1', 'FAQ']
e.headers().mapped("title")             # ['Section 1', 'Subsection 1.1', 'FAQ']
```

Behaviour notes:

- List-valued attributes (e.g. `.blocks`, `.inlines`, `.children`)
  are **flattened** into the result.
- Scalar attributes (e.g. `.title`, `.kind`, `.text`) are appended;
  the return is a plain `list` (no `.filtered()` chaining).
- The concrete subclass is preserved when every step yields the same
  `FilteredList` subclass, so the typed-return chain
  `… .mapped("blocks").filtered(kind="paragraph")` keeps working.
- Items missing the attribute are skipped silently — same convention
  as `.filtered()`.
- `coll.mapped("")` returns a shallow copy of the same subclass.


### `to_list()` — flatten body to strings

One entry per top-level block. Lists expand to one entry per top-level
item; `text` is preserved raw (use `text_plain` per-item if you want
markers stripped):

```python
s.to_list()
# ['Some content here.',
#  '**Lightweight** — small footprint.',
#  '*Flexible* — extensible by design.',
#  '`Tested` — full coverage.']
```

### `to_dict()` / `to_json()` — full structured output

Header subsections live under `children`; the body block tree lives under
`blocks`. Indented continuation paragraphs under a bullet (FAQ-style)
are attached as that bullet's `children`:

```python
e["Section 1"]["FAQ"].to_dict()
# {
#   "title": "FAQ",
#   "level": 2,
#   "text": "...",
#   "blocks": [
#     {"kind": "list", "text": "", "children": [
#       {"kind": "list_item",
#        "text": "**Which versions are supported?**",
#        "children": [
#          {"kind": "paragraph", "text": "Versions 1.0 and up."}
#        ]},
#       {"kind": "list_item",
#        "text": "**Where do I report bugs?**",
#        "children": [
#          {"kind": "paragraph", "text": "Open an issue on GitHub."}
#        ]}
#     ]}
#   ],
#   "children": []
# }

e["Section 1"]["FAQ"].to_json(indent=2)
```

### `to_text()` — Markdown stripped

Inline markers (`**bold**`, `*em*`, `` `code` ``, `[link](url)`,
`![alt](url)`) are reduced to their visible text. Bullets become
`- ` lines, ordered items become `1. `, nested children indent four
spaces, and fenced code is kept verbatim:

```python
print(s.to_text())
# Some content here.
#
# - Lightweight — small footprint.
# - Flexible — extensible by design.
# - Tested — full coverage.
```

### `to_html()` — render to HTML, optionally filter with XPath

```python
s.to_html()
# <p>Some content here.</p>
# <ul>
# <li><strong>Lightweight</strong> — small footprint.</li>
# <li><em>Flexible</em> — extensible by design.</li>
# <li><code>Tested</code> — full coverage.</li>
# </ul>

s.to_html(xpath=".//ul/li")
# ['<li><strong>Lightweight</strong> — small footprint.</li>',
#  '<li><em>Flexible</em> — extensible by design.</li>',
#  '<li><code>Tested</code> — full coverage.</li>']

s.to_html(xpath=".//strong")
# ['<strong>Lightweight</strong>']
```

#### Getting just the text value

When you want the *data* inside the matched elements rather than the
markup, you have two options:

**1. `as_text=True`** — flatten each match to its text content, including
text nested inside inline tags (`<strong>`, `<em>`, `<code>`, …):

```python
s.to_html(xpath=".//ul/li", as_text=True)
# ['Lightweight — small footprint.',
#  'Flexible — extensible by design.',
#  'Tested — full coverage.']

s.to_html(xpath=".//ul/li[1]", as_text=True)
# ['Lightweight — small footprint.']
```

**2. `/text()` in the XPath itself** — works without the `as_text` flag,
but only collects *direct* text nodes. Text wrapped in inline tags is
skipped:

```python
s.to_html(xpath=".//ul/li/text()")
# [' — small footprint.',
#  ' — extensible by design.',
#  ' — full coverage.']
# Note: 'Lightweight' / 'Flexible' / 'Tested' are missing — they sit
# inside <strong>/<em>/<code>, which /text() doesn't enter.
```

Use `as_text=True` when items contain inline formatting; use `/text()`
when you specifically want only the loose text and not the wrapped
content.

XPath uses `lxml` and is opt-in via the `[xpath]` extra:

```bash
pip install markdown-extractor[xpath]
```

Without `lxml`, plain `to_html()` still works — only `to_html(xpath=...)`
raises `ModuleNotFoundError` with the install hint.

---

## Robust extraction

The header parser walks the document with full block-context awareness,
so a stray `#` is never mistaken for a header.

| Block | Example | Behaviour |
|-------|---------|-----------|
| Fenced code | ```` ``` ```` … ```` ``` ```` (or `~~~`) | Headers inside are ignored |
| Math block | `$$` … `$$` | Headers inside are ignored |
| Tables | `\| col \| col \|` rows | Cell contents are ignored |
| YAML front matter | `---` at line 1, closes on `---`/`...` | Whole block is ignored |

```markdown
---
title: My Doc
# not a real header
---

# Real Header

```python
# also not a header
```

$$
# definitely not a header
$$
```

```python
MDExtractor(md).list()  # ['Real Header']
```

ATX headers (`#` … `######`) and Setext underlines (`===` / `---`) are
both recognised. Skip-level jumps (h1 → h3 → h2) are handled gracefully.
Any leading whitespace is allowed before a header.

---

## Slices for any granularity

Each `Section` exposes three text views:

| Property | Includes header line? | Includes child sections? |
|----------|-----------------------|--------------------------|
| `content` | yes | yes |
| `body` | no | yes |
| `text` | no | no — own prose only |

---

## API reference

### `MDExtractor`

| Member | Description |
|--------|-------------|
| `MDExtractor(markdown)` | Parse a string. |
| `MDExtractor.from_file(path, encoding="utf-8")` | Read & parse a file. |
| `e[""]` / `e.root` | Synthetic root section (whole document). |
| `e["Title"]` / `e[i]` | Top-level child by title or index. |
| `"Title" in e` | Membership test. |
| `iter(e)` / `len(e)` | Iterate top-level children / count them. |
| `.list()` | Top-level header titles. |
| `.get_section(*path)` | Strict multi-step descent (raises). |
| `.get(*path)` | Soft multi-step descent (null sentinel on miss). |
| `.find(title)` | All sections (any depth) with that title. |
| `.walk()` / `.headers()` | Depth-first iterator / list of every header. |
| `.tree()` | ASCII tree of the document's header structure. |
| `.to_list()` | Body flattened to strings (proxies to root). |
| `.to_dict()` / `.to_json(**kw)` | Serialise the tree (with body blocks). |
| `.to_text()` | Body rendered as plain text. |
| `.to_html(xpath=None, as_text=False)` | Body rendered as HTML, optionally XPath-filtered (`as_text=True` returns text values). |
| `.block(*indices)` | Soft index into root's body block tree (null Block on miss). |
| `.content` | Original Markdown source. |

### `Section`

| Member | Description |
|--------|-------------|
| `.title` / `.level` | Header text and depth (1–6, or 0 for root). |
| `.parent` / `.children` | Tree links. |
| `.path` | Title chain from top-level ancestor down to this node. |
| `.content` / `.body` / `.text` | Raw text views (see table above). |
| `.blocks` | Lazy-parsed body block tree. |
| `section["Title"]` / `section[i]` | Child by title or index (strict). |
| `section.get(*path)` | Soft multi-step descent (null sentinel on miss). |
| `section.get_section(*path)` | Strict multi-step descent. |
| `"Title" in section` | Membership test. |
| `iter(section)` / `len(section)` | Iterate / count direct children. |
| `bool(section)` | `False` only for the null sentinel returned by `get()`. |
| `.list()` | Direct child titles. |
| `.find(title)` | Recursive search. |
| `.walk()` | Depth-first iterator over self + descendants. |
| `.to_list()` | Body flattened to one string per top-level block / item. |
| `.to_dict()` | Nested dict — `blocks` (body) and `children` (header subsections). |
| `.to_json(**kw)` | `json.dumps` of `to_dict()`. |
| `.to_text()` | Body rendered as plain text (Markdown markers stripped). |
| `.to_html(xpath=None, as_text=False)` | Body rendered as HTML, optionally XPath-filtered (`as_text=True` returns text values). |
| `.block(*indices)` | Soft index walk into the body block tree (null Block on miss). |
| `.tree()` | ASCII tree of this subsection. |
| `str(section)` | Same as `.content`. |

### `Block`

A node in the body block tree.

| Member | Description |
|--------|-------------|
| `.kind` | One of `paragraph`, `list`, `ordered_list`, `list_item`, `code`, `blockquote`. |
| `.text` | The block's own text — raw, with inline Markdown markers preserved. |
| `.text_plain` | `.text` with inline markers stripped (`**bold**` → `bold`, `[t](u)` → `t`, …). |
| `.children` | Nested blocks (list items, sub-lists, indented paragraphs). |
| `.info` | Code-fence language, e.g. `"python"`. |
| `.get(*indices)` | Soft index walk into `.children` (null Block on miss). Chainable. |
| `bool(block)` | `False` only for the null sentinel returned by `get()` / `Section.block()`. |
| `.walk()` | Yield this block and every descendant. |
| `.to_dict()` | JSON-friendly nested dict. |

---

## Development

```bash
pip install -e .[dev]
pytest
```

---

## License

See [LICENSE](LICENSE).
