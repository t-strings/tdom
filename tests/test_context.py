from tdom import html


def test_no_context():
    """Default behavior when no context is provided."""
    result = html(t"Hello World")
    assert "Hello World" == str(result)

def test_empty_context():
    """Default behavior when no context is provided but None."""
    context = {}
    result = html(t"Hello World", context=context)
    assert "Hello World" == str(result)

