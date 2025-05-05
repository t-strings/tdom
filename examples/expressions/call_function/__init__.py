"""Call a function from inside a template expression."""

from tdom import html


def make_bigly(name: str) -> str:
    """A function returning a string, rather than a component."""
    return f"BIGLY: {name.upper()}"


def main():
    """Main entry point."""
    name = "viewdom"
    result = html(t"<div>Hello {make_bigly(name)}</div>")
    return result
