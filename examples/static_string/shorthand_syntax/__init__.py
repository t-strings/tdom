"""Shorthand syntax for attribute values means no need for double quotes."""

from tdom import html


def main():
    """Main entry point."""
    result = html(t'<div class={"Container1".lower()}>Hello World</div>')
    return result
