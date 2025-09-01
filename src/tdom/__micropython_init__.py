"""Used by MicroPython to remap imports from tdom.py to micropython.py"""

from .micropython import (
    COMMENT,
    DOCUMENT_TYPE,
    ELEMENT,
    FRAGMENT,
    TEXT,
    Comment,
    DocumentType,
    Element,
    Fragment,
    Node,
    Text,
    html,
    parse,
    render,
    svg,
    unsafe,
)

__all__ = [
    "COMMENT",
    "Comment",
    "DOCUMENT_TYPE",
    "DocumentType",
    "ELEMENT",
    "Element",
    "FRAGMENT",
    "Fragment",
    "Node",
    "TEXT",
    "Text",
    "html",
    "parse",
    "render",
    "svg",
    "unsafe",
]
