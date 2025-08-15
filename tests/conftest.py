# ----- APP: Mimic how an app like Sphinx or Flask would do
# both a global registry and a per-request container.

import sys
from dataclasses import dataclass

import pytest
from svcs import Registry, Container
from venusian import Scanner


@dataclass
class URL:
    path: str


@pytest.fixture
def registry() -> Registry:
    _registry = Registry()
    return _registry


@pytest.fixture
def this_container(registry: Registry) -> Container:
    """This runs on each request, gathering info from the outside."""
    url = URL(path="/foo")
    _container = Container(registry=registry)
    _container.register_local_value(URL, url)

    # Now make a Venusian scanner and do a scan, registering the
    # container with the decorators.
    s = Scanner(container=_container)
    current_module = sys.modules[__name__]
    s.scan(current_module)

    return _container


@pytest.fixture
def assert_no_console_errors(page):
    """If Chromium/Playwright has a console error, throw a pytest failure."""
    errors = []

    def on_console(msg):
        # ConsoleMessage methods: type(), text(), location(), args(), etc.
        # We only collect console messages of type "error"
        if msg.type() == "error":
            errors.append(("console", msg.text(), msg.location()))

    def on_page_error(exc):
        # JS exceptions surfaced via "pageerror"
        errors.append(("pageerror", str(exc), None))

    page.on("console", on_console)
    page.on("pageerror", on_page_error)
    try:
        yield
    finally:
        page.remove_listener("console", on_console)
        page.remove_listener("pageerror", on_page_error)
        if errors:
            formatted = []
            for kind, text, loc in errors:
                loc_str = ""
                if loc and isinstance(loc, dict):
                    file = loc.get("url") or loc.get("source", "")
                    line = loc.get("lineNumber")
                    col = loc.get("columnNumber")
                    loc_str = f" at {file}:{line}:{col}"
                formatted.append(f"[{kind}] {text}{loc_str}")
            import pytest as _pytest

            _pytest.fail("Console errors detected:\n" + "\n".join(formatted))
