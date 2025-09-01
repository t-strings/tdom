"""Examples that serve as documentation and tests.

This is run in the browser, in MicroPython.
"""

import sys

from examples.static_string import (
    string_literal,
    simple_render,
    show_vdom,
    expressions_as_values,
    shorthand_syntax,
    child_nodes,
    doctype,
    boolean_attribute_value,
)

from tdom.micropython import html, unsafe

_IS_MICRO_PYTHON = "MicroPython" in sys.version

if _IS_MICRO_PYTHON:
    TypedDict = dict
else:
    from typing import TypedDict


class Story(TypedDict):
    file_path: str
    module_path: str
    docstring: str
    code: str
    result: str
    rendered: str
    result: str


def main() -> list[Story]:
    """Return strings to be shoved into the DOM."""

    modules = (
        string_literal,
        simple_render,
        show_vdom,
        expressions_as_values,
        shorthand_syntax,
        child_nodes,
        doctype,
        boolean_attribute_value,
    )
    stories = [get_story_data(module) for module in modules]
    return stories


def get_story_data(target) -> Story:
    """For each example, extract the information needed."""

    with open(target.__file__) as f:
        code = f.read()

    module_path = target.__name__.replace("/__init__.py", "")
    file_path = str(target.__file__)
    story: Story = {
        "file_path": file_path,
        "module_path": module_path,
        "docstring": target.__doc__,
        "code": code,
        "result": unsafe(str(target.main())),
        "rendered": "",
    }
    rendered = str(render_story(story))
    story["rendered"] = rendered
    return story


def render_story(example):
    module_path = example["module_path"]
    heading = html(t"<h2>{example['docstring']}</h2>")
    docstring = html(t"<p><em>{example['docstring']}</em></p>")
    editor = html(t'<div class="editor"></div>')
    result = html(
        t'<div class="column"><h2>Result</h2><div class="result" title="Result">{example["result"]}</div></div>'
    )
    re_run = html(t'<div class="row"><button class="run-code">Re-run</button></div>')
    return html(
        t'<section id="{module_path}" title="{module_path}">{heading}{docstring}<div class="row">{editor}{result}</div>{re_run}</section>'
    )


def get_example(module):
    story = get_story_data(module)
    example = render_story(story)
    return str(example)
