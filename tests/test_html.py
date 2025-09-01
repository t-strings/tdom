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


def test_boolean_true():
    """Collapse boolean attributes for true."""
    is_hidden = True
    result = html(t"<div hidden={is_hidden} />")
    assert str(result) == "<div hidden></div>"


def test_boolean_false():
    """Collapse boolean attributes for false and remove the attribute."""
    is_hidden = False
    result = html(t"<div hidden={is_hidden} />")
    assert str(result) == "<div></div>"


def test_fstring_attribute_value():
    """Allow an interpolation to have an f-string attribute value."""
    name = "World"
    result = html(t"<div class={f'Hello {name}'}></div>")
    assert str(result) == '<div class="Hello World"></div>'


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


def test_function_component():
    """Render a t-string that references a component defined as a function."""

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


def test_class_component():
    """Render a t-string that references a component as a class."""

    from dataclasses import dataclass

    @dataclass
    class Component:
        a: str
        b: int
        children: list

        def __call__(self):
            return html(
                t"""
                    <div a={self.a} b={self.b}>
                        {self.children}
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


def test_data_spread():
    """Ask for kwargs and allow special spread syntax."""

    def MyComponent(**kwargs):
        return html(t"<div data={kwargs}></div>")

    result = html(t"""
      <{MyComponent} a="1" b={2}>
        <p>first element {"child"}</p>
        <p c={3}>second element child</p>
      </>
    """)
    assert '<div data-a="1" data-b="2"></div>' == str(result)
