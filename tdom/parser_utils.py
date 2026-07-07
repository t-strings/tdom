from dataclasses import dataclass
from string.templatelib import Template

from .placeholders import PlaceholderConfig
from .source import LinePosition, MutableLinePosition
from .template_utils import PartPosition

type HTMLAttribute = tuple[str, str | None]


def make_parser_pos_translator(
    template: Template, config: PlaceholderConfig
) -> ParserPositionTranslator:
    # Precompute these.
    source_text_parts = tuple(
        template.strings[index // 2]
        if index % 2 == 0
        else config.make_placeholder((index - 1) // 2)
        for index in range(2 * len(template.strings) - 1)
    )
    source_text_lines = tuple("".join(source_text_parts).split("\n"))
    return ParserPositionTranslator(source_text_parts, source_text_lines)


@dataclass
class ParserPositionTranslator:
    source_text_parts: tuple[str, ...]
    " The source text of each template part, with placeholders. "

    source_text_lines: tuple[str, ...]
    " The source text of the entire template, with placeholders. "

    def validate(self, parser_pos: LinePosition):
        """
        Check parser position targets existing line and offset in template.

        This attempts to reduce the complexity of the translating by letting us
        assume the translation is possible.
        """
        if parser_pos.line > len(self.source_text_lines):
            raise ValueError("Line does not exist in source.")
        elif parser_pos.line <= 0:
            raise ValueError("Unreachable line number, must be > 0.")
        # @NOTE: This includes an offset that is at the end of the line.
        last_index = len(self.source_text_lines[parser_pos.line - 1])
        if parser_pos.offset > last_index:
            raise ValueError(
                f"Offset exceeds reachable characters or EOL in source line {parser_pos.line}: {parser_pos.offset} > {last_index}"
            )
        elif parser_pos.offset < 0:
            raise ValueError("Unreachable offset, must be >= 0.")

    def translate(self, parser_pos: LinePosition) -> PartPosition:
        self.validate(parser_pos)
        part_pos = parser_pos_to_part_pos(self.source_text_parts, parser_pos)
        if part_pos.index % 2 != 0 and part_pos.offset != 0:
            # You can only land on the start of an interpolation
            # There is no way to translate a position within a placeholder
            # to a position within the original interpolation representation.
            raise ValueError(
                "Invalid parser position results in offset within interpolation!"
            )
        return part_pos


def parser_pos_to_part_pos(
    parts: tuple[str, ...],
    parser_pos: LinePosition,
) -> PartPosition:
    """
    Translate the given parser position into a template part position.

    - Iterate over the template parts.
    - Track the current line and offset while advancing into each part.
    - When we reach the parser position then return the current part
        and the current offset from the start of that part.

    """
    pos = MutableLinePosition()
    last_index = len(parts) - 1
    for index, part_text in enumerate(parts):
        nls_found = part_text.count("\n")
        if parser_pos.line > pos.line:  # need more lines
            nls_need = parser_pos.line - pos.line  # how many are needed?
            if nls_found >= nls_need:
                pos.line += nls_need
                lines_found = part_text.split("\n")
                offset_found = len(lines_found[nls_need])
                if offset_found >= parser_pos.offset:
                    # needed lines, found lines, found offset
                    pos.offset = parser_pos.offset
                    total_offset = (
                        sum(len(line) + 1 for line in lines_found[:nls_need])
                        + parser_pos.offset
                    )
                    return PartPosition(index, total_offset)
                else:
                    # got enough lines, still need more offset
                    pos.offset = offset_found
            elif nls_found > 0:
                # some lines but still need more lines
                last_nl_index = part_text.rfind("\n")
                pos.line += nls_found
                pos.offset = len(part_text[last_nl_index + 1 :])
            else:
                # no lines, still need more lines
                pos.offset += len(part_text)
        elif parser_pos.line == pos.line:
            # got enough lines, we just need more offset
            first_nl_index = part_text.find("\n")
            offset_found = (
                len(part_text[:first_nl_index]) if nls_found else len(part_text)
            )
            offset_need = parser_pos.offset - pos.offset
            if offset_found > offset_need:
                pos.offset += offset_need
                total_offset = offset_need
                # had lines, found offset
                return PartPosition(index, total_offset)
            elif offset_found == offset_need:
                if index != last_index and first_nl_index == -1:
                    return PartPosition(index + 1, 0)
                else:
                    return PartPosition(last_index, offset_found)
            else:
                pos.offset += offset_found
        else:
            # We should have dropped out and failed earlier this would be a bug.
            raise AssertionError(
                f"Unexpected line: {pos.line} greater than asked for {parser_pos.line}"
            )
    raise AssertionError(
        "Unexpected position {pos}, did not reach required position {parser_pos}"
    )
