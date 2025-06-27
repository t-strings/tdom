"""Use a global registry.

You can get some of the benefits of a container without changes
to tdom. Specifically, without passing in a container to html().
Instead, we'll make a svcs.Registry instance and use venusian
to "attach" it as a (globally) stateful decorator.

The downside: it is the same single container for the entire
lifetime of the application. This doesn't help per-request
types of applications.
"""

import sys
from dataclasses import dataclass
from inspect import signature

import pytest
from svcs import Registry, Container
from venusian import Scanner, attach

from tdom import html


@dataclass
class Greeting:
    salutation: str = "Hello"

def injectable(wrapped):
    _scanner: Scanner | None = None
    param_names = [param.name for param in signature(wrapped).parameters.values()]

    def _inject(*args, **kwargs):
        """Wrap the callable with a factory that can supply container."""
        if _scanner is None:
            return wrapped(*args, **kwargs)
        # Let's inject container if it is asked for
        _kwargs = kwargs.copy()
        if "container" in param_names:
            container = getattr(_scanner, "container")
            _kwargs["container"] = container
        return wrapped(*args, **_kwargs)

    def callback(scanner, name, ob):
        """This is called by venusian at scan time."""
        nonlocal _scanner
        _scanner = scanner

    attach(_inject, callback)
    return _inject

@pytest.fixture
def container() -> Container:
    r = Registry()
    r.register_factory(Greeting, Greeting)
    c = Container(registry=r)
    return c

@pytest.fixture
def scanner(container):
    """Make a Venusian scanner that scans callables only in the test module."""
    s = Scanner(container=container)
    current_module = sys.modules[__name__]
    s.scan(current_module)
    return s

@injectable
def Header(name, container: Container):
    greeting = container.get(Greeting)
    salutation = greeting.salutation
    return html(t"<h1>{salutation} {name}</h1>")

def test_scan_test_function(scanner):
    """Make sure Venusian looks in the current module."""

    result = html(t'<div><{Header} name="World"/></div>')
    # TODO Why was the space between Hello and World lost?
    assert str(result) == "<div><h1>HelloWorld</h1></div>"
