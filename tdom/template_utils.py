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

    def slice(
        self,
        start: PartPosition | None = None,
        stop: PartPosition | None = None,
    ) -> TemplateRef:
        """Return the half-open interval from start (inclusive) to stop (exclusive)."""
        size = 2 * len(self.strings) - 1
        first = start.index if start else 0
        if first >= size:
            raise ValueError(
                f"Start position index falls outside the template: {first} >= {size}."
            )
        offset = start.offset if start else None
        last = stop.index if stop else size - 1
        if last >= size:
            raise ValueError(
                f"Stop position index falls outside the template: {last} >= {size}."
            )
        limit = stop.offset if stop else None
        if start is not None and stop is not None and start > stop:
            raise ValueError("Start position must not be after stop position.")

        first_string = first // 2
        last_string = last // 2
        strings = list(self.strings[first_string : last_string + 1])
        i_indexes = self.i_indexes[first_string:last_string]

        # Apply the stop first because both positions may be in the same string.
        if last % 2 == 0:
            strings[-1] = strings[-1][:limit]

        if first % 2 == 0:
            strings[0] = strings[0][offset:]
        else:
            strings[0] = ""

        return TemplateRef(strings=tuple(strings), i_indexes=i_indexes)


def slice_to_tref(
    template: Template,
    start: PartPosition | None = None,
    stop: PartPosition | None = None,
) -> TemplateRef:
    """
    Slice a template ref from a template based on the given start and stop.
    """
    tref = TemplateRef(
        strings=template.strings, i_indexes=tuple(range(len(template.strings) - 1))
    )
    return tref.slice(start=start, stop=stop)


@dataclass(slots=True, frozen=True, order=True)
class PartPosition:
    """
    A unified template part position.

    Translate indexes into strings by multiplying by 2.
    ie. 0->0, 1->2, 2->4, etc.
    Reverse by dividing by 2.

    Translate indexes into interpolations by multiplying by 2 and then adding 1.
    ie. 0->1, 1->3, 2->5, etc.
    Reverse by subtracting 1 and dividing by 2.

    Using unified indexes allows for simpler iteration as well as starting
    or stopping at either type of part more seamlessly.
    """

    index: int
    """Index of the template parts, translate for strings/interpolations."""

    offset: int = 0
    """Offset from the start of the template part."""

    def __post_init__(self) -> None:
        """Validate invariants shared by every template part position."""
        if self.index < 0:
            raise ValueError("Index must always be positive or zero.")
        if self.offset < 0:
            raise ValueError("Offset must always be positive or zero.")
        if self.index % 2 != 0 and self.offset != 0:
            # Interpolations are indivisible, so their only position is the start.
            raise ValueError("Interpolation part positions must always have offset 0.")
