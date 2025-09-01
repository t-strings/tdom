"""Ensure tests still work when imported from tdom.py."""

from tdom.tdom import (
    get_component_value,
    html,
)

# Tests for get_component_value


def test_props_and_target_no_children():
    """Neither side has children."""

    def target():
        return 99

    props = {}
    children = []
    context = {}
    result = get_component_value(props, target, children, context)
    assert result == 99


def test_style():
    """Style attribute."""
    style = {"color": "red", "font-size": "12px"}
    result = html(t"<div style={style} />")
    assert str(result) == '<div style="color:red;font-size:12px"></div>'
