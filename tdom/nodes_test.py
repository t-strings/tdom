import pytest
from markupsafe import Markup
from dataclasses import dataclass, field
import datetime
import typing as t
from string.templatelib import Interpolation, Template
from itertools import product

from .placeholders import make_placeholder_config
from .processor import prep_component_kwargs
from .callables import get_callable_info
from .nodes import Comment, DocumentType, Element, Fragment, Text, to_node, Node


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


def test_text_equality():
    text1 = Text("<Hello>")
    text2 = Text(Markup("&lt;Hello&gt;"))
    text3 = Text(Markup("<Hello>"))
    assert text1 == text2
    assert text1 != text3


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


#
# to_node()
#
def test_empty():
    node = to_node(t"")
    assert node == Fragment(children=[])
    assert str(node) == ""


def test_text_literal():
    node = to_node(t"Hello, world!")
    assert node == Text("Hello, world!")
    assert str(node) == "Hello, world!"


def test_text_singleton():
    greeting = "Hello, Alice!"
    node = to_node(t"{greeting}")
    assert node == Text("Hello, Alice!")
    assert str(node) == "Hello, Alice!"


def test_text_template():
    name = "Alice"
    node = to_node(t"Hello, {name}!")
    assert node == Fragment(children=[Text("Hello, "), Text("Alice"), Text("!")])
    assert str(node) == "Hello, Alice!"


def test_text_template_escaping():
    name = "Alice & Bob"
    node = to_node(t"Hello, {name}!")
    assert node == Fragment(children=[Text("Hello, "), Text("Alice & Bob"), Text("!")])
    assert str(node) == "Hello, Alice &amp; Bob!"


#
# Comments.
#
def test_comment():
    node = to_node(t"<!--This is a comment-->")
    assert node == Comment("This is a comment")
    assert str(node) == "<!--This is a comment-->"


def test_comment_empty():
    node = to_node(t"<!---->")
    assert node == Comment("")
    assert str(node) == "<!---->"


def test_comment_template():
    text = "comment"
    node = to_node(t"<!--This is a {text}-->")
    assert node == Comment("This is a comment")
    assert str(node) == "<!--This is a comment-->"


def test_comment_template_escaping():
    text = "-->comment"
    node = to_node(t"<!--This is a {text}-->")
    assert node == Comment("This is a -->comment")
    assert str(node) == "<!--This is a --&gt;comment-->"


def test_comment_special_chars():
    node = to_node(t"<!--Special chars: <>&\"'-->")
    assert node == Comment("Special chars: <>&\"'")
    assert str(node) == "<!--Special chars: <>&\"'-->"


#
# Document types.
#
def test_parse_document_type():
    node = to_node(t"<!doctype html>")
    assert node == DocumentType("html")
    assert str(node) == "<!DOCTYPE html>"


#
# Elements
#
def test_parse_void_element():
    node = to_node(t"<br>")
    assert node == Element("br")
    assert str(node) == "<br />"


def test_parse_void_element_self_closed():
    node = to_node(t"<br />")
    assert node == Element("br")
    assert str(node) == "<br />"


def test_parse_chain_of_void_elements():
    # Make sure our handling of CPython issue #69445 is reasonable.
    node = to_node(t"<br><hr><img src='image.png' /><br /><hr>")
    assert node == Fragment(
        children=[
            Element("br"),
            Element("hr"),
            Element("img", attrs={"src": "image.png"}),
            Element("br"),
            Element("hr"),
        ],
    )
    assert str(node) == '<br /><hr /><img src="image.png" /><br /><hr />'


def test_parse_element_with_text():
    node = to_node(t"<p>Hello, world!</p>")
    assert node == Element(
        "p",
        children=[
            Text("Hello, world!"),
        ],
    )
    assert str(node) == "<p>Hello, world!</p>"


def test_parse_nested_elements():
    node = to_node(t"<div><p>Hello</p><p>World</p></div>")
    assert node == Element(
        "div",
        children=[
            Element("p", children=[Text("Hello")]),
            Element("p", children=[Text("World")]),
        ],
    )
    assert str(node) == "<div><p>Hello</p><p>World</p></div>"


def test_parse_entities_are_escaped():
    node = to_node(t"<p>&lt;/p&gt;</p>")
    assert node == Element(
        "p",
        children=[Text("</p>")],
    )
    assert str(node) == "<p>&lt;/p&gt;</p>"


# --------------------------------------------------------------------------
# Interpolated text content
# --------------------------------------------------------------------------


def test_interpolated_text_content():
    name = "Alice"
    node = to_node(t"<p>Hello, {name}!</p>")
    assert node == Element("p", children=[Text("Hello, "), Text("Alice"), Text("!")])
    assert str(node) == "<p>Hello, Alice!</p>"


def test_escaping_of_interpolated_text_content():
    name = "<Alice & Bob>"
    node = to_node(t"<p>Hello, {name}!</p>")
    assert node == Element(
        "p", children=[Text("Hello, "), Text("<Alice & Bob>"), Text("!")]
    )
    assert str(node) == "<p>Hello, &lt;Alice &amp; Bob&gt;!</p>"


class Convertible:
    def __str__(self):
        return "string"

    def __repr__(self):
        return "repr"


def test_conversions():
    c = Convertible()
    assert f"{c!s}" == "string"
    assert f"{c!r}" == "repr"
    node = to_node(t"<li>{c!s}</li><li>{c!r}</li><li>{'😊'!a}</li>")
    assert node == Fragment(
        children=[
            Element("li", children=[Text("string")]),
            Element("li", children=[Text("repr")]),
            Element("li", children=[Text("'\\U0001f60a'")]),
        ],
    )


