"""Test an example."""

import pytest

from . import main


@pytest.mark.skip("No generator support yet")
def test_main() -> None:
    """Ensure the demo matches expected."""
    assert str(main()) == "<ul><li>First</li><li>Second</li></ul>"
