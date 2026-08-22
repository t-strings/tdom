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


@dataclass(slots=True, frozen=True)
class TemplateRef:
    """Reference to a contiguous range within an original template."""

    strings: tuple[str, ...]
    """Static string parts of the original string.templatelib.Template"""

    i_start: int = 0
    """Index of the first interpolation in the original template."""

    @property
    def i_count(self) -> int:
        """Number of interpolations referenced by this template."""
        return len(self.strings) - 1

    @property
    def i_stop(self) -> int:
        """Exclusive stop index of the interpolations in the original template."""
        return self.i_start + self.i_count

    @property
    def is_literal(self) -> bool:
        """Return True if there are no interpolations."""
        return self.i_count == 0

    @property
    def is_empty(self) -> bool:
        """Return True if the template is empty."""
        return self.is_literal and self.strings[0] == ""

    @property
    def is_singleton(self) -> bool:
        """Return True if there is exactly one interpolation and no other content."""
        return self.strings == ("", "")

    @classmethod
    def literal(cls, s: str) -> t.Self:
        return cls((s,))

    @classmethod
    def empty(cls) -> t.Self:
        return cls.literal("")

    @classmethod
    def singleton(cls, i_index: int) -> t.Self:
        return cls(("", ""), i_index)

    def __post_init__(self):
        if not self.strings:
            raise ValueError("TemplateRef must have at least one string.")
        if self.is_literal and self.i_start != 0:
            raise ValueError("Literal TemplateRef instances must have i_start 0.")

    def __iter__(self):
        index = 0
        last_s_index = len(self.strings) - 1
        while index <= last_s_index:
            s = self.strings[index]
            if s:
                yield s
            if index < last_s_index:
                yield self.i_start + index
            index += 1

    def concat(self, other: TemplateRef) -> TemplateRef:
        """Join two adjacent template references."""
        if (
            not self.is_literal
            and not other.is_literal
            and self.i_stop != other.i_start
        ):
            raise ValueError("TemplateRef interpolation ranges must be contiguous.")

        return TemplateRef(
            strings=(
                *self.strings[:-1],
                self.strings[-1] + other.strings[0],
                *other.strings[1:],
            ),
            i_start=other.i_start if self.is_literal else self.i_start,
        )

    def resolve(self, interpolations: tuple[Interpolation, ...]) -> Template:
        """Use the given interpolations to resolve this reference template into a Template."""
        resolved = [
            interpolations[i_index] for i_index in range(self.i_start, self.i_stop)
        ]
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

        # Apply the stop first because both positions may be in the same string.
        if last % 2 == 0:
            strings[-1] = strings[-1][:limit]

        if first % 2 == 0:
            strings[0] = strings[0][offset:]
        else:
            strings[0] = ""

        return TemplateRef(
            strings=tuple(strings),
            i_start=self.i_start + first_string if len(strings) > 1 else 0,
        )


def slice_to_tref(
    template: Template,
    start: PartPosition | None = None,
    stop: PartPosition | None = None,
) -> TemplateRef:
    """
    Slice a template ref from a template based on the given start and stop.
    """
    tref = TemplateRef(strings=template.strings)
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
