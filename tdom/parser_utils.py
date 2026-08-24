from bisect import bisect_left
from dataclasses import dataclass
from itertools import accumulate
from string.templatelib import Template

from .placeholders import PlaceholderConfig
from .source import LinePosition
from .template_utils import PartPosition, TemplateSpan

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

        Positions at a placeholder's start and end are represented by the end of
        its preceding string and the start of its following string, respectively.
        Positions inside placeholders cannot be translated because interpolations
        are atomic.
        """
        source_length = self.part_end_positions[-1]
        if not 0 <= abs_pos <= source_length:
            raise ValueError(
                f"Absolute position falls outside the input: {abs_pos} not in [0, {source_length}]"
            )

        last_part_index = len(self.part_end_positions) - 1
        if abs_pos == source_length:
            final_part_start = (
                self.part_end_positions[last_part_index - 1] if last_part_index else 0
            )
            return PartPosition(last_part_index // 2, source_length - final_part_start)

        part_index = bisect_left(self.part_end_positions, abs_pos)
        part_start = self.part_end_positions[part_index - 1] if part_index else 0

        if part_index % 2 == 0:
            return PartPosition(part_index // 2, abs_pos - part_start)
        if abs_pos == self.part_end_positions[part_index]:
            return PartPosition(part_index // 2 + 1, 0)
        raise ValueError("Positions inside interpolation placeholders are undefined.")

    def translate(self, parser_pos: LinePosition) -> PartPosition:
        """
        Translate a parser line position to a template part position.

        parser_pos:
            A line position in a coordinate system that consists of the entire
            template merged into a continuous string with placeholder strings
            injected for `Interpolation`s.

        return:
            A position relative to one of the `Template`'s static strings.
        """
        abs_pos = self.line_pos_to_abs_pos(parser_pos)
        return self.abs_pos_to_part_pos(abs_pos)

    def translate_span(
        self,
        parser_start: LinePosition,
        parser_length: int,
    ) -> TemplateSpan:
        """
        Translate a half-open span from parser input to template part coordinates.

        `parser_length` is measured in the placeholder-expanded parser input.
        """
        if parser_length < 0:
            raise ValueError("Parser span length must be positive or zero.")

        absolute_start = self.line_pos_to_abs_pos(parser_start)
        return TemplateSpan(
            start=self.abs_pos_to_part_pos(absolute_start),
            stop=self.abs_pos_to_part_pos(absolute_start + parser_length),
        )
