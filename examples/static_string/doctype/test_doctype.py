"""Test an example."""
from . import main


def test_main():
    """Ensure the demo matches expected."""
    assert str(main()) == "<!DOCTYPE html><div>Hello World</div>"
