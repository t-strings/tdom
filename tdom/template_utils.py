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


@dataclass(slots=True, frozen=True)
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


def validate_part_position(part_pos: PartPosition) -> None:
    """
    Basic part position validation for parts that are converted to template
    source `LinePosition`.

    @TODO: This might move into the constructor eventually depending on usage.
    """
    if part_pos.index % 2 != 0 and part_pos.offset != 0:
        # You can only land on the start of an interpolation
        raise ValueError(
            "Invalid part position, interpolations are not divisible, offset must be 0."
        )
    if not (part_pos.offset >= 0):
        raise ValueError("Offset must always be positive or zero.")
    if not (part_pos.index >= 0):
        raise ValueError("Index must always be positive or zero.")
