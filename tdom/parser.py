import random
import string
import typing as t
from collections import OrderedDict
from html.parser import HTMLParser

from markupsafe import Markup

from .nodes import (
    CONTENT_ELEMENTS,
    VOID_ELEMENTS,
    Comment,
    DocumentType,
    Element,
    Fragment,
    Node,
    Text,
)

_FRAGMENT_TAG = f"t🐍f-{''.join(random.choices(string.ascii_lowercase, k=4))}-"


class NodeParser(HTMLParser):
    root: Fragment
    stack: list[Element]

    def __init__(self):
        super().__init__()
        self.root = Fragment(children=[])
        self.stack = []

    def handle_starttag(
        self, tag: str, attrs: t.Sequence[tuple[str, str | None]]
    ) -> None:
        node = Element(tag, attrs=LastUpdatedOrderedDict(attrs), children=[])
        if tag in VOID_ELEMENTS:
            self.append_element_child(node)
        else:
            self.stack.append(node)

    def handle_startendtag(
        self, tag: str, attrs: t.Sequence[tuple[str, str | None]]
    ) -> None:
        node = Element(tag, attrs=LastUpdatedOrderedDict(attrs), children=[])
        self.append_element_child(node)

    def handle_endtag(self, tag: str) -> None:
        if not self.stack:
            raise ValueError(f"Unexpected closing tag </{tag}> with no open element.")

        element = self.stack.pop()
        if element.tag != tag:
            raise ValueError(f"Mismatched closing tag </{tag}> for <{element.tag}>.")

        self.append_element_child(element)

    def handle_data(self, data: str) -> None:
        text = Text(Markup(data) if self.in_content_element() else data)
        self.append_child(text)

    def handle_comment(self, data: str) -> None:
        comment = Comment(data)
        self.append_child(comment)

    def handle_decl(self, decl: str) -> None:
        if decl.upper().startswith("DOCTYPE"):
            doctype_content = decl[7:].strip()
            doctype = DocumentType(doctype_content)
            self.append_child(doctype)
        # For simplicity, we ignore other declarations.
        pass

    def in_content_element(self) -> bool:
        """Return True if the current context is within a content element."""
        open_element = self.get_open_element()
        return open_element is not None and open_element.tag in CONTENT_ELEMENTS

    def get_parent(self) -> Fragment | Element:
        """Return the current parent node to which new children should be added."""
        return self.stack[-1] if self.stack else self.root

    def get_open_element(self) -> Element | None:
        """Return the currently open Element, if any."""
        return self.stack[-1] if self.stack else None

    def append_element_child(self, child: Element) -> None:
        parent = self.get_parent()
        node: Element | Fragment = child
        # Special case: if the element is a Fragment, convert it to a Fragment node.
        if child.tag == _FRAGMENT_TAG:
            assert not child.attrs, (
                "Fragment elements should never be able to have attributes."
            )
            node = Fragment(children=child.children)
        parent.children.append(node)

    def append_child(self, child: Fragment | Text | Comment | DocumentType) -> None:
        parent = self.get_parent()
        parent.children.append(child)

    def close(self) -> None:
        if self.stack:
            raise ValueError("Invalid HTML structure: unclosed tags remain.")
        super().close()

    def get_node(self) -> Node:
        """Get the Node tree parsed from the input HTML."""
        # CONSIDER: Should we invert things and offer streaming parsing?
        assert not self.stack, "Did you forget to call close()?"
        if len(self.root.children) > 1:
            # The parse structure results in multiple root elements, so we
            # return a Fragment to hold them all.
            return self.root
        elif len(self.root.children) == 1:
            # The parse structure results in a single root element, so we
            # return that element directly. This will be a non-Fragment Node.
            return self.root.children[0]
        else:
            # Special case: the parse structure is empty; we treat
            # this as an empty Text Node.
            return Text("")

    def feed(self, data: str) -> None:
        # Special case: handle custom fragment syntax <>...</>
        # by replacing it with a unique tag name that is unlikely
        # to appear in normal HTML.
        data = data.replace("<>", f"<{_FRAGMENT_TAG}>").replace(
            "</>", f"</{_FRAGMENT_TAG}>"
        )
        super().feed(data)


def parse_html(input: str | t.Iterable[str]) -> Node:
    """
    Parse a string, or sequence of HTML string chunks, into a Node tree.

    If a single string is provided, it is parsed as a whole. If an iterable
    of strings is provided, each string is fed to the parser in sequence.
    This is particularly useful if you want to keep specific text chunks
    separate in the resulting Node tree.
    """
    parser = NodeParser()
    iterable = [input] if isinstance(input, str) else input
    for chunk in iterable:
        parser.feed(chunk)
    parser.close()
    return parser.get_node()


class LastUpdatedOrderedDict(OrderedDict):
    """
    Store items in the order the keys were last added.
    This differs from a regular dict which uses "insertion order".

    @NOTE: This is directly from the python documentation
    """

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        self.move_to_end(key)
