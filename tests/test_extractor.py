from pathlib import Path
from textwrap import dedent

import pytest

from markdown_extractor import BlockList, MDExtractor, Section, SectionList


# ---------------------------------------------------------------- basic API


def test_basic_parsing_matches_prompt_example():
    md = dedent(
        """
        # Section 1
        Some content here.

        ## Subsection 1.1
        More details.
        """
    )
    e = MDExtractor(md)

    assert e.list() == ["Section 1"]
    assert e["Section 1"].list() == ["Subsection 1.1"]

    s1 = str(e["Section 1"])
    assert "# Section 1" in s1
    assert "Some content here." in s1
    assert "## Subsection 1.1" in s1

    sub = str(e["Section 1"]["Subsection 1.1"])
    assert sub.startswith("## Subsection 1.1")
    assert "More details." in sub


def test_root_is_full_document():
    md = "# A\nbody\n"
    e = MDExtractor(md)
    assert e[""].title == ""
    assert e[""].level == 0
    assert str(e[""]) == md


def test_get_section_path():
    md = "# A\n## B\n### C\nleaf\n"
    e = MDExtractor(md)
    assert e.get_section("A", "B", "C").title == "C"
    assert e.get_section("A", "B", "C").path == ["A", "B", "C"]


def test_index_access_alongside_title_access():
    md = "# First\n# Second\n"
    e = MDExtractor(md)
    assert e[0].title == "First"
    assert e[1].title == "Second"
    assert e["First"] is e[0]


def test_contains_iter_len():
    md = "# A\n## A1\n## A2\n# B\n"
    e = MDExtractor(md)
    assert "A" in e
    assert "Nope" not in e
    assert len(e) == 2
    assert [s.title for s in e] == ["A", "B"]
    assert len(e["A"]) == 2


# ---------------------------------------------------------------- robust extraction


def test_ignores_headers_inside_fenced_code():
    md = dedent(
        """
        # Real
        body
        ```
        # Fake inside code
        ## Also fake
        ```
        more body
        """
    )
    e = MDExtractor(md)
    assert e.list() == ["Real"]


def test_ignores_headers_inside_tilde_fenced_code():
    md = dedent(
        """
        # Real
        ~~~python
        # not a header
        ~~~
        """
    )
    e = MDExtractor(md)
    assert e.list() == ["Real"]


def test_ignores_headers_inside_math_block():
    md = dedent(
        """
        # Real
        $$
        # not a header
        x = 1
        $$
        """
    )
    e = MDExtractor(md)
    assert e.list() == ["Real"]


def test_ignores_headers_inside_yaml_front_matter():
    md = dedent(
        """\
        ---
        title: doc
        # not a header
        author: someone
        ---

        # Real
        """
    )
    e = MDExtractor(md)
    assert e.list() == ["Real"]


def test_ignores_headers_inside_table():
    md = dedent(
        """
        # Real

        | symbol | meaning   |
        |--------|-----------|
        | #      | hash      |
        | ##     | also hash |

        # Also Real
        """
    )
    e = MDExtractor(md)
    assert e.list() == ["Real", "Also Real"]


def test_indented_headers_are_accepted():
    md = "  # Indented\n   ## Also indented\nbody\n"
    e = MDExtractor(md)
    assert e.list() == ["Indented"]
    assert e["Indented"].list() == ["Also indented"]


# ---------------------------------------------------------------- tree shape


def test_non_monotonic_levels():
    # h1 -> h3 -> h2: the h2 should still attach below h1 (skip-level OK).
    md = "# A\n### Deep\n## Mid\n"
    e = MDExtractor(md)
    a = e["A"]
    assert [c.title for c in a.children] == ["Deep", "Mid"]
    assert a["Deep"].level == 3
    assert a["Mid"].level == 2


def test_find_returns_all_matches():
    md = "# A\n## X\nfoo\n# B\n## X\nbar\n"
    e = MDExtractor(md)
    hits = e.find("X")
    assert len(hits) == 2
    paths = sorted(h.path for h in hits)
    assert paths == [["A", "X"], ["B", "X"]]


def test_walk_yields_all_headers_in_order():
    md = "# A\n## A1\n## A2\n# B\n"
    e = MDExtractor(md)
    titles = [s.title for s in e.walk()]
    assert titles == ["A", "A1", "A2", "B"]


# ---------------------------------------------------------------- serialisation


