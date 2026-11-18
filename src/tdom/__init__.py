from markupsafe import Markup, escape

from .processor import html, svg
from .scope import Scope, ScopedTemplate

# We consider `Markup` and `escape` to be part of this module's public API

__all__ = [
    "Markup",
    "Scope",
    "ScopedTemplate",
    "escape",
    "html",
    "svg",
]
