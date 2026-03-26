from markupsafe import Markup, escape

from .nodes.nodes import Comment, DocumentType, Element, Fragment, Node, Text
from .nodes.processor import to_node
from .processor import to_html, to_svg

html = to_html
svg = to_svg


# We consider `Markup` and `escape` to be part of this module's public API

__all__ = [
    "Comment",
    "DocumentType",
    "Element",
    "Fragment",
    "Markup",
    "Node",
    "Text",
    "escape",
    "html",
    "html",
    "html",
    "svg",
    "to_html",
    "to_node",
]
