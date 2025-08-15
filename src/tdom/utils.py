from types import GeneratorType
from .parser import _instrument, _prefix
from .dom import Fragment, Node, Text
from .dom import COMMENT, ELEMENT, FRAGMENT
from .dom import _IS_MICRO_PYTHON, _appendChildren, _replaceWith, parse as domify

if not _IS_MICRO_PYTHON:
    from inspect import signature


def _as_comment(node):
    return lambda value: _replaceWith(node, _as_node(value))


def get_component_value(props, target, children, container, imp=_IS_MICRO_PYTHON):
    """Sniff out the args, call the target, return the value."""

    e1 = "required positional argument: 'children'"
    e2 = "function takes 1 positional arguments but 0 were given"

    # Make a copy of the props. We might not need it, but it is a simpler flow.
    _props = props.copy()

    if not imp:
        # The normal flow
        params = signature(target).parameters
        if "children" in params:
            _props["children"] = children
        if "container" in params:
            _props["container"] = container
        result = target(**_props)
    else:
        # Try without children, if it fails, try again with
        try:
            result = target(**props)
        except TypeError as e:
            # MicroPython seems to have different behavior for positional
            # and keyword parameters, so try both. We keep the CPython
            # approach so we can test from CPython.
            if e1 in str(e) or e2 in str(e):
                _props["children"] = children
                result = target(**_props)
            else:
                raise e
    return result


def _as_component(node, components, container):
    def component(value):
        def reveal():
            result = get_component_value(node.props, value, node["children"], container)
            _replaceWith(node, _as_node(result))

        components.append(reveal)

    return component


def _as_node(value):
    if isinstance(value, Node):
        return value
    if isinstance(value, (list, tuple, GeneratorType)):
        node = Fragment()
        _appendChildren(node, value)
        return node
    if callable(value):
        # TODO: this could be a hook pleace for asyncio
        #       and run to completion before continuing
        return _as_node(value())
    return Text(value)


def _as_prop(node, name, listeners):
    props = node["props"]

    def aria(value):
        for k, v in value.items():
            lower = k.lower()
            props[lower if lower == "role" else f"aria-{lower}"] = v

    def attribute(value):
        props[name] = value

    def dataset(value):
        for k, v in value.items():
            props[f"data-{k.replace('_', '-')}"] = v

    def listener(value):
        if value in listeners:
            i = listeners.index(value)
        else:
            i = len(listeners)
            listeners.append(value)

        props[name] = f"self.python_listeners?.[{i}](event)"

    def style(value):
        if isinstance(value, dict):
            props["style"] = ";".join([f"{k}:{v}" for k, v in value.items()])
        else:
            props["style"] = value

    if name[0] == "@":
        name = "on" + name[1:].lower()
        return listener
    if name == "style":
        return style
    if name == "aria":
        return aria
    # TODO: find which other node has a `data` attribute
    elif name == "data" and node["name"].lower() != "object":
        return dataset
    else:
        return attribute


def _set_updates(node, updates, path):
    type = node["type"]
    if type == ELEMENT:
        if node["name"] == _prefix:
            updates.append(_Update(path, _Component()))

        remove = []
        props = node["props"]
        for key, name in props.items():
            if key.startswith(_prefix):
                remove.append(key)
                updates.append(_Update(path, _Attribute(name)))

        for key in remove:
            del props[key]

    if type == ELEMENT or type == FRAGMENT:
        i = 0
        for child in node["children"]:
            _set_updates(child, updates, path + [i])
            i += 1

    elif type == COMMENT and node["data"] == _prefix:
        updates.append(_Update(path, _Comment()))


class _Attribute:
    def __init__(self, name):
        self.name = name

    def __call__(self, node, listeners):
        return _as_prop(node, self.name, listeners)


class _Comment:
    def __call__(self, node):
        return _as_comment(node)


class _Component:
    def __call__(self, node, updates, container=None):
        return _as_component(node, updates, container)


class _Update:
    def __init__(self, path, update):
        self.path = path
        self.value = update


def _parse(template, length, svg):
    updates = []
    content = _instrument(template, svg)
    fragment = domify(content, svg)

    if len(fragment["children"]) == 1:
        node = fragment["children"][0]
        if node["type"] != ELEMENT or node["name"] != _prefix:
            fragment = node

    _set_updates(fragment, updates, [])

    if len(updates) != length:
        raise ValueError(f"{len(updates)} updates found, expected {length}")

    return [fragment, updates]
