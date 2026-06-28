import typing as t
from collections.abc import Sequence
from dataclasses import dataclass
from string.templatelib import Interpolation, Template


def template_from_parts(
    strings: Sequence[str], interpolations: Sequence[Interpolation]
) -> Template:
    """Construct a template string from the given strings and parts."""
    assert len(strings) == len(interpolations) + 1, (
        "TemplateRef must have one more string than interpolation references."
    )
    flat = [x for pair in zip(strings, interpolations) for x in pair] + [strings[-1]]
    return Template(*flat)


def combine_template_refs(*template_refs: TemplateRef) -> TemplateRef:
    return TemplateRef.from_naive_template(
        sum((tr.to_naive_template() for tr in template_refs), t"")
    )


@dataclass(slots=True, frozen=True)
class TemplateRef:
    """Reference to a template with indexes for its original interpolations."""

    strings: tuple[str, ...]
    """Static string parts of the original string.templatelib.Template"""

    i_indexes: tuple[int, ...]
    """Indexes of the interpolations in the original string.templatelib.Template"""

    @property
    def is_literal(self) -> bool:
        """Return True if there are no interpolations."""
        return not self.i_indexes

    @property
    def is_empty(self) -> bool:
        """Return True if the template is empty."""
        return self.is_literal and self.strings[0] == ""

    @property
    def is_singleton(self) -> bool:
        """Return True if there is exactly one interpolation and no other content."""
        return self.strings == ("", "")

    def to_naive_template(self) -> Template:
        return template_from_parts(
            self.strings, [Interpolation(i, "", None, "") for i in self.i_indexes]
        )

    @classmethod
    def literal(cls, s: str) -> t.Self:
        return cls((s,), ())

    @classmethod
    def empty(cls) -> t.Self:
        return cls.literal("")

    @classmethod
    def singleton(cls, i_index: int) -> t.Self:
        return cls(("", ""), (i_index,))

    @classmethod
    def from_naive_template(cls, t: Template) -> TemplateRef:
        return cls(
            strings=t.strings,
            i_indexes=tuple(int(ip.value) for ip in t.interpolations),
        )

    def __post_init__(self):
        if len(self.strings) != len(self.i_indexes) + 1:
            raise ValueError(
                "TemplateRef must have one more string than interpolation indexes."
            )

    def __iter__(self):
        index = 0
        last_s_index = len(self.strings) - 1
        while index <= last_s_index:
            s = self.strings[index]
            if s:
                yield s
            if index < last_s_index:
                yield self.i_indexes[index]
            index += 1

    def resolve(self, interpolations: tuple[Interpolation, ...]) -> Template:
        """Use the given interpolations to resolve this reference template into a Template."""
        resolved = [interpolations[i_index] for i_index in self.i_indexes]
        return template_from_parts(self.strings, resolved)


def slice_from_template(
    template: Template, tslice: TemplateSlice
) -> t.Generator[Interpolation | str]:
    """
    Yield the template parts that make up the requested slice.
    """
    if tslice.start is None:
        first = 0
    else:
        first = tslice.start
        assert first >= 0 and first < len(template.strings)
    if tslice.start_offset is None:
        offset = None
    else:
        offset = tslice.start_offset
    if tslice.stop is None:
        last = len(template.strings) - 1
    else:
        last = tslice.stop - 1
        assert last >= 0 and last < len(template.strings)
    if tslice.stop_limit is None:
        limit = None
    else:
        limit = tslice.stop_limit

    if first == last:
        yield template.strings[first][offset:limit]
        return
    else:
        yield template.strings[first][offset:]
        yield template.interpolations[first]

    for index in range(first + 1, last + 1):
        if index == last:
            yield template.strings[last][:limit]
        else:
            yield template.strings[index]
            yield template.interpolations[index]


@dataclass(frozen=True, slots=True)
class TemplateSlice:
    """
    strings[start][start_offset:]
    ...
    strings[stop][:stop_limit]

    @NOTE: Start offset could be len(string[start]) and likewise stop_limit could be 0.
    """

    start: int | None = None
    start_offset: int | None = None
    stop: int | None = None
    stop_limit: int | None = None
