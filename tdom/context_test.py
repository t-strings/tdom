"""Tests for `tdom.context` -- Provider components and `create_context`.

Each test runs in a fresh `contextvars.Context` (via the `@isolated`
decorator) so `.set()` calls in one test cannot leak into another.
"""

import functools
from contextvars import ContextVar, copy_context
from dataclasses import dataclass
from string.templatelib import Template

import pytest

from . import html
from .context import Context, Scope, ScopedTemplate, create_context, make_provider


def isolated(fn):
    """Run the test in a fresh contextvars.Context."""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        return copy_context().run(fn, *args, **kwargs)

    return wrapper


# Used by the lower-level `make_provider` tests below.
theme: ContextVar[str] = ContextVar("test_theme", default="auto")


# Used by the higher-level `create_context` tests.
ui_lang: Context[str] = create_context(default="en", name="test_ui_lang")


# Context wrapping a raw ContextVar -- the "escape hatch"
# for developers that want raw set/reset semantics on the underlying cv.
raw_lang_cv: ContextVar[str] = ContextVar("test_raw_lang", default="en")
raw_lang: Context[str] = Context(raw_lang_cv)


# ---------------------------------------------------------------------------
# make_provider: low-level wrapping of an existing ContextVar
# ---------------------------------------------------------------------------


@isolated
def test_provider_scopes_to_subtree():
    ThemeProvider = make_provider(theme)

    def Banner() -> Template:
        return t"<span class={theme.get()}>x</span>"

    body = html(t'<{ThemeProvider} value="dark"><{Banner}/></{ThemeProvider}>')
    assert 'class="dark"' in body


@isolated
def test_provider_resets_after_subtree():
    """After the Provider's children are rendered, the ContextVar is restored."""
    ThemeProvider = make_provider(theme)

    def Banner() -> Template:
        return t"<span class={theme.get()}>x</span>"

    html(t'<{ThemeProvider} value="dark"><{Banner}/></{ThemeProvider}>')
    assert theme.get() == "auto"


@isolated
def test_provider_nests():
    """Innermost Provider wins inside its children; outer wins outside."""
    ThemeProvider = make_provider(theme)

    def Show() -> Template:
        return t"<span class={theme.get()}>x</span>"

    body = html(
        t'<{ThemeProvider} value="dark">'
        t'<{ThemeProvider} value="light">'
        t"<{Show}/>"
        t"</{ThemeProvider}>"
        t"</{ThemeProvider}>"
    )
    assert 'class="light"' in body


@isolated
def test_provider_resets_on_exception_in_children():
    ThemeProvider = make_provider(theme)

    def Boom() -> Template:
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        html(t'<{ThemeProvider} value="dark"><{Boom}/></{ThemeProvider}>')

    assert theme.get() == "auto"


@isolated
def test_provider_does_not_leak_to_siblings():
    ThemeProvider = make_provider(theme)

    def Show() -> Template:
        return t"<span class={theme.get()}>x</span>"

    body = html(t"""
        <{ThemeProvider} value="dark"><{Show}/></{ThemeProvider}>
        <{ThemeProvider} value="light"><{Show}/></{ThemeProvider}>
    """)
    assert body.count('class="dark"') == 1
    assert body.count('class="light"') == 1


@isolated
def test_provider_children_stay_as_templates():
    """
    Inside the children walk the ContextVar is set, but children are still
    Templates (not pre-rendered strings) -- the processor walks them in
    the same depth-first pass.
    """
    ThemeProvider = make_provider(theme)

    seen_via_get: list[str] = []

    def Probe(label: str) -> Template:
        seen_via_get.append(theme.get())
        return t"<span data-label={label}>x</span>"

    html(t"""
        <{ThemeProvider} value="dark">
            <{Probe} label="a"/>
            <{Probe} label="b"/>
        </{ThemeProvider}>
    """)

    assert seen_via_get == ["dark", "dark"]


def test_provider_isolated_across_async_contexts():
    """`.set` inside a Provider stays inside its async/thread context."""
    ThemeProvider = make_provider(theme)

    def in_a():
        html(t'<{ThemeProvider} value="dark"><{_noop}/></{ThemeProvider}>')
        return theme.get()

    def in_b():
        return theme.get()

    assert copy_context().run(in_a) == "auto"  # reset after Provider closes
    assert copy_context().run(in_b) == "auto"


