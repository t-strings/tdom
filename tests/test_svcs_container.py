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

import sys
from dataclasses import dataclass

import pytest
from svcs import Container, Registry

from conftest import URL, Greeting


@pytest.fixture
def current_module():
    return sys.modules[__name__]


@dataclass
class Welcome:
    """A factory to say hello to a URL path."""

    container: Container

    def __call__(self) -> str:
        greeting = self.container.get(Greeting)
        url = self.container.get(URL)
        result = f"{greeting.salutation}, {url.path} !!"
        return result


def test_get_welcome(registry: Registry, container: Container) -> None:
    registry.register_factory(Welcome, Welcome)
    _welcome = container.get(Welcome)
    result = _welcome()
    assert result == "Hello, /foo !!"


def test_override_greeting(registry: Registry, container: Container) -> None:
    """This site has a different Greeting."""

    @dataclass
    class FrenchGreeting(Greeting):
        salutation: str = "Bonjour"

    # Supply a different implementation of Greeting
    registry.register_factory(Greeting, FrenchGreeting)

    # Now get the welcome
    registry.register_factory(Welcome, Welcome)
    _welcome = container.get(Welcome)
    result = _welcome()
    assert result == "Bonjour, /foo !!"
