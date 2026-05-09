# md-extractor

Turn a Markdown document into a navigable tree of sections keyed by header.
Bracket access, recursive search, JSON export — and a header detector that
**doesn't get fooled** by `#` characters living inside code blocks, tables,
math blocks, or YAML front matter.

- Zero runtime dependencies. Pure Python, `>= 3.8`.
- Lazy slicing — sections share a single line buffer, so the tree is cheap
  even for very large documents.

---

## Installation

```bash
pip install md-extractor
```

Or, from a local checkout:

```bash
pip install -e .
```

---

## Quick start

```python
from md_extract import MDExtractor

markdown_content = """
# Section 1
Some content here.

## Subsection 1.1
More details.
"""

extractor = MDExtractor(markdown_content)

# Access sections using dictionary-style brackets
print(extractor["Section 1"])
# # Section 1
# Some content here.
#
# ## Subsection 1.1
# More details.

# Access nested sections
print(extractor["Section 1"]["Subsection 1.1"])
# ## Subsection 1.1
# More details.

# List child headers
print(extractor.list())
# ['Section 1']

# Access the full document (root)
print(extractor[""])
```

Load straight from disk:

```python
extractor = MDExtractor.from_file("README.md")
```

---

## Features

### Nested parsing

ATX headers (`#` … `######`) and Setext underlines (`===` / `---`) are both
recognised and assembled into a tree that mirrors header level. Skip-level
jumps (h1 → h3 → h2) are handled gracefully.

### Robust extraction — what gets ignored

`md-extractor` walks the document with full block-context awareness, so a
stray `#` is never mistaken for a header.

| Block | Example | Behaviour |
|-------|---------|-----------|
| Fenced code | ```` ``` ```` … ```` ``` ```` (or `~~~`) | Headers inside are ignored |
| Math block | `$$` … `$$` | Headers inside are ignored |
| Tables | `\| col \| col \|` rows | Cell contents are ignored |
| YAML front matter | `---` at line 1, closes on `---`/`...` | Whole block is ignored |

````
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
````

```python
MDExtractor(md).list()  # ['Real Header']
```

### Indentation support

Any leading whitespace is allowed before a header — useful for documents
that nest headers under list items.

```python
MDExtractor("  # Indented\n").list()   # ['Indented']
```

### Easy access

Bracket notation, multi-step navigation, and `__contains__` all work:

```python
extractor["Section 1"]["Subsection 1.1"]
extractor.get_section("Section 1", "Subsection 1.1")   # equivalent
"Section 1" in extractor
```

Empty string returns the synthetic root, i.e. the whole document:

```python
extractor[""]   # the full source
```

### Discovery

```python
extractor.list()                 # immediate child titles
extractor["Section 1"].list()    # children of "Section 1"
extractor.find("Subsection 1.1") # every section with that title (any depth)
extractor.walk()                 # depth-first iterator over every header
extractor.tree()                 # ASCII tree of the whole document
```

### Slices for any granularity

Each `Section` exposes three text views:

| Property | Includes header line? | Includes child sections? |
|----------|-----------------------|--------------------------|
| `content` | yes | yes |
| `body` | no | yes |
| `text` | no | no — own prose only |

### Serialisation

```python
extractor.to_dict()       # JSON-friendly nested dict
extractor.to_json(indent=2)
```

### File ingestion

```python
MDExtractor.from_file("docs/guide.md", encoding="utf-8")
```

---

## API reference

### `MDExtractor`

| Member | Description |
|--------|-------------|
| `MDExtractor(markdown: str)` | Parse a string. |
| `MDExtractor.from_file(path, encoding="utf-8")` | Read & parse a file. |
| `extractor[""]` | Synthetic root section (whole document). |
| `extractor["Title"]` | Top-level child section by title. |
| `extractor[i]` | Top-level child section by index. |
| `"Title" in extractor` | Membership test. |
| `iter(extractor)` / `len(extractor)` | Iterate top-level children / count them. |
| `.list()` | Top-level header titles. |
| `.get_section(*path)` | Walk multiple titles in one call. |
| `.find(title)` | All sections (any depth) with that title. |
| `.walk()` | Depth-first iterator over every header section. |
| `.headers()` | Same as `walk()` but materialised as a list. |
| `.to_dict()` / `.to_json(**json_kw)` | Serialise the tree. |
| `.tree()` | ASCII tree rendering. |
| `.root` | The level-0 root `Section`. |
| `.content` | Original Markdown source. |

### `Section`

| Member | Description |
|--------|-------------|
| `.title` / `.level` | Header text and depth (1–6, or 0 for root). |
| `.parent` / `.children` | Tree links. |
| `.path` | Title chain from top-level ancestor down to this node. |
| `.content` | Header line + body + nested sections. |
| `.body` | `content` minus the header line. |
| `.text` | Just this section's own prose, no subsections. |
| `section["Title"]` / `section[i]` | Child by title or index. |
| `"Title" in section` | Membership test. |
| `iter(section)` / `len(section)` | Iterate / count direct children. |
| `.list()` | Direct child titles. |
| `.get_section(*path)` | Multi-step descent. |
| `.find(title)` | Recursive search. |
| `.walk()` | Depth-first iterator over self + descendants. |
| `.to_dict()` | Nested dict. |
| `.tree()` | ASCII tree. |
| `str(section)` | Same as `.content`. |

---

## Development

```bash
pip install -e .[dev]
pytest
```

---

## License

See [LICENSE](LICENSE).