def _noop() -> Template:
    return t""


# ---------------------------------------------------------------------------
# create_context: high-level helper bundling ContextVar + Provider
# ---------------------------------------------------------------------------


@isolated
def test_create_context_default():
    assert ui_lang.get() == "en"


@isolated
def test_create_context_provider_scopes_to_subtree():
    def Greet() -> Template:
        return t"<p data-lang={ui_lang.get()}>x</p>"

    body = html(t'<{ui_lang.Provider} value="fr"><{Greet}/></{ui_lang.Provider}>')
    assert 'data-lang="fr"' in body
    # Outside the Provider, value is the default.
    assert ui_lang.get() == "en"


@isolated
def test_create_context_provider_overrides_bare_set():
    """A Provider wins over a raw bare-`set()` on the underlying cv."""

    def Greet() -> Template:
        return t"<p data-lang={raw_lang.get()}>x</p>"

    raw_lang_cv.set("de")
    body = html(t'<{raw_lang.Provider} value="fr"><{Greet}/></{raw_lang.Provider}>')
    assert 'data-lang="fr"' in body
    # The bare-set value is back outside the Provider.
    assert raw_lang.get() == "de"


# ---------------------------------------------------------------------------
# Context.provide: imperative counterpart to .Provider
# ---------------------------------------------------------------------------


@isolated
def test_provide_scopes_to_with_block():
    with ui_lang.provide("fr"):
        assert ui_lang.get() == "fr"
    assert ui_lang.get() == "en"


@isolated
def test_provide_restores_after_block():
    raw_lang_cv.set("de")
    with raw_lang.provide("fr"):
        assert raw_lang.get() == "fr"
    assert raw_lang.get() == "de"


@isolated
def test_provide_restores_on_exception():
    with pytest.raises(RuntimeError, match="boom"), ui_lang.provide("fr"):
        assert ui_lang.get() == "fr"
        raise RuntimeError("boom")
    assert ui_lang.get() == "en"


@isolated
def test_provide_nests():
    with ui_lang.provide("fr"):
        with ui_lang.provide("ja"):
            assert ui_lang.get() == "ja"
        assert ui_lang.get() == "fr"
    assert ui_lang.get() == "en"


@isolated
def test_provide_composes_with_provider_component():
    """`provide()` and `Provider` share the same underlying ContextVar."""

    def Greet() -> Template:
        return t"<p data-lang={ui_lang.get()}>x</p>"

    with ui_lang.provide("fr"):
        # Inside the `with`, the Provider can still override locally...
        body = html(t'<{ui_lang.Provider} value="ja"><{Greet}/></{ui_lang.Provider}>')
        assert 'data-lang="ja"' in body
        # ...and the `with`-scoped value is restored after the template.
        assert ui_lang.get() == "fr"
    assert ui_lang.get() == "en"


# ---------------------------------------------------------------------------
# Provider return shape: ScopedTemplate wrapping a Scope
# ---------------------------------------------------------------------------


def test_provider_returns_scoped_template():
    """`make_provider` produces a component that returns a ScopedTemplate."""
    ThemeProvider = make_provider(theme)
    result = ThemeProvider(value="dark", children=t"")
    assert isinstance(result, ScopedTemplate)
    assert isinstance(result.scope, Scope)
    assert result.scope.cv is theme
    assert result.scope.value == "dark"


# ---------------------------------------------------------------------------
# Factory-style providers: dataclass components returning ScopedTemplate
# ---------------------------------------------------------------------------


@isolated
def test_factory_component_returning_scoped_template_directly():
    """A factory component whose `__call__` returns a `ScopedTemplate` directly."""

    @dataclass
    class ThemeProvider:
        children: Template
        value: str

        def __call__(self) -> ScopedTemplate:
            return ScopedTemplate(
                template=self.children,
                scope=Scope(cv=theme, value=self.value),
            )

    def Banner() -> Template:
        return t"<span class={theme.get()}>x</span>"

    body = html(t'<{ThemeProvider} value="dark"><{Banner}/></{ThemeProvider}>')
    assert 'class="dark"' in body
    # Scope resets after the subtree, same as the function-style provider.
    assert theme.get() == "auto"
