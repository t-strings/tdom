"""
Scoped values for tdom components.

Pass data through a tree of components without threading it as a prop at
every level. If you've used React's Context or any of its many cousins,
you'll feel right at home.

Under the hood, this module builds on Python's `contextvars`, the
standard-library machinery that already handles the hard parts:
per-async-task isolation, save and restore, well-defined behavior under
concurrency. We just wrap it in three flavors:

- `make_provider(cv)`: low-level. You bring your own `ContextVar`; we
  hand you back a tdom component that scopes the variable's value to a
  children subtree.

- `Context(cv)`: mid-level. You bring your own `ContextVar`; we hand you
  back our `Context` abstraction; see below for details.

- `create_context(default=...)`: high-level. We create a fresh
  `ContextVar`, a matching Provider component, a `.get()` accessor, and
  a `.provide(value)` context manager, all bundled into a tidy
  `Context`. Most developers will want to use this!

Here's the high-level version in action:

    theme = create_context(default="auto")

    def Banner() -> Template:
        return t"<h1 class={theme.get()}>Hello!</h1>"

    def App() -> Template:
        return t'<{theme.Provider} value="dark"><{Banner}/></{theme.Provider}>'

Inside the Provider's subtree, `theme.get()` returns `"dark"`. Outside,
it returns whatever the surrounding scope had: the default, or
whatever another outer Provider set. Providers nest as you'd expect: the
innermost one wins inside its own children, and everything resets
cleanly on the way out (even if an exception is raised).

One important caveat: `create_context` must be called at module level,
never inside a function that runs repeatedly. This isn't a `tdom`
rule; it comes straight from `ContextVar` itself. The Python docs put
it this way:

    Important: Context Variables should be created at the top module
    level and never in closures. Context objects hold strong references
    to context variables which prevents context variables from being
    properly garbage collected.

In short: treat your contexts like any other module-level constant.
Create them once, at import time, and reuse them everywhere. After
all, contexts really *are* specialized global variables.
"""

import typing as t
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from string.templatelib import Template

__all__ = [
    "Context",
    "Scope",
    "ScopedTemplate",
    "create_context",
    "make_provider",
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
        token = self.cv.set(self.value)
        try:
            yield
        finally:
            self.cv.reset(token)


@dataclass(frozen=True, slots=True)
class ScopedTemplate:
    """
    A `Template` bundled with the `Scope` that should be active while it
    renders.

    Returned by context-provider components (see `make_provider`). The
    template processor recognizes this shape, activates the scope, walks
    the template, and resets when done.
    """

    template: Template
    scope: Scope


def make_provider[T](cv: ContextVar[T]) -> t.Callable[..., ScopedTemplate]:
    """
    Make a tdom component that scopes `cv` to its children subtree.

    The returned component is suitable for use as a tdom component:

        theme: ContextVar[str] = ContextVar("theme", default="auto")
        ThemeProvider = make_provider(theme)

        return t'<{ThemeProvider} value="dark"><{Banner}/></{ThemeProvider}>'

    Consumers inside the subtree see `value` via `theme.get()`.
    """

    def Provider(value: T, children: Template) -> ScopedTemplate:
        return ScopedTemplate(template=children, scope=Scope(cv=cv, value=value))

    Provider.__name__ = f"{cv.name}Provider"
    # Set this to make tracebacks/debugging nicer:
    Provider.__qualname__ = Provider.__name__
    return Provider


class Context[T]:
    """
    A `ContextVar` bundled with a tdom Provider component.

    Created by `create_context()`. Exposes:

      - `.get()`  -- read the current value (per-async/thread-context
        isolation, courtesy of the underlying `ContextVar`).
      - `.Provider`  -- a tdom component scoping the value to a subtree
        of a template (composable, in-template scoping).
      - `.provide(value)`  -- a context manager scoping the value to a
        `with` block (for imperative scoping at a render-call boundary
        -- route handlers, middleware, tests).

    Note: there's deliberately no `.set(value)` method. Contexts are
    *scoped* values, not mutable state -- use `Provider` or `provide()`
    instead. If you need raw set/reset/token semantics, build a
    `Context` directly from your own `ContextVar` and manipulate it
    however you like.
    """

    __slots__ = ("Provider", "_cv")

    def __init__(self, cv: ContextVar[T]) -> None:
        self._cv = cv
        self.Provider = make_provider(cv)

    def get(self) -> T:
        return self._cv.get()

    def provide(self, value: T) -> t.ContextManager[None]:
        """
        Scope `value` to a `with` block. For imperative scoping at the
        boundary between Python code and a render.

        The typical use case: imperative code (a route handler,
        middleware, a test) needs to bind a context value before
        calling `html()`:

            with current_user.provide(request.user):
                return html(t'<{Page}/>')
        """
        return Scope(cv=self._cv, value=value).activate()


def create_context[T](
    default: T,
    *,
    name: str = "tdom_context",
) -> Context[T]:
    """
    Create a tdom-aware Context with a fresh underlying `ContextVar`.

    Must be called at module level.

    Example use:

        theme = create_context(default="auto")

        def Banner() -> Template:
            return t"<h1 class={theme.get()}>...</h1>"

        def App() -> Template:
            return t'<{theme.Provider} value="dark"><{Banner} /></{theme.Provider}>'

    You can also use the returned `Context` directly, without embedding
    a `Provider` inovcation in your t-string:

        theme = create_context(default="auto")

        def Banner() -> Template:
            return t"<h1 class={theme.get()}>...</h1>"

        def App() -> Template:
            return t"<{Banner} />"

        with theme.provide("dark"):
            return html(t"<{App} />")
    """
    cv: ContextVar[T] = ContextVar(name, default=default)
    return Context(cv)
