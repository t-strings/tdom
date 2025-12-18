from string.templatelib import Interpolation

import pytest

from .template_utils import TemplateRef, template_from_parts


def test_template_from_parts() -> None:
    strings = ("Hello, ", "! Today is ", ".")
    interpolations = (Interpolation("Alice"), Interpolation("Monday"))
    template = template_from_parts(strings, interpolations)
    assert template.strings == strings
    assert template.interpolations == interpolations


def test_template_ref_is_literal() -> None:
    literal_ref = TemplateRef.literal("Hello")
    assert literal_ref.is_literal

    non_literal_ref = TemplateRef(("", ""), (0,))
    assert not non_literal_ref.is_literal


def test_template_ref_is_empty() -> None:
    empty_ref = TemplateRef.empty()
    assert empty_ref.is_empty

    non_empty_ref = TemplateRef.literal("Hello")
    assert not non_empty_ref.is_empty


def test_template_ref_is_singleton() -> None:
    singleton_ref = TemplateRef.singleton(0)
    assert singleton_ref.is_singleton

    non_singleton_ref = TemplateRef.literal("Hello")
    assert not non_singleton_ref.is_singleton


def test_template_ref_post_init_validation() -> None:
    with pytest.raises(ValueError):
        _ = TemplateRef(("Hello",), (0, 1))