def test_interpolated_in_content_node():
    # https://github.com/t-strings/tdom/issues/68
    evil = "</style><script>alert('whoops');</script><style>"
    node = to_node(t"<style>{evil}{evil}</style>")
    assert node == Element(
        "style",
        children=[
            Text("</style><script>alert('whoops');</script><style>"),
            Text("</style><script>alert('whoops');</script><style>"),
        ],
    )
    LT = "&lt;"
    assert (
        str(node)
        == f"<style>{LT}/style><script>alert('whoops');</script><style>{LT}/style><script>alert('whoops');</script><style></style>"
    )


def test_interpolated_trusted_in_content_node():
    # https://github.com/t-strings/tdom/issues/68
    node = to_node(t"<script>if (a < b && c > d) {{ alert('wow'); }}</script>")
    assert node == Element(
        "script",
        children=[Text("if (a < b && c > d) { alert('wow'); }")],
    )
    assert str(node) == ("<script>if (a < b && c > d) { alert('wow'); }</script>")


def test_script_elements_error():
    nested_template = t"<div></div>"
    # Putting non-text content inside a script is not allowed.
    with pytest.raises(ValueError):
        node = to_node(t"<script>{nested_template}</script>")
        _ = str(node)


# --------------------------------------------------------------------------
# Interpolated non-text content
# --------------------------------------------------------------------------


def test_interpolated_false_content():
    node = to_node(t"<div>{False}</div>")
    assert node == Element("div")
    assert str(node) == "<div></div>"


def test_interpolated_none_content():
    node = to_node(t"<div>{None}</div>")
    assert node == Element("div", children=[])
    assert str(node) == "<div></div>"


def test_interpolated_zero_arg_function():
    def get_value():
        return "dynamic"

    node = to_node(t"<p>The value is {get_value}.</p>")
    assert node == Element(
        "p", children=[Text("The value is "), Text("dynamic"), Text(".")]
    )


def test_interpolated_multi_arg_function_fails():
    def add(a, b):  # pragma: no cover
        return a + b

    with pytest.raises(TypeError):
        _ = to_node(t"<p>The sum is {add}.</p>")


# --------------------------------------------------------------------------
# Raw HTML injection tests
# --------------------------------------------------------------------------


def test_raw_html_injection_with_markupsafe():
    raw_content = Markup("<strong>I am bold</strong>")
    node = to_node(t"<div>{raw_content}</div>")
    assert node == Element("div", children=[Text(text=raw_content)])
    assert str(node) == "<div><strong>I am bold</strong></div>"


def test_raw_html_injection_with_dunder_html_protocol():
    class SafeContent:
        def __init__(self, text):
            self._text = text

        def __html__(self):
            # In a real app, this would come from a sanitizer or trusted source
            return f"<em>{self._text}</em>"

    content = SafeContent("emphasized")
    node = to_node(t"<p>Here is some {content}.</p>")
    assert node == Element(
        "p",
        children=[
            Text("Here is some "),
            Text(Markup("<em>emphasized</em>")),
            Text("."),
        ],
    )
    assert str(node) == "<p>Here is some <em>emphasized</em>.</p>"


def test_raw_html_injection_with_format_spec():
    raw_content = "<u>underlined</u>"
    node = to_node(t"<p>This is {raw_content:safe} text.</p>")
    assert node == Element(
        "p",
        children=[
            Text("This is "),
            Text(Markup(raw_content)),
            Text(" text."),
        ],
    )
    assert str(node) == "<p>This is <u>underlined</u> text.</p>"


def test_raw_html_injection_with_markupsafe_unsafe_format_spec():
    supposedly_safe = Markup("<i>italic</i>")
    node = to_node(t"<p>This is {supposedly_safe:unsafe} text.</p>")
    assert node == Element(
        "p",
        children=[
            Text("This is "),
            Text(str(supposedly_safe)),
            Text(" text."),
        ],
    )
    assert str(node) == "<p>This is &lt;i&gt;italic&lt;/i&gt; text.</p>"


# --------------------------------------------------------------------------
# Conditional rendering and control flow
# --------------------------------------------------------------------------


def test_conditional_rendering_with_if_else():
    is_logged_in = True
    user_profile = t"<span>Welcome, User!</span>"
    login_prompt = t"<a href='/login'>Please log in</a>"
    node = to_node(t"<div>{user_profile if is_logged_in else login_prompt}</div>")

    assert node == Element(
        "div", children=[Element("span", children=[Text("Welcome, User!")])]
    )
    assert str(node) == "<div><span>Welcome, User!</span></div>"

    is_logged_in = False
    node = to_node(t"<div>{user_profile if is_logged_in else login_prompt}</div>")
    assert str(node) == '<div><a href="/login">Please log in</a></div>'


def test_conditional_rendering_with_and():
    show_warning = True
    warning_message = t'<div class="warning">Warning!</div>'
    node = to_node(t"<main>{show_warning and warning_message}</main>")

    assert node == Element(
        "main",
        children=[
            Element("div", attrs={"class": "warning"}, children=[Text("Warning!")]),
        ],
    )
    assert str(node) == '<main><div class="warning">Warning!</div></main>'

    show_warning = False
    node = to_node(t"<main>{show_warning and warning_message}</main>")
    # Assuming False renders nothing
    assert str(node) == "<main></main>"


# --------------------------------------------------------------------------
# Interpolated nesting of templates and elements
# --------------------------------------------------------------------------


def test_interpolated_template_content():
    child = t"<span>Child</span>"
    node = to_node(t"<div>{child}</div>")
    assert node == Element("div", children=[to_node(child)])
    assert str(node) == "<div><span>Child</span></div>"


def test_interpolated_element_content():
    child = to_node(t"<span>Child</span>")
    node = to_node(t"<div>{child}</div>")
    assert node == Element("div", children=[child])
    assert str(node) == "<div><span>Child</span></div>"


def test_interpolated_nonstring_content():
    number = 42
    node = to_node(t"<p>The answer is {number}.</p>")
    assert node == Element(
        "p", children=[Text("The answer is "), Text("42"), Text(".")]
    )
    assert str(node) == "<p>The answer is 42.</p>"


