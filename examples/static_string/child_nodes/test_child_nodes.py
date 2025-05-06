"""Test an example."""
from . import main
from tdom import Element

def test_main() -> None:
    """Ensure the demo matches expected."""
    result: Element = main()
    assert result.props == {}
    # Test first child
    assert result.children[0] == {'type': 3, 'data': 'Hello '}
    assert str(result) == '<div>Hello <span>World<em>!</em></span></div>'
