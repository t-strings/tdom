"""Test an example."""
from . import main


def test_main() -> None:
    """Ensure the demo matches expected."""
    assert str(main()) == '<div class="container1">Hello World</div>'
