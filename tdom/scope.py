"""
Scope and ScopedTemplate provide a low-level mechanism for tdom components
to offer context-like functionality, allowing values to flow into nested
children without requiring prop drilling.

Under the hood, we build on top of Python's contextvars, because they are
async context and thread safe: valuable for integrations with just about
any web framework out there.

Example use:

from typing import Literal
from contextvars import ContextVar

type Theme = Literal["auto", "light", "dark"]
theme: ContextVar[Theme] = ContextVar("theme", default="auto")


def ThemeProvider(children: Template, value: Theme) -> ScopedTemplate:
    retrun ScopedTemplate(children, Scope(theme, value))
"""

import typing as t
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from string.templatelib import Template

__all__ = [
    "Scope",
    "ScopedTemplate",
]


@dataclass(frozen=True, slots=True)
class Scope[T]:
    """
    A binding of a `ContextVar` to a value, activatable as a context manager.
    """

    cv: ContextVar[T]
    value: T

    @contextmanager
    def activate(self) -> t.Generator[None]:
        """Set `cv` to `value` for the duration of the block, then reset."""
        with self.cv.set(self.value):
            yield


@dataclass(frozen=True, slots=True)
class ScopedTemplate:
    """
    A `Template` bundled with the `Scope` that should be active while it
    renders.

    `tdom` components can return this type in place of a regular `Template`
    to ensure that nested content has access to the appropriate values.
    """

    scope: Scope
    template: Template
