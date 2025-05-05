"""Show the VDOM itself."""
from tdom import html


def main():
    """Main entry point."""
    result = html(t'<div class="container">Hello World</div>')
    return result
