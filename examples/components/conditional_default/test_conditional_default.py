"""Test an example."""

from . import main


def test_main() -> None:
    """Ensure the demo matches expected."""
    assert str(main()) == "<body><h1>Other Heading</h1></body>"
