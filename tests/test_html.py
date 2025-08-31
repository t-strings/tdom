"""Test some of the HTML processing features."""

from tdom import html, svg, unsafe


def test_automatic_quotes():
    """Automatic quotes with safe escapes."""
    result = html(t"""<p class={'test & "test"'}>Hello</p>""")
    assert str(result) == '<p class="test &amp; &quot;test&quot;">Hello</p>'


def test_sanitized_content():
    """Sanitized content out of the box"""
    from random import random

    result = html(t"Some random number: {random()}")
    # QUESTION: Not sure what to test here
    assert str(result).startswith("Some random number")


def test_self_closing_tags():
    """Sanitized content out of the box"""
    value = "Hello"
    result = html(t"<textarea placeholder={value} />")
    assert str(result) == '<textarea placeholder="Hello"></textarea>'


def test_special_attributes():
    """Data and ARIA"""
    data = {"a": 1, "b": 2}
    aria = {"role": "button", "label": "Click me"}
    result = html(t"<div data={data} aria={aria} />")
    assert (
        str(result)
        == '<div data-a="1" data-b="2" role="button" aria-label="Click me"></div>'
    )


def test_click_handler():
    """Bind a Python function to an element event handler."""

    def on_click(event):
        import js

        js.alert(event.type)

    result = html(t"<div @click={on_click} />")
    assert str(result) == '<div onclick="self.python_listeners?.[0](event)"></div>'


def test_ignore_voided():
    """Voided elements."""
    result = html(t"<hr />")
    assert str(result) == "<hr>"


def test_void_siblings():
    """Voided elements' siblings."""
    result = html(t"<p /><hr><p />")
    assert str(result) == "<p></p><hr><p></p>"


def test_dev_comments():
    """Developer comments."""
    result = html(t"<!--#1--><!--#2#--><!--##--><!--3#-->")
    assert str(result) == "<!--#1--><!--3#-->"


def test_svg():
    """preseved XML/SVG self closing nature."""
    result = html(
        t"""
    <svg>
      {svg(t'<rect width="200" height="100" rx="20" ry="20" fill="blue" />')}
    </svg>
    """
    )
    assert str(result) == (
        '<svg><rect width="200" height="100" rx="20" ry="20" fill="blue" /></svg>'
    )


def test_style():
    """Style attribute."""
    style = {"color": "red", "font-size": "12px"}
    result = html(t"<div style={style} />")
    assert str(result) == '<div style="color:red;font-size:12px"></div>'


def test_unsafe():
    """Unsafe strings."""
    # First, a usage without wrapping in unsafe
    span = "<span>Hello World</span>"
    result1 = html(t"<div>{span}</div>")
    assert str(result1) == "<div>&lt;span&gt;Hello World&lt;/span&gt;</div>"

    # Now wrap it in unsafe and it isn't escaped
    result2 = html(t"<div>{unsafe(span)}</div>")
    assert str(result2) == "<div><span>Hello World</span></div>"


def test_component():
    """Render a t-string that references a component."""

    def Component(a: str, b: int, children: list):
        return html(
            t"""
                <div a={a} b={b}>
                    {children}
                </div>
            """
        )

    result = html(
        t"""
            <{Component} a="1" b={2}>
                <p>Hello Components!</p>
            <//>
        """
    )

    assert "<p>Hello Components!</p>" in str(result)


def test_component_without_children():
    """Render a t-string that references a component."""

    def Component(a: str, b: int):
        return html(
            t"""
                <div a={a} b={b} />
            """
        )

    result = html(
        t"""
            <{Component} a="1" b={2} />
        """
    )

    assert '<div a="1" b="2"></div>' in str(result)


def test_lists_within_layout():
    """A template in a template."""

    names = ["John", "Jane", "Jill"]
    result = html(
        t"""
            <ul>
                {[html(t"<li>{name}</li>") for name in names]}
            </ul>
        """
    )

    assert "<li>John</li>" in str(result)
    assert "<li>Jane</li>" in str(result)
    assert "<li>Jill</li>" in str(result)


def test_no_context():
    """Default behavior when no context is provided."""
    result = html(t"Hello World")
    assert "Hello World" == str(result)


def test_empty_context():
    """Default behavior when no context is provided but None."""
    request_context = {}
    result = html(t"Hello World", context=request_context)
    assert "Hello World" == str(result)


def test_component_no_context():
    """A component that does not ask for a context."""

    def Header():
        return html(t"Hello World")

    result = html(t"<{Header}/>")
    assert "Hello World" == str(result)


def test_component_not_ask_context():
    """A component does not ask for a context."""

    def Header():
        return html(t"Hello World")

    request_context = {}
    result = html(t"<{Header}/>", context=request_context)
    assert "Hello World" == str(result)


def test_component_asks_context():
    """A component asks for a context."""

    def Header(context):
        label = context["label"]
        return html(t"Hello {label}")

    request_context = {"label": "World"}
    result = html(t"<{Header}/>", context=request_context)
    assert "Hello World" == str(result)
