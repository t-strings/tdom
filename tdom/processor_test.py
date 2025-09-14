import typing as t
from string.templatelib import Template

import pytest
from markupsafe import Markup

from .nodes import Element, Fragment, Node, Text
from .processor import ComponentCallable, html

# --------------------------------------------------------------------------
# Basic HTML parsing tests
# --------------------------------------------------------------------------


def test_parse_empty():
    node = html(t"")
    assert node == Text("")
    assert str(node) == ""


def test_parse_text():
    node = html(t"Hello, world!")
    assert node == Text("Hello, world!")
    assert str(node) == "Hello, world!"


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
            Text(supposedly_safe),
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
        attrs={"href": Markup('https://example.com/?q="test"&lang=en')},
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
        == '<a href="https://example.com/" id="link1" target="_blank">Link</a>'
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


def test_interpolated_attribute_spread_with_class_attribute():
    attrs = {"id": "button1", "class": ["btn", "btn-primary"]}
    node = html(t"<button {attrs}>Click me</button>")
    assert node == Element(
        "button",
        attrs={"id": "button1", "class": "btn btn-primary"},
        children=[Text("Click me")],
    )
    assert str(node) == '<button id="button1" class="btn btn-primary">Click me</button>'


def test_interpolated_data_attributes():
    data = {"user-id": 123, "role": "admin"}
    node = html(t"<div data={data}>User Info</div>")
    assert node == Element(
        "div",
        attrs={"data-user-id": "123", "data-role": "admin"},
        children=[Text("User Info")],
    )
    assert str(node) == '<div data-user-id="123" data-role="admin">User Info</div>'


def test_interpolated_aria_attributes():
    aria = {"label": "Close", "hidden": True}
    node = html(t"<button aria={aria}>X</button>")
    assert node == Element(
        "button",
        attrs={"aria-label": "Close", "aria-hidden": "true"},
        children=[Text("X")],
    )
    assert str(node) == '<button aria-label="Close" aria-hidden="true">X</button>'


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


# --------------------------------------------------------------------------
# Function component interpolation tests
# --------------------------------------------------------------------------


def TemplateComponent(
    *children: Node, first: str, second: int, third_arg: str, **attrs: t.Any
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
        t'<{TemplateComponent} first=1 second={99} third-arg="comp1" class="my-comp">Hello, Component!</{TemplateComponent}>'
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


def test_invalid_component_invocation():
    with pytest.raises(TypeError):
        _ = html(t"<{TemplateComponent}>Missing props</{TemplateComponent}>")  # type: ignore


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
        *children: Node, sub_component: ComponentCallable, **attrs: t.Any
    ) -> Template:
        return t"<{sub_component} {attrs}>{children}</{sub_component}>"

    node = html(
        t'<{Wrapper} sub-component={TemplateComponent} class="wrapped" first=1 second={99} third-arg="comp1"><p>Inside wrapper</p></{Wrapper}>'
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
