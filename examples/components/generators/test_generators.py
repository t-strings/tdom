"""Test an example."""

import pytest

from . import main


# TODO Andrea this test should pass
@pytest.mark.skip(reason="Broken in latest generator support")
def test_main() -> None:
    """Ensure the demo matches expected."""
    assert str(main()) == "<ul><li>First</li><li>Second</li></ul>"
