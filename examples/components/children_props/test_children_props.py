"""Test an example."""

from . import main


def test_main():
    """Ensure the demo matches expected."""
    assert str(main()) == "<h1>My Title</h1><div>Child</div>"
