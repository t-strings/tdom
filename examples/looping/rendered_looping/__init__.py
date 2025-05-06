"""Generate a list of VDOMs then use in a render."""

from tdom import html


def main():
    """Main entry point."""
    message = "Hello"
    names = ["World", "Universe"]
    items = [html(t"<li>{label}</li>") for label in names]
    result = html(
        t"""
            <ul title="{message}">
              {items}
            </ul>
            """
    )
    return result
