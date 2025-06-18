"""Escape untrusted values by using the unsafe function."""

from tdom import html, unsafe


def main():
    """Main entry point."""
    span = "<span>Hello World</span>"
    result = html(t"<div>{unsafe(span)}</div>")
    return result
