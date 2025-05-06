"""Use a nested f-string to communicate a dynamic attribute value."""

from tdom import html


def main():
    """Main entry point."""
    result = html(t'<div class="{f"container{1}"}">Hello World</div>')
    return result