def test_list_items():
    items = ["Apple", "Banana", "Cherry"]
    node = to_node(t"<ul>{[t'<li>{item}</li>' for item in items]}</ul>")
    assert node == Element(
        "ul",
        children=[
            Element("li", children=[Text("Apple")]),
            Element("li", children=[Text("Banana")]),
            Element("li", children=[Text("Cherry")]),
        ],
    )
    assert str(node) == "<ul><li>Apple</li><li>Banana</li><li>Cherry</li></ul>"


def test_nested_list_items():
    # TODO XXX this is a pretty abusrd test case; clean it up when refactoring
    outer = ["fruit", "more fruit"]
    inner = ["apple", "banana", "cherry"]
    inner_items = [t"<li>{item}</li>" for item in inner]
    outer_items = [t"<li>{category}<ul>{inner_items}</ul></li>" for category in outer]
    node = to_node(t"<ul>{outer_items}</ul>")
    assert node == Element(
        "ul",
        children=[
            Element(
                "li",
                children=[
                    Text("fruit"),
                    Element(
                        "ul",
                        children=[
                            Element("li", children=[Text("apple")]),
                            Element("li", children=[Text("banana")]),
                            Element("li", children=[Text("cherry")]),
                        ],
                    ),
                ],
            ),
            Element(
                "li",
                children=[
                    Text("more fruit"),
                    Element(
                        "ul",
                        children=[
                            Element("li", children=[Text("apple")]),
                            Element("li", children=[Text("banana")]),
                            Element("li", children=[Text("cherry")]),
                        ],
                    ),
                ],
            ),
        ],
    )
    assert (
        str(node)
        == "<ul><li>fruit<ul><li>apple</li><li>banana</li><li>cherry</li></ul></li><li>more fruit<ul><li>apple</li><li>banana</li><li>cherry</li></ul></li></ul>"
    )


# --------------------------------------------------------------------------
# Attributes
# --------------------------------------------------------------------------


def test_literal_attrs():
    node = to_node(
        (
            t"<a "
            t" id=example_link"  # no quotes allowed without spaces
            t" autofocus"  # bare / boolean
            t' title=""'  # empty attribute
            t' href="https://example.com" target="_blank"'
            t"></a>"
        )
    )
    assert node == Element(
        "a",
        attrs={
            "id": "example_link",
            "autofocus": None,
            "title": "",
            "href": "https://example.com",
            "target": "_blank",
        },
    )
    assert (
        str(node)
        == '<a id="example_link" autofocus title="" href="https://example.com" target="_blank"></a>'
    )


def test_literal_attr_escaped():
    node = to_node(t'<a title="&lt;"></a>')
    assert node == Element(
        "a",
        attrs={"title": "<"},
    )
    assert str(node) == '<a title="&lt;"></a>'


def test_interpolated_attr():
    url = "https://example.com/"
    node = to_node(t'<a href="{url}"></a>')
    assert node == Element("a", attrs={"href": "https://example.com/"})
    assert str(node) == '<a href="https://example.com/"></a>'


def test_interpolated_attr_escaped():
    url = 'https://example.com/?q="test"&lang=en'
    node = to_node(t'<a href="{url}"></a>')
    assert node == Element(
        "a",
        attrs={"href": 'https://example.com/?q="test"&lang=en'},
    )
    assert (
        str(node) == '<a href="https://example.com/?q=&#34;test&#34;&amp;lang=en"></a>'
    )


def test_interpolated_attr_unquoted():
    id = "roquefort"
    node = to_node(t"<div id={id}></div>")
    assert node == Element("div", attrs={"id": "roquefort"})
    assert str(node) == '<div id="roquefort"></div>'


def test_interpolated_attr_true():
    disabled = True
    node = to_node(t"<button disabled={disabled}></button>")
    assert node == Element("button", attrs={"disabled": None})
    assert str(node) == "<button disabled></button>"


def test_interpolated_attr_false():
    disabled = False
    node = to_node(t"<button disabled={disabled}></button>")
    assert node == Element("button")
    assert str(node) == "<button></button>"


def test_interpolated_attr_none():
    disabled = None
    node = to_node(t"<button disabled={disabled}></button>")
    assert node == Element("button")
    assert str(node) == "<button></button>"


def test_interpolate_attr_empty_string():
    node = to_node(t'<div title=""></div>')
    assert node == Element(
        "div",
        attrs={"title": ""},
    )
    assert str(node) == '<div title=""></div>'


def test_spread_attr():
    attrs = {"href": "https://example.com/", "target": "_blank"}
    node = to_node(t"<a {attrs}></a>")
    assert node == Element(
        "a",
        attrs={"href": "https://example.com/", "target": "_blank"},
    )
    assert str(node) == '<a href="https://example.com/" target="_blank"></a>'


def test_spread_attr_none():
    attrs = None
    node = to_node(t"<a {attrs}></a>")
    assert node == Element("a")
    assert str(node) == "<a></a>"


def test_spread_attr_type_errors():
    for attrs in (0, [], (), False, True):
        with pytest.raises(TypeError):
            _ = to_node(t"<a {attrs}></a>")


def test_templated_attr_mixed_interpolations_start_end_and_nest():
    left, middle, right = 1, 3, 5
    prefix, suffix = t'<div data-range="', t'"></div>'
    # Check interpolations at start, middle and/or end of templated attr
    # or a combination of those to make sure text is not getting dropped.
    for left_part, middle_part, right_part in product(
        (t"{left}", Template(str(left))),
        (t"{middle}", Template(str(middle))),
        (t"{right}", Template(str(right))),
    ):
        test_t = prefix + left_part + t"-" + middle_part + t"-" + right_part + suffix
        node = to_node(test_t)
        assert node == Element(
            "div",
            attrs={"data-range": "1-3-5"},
        )
        assert str(node) == '<div data-range="1-3-5"></div>'


