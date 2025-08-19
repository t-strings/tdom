"""Ensure all the decorator policies work as advertised."""

import sys
from dataclasses import dataclass

import pytest
from venusian import Scanner

from conftest import Greeting
from tdom import html
from tdom.decorators import injectable
from svcs import Registry, Container


@pytest.fixture
def current_module():
    return sys.modules[__name__]


@injectable()
def FunctionHeader(container: Container, name: str):
    """Expect a container to be injected along with a prop from the usage."""
    greeting = container.get(Greeting)
    salutation = greeting.salutation
    return html(t"<span>{salutation}</span>: {name}")


def test_scan_test_function(container: Container):
    """Make sure Venusian looks in the current module."""

    result = html(t'<div><{FunctionHeader} name="World"/></div>', container=container)
    assert str(result) == "<div><span>Hello</span>: World</div>"


@injectable()
@dataclass
class ClassHeader:
    container: Container
    name: str

    def __call__(self) -> str:
        greeting = self.container.get(Greeting)
        salutation = greeting.salutation
        return html(t"<span>{salutation}</span>: {self.name}")


def test_scan_test_dataclass(scanner: Scanner, container: Container):
    """Make sure Venusian can make a class as well as a function."""

    result = html(t'<div><{ClassHeader} name="World"/></div>', container=container)
    assert str(result) == "<div><span>Hello</span>: World</div>"


@injectable()
@dataclass
class ClassFooter:
    container: Container
    name: str

    def __call__(self):
        return html(t"<footer>Bonjour</footer>: {self.name}")


# @injectable(for_=ClassFooter)
@dataclass
class FrenchClassFooter:
    container: Container
    name: str

    def __call__(self):
        return html(t"<footer>Bonjour</span>: {self.name}")


def test_override_registered_components(container: Container):
    """ClassFooter ships with "the system" but this site has a new one."""

    # This is where the "site" would have registered some overrides, for
    # example, in a Sphinx conf.py
    x = 1

    #
    # I keep getting a registry without the registrations in this module.
    # Need to make the current_module and scan explicit. Possibly look at
    # Hopscotch to see how to register stuff local to each test *function*.
    result = html(t"<div><{ClassFooter}/></div>", container=container)
    # assert str(result) == "<div><footer>Bonjour</footer>: World</div>"


# def test_import_construction(scanner: Scanner):
#     import_time = injectable(after=tuple())
#     assert import_time.__class__ is injectable
#     assert import_time.after == tuple()
#     import_time.venusian_callback(scanner, "ClassHeader", ClassHeader)
#     assert import_time.param_names == ["container", "name"]
#     wrapped = import_time(ClassHeader)
#     assert wrapped


# def test_inject_container(app_registry: Registry, this_container: Container):
#     result = html(t'<{Header1} name="World"/>', container=this_container)
#     assert "<div>HelloWorld</div>" == str(result)

# @injectable(after=[])
# def Header2(container: Container, name: str):
#     """The decorator has empty middleware for the component return value. """
#     greeting = container.get(Greeting)
#     return html(t"<div>{greeting.salutation} {name}</div>")
#
# def test_empty_after_middleware(app_registry: Registry, this_container: Container):
#     result = html(t'<{Header2} name="World"/>', container=this_container)
#     assert "<div>HelloWorld</div>" == str(result)
#
# def spanify1(node: Node) -> Node:
#     """Convert any divs to spans."""
#     x = 1
#     return node
#
#
# @injectable(after=(spanify1,))
# def Header3(container: Container, name: str):
#     """The decorator has after middleware for the component return value. """
#     greeting = container.get(Greeting)
#     return html(t"<div>{greeting.salutation} {name}</div>")
#
#
# def test_after_middleware(app_registry: Registry, this_container: Container):
#     result = html(t'<{Header3} name="World"/>', container=this_container)
#     assert "<div>HelloWorld</div>" == str(result)
#
