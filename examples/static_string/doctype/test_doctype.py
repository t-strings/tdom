"""Test an example."""
from . import main


def test_main() -> None:
    """Ensure the demo matches expected."""
    assert main() == "<!DOCTYPE html>\n<div>Hello World</div>"
