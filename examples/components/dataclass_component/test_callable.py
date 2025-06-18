"""Test an example."""

import pytest

from . import main


def test_main():
    """Ensure the greeting matches what is expected."""
    assert str(main()) == "<div>Hello tdom</div>"
