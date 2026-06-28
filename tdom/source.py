import typing as t
from dataclasses import dataclass
from string.templatelib import Interpolation, Template

from .parser_utils import HTMLAttribute
from .placeholders import PlaceholderConfig
from .template_utils import TemplateRef


@dataclass(slots=True, frozen=True)
class FrozenPosition:
    "A immutable position in a block of source code."

    line: int = 1
    " Line of code, starts at 1. "
    offset: int = 0
    " Offset from the start of the line, starts at 0. "


@dataclass(slots=True)
class Position:
    "A position in a block of source code."

    line: int = 1
    " Line of code, starts at 1. "
    offset: int = 0
    " Offset from the start of the line, starts at 0. "

    def freeze(self) -> FrozenPosition:
        return FrozenPosition(line=self.line, offset=self.offset)


@dataclass(frozen=True, slots=True)
class TagSourceInfo:
    """
    Retained tag information from the parsed source.

    @NOTE: These properties DEPEND on the placeholder configuration because
    they can contain embedded placeholders.
    """

    starttag_text: str
    " Entire starttag as parsed, includes placeholders, . "
    raw_attrs: tuple[HTMLAttribute, ...]
    " Attrs as parsed, includes placeholders. "
    startend: bool
    " Was parsed as startend tag, ie. <tag />. "
    starttag_pos: FrozenPosition
    " Position of the parser when the element starttag was parsed. "
    endtag_pos: FrozenPosition | None = None
    " Position of the parser when the element endtag was parsed. "


@dataclass(frozen=True)
class MultiPosition:
    """
    @NOTE: Like other position tools this does not support positioning within
    an interpolation.  Either you are at the start of interpolation or at an
    offset within a string.
    """

    pos: FrozenPosition
    tpos: FrozenPosition
    s_index: int
    s_offset: int
    i_index: int


def iterate_template_from_s_index(template: Template, s_index: int):
    last_index = len(template.strings) - 1
    if s_index < 0 or s_index > last_index:
        return
    index = 0
    while index <= last_index:
        yield template.strings[index]
        if index < last_index:
            yield template.interpolations[index]
        index += 1


def iterate_template_from_i_index(template: Template, i_index: int):
    last_index = len(template.strings) - 1
    if i_index < 0 or i_index >= last_index:
        return
    index = 0
    while index <= last_index:
        if index < last_index:
            yield template.interpolations[index]
        index += 1
        yield template.strings[index]


def template_repr_iter(template: Template) -> t.Generator[str]:
    for part in template:
        if isinstance(part, str):
            yield part
        else:
            yield interpolation_repr(part)


def template_repr(template: Template) -> str:
    return "".join(template_repr_iter(template))


def interpolation_repr(ip: Interpolation) -> str:
    expr_str = ip.expression
    conversion_str = f"!{ip.conversion}" if ip.conversion is not None else ""
    format_spec_str = f":{ip.format_spec}" if ip.format_spec else ""
    return f"{{{expr_str}{conversion_str}{format_spec_str}}}"


@dataclass
class SourceReader:
    "Format report-like strings from template source for the parser."

    template: Template

    placeholder_config: PlaceholderConfig

    def ref_to_repr(self, ref: TemplateRef, limit: int | None = None) -> str:
        filled_template = ref.resolve(self.template.interpolations)
        return template_repr(filled_template)[:limit]

    def make_template_pos_msg(self, parser_pos: FrozenPosition) -> str:
        template_pos = self.to_template_pos(parser_pos)
        return f"line {template_pos.line} offset {template_pos.offset}"

    def to_template_pos(self, parser_pos: FrozenPosition) -> FrozenPosition:
        mpos = self._compute_positions(parser_pos)
        return mpos.tpos

    def make_template_slice(self, parser_pos: FrozenPosition, limit: int | None = None):
        mpos = self._compute_positions(parser_pos)
        if mpos.s_index > mpos.i_index:
            sub_template = Template(
                *iterate_template_from_s_index(self.template, mpos.s_index)
            )
            return template_repr(sub_template)[mpos.s_offset : limit]
        else:
            sub_template = Template(
                *iterate_template_from_i_index(self.template, mpos.i_index)
            )
            return template_repr(sub_template)[:limit]

    def _compute_positions(self, parser_pos: FrozenPosition) -> MultiPosition:
        return compute_template_positions(
            self.template, self.placeholder_config, parser_pos
        )


