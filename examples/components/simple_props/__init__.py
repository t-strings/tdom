"""Use ``children`` as a built-in "prop"."""

from tdom import html


def Heading(title):
    """Default heading."""
    return html(t"<h1>{title}</h1>")


def main():
    """Main entry point."""
    result = html(t'<{Heading} title="My Title" />')
    return result
