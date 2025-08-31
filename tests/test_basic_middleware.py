"""Simple middleware as a decorator.

Use a decorator to intercept the returned ``Node`` and apply some
transformations:

- Text transforms such as uppercase
- Find and rewrite hrefs
- Linting, such as raising an exception on images without an alt
- Stashing extra props and processing in middleware
- Post-processing middleware at the end
"""
import pytest

from tdom import html, Text, Node, Element


def test_no_middleware():
    """Default behavior, no changes."""
    result = html(t"<div>Hello World</div>")
    assert "<div>Hello World</div>" == str(result)

def test_change_text_case():
    """Middleware that finds all text values and changes to uppercase."""

    # As we can see, if all intermediate results are converted to a string, such
    # as components, then middleware can't recurse into them.

    def text_case(node: Node) -> Node:
        # Normally we would recurse a tree
        for child in node.children:
            if isinstance(child, Text):
                child["data"] = child.data.upper()
        return node

    # Apply middleware to the
    result_node = html(t"<div>Hello World</div>")
    result = text_case(result_node)
    assert "<div>HELLO WORLD</div>" == str(result)


def test_simple_prefix_href():
    """Find all nodes with any href and add a prefix."""
    def prefix_href(node: Node) -> Node:
        prefix = "/public"
        for child in node.children:
            if isinstance(child, Element) and "href" in child.props:
                # This is simple-minded. Later examples show
                # a much richer approach.
                child.props["href"] = prefix + child.props["href"]

        return node

    result_node = html(t'<div><a href="/posts/1.html">First Post</a></div>')
    result = prefix_href(result_node)
    assert '<div><a href="/public/posts/1.html">First Post</a></div>' == str(result)

def test_enforce_auth():
    """Find all image nodes without an auth and raise an exception."""
    def prefix_href(node: Node) -> Node:
        for child in node.children:
            if isinstance(child, Element) and child.name == "img":
                if "alt" not in child.props:
                    raise ValueError("Missing 'alt' property")

        return node

    result_node = html(t'<div><img src="1.png"></img></div>')
    with pytest.raises(ValueError):
        prefix_href(result_node)

def test_custom_props():
    """Components can stash data for use by middleware."""
    from datetime import datetime
    def render_time(node: Node) -> Node:
        """Stash the datetime when a node was rendered."""
        now = datetime.now()
        if "tc" not in node.props:
            # Make the namespace if it isn't there
            node.props["tc"] = {}
        node.props["tc"]["render_time"] = now
        return node
    before = datetime.now()
    result_node = html(t'<div>Hello World</div>')
    result = render_time(result_node)
    assert before < result.props["tc"]["render_time"]

def test_defer_str():
    """Perhaps some middleware should run as late as possible."""

    # Some middleware might be expensive, and you want to defer it until the
    # node is rendered. Some might need more information before running: other
    # nodes in the document, other content in the system, etc.

    # Some middleware that runs at the very end. Perhaps, when
    # the server stringifies a response.
    def remove_tc(node: Node) -> Node:
        """Remove the housekeeping namespace in props."""
        if "tc" in node.props:
            del node.props["tc"]
        return node

    # Now monkey-patch the __str__ with a lambda that will be
    # called later. It applies the final middleware.
    # NOTE: This is a dumb way to do it, would be better in dom.py
    final_middlewares = (remove_tc,)
    def process_final_middlewares(node: Node) -> Node:
        """Run all the after-processing middleware"""
        [this_middleware(node) for this_middleware in final_middlewares]
        return node

    def run_final_middlewares(node: Node, element_str) -> str:
        """Run the middlewares then use original __str__ to make a string."""
        process_final_middlewares(node)
        return element_str(node)

    original_str = Element.__str__
    Element.__str__ = lambda this_node: run_final_middlewares(this_node, original_str)

    # Some component middleware, same as before.
    from datetime import datetime
    def render_time(node: Node) -> Node:
        """Stash the datetime when a node was rendered."""
        now = datetime.now()
        if "tc" not in node.props:
            # Make the namespace if it isn't there
            node.props["tc"] = {}
        node.props["tc"]["render_time"] = now
        return node
    result_node = html(t'<div>Hello World</div>')
    result = render_time(result_node)

    # It's time to stringify the response. Process all the final
    # middleware. But the prop isn't removed until str() is called.
    assert "tc" in result.props
    str(result)
    assert "tc" not in result.props

    # un-monkey-patch Element
    Element.__str__ = original_str

