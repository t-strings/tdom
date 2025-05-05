"""Render a string wrapped by a div."""

from tdom import html


def main():
    """Main entry point."""
    result = html(t"<div>Hello World</div>")
    return result
