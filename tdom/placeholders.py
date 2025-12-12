from dataclasses import dataclass
import re
import random
import string
from string.templatelib import Interpolation, Template
import typing as t


FRAGMENT_TAG = f"t🐍f-{''.join(random.choices(string.ascii_lowercase, k=4))}-"

_PLACEHOLDER_PREFIX = f"t🐍{''.join(random.choices(string.ascii_lowercase, k=2))}-"
_PLACEHOLDER_SUFFIX = f"-{''.join(random.choices(string.ascii_lowercase, k=2))}🐍t"
_PLACEHOLDER_PATTERN = re.compile(
    re.escape(_PLACEHOLDER_PREFIX) + r"(\d+)" + re.escape(_PLACEHOLDER_SUFFIX)
)


def placeholder(i: int) -> str:
    """Generate a placeholder for the i-th interpolation."""
    return f"{_PLACEHOLDER_PREFIX}{i}{_PLACEHOLDER_SUFFIX}"


@dataclass(frozen=True, slots=True)
class _PlaceholderMatch:
    start: int
    end: int
    index: int | None


def find_placeholder(s: str) -> int | None:
    """
    If the string is exactly one placeholder, return its index. Otherwise, None.
    """
    match = _PLACEHOLDER_PATTERN.fullmatch(s)
    return int(match.group(1)) if match else None


def _find_all_placeholders(s: str) -> t.Iterable[_PlaceholderMatch]:
    """
    Find all placeholders in a string, returning their positions and indices.

    If there is non-placeholder text in the string, its position is also
    returned with index None.
    """
    matches = list(_PLACEHOLDER_PATTERN.finditer(s))
    last_end = 0
    for match in matches:
        if match.start() > last_end:
            yield _PlaceholderMatch(last_end, match.start(), None)
        index = int(match.group(1))
        yield _PlaceholderMatch(match.start(), match.end(), index)
        last_end = match.end()
    if last_end < len(s):
        yield _PlaceholderMatch(last_end, len(s), None)


def placeholders_to_template(text: str, format_spec: str) -> tuple[Template, list[str]]:
    """
    Replace placeholders in text with interpolations to make template.

    Return the template and a list of placeholders in the order they were found.
    """
    placeholders: list[str] = []
    parts: list[str | Interpolation] = []
    for match_info in _find_all_placeholders(text):
        match_str = text[match_info.start : match_info.end]
        if match_info.index is not None:
            placeholders.append(match_str)
            parts.append(Interpolation(match_info.index, "", None, format_spec))
        else:
            parts.append(match_str)
    return Template(*parts), placeholders
