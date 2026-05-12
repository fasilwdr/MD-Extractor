"""Tests for inline-token extraction on paragraph and list_item blocks."""

from textwrap import dedent

from markdown_extractor import BlockList, MDExtractor
from markdown_extractor.inline import parse_inlines


# ---------------------------------------------------------------- parse_inlines unit


def test_parse_inlines_empty_string_returns_empty():
    assert parse_inlines("") == []


def test_parse_inlines_plain_text_returns_empty():
    # No inline markers → no payload (the raw text is already on Block.text).
    assert parse_inlines("Just plain text with no markup") == []


def test_parse_inlines_single_image():
    tokens = parse_inlines("![alt text](img.png)")
    assert len(tokens) == 1
    assert tokens[0].kind == "image"
    assert tokens[0].text == "alt text"
    assert tokens[0].info == "img.png"


def test_parse_inlines_single_link():
    tokens = parse_inlines("[label](https://example.com)")
    assert len(tokens) == 1
    assert tokens[0].kind == "link"
    assert tokens[0].text == "label"
    assert tokens[0].info == "https://example.com"


def test_parse_inlines_inline_code():
    tokens = parse_inlines("`x = 1`")
    assert len(tokens) == 1
    assert tokens[0].kind == "code"
    assert tokens[0].text == "x = 1"
    assert tokens[0].info == ""


def test_parse_inlines_bold():
    tokens = parse_inlines("**strong**")
    assert len(tokens) == 1
    assert tokens[0].kind == "bold"
    assert tokens[0].text == "strong"


def test_parse_inlines_em_star_and_underscore():
    star = parse_inlines("*emphasised*")
    under = parse_inlines("_emphasised_")
    assert len(star) == 1 and star[0].kind == "em" and star[0].text == "emphasised"
    assert len(under) == 1 and under[0].kind == "em" and under[0].text == "emphasised"


def test_parse_inlines_returns_block_list():
    # Type matters: BlockList allows .filtered(kind=...).
    tokens = parse_inlines("![a](x) and [b](y)")
    assert isinstance(tokens, BlockList)
    images = tokens.filtered(kind="image")
    assert len(images) == 1 and images[0].info == "x"


def test_parse_inlines_mixed_text_and_inlines_preserves_order():
    tokens = parse_inlines("see ![alt](src) then [label](url) end")
    kinds = [t.kind for t in tokens]
    assert kinds == ["text", "image", "text", "link", "text"]
    assert tokens[0].text == "see "
    assert tokens[1].text == "alt" and tokens[1].info == "src"
    assert tokens[2].text == " then "
    assert tokens[3].text == "label" and tokens[3].info == "url"
    assert tokens[4].text == " end"


def test_parse_inlines_text_before_first_marker_is_emitted():
    tokens = parse_inlines("prefix `code` suffix")
    assert [t.kind for t in tokens] == ["text", "code", "text"]
    assert tokens[0].text == "prefix "
    assert tokens[2].text == " suffix"


def test_parse_inlines_code_shields_contents():
    # The `**bold**` inside backticks must stay as code, not become bold.
    tokens = parse_inlines("`**bold**`")
    assert len(tokens) == 1
    assert tokens[0].kind == "code"
    assert tokens[0].text == "**bold**"


def test_parse_inlines_image_beats_link_at_same_position():
    # ![alt](src) starts with `!`, the link regex would otherwise match
    # the [alt](src) tail. Tie-breaking on priority means image wins.
    tokens = parse_inlines("![alt](src)")
    assert len(tokens) == 1
    assert tokens[0].kind == "image"


def test_parse_inlines_bold_beats_em_at_same_position():
    tokens = parse_inlines("**word**")
    assert len(tokens) == 1
    assert tokens[0].kind == "bold"


def test_parse_inlines_is_flat_no_recursion_into_bold():
    # Nested formatting stays as raw text inside the outer token —
    # documented limitation. HTML rendering still handles it via
    # substitution order; programmatic consumers can re-parse.
    tokens = parse_inlines("**[link](url)**")
    assert len(tokens) == 1
    assert tokens[0].kind == "bold"
    assert tokens[0].text == "[link](url)"


# ---------------------------------------------------------------- block integration


def test_paragraph_dict_carries_image_inline():
    md = "# A\n![alt text](img.png)\n"
    para = MDExtractor(md)["A"].to_dict()["blocks"][0]
    assert para["kind"] == "paragraph"
    assert para["inlines"] == [
        {"kind": "image", "text": "alt text", "info": "img.png"}
    ]