def test_to_dict_shape():
    md = "# A\n## B\nbody\n"
    e = MDExtractor(md)
    d = e.to_dict()
    assert d["title"] == ""
    assert d["children"][0]["title"] == "A"
    assert d["children"][0]["children"][0]["title"] == "B"
    assert "body" in d["children"][0]["children"][0]["text"]


def test_to_json_round_trips():
    import json

    md = "# A\n## B\n"
    e = MDExtractor(md)
    parsed = json.loads(e.to_json())
    assert parsed["children"][0]["title"] == "A"


def test_tree_renders():
    md = "# A\n## B\n# C\n"
    rendered = MDExtractor(md).tree()
    assert "# A" in rendered
    assert "## B" in rendered
    assert "# C" in rendered


# ---------------------------------------------------------------- file IO


def test_from_file_reads_real_fixture():
    fixture = Path(__file__).resolve().parents[1] / "example" / "sample.md"
    if not fixture.exists():
        pytest.skip(f"fixture missing: {fixture}")
    e = MDExtractor.from_file(fixture)
    titles = e.list()
    assert "Sample Module" in titles
    assert "✨ Features" in titles
    sample = e["Sample Module"]
    # The bash code block in the document must NOT generate phantom headers.
    for header in e.walk():
        assert "Restart Odoo" not in header.title


# ---------------------------------------------------------------- type guards


def test_non_string_input_rejected():
    with pytest.raises(TypeError):
        MDExtractor(123)


def test_missing_section_raises_key_error():
    e = MDExtractor("# A\n")
    with pytest.raises(KeyError):
        _ = e["Nope"]


# ---------------------------------------------------------------- body blocks


def test_to_list_flattens_paragraphs_and_bullets():
    md = dedent(
        """
        # Overview
        Intro paragraph.

        - First feature
        - Second feature
        - Third feature
        """
    )
    e = MDExtractor(md)
    assert e["Overview"].to_list() == [
        "Intro paragraph.",
        "First feature",
        "Second feature",
        "Third feature",
    ]


def test_to_dict_includes_blocks_with_nested_bullets():
    md = dedent(
        """
        # FAQ
        - **Q1?**

            Answer one.
        - **Q2?**

            Answer two.
        """
    )
    e = MDExtractor(md)
    blocks = e["FAQ"].to_dict()["blocks"]
    list_block = next(b for b in blocks if b["kind"] == "list")
    items = list_block["children"]
    assert items[0]["text"] == "**Q1?**"
    assert items[0]["children"][0]["text"] == "Answer one."
    assert items[1]["text"] == "**Q2?**"
    assert items[1]["children"][0]["text"] == "Answer two."


def test_to_dict_keeps_existing_children_for_header_subsections():
    # Backwards compat: header subsections still live under "children".
    md = "# A\n## B\nbody\n"
    e = MDExtractor(md)
    d = e.to_dict()
    assert d["children"][0]["title"] == "A"
    assert d["children"][0]["children"][0]["title"] == "B"


def test_blocks_property_is_cached():
    md = "# A\n- one\n- two\n"
    e = MDExtractor(md)
    assert e["A"].blocks is e["A"].blocks


def test_to_list_handles_code_and_blockquote():
    md = dedent(
        """
        # Mix
        Para text.

        ```python
        x = 1
        ```

        > a quote line
        """
    )
    e = MDExtractor(md)
    out = e["Mix"].to_list()
    assert "Para text." in out
    assert "x = 1" in out
    assert "a quote line" in out


def test_ordered_list_kind():
    md = dedent(
        """
        # Steps
        1. first
        2. second
        """
    )
    e = MDExtractor(md)
    blocks = e["Steps"].blocks
    assert blocks[0].kind == "ordered_list"
    assert [c.text for c in blocks[0].children] == ["first", "second"]


# ---------------------------------------------------------------- HTML rendering


def test_to_html_paragraphs_and_lists():
    md = dedent(
        """
        # Overview
        Intro.

        - one
        - two
        """
    )
    html = MDExtractor(md)["Overview"].to_html()
    assert "<p>Intro.</p>" in html
    assert "<ul>" in html and "</ul>" in html
    assert "<li>one</li>" in html
    assert "<li>two</li>" in html


def test_to_html_inline_formatting():
    md = "# A\nThis is **bold**, *em*, `code`, and a [link](https://example.com).\n"
    html = MDExtractor(md)["A"].to_html()
    assert "<strong>bold</strong>" in html
    assert "<em>em</em>" in html
    assert "<code>code</code>" in html
    assert '<a href="https://example.com">link</a>' in html


