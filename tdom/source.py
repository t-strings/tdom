from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class LinePosition:
    """An immutable position in a block of source code."""

    line: int = 1
    """Line of code, starts at 1."""
    offset: int = 0
    """Offset from the start of the line, starts at 0."""

    def advance_over(self, text: str) -> LinePosition:
        """Return the position reached after advancing over text."""
        line_count = text.count("\n")
        if line_count:
            return LinePosition(
                line=self.line + line_count,
                offset=len(text.rsplit("\n", 1)[-1]),
            )
        return LinePosition(line=self.line, offset=self.offset + len(text))
