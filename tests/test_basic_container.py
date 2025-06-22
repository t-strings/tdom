from tdom import html


def test_no_container():
    """Default behavior when no container is provided."""
    result = html(t"Hello World")
    assert "Hello World" == str(result)

def test_component_no_container():
    """A component asks for a container."""
    def Header():
        return html(t"Hello World")
    result = html(t"<{Header}/>")
    assert "Hello World" == str(result)

def test_empty_container():
    """Default behavior when no container is provided but None."""
    request_container = {}
    result = html(t"Hello World", container=request_container)
    assert "Hello World" == str(result)

def test_component_empty_container():
    """A component asks for a container."""
    def Header():
        return html(t"Hello World")
    request_container = {}
    result = html(t"<{Header}/>", container=request_container)
    assert "Hello World" == str(result)

def test_component_not_ask_container():
    """A component does not ask for a container."""
    def Header():
        return html(t"Hello World")
    request_container = {}
    result = html(t"<{Header}/>", container=request_container)
    assert "Hello World" == str(result)

def test_component_asks_container():
    """A component asks for a container."""
    def Header(container):
        label = container["label"]
        return html(t"Hello {label}")
    request_container = {"label": "World"}
    result = html(t"<{Header}/>", container=request_container)
    assert "Hello World" == str(result)

