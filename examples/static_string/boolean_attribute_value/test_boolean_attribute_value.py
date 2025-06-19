"""Test an example."""

from . import main


def test_main():
    """Ensure the demo matches expected."""
    assert "<div editable>Hello World</div>" == str(main())