def test_templated_attr_no_quotes():
    start = 1
    end = 5
    node = to_node(t"<div data-range={start}-{end}></div>")
    assert node == Element(
        "div",
        attrs={"data-range": "1-5"},
    )
    assert str(node) == '<div data-range="1-5"></div>'


def test_attr_merge_disjoint_interpolated_attr_spread_attr():
    attrs = {"href": "https://example.com/", "id": "link1"}
    target = "_blank"
    node = to_node(t"<a {attrs} target={target}></a>")
    assert node == Element(
        "a",
        attrs={"href": "https://example.com/", "id": "link1", "target": "_blank"},
    )
    assert str(node) == '<a href="https://example.com/" id="link1" target="_blank"></a>'


def test_attr_merge_overlapping_spread_attrs():
    attrs1 = {"href": "https://example.com/", "id": "overwrtten"}
    attrs2 = {"target": "_blank", "id": "link1"}
    node = to_node(t"<a {attrs1} {attrs2}></a>")
    assert node == Element(
        "a",
        attrs={"href": "https://example.com/", "target": "_blank", "id": "link1"},
    )
    assert str(node) == '<a href="https://example.com/" target="_blank" id="link1"></a>'


def test_attr_merge_replace_literal_attr_str_str():
    node = to_node(t'<div title="default" {dict(title="fresh")}></div>')
    assert node == Element("div", {"title": "fresh"})
    assert str(node) == '<div title="fresh"></div>'


def test_attr_merge_replace_literal_attr_str_true():
    node = to_node(t'<div title="default" {dict(title=True)}></div>')
    assert node == Element("div", {"title": None})
    assert str(node) == "<div title></div>"


def test_attr_merge_replace_literal_attr_true_str():
    node = to_node(t"<div title {dict(title='fresh')}></div>")
    assert node == Element("div", {"title": "fresh"})
    assert str(node) == '<div title="fresh"></div>'


def test_attr_merge_remove_literal_attr_str_none():
    node = to_node(t'<div title="default" {dict(title=None)}></div>')
    assert node == Element("div")
    assert str(node) == "<div></div>"


def test_attr_merge_remove_literal_attr_true_none():
    node = to_node(t"<div title {dict(title=None)}></div>")
    assert node == Element("div")
    assert str(node) == "<div></div>"


def test_attr_merge_other_literal_attr_intact():
    node = to_node(t'<img title="default" {dict(alt="fresh")}>')
    assert node == Element("img", {"title": "default", "alt": "fresh"})
    assert str(node) == '<img title="default" alt="fresh" />'


def test_placeholder_collision_avoidance():
    config = make_placeholder_config()
    # This test is to ensure that our placeholder detection avoids collisions
    # even with content that might look like a placeholder.
    tricky = "0"
    template = Template(
        f'<div data-tricky="{config.prefix}',
        Interpolation(tricky, "tricky", None, ""),
        f'{config.suffix}"></div>',
    )
    node = to_node(template)
    assert node == Element(
        "div",
        attrs={"data-tricky": config.prefix + tricky + config.suffix},
        children=[],
    )
    assert (
        str(node) == f'<div data-tricky="{config.prefix}{tricky}{config.suffix}"></div>'
    )


#
# Special data attribute handling.
#
def test_interpolated_data_attributes():
    data = {"user-id": 123, "role": "admin", "wild": True, "false": False, "none": None}
    node = to_node(t"<div data={data}>User Info</div>")
    assert node == Element(
        "div",
        attrs={"data-user-id": "123", "data-role": "admin", "data-wild": None},
        children=[Text("User Info")],
    )
    assert (
        str(node)
        == '<div data-user-id="123" data-role="admin" data-wild>User Info</div>'
    )


def test_data_attr_toggle_to_str():
    for node in [
        to_node(t"<div data-selected data={dict(selected='yes')}></div>"),
        to_node(t'<div data-selected="no" data={dict(selected="yes")}></div>'),
    ]:
        assert node == Element("div", {"data-selected": "yes"})
        assert str(node) == '<div data-selected="yes"></div>'


def test_data_attr_toggle_to_true():
    node = to_node(t'<div data-selected="yes" data={dict(selected=True)}></div>')
    assert node == Element("div", {"data-selected": None})
    assert str(node) == "<div data-selected></div>"


def test_data_attr_unrelated_unaffected():
    node = to_node(t"<div data-selected data={dict(active=True)}></div>")
    assert node == Element("div", {"data-selected": None, "data-active": None})
    assert str(node) == "<div data-selected data-active></div>"


def test_data_attr_templated_error():
    data1 = {"user-id": "user-123"}
    data2 = {"role": "admin"}
    with pytest.raises(TypeError):
        node = to_node(t'<div data="{data1} {data2}"></div>')
        print(str(node))


def test_data_attr_none():
    button_data = None
    node = to_node(t"<button data={button_data}>X</button>")
    assert node == Element("button", children=[Text("X")])
    assert str(node) == "<button>X</button>"


def test_data_attr_errors():
    for v in [False, [], (), 0, "data?"]:
        with pytest.raises(TypeError):
            _ = to_node(t"<button data={v}>X</button>")


def test_data_literal_attr_bypass():
    # Trigger overall attribute resolution with an unrelated interpolated attr.
    node = to_node(t'<p data="passthru" id={"resolved"}></p>')
    assert node == Element(
        "p",
        attrs={"data": "passthru", "id": "resolved"},
    ), "A single literal attribute should not trigger data expansion."


#
# Special aria attribute handling.
#
def test_aria_templated_attr_error():
    aria1 = {"label": "close"}
    aria2 = {"hidden": "true"}
    with pytest.raises(TypeError):
        node = to_node(t'<div aria="{aria1} {aria2}"></div>')
        print(str(node))


