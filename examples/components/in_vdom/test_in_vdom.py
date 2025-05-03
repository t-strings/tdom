"""Test an example."""
import pytest

from tdom import Element
from . import main


@pytest.mark.skip("Components are missing Element.name")
def test_main() -> None:
    """Ensure the demo matches expected."""
    result: Element = main()
    # TODO Andrea Should components have an Element.name?
    assert result.name == "Heading"