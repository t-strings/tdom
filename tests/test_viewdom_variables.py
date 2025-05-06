"""
Port the code from viewdom.examples.variables.
"""

import pytest

from tdom import html


@pytest.fixture(scope="module")
def fixture_name():
    return "Fixture Name"

def no_fixture_name():
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


def test_from_function_arg(fixture_name=no_fixture_name):
    """A symbol is passed into a function."""
    result = html(t"<div>Hello {fixture_name}</div>")
    assert str(result) == "<div>Hello Fixture Name</div>"
