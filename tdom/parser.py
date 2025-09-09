import typing as t
from html.parser import HTMLParser

from .nodes import VOID_ELEMENTS, Comment, DocumentType, Element, Fragment, Node, Text


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
        element = Element(tag, attrs=dict(attrs), children=[])
        self.stack.append(element)

        # Unfortunately, Python's built-in HTMLParser has inconsistent behavior
        # with void elements. In particular, it calls handle_endtag() for them
        # only if they explicitly self-close (e.g., <br />). But in the HTML
        # spec itself, *there is no distinction* between <br> and <br />.
        # So we need to handle this case ourselves.
        #
        # See https://github.com/python/cpython/issues/69445
        if tag in VOID_ELEMENTS:
            # Always call handle_endtag for void elements. If it happens
            # to be self-closed in the input, handle_endtag() will effectively
            # be called twice. We ignore the second call there.
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        if tag in VOID_ELEMENTS:
            # Special case: handle Python issue #69445 (see comment above).
            most_recent_closed = self.get_most_recent_closed_element()
            if most_recent_closed and most_recent_closed.tag == tag:
                # Ignore this call; we've already closed it.
                return
            open_element = self.get_open_element()
            if open_element and open_element.tag == tag:
                _ = self.stack.pop()
                self.append_child(open_element)
                return

        if not self.stack:
            raise ValueError(f"Unexpected closing tag </{tag}> with no open element.")

        element = self.stack.pop()
        if element.tag != tag:
            raise ValueError(f"Mismatched closing tag </{tag}> for <{element.tag}>.")

        self.append_child(element)

    def handle_data(self, data: str) -> None:
        text = Text(data)
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

    def get_parent(self) -> Fragment | Element:
        """Return the current parent node to which new children should be added."""
        return self.stack[-1] if self.stack else self.root

    def get_open_element(self) -> Element | None:
        """Return the currently open Element, if any."""
        return self.stack[-1] if self.stack else None

    def get_most_recent_closed_element(self) -> Element | None:
        """Return the most recently closed Element, if any."""
        parent = self.get_parent()
        if parent.children and isinstance(parent.children[-1], Element):
            return parent.children[-1]
        return None

    def append_child(self, child: Node) -> None:
        parent = self.get_parent()
        # We *know* our parser is using lists for children, so this cast is safe.
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
