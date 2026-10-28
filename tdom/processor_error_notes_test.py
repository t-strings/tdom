"""
Tests for error notes generated during template processing exceptions.

@NOTE: These tests are meant to only check the strings in `e.__notes__` are correct.

The primary tests for the processor are meant to check that all error conditions are "handled".
"""

from dataclasses import dataclass
from string.templatelib import Template

import pytest
from markupsafe import Markup

from .processor import (
    AttributeProcessingError,
    ComponentProcessingError,
    ProcessContext,
    TemplateParserProxy,
    TextProcessingError,
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


@pytest.fixture
def markup_maker():
    return MarkupMaker


@dataclass
class MarkupMaker:
    """
    Returns supposedly sanitized HTML via __html__().

    Use the fixture `markup_maker` instead of using this directly.
    """

    payload: str = ""

    throw: bool = False

    def __html__(self) -> str:
        if self.throw:
            raise ValueError("Failed to make markup.")
        return self.payload


@pytest.fixture
def wrapper_maker():
    return WrapperMaker


@dataclass
class WrapperMaker:
    """
    Configure a component that wraps all children in the specified tag.

    Use fixture `wrapper_maker` instead of using this directly.

    @NOTE: This component only supports the "1st call" usage because it is preconfigured.
    """

    tag: str = "div"

    def __call__(self, children: Template) -> Template:
        return Template(f"<{self.tag}>") + t"{children}" + Template(f"</{self.tag}>")


class TestAttributes:
    """
    Test error notes from attributes.
    """

    def test_interpolated_attribute(self):
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

    def test_templated_attribute(self):
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

    def test_spread_attribute(self):
        with pytest.raises(AttributeProcessingError, match="no") as exc_info:
            _ = html(t"<div {0}></div>")
        assert_notes(
            exc_info.value.__notes__,
            ["... in spread attribute {0} for <div {0}> at line 1 offset 0"],
        )

    def test_literal_attribute(self):
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


class TestTextInterpolations:
    """
    Test error notes from text node interpolations.

    A singleton TemplateRef is exactly 1 interpolation without any leading or trailing text.
    - <div>{singleton}</div>
    - <script>{singleton}</script>
    - <!--{singleton}-->
    - {singleton}

    A "mixed" TemplateRef is either 1 interpolation with non-empty leading and/or trailing text or 2 or more interpolations.
    """

    def test_ambiguous_singleton(self, cb_value_error):
        with pytest.raises(Exception) as exc_info:
            # This text is not in any element at all.
            _ = html(t"{cb_value_error:callback}")
        assert_notes(
            exc_info.value.__notes__,
            [
                "... in {cb_value_error:callback} at line 1 offset 0",
            ],
        )

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

    def test_ambiguous_mixed(self, cb_value_error):
        with pytest.raises(Exception) as exc_info:
            # This text is not in any element at all.
            _ = html(t"ok {cb_value_error:callback}")
        assert_notes(
            exc_info.value.__notes__,
            [
                "... in {cb_value_error:callback} within ok {cb_value_error:callback} at line 1 offset 0",
            ],
        )

    def test_mixed_multiline(self, cb_value_error):
        def setup_template():
            return t"""<b>\nabc   {cb_value_error:callback}\n</b>"""

        with pytest.raises(Exception) as exc_info:
            _ = html(setup_template())
        assert_notes(
            exc_info.value.__notes__,
            [
                # @NOTE: This offset is to the TText position in the Template
                # and not the interpolation's location WITHIN the TText.
                "... in {cb_value_error:callback} within \nabc   {cb_value_error:callback}\n at line 1 offset 3",
                "... in <b> at line 1 offset 0",
            ],
        )

    def test_singleton_with_ambiguous_singleton_template(self, cb_value_error):
        def setup_template():  # avoidqa: RUF027
            inner_t = t"{cb_value_error:callback}"
            return t"<div>{inner_t}</div>"

        with pytest.raises(ValueError, match="Callback failed") as exc_info:
            _ = html(setup_template())
        assert_notes(
            exc_info.value.__notes__,
            [
                "... in {cb_value_error:callback} at line 1 offset 0",
                "... in {inner_t} at line 1 offset 5",
                "... in <div> at line 1 offset 0",
            ],
        )

    def test_mixed_with_ambiguous_singleton_template(self, cb_value_error):
        def setup_template():  # avoidqa: RUF027
            inner_t = t"{cb_value_error:callback}"
            return t"<div>ok {inner_t}</div>"

        with pytest.raises(ValueError, match="Callback failed") as exc_info:
            _ = html(setup_template())
        assert_notes(
            exc_info.value.__notes__,
            [
                "... in {cb_value_error:callback} at line 1 offset 0",
                "... in {inner_t} within ok {inner_t} at line 1 offset 5",
                "... in <div> at line 1 offset 0",
            ],
        )

    def test_singleton_with_mixed_template(self, cb_value_error):
        def setup_template():  # avoidqa: RUF027
            inner_t = t"ok {cb_value_error:callback}"
            return t"<div>{inner_t}</div>"

        with pytest.raises(ValueError, match="Callback failed") as exc_info:
            _ = html(setup_template())
        assert_notes(
            exc_info.value.__notes__,
            [
                "... in {cb_value_error:callback} within ok {cb_value_error:callback} at line 1 offset 0",
                "... in {inner_t} at line 1 offset 5",
                "... in <div> at line 1 offset 0",
            ],
        )


class TestCommentInterpolations:
    """
    Test error notes from comment node interpolations.
    """

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


class TestComponentInterpolations:
    """
    Test error notes from component node interpolations.
    """

    def test_children_mixed_interpolation(self, cb_value_error, wrapper_maker):
        def setup_template() -> Template:
            DivWrapper = wrapper_maker("div")  # avoidqa: RUF027
            return t"""<{DivWrapper}>ok? {cb_value_error:callback}</{DivWrapper}>"""

        with pytest.raises(ValueError) as exc_info:
            _ = html(setup_template())
        assert_notes(
            exc_info.value.__notes__,
            [
                "... in {cb_value_error:callback} within ok? {cb_value_error:callback} at line 1 offset 0",
                "... in {children} at line 1 offset 5",  # @TODO: Should this be inlined into the parent tag?
                "... in <div> at line 1 offset 0",
                "... in <{DivWrapper}> at line 1 offset 0",
            ],
        )

    def test_children_singleton_interpolation(self, cb_value_error, wrapper_maker):
        def setup_template() -> Template:
            DivWrapper = wrapper_maker("div")  # avoidqa: RUF027
            return t"""<{DivWrapper}>{cb_value_error:callback}</{DivWrapper}>"""

        with pytest.raises(ValueError) as exc_info:
            _ = html(setup_template())
        assert_notes(
            exc_info.value.__notes__,
            [
                "... in {cb_value_error:callback} at line 1 offset 0",
                "... in {children} at line 1 offset 5",
                "... in <div> at line 1 offset 0",
                "... in <{DivWrapper}> at line 1 offset 0",
            ],
        )


class TestComponentAttributes:
    """
    Test error notes from component node attributes.
    """

    def test_missing(self):
        def setup_template() -> Template:
            def Badge(label: str) -> Template:
                return t"<b>{label}</b>"

            return t"<div><{Badge}/></div>"

        with pytest.raises(
            ComponentProcessingError,
            match="Missing required parameters for component: label",
        ) as exc_info:
            _ = html(setup_template())
        assert_notes(
            exc_info.value.__notes__,
            [
                "... in <{Badge}/> at line 1 offset 5",
            ],
        )


class TestNestedProcessorCallout:
    """
    Test error notes involving nested calls to html() while already actively processing a template with html().

    @NOTE: This isn't recommended usage but it should still work and
    is helpful as a sanity check if we are cleaning up properly.
    """

    def test_another_html_via_callback(self, cb_value_error):
        """Make a 2nd call to html() from a callback during processing the 1st html() call."""

        def setup_template() -> Template:
            def get_content() -> str:
                return Markup(html(t"<span>{cb_value_error:callback}</span>"))

            return t"<div>{get_content:callback}</div>"

        with pytest.raises(ValueError, match="Callback failed") as exc_info:
            _ = html(setup_template())
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

        def setup_template() -> Template:
            def Content(children: Template) -> Template:
                content = Markup(html(children))
                return t"<span>{content}</span>"

            return t"<div><{Content}><b>{cb_value_error:callback}</b></{Content}></div>"

        with pytest.raises(ValueError, match="Callback failed") as exc_info:
            _ = html(setup_template())
        assert_notes(
            exc_info.value.__notes__,
            [
                "... in {cb_value_error:callback} at line 1 offset 3",
                "... in <b> at line 1 offset 0",
                "... in <{Content}> at line 1 offset 5",
            ],
        )


class TestHTMLDunder:
    """
    Test error notes involving objects with __html__ methods.
    """

    def test_via_normal_interpolation(self, markup_maker):
        def setup_template():
            content = markup_maker(throw=True)
            return t"<div>{content}</div>"

        with pytest.raises(ValueError, match="Failed to make markup") as exc_info:
            _ = html(setup_template())
        assert_notes(
            exc_info.value.__notes__,
            [
                "... in {content} at line 1 offset 5",
                "... in <div> at line 1 offset 0",
            ],
        )

    def test_via_script_interpolation(self, markup_maker):
        def setup_template():
            content = markup_maker(throw=True)
            return t"<div><script>{content}</script></div>"

        with pytest.raises(ValueError, match="Failed to make markup") as exc_info:
            _ = html(setup_template())
        assert_notes(
            exc_info.value.__notes__,
            [
                "... in {content} at line 1 offset 13",
                "... in <script> at line 1 offset 5",
            ],
        )

    def test_via_script_mixed_not_allowed(self, markup_maker):
        """
        Markup objects are not allowed inside scripts unless the content is a single interpolation.
        """

        def setup_template() -> Template:
            content = markup_maker(payload="<span></span>", throw=False)
            return t"<div><script>Ok? {content}</script></div>"

        with pytest.raises(
            TextProcessingError, match="are not supported within script"
        ) as exc_info:
            _ = html(setup_template())
        assert_notes(
            exc_info.value.__notes__,
            [
                "... in {content} within Ok? {content} at line 1 offset 13",
                "... in <script> at line 1 offset 5",
            ],
        )
