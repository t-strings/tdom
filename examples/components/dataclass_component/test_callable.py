"""Test an example."""

import pytest

from . import main

@pytest.mark.skip("No dataclass support yet")
def test_main() -> None:
    """Ensure the greeting matches what is expected."""
    assert str(main()) == "<div>Hello viewdom</div>"