def test_to_html_image():
    md = "# A\n![alt text](img.png)\n"
    html = MDExtractor(md)["A"].to_html()
    assert '<img src="img.png" alt="alt text">' in html


def test_to_html_code_fence_preserves_content():
    md = dedent(
        """
        # A
        ```python
        x = 1 < 2
        ```
        """
    )
    html = MDExtractor(md)["A"].to_html()
    assert '<pre><code class="language-python">' in html
    # Content inside <code> must be HTML-escaped.
    assert "x = 1 &lt; 2" in html


def test_to_html_xpath_filters_to_list_items():
    pytest.importorskip("lxml")
    md = dedent(
        """
        # A
        Intro.

        - one
        - two
        """
    )
    matches = MDExtractor(md)["A"].to_html(xpath=".//ul/li")
    assert isinstance(matches, list)
    assert len(matches) == 2
    assert "one" in matches[0]
    assert "two" in matches[1]


def test_to_html_xpath_text_extraction():
    pytest.importorskip("lxml")
    md = "# A\n- alpha\n- beta\n"
    matches = MDExtractor(md)["A"].to_html(xpath=".//li/text()")
    assert "alpha" in matches
    assert "beta" in matches


def test_to_html_xpath_as_text_returns_text_content():
    pytest.importorskip("lxml")
    md = dedent(
        """
        # A
        1. First feature.
        2. Second feature.
        """
    )
    out = MDExtractor(md)["A"].to_html(xpath="//ol/li[1]", as_text=True)
    assert out == ["First feature."]


def test_to_html_xpath_as_text_recurses_through_inline_tags():
    # The whole reason as_text exists: /text() drops the <strong> child,
    # but text_content() flattens it.
    pytest.importorskip("lxml")
    md = dedent(
        """
        # A
        - **bold** item one
        - *em* item two
        """
    )
    s = MDExtractor(md)["A"]
    direct_text = s.to_html(xpath="//ul/li/text()")
    flattened = s.to_html(xpath="//ul/li", as_text=True)

    # /text() collects only direct text children — the bolded word is lost.
    assert all("bold" not in t for t in direct_text)
    # as_text=True flattens recursively — the bolded word is preserved.
    assert flattened == ["bold item one", "em item two"]


def test_to_html_as_text_ignored_without_xpath():
    pytest.importorskip("lxml")
    md = "# A\nhi\n"
    # as_text only kicks in when xpath is given.
    assert MDExtractor(md)["A"].to_html(as_text=True) == MDExtractor(md)["A"].to_html()


def test_extractor_to_html_as_text_proxies_to_root():
    pytest.importorskip("lxml")
    md = "# A\n- one\n- two\n"
    e = MDExtractor(md)
    assert e.to_html(xpath="//li", as_text=True) == e.root.to_html(xpath="//li", as_text=True)


def test_extractor_to_list_and_to_html_proxy_to_root():
    md = "# A\nintro\n- x\n- y\n"
    e = MDExtractor(md)
    assert e.to_list() == e.root.to_list()
    assert e.to_html() == e.root.to_html()


# ---------------------------------------------------------------- Section.to_json


def test_section_to_json_round_trips():
    import json as _json

    md = "# A\nbody text\n- x\n- y\n"
    e = MDExtractor(md)
    parsed = _json.loads(e["A"].to_json())
    assert parsed["title"] == "A"
    assert parsed["blocks"][0]["text"] == "body text"


def test_section_to_json_passes_kwargs():
    md = "# A\nhi\n"
    e = MDExtractor(md)
    pretty = e["A"].to_json(indent=2)
    assert "\n" in pretty
    assert pretty.startswith("{")


# ---------------------------------------------------------------- soft .get() + null sentinel


def test_get_present_returns_section():
    md = "# A\n## B\nbody\n"
    e = MDExtractor(md)
    s = e.get("A", "B")
    assert s.title == "B"
    assert bool(s) is True


def test_get_missing_returns_falsy_null_section():
    md = "# A\n"
    e = MDExtractor(md)
    null = e.get("Nope")
    assert bool(null) is False
    assert null.title == ""


def test_null_section_to_methods_return_empty():
    md = "# A\n"
    e = MDExtractor(md)
    null = e.get("Nope", "Deeper")
    assert null.to_list() == []
    assert null.to_html() == ""
    assert null.to_text() == ""
    d = null.to_dict()
    assert d == {"title": "", "level": 0, "text": "", "blocks": [], "children": []}
    import json as _json
    assert _json.loads(null.to_json()) == d


