"""
Port the code from viewdom.examples.static_string.
"""

import pytest

from tdom import html


def test_string_literal():
    """Simplest form of templating: just a string, no tags, no attributes"""
    result = html(t"Hello World")
    assert str(result) == "Hello World"


def test_simple_render():
    """Same thing, but in a `<div> with attributes`."""
    result = html(t'<div title="Greeting">Hello World</div>')
    assert str(result) == '<div title="Greeting">Hello World</div>'


def test_simple_interpolation():
    """Simplest rendering of a value in the scope."""
    name = "World"
    result = html(t"<div>Hello {name}</div>")
    assert str(result) == "<div>Hello World</div>"


def test_attribute_value_expression():
    """Pass in a Python symbol as part of the template, inside curly braces."""
    klass = "container1"
    result = html(t"<div class={klass}>Hello World</div>")
    assert str(result) == '<div class="container1">Hello World</div>'


def test_expressions_in_attribute_value():
    """Simple Python expression cannot be used inside an attribute value."""
    try:
        result = html(t'<div class="container{1}">Hello World</div>')
        raise Exception("Should not happen")
    except ValueError as e:
        assert str(e) == "0 updates found, expected 1"


def test_child_nodes():
    """Nested markup shows up as nodes."""
    result = html(t"<div>Hello <span>World<em>!</em></span></div>")
    assert str(result) == "<div>Hello <span>World<em>!</em></span></div>"


def test_doctype():
    """Sometimes it is hard to get a DOCTYPE in to the resulting output."""
    result = html(t"<!DOCTYPE html>\n<div>Hello World</div>")
    assert str(result) == "<!DOCTYPE html><div>Hello World</div>"


def test_reducing_boolean():
    """collapse truthy-y values into simplified HTML attributes."""
    result = html(t"<div editable={True}>Hello World</div>")
    assert str(result) == "<div editable>Hello World</div>"
