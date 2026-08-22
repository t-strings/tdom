from string.templatelib import Interpolation, Template

import pytest

from .template_utils import (
    PartPosition,
    TemplateRef,
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

    non_literal_ref = TemplateRef(("", ""))
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


def test_template_ref_interpolation_range() -> None:
    ref = TemplateRef(("A", "B", "C"), i_start=3)

    assert ref.i_start == 3
    assert ref.i_count == 2
    assert ref.i_stop == 5


def test_template_ref_post_init_validation() -> None:
    with pytest.raises(ValueError, match="at least one string"):
        _ = TemplateRef(())

    with pytest.raises(ValueError, match="Literal TemplateRef"):
        _ = TemplateRef(("Hello",), i_start=1)


def test_template_ref_concat():
    template_refs = (
        TemplateRef.literal("ab"),
        TemplateRef(("c", "d")),
        TemplateRef(("ef", ""), i_start=1),
        TemplateRef(("", "ghi"), i_start=2),
    )
    combined = template_refs[0]
    for ref in template_refs[1:]:
        combined = combined.concat(ref)

    assert combined == TemplateRef(("abc", "def", "", "ghi"))


def test_template_ref_concat_literals():
    assert TemplateRef.literal("abc").concat(
        TemplateRef.literal("def")
    ) == TemplateRef.literal("abcdef")


def test_template_ref_concat_with_nonzero_start():
    combined = (
        TemplateRef.literal("a")
        .concat(TemplateRef(("b", "c"), i_start=3))
        .concat(TemplateRef.literal("d"))
        .concat(TemplateRef(("e", "f"), i_start=4))
    )

    assert combined == TemplateRef(("ab", "cde", "f"), i_start=3)


def test_template_ref_concat_rejects_discontiguous_ranges():
    with pytest.raises(ValueError, match="ranges must be contiguous"):
        _ = TemplateRef.singleton(1).concat(TemplateRef.singleton(3))


def test_template_ref_iter_singleton():
    assert list(TemplateRef.singleton(1)) == [1]


def test_template_ref_iter_empty():
    assert list(TemplateRef.empty()) == []


def test_template_ref_iter_empty_prefix():
    assert list(TemplateRef(("", "def"), i_start=1)) == [1, "def"]


def test_template_ref_iter_empty_suffix():
    assert list(TemplateRef(("abc", ""), i_start=1)) == ["abc", 1]


def test_template_ref_iter_literal():
    assert list(TemplateRef.literal("abc")) == ["abc"]


def test_template_ref_iter_only_interpolations():
    assert list(TemplateRef(("", "", "", ""), i_start=1)) == [1, 2, 3]


def test_template_ref_iter_complete():
    assert list(TemplateRef(("abc", "def", "ghi", "jkl"), i_start=1)) == [
        "abc",
        1,
        "def",
        2,
        "ghi",
        3,
        "jkl",
    ]


def test_template_ref_resolve():
    src_t = t"{'a'}b{'c'}d{'e'}f"
    src_ref = TemplateRef(strings=src_t.strings)
    resolved_t = src_ref.resolve(src_t.interpolations)
    assert resolved_t.values == ("a", "c", "e")
    assert resolved_t.strings == ("", "b", "d", "f")


class TestPartPosition:
    @pytest.mark.parametrize(
        ("index", "offset", "message"),
        (
            (-1, 0, "Index must always be positive or zero"),
            (0, -1, "Offset must always be positive or zero"),
            (1, 1, "Interpolation part positions must always have offset 0"),
        ),
    )
    def test_invalid(self, index: int, offset: int, message: str) -> None:
        with pytest.raises(ValueError, match=message):
            _ = PartPosition(index, offset)

    @pytest.mark.parametrize(
        ("earlier", "later"),
        (
            (PartPosition(0), PartPosition(0, 1)),
            (PartPosition(0, 1), PartPosition(1)),
            (PartPosition(1), PartPosition(2)),
        ),
    )
    def test_ordering(self, earlier: PartPosition, later: PartPosition) -> None:
        assert earlier < later


class TestTemplateRefSlice:
    def test_preserves_interpolation_indexes(self) -> None:
        ref = TemplateRef(strings=("A", "B", "C"), i_start=3)

        assert ref.slice() == ref
        assert ref.slice(start=PartPosition(1), stop=PartPosition(2, 1)) == TemplateRef(
            strings=("", "B"), i_start=3
        )

    def test_literal_slice_normalizes_interpolation_start(self) -> None:
        ref = TemplateRef(strings=("A", "B"), i_start=3)

        assert ref.slice(start=PartPosition(2)) == TemplateRef.literal("B")

    @pytest.mark.parametrize(
        ("start", "stop"),
        (
            (PartPosition(2), PartPosition(0)),
            (PartPosition(0, 2), PartPosition(0, 1)),
        ),
    )
    def test_reversed_range(self, start: PartPosition, stop: PartPosition) -> None:
        with pytest.raises(
            ValueError, match="Start position must not be after stop position"
        ):
            _ = TemplateRef(strings=("ABC", "DEF"), i_start=3).slice(
                start=start, stop=stop
            )

    @pytest.mark.parametrize(
        ("start", "stop", "bound"),
        (
            (PartPosition(3), None, "Start"),
            (None, PartPosition(3), "Stop"),
        ),
    )
    def test_position_outside_template(
        self,
        start: PartPosition | None,
        stop: PartPosition | None,
        bound: str,
    ) -> None:
        with pytest.raises(ValueError, match=f"{bound} position index"):
            _ = TemplateRef.literal("ABC").slice(start=start, stop=stop)


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

    def test_interpolation_interval(self) -> None:
        assert slice_to_tref(
            t"<div>{0}</div>",
            start=PartPosition(1),
            stop=PartPosition(2),
        ) == TemplateRef(strings=("", ""))