def test_null_section_xpath_returns_empty_without_lxml_call():
    # Empty HTML short-circuits before importing lxml, so this works
    # even in environments where the [xpath] extra isn't installed.
    md = "# A\n"
    null = MDExtractor(md).get("Nope")
    assert null.to_html(xpath=".//ul") == []


def test_get_chains_through_null():
    md = "# A\n"
    e = MDExtractor(md)
    # Even after a missing path, further .get() calls keep returning null.
    assert e.get("Nope").get("Still nope").to_list() == []


def test_strict_bracket_access_still_raises():
    # Soft access via .get() must not soften the strict [] contract.
    e = MDExtractor("# A\n")
    with pytest.raises(KeyError):
        _ = e["Nope"]


def test_get_with_no_path_returns_self_root():
    e = MDExtractor("# A\n")
    assert e.get() is e.root


# ---------------------------------------------------------------- to_text


def test_to_text_strips_inline_formatting():
    md = "# A\nThis is **bold**, *em*, `code`, and a [link](https://x.com).\n"
    text = MDExtractor(md)["A"].to_text()
    assert "**" not in text
    assert "`" not in text
    assert "[link]" not in text
    assert "bold" in text and "em" in text and "code" in text and "link" in text


def test_to_text_renders_unordered_and_ordered_lists():
    md = dedent(
        """
        # A
        - one
        - two

        1. first
        2. second
        """
    )
    text = MDExtractor(md)["A"].to_text()
    assert "- one" in text
    assert "- two" in text
    assert "1. first" in text
    assert "2. second" in text


def test_to_text_indents_nested_bullet_children():
    md = dedent(
        """
        # FAQ
        - **Q1?**

            Answer one.
        """
    )
    text = MDExtractor(md)["FAQ"].to_text()
    lines = text.splitlines()
    assert lines[0] == "- Q1?"
    # The answer paragraph is indented under the bullet.
    assert any(line.startswith("  Answer one.") for line in lines)


def test_to_text_keeps_code_block_verbatim():
    md = dedent(
        """
        # A
        ```python
        x = 1 < 2
        ```
        """
    )
    text = MDExtractor(md)["A"].to_text()
    assert "x = 1 < 2" in text


def test_to_text_image_falls_back_to_alt():
    md = "# A\n![pretty alt](img.png)\n"
    text = MDExtractor(md)["A"].to_text()
    assert "pretty alt" in text
    assert "img.png" not in text


def test_extractor_to_text_proxies_to_root():
    md = "# A\nhi\n- x\n"
    e = MDExtractor(md)
    assert e.to_text() == e.root.to_text()


# ---------------------------------------------------------------- Block.text_plain + soft chain


def test_block_text_plain_strips_inline_markers():
    md = dedent(
        """
        # A
        - **bold** item
        - *em* item
        - `code` item
        - [link](https://x.com) here
        - ![alt text](pic.png)
        """
    )
    items = MDExtractor(md)["A"].blocks[0].children
    assert items[0].text_plain == "bold item"
    assert items[1].text_plain == "em item"
    assert items[2].text_plain == "code item"
    assert items[3].text_plain == "link here"
    assert items[4].text_plain == "alt text"


def test_block_text_plain_on_null_block_is_empty():
    md = "# A\n- one\n"
    null = MDExtractor(md)["A"].block(99)
    assert null.text_plain == ""


def test_block_get_walks_children_by_index():
    md = dedent(
        """
        # FAQ
        - **Q1?**

            Answer one.
        - **Q2?**

            Answer two.
        """
    )
    list_block = MDExtractor(md)["FAQ"].blocks[0]
    # First item has the answer paragraph as child[0].
    assert list_block.get(0, 0).text == "Answer one."
    assert list_block.get(1, 0).text == "Answer two."


def test_block_get_out_of_range_returns_falsy_null():
    md = "# A\n- one\n"
    list_block = MDExtractor(md)["A"].blocks[0]
    null = list_block.get(99)
    assert bool(null) is False
    assert null.text_plain == ""


def test_block_get_chains_through_null():
    md = "# A\n- one\n"
    block = MDExtractor(md)["A"].blocks[0]
    assert block.get(99).get(0).get(5).text_plain == ""


