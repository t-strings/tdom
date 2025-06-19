"""Test an example."""

from . import main


def test_main():
    """Ensure the demo matches expected."""
    assert str(main()) == "<div>Hello World</div>"
