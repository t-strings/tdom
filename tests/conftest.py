# ----- APP: Mimic how an app like Sphinx or Flask would do
# both a global registry and a per-request container.

import sys
from dataclasses import dataclass

import pytest
from svcs import Container, Registry
from venusian import Scanner

pytest_plugins = ("tdom.fixtures",)


@dataclass
class Greeting:
    salutation: str = "Hello"


@dataclass
class URL:
    path: str


@pytest.fixture
def registry() -> Registry:
    _registry = Registry()
    _registry.register_factory(Greeting, Greeting)
    return _registry


@pytest.fixture
def scanner(registry: Registry) -> Scanner:
    _scanner = Scanner(registry=registry)
    current_module = sys.modules[__name__]
    _scanner.scan(current_module)
    return _scanner


@pytest.fixture
def container(registry: Registry, scanner: Scanner) -> Container:
    """This runs on each request, gathering info from the outside."""
    url = URL(path="/foo")
    _container = Container(registry=registry)
    _container.register_local_value(URL, url)

    return _container
