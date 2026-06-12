from collections.abc import Callable
from string.templatelib import Template

import pytest

from tdom import html
from tdom.parser import TemplateParser
from tdom.tnodes import TComponent, TElement


def PTC(children: Template) -> Template:
    """Pass children through."""
    return children


def get_relaxed_html_templates(
    Comp: Callable[[Template], Template] = PTC,
) -> tuple[Template, ...]:
    return (
        t"<div><{Comp}><circle/></{Comp}></div>",
        t"<div><{Comp}><mspace/></{Comp}></div>",
        t"<div><{Comp}><div/></{Comp}></div>",
        t"<div><{Comp}><div><{Comp}/><{Comp}><div/></{Comp}></div></{Comp}></div>",
    )


def get_relaxed_xml_templates(
    Comp: Callable[[Template], Template] = PTC,
) -> tuple[Template, ...]:
    return (
        t"<svg><{Comp}><input></{Comp}></svg>",
        t"<svg><{Comp}><svg><input></svg></{Comp}></svg>",
        t"<math><{Comp}><input></{Comp}></math>",
        t"<svg><{Comp}><math><input></math></{Comp}></svg>",
        t"<svg><{Comp}><foreignobject><circle/></foreignobject></{Comp}></svg>",
    )


class TestRelaxedRulesInParser:
    """These templates work in the parser because we don't have enough ctx."""

    def test_html_wrapped(self):
        # html rules relaxed during component parsing
        for tf in get_relaxed_html_templates():
            node = TemplateParser.parse(tf)
            assert isinstance(node, TElement) and node.tag == "div"
            assert len(node.children) == 1 and isinstance(node.children[0], TComponent)

    def test_xml_wrapped(self):
        # xml (svg/mathml) rules relaxed during component parsing
        for tf in get_relaxed_xml_templates():
            node = TemplateParser.parse(tf)
            assert isinstance(node, TElement) and node.tag in ("svg", "math")
            assert len(node.children) == 1 and isinstance(node.children[0], TComponent)


class TestRelaxedRulesInProcessor:
    """These templates fail in the processor when only passed through."""

    def test_html_wrapped_component_ok(self):
        for tf in get_relaxed_html_templates():
            with pytest.raises(ValueError):
                _ = html(tf)

    def test_xml_wrapped_component_ok(self):
        for tf in get_relaxed_xml_templates():
            with pytest.raises(ValueError):
                _ = html(tf)