def test_aria_interpolated_attr_dict():
    aria = {"label": "Close", "hidden": True, "another": False, "more": None}
    node = to_node(t"<button aria={aria}>X</button>")
    assert node == Element(
        "button",
        attrs={"aria-label": "Close", "aria-hidden": "true", "aria-another": "false"},
        children=[Text("X")],
    )
    assert (
        str(node)
        == '<button aria-label="Close" aria-hidden="true" aria-another="false">X</button>'
    )


def test_aria_interpolate_attr_none():
    button_aria = None
    node = to_node(t"<button aria={button_aria}>X</button>")
    assert node == Element("button", children=[Text("X")])
    assert str(node) == "<button>X</button>"


def test_aria_attr_errors():
    for v in [False, [], (), 0, "aria?"]:
        with pytest.raises(TypeError):
            _ = to_node(t"<button aria={v}>X</button>")


def test_aria_literal_attr_bypass():
    # Trigger overall attribute resolution with an unrelated interpolated attr.
    node = to_node(t'<p aria="passthru" id={"resolved"}></p>')
    assert node == Element(
        "p",
        attrs={"aria": "passthru", "id": "resolved"},
    ), "A single literal attribute should not trigger aria expansion."


#
# Special class attribute handling.
#
def test_interpolated_class_attribute():
    class_list = ["btn", "btn-primary", "one two", None]
    class_dict = {"active": True, "btn-secondary": False}
    class_str = "blue"
    class_space_sep_str = "green yellow"
    class_none = None
    class_empty_list = []
    class_empty_dict = {}
    button_t = (
        t"<button "
        t' class="red" class={class_list} class={class_dict}'
        t" class={class_empty_list} class={class_empty_dict}"  # ignored
        t" class={class_none}"  # ignored
        t" class={class_str} class={class_space_sep_str}"
        t" >Click me</button>"
    )
    node = to_node(button_t)
    assert node == Element(
        "button",
        attrs={"class": "red btn btn-primary one two active blue green yellow"},
        children=[Text("Click me")],
    )
    assert (
        str(node)
        == '<button class="red btn btn-primary one two active blue green yellow">Click me</button>'
    )


def test_interpolated_class_attribute_with_multiple_placeholders():
    classes1 = ["btn", "btn-primary"]
    classes2 = [False and "disabled", None, {"active": True}]
    node = to_node(t'<button class="{classes1} {classes2}">Click me</button>')
    # CONSIDER: Is this what we want? Currently, when we have multiple
    # placeholders in a single attribute, we treat it as a string attribute.
    assert node == Element(
        "button",
        attrs={"class": "['btn', 'btn-primary'] [False, None, {'active': True}]"},
        children=[Text("Click me")],
    )


def test_interpolated_attribute_spread_with_class_attribute():
    attrs = {"id": "button1", "class": ["btn", "btn-primary"]}
    node = to_node(t"<button {attrs}>Click me</button>")
    assert node == Element(
        "button",
        attrs={"id": "button1", "class": "btn btn-primary"},
        children=[Text("Click me")],
    )
    assert str(node) == '<button id="button1" class="btn btn-primary">Click me</button>'


def test_class_literal_attr_bypass():
    # Trigger overall attribute resolution with an unrelated interpolated attr.
    node = to_node(t'<p class="red red" id={"veryred"}></p>')
    assert node == Element(
        "p",
        attrs={"class": "red red", "id": "veryred"},
    ), "A single literal attribute should not trigger class accumulator."


def test_class_none_ignored():
    class_item = None
    node = to_node(t"<p class={class_item}></p>")
    assert node == Element("p")
    # Also ignored inside a sequence.
    node = to_node(t"<p class={[class_item]}></p>")
    assert node == Element("p")


def test_class_type_errors():
    for class_item in (False, True, 0):
        with pytest.raises(TypeError):
            _ = to_node(t"<p class={class_item}></p>")
        with pytest.raises(TypeError):
            _ = to_node(t"<p class={[class_item]}></p>")


def test_class_merge_literals():
    node = to_node(t'<p class="red" class="blue"></p>')
    assert node == Element("p", {"class": "red blue"})


def test_class_merge_literal_then_interpolation():
    class_item = "blue"
    node = to_node(t'<p class="red" class="{[class_item]}"></p>')
    assert node == Element("p", {"class": "red blue"})


#
# Special style attribute handling.
#
def test_style_literal_attr_passthru():
    p_id = "para1"  # non-literal attribute to cause attr resolution
    node = to_node(t'<p style="color: red" id={p_id}>Warning!</p>')
    assert node == Element(
        "p",
        attrs={"style": "color: red", "id": "para1"},
        children=[Text("Warning!")],
    )
    assert str(node) == '<p style="color: red" id="para1">Warning!</p>'


def test_style_in_interpolated_attr():
    styles = {"color": "red", "font-weight": "bold", "font-size": "16px"}
    node = to_node(t"<p style={styles}>Warning!</p>")
    assert node == Element(
        "p",
        attrs={"style": "color: red; font-weight: bold; font-size: 16px"},
        children=[Text("Warning!")],
    )
    assert (
        str(node)
        == '<p style="color: red; font-weight: bold; font-size: 16px">Warning!</p>'
    )


def test_style_in_templated_attr():
    color = "red"
    node = to_node(t'<p style="color: {color}">Warning!</p>')
    assert node == Element(
        "p",
        attrs={"style": "color: red"},
        children=[Text("Warning!")],
    )
    assert str(node) == '<p style="color: red">Warning!</p>'


def test_style_in_spread_attr():
    attrs = {"style": {"color": "red"}}
    node = to_node(t"<p {attrs}>Warning!</p>")
    assert node == Element(
        "p",
        attrs={"style": "color: red"},
        children=[Text("Warning!")],
    )
    assert str(node) == '<p style="color: red">Warning!</p>'


