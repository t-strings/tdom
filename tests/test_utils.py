from typing import Sequence

from tdom.tdom import (
    Element,
    Fragment,
    Text,
    _as_node,
    _serialize_attributes,
    get_component_value,
    unsafe,
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


def test_props_empty_target_children():
    """Props have empty children."""

    def target(children: Sequence):
        return len(children)

    props = {}
    _children = []
    context = {}
    result = get_component_value(props, target, _children, context)
    assert result == 0


def test_props_yes_target_yes():
    """Both sides provide/expect children."""

    def target(children: Sequence):
        return len(children)

    props = {}
    _children = [1, 2, 3]
    context = {}
    result = get_component_value(props, target, _children, context)
    assert result == 3


def test_micropython_no_children():
    def target():
        return 99

    props = {}
    _children = []
    context = {}
    imp = True  # Simulate running under MicroPython
    result = get_component_value(props, target, _children, context, imp=imp)
    assert result == 99


def test_micropython_with_children():
    def target(children: Sequence):
        return len(children)

    props = {}
    _children = [1, 2, 3]
    context = {}
    imp = True  # Simulate running under MicroPython
    result = get_component_value(props, target, _children, context, imp=imp)
    assert result == 3


def test_not_micropython_children_context_injection():
    """The target asks for both children and context."""

    def target(children, context):
        return children, context

    props = {}
    _children = [1, 2, 3]
    _context = {"name": "context"}
    result = get_component_value(props, target, _children, _context)
    assert result == (_children, _context)


def test_replace_target():
    """The target asks for both children and context."""

    def target(children, context):
        return children, context

    def replacement_target(children, context):
        return "replacement"

    props = {}
    _children = [1, 2, 3]
    _context = {"name": "context"}
    result = get_component_value(props, target, _children, _context)
    assert result == (_children, _context)


# Tests for _as_node


def test_as_node_with_existing_node():
    n = Text("hello")
    out = _as_node(n)
    assert out is n


def test_as_node_with_list_fragment():
    out = _as_node([Text("a"), Text("b")])
    assert isinstance(out, Fragment)
    assert [str(c) for c in out["children"]] == ["a", "b"]


def test_as_node_with_tuple_and_generator():
    def gen():
        yield Text("x")
        yield Text("y")

    t = (Text("a"), Text("b"))
    out_tuple = _as_node(t)
    assert isinstance(out_tuple, Fragment)
    assert [str(c) for c in out_tuple["children"]] == ["a", "b"]

    out_gen = _as_node(gen())
    assert isinstance(out_gen, Fragment)
    assert [str(c) for c in out_gen["children"]] == ["x", "y"]


def test_as_node_with_callable_and_primitive():
    def fn():
        return Text("ok")

    out_callable = _as_node(fn)
    assert isinstance(out_callable, Text)
    assert str(out_callable) == "ok"

    out_primitive = _as_node(123)
    assert isinstance(out_primitive, Text)
    assert str(out_primitive) == "123"


# Tests for attribute serialization helpers via Element stringification


def test_serialize_attributes_html_boolean_and_escaping():
    el = Element("div", xml=False)
    el["props"].update(
        {
            "hidden": True,  # boolean HTML should collapse
            "data": None,  # None should be omitted
            "ok": False,  # False should be omitted
            "title": 'A "+& test',  # must escape and be double-quoted
        }
    )
    s = str(el)
    assert s.startswith("<div ") and s.endswith('"></div>')
    assert " hidden" in s  # collapsed boolean
    assert ' title="A &quot;+&amp; test"' in s
    assert " data=" not in s
    assert " ok=" not in s


def test_serialize_attributes_html_unsafe_passthrough():
    el = Element("div", xml=False)
    el["props"]["data-html"] = unsafe("<span>")
    assert str(el) == '<div data-html="<span>"></div>'


def test_empty_element_rendering_html_vs_xml():
    # HTML void element has no closing slash
    hr = Element("hr", xml=False)
    assert str(hr) == "<hr>"
    # HTML non-void gets explicit closing tag
    p = Element("p", xml=False)
    assert str(p) == "<p></p>"
    # XML self-closing
    rect = Element("rect", xml=True)
    assert str(rect) == "<rect />"


# Sanity check that _serialize_attributes mirrors Element serialization for typical props


def test_serialize_attributes_function_direct():
    props = {"checked": True, "value": "a&b", "skip": None}
    attrs_html = _serialize_attributes(props, xml=False)
    attrs_xml = _serialize_attributes(props, xml=True)
    assert attrs_html.strip() == 'checked value="a&amp;b"'
    assert attrs_xml.strip() == 'checked="" value="a&amp;b"'
