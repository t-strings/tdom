from markupsafe import Markup, escape

from .nodes import Comment, DocumentType, Element, Fragment, Node, Text
from .processor import html

# We consider `Markup` and `escape` to be part of this module's public API

__all__ = [
    "Comment",
    "DocumentType",
    "Element",
    "escape",
    "Fragment",
    "html",
    "Markup",
    "Node",
    "Text",
]
