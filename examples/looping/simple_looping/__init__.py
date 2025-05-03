"""Loop through values in a template and render them in a nested template."""

from tdom import html


def main():
    """Main entry point."""
    message = "Hello"
    names = ["World", "Universe"]
    result = html(
        t"""
            <ul title="{message}">
                {[
                    html(t'<li>{name}</li>')
                    for name in names
                ]}
            </ul>
            """
    )
    return result
