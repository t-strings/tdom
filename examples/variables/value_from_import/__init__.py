"""Get a variable from an import."""

from .. import name  # noqa F401
from tdom import html


def Hello():
    """A simple hello component."""
    return html(t"<div>Hello {name}</div>")


def main():
    """Main entry point."""
    result = Hello()
    return result
