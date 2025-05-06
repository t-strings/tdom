"""Render just a string literal."""

from tdom import html


def main():
    """Main entry point."""
    result = html(t"Hello World")
    return result
