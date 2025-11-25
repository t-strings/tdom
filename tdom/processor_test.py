import datetime
import typing as t
from dataclasses import dataclass, field
from string.templatelib import Interpolation, Template

import pytest
from markupsafe import Markup

from .nodes import Element, Fragment, Node, Text, Comment, DocumentType
from .placeholders import _PLACEHOLDER_PREFIX, _PLACEHOLDER_SUFFIX
from .processor import html


# --------------------------------------------------------------------------
# Basic HTML parsing tests
# --------------------------------------------------------------------------


def test_parse_empty():
    node = html(t"")
    assert node == Fragment(children=[])
    assert str(node) == ""


def test_parse_text():
    node = html(t"Hello, world!")
    assert node == Text("Hello, world!")
    assert str(node) == "Hello, world!"


def test_parse_comment():
    node = html(t"<!--This is a comment-->")
    assert node == Comment("This is a comment")
    assert str(node) == "<!--This is a comment-->"


def test_parse_document_type():
    node = html(t"<!doctype html>")
    assert node == DocumentType("html")
    assert str(node) == "<!DOCTYPE html>"


def test_parse_void_element():
    node = html(t"<br>")
    assert node == Element("br")
    assert str(node) == "<br />"


def test_parse_void_element_self_closed():
    node = html(t"<br />")
    assert node == Element("br")
    assert str(node) == "<br />"


def test_parse_chain_of_void_elements():
    # Make sure our handling of CPython issue #69445 is reasonable.
    node = html(t"<br><hr><img src='image.png' /><br /><hr>")
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


def test_static_boolean_attr_retained():
    # Make sure a boolean attribute (bare attribute) is not omitted.
    node = html(t"<input disabled>")
    assert node == Element("input", {"disabled": None})
    assert str(node) == "<input disabled />"


def test_parse_element_with_text():
    node = html(t"<p>Hello, world!</p>")
    assert node == Element(
        "p",
        children=[
            Text("Hello, world!"),
        ],
    )
    assert str(node) == "<p>Hello, world!</p>"


def test_parse_element_with_attributes():
    node = html(t'<a href="https://example.com" target="_blank">Link</a>')
    assert node == Element(
        "a",
        attrs={"href": "https://example.com", "target": "_blank"},
        children=[
            Text("Link"),
        ],
    )
    assert str(node) == '<a href="https://example.com" target="_blank">Link</a>'


def test_parse_nested_elements():
    node = html(t"<div><p>Hello</p><p>World</p></div>")
    assert node == Element(
        "div",
        children=[
            Element("p", children=[Text("Hello")]),
            Element("p", children=[Text("World")]),
        ],
    )
    assert str(node) == "<div><p>Hello</p><p>World</p></div>"


def test_parse_entities_are_escaped():
    node = html(t"<p>&lt;/p&gt;</p>")
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
    node = html(t"<p>Hello, {name}!</p>")
    assert node == Element("p", children=[Text("Hello, "), Text("Alice"), Text("!")])
    assert str(node) == "<p>Hello, Alice!</p>"


def test_escaping_of_interpolated_text_content():
    name = "<Alice & Bob>"
    node = html(t"<p>Hello, {name}!</p>")
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
    node = html(t"<li>{c!s}</li><li>{c!r}</li><li>{'😊'!a}</li>")
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
    node = html(t"<style>{evil}{evil}</style>")
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
    node = html(t"<script>if (a < b && c > d) {{ alert('wow'); }}</script>")
    assert node == Element(
        "script",
        children=[Text("if (a < b && c > d) { alert('wow'); }")],
    )
    assert str(node) == ("<script>if (a < b && c > d) { alert('wow'); }</script>")


# --------------------------------------------------------------------------
# Interpolated non-text content
# --------------------------------------------------------------------------


def test_interpolated_false_content():
    node = html(t"<div>{False}</div>")
    assert node == Element("div", children=[])
    assert str(node) == "<div></div>"


