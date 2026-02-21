from string.templatelib import Template

from .processor import to_node
from .nodes import Element, Text, Fragment, DocumentType, Comment

#
# @NOTE: Most of the processor tests are in the main process_test.py file.
#


def test_to_node_integration():
    """Test all the major elements with nodes."""
    title = "Test Title"
    url_path = "about"
    content = "About"
    extra_kwargs = {"id": "my-link"}

    def simple_comp(label: str, children: Template) -> Template:
        return t"<section>{label}: {children}</section><span>Tail</span>"

    node = to_node(
        (
            t"<!doctype html>"
            t"<!-- comment -->"
            t"<script>var x = 1;</script>"
            t"<div><br>&gt;</div>"
            t"<div>{[0, 1]}</div>"
            t'<a class="red" title={title} href="/{url_path}" {extra_kwargs}>{content}</a>'
            t'<{simple_comp} label="The Children"><span>Child0</span><span>Child1</span></{simple_comp}>'
        )
    )
    assert node == Fragment(
        children=[
            DocumentType("html"),
            Comment(" comment "),
            Element("script", children=[Text("var x = 1;")]),
            Element("div", children=[Element("br"), Text(">")]),
            Element("div", children=[Text("0"), Text("1")]),
            Element(
                "a",
                attrs={
                    "class": "red",
                    "title": title,
                    "href": f"/{url_path}",
                    "id": "my-link",
                },
                children=[Text(content)],
            ),
            Element(
                "section",
                children=[
                    Text("The Children"),
                    Text(": "),
                    Element("span", children=[Text("Child0")]),
                    Element("span", children=[Text("Child1")]),
                ],
            ),
            Element("span", children=[Text("Tail")]),
        ]
    )
