import re
import sys
from html import escape
from random import random
from string.templatelib import Template
from types import GeneratorType


# DOM: Start

_IS_MICRO_PYTHON = "MicroPython" in sys.version
if not _IS_MICRO_PYTHON:
    from inspect import signature  # noqa: F401


_prefix = "t🐍" + str(random())[2:5]
_data = f"<!--{_prefix}-->"


ELEMENT = 1
# ATTRIBUTE = 2
TEXT = 3
# CDATA = 4
# ENTITY_REFERENCE = 5
# ENTITY = 6
# PROCESSING_INSTRUCTION = 7
COMMENT = 8
# DOCUMENT = 9
DOCUMENT_TYPE = 10
FRAGMENT = 11
# NOTATION = 12


TEXT_ELEMENTS = (
    "plaintext",
    "script",
    "style",
    "textarea",
    "title",
    "xmp",
)


VOID_ELEMENTS = (
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "keygen",
    "link",
    "menuitem",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
)


class Node(dict):
    def __init__(self, **kwargs):
        super().__init__(type=self.type, **kwargs)
        self.parent = None

    def __getattr__(self, name):
        return self[name] if name in self else None


class Comment(Node):
    type = COMMENT

    def __init__(self, data):
        super().__init__(data=data)

    def __str__(self):
        return f"<!--{str(self['data'])}-->"


class DocumentType(Node):
    type = DOCUMENT_TYPE

    def __init__(self, data):
        super().__init__(data=data)

    def __str__(self):
        return f"<!{self['data']}>"


class Text(Node):
    type = TEXT

    def __init__(self, data):
        super().__init__(data=data)

    def __str__(self):
        data = self["data"]
        return data if isinstance(data, Unsafe) else escape(str(data))


class Element(Node):
    type = ELEMENT

    def __init__(self, name, xml=False):
        super().__init__(name=name, xml=xml, props={}, children=[])

    def __str__(self):
        xml = self["xml"]
        name = self["name"]
        html = f"<{name}"
        for key, value in self["props"].items():
            if value is not None:
                if isinstance(value, bool):
                    if value:
                        html += f' {key}=""' if xml else f" {key}"
                else:
                    html += f' {key}="{escape(str(value))}"'
        if len(self["children"]) > 0:
            html += ">"
            just_text = not xml and name.lower() in TEXT_ELEMENTS
            for child in self["children"]:
                html += child["data"] if just_text else str(child)
            html += f"</{name}>"
        elif xml:
            html += " />"
        else:
            html += ">"
            if name.lower() not in VOID_ELEMENTS:
                html += "</" + name + ">"
        return html


class Fragment(Node):
    type = FRAGMENT

    def __init__(self):
        super().__init__(children=[])

    def __str__(self):
        return "".join(str(child) for child in self["children"])


def _append(parent, node):
    parent["children"].append(node)
    node.parent = parent


def _appendChildren(parent, nodes, clone=False):
    children = parent["children"]
    for node in nodes:
        if clone:
            node = _clone(node)
        children.append(node)
        node.parent = parent


def _clone(node):
    node_type = node["type"]
    if node_type == FRAGMENT:
        fragment = Fragment()
        _appendChildren(fragment, node["children"], True)
        return fragment
    if node_type == ELEMENT:
        element = Element(node["name"], node["xml"])
        element["props"] = node["props"].copy()
        _appendChildren(element, node["children"], True)
        return element
    if node_type == TEXT:
        return Text(node["data"])
    if node_type == COMMENT:
        return Comment(node["data"])
    if node_type == DOCUMENT_TYPE:
        return DocumentType(node["data"])
    # We shouldn't get here
    raise ValueError(f"Unknown element type: {node_type}")


def _replaceWith(current, node):
    parent = current.parent
    children = parent["children"]
    children[children.index(current)] = node
    node.parent = parent
    current.parent = None