def test_interpolated_none_content():
    node = html(t"<div>{None}</div>")
    assert node == Element("div", children=[])
    assert str(node) == "<div></div>"


def test_interpolated_zero_arg_function():
    def get_value():
        return "dynamic"

    node = html(t"<p>The value is {get_value}.</p>")
    assert node == Element(
        "p", children=[Text("The value is "), Text("dynamic"), Text(".")]
    )


def test_interpolated_multi_arg_function_fails():
    def add(a, b):  # pragma: no cover
        return a + b

    with pytest.raises(TypeError):
        _ = html(t"<p>The sum is {add}.</p>")


# --------------------------------------------------------------------------
# Raw HTML injection tests
# --------------------------------------------------------------------------


def test_raw_html_injection_with_markupsafe():
    raw_content = Markup("<strong>I am bold</strong>")
    node = html(t"<div>{raw_content}</div>")
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
    node = html(t"<p>Here is some {content}.</p>")
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
    node = html(t"<p>This is {raw_content:safe} text.</p>")
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
    node = html(t"<p>This is {supposedly_safe:unsafe} text.</p>")
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
    node = html(t"<div>{user_profile if is_logged_in else login_prompt}</div>")

    assert node == Element(
        "div", children=[Element("span", children=[Text("Welcome, User!")])]
    )
    assert str(node) == "<div><span>Welcome, User!</span></div>"

    is_logged_in = False
    node = html(t"<div>{user_profile if is_logged_in else login_prompt}</div>")
    assert str(node) == '<div><a href="/login">Please log in</a></div>'


def test_conditional_rendering_with_and():
    show_warning = True
    warning_message = t'<div class="warning">Warning!</div>'
    node = html(t"<main>{show_warning and warning_message}</main>")

    assert node == Element(
        "main",
        children=[
            Element("div", attrs={"class": "warning"}, children=[Text("Warning!")]),
        ],
    )
    assert str(node) == '<main><div class="warning">Warning!</div></main>'

    show_warning = False
    node = html(t"<main>{show_warning and warning_message}</main>")
    # Assuming False renders nothing
    assert str(node) == "<main></main>"


# --------------------------------------------------------------------------
# Interpolated nesting of templates and elements
# --------------------------------------------------------------------------


def test_interpolated_template_content():
    child = t"<span>Child</span>"
    node = html(t"<div>{child}</div>")
    assert node == Element("div", children=[html(child)])
    assert str(node) == "<div><span>Child</span></div>"


def test_interpolated_element_content():
    child = html(t"<span>Child</span>")
    node = html(t"<div>{child}</div>")
    assert node == Element("div", children=[child])
    assert str(node) == "<div><span>Child</span></div>"


def test_interpolated_nonstring_content():
    number = 42
    node = html(t"<p>The answer is {number}.</p>")
    assert node == Element(
        "p", children=[Text("The answer is "), Text("42"), Text(".")]
    )
    assert str(node) == "<p>The answer is 42.</p>"


def test_list_items():
    items = ["Apple", "Banana", "Cherry"]
    node = html(t"<ul>{[t'<li>{item}</li>' for item in items]}</ul>")
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
    node = html(t"<ul>{outer_items}</ul>")
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
# Interpolated attribute content
# --------------------------------------------------------------------------


def test_interpolated_attribute_value():
    url = "https://example.com/"
    node = html(t'<a href="{url}">Link</a>')
    assert node == Element(
        "a", attrs={"href": "https://example.com/"}, children=[Text("Link")]
    )
    assert str(node) == '<a href="https://example.com/">Link</a>'


def test_escaping_of_interpolated_attribute_value():
    url = 'https://example.com/?q="test"&lang=en'
    node = html(t'<a href="{url}">Link</a>')
    assert node == Element(
        "a",
        attrs={"href": 'https://example.com/?q="test"&lang=en'},
        children=[Text("Link")],
    )
    assert (
        str(node)
        == '<a href="https://example.com/?q=&#34;test&#34;&amp;lang=en">Link</a>'
    )