def test_style_merged_from_all_attrs():
    attrs = dict(style="font-size: 15px")
    style = {"font-weight": "bold"}
    color = "red"
    node = to_node(
        t'<p style="font-family: serif" style="color: {color}" style={style} {attrs}></p>'
    )
    assert node == Element(
        "p",
        {"style": "font-family: serif; color: red; font-weight: bold; font-size: 15px"},
    )
    assert (
        str(node)
        == '<p style="font-family: serif; color: red; font-weight: bold; font-size: 15px"></p>'
    )


def test_style_override_left_to_right():
    suffix = t"></p>"
    parts = [
        (t'<p style="color: red"', "color: red"),
        (t" style={dict(color='blue')}", "color: blue"),
        (t''' style="color: {"green"}"''', "color: green"),
        (t""" {dict(style=dict(color="yellow"))}""", "color: yellow"),
    ]
    for index in range(len(parts)):
        expected_style = parts[index][1]
        t = sum([part[0] for part in parts[: index + 1]], t"") + suffix
        node = to_node(t)
        assert node == Element("p", {"style": expected_style})
        assert str(node) == f'<p style="{expected_style}"></p>'


def test_interpolated_style_attribute_multiple_placeholders():
    styles1 = {"color": "red"}
    styles2 = {"font-weight": "bold"}
    # CONSIDER: Is this what we want? Currently, when we have multiple
    # placeholders in a single attribute, we treat it as a string attribute
    # which produces an invalid style attribute.
    with pytest.raises(ValueError):
        _ = to_node(t"<p style='{styles1} {styles2}'>Warning!</p>")


def test_interpolated_style_attribute_merged():
    styles1 = {"color": "red"}
    styles2 = {"font-weight": "bold"}
    node = to_node(t"<p style={styles1} style={styles2}>Warning!</p>")
    assert node == Element(
        "p",
        attrs={"style": "color: red; font-weight: bold"},
        children=[Text("Warning!")],
    )
    assert str(node) == '<p style="color: red; font-weight: bold">Warning!</p>'


def test_interpolated_style_attribute_merged_override():
    styles1 = {"color": "red", "font-weight": "normal"}
    styles2 = {"font-weight": "bold"}
    node = to_node(t"<p style={styles1} style={styles2}>Warning!</p>")
    assert node == Element(
        "p",
        attrs={"style": "color: red; font-weight: bold"},
        children=[Text("Warning!")],
    )
    assert str(node) == '<p style="color: red; font-weight: bold">Warning!</p>'


def test_style_attribute_str():
    styles = "color: red; font-weight: bold;"
    node = to_node(t"<p style={styles}>Warning!</p>")
    assert node == Element(
        "p",
        attrs={"style": "color: red; font-weight: bold"},
        children=[Text("Warning!")],
    )
    assert str(node) == '<p style="color: red; font-weight: bold">Warning!</p>'


def test_style_attribute_non_str_non_dict():
    with pytest.raises(TypeError):
        styles = [1, 2]
        _ = to_node(t"<p style={styles}>Warning!</p>")


def test_style_literal_attr_bypass():
    # Trigger overall attribute resolution with an unrelated interpolated attr.
    node = to_node(t'<p style="invalid;invalid:" id={"resolved"}></p>')
    assert node == Element(
        "p",
        attrs={"style": "invalid;invalid:", "id": "resolved"},
    ), "A single literal attribute should bypass style accumulator."


def test_style_none():
    styles = None
    node = to_node(t"<p style={styles}></p>")
    assert node == Element("p")


# --------------------------------------------------------------------------
# Function component interpolation tests
# --------------------------------------------------------------------------


def FunctionComponent(
    children: t.Iterable[Node], first: str, second: int, third_arg: str, **attrs: t.Any
) -> Template:
    # Ensure type correctness of props at runtime for testing purposes
    assert isinstance(first, str)
    assert isinstance(second, int)
    assert isinstance(third_arg, str)
    new_attrs = {
        "id": third_arg,
        "data": {"first": first, "second": second},
        **attrs,
    }
    return t"<div {new_attrs}>Component: {children}</div>"


def test_interpolated_template_component():
    node = to_node(
        t'<{FunctionComponent} first=1 second={99} third-arg="comp1" class="my-comp">Hello, Component!</{FunctionComponent}>'
    )
    assert node == Element(
        "div",
        attrs={
            "id": "comp1",
            "data-first": "1",
            "data-second": "99",
            "class": "my-comp",
        },
        children=[Text("Component: "), Text("Hello, Component!")],
    )
    assert (
        str(node)
        == '<div id="comp1" data-first="1" data-second="99" class="my-comp">Component: Hello, Component!</div>'
    )


def test_interpolated_template_component_no_children_provided():
    """Same test, but the caller didn't provide any children."""
    node = to_node(
        t'<{FunctionComponent} first=1 second={99} third-arg="comp1" class="my-comp" />'
    )
    assert node == Element(
        "div",
        attrs={
            "id": "comp1",
            "data-first": "1",
            "data-second": "99",
            "class": "my-comp",
        },
        children=[
            Text("Component: "),
        ],
    )
    assert (
        str(node)
        == '<div id="comp1" data-first="1" data-second="99" class="my-comp">Component: </div>'
    )


def test_invalid_component_invocation():
    with pytest.raises(TypeError):
        _ = to_node(t"<{FunctionComponent}>Missing props</{FunctionComponent}>")


def test_prep_component_kwargs_named():
    def InputElement(size=10, type="text"):
        pass

    callable_info = get_callable_info(InputElement)
    assert prep_component_kwargs(callable_info, {"size": 20}, system_kwargs={}) == {
        "size": 20
    }
    assert prep_component_kwargs(
        callable_info, {"type": "email"}, system_kwargs={}
    ) == {"type": "email"}
    assert prep_component_kwargs(callable_info, {}, system_kwargs={}) == {}


