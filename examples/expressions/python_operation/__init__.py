"""Python operation in the expression."""

from tdom import html


def main():
    """Main entry point."""
    name = "viewdom"
    result = html(t"<div>Hello {name.upper()}</div>")
    return result
