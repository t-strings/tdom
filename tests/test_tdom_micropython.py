from typing import Sequence

from tdom.micropython import (
    get_component_value,
)


def test_micropython_no_children():
    def target():
        return 99

    props = {}
    _children = []
    context = {}
    result = get_component_value(props, target, _children, context)
    assert result == 99


def test_micropython_with_children():
    def target(children: Sequence):
        return len(children)

    props = {}
    _children = [1, 2, 3]
    context = {}
    result = get_component_value(props, target, _children, context)
    assert result == 3
