"""Pass a Python symbol as part of an expression."""

from tdom import html


def Heading(title):
    """The default heading."""
    return html(t"<h1>{title}</h1>")


def main():
    """Main entry point."""
    result = html(t'<{Heading} title={"My Title"} />')
    return result
