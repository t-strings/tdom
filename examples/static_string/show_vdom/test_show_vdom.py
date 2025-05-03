"""Test an example."""
from . import main
from tdom import Element


def test_main() -> None:
    """Ensure the demo matches expected."""
    result: Element = main()
    assert result.name == 'div'
    assert result.props == {"class": "container"}
    assert result.children == [{'data': 'Hello World', 'type': 3}]
