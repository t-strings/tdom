"""Children as props."""

from tdom import html


def Heading(props, children):
    """The default heading."""
    return html(t"<h1>{props['title']}</h1><div>{children}</div>")


def main():
    """Main entry point."""
    result = html(t'<{Heading} title="My Title">Child<//>')
    return result
