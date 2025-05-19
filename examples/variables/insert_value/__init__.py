"""Simple example of inserting a variable value into a template."""

from tdom import html


def main():
    """Main entry point."""
    name = "tdom"
    result = html(t"<div>Hello {name}</div>")
    return result