def test_section_block_combined_indices():
    md = dedent(
        """
        # Overview
        intro

        - **alpha**
        - **beta**
        """
    )
    s = MDExtractor(md)["Overview"]
    # block(1, 1) == blocks[1].children[1] (the second list item).
    assert s.block(1, 1).text_plain == "beta"
    assert s.block(1, 1).text == s.blocks[1].children[1].text


def test_section_block_missing_returns_null():
    md = "# A\nhi\n"
    s = MDExtractor("# A\nhi\n")["A"]
    assert s.block(99).text_plain == ""
    assert s.block(99, 99).text_plain == ""
    assert not s.block(99)


def test_section_block_with_no_indices_is_null():
    md = "# A\n- one\n"
    s = MDExtractor(md)["A"]
    assert not s.block()
    assert s.block().text_plain == ""


def test_strict_block_indexing_still_raises():
    md = "# A\n- one\n"
    s = MDExtractor(md)["A"]
    with pytest.raises(IndexError):
        _ = s.blocks[99]


def test_block_bool_truthy_for_real_blocks():
    md = "# A\nhello\n"
    s = MDExtractor(md)["A"]
    assert bool(s.blocks[0]) is True


def test_extractor_block_proxies_to_root():
    md = "# A\nhi\n"
    e = MDExtractor(md)
    # Both routes yield the same null block on miss (root has no body blocks
    # before its first header child).
    assert e.block(99).text_plain == e.root.block(99).text_plain == ""


def test_user_snippet_works_end_to_end():
    # The exact pattern from the user's request.
    md = dedent(
        """
        # Sample Module
        ## 📋 Overview
        Intro paragraph.

        - ⚡ **Lightweight & Fast** — Minimal footprint.
        - 🔌 **Plug & Play** — Install in seconds.
        - 🛡️ **Production Ready** — Battle-tested.
        """
    )
    e = MDExtractor(md)
    overview = e.get("Sample Module", "📋 Overview")
    plain = overview.to_dict()["blocks"][1]["children"][1]["text"]
    # Apply text_plain via the Block route (since dict has raw text).
    assert overview.blocks[1].children[1].text_plain == \
        "🔌 Plug & Play — Install in seconds."
    # Soft chain matches the strict one.
    assert overview.block(1, 1).text_plain == \
        overview.blocks[1].children[1].text_plain
    # Raw dict text still has markers (lossless round-trip preserved).
    assert "**" in plain


# ---------------------------------------------------------------- .filtered()


def test_blocks_filtered_by_kind():
    md = dedent(
        """
        # S
        Para one.

        - bullet a
        - bullet b

        ```
        code
        ```
        """
    )
    s = MDExtractor(md)["S"]
    paragraphs = s.blocks.filtered(kind="paragraph")
    assert isinstance(paragraphs, BlockList)
    assert [b.text for b in paragraphs] == ["Para one."]


def test_children_filtered_returns_typed_list():
    md = "# A\n## A1\n## A2\n### A2a\n"
    e = MDExtractor(md)
    h2 = e["A"].children.filtered(level=2)
    assert isinstance(h2, SectionList)
    assert [s.title for s in h2] == ["A1", "A2"]
    # isinstance still passes for plain list
    assert isinstance(h2, list)


def test_walk_returns_filterable():
    md = "# A\n## A1\n## A2\n# B\n"
    e = MDExtractor(md)
    walked = e.walk()
    assert isinstance(walked, SectionList)
    only_h2 = walked.filtered(level=2)
    assert [s.title for s in only_h2] == ["A1", "A2"]


def test_section_walk_includes_self_and_descendants():
    md = "# A\n## A1\n## A2\n"
    e = MDExtractor(md)
    walked = e["A"].walk()
    assert isinstance(walked, SectionList)
    assert [s.title for s in walked] == ["A", "A1", "A2"]


def test_find_returns_filterable():
    md = "# A\n## Foo\n# B\n## Foo\n"
    e = MDExtractor(md)
    foos = e.find("Foo")
    assert isinstance(foos, SectionList)
    # Narrow further by level — kwargs filtering works on a find() result.
    h2_foos = foos.filtered(level=2)
    assert isinstance(h2_foos, SectionList)
    assert len(h2_foos) == 2


def test_headers_returns_filterable():
    md = "# A\n## A1\n### A1a\n"
    e = MDExtractor(md)
    headers = e.headers()
    assert isinstance(headers, SectionList)
    deep = headers.filtered(level__gte=2)
    assert [s.title for s in deep] == ["A1", "A1a"]


