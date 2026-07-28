from dataclasses import dataclass
from string.templatelib import Template

from .placeholders import PlaceholderConfig
from .source import LinePosition, MutableLinePosition
from .template_utils import PartPosition, validate_part_position

type HTMLAttribute = tuple[str, str | None]


@dataclass(frozen=True)
class ParserPosition:
    """
    A parser position returned by the template parser.

    In certain cases the offset points at "nothing" but has extra meaning
    handling by flags.  These can be used when converting this position
    to a PartPosition.
    """

    line: int = 1
    " Line number, starts counting at 1. "

    offset: int = 0
    " Offset into the line, starts counting at 0. "

    eol: bool = False
    " Offset to the NL at the end of line. "

    eof: bool = False
    " Offset to the end of the input, there is no line terminator."


def precompute_line_to_part_pos(
    source_text_parts: tuple[str, ...],
) -> dict[int, PartPosition]:
    line_to_part_pos = {1: PartPosition(0, 0)}
    line = 1
    for index, part_text in enumerate(source_text_parts):
        start = 0
        while 1:
            nl_index = part_text.find("\n", start)
            if nl_index != -1:
                line += 1
                start = nl_index + 1
                line_to_part_pos[line] = PartPosition(index, start)
            else:
                break
    return line_to_part_pos


def make_parser_pos_translator(
    template: Template, config: PlaceholderConfig
) -> ParserPositionTranslator:

    source_text_parts = tuple(
        template.strings[index // 2]
        if index % 2 == 0
        else config.make_placeholder((index - 1) // 2)
        for index in range(2 * len(template.strings) - 1)
    )
    source_text_lines = tuple("".join(source_text_parts).split("\n"))

    line_to_part_pos = precompute_line_to_part_pos(source_text_parts)

    return ParserPositionTranslator(
        source_text_parts, source_text_lines, line_to_part_pos
    )


@dataclass
class ParserPositionTranslator:
    source_text_parts: tuple[str, ...]
    " The source text of each template part, with placeholders. "

    source_text_lines: tuple[str, ...]
    " The source text of the entire template, with placeholders. "

    line_to_part_pos: dict[int, PartPosition]
    " Precomputed mapping from line number to part position. "

    def validate_raw_parser_pos(
        self,
        raw_parser_pos: LinePosition,
        coerce_eol: bool = True,
        coerce_eof: bool = True,
    ) -> ParserPosition:
        """
        Check parser position targets existing line and offset in template.

        This attempts to reduce the complexity of the translating by letting us
        assume the translation is possible.
        """
        line = raw_parser_pos.line
        offset = raw_parser_pos.offset
        if line > len(self.source_text_lines):
            raise ValueError("Line does not exist in source.")
        elif line <= 0:
            raise ValueError("Unreachable line number, must be > 0.")
        # either eol or eof
        end_index = len(self.source_text_lines[line - 1])
        last_line = len(self.source_text_lines)  # 1-based
        eof = False
        eol = False
        if offset < 0:
            raise ValueError("Unreachable offset, must be >= 0.")
        elif offset == end_index and line == last_line:
            if coerce_eof:
                eof = True
            else:
                raise ValueError(
                    f"Offset exceeds reachable characters of last line and coerce EOF is off: {line}: {offset} == {end_index}"
                )
        elif offset == end_index and line != last_line:
            if coerce_eol:
                eol = True
            else:
                raise ValueError(
                    f"Offset exceeds reachable characters of line terminated with newline and coerce EOL is off: {line}: {offset} == {end_index}"
                )
        elif offset >= end_index:
            raise ValueError(
                f"Offset exceeds reachable characters of line: {line}: {offset} >= {end_index}"
            )
        return ParserPosition(line=line, offset=offset, eol=eol, eof=eof)

    def translate(self, pos: LinePosition) -> PartPosition:
        parser_pos = self.validate_raw_parser_pos(pos)
        part_pos = parser_pos_to_part_pos(
            self.source_text_parts, parser_pos, self.line_to_part_pos
        )
        validate_part_position(part_pos)
        return part_pos


def parser_pos_to_part_pos(
    parts: tuple[str, ...],
    parser_pos: ParserPosition,
    line_to_part_pos: dict[int, PartPosition],
) -> PartPosition:
    """
    Translate the given parser position into a template part position.

    - Jump to the precomputed part position for the given line.
    - Iterate over the subsequent template parts.
    - Track the offset while advancing into each part.
    - When we reach the parser position then return the current part
        and the current offset from the start of that part.

    """
    pos = MutableLinePosition(line=parser_pos.line, offset=0)
    part_pos = line_to_part_pos[parser_pos.line]
    start_text = parts[part_pos.index][part_pos.offset :]
    last_index = len(parts) - 1
    for index, part_text in enumerate(
        (start_text, *parts[part_pos.index + 1 :]), start=part_pos.index
    ):
        # got enough lines, we just need more offset
        first_nl_index = part_text.find("\n")
        offset_found = (
            len(part_text[:first_nl_index]) if first_nl_index != -1 else len(part_text)
        )
        offset_need = parser_pos.offset - pos.offset
        part_offset = 0 if index != part_pos.index else part_pos.offset
        if offset_found > offset_need:
            pos.offset += offset_need
            part_offset += offset_need
            return PartPosition(index, part_offset)
        elif offset_found == offset_need:
            part_offset += offset_need
            if first_nl_index == -1:
                if index != last_index:
                    return PartPosition(index + 1, 0)
                elif parser_pos.eof:  # index is last_index
                    return PartPosition(index, part_offset)
                else:
                    # This is the last index, a string,
                    # and the parser position is pointing off the end.
                    raise ValueError(
                        "Configured parser position lands at EOF but eof is False."
                    )
            else:
                if parser_pos.eol:
                    return PartPosition(index, part_offset)
                else:
                    raise ValueError(
                        "Configured parser position lands at EOL but eol is False."
                    )
        else:
            pos.offset += offset_found
    raise AssertionError(
        f"Unexpected position {pos}, did not reach required position {parser_pos}"
    )
