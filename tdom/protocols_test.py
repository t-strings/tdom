from markupsafe import Markup, escape

from .protocols import HasHTMLDunder


class LTEntity:
    def __html__(self):
        return "&lt;"


def test_custom_html_dunder_isinstance_has_html_dunder():
    lt = LTEntity()
    assert isinstance(lt, HasHTMLDunder)


def test_markup_isinstance_has_html_dunder():
    wrapped_html = Markup(escape("<div>"))
    assert isinstance(wrapped_html, HasHTMLDunder)


def test_str_not_isinstance_has_html_dunder():
    html_str = "<div>"
    assert not isinstance(html_str, HasHTMLDunder)