def test_interpolated_unquoted_attribute_value():
    id = "roquefort"
    node = html(t"<div id={id}>Cheese</div>")
    assert node == Element("div", attrs={"id": "roquefort"}, children=[Text("Cheese")])
    assert str(node) == '<div id="roquefort">Cheese</div>'


def test_interpolated_attribute_value_true():
    disabled = True
    node = html(t"<button disabled={disabled}>Click me</button>")
    assert node == Element(
        "button", attrs={"disabled": None}, children=[Text("Click me")]
    )
    assert str(node) == "<button disabled>Click me</button>"


def test_interpolated_attribute_value_falsy():
    disabled = False
    crumpled = None
    node = html(t"<button disabled={disabled} crumpled={crumpled}>Click me</button>")
    assert node == Element("button", attrs={}, children=[Text("Click me")])
    assert str(node) == "<button>Click me</button>"


def test_interpolated_attribute_spread_dict():
    attrs = {"href": "https://example.com/", "target": "_blank"}
    node = html(t"<a {attrs}>Link</a>")
    assert node == Element(
        "a",
        attrs={"href": "https://example.com/", "target": "_blank"},
        children=[Text("Link")],
    )
    assert str(node) == '<a href="https://example.com/" target="_blank">Link</a>'


def test_interpolated_mixed_attribute_values_and_spread_dict():
    attrs = {"href": "https://example.com/", "id": "link1"}
    target = "_blank"
    node = html(t'<a {attrs} target="{target}">Link</a>')
    assert node == Element(
        "a",
        attrs={"href": "https://example.com/", "id": "link1", "target": "_blank"},
        children=[Text("Link")],
    )
    assert (
        str(node)
        == '<a href="https://example.com/" id="link1" target="_blank">Link</a>'
    )


def test_multiple_attribute_spread_dicts():
    attrs1 = {"href": "https://example.com/", "id": "overwrtten"}
    attrs2 = {"target": "_blank", "id": "link1"}
    node = html(t"<a {attrs1} {attrs2}>Link</a>")
    assert node == Element(
        "a",
        attrs={"href": "https://example.com/", "id": "link1", "target": "_blank"},
        children=[Text("Link")],
    )
    assert (
        str(node)
        == '<a href="https://example.com/" target="_blank" id="link1">Link</a>'
    )


def test_interpolated_class_attribute():
    classes = ["btn", "btn-primary", False and "disabled", None, {"active": True}]
    node = html(t'<button class="{classes}">Click me</button>')
    assert node == Element(
        "button",
        attrs={"class": "btn btn-primary active"},
        children=[Text("Click me")],
    )
    assert str(node) == '<button class="btn btn-primary active">Click me</button>'


def test_interpolated_class_attribute_with_multiple_placeholders():
    classes1 = ["btn", "btn-primary"]
    classes2 = [False and "disabled", None, {"active": True}]
    node = html(t'<button class="{classes1} {classes2}">Click me</button>')
    # CONSIDER: Is this what we want? Currently, when we have multiple
    # placeholders in a single attribute, we treat it as a string attribute.
    assert node == Element(
        "button",
        attrs={"class": "['btn', 'btn-primary'] [False, None, {'active': True}]"},
        children=[Text("Click me")],
    )


def test_interpolated_attribute_spread_with_class_attribute():
    attrs = {"id": "button1", "class": ["btn", "btn-primary"]}
    node = html(t"<button {attrs}>Click me</button>")
    assert node == Element(
        "button",
        attrs={"id": "button1", "class": "btn btn-primary"},
        children=[Text("Click me")],
    )
    assert str(node) == '<button id="button1" class="btn btn-primary">Click me</button>'


