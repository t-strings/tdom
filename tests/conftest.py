# ----- APP: Mimic how an app like Sphinx or Flask would do
# both a global registry and a per-request container.

from dataclasses import dataclass

import pytest

pytest_plugins = ("tdom.fixtures",)


@dataclass
class Greeting:
    salutation: str = "Hello"


@dataclass
class URL:
    path: str


@pytest.fixture
def registry():
    _registry = {}
    # _registry.register_factory(Greeting, Greeting)
    return _registry


# @pytest.fixture
# def container(registry: Registry, scanner: Scanner) -> Container:
#     """This runs on each request, gathering info from the outside."""
#     url = URL(path="/foo")
#     _container = Container(registry=registry)
#     _container.register_local_value(URL, url)
#
#     return _container
