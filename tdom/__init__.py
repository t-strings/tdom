from markupsafe import Markup, escape

from .processor import html, svg

# We consider `Markup` and `escape` to be part of this module's public API

__all__ = [
    "Markup",
    "escape",
    "html",
    "svg",
]