def test_interpolated_attribute_value_embedded_placeholder():
    slug = "item42"
    node = html(t"<div data-id='prefix-{slug}'></div>")
    assert node == Element(
        "div",
        attrs={"data-id": "prefix-item42"},
        children=[],
    )
    assert str(node) == '<div data-id="prefix-item42"></div>'


def test_interpolated_attribute_value_with_static_prefix_and_suffix():
    counter = 3
    node = html(t'<div data-id="item-{counter}-suffix"></div>')
    assert node == Element(
        "div",
        attrs={"data-id": "item-3-suffix"},
        children=[],
    )
    assert str(node) == '<div data-id="item-3-suffix"></div>'


def test_attribute_value_empty_string():
    node = html(t'<div data-id=""></div>')
    assert node == Element(
        "div",
        attrs={"data-id": ""},
        children=[],
    )


def test_interpolated_attribute_value_multiple_placeholders():
    start = 1
    end = 5
    node = html(t'<div data-range="{start}-{end}"></div>')
    assert node == Element(
        "div",
        attrs={"data-range": "1-5"},
        children=[],
    )
    assert str(node) == '<div data-range="1-5"></div>'


def test_interpolated_attribute_value_tricky_multiple_placeholders():
    start = "start"
    end = "end"
    node = html(t'<div data-range="{start}5-and-{end}12"></div>')
    assert node == Element(
        "div",
        attrs={"data-range": "start5-and-end12"},
        children=[],
    )
    assert str(node) == '<div data-range="start5-and-end12"></div>'


def test_placeholder_collision_avoidance():
    # This test is to ensure that our placeholder detection avoids collisions
    # even with content that might look like a placeholder.
    tricky = "123"
    template = Template(
        '<div data-tricky="',
        _PLACEHOLDER_PREFIX,
        Interpolation(tricky, "tricky"),
        _PLACEHOLDER_SUFFIX,
        '"></div>',
    )
    node = html(template)
    assert node == Element(
        "div",
        attrs={"data-tricky": _PLACEHOLDER_PREFIX + tricky + _PLACEHOLDER_SUFFIX},
        children=[],
    )
    assert (
        str(node)
        == f'<div data-tricky="{_PLACEHOLDER_PREFIX}{tricky}{_PLACEHOLDER_SUFFIX}"></div>'
    )


def test_interpolated_attribute_value_multiple_placeholders_no_quotes():
    start = 1
    end = 5
    node = html(t"<div data-range={start}-{end}></div>")
    assert node == Element(
        "div",
        attrs={"data-range": "1-5"},
        children=[],
    )
    assert str(node) == '<div data-range="1-5"></div>'


def test_interpolated_data_attributes():
    data = {"user-id": 123, "role": "admin", "wild": True, "false": False, "none": None}
    node = html(t"<div data={data}>User Info</div>")
    assert node == Element(
        "div",
        attrs={"data-user-id": "123", "data-role": "admin", "data-wild": None},
        children=[Text("User Info")],
    )
    assert (
        str(node)
        == '<div data-user-id="123" data-role="admin" data-wild>User Info</div>'
    )


def test_data_attr_toggle_to_removed():
    for v in False, None:
        for node in [
            html(t"<div data-selected data={dict(selected=v)}></div>"),
            html(t'<div data-selected="on" data={dict(selected=v)}></div>'),
        ]:
            assert node == Element("div")
            assert str(node) == "<div></div>"


def test_data_attr_toggle_to_str():
    for node in [
        html(t"<div data-selected data={dict(selected='yes')}></div>"),
        html(t'<div data-selected="no" data={dict(selected="yes")}></div>'),
    ]:
        assert node == Element("div", {"data-selected": "yes"})
        assert str(node) == '<div data-selected="yes"></div>'


def test_data_attr_toggle_to_true():
    node = html(t'<div data-selected="yes" data={dict(selected=True)}></div>')
    assert node == Element("div", {"data-selected": None})
    assert str(node) == "<div data-selected></div>"


