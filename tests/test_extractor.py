from pathlib import Path
from textwrap import dedent

import pytest

from md_extract import MDExtractor, Section


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
