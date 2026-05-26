"""Tests for `tdom.context` -- Provider components and `create_context`.

Each test runs in a fresh `contextvars.Context` (via the `@isolated`
decorator) so `.set()` calls in one test cannot leak into another.
"""

import functools
from contextvars import ContextVar, copy_context
from dataclasses import dataclass
from string.templatelib import Template

from . import html
from .scope import Scope, ScopedTemplate


def isolated(fn):
    """Run the test in a fresh contextvars.Context."""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        return copy_context().run(fn, *args, **kwargs)

    return wrapper


theme: ContextVar[str] = ContextVar("theme", default="auto")


@isolated
def test_scope_activate():
    scope = Scope(theme, "dark")
    assert theme.get() == "auto"
    with scope.activate():
        assert theme.get() == "dark"


@isolated
def test_scoped_template_from_component_is_activated():
    def SubComponent() -> Template:
        return t'<h1 data-sub-theme="{theme.get()}">test</h1>'

    def Component() -> ScopedTemplate:
        return ScopedTemplate(
            Scope(theme, "dank"),
            t'<div data-theme="{theme.get()}"><{SubComponent} /></div>',
        )

    result = html(t"<{Component} />")
    assert 'data-theme="auto"' in result
    assert 'data-sub-theme="dank"' in result


@isolated
def test_provider_style_component():
    def ThemeProvider(children: Template, value: str) -> ScopedTemplate:
        return ScopedTemplate(Scope(theme, value), children)

    def SubComponent() -> Template:
        return t'<h1 data-sub-theme="{theme.get()}">test</h1>'

    def Component() -> Template:
        return t'''
            <div data-theme="{theme.get()}">
                <{ThemeProvider} value="musty">
                    <{SubComponent} />
                </{ThemeProvider}>
            </div>
        '''

    result = html(t"<{Component} />")
    assert 'data-theme="auto"' in result
    assert 'data-sub-theme="musty"' in result


@isolated
def test_scoped_template_from_factory_component_is_activated():
    @dataclass
    class SubComponent:
        def __call__(self) -> Template:
            return t'<h1 data-sub-theme="{theme.get()}">test</h1>'

    @dataclass
    class Component:
        def __call__(self) -> ScopedTemplate:
            return ScopedTemplate(
                Scope(theme, "stuffy"),
                t'<div data-theme="{theme.get()}"><{SubComponent} /></div>',
            )

    result = html(t"<{Component} />")
    assert 'data-theme="auto"' in result
    assert 'data-sub-theme="stuffy"' in result
