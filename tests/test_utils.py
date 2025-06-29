from typing import Sequence

from tdom.utils import get_component_value


def test_props_and_target_no_children():
    """Neither side has children."""
    def target():
        return 99
    props = {}
    children = []
    result = get_component_value(props, target, children)
    assert result == 99

def test_props_empty_target_children():
    """Props have empty children."""
    def target(children: Sequence):
        return len(children)
    props = {}
    _children = []
    result = get_component_value(props, target, _children)
    assert result == 0

def test_props_yes_target_yes():
    """Neither side has children."""
    def target(children: Sequence):
        return len(children)
    props = {}
    _children = [1, 2, 3]
    result = get_component_value(props, target, _children)
    assert result == 3


def test_micropython_no_children():
    def target():
        return 99
    props = {}
    _children = []
    imp = True  # Simulate running under MicroPython
    result = get_component_value(props, target, _children, imp=imp)
    assert result == 99


def test_micropython_with_children():
    def target(children: Sequence):
        return len(children)
    props = {}
    _children = [1, 2, 3]
    imp = True  # Simulate running under MicroPython
    result = get_component_value(props, target, _children, imp=imp)
    assert result == 3

