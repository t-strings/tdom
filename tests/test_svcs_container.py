"""Use an actual svcs container.

Switch from a simple dict as the container, to a global svcs registry
and a per-request container. This shows some patterns along the way:

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
from dataclasses import dataclass

import pytest
from svcs import Container, Registry

from tdom import html
from tdom.decorators import injectable

@dataclass
class Greeting:
    """A factory registered with this app at startup time."""
    salutation: str = "Hello"


@injectable
def Header1(container: Container, name: str):
    """Expect a container to be injected along with a prop from the usage."""
    greeting = container.get(Greeting)
    return html(t"<div>{greeting.salutation} {name}</div>")

@pytest.fixture
def app_registry(registry: Registry) -> None:
    """This app registers some factories at startup."""
    registry.register_factory(Greeting, Greeting)

def test_inject_container(app_registry: Registry, this_container: Container):
    result = html(t'<{Header1} name="World"/>', container=this_container)
    assert "<div>HelloWorld</div>" == str(result)