def compute_template_positions(
    template: Template,
    placeholder_config: PlaceholderConfig,
    parser_pos: FrozenPosition,
) -> MultiPosition:
    """
    Translate the given parser (pos)ition into template (pos)ition.

    @NOTE: There can be newlines in an interpolation expression which
    results in the parser position's line being less than the
    template position's line since a placeholder will not contain newlines.

    @NOTE: Similarly an interpolation as displayed can be longer than a
    placeholder OR shorter than a placeholder causing the offsets to go
    out of sync.

    @NOTE: There is a weird issue with `format_spec` and the specification
    where you can't tell if a ':' was used or not when the `format_spec` is
    empty.  We just assume no one would leave it in without a non-empty
    format_spec, ie. t"{val:}" would not exist even though it is valid. The
    conversion does not have this issue because "{val!}" is invalid and when
    no conversion is set the conversion value is None.
    """
    #
    # Walk until we reach the given parser pos, keeping both parser position
    # and template position in sync.  When the given parser position is reached
    # then return the synced up template position.
    #
    pos = Position()
    tpos = Position()
    last_s_index = len(template.strings) - 1
    for s_index in range(len(template.strings)):
        #
        # Walk through `strings[s_index]`
        #
        s = template.strings[s_index]
        if parser_pos.line > pos.line:
            # need more lines
            nls_found = s.count("\n")  # how many were found?
            nls_need = parser_pos.line - pos.line  # how many are needed?
            if nls_found >= nls_need:
                pos.line += nls_need
                tpos.line += nls_need
                offset_found = len(s.split("\n", nls_need + 1)[nls_need])
                if offset_found >= parser_pos.offset:
                    # needed lines, found lines, found offset
                    tpos.offset = pos.offset = parser_pos.offset
                    total_offset = (
                        sum(
                            len(line) + 1
                            for line in s.split("\n", nls_need + 1)[:nls_need]
                        )
                        + parser_pos.offset
                    )
                    return MultiPosition(
                        pos=parser_pos,
                        tpos=tpos.freeze(),
                        s_index=s_index,
                        i_index=s_index - 1,
                        s_offset=total_offset,
                    )
                else:
                    # got enough lines, still need more offset
                    tpos.offset = pos.offset = offset_found
            elif nls_found > 0:
                # some lines but still need more lines
                pos.line += nls_found
                tpos.line += nls_found
                tpos.offset = pos.offset = len(s[s.rfind("\n") + 1 :])
            else:
                # no lines, still need more lines
                offset_found = len(s)
                tpos.offset += offset_found
                pos.offset += offset_found
        elif parser_pos.line == pos.line:
            # got enough lines, we just need more offset
            offset_found = len(s[: s.find("\n")]) if "\n" in s else len(s)
            offset_need = parser_pos.offset - pos.offset
            if offset_found >= offset_need:
                pos.offset += offset_need
                tpos.offset += offset_need
                total_offset = offset_need  # only from the start of this string.
                # had lines, found offset
                return MultiPosition(
                    pos=parser_pos,
                    tpos=tpos.freeze(),
                    s_index=s_index,
                    i_index=s_index - 1,
                    s_offset=total_offset,
                )
            else:
                tpos.offset += offset_found
                pos.offset += offset_found
        else:
            # We should have dropped out and failed earlier this would be a bug.
            raise AssertionError(
                f"Unexpected line: {pos.line} greater than asked for {parser_pos.line}"
            )

        #
        # Walk through `interpolations[s_index]`
        #
        if s_index < last_s_index:
            ph_length = len(placeholder_config.make_placeholder(s_index))
            if (
                pos.line == parser_pos.line
                and pos.offset + ph_length > parser_pos.offset
            ):
                # Ie. we don't know how to determine how much of the
                # interpolation expression would be equivalent to
                # a substring of a placeholder.
                raise ValueError(
                    f"Cannot split a placeholder for interpolations[{s_index}], placeholders are atomic."
                )

            ip = template.interpolations[s_index]
            expr = ip.expression
            expr_line_count = expr.count("\n")
            tpos.line += expr_line_count
            pos.offset += ph_length
            EXCLAIMATION_POINT = CONVERSION_CHAR = SEMICOLON = LEFT_CURLY_BRACE = (
                RIGHT_CURLY_BRACE
            ) = 1
            tail = (
                (
                    EXCLAIMATION_POINT + CONVERSION_CHAR
                    if ip.conversion is not None
                    else 0
                )  # "!" and conversion char or neither
                + (SEMICOLON if ip.format_spec else 0)  # ":" or not
                + len(ip.format_spec)
                + RIGHT_CURLY_BRACE
            )
            if expr_line_count > 0:
                tpos.offset = len(expr[expr.rfind("\n") + 1 :]) + tail
            else:
                tpos.offset += LEFT_CURLY_BRACE + len(expr) + tail
            if pos == parser_pos:
                return MultiPosition(
                    pos=parser_pos,
                    tpos=tpos.freeze(),
                    s_index=s_index,
                    i_index=s_index,
                    s_offset=0,
                )
    if pos == parser_pos:
        # @TODO: When can this fall through happen? Or is this always an error?
        return MultiPosition(
            pos=parser_pos,
            tpos=tpos.freeze(),
            s_index=len(template.strings) - 1,
            i_index=len(template.strings) - 2,
            s_offset=len(template.strings[-1]),
        )
    else:
        raise ValueError(
            "Unexpected position {pos}, did not reach required position {parser_pos}"
        )