@pytest.mark.skip("Should we just ignore unused user-specified kwargs?")
def test_prep_component_kwargs_unused_kwargs():
    def InputElement(size=10, type="text"):
        pass

    callable_info = get_callable_info(InputElement)
    with pytest.raises(ValueError):
        assert (
            prep_component_kwargs(callable_info, {"type2": 15}, system_kwargs={}) == {}
        )


def FunctionComponentNoChildren(first: str, second: int, third_arg: str) -> Template:
    # Ensure type correctness of props at runtime for testing purposes
    assert isinstance(first, str)
    assert isinstance(second, int)
    assert isinstance(third_arg, str)
    new_attrs = {
        "id": third_arg,
        "data": {"first": first, "second": second},
    }
    return t"<div {new_attrs}>Component: ignore children</div>"


def test_interpolated_template_component_ignore_children():
    node = to_node(
        t'<{FunctionComponentNoChildren} first=1 second={99} third-arg="comp1">Hello, Component!</{FunctionComponentNoChildren}>'
    )
    assert node == Element(
        "div",
        attrs={
            "id": "comp1",
            "data-first": "1",
            "data-second": "99",
        },
        children=[Text(text="Component: ignore children")],
    )
    assert (
        str(node)
        == '<div id="comp1" data-first="1" data-second="99">Component: ignore children</div>'
    )


def FunctionComponentKeywordArgs(first: str, **attrs: t.Any) -> Template:
    # Ensure type correctness of props at runtime for testing purposes
    assert isinstance(first, str)
    assert "children" in attrs
    _ = attrs.pop("children")
    new_attrs = {"data-first": first, **attrs}
    return t"<div {new_attrs}>Component with kwargs</div>"


def test_children_always_passed_via_kwargs():
    node = to_node(
        t'<{FunctionComponentKeywordArgs} first="value" extra="info">Child content</{FunctionComponentKeywordArgs}>'
    )
    assert node == Element(
        "div",
        attrs={
            "data-first": "value",
            "extra": "info",
        },
        children=[Text("Component with kwargs")],
    )
    assert (
        str(node) == '<div data-first="value" extra="info">Component with kwargs</div>'
    )


def test_children_always_passed_via_kwargs_even_when_empty():
    node = to_node(t'<{FunctionComponentKeywordArgs} first="value" extra="info" />')
    assert node == Element(
        "div",
        attrs={
            "data-first": "value",
            "extra": "info",
        },
        children=[Text("Component with kwargs")],
    )
    assert (
        str(node) == '<div data-first="value" extra="info">Component with kwargs</div>'
    )


def ColumnsComponent() -> Template:
    return t"""<td>Column 1</td><td>Column 2</td>"""


def test_fragment_from_component():
    # This test assumes that if a component returns a template that parses
    # into multiple root elements, they are treated as a fragment.
    node = to_node(t"<table><tr><{ColumnsComponent} /></tr></table>")
    assert node == Element(
        "table",
        children=[
            Element(
                "tr",
                children=[
                    Element("td", children=[Text("Column 1")]),
                    Element("td", children=[Text("Column 2")]),
                ],
            ),
        ],
    )
    assert str(node) == "<table><tr><td>Column 1</td><td>Column 2</td></tr></table>"


def test_component_passed_as_attr_value():
    def Wrapper(
        children: t.Iterable[Node], sub_component: t.Callable, **attrs: t.Any
    ) -> Template:
        return t"<{sub_component} {attrs}>{children}</{sub_component}>"

    node = to_node(
        t'<{Wrapper} sub-component={FunctionComponent} class="wrapped" first=1 second={99} third-arg="comp1"><p>Inside wrapper</p></{Wrapper}>'
    )
    assert node == Element(
        "div",
        attrs={
            "id": "comp1",
            "data-first": "1",
            "data-second": "99",
            "class": "wrapped",
        },
        children=[Text("Component: "), Element("p", children=[Text("Inside wrapper")])],
    )
    assert (
        str(node)
        == '<div id="comp1" data-first="1" data-second="99" class="wrapped">Component: <p>Inside wrapper</p></div>'
    )


def test_nested_component_gh23():
    # See https://github.com/t-strings/tdom/issues/23 for context
    def Header():
        return to_node(t"{'Hello World'}")

    node = to_node(t"<{Header} />")
    assert node == Text("Hello World")
    assert str(node) == "Hello World"


def test_component_returning_iterable():
    def Items() -> t.Iterable:
        for i in range(2):
            yield t"<li>Item {i + 1}</li>"
        yield to_node(t"<li>Item {3}</li>")

    node = to_node(t"<ul><{Items} /></ul>")
    assert node == Element(
        "ul",
        children=[
            Element("li", children=[Text("Item "), Text("1")]),
            Element("li", children=[Text("Item "), Text("2")]),
            Element("li", children=[Text("Item "), Text("3")]),
        ],
    )
    assert str(node) == "<ul><li>Item 1</li><li>Item 2</li><li>Item 3</li></ul>"


def test_component_returning_fragment():
    def Items() -> Node:
        return to_node(t"<li>Item {1}</li><li>Item {2}</li><li>Item {3}</li>")

    node = to_node(t"<ul><{Items} /></ul>")
    assert node == Element(
        "ul",
        children=[
            Element("li", children=[Text("Item "), Text("1")]),
            Element("li", children=[Text("Item "), Text("2")]),
            Element("li", children=[Text("Item "), Text("3")]),
        ],
    )
    assert str(node) == "<ul><li>Item 1</li><li>Item 2</li><li>Item 3</li></ul>"


@dataclass
class ClassComponent:
    """Example class-based component."""

    user_name: str
    image_url: str
    homepage: str = "#"
    children: t.Iterable[Node] = field(default_factory=list)

    def __call__(self) -> Node:
        return to_node(
            t"<div class='avatar'>"
            t"<a href={self.homepage}>"
            t"<img src='{self.image_url}' alt='{f'Avatar of {self.user_name}'}' />"
            t"</a>"
            t"<span>{self.user_name}</span>"
            t"{self.children}"
            t"</div>",
        )


