import typing as t
from collections.abc import Sequence
from dataclasses import dataclass
from string.templatelib import Interpolation, Template


def template_from_parts(
    strings: Sequence[str], interpolations: Sequence[Interpolation]
) -> Template:
    """Construct a template string from the given strings and parts."""
    assert len(strings) == len(interpolations) + 1, (
        "A template must have one more string than interpolations."
    )
    flat = [x for pair in zip(strings, interpolations) for x in pair] + [strings[-1]]
    return Template(*flat)


@dataclass(slots=True, frozen=True)
class TemplateRef:
    """Template strings whose interpolations are supplied by another template."""

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

    def __post_init__(self) -> None:
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

    def bind(self, source: Template) -> Template:
        """Bind interpolation objects from a structurally compatible template."""
        return template_from_parts(
            self.strings, source.interpolations[self.i_start : self.i_stop]
        )


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

    @property
    def is_string(self) -> bool:
        """Return True if this position is within a string part."""
        return self.index % 2 == 0

    @property
    def is_interpolation(self) -> bool:
        """Return True if this position is at an interpolation part."""
        return not self.is_string

    def __post_init__(self) -> None:
        """Validate invariants shared by every template part position."""
        if self.index < 0:
            raise ValueError("Index must always be positive or zero.")
        if self.offset < 0:
            raise ValueError("Offset must always be positive or zero.")
        if self.is_interpolation and self.offset != 0:
            # Interpolations are indivisible, so their only position is the start.
            raise ValueError("Interpolation part positions must always have offset 0.")

    def validate(self, source: Template) -> None:
        """Raise if this position falls outside the source template."""
        part_count = 2 * len(source.strings) - 1
        if self.index >= part_count:
            raise ValueError(
                "PartPosition index falls outside the template: "
                f"{self.index} >= {part_count}."
            )
        if self.is_string:
            string = source.strings[self.index // 2]
            if self.offset > len(string):
                raise ValueError(
                    "PartPosition offset falls outside its string: "
                    f"{self.offset} > {len(string)}."
                )


@dataclass(slots=True, frozen=True)
class TemplateSpan:
    """A half-open span in the global part coordinates of a template."""

    start: PartPosition
    stop: PartPosition

    def __post_init__(self) -> None:
        if self.start > self.stop:
            raise ValueError("TemplateSpan start must not be after stop.")

    def extract(self, source: Template) -> Template:
        """Extract this span from a structurally compatible template."""
        self.start.validate(source)
        self.stop.validate(source)

        first_string = self.start.index // 2
        last_string = self.stop.index // 2
        strings = list(source.strings[first_string : last_string + 1])

        if self.stop.is_string:
            strings[-1] = strings[-1][: self.stop.offset]

        if self.start.is_string:
            strings[0] = strings[0][self.start.offset :]
        else:
            strings[0] = ""

        return template_from_parts(
            strings, source.interpolations[first_string:last_string]
        )
