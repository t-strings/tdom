import typing as t
from dataclasses import dataclass
from string.templatelib import Interpolation, Template


def template_from_parts(
    strings: t.Sequence[str], interpolations: t.Sequence[Interpolation]
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
            i_indexes=tuple([int(ip.value) for ip in t.interpolations]),
        )

    def __post_init__(self):
        if len(self.strings) != len(self.i_indexes) + 1:
            raise ValueError(
                "TemplateRef must have one more string than interpolation indexes."
            )
