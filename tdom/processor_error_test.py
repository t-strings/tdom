"""
Tests for processing errors.
"""

from string.templatelib import Template

import pytest
from markupsafe import Markup

from .processor import (
    AttributeProcessingError,
    ComponentProcessingError,
    ProcessContext,
    TemplateParserProxy,
    _make_default_template_processor,
)

processor_api = _make_default_template_processor(
    parser_api=TemplateParserProxy(),  # do not use cache
)


def make_ctx(**kwargs):
    return ProcessContext(**kwargs)


def html(template: Template, assume_ctx: ProcessContext | None = None):
    if assume_ctx is None:
        assume_ctx = ProcessContext()
    return processor_api.process(template, assume_ctx=assume_ctx)


def assert_notes(actual: list[str], expected: list[str]) -> None:
    """
    Check note by note so the diff isn't exploded when one note is off but fallback to full comparison.
    """
    expected_count = len(expected)
    actual_count = len(actual)
    for index in range(actual_count):
        if index < expected_count:
            # Compare line by line to catch formatting differences
            assert actual[index] == expected[index], (
                f"actual[{index}] != expected[{index}]"
            )
        else:
            break
    # Catch parity differences and anything else but with special pytest handling.
    if expected_count != actual_count:
        assert actual == expected


@pytest.fixture
def cb_value_error():
    """Callback that just raises value error."""

    def _cb_value_error():
        raise ValueError("Callback failed.")

    return _cb_value_error


class TestAttributeErrors:
    def test_interpolated_attribute_error(self):
        with pytest.raises(
            AttributeProcessingError, match="Cannot use int as value"
        ) as exc_info:
            _ = html(t"<div aria={0}></div>")
        assert_notes(
            exc_info.value.__notes__,
            [
                "... in interpolated attribute aria={0} for <div aria={0}> at line 1 offset 0"
            ],
        )

    def test_templated_attribute_error(self):
        with pytest.raises(
            AttributeProcessingError, match="data attributes cannot be templated"
        ) as exc_info:
            _ = html(t'<div data="label_{0}"></div>')
        assert_notes(
            exc_info.value.__notes__,
            [
                '... in templated attribute data=label_{0} for <div data="label_{0}"> at line 1 offset 0'
            ],
        )

    def test_spread_attribute_error(self):
        with pytest.raises(AttributeProcessingError, match="no") as exc_info:
            _ = html(t"<div {0}></div>")
        assert_notes(
            exc_info.value.__notes__,
            ["... in spread attribute {0} for <div {0}> at line 1 offset 0"],
        )

    def test_literal_attribute_error(self):
        with pytest.raises(
            AttributeProcessingError, match="Invalid number of parts"
        ) as exc_info:
            _ = html(t'<div style="status:great" style="status:"></div>')
        assert_notes(
            exc_info.value.__notes__,
            [
                '... in literal attribute style=status: for <div style="status:great" style="status:"> at line 1 offset 0'
            ],
        )


class TestTextInterpolationNotes:
    def test_singleton(self, cb_value_error):
        with pytest.raises(Exception) as exc_info:
            _ = html(t"<div>{cb_value_error:callback}</div>")
        assert_notes(
            exc_info.value.__notes__,
            [
                "... in {cb_value_error:callback} at line 1 offset 5",
                "... in <div> at line 1 offset 0",
            ],
        )

    def test_mixed_multiline(self, cb_value_error):
        def nofmt():
            return t"""<div>\n    {cb_value_error:callback}\n</div>"""

        with pytest.raises(Exception) as exc_info:
            _ = html(nofmt())
        assert_notes(
            exc_info.value.__notes__,
            [
                "... in {cb_value_error:callback} within \n    {cb_value_error:callback}\n at line 1 offset 5",
                "... in <div> at line 1 offset 0",
            ],
        )

    def test_singleton_with_singleton_template(self, cb_value_error):
        def outer_t():  # avoidqa: RUF027
            inner_t = t"{cb_value_error:callback}"
            return t"<div>{inner_t}</div>"

        with pytest.raises(ValueError, match="Callback failed") as exc_info:
            _ = html(outer_t())
        assert_notes(
            exc_info.value.__notes__,
            [
                "... in {cb_value_error:callback} at line 1 offset 0",
                "... in {inner_t} at line 1 offset 5",
                "... in <div> at line 1 offset 0",
            ],
        )

    def test_mixed_with_singleton_template(self, cb_value_error):
        def outer_t():  # avoidqa: RUF027
            inner_t = t"{cb_value_error:callback}"
            return t"<div>ok {inner_t}</div>"

        with pytest.raises(ValueError, match="Callback failed") as exc_info:
            _ = html(outer_t())
        assert_notes(
            exc_info.value.__notes__,
            [
                "... in {cb_value_error:callback} at line 1 offset 0",
                "... in {inner_t} within ok {inner_t} at line 1 offset 5",
                "... in <div> at line 1 offset 0",
            ],
        )

    def test_singleton_with_mixed_template(self, cb_value_error):
        def outer_t():  # avoidqa: RUF027
            inner_t = t"ok {cb_value_error:callback}"
            return t"<div>{inner_t}</div>"

        with pytest.raises(ValueError, match="Callback failed") as exc_info:
            _ = html(outer_t())
        assert_notes(
            exc_info.value.__notes__,
            [
                "... in {cb_value_error:callback} within ok {cb_value_error:callback} at line 1 offset 0",
                "... in {inner_t} at line 1 offset 5",
                "... in <div> at line 1 offset 0",
            ],
        )


