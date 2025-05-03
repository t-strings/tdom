"""Boolean attribute values are reduced during rendering."""

from tdom import html


def main():
    """Main entry point."""
    result = html(t"<div editable={True}>Hello World</div>")
    return result
