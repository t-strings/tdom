from string.templatelib import Interpolation

import pytest

from .template_utils import TemplateRef, combine_template_refs, template_from_parts


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


def test_combine_template_refs():
    template_refs = map(
        TemplateRef.from_naive_template,
        [
            t"ab",
            t"c{0}d",
            t"ef{1}",
            t"{2}ghi",
        ],
    )
    assert combine_template_refs(*template_refs) == TemplateRef.from_naive_template(
        t"abc{0}def{1}{2}ghi"
    )


def test_template_ref_iter_singleton():
    assert list(TemplateRef.from_naive_template(t"{1}")) == [1]


def test_template_ref_iter_empty():
    assert list(TemplateRef.from_naive_template(t"")) == []


def test_template_ref_iter_empty_prefix():
    assert list(TemplateRef.from_naive_template(t"{1}def")) == [1, "def"]


def test_template_ref_iter_empty_suffix():
    assert list(TemplateRef.from_naive_template(t"abc{1}")) == ["abc", 1]


def test_template_ref_iter_literal():
    assert list(TemplateRef.from_naive_template(t"abc")) == ["abc"]


def test_template_ref_iter_only_interpolations():
    assert list(TemplateRef.from_naive_template(t"{1}{3}{5}")) == [1, 3, 5]


def test_template_ref_iter_complete():
    assert list(TemplateRef.from_naive_template(t"abc{1}def{3}ghi{5}jkl")) == [
        "abc",
        1,
        "def",
        3,
        "ghi",
        5,
        "jkl",
    ]


def test_template_ref_resolve():
    src_t = t"{'a'}b{'c'}d{'e'}f"
    src_ref = TemplateRef(
        strings=src_t.strings, i_indexes=tuple(range(len(src_t.interpolations)))
    )
    resolved_t = src_ref.resolve(src_t.interpolations)
    assert resolved_t.values == ("a", "c", "e")
    assert resolved_t.strings == ("", "b", "d", "f")


from .template_utils import PartPosition, slice_to_tref


class TestSliceToTRef:
    def test_string_only_stop(self):
        parts = list(
            TemplateRef.from_naive_template(t"<div></div>").slice(
                start=None, stop=PartPosition(index=0, offset=5)
            )
        )
        assert parts == ["<div>"]

    def test_string_only_start(self):
        parts = list(
            slice_to_tref(t"<div></div>", start=PartPosition(index=0, offset=5))
        )
        assert parts == ["</div>"]

    def test_string_only_start_stop(self):
        parts = list(
            slice_to_tref(
                t"<div></div>",
                start=PartPosition(index=0, offset=4),
                stop=PartPosition(index=0, offset=6),
            )
        )
        assert parts == ["><"]

    def test_single_interpolation_stop(self):
        parts = slice_to_tref(
            t"<div>{0}</div>", start=None, stop=PartPosition(index=1, offset=0)
        )
        assert list(parts) == ["<div>"]

    def test_single_interpolation_start(self):
        parts = slice_to_tref(
            t"<div>{0}</div>", start=PartPosition(index=1, offset=0)
        )
        assert list(parts) == [0, "</div>"]

    def test_end_after_interpolation(self):
        parts = list(
            slice_to_tref(
                t"<div>{0}</div>", start=None, stop=PartPosition(index=2, offset=0)
            )
        )
        assert parts == ["<div>", 0]

    def test_newlines(self):
        parts = list(
            slice_to_tref(
                t"<div>\n{0}</div>", start=None, stop=PartPosition(index=0, offset=5)
            )
        )
        assert parts == ["<div>"]
        parts = list(
            slice_to_tref(
                t"<div>\n{0}</div>", start=None, stop=PartPosition(index=0, offset=6)
            )
        )
        assert parts == ["<div>\n"]
        parts = list(
            slice_to_tref(
                t"<div>\n{0}</div>", start=None, stop=PartPosition(index=0, offset=7)
            )
        )
        assert parts == ["<div>\n"]
        parts = list(
            slice_to_tref(t"<div>\n{0}</div>", start=PartPosition(index=0, offset=7))
        )
        assert parts == [0, "</div>"]

    def test_start_stop_just_interpolation(self):
        parts = list(
            TemplateRef.from_naive_template(t"<div>{0}={1}</div>").slice(
                start=PartPosition(index=1, offset=0),
                stop=PartPosition(index=2, offset=0),
            )
        )
        assert parts == [0]

    def test_start_stop_just_string(self):
        parts = list(
            TemplateRef.from_naive_template(t"<div>{0}={1}</div>").slice(
                start=PartPosition(index=2, offset=0),
                stop=PartPosition(index=3, offset=0),
            )
        )
        assert parts == ["="]

    def test_start_stop_substring(self):
        parts = list(
            TemplateRef.from_naive_template(t"<div>{0}={1}</div>").slice(
                start=PartPosition(index=0, offset=1),
                stop=PartPosition(index=0, offset=4),
            )
        )
        assert parts == ["div"]