if _IS_MICRO_PYTHON:
    import re

    ATTRIBUTES = re.compile(r'([^\s=]+)(=(([\'"])[\s\S]*?\4|\S+))?')
    NAME_CHAR = re.compile(r"[^/>\s]")

    class Unsafe(str):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

    def _attributes(props, attrs):
        while match := ATTRIBUTES.match(attrs.strip()):
            key = match.group(1)
            equal = match.group(2)
            if equal:
                value = match.group(3)
                # somehow MicroPython doesn't support match.group(4) for quoted values
                if (
                    value
                    and value[0] == value[-1]
                    and (value[0] == '"' or value[0] == "'")
                ):
                    value = value[1:-1]
                props[key] = value
                i = attrs.index(equal) + len(equal)
            else:
                props[key] = True
                i = attrs.index(key) + len(key)

            attrs = attrs[i:]

    def _text(node, content, ts, te):
        if ts < te:
            data = content[ts:te]
            if data.strip():
                _append(node, Text(data))

    def parse(content, xml=False):
        node = Fragment()
        length = len(content)
        i = 0
        ts = 0
        te = 0
        while i < length:
            i += 1
            if content[i - 1] == "<":
                if content[i] == "/":
                    _text(node, content, ts, te)
                    ts = te = i = content.index(">", i + 1) + 1
                    node = node.parent
                    continue

                if content[i] == "!":
                    _text(node, content, ts, te)
                    if content[i + 1 : i + 3] == "--":
                        j = content.index("-->", i + 3)
                        data = content[i + 3 : j]
                        if not (data.startswith("#") and data.endswith("#")):
                            _append(node, Comment(data))
                        i = j + 3
                    else:
                        j = content.index(">", i + 1)
                        _append(node, DocumentType(content[i + 1 : j]))
                        i = j + 1
                    ts = te = i
                    continue

                j = i
                while j < length and NAME_CHAR.match(content[j]):
                    j += 1

                if i < j:
                    _text(node, content, ts, te)
                    name = content[i:j]
                    element = Element(name, xml)
                    _append(node, element)

                    not_void = not xml and name.lower() not in VOID_ELEMENTS
                    if not_void:
                        node = element

                    i = j
                    j = content.index(">", i)
                    closing = content[j - 1] == "/"
                    if closing:
                        j -= 1
                    if i < j:
                        _attributes(node["props"], content[i:j])
                    if closing:
                        j += 1
                        if not_void:
                            node = node.parent
                    ts = te = i = j + 1
                    continue

            te += 1

        _text(node, content, ts, te)
        return node

else:
    from html.parser import HTMLParser

    class Unsafe(str):
        def __new__(cls, value, *args, **kwargs):
            return super().__new__(cls, value)

    class DOMParser(HTMLParser):
        def __init__(self, xml=False):
            super().__init__()
            self.xml = xml
            self.node = Fragment()

        def handle_starttag(self, tag, attrs):
            element = Element(tag, self.xml)
            _append(self.node, element)

            if not self.xml and tag.lower() not in VOID_ELEMENTS:
                self.node = element

            props = element["props"]
            for name, value in attrs:
                props[name] = value

        def handle_endtag(self, tag):
            if not self.xml and tag.lower() not in VOID_ELEMENTS:
                parent = self.node.parent
                if parent:
                    self.node = parent

        def handle_data(self, data):
            # this is needed to handle sparse interpolations
            # within <style> or <script> tags where this parser
            # won't allow children nodes and it passes all as data
            text = data.split(_data)
            for i in range(len(text) - 1):
                # empty nodes are ignored
                if len(text[i].strip()) > 0:
                    _append(self.node, Text(text[i]))
                # the comment node though is needed to handle updates
                _append(self.node, Comment(_prefix))

            # same applies for the last node
            if len(text[-1].strip()) > 0:
                _append(self.node, Text(text[-1]))

        def handle_comment(self, data):
            if data == "/":
                self.handle_endtag(self.node["name"])
            elif not (data.startswith("#") and data.endswith("#")):
                _append(self.node, Comment(data))

        def handle_decl(self, data):
            _append(self.node, DocumentType(data))

        def unknown_decl(self, data):
            raise Exception(f"Unknown declaration: {data}")

    def parse(content, xml=False):
        parser = DOMParser(xml)
        parser.feed(content)
        return parser.node


def unsafe(value):
    return Unsafe(value)


# DOM: End

## Parser: Start

