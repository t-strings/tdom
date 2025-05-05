"""Get a variable from a passed-in ``prop``."""

from tdom import html


def Hello(name):
    """A simple hello component."""
    return html(t"<div>Hello {name}</div>")


def main():
    """Main entry point."""
    result = Hello(name="viewdom")
    return result
