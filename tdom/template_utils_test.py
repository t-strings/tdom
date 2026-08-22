from string.templatelib import Interpolation, Template

import pytest

from .template_utils import (
    PartPosition,
    TemplateRef,
    TemplateSpan,
    template_from_parts,
)


def test_template_from_parts() -> None:
    strings = ("Hello, ", "! Today is ", ".")
    interpolations = (Interpolation("Alice"), Interpolation("Monday"))
    template = template_from_parts(strings, interpolations)
    assert template.strings == strings
    assert template.interpolations == interpolations


def test_template_ref_is_literal() -> None:
    literal = TemplateRef.literal("Hello")
    assert literal.is_literal

    non_literal = TemplateRef(("", ""))
    assert not non_literal.is_literal


def test_template_ref_is_empty() -> None:
    empty = TemplateRef.empty()
    assert empty.is_empty

    non_empty = TemplateRef.literal("Hello")
    assert not non_empty.is_empty


def test_template_ref_is_singleton() -> None:
    singleton = TemplateRef.singleton(0)
    assert singleton.is_singleton

    non_singleton = TemplateRef.literal("Hello")
    assert not non_singleton.is_singleton


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
    refs = (
        TemplateRef.literal("ab"),
        TemplateRef(("c", "d")),
        TemplateRef(("ef", ""), i_start=1),
        TemplateRef(("", "ghi"), i_start=2),
    )
    combined = refs[0]
    for ref in refs[1:]:
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


def test_template_ref_bind():
    src_t = t"{'a'}b{'c'}d{'e'}f"
    ref = TemplateRef(strings=("before ", " after"), i_start=1)
    bound = ref.bind(src_t)
    assert bound.values == ("c",)
    assert bound.strings == ref.strings


class TestPartPosition:
    @pytest.mark.parametrize(
        ("position", "is_string", "is_interpolation"),
        (
            (PartPosition(0), True, False),
            (PartPosition(1), False, True),
            (PartPosition(2), True, False),
        ),
    )
    def test_part_type(
        self,
        position: PartPosition,
        is_string: bool,
        is_interpolation: bool,
    ) -> None:
        assert position.is_string is is_string
        assert position.is_interpolation is is_interpolation

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


class TestTemplateSpan:
    @pytest.mark.parametrize(
        ("start", "stop"),
        (
            (PartPosition(2), PartPosition(0)),
            (PartPosition(0, 2), PartPosition(0, 1)),
        ),
    )
    def test_reversed_range(self, start: PartPosition, stop: PartPosition) -> None:
        with pytest.raises(ValueError, match="start must not be after stop"):
            _ = TemplateSpan(start=start, stop=stop)

    @pytest.mark.parametrize(
        "span",
        (
            TemplateSpan(PartPosition(3), PartPosition(3)),
            TemplateSpan(PartPosition(0), PartPosition(3)),
        ),
    )
    def test_position_outside_template(self, span: TemplateSpan) -> None:
        with pytest.raises(ValueError, match="PartPosition index"):
            _ = span.extract(t"ABC")

    def test_offset_outside_template_string(self) -> None:
        span = TemplateSpan(PartPosition(0, 4), PartPosition(0, 4))

        with pytest.raises(ValueError, match="PartPosition offset"):
            _ = span.extract(t"ABC")

    def test_retains_original_interpolation_objects(self) -> None:
        source = t"before {object()} after"
        span = TemplateSpan(PartPosition(0, 7), PartPosition(2, 0))

        extracted = span.extract(source)

        assert extracted.strings == ("", "")
        assert extracted.interpolations[0] is source.interpolations[0]


class TestTemplateSpanExtract:
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
        span = TemplateSpan(
            start=start or PartPosition(0),
            stop=stop or PartPosition(2 * len(t.strings) - 2, len(t.strings[-1])),
        )
        extracted = span.extract(t)
        parts: list[str | object] = []
        for index, string in enumerate(extracted.strings):
            if string:
                parts.append(string)
            if index < len(extracted.values):
                parts.append(extracted.values[index])
        assert tuple(parts) == result

    def test_interpolation_interval(self) -> None:
        extracted = TemplateSpan(
            start=PartPosition(1),
            stop=PartPosition(2),
        ).extract(t"<div>{0}</div>")

        assert extracted.strings == ("", "")
        assert extracted.values == (0,)
