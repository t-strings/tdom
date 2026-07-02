import typing as t
from dataclasses import dataclass
from string.templatelib import Interpolation, Template

from .template_utils import PartPosition, TemplateRef, slice_from_template


@dataclass(slots=True, frozen=True)
class LinePosition:
    "A immutable position in a block of source code."

    line: int = 1
    " Line of code, starts at 1. "
    offset: int = 0
    " Offset from the start of the line, starts at 0. "


@dataclass(slots=True)
class MutableLinePosition:
    "A mutable position in a block of source code."

    line: int = 1
    " Line of code, starts at 1. "
    offset: int = 0
    " Offset from the start of the line, starts at 0. "

    def freeze(self) -> LinePosition:
        "Freeze ourself into an immutable object with the same values."
        return LinePosition(line=self.line, offset=self.offset)


def template_repr_iter(template: Template) -> t.Generator[str]:
    """
    Yield a string representation of each part of a given template.

    @NOTE: This will not yield empty strings because it uses the underlying
    template iterator which does not.
    """
    for part in template:
        if isinstance(part, str):
            yield part
        else:
            yield interpolation_repr(part)


def template_repr(template: Template) -> str:
    """
    Create a string representation of the given template.
    """
    return "".join(template_repr_iter(template))


def interpolation_repr(ip: Interpolation) -> str:
    """
    Create a string representation of the given interpolation.
    """
    expr_str = ip.expression
    conversion_str = f"!{ip.conversion}" if ip.conversion is not None else ""
    format_spec_str = f":{ip.format_spec}" if ip.format_spec else ""
    return f"{{{expr_str}{conversion_str}{format_spec_str}}}"


@dataclass
class SourceReader:
    "Format report-like strings from template source for error reporting."

    template: Template

    def ref_to_repr(self, ref: TemplateRef, limit: int | None = None) -> str:
        """
        Convert tref to string representation of the underlying template.
        """
        filled_template = ref.resolve(self.template.interpolations)
        return template_repr(filled_template)[:limit]

    def make_template_pos_msg(self, source_pos: PartPosition) -> str:
        """
        Make a message to display the line number and offset number.
        """
        template_pos = self.to_template_pos(source_pos)
        return f"line {template_pos.line} offset {template_pos.offset}"

    def to_template_pos(self, source_pos: PartPosition) -> LinePosition:
        """
        Convert a (template) part position into a line position based on the
        string representation of the template.
        """
        pos = MutableLinePosition()
        for part in slice_from_template(self.template, start=None, stop=source_pos):
            if isinstance(part, str):
                text = part
            else:
                text = interpolation_repr(part)
            nls = text.count("\n")
            if nls:
                pos.offset = len(text) - (text.rfind("\n") + 1)
                pos.line += nls
            else:
                pos.offset += len(text)
        return pos.freeze()
