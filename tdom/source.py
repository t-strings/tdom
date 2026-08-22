from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class LinePosition:
    """A immutable position in a block of source code."""

    line: int = 1
    """Line of code, starts at 1."""
    offset: int = 0
    """Offset from the start of the line, starts at 0."""
