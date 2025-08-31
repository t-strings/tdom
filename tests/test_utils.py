from typing import Sequence

from tdom.utils import get_component_value


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
    """Neither side has children."""

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
