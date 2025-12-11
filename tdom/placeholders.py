import random
import re
import string
import typing as t
from dataclasses import dataclass

_PLACEHOLDER_PREFIX = f"t🐍{''.join(random.choices(string.ascii_lowercase, k=2))}-"
_PLACEHOLDER_SUFFIX = f"-{''.join(random.choices(string.ascii_lowercase, k=2))}🐍t"
_PLACEHOLDER_PATTERN = re.compile(
    re.escape(_PLACEHOLDER_PREFIX) + r"(\d+)" + re.escape(_PLACEHOLDER_SUFFIX)
)


def make_placeholder(i: int) -> str:
    """Generate a placeholder for the i-th interpolation."""
    return f"{_PLACEHOLDER_PREFIX}{i}{_PLACEHOLDER_SUFFIX}"


def match_placeholders(s: str) -> list[re.Match[str]]:
    """Find all placeholders in a string."""
    return list(_PLACEHOLDER_PATTERN.finditer(s))


def find_placeholders(s: str) -> TemplateRef:
    """
    Find all placeholders in a string and return a TemplateRef.

    If no placeholders are found, returns a static TemplateRef.
    """
    matches = match_placeholders(s)
    if not matches:
        return TemplateRef.static(s)

    strings: list[str] = []
    i_indexes: list[int] = []
    last_index = 0
    for match in matches:
        start, end = match.span()
        strings.append(s[last_index:start])
        i_indexes.append(int(match[1]))
        last_index = end
    strings.append(s[last_index:])

    return TemplateRef(tuple(strings), tuple(i_indexes))


# XXX consider where this belongs in practice; it is now placeholder-independent
@dataclass(slots=True, frozen=True)
class TemplateRef:
    """Reference to a template with indexes for its original interpolations."""

    strings: tuple[str, ...]
    """Static string parts of the original string.templatelib.Template"""

    i_indexes: tuple[int, ...]
    """Indexes of the interpolations in the original string.templatelib.Template"""

    @property
    def is_static(self) -> bool:
        """Return True if there are no interpolations."""
        return not self.i_indexes

    @property
    def is_empty(self) -> bool:
        """Return True if the template is empty."""
        return self.is_static and self.strings[0] == ""

    @property
    def is_singleton(self) -> bool:
        """Return True if there is exactly one interpolation and no other content."""
        return self.strings == ("", "")

    @classmethod
    def static(cls, s: str) -> t.Self:
        return cls((s,), ())

    @classmethod
    def empty(cls) -> t.Self:
        return cls.static("")

    @classmethod
    def singleton(cls, i_index: int) -> t.Self:
        return cls(("", ""), (i_index,))

    def __post_init__(self):
        if len(self.strings) != len(self.i_indexes) + 1:
            raise ValueError(
                "PlaceholderRef must have one more string than interpolation indexes."
            )


class PlaceholderState:
    known: set[int]
    """Collection of currently 'known and active' placeholder indexes."""

    def __init__(self):
        self.known = set()

    @property
    def is_empty(self) -> bool:
        return len(self.known) == 0

    def add_placeholder(self, index: int) -> str:
        placeholder = make_placeholder(index)
        self.known.add(index)
        return placeholder

    def remove_placeholders(self, text: str) -> TemplateRef:
        """
        Find all known placeholders in the text and return their indices.

        If unknown placeholders are found, raises ValueError.

        If no placeholders are found, returns a static PlaceholderRef.
        """
        pt = find_placeholders(text)
        for index in pt.i_indexes:
            if index not in self.known:
                raise ValueError(f"Unknown placeholder index {index} found in text.")
            self.known.remove(index)
        return pt
