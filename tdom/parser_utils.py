import typing as t
from bisect import bisect_left
from dataclasses import dataclass
from string.templatelib import Template

from .placeholders import PlaceholderConfig
from .source import LinePosition
from .template_utils import PartPosition, TemplateSpan

type HTMLAttribute = tuple[str, str | None]
type AbsolutePosition = int
"""Absolute position in the placeholder-expanded template source, starting at 0."""


def make_parser_pos_translator(
    template: Template, config: PlaceholderConfig
) -> ParserPositionTranslator:
    """
    Configure and return a `ParserPositionTranslator`.

    Precompute line and string positions to make translation efficient.
    """

    line_start_positions: list[AbsolutePosition] = [0]
    string_start_positions: list[AbsolutePosition] = []
    string_end_positions: list[AbsolutePosition] = []
    source_pos: AbsolutePosition = 0

    def line_starts(string: str) -> t.Iterator[AbsolutePosition]:
        return (
            source_pos + offset + 1
            for offset, char in enumerate(string)
            if char == "\n"
        )

    for s_index, string in enumerate(template.strings):
        string_start_positions.append(source_pos)
        line_start_positions.extend(line_starts(string))
        source_pos += len(string)
        string_end_positions.append(source_pos)

        if s_index < len(template.interpolations):
            placeholder = config.make_placeholder(s_index)
            line_start_positions.extend(line_starts(placeholder))
            source_pos += len(placeholder)

    return ParserPositionTranslator(
        line_start_positions=tuple(line_start_positions),
        string_start_positions=tuple(string_start_positions),
        string_end_positions=tuple(string_end_positions),
    )


@dataclass(frozen=True, slots=True)
class ParserPositionTranslator:
    line_start_positions: tuple[AbsolutePosition, ...]
    """Absolute positions where lines in the parser input start."""

    string_start_positions: tuple[AbsolutePosition, ...]
    """Absolute positions where static strings start in the parser input."""

    string_end_positions: tuple[AbsolutePosition, ...]
    """Absolute positions where static strings end in the parser input."""

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
            else self.string_end_positions[-1]
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
        source_length = self.string_end_positions[-1]
        if not 0 <= abs_pos <= source_length:
            raise ValueError(
                f"Absolute position falls outside the input: {abs_pos} not in [0, {source_length}]"
            )

        s_index = bisect_left(self.string_end_positions, abs_pos)
        string_start = self.string_start_positions[s_index]
        if abs_pos < string_start:
            raise ValueError(
                "Positions inside interpolation placeholders are undefined."
            )
        return PartPosition(s_index, abs_pos - string_start)

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
