"""
Port the code from viewdom.examples.expressions.
"""

import pytest

from tdom import html


@pytest.fixture(scope="module")
def fixture_name():
    return "Fixture Name"


def test_insert_variable():
    """Template is in a function, and `name` comes from that scope."""
    name = "World"
    result = html(t"<div>Hello {name}</div>")
    assert str(result) == "<div>Hello World</div>"


def test_from_import():
    """A symbol is imported from another module."""
    name = pytest.__name__
    result = html(t"<div>Hello {name}</div>")
    assert str(result) == "<div>Hello pytest</div>"


def test_from_function_arg(fixture_name):
    """A symbol is passed into a function."""
    result = html(t"<div>Hello {fixture_name}</div>")
    assert str(result) == "<div>Hello Fixture Name</div>"


def test_python_expression():
    """Use an expression which adds two numbers together."""
    result = html(t"<div>Hello {2+2}</div>")
    assert str(result) == "<div>Hello 4</div>"


def test_call_function():
    """Use an expression which calls a function."""

    def make_bigly(name: str) -> str:
        """A function returning a string, rather than a component."""
        return f"BIGLY: {name.upper()}"

    name = "World"
    result = html(t"<div>Hello {make_bigly(name)}</div>")
    assert str(result) == "<div>Hello BIGLY: WORLD</div>"
