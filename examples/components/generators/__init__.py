"""Generators as components."""

from tdom import html


def Todos(props, children):
    """A sequence of li items."""
    for todo in ["First", "Second"]:  # noqa B007
        # TODO Andrea need to add generator support
        yield html(t"<li>{todo}</li>")


def main():
    """Main entry point."""
    result = html(t"<ul><{Todos}/></ul>")
    return result
