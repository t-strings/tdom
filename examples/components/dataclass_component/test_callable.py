"""Test an example."""

import pytest

from . import main

def test_main() -> None:
    """Ensure the greeting matches what is expected."""
    assert str(main()) == "<div>Hello viewdom</div>"
