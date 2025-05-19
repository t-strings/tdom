"""Simple arithmetic expression in a template."""

from tdom import html


def main():
    """Main entry point."""
    name = "tdom"
    result = html(t"<div>Hello {1 + 3}</div>")
    return result
