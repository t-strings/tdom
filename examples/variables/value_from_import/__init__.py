"""Get a variable from an import."""

from tdom import html

name = "World"


def Hello():
    """A simple hello component."""
    return html(t"<div>Hello {name}</div>")


def main():
    """Main entry point."""
    result = Hello()
    return result