class TestCommentInterpolationNotes:
    def test_singleton(self, cb_value_error):
        with pytest.raises(ValueError, match="Callback failed") as exc_info:
            _ = html(t"<!--{cb_value_error:callback}-->")
        assert_notes(
            exc_info.value.__notes__,
            [
                "... in <!--{cb_value_error:callback}--> at line 1 offset 0",
            ],
        )

    def test_mixed(self, cb_value_error):
        with pytest.raises(ValueError, match="Callback failed") as exc_info:
            _ = html(t"<!--ok {cb_value_error:callback}-->")
        assert_notes(
            exc_info.value.__notes__,
            [
                "... in {cb_value_error:callback} within <!--ok {cb_value_error:callback}--> at line 1 offset 0",
            ],
        )


class TestComponentNotes:
    @pytest.fixture
    def Wrapper(self):
        def _Wrapper(children: Template) -> Template:
            return t"<div>{children}</div>"

        return _Wrapper

    def test_children_mixed_interpolation(self, cb_value_error, Wrapper):
        def nofmt() -> Template:
            DivWrapper = Wrapper  # avoidqa: RUF027
            return t"""<{DivWrapper}>ok? {cb_value_error:callback}</{DivWrapper}>"""

        with pytest.raises(ValueError) as exc_info:
            _ = html(nofmt())
        assert_notes(
            exc_info.value.__notes__,
            [
                "... in {cb_value_error:callback} within ok? {cb_value_error:callback} at line 1 offset 0",
                "... in {children} at line 1 offset 5",  # @TODO: Should this be inlined into the parent tag?
                "... in <div> at line 1 offset 0",
                "... in <{DivWrapper}> at line 1 offset 0",
            ],
        )

    def test_children_singleton_interpolation(self, cb_value_error, Wrapper):
        def nofmt() -> Template:
            DivWrapper = Wrapper  # avoidqa: RUF027
            return t"""<{DivWrapper}>{cb_value_error:callback}</{DivWrapper}>"""

        with pytest.raises(ValueError) as exc_info:
            _ = html(nofmt())
        assert_notes(
            exc_info.value.__notes__,
            [
                "... in {cb_value_error:callback} at line 1 offset 0",
                "... in {children} at line 1 offset 5",
                "... in <div> at line 1 offset 0",
                "... in <{DivWrapper}> at line 1 offset 0",
            ],
        )

    def test_component_attribute_error(self):
        def nofmt() -> Template:
            def Badge(label: str) -> Template:
                return t"<b>{label}</b>"

            return t"<div><{Badge}/></div>"

        with pytest.raises(
            ComponentProcessingError,
            match="Missing required parameters for component: label",
        ) as exc_info:
            _ = html(nofmt())
        assert_notes(
            exc_info.value.__notes__,
            [
                "... in <{Badge}/> at line 1 offset 5",
            ],
        )


class TestAnotherProcessor:
    def test_another_html_via_callback(self, cb_value_error):
        """Make a 2nd call to html() from a callback during processing the 1st html() call."""

        def nofmt() -> Template:
            def get_content() -> str:
                return Markup(html(t"<span>{cb_value_error:callback}</span>"))

            return t"<div>{get_content:callback}</div>"

        with pytest.raises(ValueError, match="Callback failed") as exc_info:
            _ = html(nofmt())
        assert_notes(
            exc_info.value.__notes__,
            [
                "... in {cb_value_error:callback} at line 1 offset 6",
                "... in <span> at line 1 offset 0",
                "... in {get_content:callback} at line 1 offset 5",
                "... in <div> at line 1 offset 0",
            ],
        )

    def test_another_html_via_component(self, cb_value_error):
        """Make a 2nd call to html() from a component during processing the 1st html() call."""

        def nofmt() -> Template:
            def Content(children: Template) -> Template:
                content = Markup(html(children))
                return t"<span>{content}</span>"

            return t"<div><{Content}><b>{cb_value_error:callback}</b></{Content}></div>"

        with pytest.raises(ValueError, match="Callback failed") as exc_info:
            _ = html(nofmt())
        assert_notes(
            exc_info.value.__notes__,
            [
                "... in {cb_value_error:callback} at line 1 offset 3",
                "... in <b> at line 1 offset 0",
                "... in <{Content}> at line 1 offset 5",
            ],
        )
