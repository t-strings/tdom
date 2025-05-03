"""Pass a Python symbol as part of an expression."""

from tdom import html


def Heading(props, children):
    """The default heading."""
    title = props["title"]
    return html(t"<h1>{title}</h1>")


def main():
    """Main entry point."""
    result = html(t'<{Heading} title={"My Title"} />')
    return result
