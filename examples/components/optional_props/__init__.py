"""Optional props."""
from tdom import html


def Heading(title="My Title"):
    """The default heading."""

    return html(t"<h1>{title}</h1>")


def main():
    """Main entry point."""
    result = html(t"<{Heading} />")
    return result
