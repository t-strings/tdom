from string.templatelib import Interpolation, Template

import pytest

from .template_utils import (
    PartPosition,
    TemplateRef,
    combine_template_refs,
    slice_to_tref,
    template_from_parts,
)


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


class TestSliceToTRef:
    @pytest.mark.parametrize(
        ("t", "start", "stop", "result"),
        (
            (t"<div></div>", None, PartPosition(0, offset=5), ("<div>",)),
            (t"<div></div>", PartPosition(0, offset=5), None, ("</div>",)),
            (
                t"<div></div>",
                PartPosition(0, offset=4),
                PartPosition(0, offset=6),
                ("><",),
            ),
            (t"<div></div>", PartPosition(0, offset=5), PartPosition(0, offset=5), ()),
            (t"<div>{0}</div>", None, PartPosition(1, offset=0), ("<div>",)),
            (t"<div>{0}</div>", PartPosition(1, offset=0), None, (0, "</div>")),
            (t"<div>{0}</div>", PartPosition(2, offset=0), None, ("</div>",)),
            (t"<div>{0}</div>", None, PartPosition(2, offset=0), ("<div>", 0)),
            (
                t"<div>{0}</div>",
                PartPosition(1, offset=0),
                PartPosition(2, offset=0),
                (0,),
            ),
            (
                t"<div>{0}</div>",
                PartPosition(1, offset=0),
                PartPosition(1, offset=0),
                (),
            ),
            (t"", None, PartPosition(0, offset=0), ()),
            (t"", PartPosition(0, offset=0), None, ()),
            (t"", None, None, ()),
            (t"{0}", None, PartPosition(2, offset=0), (0,)),
            (t"{0}", PartPosition(0, offset=0), None, (0,)),
            (t"{0}", None, None, (0,)),
        ),
    )
    def test_interval(
        self,
        t: Template,
        start: PartPosition | None,
        stop: PartPosition | None,
        result: tuple[str | int, ...],
    ) -> None:
        parts = tuple(slice_to_tref(t, start=start, stop=stop))
        assert parts == result

    def test_bad_interpolation_target(self) -> None:
        with pytest.raises(
            AssertionError,
            match="Interpolation part positions must always have offset 0",
        ):
            _ = slice_to_tref(
                t"<div>{0}</div>",
                start=None,
                stop=PartPosition(1, 20),
            )


class TestTemplateRefSlice:
    def test_shifted_indexes(self):
        # We start with the normal template where the interpolation values
        # match their corresponding (non-unified) index: 0->0, 1->1, etc.
        # Then use slice_to_tref to setup TemplateRef with shifted indexes.
        tref = slice_to_tref(
            t"<div>{0}<span>{1}</span>{2}</div>", PartPosition(2, 0), None
        )
        # After slicing from <span> the i_indexes are now shifted, ie. 0->1, 1->2
        assert tref.i_indexes == (1, 2), "0 should be removed, "
        # @NOTE: These parts are now relative to the new slice.
        # The unified index 3 is the interpolation with value == 2.
        sliced_from_interpolation = tref.slice(start=PartPosition(3, 0))
        assert sliced_from_interpolation.i_indexes == (2,), "only 2 should remain"
        assert tuple(sliced_from_interpolation) == (2, "</div>")
        # @NOTE: Again, this position is relative.
        # The unified index 2 is the string "</span>".
        sliced_from_str = tref.slice(start=PartPosition(2, 0))
        assert sliced_from_str.i_indexes == (2,), "only 2 should remain"
        assert tuple(sliced_from_str) == ("</span>", 2, "</div>")
