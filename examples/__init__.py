"""Examples that serve as documentation and tests.

This is run in the browser, in MicroPython.
"""


# TODO expressions_as_values is broken in MicroPython, f-string in an expression
# from static_string import string_literal, simple_render, show_vdom #, expressions_as_values, shorthand_syntax, child_nodes, doctype, boolean_attribute_value
from static_string import string_literal, simple_render, show_vdom, shorthand_syntax, child_nodes, doctype, boolean_attribute_value

from tdom import html
from tdom.dom import _IS_MICRO_PYTHON

if _IS_MICRO_PYTHON:
    TypedDict = dict
else:
    from typing import TypedDict

class Story(TypedDict):
    path: str
    docstring: str
    code: str
    result: str
    rendered: str
    result: str | None


def main() -> list[Story]:
    """Return strings to be shoved into the DOM."""

    # Walk the examples, building a list of
    # modules = (string_literal, simple_render, show_vdom, expressions_as_values, shorthand_syntax, child_nodes, doctype, boolean_attribute_value)
    modules = (string_literal, simple_render, show_vdom, shorthand_syntax, child_nodes, doctype, boolean_attribute_value)
    stories = [get_story_data(module) for module in modules]
    return stories

def get_story_data(target) -> Story:
    """For each example, extract the information needed."""

    with open(target.__file__) as f:
        code = f.read()

    story: Story = {
        "path": str(target.__file__),
        "docstring": target.__doc__,
        "code": code,
        "result": str(target.main()),
        "rendered": None,
    }
    rendered = str(render_story(story))
    story["rendered"] = rendered
    return story


def render_story(example):
    heading = html(t'<h2>{example["docstring"]}</h2>')
    docstring = html(t'<p><em>{example["docstring"]}</em></p>')
    editor = html(t'<div class="editor"></div>')
    result = html(t'<div class="column"><h3>Result</h3>{example["result"]}</div>')
    return html(t'<section title="{example["path"]}">{heading}{docstring}<div class="row">{editor}{result}</div></section>')

def get_example(module):
    story = get_story_data(module)
    example = render_story(story)
    return str(example)