def test_paragraph_dict_carries_link_inline():
    md = "# A\nSee [docs](https://example.com) for details.\n"
    para = MDExtractor(md)["A"].to_dict()["blocks"][0]
    assert para["inlines"] == [
        {"kind": "text", "text": "See "},
        {"kind": "link", "text": "docs", "info": "https://example.com"},
        {"kind": "text", "text": " for details."},
    ]


def test_list_item_dict_carries_link_inline():
    md = "# A\n- See [docs](https://example.com)\n"
    list_block = MDExtractor(md)["A"].to_dict()["blocks"][0]
    item = list_block["children"][0]
    assert item["kind"] == "list_item"
    assert {"kind": "link", "text": "docs", "info": "https://example.com"} in item["inlines"]


def test_plain_paragraph_dict_omits_inlines_field():
    md = "# A\nJust a plain sentence with no markdown.\n"
    para = MDExtractor(md)["A"].to_dict()["blocks"][0]
    assert "inlines" not in para


def test_user_screenshots_example_exposes_images_structurally():
    # The exact case from the user's bug report.
    md = dedent(
        """
        ## Screenshots

        > Live preview
        ![Animated demo of the module in motion.](static/description/img/img_1.png)

        > Main dashboard
        ![Clean, modern interface that fits right into Odoo.](static/description/img/img_2.png)
        """
    )
    sec = MDExtractor(md).get_section("Screenshots")
    blocks = sec.to_dict()["blocks"]
    # The image paragraphs sit at indices 1 and 3 (alternating with blockquotes).
    img_paras = [b for b in blocks if b["kind"] == "paragraph"]
    assert len(img_paras) == 2
    assert img_paras[0]["inlines"] == [
        {
            "kind": "image",
            "text": "Animated demo of the module in motion.",
            "info": "static/description/img/img_1.png",
        }
    ]
    assert img_paras[1]["inlines"] == [
        {
            "kind": "image",
            "text": "Clean, modern interface that fits right into Odoo.",
            "info": "static/description/img/img_2.png",
        }
    ]


def test_inlines_field_is_filterable_blocklist():
    md = "# A\nSee ![one](a.png) and ![two](b.png) and [link](url).\n"
    para = MDExtractor(md)["A"].blocks[0]
    assert isinstance(para.inlines, BlockList)
    images = para.inlines.filtered(kind="image")
    links = para.inlines.filtered(kind="link")
    assert [(img.text, img.info) for img in images] == [("one", "a.png"), ("two", "b.png")]
    assert [(lk.text, lk.info) for lk in links] == [("link", "url")]


def test_walk_then_inlines_extracts_every_image_in_section():
    md = dedent(
        """
        # Gallery
        Intro ![intro](i.png).

        - bullet with ![bullet](b.png)
        - bullet with [link](u)

        ![standalone](s.png)
        """
    )
    sec = MDExtractor(md)["Gallery"]
    images = [
        t for top in sec.blocks
        for b in top.walk()
        for t in b.inlines
        if t.kind == "image"
    ]
    srcs = [t.info for t in images]
    assert srcs == ["i.png", "b.png", "s.png"]


def test_to_json_includes_inlines():
    import json
    md = "# A\n![alt](src)\n"
    parsed = json.loads(MDExtractor(md)["A"].to_json())
    para = parsed["blocks"][0]
    assert para["inlines"] == [
        {"kind": "image", "text": "alt", "info": "src"}
    ]


# ---------------------------------------------------------------- regression: renderers unchanged


def test_to_html_output_unchanged_for_screenshots_example():
    md = dedent(
        """
        ## Screenshots

        > Live preview
        ![Animated demo.](img1.png)
        """
    )
    html = MDExtractor(md).get_section("Screenshots").to_html()
    # Same shape the user reported as "perfect" before the change.
    assert "<blockquote>" in html and "</blockquote>" in html
    assert "<p>Live preview</p>" in html
    assert '<img src="img1.png" alt="Animated demo.">' in html


def test_to_text_strips_inline_markers_as_before():
    md = "# A\nThis is **bold**, *em*, `code`, and a [link](https://x.com).\n"
    text = MDExtractor(md)["A"].to_text()
    # Existing test_to_text_strips_inline_formatting guarantees match;
    # this is a focused regression now that the regexes moved.
    assert "**" not in text and "`" not in text
    assert "bold" in text and "em" in text and "code" in text and "link" in text
