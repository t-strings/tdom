"""Use an actual svcs container.

Switch from a simple dict as the container, to a svcs registry and container.
This shows some patterns along the way:

- Just a global registry, close to the basic example, with a dict interface

- A stateful decorator using venusian that has access to the global registry

- Make a svcs container for each "request" and use that instead

- Simplify this by having a pluggable app that manages the svcs part

- A decorator that configures middleware on all components

- A decorator that configures middleware just for its wrapped component

- Stateful middleware, such as a helmet-style per-request

- Lifecycle rendering, to generate a responsive image and update the node later

Note that none of this requires any changes to `tdom` beyond passing down
a container.
"""
import sys
from dataclasses import dataclass

import pytest
from svcs import Registry, Container
from venusian import Scanner

from tdom import html
from tdom.decorators import injectable

@dataclass
class URL:
    path: str


@pytest.fixture
def registry() -> Registry:
    _registry = Registry()
    _registry.register_factory(Greeting, Greeting)

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

@dataclass
class Greeting:
    salutation: str = "Hello"

@injectable
def Header(container: Container, name: str):
    greeting = container.get(Greeting)
    return html(t"<div>{greeting.salutation} {name}</div>")

def test_make_container(this_container: Container):
    """Mimic per-request processing."""

    # The outside system hands us one of these, perhaps from "request"

    # A view is passed this configured container and
    # returns a result
    result = html(t'<{Header} name="World"/>', container=this_container)
    assert "<div>Hello World</div>" == str(result)