def test_data_attr_unrelated_unaffected():
    node = html(t"<div data-selected data={dict(active=True)}></div>")
    assert node == Element("div", {"data-selected": None, "data-active": None})
    assert str(node) == "<div data-selected data-active></div>"


def test_interpolated_data_attribute_multiple_placeholders():
    confusing = {"user-id": "user-123"}
    placeholders = {"role": "admin"}
    with pytest.raises(TypeError):
        _ = html(t'<div data="{confusing} {placeholders}">User Info</div>')


def test_interpolated_aria_attributes():
    aria = {"label": "Close", "hidden": True, "another": False, "more": None}
    node = html(t"<button aria={aria}>X</button>")
    assert node == Element(
        "button",
        attrs={"aria-label": "Close", "aria-hidden": "true", "aria-another": "false"},
        children=[Text("X")],
    )
    assert (
        str(node)
        == '<button aria-label="Close" aria-hidden="true" aria-another="false">X</button>'
    )


def test_interpolated_aria_attribute_multiple_placeholders():
    confusing = {"label": "Close"}
    placeholders = {"hidden": True}
    with pytest.raises(TypeError):
        _ = html(t'<button aria="{confusing} {placeholders}">X</button>')


def test_interpolated_style_attribute():
    styles = {"color": "red", "font-weight": "bold", "font-size": "16px"}
    node = html(t"<p style={styles}>Warning!</p>")
    assert node == Element(
        "p",
        attrs={"style": "color: red; font-weight: bold; font-size: 16px"},
        children=[Text("Warning!")],
    )
    assert (
        str(node)
        == '<p style="color: red; font-weight: bold; font-size: 16px">Warning!</p>'
    )


def test_clear_static_style():
    node = html(t'<p style="font-color: red" {dict(style=None)}></p>')
    assert node == Element("p")
    assert str(node) == "<p></p>"


def test_override_static_style_str_str():
    node = html(t'<p style="font-color: red" {dict(style="font-size: 15px")}></p>')
    assert node == Element("p", {"style": "font-size: 15px"})
    assert str(node) == '<p style="font-size: 15px"></p>'


def test_override_static_style_str_builder():
    node = html(t'<p style="font-color: red" {dict(style={"font-size": "15px"})}></p>')
    assert node == Element("p", {"style": "font-size: 15px"})
    assert str(node) == '<p style="font-size: 15px"></p>'


def test_interpolated_style_attribute_multiple_placeholders():
    styles1 = {"color": "red"}
    styles2 = {"font-weight": "bold"}
    node = html(t"<p style='{styles1} {styles2}'>Warning!</p>")
    # CONSIDER: Is this what we want? Currently, when we have multiple
    # placeholders in a single attribute, we treat it as a string attribute.
    assert node == Element(
        "p",
        attrs={"style": "{'color': 'red'} {'font-weight': 'bold'}"},
        children=[Text("Warning!")],
    )


def test_style_attribute_str():
    styles = "color: red; font-weight: bold;"
    node = html(t"<p style={styles}>Warning!</p>")
    assert node == Element(
        "p",
        attrs={"style": "color: red; font-weight: bold;"},
        children=[Text("Warning!")],
    )
    assert str(node) == '<p style="color: red; font-weight: bold;">Warning!</p>'


def test_style_attribute_non_str_non_dict():
    with pytest.raises(TypeError):
        styles = [1, 2]
        _ = html(t"<p style={styles}>Warning!</p>")


