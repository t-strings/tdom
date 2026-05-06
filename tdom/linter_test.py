from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from string.templatelib import Template

import pytest

from .linter import LintingTemplateProcessor, OnErrors, strict_checked_types_map
from .processor import ProcessContext
from .protocols import HasHTMLDunder


class HTML(HasHTMLDunder):
    text: str = ""

    def __html__(self) -> str:
        return self.text


@dataclass
class ColorFactoryComponent:
    color: str
    children: Template

    def __call__(self) -> Template:
        return t"<div class={self.color}>{self.children}</div>"


def ColorFunctionComponent(color: str, children: Template) -> Template:
    return t"<div class={color}>{children}</div>"


class TestLinterWithStrictTypes:
    @pytest.fixture
    def html(self) -> Callable[[Template], str]:
        tp = LintingTemplateProcessor(
            on_errors=OnErrors.RAISE, checked_types_map=strict_checked_types_map.copy()
        )
        ctx = ProcessContext()

        def _html(t: Template):
            return tp.process(t, assume_ctx=ctx)

        return _html

    def test_comment_inexact(self, html):
        assert html(t"<!-- {'works'} -->") == "<!-- works -->"
        with pytest.raises(
            ValueError, match="Invalid raw text inexact interpolation value."
        ):
            _ = html(t"<!-- {Template} -->")

    def test_comment_exact(self, html):
        assert html(t"<!--{'works'}-->") == "<!--works-->"
        with pytest.raises(
            ValueError, match="Invalid raw text exact interpolation value."
        ):
            _ = html(t"<!--{Template}-->")

    def test_element(self, html):
        content = "PRESS"
        assert (
            html(
                t'<div class="theme-default" id="thediv" aria={ {"button": True, "label": "divbutton"} } data={ {"active": True, "id": "thediv"} } class={ {"red": True} } class={["blue"]} style="background-color: yellow; z-index: 100" style={ {"color": "purple"} }>{content}</div>'
            )
            == '<div id="thediv" aria-button="true" aria-label="divbutton" data-active data-id="thediv" class="theme-default red blue" style="background-color: yellow; z-index: 100; color: purple">PRESS</div>'
        )

    def test_interpolated_general_attr(self, html):
        a = datetime.now(tz=timezone.utc)
        with pytest.raises(ValueError, match="Invalid interpolated attribute value"):
            _ = html(t"<div title={a}></div>")
        _ = html(t"<div title={100}></div>")  # OK

    def test_interpolated_class_attr(self, html):
        a = datetime.now(tz=timezone.utc)
        with pytest.raises(
            ValueError, match="Invalid interpolated class attribute value"
        ):
            _ = html(t"<div class={a}></div>")
        with pytest.raises(
            ValueError, match="Invalid interpolated class attribute value"
        ):
            _ = html(t"<div class={100}></div>")  # still not OK
        _ = html(t"<div class={('red',)}></div>")  # OK

    def test_spread_class_attr(self, html):
        a = datetime.now(tz=timezone.utc)
        with pytest.raises(ValueError, match="Invalid spread class attribute value"):
            _ = html(t"<div { {'class': a} }></div>")
        with pytest.raises(ValueError, match="Invalid spread class attribute value"):
            _ = html(t"<div { {'class': 100} }></div>")  # still not ok
        _ = html(t"<div { {'class': 'red'} }></div>")  # OK

    def test_function_component(self, html):
        assert (
            html(
                t"<{ColorFunctionComponent} color=red><span>OK</span></{ColorFunctionComponent}>"
            )
            == '<div class="red"><span>OK</span></div>'
        )

    def test_factory_component(self, html):
        assert (
            html(
                t"<{ColorFunctionComponent} color=red><span>OK</span></{ColorFunctionComponent}>"
            )
            == '<div class="red"><span>OK</span></div>'
        )

    def test_bad_component(self, html):
        def bad_call() -> str:
            return ""

        _ = html(t"<{bad_call} color=red><span>OK</span></{bad_call}>")
