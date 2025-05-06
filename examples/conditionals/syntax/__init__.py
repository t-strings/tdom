"""Use normal Python syntax for conditional rendering in a template."""

from tdom import html


def main():
    """Main entry point."""
    message = "Say Howdy"
    not_message = "So Sad"
    show_message = True
    result = html(
        t"""
        <h1>Show?</h1>
        {message if show_message else not_message}
    """
    )
    return result
