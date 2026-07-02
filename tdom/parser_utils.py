from string.templatelib import Template

from .placeholders import PlaceholderConfig
from .source import LinePosition, MutableLinePosition
from .template_utils import PartPosition

type HTMLAttribute = tuple[str, str | None]


def parser_pos_to_part_pos(
    template: Template,
    placeholder_config: PlaceholderConfig,
    parser_pos: LinePosition,
) -> PartPosition:
    """
    Translate the given parser position into a template part position.
    """
    pos = MutableLinePosition()
    combined_size = 2 * len(template.strings) - 1
    last_index = combined_size - 1
    for index in range(combined_size):
        if index % 2 == 0:
            s = template.strings[index // 2]
            if parser_pos.line > pos.line:
                # need more lines
                nls_found = s.count("\n")  # how many were found?
                nls_need = parser_pos.line - pos.line  # how many are needed?
                if nls_found >= nls_need:
                    pos.line += nls_need
                    offset_found = len(s.split("\n", nls_need + 1)[nls_need])
                    if offset_found >= parser_pos.offset:
                        # needed lines, found lines, found offset
                        pos.offset = parser_pos.offset
                        total_offset = (
                            sum(
                                len(line) + 1
                                for line in s.split("\n", nls_need + 1)[:nls_need]
                            )
                            + parser_pos.offset
                        )
                        return PartPosition(index, total_offset)
                    else:
                        # got enough lines, still need more offset
                        pos.offset = offset_found
                elif nls_found > 0:
                    # some lines but still need more lines
                    pos.line += nls_found
                    pos.offset = len(s[s.rfind("\n") + 1 :])
                else:
                    # no lines, still need more lines
                    offset_found = len(s)
                    pos.offset += offset_found
            elif parser_pos.line == pos.line:
                # got enough lines, we just need more offset
                offset_found = len(s[: s.find("\n")]) if "\n" in s else len(s)
                offset_need = parser_pos.offset - pos.offset
                if offset_found > offset_need:
                    pos.offset += offset_need
                    total_offset = offset_need  # only from the start of this string.
                    # had lines, found offset
                    return PartPosition(index, total_offset)
                elif offset_found == offset_need:
                    if index < last_index:
                        # @TODO: Start at the interpolation ?
                        return PartPosition(index + 1, 0)
                    else:
                        # @TEST
                        # @TODO: Is this possible?  Seems like this position would
                        # technically be undefined and an error.
                        #  Start at the very end of the last part (can this exist?)
                        return PartPosition(index, len(s))
                else:
                    pos.offset += offset_found
            else:
                # We should have dropped out and failed earlier this would be a bug.
                raise AssertionError(
                    f"Unexpected line: {pos.line} greater than asked for {parser_pos.line}"
                )

        else:
            i_index = (index - 1) // 2
            ph_length = len(placeholder_config.make_placeholder(i_index))
            if (
                pos.line == parser_pos.line
                and pos.offset + ph_length > parser_pos.offset
            ):
                # Ie. we don't know how to determine how much of the
                # interpolation expression would be equivalent to
                # a substring of a placeholder.
                raise ValueError(
                    f"Cannot split a placeholder for interpolations[{i_index}], placeholders are atomic."
                )
            pos.offset += ph_length
            if pos == parser_pos:
                # An offset to the end of this interpolation should be the start
                # of the following string.
                # @TEST
                # @TODO: Do we need this check or would it be picked up
                # in the next iteration?
                return PartPosition(index + 1, 0)
    if pos == parser_pos:
        # @TEST
        # @TODO: When can this fall through happen? Or is this always an error?
        return PartPosition(last_index, len(template.strings[-1]))
    else:
        raise ValueError(
            "Unexpected position {pos}, did not reach required position {parser_pos}"
        )
