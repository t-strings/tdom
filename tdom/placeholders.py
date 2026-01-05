from dataclasses import dataclass, field
import random
import re
import string

from .template_utils import TemplateRef


def make_placeholder_config() -> PlaceholderConfig:
    prefix = f"t🐍{''.join(random.choices(string.ascii_lowercase, k=2))}-"
    suffix = f"-{''.join(random.choices(string.ascii_lowercase, k=2))}🐍t"
    return PlaceholderConfig(
        prefix=prefix,
        suffix=suffix,
        pattern=re.compile(re.escape(prefix) + r"(\d+)" + re.escape(suffix)),
    )


@dataclass(frozen=True)
class PlaceholderConfig:
    """String operations for working with a placeholder pattern."""

    prefix: str
    suffix: str
    pattern: re.Pattern

    def make_placeholder(self, i: int) -> str:
        """Generate a placeholder for the i-th interpolation."""
        return f"{self.prefix}{i}{self.suffix}"

    def match_placeholders(self, s: str) -> list[re.Match[str]]:
        """Find all placeholders in a string."""
        return list(self.pattern.finditer(s))

    def find_placeholders(self, s: str) -> TemplateRef:
        """
        Find all placeholders in a string and return a TemplateRef.

        If no placeholders are found, returns a static TemplateRef.
        """
        matches = self.match_placeholders(s)
        if not matches:
            return TemplateRef.literal(s)

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


@dataclass
class PlaceholderState:
    known: set[int] = field(default_factory=set)
    config: PlaceholderConfig = field(default_factory=make_placeholder_config)
    """Collection of currently 'known and active' placeholder indexes."""

    @property
    def is_empty(self) -> bool:
        return len(self.known) == 0

    def add_placeholder(self, index: int) -> str:
        placeholder = self.config.make_placeholder(index)
        self.known.add(index)
        return placeholder

    def remove_placeholders(self, text: str) -> TemplateRef:
        """
        Find all known placeholders in the text and return their indices.

        If unknown placeholders are found, raises ValueError.

        If no placeholders are found, returns a static PlaceholderRef.
        """
        pt = self.config.find_placeholders(text)
        for index in pt.i_indexes:
            if index not in self.known:
                raise ValueError(f"Unknown placeholder index {index} found in text.")
            self.known.remove(index)
        return pt