_elements_pattern = re.compile(
    "<(\x01|[a-zA-Z0-9]+[a-zA-Z0-9:._-]*)([^>]*?)(/?)>",
)

_attributes_pattern = re.compile(
    r'([^\s\\>\'"=]+)\s*=\s*([\'"]?)' + "\x01",
)

_holes_pattern = re.compile(
    "[\x01\x02]",
)


def _as_attribute(match):
    return f"\x02={match.group(2)}{match.group(1)}"


def _as_closing(name, xml, self_closing):
    if len(self_closing) > 0:
        if xml or name.lower() in VOID_ELEMENTS:
            return " /"
        else:
            return f"></{name}"
    return ""


# \x01 Node.ELEMENT_NODE
# \x02 Node.ATTRIBUTE_NODE


def _instrument(template, xml):
    def pin(match):
        name = match.group(1)
        if name == "\x01":
            name = _prefix
        attrs = match.group(2)
        self_closing = match.group(3)
        return f"<{name}{re.sub(_attributes_pattern, _as_attribute, attrs).rstrip()}{
            _as_closing(name, xml, self_closing)
        }>"

    def point():
        nonlocal i
        i += 1
        return _prefix + str(i - 1)

    i = 0
    return re.sub(
        _holes_pattern,
        lambda match: f"<!--{_prefix}-->" if match.group(0) == "\x01" else point(),
        re.sub(
            _elements_pattern, pin, "\x01".join(template).strip().replace("</>", "<//>")
        ),
    )


## Parser: End


def _as_comment(node):
    return lambda value: _replaceWith(node, _as_node(value))


def get_component_value(props, target, children, context, imp=_IS_MICRO_PYTHON):
    """Sniff out the args, call the target, return the value."""

    e1 = "required positional argument: 'children'"
    e2 = "function takes 1 positional arguments but 0 were given"

    # Make a copy of the props.
    _props = props.copy()

    if not imp:
        # We aren't in MicroPython so let's do the full sniffing
        params = signature(target).parameters
        if "children" in params:
            _props["children"] = children
        if "context" in params:
            _props["context"] = context
        result = target(**_props)
    else:
        # We're in MicroPython. Try without children, if it fails, try again with
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


def _as_component(node, components, context):
    def component(value):
        def reveal():
            result = get_component_value(node.props, value, node["children"], context)
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
    def __call__(self, node, updates, context=None):
        return _as_component(node, updates, context)


class _Update:
    def __init__(self, path, update):
        self.path = path
        self.value = update


def _parse(template, length, svg):
    updates = []
    content = _instrument(template, svg)
    fragment = parse(content, svg)

    if len(fragment["children"]) == 1:
        node = fragment["children"][0]
        if node["type"] != ELEMENT or node["name"] != _prefix:
            fragment = node

    _set_updates(fragment, updates, [])

    if len(updates) != length:
        raise ValueError(f"{len(updates)} updates found, expected {length}")

    return [fragment, updates]


# Entry point: Start (this was in __init__.py)

_parsed = {}
_listeners = []


def _util(svg):
    def fn(t, context: dict = None):
        if not isinstance(t, Template):
            raise ValueError("Argument is not a Template instance")

        strings = t.strings

        values = [entry.value for entry in t.interpolations]

        length = len(values)

        if strings not in _parsed:
            _parsed[strings] = _parse(strings, length, svg)

        content, updates = _parsed[strings]

        node = _clone(content)
        changes = []
        path = None
        child = None
        i = 0

        for update in updates:
            if path != update.path:
                path = update.path
                child = node
                for index in path:
                    child = child["children"][index]

            if isinstance(update.value, _Attribute):
                changes.append(update.value(child, _listeners))
            elif isinstance(update.value, _Comment):
                changes.append(update.value(child))
            else:
                changes.append(update.value(child, changes, context))

        for i in range(length):
            changes[i](values[i])

        for i in range(len(changes) - 1, length - 1, -1):
            changes[i]()

        return node

    return fn


def render(where, what):
    result = where(what() if callable(what) else what, _listeners)
    _listeners.clear()
    return result


html = _util(False)
svg = _util(True)
