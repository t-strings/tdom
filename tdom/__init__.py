from markupsafe import Markup, escape

from .nodes import Comment, DocumentType, Element, Fragment, Node, Text, to_node
from .processor import to_html

# @BWC: Temporary shim.
html = to_node

# We consider `Markup` and `escape` to be part of this module's public API

__all__ = [
    "Comment",
    "DocumentType",
    "Element",
    "escape",
    "Fragment",
    "to_html",
    "to_node",
    "html",
    "Markup",
    "Node",
    "Text",
]
