"""Simple function component, nothing dynamic, that returns a VDOM."""
from tdom import html


def Heading(props, children):
    """The default heading."""
    return html(t"<h1>My Title</h1>")


def main():
    """Main entry point."""
    result = html(t"<{Heading} />")
    return result
