import pytest

from .nodes import Comment, DocumentType, Element, Fragment, Text
from .parser import parse_html


def test_parse_empty():
    node = parse_html("")
    assert node == Text("")


def test_parse_text():
    node = parse_html("Hello, world!")
    assert node == Text("Hello, world!")


def test_parse_text_with_entities():
    node = parse_html("Panini&apos;s")
    assert node == Text("Panini's")


def test_parse_void_element():
    node = parse_html("<br>")
    assert node == Element("br")


def test_parse_void_element_self_closed():
    node = parse_html("<br />")
    assert node == Element("br")


def test_parse_uppercase_void_element():
    node = parse_html("<BR>")
    assert node == Element("br")


def test_parse_standard_element_with_text():
    node = parse_html("<div>Hello, world!</div>")
    assert node == Element("div", children=[Text("Hello, world!")])


def test_parse_nested_elements():
    node = parse_html("<div><span>Nested</span> content</div>")
    assert node == Element(
        "div",
        children=[
            Element("span", children=[Text("Nested")]),
            Text(" content"),
        ],
    )


def test_parse_element_with_attributes():
    node = parse_html('<a href="https://example.com" target="_blank">Link</a>')
    assert node == Element(
        "a",
        attrs={"href": "https://example.com", "target": "_blank"},
        children=[Text("Link")],
    )


def test_parse_comment():
    node = parse_html("<!-- This is a comment -->")
    assert node == Comment(" This is a comment ")


def test_parse_doctype():
    node = parse_html("<!DOCTYPE html>")
    assert node == DocumentType("html")


def test_parse_multiple_voids():
    node = parse_html("<br><hr><hr /><hr /><br /><br><br>")
    assert node == Fragment(
        children=[
            Element("br"),
            Element("hr"),
            Element("hr"),
            Element("hr"),
            Element("br"),
            Element("br"),
            Element("br"),
        ]
    )


def test_parse_mixed_content():
    node = parse_html(
        '<!DOCTYPE html><!-- Comment --><div class="container">'
        "Hello, <br class='funky' />world <!-- neato -->!</div>"
    )
    assert node == Fragment(
        children=[
            DocumentType("html"),
            Comment(" Comment "),
            Element(
                "div",
                attrs={"class": "container"},
                children=[
                    Text("Hello, "),
                    Element("br", attrs={"class": "funky"}),
                    Text("world "),
                    Comment(" neato "),
                    Text("!"),
                ],
            ),
        ]
    )


def test_parse_script_tag_content():
    node = parse_html("<script>if (a < b && c > d) { alert('wow'); }</script>")
    assert node == Element(
        "script",
        children=[Text("if (a < b && c > d) { alert('wow'); }")],
    )
    assert str(node) == ("<script>if (a < b && c > d) { alert('wow'); }</script>")


def test_parse_script_with_entities():
    # The <script> tag (and <style>) tag uses the CDATA content model.
    node = parse_html("<script>var x = 'a &amp; b';</script>")
    assert node == Element(
        "script",
        children=[Text("var x = 'a &amp; b';")],
    )
    assert str(node) == "<script>var x = 'a &amp; b';</script>"


def test_parse_textarea_tag_content():
    node = parse_html("<textarea>if (a < b && c > d) { alert('wow'); }</textarea>")
    assert node == Element(
        "textarea",
        children=[Text("if (a < b && c > d) { alert('wow'); }")],
    )
    assert str(node) == "<textarea>if (a < b && c > d) { alert('wow'); }</textarea>"


def test_parse_textarea_with_entities():
    # The <textarea> (and <title>) tag uses the RCDATA content model.
    node = parse_html("<textarea>var x = 'a &amp; b';</textarea>")
    assert node == Element(
        "textarea",
        children=[Text("var x = 'a & b';")],
    )
    assert str(node) == "<textarea>var x = 'a & b';</textarea>"


def test_parse_title_unusual():
    node = parse_html("<title>My & Awesome <Site></title>")
    assert node == Element(
        "title",
        children=[Text("My & Awesome <Site>")],
    )
    assert str(node) == "<title>My & Awesome <Site></title>"


def test_parse_mismatched_tags():
    with pytest.raises(ValueError):
        _ = parse_html("<div><span>Mismatched</div></span>")


def test_parse_unclosed_tag():
    with pytest.raises(ValueError):
        _ = parse_html("<div>Unclosed")


def test_parse_unexpected_closing_tag():
    with pytest.raises(ValueError):
        _ = parse_html("Unopened</div>")


def test_nested_self_closing_tags():
    node = parse_html("<div></div><br>")
    assert node == Fragment(
        children=[
            Element("div"),
            Element("br"),
        ]
    )


def test_parse_html_iter_preserves_chunks():
    chunks = [
        "<div>",
        "Hello ",
        "there, ",
        "<span>world</span>",
        "!</div>",
    ]
    node = parse_html(chunks)
    assert node == Element(
        "div",
        children=[
            Text("Hello "),
            Text("there, "),
            Element("span", children=[Text("world")]),
            Text("!"),
        ],
    )