def test_filtered_returning_empty_keeps_subclass_type():
    md = "# A\nbody\n"
    s = MDExtractor(md)["A"]
    empty = s.blocks.filtered(kind="nonexistent")
    assert empty == []
    assert isinstance(empty, BlockList)


def test_slice_preserves_subclass_type():
    md = "# A\n## A1\n## A2\n## A3\n"
    children = MDExtractor(md)["A"].children
    sliced = children[1:]
    assert isinstance(sliced, SectionList)
    assert [s.title for s in sliced] == ["A2", "A3"]
    # Sliced result is still filterable (no kwargs = shallow copy).
    assert len(sliced.filtered()) == 2


def test_block_children_default_is_filterable():
    md = dedent(
        """
        # S
        - top
            - nested a
            - nested b
        """
    )
    s = MDExtractor(md)["S"]
    outer_list = s.blocks[0]
    assert outer_list.kind == "list"
    # The single top-level item has one nested list among its children.
    nested_lists = outer_list.children[0].children.filtered(kind="list")
    assert isinstance(nested_lists, BlockList)
    assert len(nested_lists) == 1


def test_block_walk_returns_block_list():
    md = dedent(
        """
        # S
        - top
            - nested
        """
    )
    s = MDExtractor(md)["S"]
    walked = s.blocks[0].walk()
    assert isinstance(walked, BlockList)
    items = walked.filtered(kind="list_item")
    assert isinstance(items, BlockList)
    assert len(items) == 2


def test_chained_filters_keep_type():
    md = "# A\n## A1\n### A1a\n## A2\n# B\n## B1\n"
    e = MDExtractor(md)
    result = (
        e.headers()
        .filtered(level=2)
        .filtered(title__startswith="A")
    )
    assert isinstance(result, SectionList)
    assert [s.title for s in result] == ["A1", "A2"]


# ---------- operator-specific coverage


def test_multiple_kwargs_are_anded():
    md = "# S\n```python\nx = 1\n```\n\n```\nplain\n```\n"
    s = MDExtractor(md)["S"]
    py = s.blocks.filtered(kind="code", info="python")
    assert len(py) == 1
    assert py[0].info == "python"


def test_ne_operator():
    md = "# A\n## A1\n### A1a\n"
    e = MDExtractor(md)
    not_h1 = e.headers().filtered(level__ne=1)
    assert [s.title for s in not_h1] == ["A1", "A1a"]


def test_lt_lte_gt_gte_operators():
    e = MDExtractor("# A\n## B\n### C\n#### D\n")
    assert [s.title for s in e.headers().filtered(level__lt=2)] == ["A"]
    assert [s.title for s in e.headers().filtered(level__lte=2)] == ["A", "B"]
    assert [s.title for s in e.headers().filtered(level__gt=3)] == ["D"]
    assert [s.title for s in e.headers().filtered(level__gte=3)] == ["C", "D"]


def test_in_operator():
    e = MDExtractor("# A\n## B\n### C\n")
    only_h1_h3 = e.headers().filtered(level__in=[1, 3])
    assert [s.title for s in only_h1_h3] == ["A", "C"]


def test_startswith_endswith_operators():
    e = MDExtractor("# Section A\n## Subsection 1\n## Other\n")
    assert [s.title for s in e.walk().filtered(title__startswith="Sub")] == [
        "Subsection 1"
    ]
    assert [s.title for s in e.walk().filtered(title__endswith="A")] == ["Section A"]


def test_contains_operator_on_string():
    e = MDExtractor("# Hello World\n## Goodbye\n")
    hits = e.walk().filtered(title__contains="orld")
    assert [s.title for s in hits] == ["Hello World"]


def test_no_kwargs_returns_shallow_copy():
    e = MDExtractor("# A\n# B\n")
    original = e.headers()
    copy = original.filtered()
    assert [s.title for s in copy] == ["A", "B"]
    assert copy is not original
    assert isinstance(copy, SectionList)


def test_missing_attribute_treated_as_no_match():
    # Block has no `.level`; filtering by it should match nothing, not raise.
    s = MDExtractor("# S\nbody\n")["S"]
    assert s.blocks.filtered(level=1) == []


def test_unknown_operator_suffix_treated_as_attr_name():
    # `foo__weirdop=x` — `weirdop` is not in the operator table, so the
    # whole key is treated as an attribute name. No such attribute exists,
    # so no matches and no exception.
    e = MDExtractor("# A\n")
    assert e.headers().filtered(unknown__weirdop="x") == []
