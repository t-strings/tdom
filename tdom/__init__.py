from markupsafe import Markup, escape

from .context import Context, Scope, ScopedTemplate, create_context, make_provider
from .processor import html, svg

# We consider `Markup` and `escape` to be part of this module's public API

__all__ = [
    "Context",
    "Markup",
    "Scope",
    "ScopedTemplate",
    "create_context",
    "escape",
    "html",
    "make_provider",
    "svg",
]