def test_class_component_implicit_invocation_with_children():
    node = to_node(
        t"<{ClassComponent} user-name='Alice' image-url='https://example.com/alice.png'>Fun times!</{ClassComponent}>"
    )
    assert node == Element(
        "div",
        attrs={"class": "avatar"},
        children=[
            Element(
                "a",
                attrs={"href": "#"},
                children=[
                    Element(
                        "img",
                        attrs={
                            "src": "https://example.com/alice.png",
                            "alt": "Avatar of Alice",
                        },
                    )
                ],
            ),
            Element("span", children=[Text("Alice")]),
            Text("Fun times!"),
        ],
    )
    assert (
        str(node)
        == '<div class="avatar"><a href="#"><img src="https://example.com/alice.png" alt="Avatar of Alice" /></a><span>Alice</span>Fun times!</div>'
    )


def test_class_component_direct_invocation():
    avatar = ClassComponent(
        user_name="Alice",
        image_url="https://example.com/alice.png",
        homepage="https://example.com/users/alice",
    )
    node = to_node(t"<{avatar} />")
    assert node == Element(
        "div",
        attrs={"class": "avatar"},
        children=[
            Element(
                "a",
                attrs={"href": "https://example.com/users/alice"},
                children=[
                    Element(
                        "img",
                        attrs={
                            "src": "https://example.com/alice.png",
                            "alt": "Avatar of Alice",
                        },
                    )
                ],
            ),
            Element("span", children=[Text("Alice")]),
        ],
    )
    assert (
        str(node)
        == '<div class="avatar"><a href="https://example.com/users/alice"><img src="https://example.com/alice.png" alt="Avatar of Alice" /></a><span>Alice</span></div>'
    )


@dataclass
class ClassComponentNoChildren:
    """Example class-based component that does not ask for children."""

    user_name: str
    image_url: str
    homepage: str = "#"

    def __call__(self) -> Node:
        return to_node(
            t"<div class='avatar'>"
            t"<a href={self.homepage}>"
            t"<img src='{self.image_url}' alt='{f'Avatar of {self.user_name}'}' />"
            t"</a>"
            t"<span>{self.user_name}</span>"
            t"ignore children"
            t"</div>",
        )


def test_class_component_implicit_invocation_ignore_children():
    node = to_node(
        t"<{ClassComponentNoChildren} user-name='Alice' image-url='https://example.com/alice.png'>Fun times!</{ClassComponentNoChildren}>"
    )
    assert node == Element(
        "div",
        attrs={"class": "avatar"},
        children=[
            Element(
                "a",
                attrs={"href": "#"},
                children=[
                    Element(
                        "img",
                        attrs={
                            "src": "https://example.com/alice.png",
                            "alt": "Avatar of Alice",
                        },
                    )
                ],
            ),
            Element("span", children=[Text("Alice")]),
            Text("ignore children"),
        ],
    )
    assert (
        str(node)
        == '<div class="avatar"><a href="#"><img src="https://example.com/alice.png" alt="Avatar of Alice" /></a><span>Alice</span>ignore children</div>'
    )


def AttributeTypeComponent(
    data_int: int,
    data_true: bool,
    data_false: bool,
    data_none: None,
    data_float: float,
    data_dt: datetime.datetime,
    **kws: dict[str, object | None],
) -> Template:
    """Component to test that we don't incorrectly convert attribute types."""
    assert isinstance(data_int, int)
    assert data_true is True
    assert data_false is False
    assert data_none is None
    assert isinstance(data_float, float)
    assert isinstance(data_dt, datetime.datetime)
    for kw, v_type in [
        ("spread_true", True),
        ("spread_false", False),
        ("spread_int", int),
        ("spread_none", None),
        ("spread_float", float),
        ("spread_dt", datetime.datetime),
        ("spread_dict", dict),
        ("spread_list", list),
    ]:
        if v_type in (True, False, None):
            assert kw in kws and kws[kw] is v_type, (
                f"{kw} should be {v_type} but got {kws=}"
            )
        else:
            assert kw in kws and isinstance(kws[kw], v_type), (
                f"{kw} should instance of {v_type} but got {kws=}"
            )
    return t"Looks good!"


def test_attribute_type_component():
    an_int: int = 42
    a_true: bool = True
    a_false: bool = False
    a_none: None = None
    a_float: float = 3.14
    a_dt: datetime.datetime = datetime.datetime(2024, 1, 1, 12, 0, 0)
    spread_attrs: dict[str, object | None] = {
        "spread_true": True,
        "spread_false": False,
        "spread_none": None,
        "spread_int": 0,
        "spread_float": 0.0,
        "spread_dt": datetime.datetime(2024, 1, 1, 12, 0, 1),
        "spread_dict": dict(),
        "spread_list": ["eggs", "milk"],
    }
    node = to_node(
        t"<{AttributeTypeComponent} data-int={an_int} data-true={a_true} "
        t"data-false={a_false} data-none={a_none} data-float={a_float} "
        t"data-dt={a_dt} {spread_attrs}/>"
    )
    assert node == Text("Looks good!")
    assert str(node) == "Looks good!"


def test_component_non_callable_fails():
    with pytest.raises(TypeError):
        _ = to_node(t"<{'not a function'} />")


def RequiresPositional(whoops: int, /) -> Template:  # pragma: no cover
    return t"<p>Positional arg: {whoops}</p>"


def test_component_requiring_positional_arg_fails():
    with pytest.raises(TypeError):
        _ = to_node(t"<{RequiresPositional} />")


def test_mismatched_component_closing_tag_fails():
    with pytest.raises(TypeError):
        _ = to_node(
            t"<{FunctionComponent} first=1 second={99} third-arg='comp1'>Hello</{ClassComponent}>"
        )