def test_special_attrs_as_static():
    node = html(t'<p aria="aria?" data="data?" class="class?" style="style?"></p>')
    assert node == Element(
        "p",
        attrs={"aria": "aria?", "data": "data?", "class": "class?", "style": "style?"},
    )


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
    node = html(
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
    node = html(
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
        _ = html(t"<{FunctionComponent}>Missing props</{FunctionComponent}>")


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
    node = html(
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
    node = html(
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
    node = html(t'<{FunctionComponentKeywordArgs} first="value" extra="info" />')
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
    node = html(t"<table><tr><{ColumnsComponent} /></tr></table>")
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

    node = html(
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
        return html(t"{'Hello World'}")

    node = html(t"<{Header} />")
    assert node == Text("Hello World")
    assert str(node) == "Hello World"


def test_component_returning_iterable():
    def Items() -> t.Iterable:
        for i in range(2):
            yield t"<li>Item {i + 1}</li>"
            # What should be happening here?
        yield html(t"<li>Item {3}</li>")

    node = html(t"<ul><{Items} /></ul>")
    assert node == Element(
        "ul",
        children=[
            Element("li", children=[Text("Item "), Text("1")]),
            Element("li", children=[Text("Item "), Text("2")]),
            Element("li", children=[Text("Item "), Text("3")]),
        ],
    )
    assert str(node) == "<ul><li>Item 1</li><li>Item 2</li><li>Item 3</li></ul>"


def test_component_returning_explicit_fragment():
    def Items() -> Node:
        return html(t"<><li>Item {1}</li><li>Item {2}</li><li>Item {3}</li></>")

    node = html(t"<ul><{Items} /></ul>")
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
        return html(
            t"<div class='avatar'>"
            t"<a href={self.homepage}>"
            t"<img src='{self.image_url}' alt='{f'Avatar of {self.user_name}'}' />"
            t"</a>"
            t"<span>{self.user_name}</span>"
            t"{self.children}"
            t"</div>",
        )


def test_class_component_implicit_invocation_with_children():
    node = html(
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
    node = html(t"<{avatar} />")
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
        return html(
            t"<div class='avatar'>"
            t"<a href={self.homepage}>"
            t"<img src='{self.image_url}' alt='{f'Avatar of {self.user_name}'}' />"
            t"</a>"
            t"<span>{self.user_name}</span>"
            t"ignore children"
            t"</div>",
        )


def test_class_component_implicit_invocation_ignore_children():
    node = html(
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
    node = html(
        t"<{AttributeTypeComponent} data-int={an_int} data-true={a_true} "
        t"data-false={a_false} data-none={a_none} data-float={a_float} "
        t"data-dt={a_dt} {spread_attrs}/>"
    )
    assert node == Text("Looks good!")
    assert str(node) == "Looks good!"


def test_component_non_callable_fails():
    with pytest.raises(TypeError):
        _ = html(t"<{'not a function'} />")


def RequiresPositional(whoops: int, /) -> Template:  # pragma: no cover
    return t"<p>Positional arg: {whoops}</p>"


def test_component_requiring_positional_arg_fails():
    with pytest.raises(TypeError):
        _ = html(t"<{RequiresPositional} />")


def test_replace_static_attr_str_str():
    node = html(t'<div title="default" {dict(title="fresh")}></div>')
    assert node == Element("div", {"title": "fresh"})
    assert str(node) == '<div title="fresh"></div>'


def test_replace_static_attr_str_true():
    node = html(t'<div title="default" {dict(title=True)}></div>')
    assert node == Element("div", {"title": None})
    assert str(node) == "<div title></div>"


def test_replace_static_attr_true_str():
    node = html(t"<div title {dict(title='fresh')}></div>")
    assert node == Element("div", {"title": "fresh"})
    assert str(node) == '<div title="fresh"></div>'


def test_remove_static_attr_str_none():
    node = html(t'<div title="default" {dict(title=None)}></div>')
    assert node == Element("div")
    assert str(node) == "<div></div>"


def test_remove_static_attr_true_none():
    node = html(t"<div title {dict(title=None)}></div>")
    assert node == Element("div")
    assert str(node) == "<div></div>"


def test_other_static_attr_intact():
    node = html(t'<img title="default" {dict(alt="fresh")}>')
    assert node == Element("img", {"title": "default", "alt": "fresh"})
    assert str(node) == '<img title="default" alt="fresh" />'
