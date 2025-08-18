"""Ensure all the decorator policies work as advertised."""

from dataclasses import dataclass

from conftest import Greeting
from tdom import html
from tdom.decorators import injectable
from svcs import Registry, Container


@injectable()
def Header01(container: Container, name: str):
    """Expect a container to be injected along with a prop from the usage."""
    greeting = container.get(Greeting)
    salutation = greeting.salutation
    return html(t"<span>{salutation}</span>: {name}")


def test_scan_test_function(container: Container):
    """Make sure Venusian looks in the current module."""

    result = html(t'<div><{Header01} name="World"/></div>', container=container)
    assert str(result) == "<div><span>Hello</span>: World</div>"


@injectable()
@dataclass
class Header02:
    container: Container
    name: str

    def __call__(self) -> str:
        greeting = self.container.get(Greeting)
        salutation = greeting.salutation
        return html(t"<span>{salutation}</span>: {self.name}")


def test_scan_test_dataclass(container: Container):
    """Make sure Venusian can make a class as well as a function."""

    result = html(t'<div><{Header02} name="World"/></div>', container=container)
    assert str(result) == "<div><span>Hello</span>: World</div>"


def test_override_registered_components(registry: Registry, container: Container):
    """Header02 ships with "the system" but this site has a new one."""

    @dataclass
    class FrenchHeader02:
        container: Container
        name: str

        def __call__(self):
            return html(t"<span>Bonjour</span>: {self.name}")

    # This is where the "site" would have registered some overrides, for
    # example, in a Sphinx conf.py
    registry.register_factory(Header02, FrenchHeader02)

    result = html(t'<div><{Header02} name="World"/></div>', container=container)
    assert str(result) == "<div><span>Bonjour</span>: World</div>"


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
