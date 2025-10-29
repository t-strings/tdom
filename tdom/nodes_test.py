import pytest

from .nodes import Comment, DocumentType, Element, Fragment, Text


def test_comment():
    comment = Comment("This is a comment")
    assert str(comment) == "<!--This is a comment-->"


def test_comment_empty():
    comment = Comment("")
    assert str(comment) == "<!---->"


def test_comment_special_chars():
    comment = Comment("Special chars: <>&\"'")
    assert str(comment) == "<!--Special chars: <>&\"'-->"


def test_doctype_default():
    doctype = DocumentType()
    assert str(doctype) == "<!DOCTYPE html>"


def test_doctype_custom():
    doctype = DocumentType("xml")
    assert str(doctype) == "<!DOCTYPE xml>"


def test_text():
    text = Text("Hello, world!")
    assert str(text) == "Hello, world!"


def test_text_escaping():
    text = Text("<script>alert('XSS')</script>")
    assert str(text) == "&lt;script&gt;alert(&#39;XSS&#39;)&lt;/script&gt;"


def test_text_safe():
    class CustomHTML(str):
        def __html__(self) -> str:
            return "<b>Bold Text</b>"

    text = Text(CustomHTML())
    assert str(text) == "<b>Bold Text</b>"


def test_fragment_empty():
    fragment = Fragment()
    assert str(fragment) == ""


def test_fragment_with_text():
    fragment = Fragment(children=[Text("test")])
    assert str(fragment) == "test"


def test_fragment_with_multiple_texts():
    fragment = Fragment(children=[Text("Hello"), Text(" "), Text("World")])
    assert str(fragment) == "Hello World"


def test_element_no_children():
    div = Element("div")
    assert not div.is_void
    assert str(div) == "<div></div>"


def test_void_element_no_children():
    br = Element("br")
    assert br.is_void
    assert str(br) == "<br />"


def test_element_invalid_empty_tag():
    with pytest.raises(ValueError):
        _ = Element("")


def test_element_is_content():
    assert Element("script").is_content
    assert Element("title").is_content
    assert not Element("div").is_content
    assert not Element("br").is_content  # Void element


def test_void_element_with_attributes():
    br = Element("br", attrs={"class": "line-break", "hidden": None})
    assert str(br) == '<br class="line-break" hidden />'


def test_void_element_with_children():
    with pytest.raises(ValueError):
        _ = Element("br", children=[Text("should not be here")])


def test_standard_element_with_attributes():
    div = Element(
        "div",
        attrs={"id": "main", "data-role": "container", "hidden": None},
    )
    assert str(div) == '<div id="main" data-role="container" hidden></div>'


def test_standard_element_with_text_child():
    div = Element("div", children=[Text("Hello, world!")])
    assert str(div) == "<div>Hello, world!</div>"


def test_standard_element_with_element_children():
    div = Element(
        "div",
        children=[
            Element("h1", children=[Text("Title")]),
            Element("p", children=[Text("This is a paragraph.")]),
        ],
    )
    assert str(div) == "<div><h1>Title</h1><p>This is a paragraph.</p></div>"


def test_element_with_fragment_with_children():
    div = Element(
        "div",
        children=[
            Fragment(
                children=[
                    Element("div", children=[Text("wow")]),
                    Text("inside fragment"),
                ]
            )
        ],
    )
    assert str(div) == "<div><div>wow</div>inside fragment</div>"


def test_standard_element_with_mixed_children():
    div = Element(
        "div",
        children=[
            Text("Intro text."),
            Element("h1", children=[Text("Title")]),
            Text("Some more text."),
            Element("hr"),
            Element("p", children=[Text("This is a paragraph.")]),
        ],
    )
    assert str(div) == (
        "<div>Intro text.<h1>Title</h1>Some more text.<hr /><p>This is a paragraph.</p></div>"
    )


def test_complex_tree():
    html = Fragment(
        children=[
            DocumentType(),
            Element(
                "html",
                children=[
                    Element(
                        "head",
                        children=[
                            Element("title", children=[Text("Test Page")]),
                            Element("meta", attrs={"charset": "UTF-8"}),
                        ],
                    ),
                    Element(
                        "body",
                        attrs={"class": "main-body"},
                        children=[
                            Element("h1", children=[Text("Welcome to the Test Page")]),
                            Element(
                                "p",
                                children=[
                                    Text("This is a sample paragraph with "),
                                    Element("strong", children=[Text("bold text")]),
                                    Text(" and "),
                                    Element("em", children=[Text("italic text")]),
                                    Text("."),
                                ],
                            ),
                            Element("br"),
                            Element(
                                "ul",
                                children=[
                                    Element("li", children=[Text("Item 1")]),
                                    Element("li", children=[Text("Item 2")]),
                                    Element("li", children=[Text("Item 3")]),
                                ],
                            ),
                        ],
                    ),
                ],
            ),
        ]
    )
    assert str(html) == (
        "<!DOCTYPE html><html><head><title>Test Page</title>"
        '<meta charset="UTF-8" /></head><body class="main-body">'
        "<h1>Welcome to the Test Page</h1>"
        "<p>This is a sample paragraph with <strong>bold text</strong> and "
        "<em>italic text</em>.</p><br /><ul><li>Item 1</li><li>Item 2</li>"
        "<li>Item 3</li></ul></body></html>"
    )


def test_dunder_html_method():
    div = Element("div", children=[Text("Hello")])
    assert div.__html__() == str(div)


def test_escaping_of_text_content():
    div = Element("div", children=[Text("<script>alert('XSS')</script>")])
    assert str(div) == "<div>&lt;script&gt;alert(&#39;XSS&#39;)&lt;/script&gt;</div>"


def test_escaping_of_attribute_values():
    div = Element("div", attrs={"class": '">XSS<'})
    assert str(div) == '<div class="&#34;&gt;XSS&lt;"></div>'
