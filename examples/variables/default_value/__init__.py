"""The prop has a default value, so caller doesn't have to provide it."""

from tdom import html


def Hello(name="viewdom"):
    """A simple hello component."""
    return html(t"<div>Hello {name}</div>")


def main():
    """Main entry point."""
    result = Hello()
    return result
