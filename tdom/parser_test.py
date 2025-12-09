import pytest

from .parser import (
    TComment,
    TDocumentType,
    TElement,
    TemplateParser,
    TFragment,
    TLiteralAttribute,
    TText,
)


def test_parse_empty():
    node = TemplateParser.parse(t"")
    assert node == TText.empty()


def test_parse_text():
    node = TemplateParser.parse(t"Hello, world!")
    assert node == TText.static("Hello, world!")


def test_parse_text_with_entities():
    node = TemplateParser.parse(t"Panini&apos;s")
    assert node == TText.static("Panini&apos;s")


def test_parse_void_element():
    node = TemplateParser.parse(t"<br>")
    assert node == TElement("br")


def test_parse_void_element_self_closed():
    node = TemplateParser.parse(t"<br />")
    assert node == TElement("br")


def test_parse_uppercase_void_element():
    node = TemplateParser.parse(t"<BR>")
    assert node == TElement("br")


def test_parse_standard_element_with_text():
    node = TemplateParser.parse(t"<div>Hello, world!</div>")
    assert node == TElement("div", children=[TText.static("Hello, world!")])


def test_parse_nested_elements():
    node = TemplateParser.parse(t"<div><span>Nested</span> content</div>")
    assert node == TElement(
        "div",
        children=[
            TElement("span", children=[TText.static("Nested")]),
            TText.static(" content"),
        ],
    )


def test_parse_element_with_attributes():
    node = TemplateParser.parse(
        t'<a href="https://example.com" target="_blank">Link</a>'
    )
    assert node == TElement(
        "a",
        attrs=[
            TLiteralAttribute("href", "https://example.com"),
            TLiteralAttribute("target", "_blank"),
        ],
        children=[TText.static("Link")],
    )


def test_parse_element_attribute_order():
    node = TemplateParser.parse(t'<a title="a" href="b" title="c"></a>')
    assert isinstance(node, TElement)
    assert node.attrs == [
        TLiteralAttribute("title", "a"),
        TLiteralAttribute("href", "b"),
        TLiteralAttribute("title", "c"),
    ]


def test_parse_comment():
    node = TemplateParser.parse(t"<!-- This is a comment -->")
    assert node == TComment.static(" This is a comment ")


def test_parse_doctype():
    node = TemplateParser.parse(t"<!DOCTYPE html>")
    assert node == TDocumentType("html")


def test_parse_multiple_voids():
    node = TemplateParser.parse(t"<br><hr><hr /><hr /><br /><br><br>")
    assert node == TFragment(
        children=[
            TElement("br"),
            TElement("hr"),
            TElement("hr"),
            TElement("hr"),
            TElement("br"),
            TElement("br"),
            TElement("br"),
        ]
    )


def test_parse_mixed_content():
    node = TemplateParser.parse(
        t'<!DOCTYPE html><!-- Comment --><div class="container">'
        t"Hello, <br class='funky' />world <!-- neato -->!</div>"
    )
    assert node == TFragment(
        children=[
            TDocumentType("html"),
            TComment.static(" Comment "),
            TElement(
                "div",
                attrs=[TLiteralAttribute("class", "container")],
                children=[
                    TText.static("Hello, "),
                    TElement("br", attrs=[TLiteralAttribute("class", "funky")]),
                    TText.static("world "),
                    TComment.static(" neato "),
                    TText.static("!"),
                ],
            ),
        ]
    )


def test_parse_entities_are_escaped():
    node = TemplateParser.parse(t"<p>&lt;/p&gt;</p>")
    assert node == TElement(
        "p",
        children=[TText.static("&lt;/p&gt;")],
    )


def test_parse_script_tag_content():
    node = TemplateParser.parse(
        t"<script>if (a < b && c > d) {{ alert('wow'); }}</script>"
    )
    assert node == TElement(
        "script",
        children=[TText.static("if (a < b && c > d) { alert('wow'); }")],
    )


def test_parse_script_with_entities():
    # The <script> tag (and <style>) tag uses the CDATA content model.
    node = TemplateParser.parse(t"<script>var x = 'a &amp; b';</script>")
    assert node == TElement(
        "script",
        children=[TText.static("var x = 'a &amp; b';")],
    )


def test_parse_textarea_tag_content():
    node = TemplateParser.parse(
        t"<textarea>if (a < b && c > d) {{ alert('wow'); }}</textarea>"
    )
    assert node == TElement(
        "textarea",
        children=[TText.static("if (a < b && c > d) { alert('wow'); }")],
    )


def test_parse_textarea_with_entities():
    # The <textarea> (and <title>) tag uses the RCDATA content model.
    node = TemplateParser.parse(t"<textarea>var x = 'a &amp; b';</textarea>")
    assert node == TElement(
        "textarea",
        children=[TText.static("var x = 'a & b';")],
    )
    assert str(node) == "<textarea>var x = 'a & b';</textarea>"


def test_parse_title_unusual():
    node = TemplateParser.parse(t"<title>My & Awesome <Site></title>")
    assert node == TElement(
        "title",
        children=[TText.static("My & Awesome <Site>")],
    )


def test_parse_mismatched_tags():
    with pytest.raises(ValueError):
        _ = TemplateParser.parse(t"<div><span>Mismatched</div></span>")


def test_parse_unclosed_tag():
    with pytest.raises(ValueError):
        _ = TemplateParser.parse(t"<div>Unclosed")


def test_parse_unexpected_closing_tag():
    with pytest.raises(ValueError):
        _ = TemplateParser.parse(t"Unopened</div>")


def test_self_closing_tags():
    node = TemplateParser.parse(t"<div/><p></p>")
    assert node == TFragment(
        children=[
            TElement("div"),
            TElement("p"),
        ]
    )


def test_nested_self_closing_tags():
    node = TemplateParser.parse(t"<div><br><div /><br></div>")
    assert node == TElement(
        "div", children=[TElement("br"), TElement("div"), TElement("br")]
    )
    node = TemplateParser.parse(t"<div><div /></div>")
    assert node == TElement("div", children=[TElement("div")])


def test_self_closing_tags_unexpected_closing_tag():
    with pytest.raises(ValueError):
        _ = TemplateParser.parse(t"<div /></div>")


def test_self_closing_void_tags_unexpected_closing_tag():
    with pytest.raises(ValueError):
        _ = TemplateParser.parse(t"<input /></input>")
