"""Simple arithmetic expression in a template."""

from tdom import html


def main():
    """Main entry point."""
    result = html(t"<div>Hello {1 + 3}</div>")
    return result
