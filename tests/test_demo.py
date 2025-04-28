"""Cover the examples in Andrea's demo."""

from tdom import html, svg


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



def test_component():
    """Render a t-string that references a component."""

    def Component(a:str, b:int, children:list):
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
