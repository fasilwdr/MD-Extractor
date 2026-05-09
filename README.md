# md-extractor

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
pip install md-extractor
```

For XPath support on `to_html()`:

```bash
pip install md-extractor[xpath]
```

From a local checkout:

```bash
pip install -e .
```

---

## Quick start

```python
from md_extract import MDExtractor

md = """
# Section 1
Some content here.

## Subsection 1.1
More details.
"""

e = MDExtractor(md)

e["Section 1"]                       # bracket access by title
e["Section 1"]["Subsection 1.1"]     # nested
e.get("Section 1", "Subsection 1.1") # multi-step (soft — see below)
e.list()                             # ['Section 1']
e[""]                                # synthetic root: the whole document
```

Load straight from disk:

```python
e = MDExtractor.from_file("README.md")
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
overview = e["Overview"]

overview.blocks       # the parsed Block tree (lazy, cached)
overview.text         # raw prose, no header line, no subsections
overview.body         # raw prose + nested subsections
overview.content      # the full slice including the header line
```

### `to_list()` — flatten body to strings

One entry per top-level block. Lists expand to one entry per top-level
item:

```python
overview.to_list()
# ['Intro paragraph.',
#  'First feature',
#  'Second feature',
#  'Third feature']
```

### `to_dict()` / `to_json()` — full structured output

Header subsections live under `children`; the body block tree lives under
`blocks`. Indented continuation paragraphs under a bullet (FAQ-style)
are attached as that bullet's `children`.

```python
faq.to_dict()
# {
#   "title": "FAQ",
#   "level": 2,
#   "text": "...",
#   "blocks": [
#     {"kind": "list", "children": [
#       {"kind": "list_item",
#        "text": "**Which versions are supported?**",
#        "children": [
#          {"kind": "paragraph", "text": "Versions 19.0 and up."}
#        ]},
#       ...
#     ]}
#   ],
#   "children": []
# }

faq.to_json(indent=2)
```

### `to_text()` — Markdown stripped

Inline markers (`**bold**`, `*em*`, `` `code` ``, `[link](url)`,
`![alt](url)`) are reduced to their visible text. Bullets become
`- ` lines, ordered items become `1. `, nested children indent four
spaces, and fenced code is kept verbatim.

```python
overview.to_text()
# Intro paragraph.
#
# - First feature
# - Second feature
# - Third feature
```

### `to_html()` — render to HTML, optionally filter with XPath

```python
overview.to_html()
# '<p>Intro paragraph.</p>\n<ul>\n<li>First feature</li>...'

overview.to_html(xpath=".//ul/li")
# ['<li>First feature</li>', '<li>Second feature</li>', ...]

overview.to_html(xpath=".//li/text()")
# ['First feature', 'Second feature', ...]
```

XPath uses `lxml` and is opt-in via the `[xpath]` extra:

```bash
pip install md-extractor[xpath]
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
| `.to_html(xpath=None)` | Body rendered as HTML, optionally XPath-filtered. |
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
| `.to_html(xpath=None)` | Body rendered as HTML, optionally XPath-filtered. |
| `.tree()` | ASCII tree of this subsection. |
| `str(section)` | Same as `.content`. |

### `Block`

A node in the body block tree.

| Member | Description |
|--------|-------------|
| `.kind` | One of `paragraph`, `list`, `ordered_list`, `list_item`, `code`, `blockquote`. |
| `.text` | The block's own text (empty for list / ordered_list containers). |
| `.children` | Nested blocks (list items, sub-lists, indented paragraphs). |
| `.info` | Code-fence language, e.g. `"python"`. |
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
