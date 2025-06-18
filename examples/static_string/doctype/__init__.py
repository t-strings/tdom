"""Getting a doctype into the rendered output is a bit tricky."""

from tdom import html


def main():
    """Main entry point."""
    result = html(t"<!DOCTYPE html>\n<div>Hello World</div>")
    return result
