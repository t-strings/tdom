from markupsafe import Markup, escape

from .nodes.nodes import Comment, DocumentType, Element, Fragment, Node, Text
from .nodes.processor import to_node
from .processor import to_html


html = to_html


# We consider `Markup` and `escape` to be part of this module's public API

__all__ = [
    "Comment",
    "DocumentType",
    "Element",
    "escape",
    "Fragment",
    "html",
    "to_node",
    "to_html",
    "html",
    "Markup",
    "Node",
    "Text",
]
