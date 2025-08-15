# ----- APP: Mimic how an app like Sphinx or Flask would do
# both a global registry and a per-request container.

import sys
from dataclasses import dataclass

import pytest
from svcs import Container, Registry
from venusian import Scanner

pytest_plugins = ("tdom.fixtures",)


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
