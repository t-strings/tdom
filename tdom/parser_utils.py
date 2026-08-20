from bisect import bisect_left
from dataclasses import dataclass
from itertools import accumulate
from string.templatelib import Template

from .placeholders import PlaceholderConfig
from .source import LinePosition
from .template_utils import PartPosition, validate_part_position

type HTMLAttribute = tuple[str, str | None]
type AbsolutePosition = int
"""Absolute position in the placeholder-expanded template source, starting at 0."""


def precompute_line_start_positions(source_text: str) -> tuple[AbsolutePosition, ...]:
    """
    Return the absolute positions where each line in the parser input starts.

    The first line always starts at zero. A trailing newline therefore produces
    one final line start whose absolute position is also the length of the input.
    """
    return (0, *(index + 1 for index, char in enumerate(source_text) if char == "\n"))


def make_parser_pos_translator(
    template: Template, config: PlaceholderConfig
) -> ParserPositionTranslator:
    """
    Configure and return a `ParserPositionTranslator`.

    We precompute a few things to make the translator's job easier.
    """

    source_text_parts = tuple(
        template.strings[index // 2]
        if index % 2 == 0
        else config.make_placeholder((index - 1) // 2)
        for index in range(2 * len(template.strings) - 1)
    )
    source_text = "".join(source_text_parts)

    return ParserPositionTranslator(
        line_start_positions=precompute_line_start_positions(source_text),
        part_end_positions=tuple(accumulate(map(len, source_text_parts))),
    )


@dataclass(frozen=True, slots=True)
class ParserPositionTranslator:
    line_start_positions: tuple[AbsolutePosition, ...]
    """Absolute positions where lines in the parser input start."""

    part_end_positions: tuple[AbsolutePosition, ...]
    """Absolute positions where placeholder-expanded template parts end."""

    def line_pos_to_abs_pos(
        self,
        line_pos: LinePosition,
    ) -> AbsolutePosition:
        """
        Validate and normalize a parser line position to an absolute position.

        An offset equal to a non-final line's length points at its newline. An
        offset equal to the final line's length points at EOF.
        """
        line = line_pos.line
        offset = line_pos.offset
        line_count = len(self.line_start_positions)
        if line > line_count:
            raise ValueError("Line does not exist in source.")
        elif line <= 0:
            raise ValueError("Unreachable line number, must be > 0.")
        if offset < 0:
            raise ValueError("Unreachable offset, must be >= 0.")

        line_start = self.line_start_positions[line - 1]
        line_end = (
            self.line_start_positions[line] - 1
            if line < line_count
            else self.part_end_positions[-1]
        )
        line_length = line_end - line_start
        if offset > line_length:
            raise ValueError(
                f"Offset exceeds reachable characters of line: {line}: {offset} > {line_length}"
            )
        return line_start + offset

    def abs_pos_to_part_pos(self, abs_pos: AbsolutePosition) -> PartPosition:
        """
        Translate an absolute position into a template part position.

        A position exactly between parts belongs to the following part. EOF is the
        exception: a template always ends with a string part, and EOF belongs to the
        end of that final string.
        """
        source_length = self.part_end_positions[-1]
        if not 0 <= abs_pos <= source_length:
            raise ValueError(
                f"Absolute position falls outside the input: {abs_pos} not in [0, {source_length}]"
            )

        last_index = len(self.part_end_positions) - 1
        if abs_pos == source_length:
            final_part_start = (
                self.part_end_positions[last_index - 1] if last_index else 0
            )
            return PartPosition(last_index, source_length - final_part_start)

        index = bisect_left(self.part_end_positions, abs_pos)
        part_start = self.part_end_positions[index - 1] if index else 0
        if abs_pos == self.part_end_positions[index]:
            return PartPosition(index + 1, 0)
        return PartPosition(index, abs_pos - part_start)

    def translate(self, parser_pos: LinePosition) -> PartPosition:
        """
        Translate a parser line position to a template part position.

        parser_pos:
            A line position in a coordinate system that consists of the entire
            template merged into a continuous string with placeholder strings
            injected for `Interpolation`s.

        return:
            A position in a coordinate system that uses a unified index into
            the parts of the `Template`.  For interpolations the offset must be
            `0` but the offset can be a non-zero number for string parts.
        """
        abs_pos = self.line_pos_to_abs_pos(parser_pos)
        part_pos = self.abs_pos_to_part_pos(abs_pos)
        validate_part_position(part_pos)
        return part_pos
